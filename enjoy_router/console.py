"""The Console records endpoint, with no Firebase in it. Read-only, locked by one admin key.

main.py turns a Firebase request into handle_console(); tests call it directly.

    GET  ...  Authorization: Bearer <ICDT_ADMIN_KEY>   optional ?limit=100  optional ?since=<ISO time>

Fails closed: if the admin key setting is missing or shorter than MIN_KEY_LENGTH, nothing is allowed.
Never logs the key or any record content, only codes and counts.
"""
from __future__ import annotations

import hmac
import logging
import re
from datetime import datetime
from typing import Optional

import request_coverage
from access import door as _door, inspect as _inspect, places as _places, policy as _policy
from access.territory import Scope, Territory
from handler import HttpResult, _error
from ratelimit import RateLimiter

MIN_KEY_LENGTH = 32
DEFAULT_LIMIT = 100
MAX_LIMIT = 200
SCAN_MAX = 2000   # a search or region filter looks through this many of the newest requests (Firestore has no text search)
Q_MAX = 80
# Failed key attempts: 10 per 10 minutes per visitor, then 429. Only failures are counted.
FAILURE_RULES = ((600, 10),)
SINCE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")  # same shape as stored created_at
log = logging.getLogger("enjoy_router")


def make_failure_limiter() -> RateLimiter:
    return RateLimiter(rules=FAILURE_RULES)


def list_registration_requests(store, limit: int = DEFAULT_LIMIT, since: Optional[str] = None, deleted: bool = False) -> list:
    """Newest first. since (an ISO string) keeps only records created at or after it. deleted=True returns ONLY the deleted ones (for Restore);
    otherwise a deleted request is kept but never shown."""
    limit = max(1, min(int(limit), MAX_LIMIT))
    if deleted:
        return [{k: v for k, v in d.items() if k != "completion_token"}
                for d in store.list_requests(MAX_LIMIT, since) if d.get("deleted_at")][:limit]
    # completion_token is the secret in the receipt-email link: it never goes to the Console
    # coverage_waiting is worked out here on every read (not stored): the request is urgent, nobody handled it, and no active region holds its ZIP yet
    # a request marked deleted is kept but never shown
    areas = store.list_areas()
    return [dict({k: v for k, v in d.items() if k != "completion_token"}, regions=regions_of(areas, d), **({"coverage_waiting": True} if request_coverage.is_open(areas, d) else {}))
            for d in store.list_requests(limit, since) if not d.get("deleted_at")]


def regions_of(areas, doc) -> list:
    """The live regions a request belongs to, worked out on every read (never stored): those whose ZIP list holds its ZIP, else the region it picked on the form."""
    regions = [a for a in areas if a.get("kind") == "region" and not a.get("deleted_at")]
    z = doc.get("postal_code")
    z = str(z).strip()[:5] if isinstance(z, str) else ""
    hit = [r for r in regions if z and z in {str(x).strip()[:5] for x in r.get("zip_codes", [])}]
    if not hit and doc.get("region_id"):
        hit = [r for r in regions if r.get("id") == doc.get("region_id")]
    return [{"id": r.get("id"), "name": r.get("name") or ""} for r in hit]


def _haystack(doc, view_only=False) -> str:
    keys = ("first_name", "last_name", "email", "phone", "postal_code", "confirmation_number", "preferred_location", "organization_name",
            "referrer_first_name", "referrer_last_name", "referrer_email")
    if view_only:   # a view-only person sees these masked, so searching them would leak them
        keys = tuple(k for k in keys if k not in ("email", "phone", "referrer_email", "preferred_location"))
    parts = [str(doc.get(k) or "") for k in keys] + [r["name"] for r in doc.get("regions", [])]
    text = " ".join(parts).lower()
    return text if view_only else text + " " + re.sub(r"\D", "", str(doc.get("phone") or ""))


def search_requests(store, q: str, region: str, since, only_deleted: bool, access_scope=None, view_only: bool = False):
    """(matches newest first, scanned). The newest SCAN_MAX requests, tagged with their regions, narrowed by q (every word must appear) and by region (an id, or 'none')."""
    areas = store.list_areas()
    raw = store.list_requests(SCAN_MAX, since)
    scanned = len(raw)
    docs = [d for d in raw if bool(d.get("deleted_at")) == only_deleted]
    words = [w for w in q.lower().split() if w]
    out = []
    for d in docs:
        d = dict({k: v for k, v in d.items() if k != "completion_token"}, regions=regions_of(areas, d))
        if access_scope is not None and not access_scope(d):
            continue
        if region == "none" and d["regions"]:
            continue
        if region and region != "none" and region not in {r["id"] for r in d["regions"]}:
            continue
        if words:
            h = _haystack(d, view_only)
            if not all(w in h for w in words):
                continue
        if not only_deleted and request_coverage.is_open(areas, d):
            d["coverage_waiting"] = True
        out.append(d)
    return out, scanned


def _bearer(authorization: str) -> str:
    parts = (authorization or "").split(" ", 1)
    return parts[1].strip() if len(parts) == 2 and parts[0].lower() == "bearer" else ""


def handle_console(
    method: str,
    authorization: str,
    params: dict,
    admin_key: str,
    visitor: str,
    store,
    limiter: RateLimiter,
    now: datetime,
    verifier=None,
    access_store=None,
) -> HttpResult:
    """params: the query string as a plain dict of strings. now: aware datetime. verifier + access_store switch on Google sign-in
    (access_store holds the access_roles / access_persons records); without them only the key works."""
    if method.upper() != "GET":
        return _error(405, "validation_failed", "Use GET.", {"Allow": "GET"})

    access, refusal = _door.sign_in(authorization, admin_key=admin_key, verifier=verifier, store=access_store, limiter=limiter,
                                    visitor=visitor, now=now, tag="console_records")
    if refusal:
        return refusal
    if not access.inspector and not _policy.allowed(access, _policy.RECORDS):
        return _door.forbidden("console_records")

    try:
        limit = int(params.get("limit", DEFAULT_LIMIT))
    except (TypeError, ValueError):
        return _error(400, "validation_failed", "limit must be a whole number.")
    since = params.get("since")
    only_deleted = params.get("deleted") == "1"
    if since is not None and not SINCE_PATTERN.match(since):
        return _error(400, "validation_failed", "since must look like 2026-10-09T04:26:57Z.")

    q = (params.get("q") or "").strip()
    region = (params.get("region") or "").strip()
    if len(q) > Q_MAX or len(region) > 64:
        return _error(400, "validation_failed", "q is at most %d characters." % Q_MAX)

    total = scanned = None
    try:
        scope = None if access.is_super_admin or access.inspector else Scope(access, Territory(access_store))
        if q or region:
            can = None if scope is None or scope.unlimited else (lambda d: scope.can_read(_policy.RECORDS, _places.zip_of_request(access_store, d)))
            found, scanned = search_requests(store, q, region, since, only_deleted, can, bool(access.inspector))
            total = len(found)
            records = found[:max(1, min(limit, MAX_LIMIT))]
        elif scope is not None and not scope.unlimited:   # a person with limited territory sees only the requests whose ZIP is theirs (P-65)
            wide = list_registration_requests(store, MAX_LIMIT, since, only_deleted)
            records = [r for r in wide if scope.can_read(_policy.RECORDS, _places.zip_of_request(access_store, r))][:max(1, min(limit, MAX_LIMIT))]
        else:
            records = list_registration_requests(store, limit, since, only_deleted)
    except Exception as exc:  # say nothing about the cause
        log.error("console_records code=server_error exception=%s", type(exc).__name__)
        return _error(500, "server_error", "Could not complete the request.")

    if access.inspector:                              # view only: the same requests, with private details hidden or masked (P-78)
        records = _inspect.shape_records(records)
    log.info("console_records code=ok count=%d", len(records))
    data = {"records": records, "count": len(records), "server_time": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
    if total is not None:
        data.update(total=total, scanned=scanned, truncated=scanned >= SCAN_MAX)
    body = {"ok": True, "data": data}
    return HttpResult(200, body, {"Cache-Control": "no-store"})
