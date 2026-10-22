"""Coverage of a private registration request: is a trainer region ACTIVE where the requester wants the session? (P-83, Todd 2026-10-22)

Pure functions over the list of discovery areas (states and regions); no store, no Firebase. A region is ACTIVE when it is switched on, not
deleted, and sits in a state that is switched on and not deleted.

    fields_for(areas, doc)  -> {"coverage": "covered" | "no_active_region", "coverage_state_code": "CO"} or {}
    is_open(areas, doc)     -> True when the request is an urgent one still waiting: coverage no_active_region, not handled, and no region
                               holds its ZIP now (a region added later closes the request with nobody pressing anything)

Rules: private requests only. A ZIP wins over a region picked on the form. A ZIP some active region lists is covered; any other ZIP is
no_active_region. With no ZIP, a picked active region is covered. With neither (or a region that is no longer active and no ZIP), nothing is
said ({}), so a stored request keeps what it had. The state is the ZIP table's state for the ZIP, else the covering region's state.
"""
from __future__ import annotations

import re

from launch_discovery import zip_table

ZIP = re.compile(r"^[0-9]{5}$")
OPEN = "no_active_region"


def active_regions(areas) -> list:
    live = [a for a in areas if not a.get("deleted_at")]
    states = {a.get("state_code") for a in live if a.get("kind") == "state" and a.get("is_active") is True}
    return [a for a in live if a.get("kind") == "region" and a.get("is_active") is True and a.get("state_code") in states]


def holding(regions, zip_code) -> list:
    return [r for r in regions if zip_code in {str(z).strip()[:5] for z in r.get("zip_codes", [])}]


def fields_for(areas, doc) -> dict:
    if doc.get("registration_type") != "private":
        return {}
    regions = active_regions(areas)
    z = doc.get("postal_code")
    if isinstance(z, str) and ZIP.match(z):
        state = zip_table.state_of(z) if zip_table.is_loaded() else None
        hit = holding(regions, z)
        out = {"coverage": "covered" if hit else OPEN}
        state = state or (hit[0].get("state_code") if hit else None)
        if state:
            out["coverage_state_code"] = state
        return out
    rid = doc.get("region_id")
    if rid:
        r = next((x for x in regions if x.get("id") == rid), None)
        if r is not None:
            out = {"coverage": "covered"}
            if r.get("state_code"):
                out["coverage_state_code"] = r["state_code"]
            return out
    return {}


def is_open(areas, doc) -> bool:
    if doc.get("coverage") != OPEN or doc.get("coverage_handled_at") or doc.get("deleted_at"):
        return False
    return fields_for(areas, doc).get("coverage", OPEN) != "covered"
