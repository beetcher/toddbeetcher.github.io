"""The completion link: a person who got the receipt email can open the link, see what they gave, and fill in the optional details of
THAT request. GET ?t=<token> reads it; POST {"t": token, "changes": {...}} updates it. It never creates a request.

Rules (Todd, 2026-10-14): name and email are shown but cannot be changed through the link; only optional details change; once the request is
placed in a class the link stops accepting changes; the link does not expire. Only private requests have a link in M1. The token is a
long random secret stored on the request (completion_token); it is never returned to the page or shown in the Console. Whoever holds the link
can read the answers on that one request. Logs record codes only, never values.

main.py turns a Firebase request into handle_completion(); tests call it directly.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from core import HONEYPOT, TIME_ZONE, _date_before, _field_errors, utc_stamp
from crud import attendances_service as ATT
from crud.store_errors import DocMissing, StaleUpdate
from handler import HttpResult, _error
from ratelimit import RateLimiter

log = logging.getLogger("enjoy_router")
COLLECTION = "registration_requests"
TOKEN = re.compile(r"^[A-Za-z0-9_-]{43}$")
ACTOR = "web:completion"
MAX_BODY_BYTES = 64 * 1024
# What the link may never change: who the request is from, what was agreed, and anything that belongs to a class pick.
LOCKED = frozenset({"registration_type", "idempotency_key", "first_name", "last_name", "email", "consent_to_contact",
                    "presented_cost_cents", "presented_cost_basis", "scheduled_class_id", "no_class_fits"})
SHOWN_IDENTITY = ("first_name", "last_name", "email")


def editable_fields(schemas) -> frozenset:
    return frozenset(k for k in schemas.schema["properties"] if k not in schemas.read_only and k not in LOCKED and k != HONEYPOT)


def find(store, token):
    """The live private request holding this token, or None."""
    if not isinstance(token, str) or not TOKEN.match(token):
        return None
    for d in store.query(COLLECTION, [("completion_token", "==", token)], limit=2):
        if not d.get("deleted_at") and d.get("registration_type") == "private":
            return d
    return None


def is_placed(store, doc) -> bool:
    return ATT._still_placed(store, doc["id"], set())


def view(store, schemas, doc) -> dict:
    keep = editable_fields(schemas) | set(SHOWN_IDENTITY)
    return {"confirmation_number": doc["confirmation_number"], "registration_type": doc["registration_type"],
            "editable": not is_placed(store, doc), "answers": {k: v for k, v in doc.items() if k in keep}}


def _json_error(status, code, message, fields=None):
    r = _error(status, code, message)
    if fields:
        r.body["error"]["field_errors"] = fields
    return r


def handle_completion(method: str, params: dict, raw_body: bytes, visitor: str, store, schemas, limiter: RateLimiter, now: datetime) -> HttpResult:
    method = method.upper()
    if method not in ("GET", "POST"):
        return _error(405, "validation_failed", "Use GET or POST.", {"Allow": "GET, POST"})
    if not limiter.allow(visitor, now.timestamp()):
        wait = limiter.retry_after(visitor, now.timestamp())
        return _error(429, "rate_limited", "Too many requests. Try again later.", {"Retry-After": str(wait)} if wait else {})
    try:
        if method == "GET":
            return _get(params, store, schemas)
        return _post(raw_body, store, schemas, now)
    except Exception as exc:  # say nothing about the cause
        log.error("request_completion code=server_error exception=%s", type(exc).__name__)
        return _error(500, "server_error", "Could not complete the request.")


def _get(params, store, schemas) -> HttpResult:
    doc = find(store, (params or {}).get("t"))
    if doc is None:
        log.info("request_completion op=get code=not_found")
        return _error(404, "not_found", "That link is not valid.")
    data = view(store, schemas, doc)
    log.info("request_completion op=get code=ok editable=%s", data["editable"])
    return HttpResult(200, {"ok": True, "data": data}, {"Cache-Control": "no-store"})


def _post(raw_body, store, schemas, now) -> HttpResult:
    if len(raw_body) > MAX_BODY_BYTES:
        return _error(413, "validation_failed", "The request is too large.")
    try:
        body = json.loads(raw_body.decode("utf-8")) if raw_body else None
    except (UnicodeDecodeError, ValueError):
        body = None
    if not isinstance(body, dict) or not isinstance(body.get("changes"), dict):
        return _error(400, "validation_failed", "The request body must be a JSON object with changes.")
    if body.get(HONEYPOT):   # a bot: look successful, change nothing
        return HttpResult(200, {"ok": True, "data": {"updated": True}}, {"Cache-Control": "no-store"})
    doc = find(store, body.get("t"))
    if doc is None:
        log.info("request_completion op=post code=not_found")
        return _error(404, "not_found", "That link is not valid.")
    if is_placed(store, doc):
        log.info("request_completion op=post code=already_scheduled")
        return _error(409, "already_scheduled", "This request is already scheduled. Reply to the email to change it.")
    allowed = editable_fields(schemas)
    bad = sorted(k for k in body["changes"] if k not in allowed)
    if bad:
        return _json_error(400, "validation_failed", "Some answers cannot be changed here.", [{"field": k, "issue": "not_allowed"} for k in bad])
    sets = {k: v for k, v in body["changes"].items() if v is not None}
    removals = sorted(k for k, v in body["changes"].items() if v is None and k in doc)
    merged = {k: v for k, v in doc.items() if k not in removals}
    merged.update(sets)
    errors = list(schemas.validator.iter_errors(merged))
    if errors:
        return _json_error(400, "validation_failed", "The request did not pass validation.", _field_errors(errors, merged, schemas.schema))
    today = now.astimezone(TIME_ZONE).date()
    past = [k for k in ("requested_date", "alternate_requested_date") if k in sets and _date_before(sets[k], today)]
    if past:
        return _json_error(400, "validation_failed", "A requested date is in the past.", [{"field": k, "issue": "out_of_range"} for k in past])
    if "attendee_count" in merged and len(merged.get("participants", [])) + (1 if merged.get("is_requester_attending") else 0) > merged["attendee_count"]:
        return _json_error(400, "validation_failed", "More people are named than the attendee count.", [{"field": "participants", "issue": "out_of_range"}])
    venue_id = sets.get("preferred_venue_id")
    if venue_id:
        v = store.get("venues", venue_id)
        if v is None or v.get("deleted_at") or v.get("status") != "active" or v.get("is_public_venue") is not True:
            return _error(404, "venue_not_found", "That venue was not found.")
    cid = sets.get("curriculum_id")
    if cid:
        c = store.get("curriculums", cid)
        if c is None or c.get("deleted_at") or c.get("status") != "active":
            return _error(404, "curriculum_not_found", "That curriculum was not found.")
    if not sets and not removals:
        return HttpResult(200, {"ok": True, "data": {"updated": False, "confirmation_number": doc["confirmation_number"]}}, {"Cache-Control": "no-store"})
    try:
        store.update(COLLECTION, doc["id"], {**sets, "updated_at": utc_stamp(now), "updated_by": ACTOR}, removals, expected_updated_at=doc["updated_at"])
    except StaleUpdate:
        return _error(409, "conflict", "This changed a moment ago. Please try again.")
    except DocMissing:
        return _error(404, "not_found", "That link is not valid.")
    log.info("request_completion op=post code=updated n=%d", len(sets) + len(removals))
    return HttpResult(200, {"ok": True, "data": {"updated": True, "confirmation_number": doc["confirmation_number"]}}, {"Cache-Control": "no-store"})
