"""The HTTP-shaped part of the endpoint, with no Firebase in it.

main.py turns a Firebase request into handle_http(); tests call it directly.
It does what is not a registration rule: method, size, JSON, rate limit, and the
last-resort catch so a crash never leaks details. Everything else is core.py.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from core import HTTP_STATUS, Schemas, Store, handle_registration_request
from ratelimit import RateLimiter

MAX_BODY_BYTES = 64 * 1024
log = logging.getLogger("enjoy_router")


@dataclass
class HttpResult:
    status: int
    body: dict
    headers: dict = field(default_factory=dict)


def _error(status: int, code: str, message: str, headers: Optional[dict] = None) -> HttpResult:
    h = {"Cache-Control": "no-store"}
    h.update(headers or {})
    return HttpResult(status, {"ok": False, "error": {"code": code, "message": message}}, h)


def handle_http(
    method: str,
    raw_body: bytes,
    visitor: str,
    store: Store,
    schemas: Schemas,
    limiter: RateLimiter,
    now: datetime,
) -> HttpResult:
    """method: HTTP method. raw_body: the bytes sent. visitor: a hashed visitor key. now: aware datetime."""
    if method.upper() != "POST":
        return _error(405, "validation_failed", "Use POST.", {"Allow": "POST"})

    if not limiter.allow(visitor, now.timestamp()):
        wait = limiter.retry_after(visitor, now.timestamp())
        headers = {"Retry-After": str(wait)} if wait else {}
        log.info("registration_request code=rate_limited")
        return _error(HTTP_STATUS["rate_limited"], "rate_limited", "Too many requests. Try again later.", headers)

    if len(raw_body) > MAX_BODY_BYTES:
        return _error(413, "validation_failed", "The request is too large.")
    try:
        body = json.loads(raw_body.decode("utf-8")) if raw_body else None
    except (UnicodeDecodeError, ValueError):
        return _error(400, "validation_failed", "The request body must be JSON.")

    try:
        result = handle_registration_request(body, store, schemas, now=now)
    except Exception as exc:  # last resort: say nothing about the cause to the visitor
        log.error("registration_request code=server_error exception=%s", type(exc).__name__)
        return _error(500, "server_error", "Could not complete the request.")

    # Log ids and codes only, never submitted values.
    log.info("registration_request outcome=%s code=%s id=%s", result.outcome, result.error_code or "-",
             (result.doc or {}).get("id", "-"))
    return HttpResult(result.status, result.envelope, {"Cache-Control": "no-store"})
