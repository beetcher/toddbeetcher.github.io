"""The public region list for the registration form: GET, no sign-in, read only.

Returns the switched-on regions that sit in switched-on states as [{id, name, state_code, state_name}], sorted by state name
then region name. Nothing else leaves the server (no ZIP lists, notes or timestamps). The form builds its State drop-down from
the distinct states and its Region drop-down from the regions of the chosen state. Rate limited per visitor like the venue list.

main.py turns a Firebase request into handle_public_regions(); tests call it directly.
"""
from __future__ import annotations

import logging
from datetime import datetime

from handler import HttpResult, _error
from ratelimit import RateLimiter

log = logging.getLogger("enjoy_router")
CACHE = "public, max-age=60"


def public_list(store) -> list:
    areas = [a for a in store.query("discovery_areas", [], limit=1000) if not a.get("deleted_at")]
    states = {a.get("state_code"): a for a in areas if a.get("kind") == "state" and a.get("is_active") is True}
    out = []
    for a in areas:
        if a.get("kind") != "region" or a.get("is_active") is not True or a.get("state_code") not in states:
            continue
        st = states[a["state_code"]]
        out.append({"id": a["id"], "name": a["name"], "state_code": a["state_code"], "state_name": st.get("name") or a["state_code"]})
    out.sort(key=lambda r: (r["state_name"].lower(), r["name"].lower()))
    return out


def handle_public_regions(method: str, visitor: str, store, limiter: RateLimiter, now: datetime) -> HttpResult:
    if method.upper() != "GET":
        return _error(405, "validation_failed", "Use GET.", {"Allow": "GET"})
    if not limiter.allow(visitor, now.timestamp()):
        wait = limiter.retry_after(visitor, now.timestamp())
        return _error(429, "rate_limited", "Too many requests. Try again later.", {"Retry-After": str(wait)} if wait else {})
    try:
        regions = public_list(store)
    except Exception as exc:  # last resort: the form falls back to the ZIP box alone
        log.error("public_regions code=server_error exception=%s", type(exc).__name__)
        return _error(500, "server_error", "Could not load the list.")
    log.info("public_regions count=%d", len(regions))
    return HttpResult(200, {"ok": True, "data": {"regions": regions}}, {"Cache-Control": CACHE})
