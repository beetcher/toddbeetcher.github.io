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
    return store.list_requests(limit, since)


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
) -> HttpResult:
    """params: the query string as a plain dict of strings. now: aware datetime."""
    if method.upper() != "GET":
        return _error(405, "validation_failed", "Use GET.", {"Allow": "GET"})

    if not admin_key or len(admin_key) < MIN_KEY_LENGTH:
        log.error("console_records code=not_configured")
        return _error(401, "unauthorized", "Unauthorized.")

    ts = now.timestamp()
    wait = limiter.retry_after(visitor, ts)
    if wait:
        log.info("console_records code=rate_limited")
        return _error(429, "rate_limited", "Too many attempts. Try again later.", {"Retry-After": str(wait)})

    given = _bearer(authorization)
    if not given or not hmac.compare_digest(given.encode("utf-8"), admin_key.encode("utf-8")):
        limiter.allow(visitor, ts)  # records one failure
        log.info("console_records code=unauthorized")
        return _error(401, "unauthorized", "Unauthorized.")

    try:
        limit = int(params.get("limit", DEFAULT_LIMIT))
    except (TypeError, ValueError):
        return _error(400, "validation_failed", "limit must be a whole number.")
    since = params.get("since")
    if since is not None and not SINCE_PATTERN.match(since):
        return _error(400, "validation_failed", "since must look like 2026-10-09T04:26:57Z.")

    try:
        records = list_registration_requests(store, limit, since)
    except Exception as exc:  # say nothing about the cause
        log.error("console_records code=server_error exception=%s", type(exc).__name__)
        return _error(500, "server_error", "Could not complete the request.")

    log.info("console_records code=ok count=%d", len(records))
    body = {"ok": True, "data": {"records": records, "count": len(records),
                                 "server_time": now.strftime("%Y-%m-%dT%H:%M:%SZ")}}
    return HttpResult(200, body, {"Cache-Control": "no-store"})
