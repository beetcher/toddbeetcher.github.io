"""Places with no time zone (Todd, 2026-10-23: no silent Denver). One super-admin op, `fix_place_zones`.

A place's zone decides what time every class, email and notice there says. Older places were saved without one. This op looks at every live place
with no zone:
  * a Colorado place (an address region CO, or a ZIP the shared table puts in CO) gets America/Denver (all of Colorado is Mountain time);
  * every other place is LISTED for a person to fix by hand (Arizona and Indiana split inside a state, so nothing outside Colorado is guessed).
Default is a dry run (`apply` false): it writes nothing and says what it would do.
"""
from __future__ import annotations

import re

from crud import locations_crud as LOC
from launch_discovery import zip_table

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


def run(store, actor: str, apply: bool = False, now=None) -> dict:
    places = [p for p in store.query("locations", [], limit=5000) if not p.get("deleted_at") and not p.get("time_zone")]
    fill, needs = [], []
    for p in places:
        st = _state_of(p)
        (fill if st == "CO" else needs).append((p, st))
    done = 0
    if apply:
        for p, _ in fill:
            r = LOC.update(store, p["id"], {"time_zone": "America/Denver"}, actor, now=now)
            done += 1 if r.ok else 0
    return {"without_zone": len(places), "colorado": len(fill), "filled": done, "applied": bool(apply),
            "needs_a_person": [{"id": p["id"], "name": p.get("name") or "", "state": st} for p, st in needs[:LIMIT_LISTED]], "needs_count": len(needs)}
