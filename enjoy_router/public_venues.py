"""The public venue list for the registration form: GET, no sign-in, read only.

Returns the active public venues as [{id, name, town}], sorted by name. Nothing else about a venue leaves
the server (no address, contact, GPS or notes). town is the locality of the venue's place; a venue with no
town is returned with name alone. Rate limited per visitor like the registration endpoint.

With ?zip=<Colorado ZIP> the list is nearest first and each item also carries miles (straight line, one decimal).
A venue's position is its place's GPS point when it has one, otherwise the centre of its place's ZIP (co_zips.json).
A venue with no position at all goes last, with no miles. A ZIP that is not valid or not in the table is ignored:
the list stays alphabetical with no distances.

main.py turns a Firebase request into handle_public_venues(); tests call it directly.
"""
from __future__ import annotations

import json
import logging
import math
import pathlib
import re
from datetime import datetime

from crud import locations_crud as LOC
from crud import venues_crud as V
from crud import venues_service as VS
from handler import HttpResult, _error
from ratelimit import RateLimiter

log = logging.getLogger("enjoy_router")
MAX_VENUES = 200
CACHE = "public, max-age=60"


ZIP_RE = re.compile(r"^8[01][0-9]{3}$")
_zips = None


def zip_table() -> dict:
    """Colorado ZIP -> [lat, lon], read once from co_zips.json."""
    global _zips
    if _zips is None:
        _zips = json.loads((pathlib.Path(__file__).resolve().parent / "co_zips.json").read_text())
    return _zips


def miles_between(a, b) -> float:
    """Straight-line miles between two [lat, lon] points."""
    (la1, lo1), (la2, lo2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    d = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(d))


def _gps_of(loc: dict):
    """[lat, lon] of the place's best GPS point (centre, then entrance, then any point), or None."""
    best = None
    for rank, role in enumerate(("center", "entrance")):
        for g in loc.get("geometries", []):
            geo = g.get("geometry") or {}
            if g.get("role") == role and geo.get("type") == "Point" and len(geo.get("coordinates", [])) >= 2:
                return [geo["coordinates"][1], geo["coordinates"][0]]
    for g in loc.get("geometries", []):
        geo = g.get("geometry") or {}
        if geo.get("type") == "Point" and len(geo.get("coordinates", [])) >= 2:
            best = [geo["coordinates"][1], geo["coordinates"][0]]
            break
    return best


def _position(store, venue_id: str):
    """Where the venue is: its place's GPS, else the centre of its place's ZIP, else None."""
    for link in VS._live_place_link(store, venue_id):
        got = LOC.get(store, link["location_id"])
        if not got.ok:
            continue
        gps = _gps_of(got.data)
        if gps:
            return gps
        for a in got.data.get("addresses", []):
            z = str(a.get("postal_code") or "")[:5]
            if a.get("usage") != "former" and z in zip_table():
                return zip_table()[z]
    return None


def public_list(store, zip_code=None) -> list:
    """[{id, name, town}] for active public venues, by name. town is left out when the venue's place has none.
    With a known Colorado zip_code: nearest first, each with miles."""
    got = V.list(store, {"status": "active"}, order="name", limit=MAX_VENUES)
    if not got.ok:
        return []
    origin = zip_table().get(str(zip_code)) if zip_code and ZIP_RE.match(str(zip_code)) else None
    out, positions = [], {}
    for venue in got.data["records"]:
        if venue.get("is_public_venue") is not True:
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


def handle_public_venues(method: str, visitor: str, store, limiter: RateLimiter, now: datetime, zip_code=None) -> HttpResult:
    if method.upper() != "GET":
        return _error(405, "validation_failed", "Use GET.", {"Allow": "GET"})
    if not limiter.allow(visitor, now.timestamp()):
        wait = limiter.retry_after(visitor, now.timestamp())
        return _error(429, "rate_limited", "Too many requests. Try again later.", {"Retry-After": str(wait)} if wait else {})
    try:
        venues = public_list(store, zip_code)
    except Exception as exc:  # last resort: the form falls back to its two plain choices
        log.error("public_venues code=server_error exception=%s", type(exc).__name__)
        return _error(500, "server_error", "Could not load the list.")
    log.info("public_venues count=%d", len(venues))
    return HttpResult(200, {"ok": True, "data": {"venues": venues}}, {"Cache-Control": CACHE})
