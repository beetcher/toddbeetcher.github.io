"""The public venue list for the registration form: GET, no sign-in, read only.

Returns the active public venues as [{id, name, town}], sorted by name. Nothing else about a venue leaves
the server (no address, contact, GPS or notes). town is the locality of the venue's place; a venue with no
town is returned with name alone. Rate limited per visitor like the registration endpoint.

With ?zip=<five-digit ZIP> the list is ONLY the venues in the active region whose ZIP list holds that ZIP, nearest first, each also carrying miles
(straight line, one decimal). The reply also says covered: true or false, and when covered the region's id and name. A ZIP that no active region holds
is not covered: the list is empty and covered is false (the form then tells the visitor no trainer is active there yet and still takes the request).
A ZIP wins over a region id sent with it.
A venue's position is its place's GPS point when it has one, otherwise the centre of its place's ZIP (the US ZIP table, else co_zips.json).
A venue with no position at all goes last, with no miles. A ZIP that is not five digits is ignored: the list is as if no ZIP was given. A covered ZIP that is not in the position table lists the region's venues
alphabetically with no distances.

main.py turns a Firebase request into handle_public_venues(); tests call it directly.
"""
from __future__ import annotations

import logging
from datetime import datetime

from crud import locations_crud as LOC
from crud import venues_crud as V
from crud import venues_service as VS
from geo_rank import ZIP_RE, miles_between, position_of_place, zip_origin, zip_table  # noqa: F401  (re-exported for callers and tests)
from access.places import zip_of_venue
from public_regions import active_region_docs
from handler import HttpResult, _error
from ratelimit import RateLimiter

log = logging.getLogger("enjoy_router")
MAX_VENUES = 200
CACHE = "public, max-age=60"


def _position(store, venue_id: str):
    """Where the venue is: its place's GPS, else the centre of its place's ZIP, else None."""
    for link in VS._live_place_link(store, venue_id):
        got = LOC.get(store, link["location_id"])
        if not got.ok:
            continue
        pos = position_of_place(got.data)
        if pos:
            return pos
    return None


def covering_regions(store, zip_code) -> list:
    """The active regions whose ZIP list holds this five-digit ZIP, by name. [] for a ZIP that is not five digits or that no active region holds."""
    if not isinstance(zip_code, str) or not ZIP_RE.match(zip_code):
        return []
    out = [r for r in active_region_docs(store) if zip_code in {str(z).strip()[:5] for z in r.get("zip_codes", [])}]
    out.sort(key=lambda r: (r.get("name") or "").lower())
    return out


def public_list(store, zip_code=None, region_id=None, covering=None) -> list:
    """[{id, name, town}] for active public venues, by name. town is left out when the venue's place has none.
    With a known zip_code: nearest first, each with miles. With region_id: only venues whose ZIP is on that live region's list
    (an unknown, deleted or switched-off region gives an empty list)."""
    region_zips = None
    valid_zip = isinstance(zip_code, str) and bool(ZIP_RE.match(zip_code))
    if valid_zip:   # a ZIP means its own region(s) and nothing else; a ZIP no active region holds lists nothing
        regs = covering if covering is not None else covering_regions(store, zip_code)
        region_zips = {str(z).strip()[:5] for r in regs for z in r.get("zip_codes", [])}
    elif region_id:
        r = store.get("discovery_areas", region_id)
        ok = isinstance(r, dict) and not r.get("deleted_at") and r.get("kind") == "region" and r.get("is_active") is True
        region_zips = set(r.get("zip_codes", [])) if ok else set()
    got = V.list(store, {"status": "active"}, order="name", limit=MAX_VENUES)
    if not got.ok:
        return []
    origin = zip_origin(zip_code)
    out, positions = [], {}
    for venue in got.data["records"]:
        if venue.get("is_public_venue") is not True:
            continue
        if region_zips is not None and zip_of_venue(store, venue["id"]) not in region_zips:
            continue
        item = {"id": venue["id"], "name": venue["name"]}
        place = VS._place_view(store, venue["id"]) or {}
        town = (place.get("address") or {}).get("locality")
        if town:
            item["town"] = town
        out.append(item)
        positions[venue["id"]] = _position(store, venue["id"]) if origin else None
    if origin:
        for item in out:
            pos = positions[item["id"]]
            if pos:
                item["miles"] = round(miles_between(origin, pos), 1)
        out.sort(key=lambda i: (i.get("miles") is None, i.get("miles", 0), i["name"].lower()))
    return out


def handle_public_venues(method: str, visitor: str, store, limiter: RateLimiter, now: datetime, zip_code=None, region_id=None) -> HttpResult:
    if method.upper() != "GET":
        return _error(405, "validation_failed", "Use GET.", {"Allow": "GET"})
    if not limiter.allow(visitor, now.timestamp()):
        wait = limiter.retry_after(visitor, now.timestamp())
        return _error(429, "rate_limited", "Too many requests. Try again later.", {"Retry-After": str(wait)} if wait else {})
    try:
        regs = covering_regions(store, zip_code)
        venues = public_list(store, zip_code, region_id, covering=regs)
    except Exception as exc:  # last resort: the form falls back to its two plain choices
        log.error("public_venues code=server_error exception=%s", type(exc).__name__)
        return _error(500, "server_error", "Could not load the list.")
    log.info("public_venues count=%d", len(venues))
    data = {"venues": venues}
    if isinstance(zip_code, str) and ZIP_RE.match(zip_code):
        data["covered"] = bool(regs)
        if regs:
            data["region"] = {"id": regs[0]["id"], "name": regs[0].get("name") or ""}
    return HttpResult(200, {"ok": True, "data": data}, {"Cache-Control": CACHE})
