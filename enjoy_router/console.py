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
# Failed key attempts: 10 per 10 minutes per visitor, then 429. Only failures are counted.
FAILURE_RULES = ((600, 10),)
SINCE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")  # same shape as stored created_at
log = logging.getLogger("enjoy_router")


def make_failure_limiter() -> RateLimiter:
    return RateLimiter(rules=FAILURE_RULES)


def list_registration_requests(store, limit: int = DEFAULT_LIMIT, since: Optional[str] = None) -> list:
    """Newest first. since (an ISO string) keeps only records created at or after it."""
    limit = max(1, min(int(limit), MAX_LIMIT))
    # completion_token is the secret in the receipt-email link: it never goes to the Console
    # coverage_waiting is worked out here on every read (not stored): the request is urgent, nobody handled it, and no active region holds its ZIP yet
    # a request marked deleted is kept but never shown
    areas = store.list_areas()
    return [dict({k: v for k, v in d.items() if k != "completion_token"}, **({"coverage_waiting": True} if request_coverage.is_open(areas, d) else {}))
            for d in store.list_requests(limit, since) if not d.get("deleted_at")]


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
    if since is not None and not SINCE_PATTERN.match(since):
        return _error(400, "validation_failed", "since must look like 2026-10-09T04:26:57Z.")

    try:
        scope = None if access.is_super_admin or access.inspector else Scope(access, Territory(access_store))
        if scope is not None and not scope.unlimited:   # a person with limited territory sees only the requests whose ZIP is theirs (P-65)
            wide = list_registration_requests(store, MAX_LIMIT, since)
            records = [r for r in wide if scope.can_read(_policy.RECORDS, _places.zip_of_request(access_store, r))][:max(1, min(limit, MAX_LIMIT))]
        else:
            records = list_registration_requests(store, limit, since)
    except Exception as exc:  # say nothing about the cause
        log.error("console_records code=server_error exception=%s", type(exc).__name__)
        return _error(500, "server_error", "Could not complete the request.")

    if access.inspector:                              # view only: the same requests, with private details hidden or masked (P-78)
        records = _inspect.shape_records(records)
    log.info("console_records code=ok count=%d", len(records))
    body = {"ok": True, "data": {"records": records, "count": len(records),
                                 "server_time": now.strftime("%Y-%m-%dT%H:%M:%SZ")}}
    return HttpResult(200, body, {"Cache-Control": "no-store"})
