"""Places with no time zone (Todd, 2026-10-23: no silent Denver; 2026-10-27: the system fills them all). One super-admin op, `fix_place_zones`.

A place's zone decides what time every class, email and notice there says. New places get their zone from their ZIP when they are saved
(`locations_crud`); this op catches the older ones. For every live place with no zone it uses, in this order:
  * the zone of the first address ZIP the shared ZIP-to-zone table knows (`launch_discovery/zip_zones.py`; Arizona, Navajo Nation, split states, Alaska and Hawaii are right). The street (civic) address is tried first, then the others (Z-2);
  * else a Colorado place (address region CO) gets America/Denver (all of Colorado is Mountain time).
A place with neither (no ZIP the table knows, state not Colorado) is LISTED for a person; nothing is guessed.
Default is a dry run (`apply` false): it writes nothing and says what it would do, with a count per zone, up to 10 sample places and how many upcoming
classes sit at the places it would fill (Z-1). One press fills at most FILL_CAP places (the server stops a request after 60 seconds); the answer says how many are left (Z-2).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from crud import locations_crud as LOC
from launch_discovery import zip_table, zip_zones

ZIP5 = re.compile(r"^[0-9]{5}")
LIMIT_LISTED = 200
FILL_CAP = 150
SAMPLES = 10


def _state_of(place) -> str:
    for a in place.get("addresses") or []:
        r = str(a.get("region") or "").strip().upper()
        if len(r) == 2:
            return r
    for a in place.get("addresses") or []:
        m = ZIP5.match(str(a.get("postal_code") or ""))
        if m and zip_table.is_loaded():
            st = zip_table.state_of(m.group(0))
            if st:
                return st
    return ""


def _civic_first(addresses):
    adds = [a for a in (addresses or []) if isinstance(a, dict)]
    return [a for a in adds if a.get("usage") == "civic"] + [a for a in adds if a.get("usage") != "civic"]


def _zip_of(place) -> str:
    for a in _civic_first(place.get("addresses")):
        m = ZIP5.match(str(a.get("postal_code") or ""))
        if m:
            return m.group(0)
    return ""


def zone_and_why(place):
    """(zone, why) with why "zip" or "colorado", or (None, None) when the system cannot tell."""
    z = zip_zones.zone_of_addresses(_civic_first(place.get("addresses")))
    if z:
        return z, "zip"
    return ("America/Denver", "colorado") if _state_of(place) == "CO" else (None, None)


def zone_for(place):
    """The zone this place should have, or None when the system cannot tell."""
    return zone_and_why(place)[0]


def _upcoming_classes(store, place_ids, now) -> int:
    """Classes that have not started, with no zone of their own, held at a venue whose place is about to get a zone."""
    if not place_ids:
        return 0
    venues = {l.get("subject_id") for l in store.query("location_links", [], limit=5000)
              if not l.get("deleted_at") and l.get("subject_type") == "venue" and l.get("location_id") in place_ids}
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return sum(1 for c in store.query("scheduled_classes", [], limit=5000)
               if not c.get("deleted_at") and c.get("venue_id") in venues and not c.get("time_zone")
               and c.get("status") not in ("cancelled", "completed") and str(c.get("starts_at") or "9999") > stamp)


def run(store, actor: str, apply: bool = False, now=None) -> dict:
    places = [p for p in store.query("locations", [], limit=5000) if not p.get("deleted_at") and not p.get("time_zone")]
    fill, needs = [], []
    for p in places:
        z, why = zone_and_why(p)
        (fill if z else needs).append((p, z, why))
    batch = fill[:FILL_CAP] if apply else fill
    done = 0
    if apply:
        for p, z, _ in batch:
            r = LOC.update(store, p["id"], {"time_zone": z}, actor, now=now)
            done += 1 if r.ok else 0
    by_zone = {}
    for _, z, _ in fill:
        by_zone[z] = by_zone.get(z, 0) + 1
    samples = [{"name": p.get("name") or "", "state": _state_of(p), "zip": _zip_of(p), "zone": z, "why": why} for p, z, why in fill[:SAMPLES]]
    return {"without_zone": len(places), "fillable": len(fill), "filled": done, "applied": bool(apply),
            "left": (len(fill) - done) if apply else len(fill), "from_zip": sum(1 for _, _, w in fill if w == "zip"), "from_colorado": sum(1 for _, _, w in fill if w == "colorado"),
            "by_zone": by_zone, "samples": samples, "upcoming_classes": _upcoming_classes(store, {p["id"] for p, _, _ in fill}, now),
            "cap": FILL_CAP,
            "needs_a_person": [{"id": p["id"], "name": p.get("name") or "", "state": _state_of(p)} for p, _, _ in needs[:LIMIT_LISTED]], "needs_count": len(needs)}
