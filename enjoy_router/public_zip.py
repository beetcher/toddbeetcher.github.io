"""The public place lookup for the registration form (P-86 stage A, P-93): GET, no sign-in, read only, public facts only.

One door, three questions (checked in this order when several are sent):

  ?zip=80202     -> {found, zip, town, state_code, state_name, covered, region}
                    town and state come from the shared US ZIP table; covered and region say whether an ACTIVE region (switched on,
                    not deleted, in a switched-on, not deleted state) lists the ZIP, using the same helper the server uses to judge a
                    request (request_coverage.holding), so the page and the server cannot disagree. region is {id, name, state_code}
                    or null. A ZIP that is not five digits, or not in the table, answers {found: false} and nothing else.
  ?region=<id>   -> {zips: [{zip, town}]} for ONE active region (its ZIP list, by ZIP); an unknown, switched-off or deleted region
                    answers {zips: []}.
  ?state=MN      -> {state_code, state_name, cities: [{name, zips}]}: the ten biggest cities of the state with the ZIPs that carry
                    their name (the shared city table); an unknown state answers {cities: []}.
  (nothing)      -> {found: false}

Nothing private leaves the server: no notes, timestamps, people, venues or request data, only ZIP, town, state and the id and name
of an active region. Rate limited per visitor like the other public lists. main.py turns a Firebase request into
handle_public_zip(); tests call it directly. There is no stored record here, so there is no schema file.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime

from handler import HttpResult, _error
from launch_discovery import city_table, zip_table
from public_regions import active_region_docs
from ratelimit import RateLimiter
from request_coverage import holding

log = logging.getLogger("enjoy_router")
CACHE = "public, max-age=60"
ZIP_RE = re.compile(r"^[0-9]{5}$")
STATE_RE = re.compile(r"^[A-Za-z]{2}$")

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado", "CT": "Connecticut",
    "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}


def _region_ref(r: dict) -> dict:
    return {"id": r["id"], "name": r["name"], "state_code": r["state_code"]}


def lookup_zip(store, zip_code) -> dict:
    z = zip_code.strip() if isinstance(zip_code, str) else ""
    if not ZIP_RE.match(z):
        return {"found": False}
    st = zip_table.state_of(z)
    if not st:
        return {"found": False}
    held = sorted(holding(active_region_docs(store), z), key=lambda r: (r.get("name") or "").lower())
    return {
        "found": True, "zip": z, "town": zip_table.town_of(z) or "", "state_code": st, "state_name": STATE_NAMES.get(st, st),
        "covered": bool(held), "region": _region_ref(held[0]) if held else None,
    }


def region_zips(store, region_id) -> dict:
    rid = region_id if isinstance(region_id, str) else ""
    region = next((r for r in active_region_docs(store) if r.get("id") == rid), None)
    if not region:
        return {"zips": []}
    zs = sorted({str(z).strip()[:5] for z in region.get("zip_codes", []) if ZIP_RE.match(str(z).strip()[:5])})
    return {"region": _region_ref(region), "zips": [{"zip": z, "town": zip_table.town_of(z) or ""} for z in zs]}


def state_cities(state_code) -> dict:
    sc = state_code.strip().upper() if isinstance(state_code, str) and STATE_RE.match(state_code.strip()) else ""
    if not sc or sc not in STATE_NAMES:
        return {"cities": []}
    cities = [{"name": c["name"], "zips": [z for z in c.get("zips", []) if ZIP_RE.match(str(z))]} for c in city_table.cities_in_state(sc)]
    return {"state_code": sc, "state_name": STATE_NAMES[sc], "cities": cities}


def handle_public_zip(method: str, visitor: str, store, limiter: RateLimiter, now: datetime,
                      zip_code=None, region_id=None, state_code=None) -> HttpResult:
    if method.upper() != "GET":
        return _error(405, "validation_failed", "Use GET.", {"Allow": "GET"})
    if not limiter.allow(visitor, now.timestamp()):
        wait = limiter.retry_after(visitor, now.timestamp())
        return _error(429, "rate_limited", "Too many requests. Try again later.", {"Retry-After": str(wait)} if wait else {})
    try:
        if zip_code:
            data, kind = lookup_zip(store, zip_code), "zip"
        elif region_id:
            data, kind = region_zips(store, region_id), "region"
        elif state_code:
            data, kind = state_cities(state_code), "state"
        else:
            data, kind = {"found": False}, "none"
    except Exception as exc:  # last resort: the form simply does not fill anything in
        log.error("public_zip code=server_error exception=%s", type(exc).__name__)
        return _error(500, "server_error", "Could not look that up.")
    log.info("public_zip kind=%s", kind)
    return HttpResult(200, {"ok": True, "data": data}, {"Cache-Control": CACHE})
