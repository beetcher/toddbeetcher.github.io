"""Handler for `discovery_areas`: states and named regions the Discovery station may search (see DISCOVERY_AREA_GUIDE.md).

Rules: one live state record per state_code; a region name is unique within its state; a region's ZIP codes must each be in the
region's state according to the shared ZIP table (launch_discovery/zip_table.py), and when that table is not loaded a region cannot be
saved (zip_table_missing) rather than trusting unchecked ZIPs; kind and state_code never change; a state is deleted only when no live
region is left in it. A new area starts switched OFF.
"""
from __future__ import annotations

from launch_discovery import zip_table

from .discovery_kit import live, make

STATES = frozenset("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())


def _tidy(name, v):
    return v.strip() if isinstance(v, str) and name == "name" else v


def _rules(store, doc, cur):
    problems = []
    if doc["state_code"] not in STATES:
        problems.append({"field": "state_code", "issue": "invalid_value"})
    mine = (cur or {}).get("id")
    if doc["kind"] == "state":
        if "zip_codes" in doc:
            problems.append({"field": "zip_codes", "issue": "not_allowed"})
        for d in live(store, H.COLLECTION, state_code=doc["state_code"]):
            if d["kind"] == "state" and d["id"] != mine:
                problems.append({"field": "state_code", "issue": "duplicate"})
    else:
        if not doc.get("zip_codes"):
            problems.append({"field": "zip_codes", "issue": "required"})
        for d in live(store, H.COLLECTION, state_code=doc["state_code"]):
            if d["kind"] == "region" and d["name"].lower() == doc["name"].lower() and d["id"] != mine:
                problems.append({"field": "name", "issue": "duplicate"})
        if doc.get("zip_codes"):
            if not zip_table.is_loaded():
                problems.append({"field": "zip_codes", "issue": "zip_table_missing"})
            elif any(zip_table.state_of(z) != doc["state_code"] for z in doc["zip_codes"]):
                problems.append({"field": "zip_codes", "issue": "not_in_state"})
    return problems


def _delete_rules(store, cur):
    if cur["kind"] == "state" and any(d["kind"] == "region" for d in live(store, H.COLLECTION, state_code=cur["state_code"])):
        return [{"field": "id", "issue": "in_use"}]
    return []


H = make("discovery_area", defaults={"is_active": False}, immutable=("kind", "state_code"), tidy=_tidy, rules=_rules,
         delete_rules=_delete_rules, order="name", filters=("kind", "state_code", "is_active"))
COLLECTION, create, get, list, update, soft_delete = H.COLLECTION, H.create, H.get, H.list, H.update, H.soft_delete
