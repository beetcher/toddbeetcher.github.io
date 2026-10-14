"""The public curriculum list for the registration form: GET, no sign-in, read only.

Returns the ACTIVE curriculums as [{id, title, tagline}], sorted by title. Nothing else about a curriculum leaves
the server (no slug, description, notes or timestamps); tagline is left out when a curriculum has none. A curriculum is
what a person chooses to learn; it is not a class (a class is a moment in time). Rate limited per visitor like the
venue list.

main.py turns a Firebase request into handle_public_curriculums(); tests call it directly.
"""
from __future__ import annotations

import logging
from datetime import datetime

from crud import curriculums_crud as C
from handler import HttpResult, _error
from ratelimit import RateLimiter

log = logging.getLogger("enjoy_router")
MAX_CURRICULUMS = 200
CACHE = "public, max-age=60"


def public_list(store) -> list:
    """[{id, title, tagline}] for active curriculums, by title. tagline is left out when there is none."""
    got = C.list(store, {"status": "active"}, order="title", limit=MAX_CURRICULUMS)
    if not got.ok:
        return []
    out = []
    for c in got.data["records"]:
        item = {"id": c["id"], "title": c["title"]}
        if c.get("tagline"):
            item["tagline"] = c["tagline"]
        out.append(item)
    return out


def handle_public_curriculums(method: str, visitor: str, store, limiter: RateLimiter, now: datetime) -> HttpResult:
    if method.upper() != "GET":
        return _error(405, "validation_failed", "Use GET.", {"Allow": "GET"})
    if not limiter.allow(visitor, now.timestamp()):
        wait = limiter.retry_after(visitor, now.timestamp())
        return _error(429, "rate_limited", "Too many requests. Try again later.", {"Retry-After": str(wait)} if wait else {})
    try:
        curriculums = public_list(store)
    except Exception as exc:  # last resort: the form simply leaves the question out
        log.error("public_curriculums code=server_error exception=%s", type(exc).__name__)
        return _error(500, "server_error", "Could not load the list.")
    log.info("public_curriculums count=%d", len(curriculums))
    return HttpResult(200, {"ok": True, "data": {"curriculums": curriculums}}, {"Cache-Control": CACHE})
