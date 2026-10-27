"""Places with no time zone (Todd, 2026-10-23: no silent Denver; 2026-10-27: the system fills them all). One super-admin op, `fix_place_zones`.

A place's zone decides what time every class, email and notice there says. New places get their zone from their ZIP when they are saved
(`locations_crud`); this op catches the older ones. For every live place with no zone it uses, in this order:
  * the zone of the first address ZIP the shared ZIP-to-zone table knows (`launch_discovery/zip_zones.py`; Arizona, Navajo Nation, split states, Alaska and Hawaii are right);
  * else a Colorado place (address region CO) gets America/Denver (all of Colorado is Mountain time).
A place with neither (no ZIP the table knows, state not Colorado) is LISTED for a person; nothing is guessed.
Default is a dry run (`apply` false): it writes nothing and says what it would do.
"""
from __future__ import annotations

import re

from crud import locations_crud as LOC
from launch_discovery import zip_table, zip_zones

ZIP5 = re.compile(r"^[0-9]{5}")
LIMIT_LISTED = 200


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


def zone_for(place):
    """The zone this place should have, or None when the system cannot tell."""
    z = zip_zones.zone_of_addresses(place.get("addresses"))
    if z:
        return z
    return "America/Denver" if _state_of(place) == "CO" else None


def run(store, actor: str, apply: bool = False, now=None) -> dict:
    places = [p for p in store.query("locations", [], limit=5000) if not p.get("deleted_at") and not p.get("time_zone")]
    fill, needs = [], []
    for p in places:
        z = zone_for(p)
        (fill if z else needs).append((p, z))
    done = 0
    if apply:
        for p, z in fill:
            r = LOC.update(store, p["id"], {"time_zone": z}, actor, now=now)
            done += 1 if r.ok else 0
    return {"without_zone": len(places), "fillable": len(fill), "filled": done, "applied": bool(apply),
            "needs_a_person": [{"id": p["id"], "name": p.get("name") or "", "state": _state_of(p)} for p, _ in needs[:LIMIT_LISTED]], "needs_count": len(needs)}
