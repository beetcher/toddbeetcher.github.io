"""The CRUD test endpoint, with no Firebase in it. A way to exercise the handler files with curl.

main.py turns a Firebase request into handle_crud_test(); tests call it directly.

    POST  ...  Authorization: Bearer <ICDT_ADMIN_KEY>
    body: {"collection": "venues", "op": "create", "args": {...}}

ops and their args:
    create             data, source (optional)
    get                id, include_deleted (optional)
    list               filters, order, limit (all optional)
    update             id, changes, expected_updated_at (optional)
    soft_delete        id
    set_review_summary id, review_count, average_rating

It is a TEST tool: main.py gives it a store whose collection names carry the prefix `test_`, so it can never
read or write a real collection. The actor is always system:crud_test. It is not the way real services will
call the handlers; they call them in-process.

Fails closed like the Console: no admin key setting (or shorter than 32 characters) means nothing is allowed.
Logs only codes, never the key and never record content.
"""
from __future__ import annotations

import hmac
import json
import logging
from datetime import datetime

from console import MIN_KEY_LENGTH, _bearer, make_failure_limiter  # noqa: F401  (make_failure_limiter re-exported)
from crud import venues_crud
from handler import HttpResult, _error
from ratelimit import RateLimiter

log = logging.getLogger("enjoy_router")
ACTOR = "system:crud_test"
MAX_BODY_BYTES = 100_000

# collection -> handler module. A new collection's handler file is added here.
HANDLERS = {"venues": venues_crud}

# op -> (required args, optional args)
OPS = {
    "create": ({"data"}, {"source"}),
    "get": ({"id"}, {"include_deleted"}),
    "list": (set(), {"filters", "order", "limit"}),
    "update": ({"id", "changes"}, {"expected_updated_at"}),
    "soft_delete": ({"id"}, set()),
    "set_review_summary": ({"id", "review_count", "average_rating"}, set()),
}
STATUS = {"validation_failed": 400, "not_found": 404, "conflict": 409, "server_error": 500}


def _run(module, store, op: str, a: dict, now: datetime):
    if op == "create":
        return module.create(store, a["data"], ACTOR, a.get("source", "dashboard"), now=now)
    if op == "get":
        return module.get(store, a["id"], a.get("include_deleted", False))
    if op == "list":
        kw = {k: a[k] for k in ("order", "limit") if k in a}
        return module.list(store, a.get("filters"), **kw)
    if op == "update":
        return module.update(store, a["id"], a["changes"], ACTOR, a.get("expected_updated_at"), now=now)
    if op == "soft_delete":
        return module.soft_delete(store, a["id"], ACTOR, now=now)
    return module.set_review_summary(store, a["id"], a["review_count"], a["average_rating"], now=now)


def handle_crud_test(method: str, authorization: str, raw_body: bytes, admin_key: str, visitor: str,
                     store, limiter: RateLimiter, now: datetime) -> HttpResult:
    if method.upper() != "POST":
        return _error(405, "validation_failed", "Use POST.", {"Allow": "POST"})

    if not admin_key or len(admin_key) < MIN_KEY_LENGTH:
        log.error("crud_test code=not_configured")
        return _error(401, "unauthorized", "Unauthorized.")

    ts = now.timestamp()
    wait = limiter.retry_after(visitor, ts)
    if wait:
        log.info("crud_test code=rate_limited")
        return _error(429, "rate_limited", "Too many attempts. Try again later.", {"Retry-After": str(wait)})

    given = _bearer(authorization)
    if not given or not hmac.compare_digest(given.encode("utf-8"), admin_key.encode("utf-8")):
        limiter.allow(visitor, ts)
        log.info("crud_test code=unauthorized")
        return _error(401, "unauthorized", "Unauthorized.")

    if len(raw_body) > MAX_BODY_BYTES:
        return _error(413, "validation_failed", "The request is too large.")
    try:
        body = json.loads(raw_body.decode("utf-8")) if raw_body else None
    except (UnicodeDecodeError, ValueError):
        return _error(400, "validation_failed", "The request body must be JSON.")
    if not isinstance(body, dict):
        return _error(400, "validation_failed", "Send a JSON object with collection, op and args.")

    collection, op, args = body.get("collection"), body.get("op"), body.get("args", {})
    if collection not in HANDLERS:
        return _error(400, "validation_failed", "Unknown collection. Known: " + ", ".join(sorted(HANDLERS)) + ".")
    if op not in OPS:
        return _error(400, "validation_failed", "Unknown op. Known: " + ", ".join(sorted(OPS)) + ".")
    if not isinstance(args, dict):
        return _error(400, "validation_failed", "args must be an object.")
    required, optional = OPS[op]
    missing, extra = sorted(required - set(args)), sorted(set(args) - required - optional)
    if missing or extra:
        return _error(400, "validation_failed",
                      f"For {op}: " + (f"missing {', '.join(missing)}. " if missing else "")
                      + (f"not allowed: {', '.join(extra)}." if extra else ""))

    try:
        result = _run(HANDLERS[collection], store, op, args, now)
    except Exception as exc:  # say nothing about the cause
        log.error("crud_test code=server_error op=%s exception=%s", op, type(exc).__name__)
        return _error(500, "server_error", "Could not complete the request.")

    if result.ok:
        log.info("crud_test collection=%s op=%s code=ok", collection, op)
        return HttpResult(200, {"ok": True, "data": result.data}, {"Cache-Control": "no-store"})
    log.info("crud_test collection=%s op=%s code=%s", collection, op, result.code)
    res = _error(STATUS.get(result.code, 400), result.code, "The request was refused.")
    res.body["error"]["problems"] = result.problems
    return res
