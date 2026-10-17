"""Handler for `discovery_models`: the AI models the Discovery station can pick (see DISCOVERY_MODEL_GUIDE.md).

Rules: provider plus model_name is unique among live models; a claude or openai model must name its key (key_name) and a gemini model
must not (it uses the Google project); provider cannot change after create (a different company is a different adapter, so make a new
model). A new model starts switched on. Deleting is always allowed (runs keep their own copy of the name and prices).
"""
from __future__ import annotations

from .discovery_kit import live, make

NEEDS_KEY = ("claude", "openai")


def _tidy(name, v):
    return v.strip() if isinstance(v, str) and name in ("model_name", "label", "key_name") else v


def _rules(store, doc, cur):
    problems = []
    if doc["provider"] in NEEDS_KEY and not doc.get("key_name"):
        problems.append({"field": "key_name", "issue": "required"})
    if doc["provider"] == "gemini" and doc.get("key_name"):
        problems.append({"field": "key_name", "issue": "not_allowed"})
    for d in live(store, H.COLLECTION, provider=doc["provider"]):
        if d["model_name"] == doc["model_name"] and d["id"] != (cur or {}).get("id"):
            problems.append({"field": "model_name", "issue": "duplicate"})
    return problems


H = make("discovery_model", defaults={"is_active": True}, immutable=("provider",), tidy=_tidy, rules=_rules, order="label", filters=("provider", "is_active"))
COLLECTION, create, get, list, update, soft_delete = H.COLLECTION, H.create, H.get, H.list, H.update, H.soft_delete
