"""Handler for `discovery_settings`: the ONE record of Discovery settings (see DISCOVERY_SETTING_GUIDE.md).

`create` makes the record with starting values when none exists and refuses a second. `update` changes it in place. Deleting is refused.
Rules: default_spend_cap_cents is not above max_spend_cap_cents; results_per_step is not above max_results_per_run; default_model_id,
when given, names a live model. The run MODE is not here (it comes from the environment).
"""
from __future__ import annotations

from .discovery_kit import bad, live, make
from .schema_kit import failure

DEFAULTS = {"settings_key": "default", "default_spend_cap_cents": 100, "max_spend_cap_cents": 1000, "max_results_per_run": 100,
            "results_per_step": 10}


def _rules(store, doc, cur):
    problems = []
    if doc["default_spend_cap_cents"] > doc["max_spend_cap_cents"]:
        problems.append({"field": "default_spend_cap_cents", "issue": "invalid_value"})
    if doc["results_per_step"] > doc["max_results_per_run"]:
        problems.append({"field": "results_per_step", "issue": "invalid_value"})
    if doc.get("default_model_id"):
        from . import discovery_models_crud as M
        if not store.get(M.COLLECTION.name, doc["default_model_id"]) or "deleted_at" in store.get(M.COLLECTION.name, doc["default_model_id"]):
            problems.append({"field": "default_model_id", "issue": "not_found"})
    if cur is None and live(store, H.COLLECTION):
        problems.append({"field": "settings_key", "issue": "duplicate"})
    return problems


H = make("discovery_setting", defaults=DEFAULTS, immutable=("settings_key",), rules=_rules, order="settings_key")
COLLECTION, create, get, list, update = H.COLLECTION, H.create, H.get, H.list, H.update


def soft_delete(*_a, **_k):
    return failure("validation_failed", [{"field": "op", "issue": "not_supported"}])
