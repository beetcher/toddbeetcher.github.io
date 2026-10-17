"""Handler for `discovery_types`: the kinds of thing a finder looks for (see DISCOVERY_TYPE_GUIDE.md).

Rules: finder_key must be a registered finder; key is unique within its finder among live types; finder_key and key never change
(the label is what people read). A new type starts switched on and as a distinctive-places type (is_chain false).
"""
from __future__ import annotations

from launch_discovery import FINDER_KEYS

from .discovery_kit import live, make


def _tidy(name, v):
    return v.strip() if isinstance(v, str) else v


def _rules(store, doc, cur):
    problems = []
    if doc["finder_key"] not in FINDER_KEYS:
        problems.append({"field": "finder_key", "issue": "invalid_value"})
    for d in live(store, H.COLLECTION, finder_key=doc["finder_key"]):
        if d["key"] == doc["key"] and d["id"] != (cur or {}).get("id"):
            problems.append({"field": "key", "issue": "duplicate"})
    return problems


H = make("discovery_type", defaults={"is_active": True, "is_chain": False}, immutable=("finder_key", "key"), tidy=_tidy, rules=_rules,
         order="sort_order", filters=("finder_key", "is_active"))
COLLECTION, create, get, list, update, soft_delete = H.COLLECTION, H.create, H.get, H.list, H.update, H.soft_delete
