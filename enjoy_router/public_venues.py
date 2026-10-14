"""The public venue list for the registration form: GET, no sign-in, read only.

Returns the active public venues as [{id, name, town}], sorted by name. Nothing else about a venue leaves
the server (no address, contact, GPS or notes). town is the locality of the venue's place; a venue with no
town is returned with name alone. Rate limited per visitor like the registration endpoint.

main.py turns a Firebase request into handle_public_venues(); tests call it directly.
"""
from __future__ import annotations

import logging
from datetime import datetime

from crud import venues_crud as V
from crud import venues_service as VS
from handler import HttpResult, _error
from ratelimit import RateLimiter

log = logging.getLogger("enjoy_router")
MAX_VENUES = 200
CACHE = "public, max-age=60"


def public_list(store) -> list:
    """[{id, name, town}] for active public venues, by name. town is left out when the venue's place has none."""
    got = V.list(store, {"status": "active"}, order="name", limit=MAX_VENUES)
    if not got.ok:
        return []
    out = []
    for venue in got.data["records"]:
        if venue.get("is_public_venue") is not True:
            continue
        item = {"id": venue["id"], "name": venue["name"]}
        place = VS._place_view(store, venue["id"]) or {}
        town = (place.get("address") or {}).get("locality")
        if town:
            item["town"] = town
        out.append(item)
    return out


def handle_public_venues(method: str, visitor: str, store, limiter: RateLimiter, now: datetime) -> HttpResult:
    if method.upper() != "GET":
        return _error(405, "validation_failed", "Use GET.", {"Allow": "GET"})
    if not limiter.allow(visitor, now.timestamp()):
        wait = limiter.retry_after(visitor, now.timestamp())
        return _error(429, "rate_limited", "Too many requests. Try again later.", {"Retry-After": str(wait)} if wait else {})
    try:
        venues = public_list(store)
    except Exception as exc:  # last resort: the form falls back to its two plain choices
        log.error("public_venues code=server_error exception=%s", type(exc).__name__)
        return _error(500, "server_error", "Could not load the list.")
    log.info("public_venues count=%d", len(venues))
    return HttpResult(200, {"ok": True, "data": {"venues": venues}}, {"Cache-Control": CACHE})
