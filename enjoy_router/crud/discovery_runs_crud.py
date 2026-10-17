"""Handler for `discovery_runs`: one record per press of Go (see DISCOVERY_RUN_GUIDE.md). THE RUN RECORD IS HISTORY.

Only the Discovery service writes runs (the Console door cannot reach this collection; it reads runs through the Discovery door).
There is no delete: `soft_delete` is refused. Rules checked on every save: actual cost is not above the cap, the estimate's low is not
above its high, steps_done is not above steps_planned, a stopped run names why and a finished, stopped or failed run has finished_at.
"""
from __future__ import annotations

from .discovery_kit import make
from .schema_kit import failure


def _rules(store, doc, cur):
    p = []
    if doc["actual_cost_cents"] > doc["spend_cap_cents"]:
        p.append({"field": "actual_cost_cents", "issue": "invalid_value"})
    if doc["estimated_cost_low_cents"] > doc["estimated_cost_high_cents"]:
        p.append({"field": "estimated_cost_low_cents", "issue": "invalid_value"})
    if doc.get("steps_done", 0) > doc.get("steps_planned", 0):
        p.append({"field": "steps_done", "issue": "invalid_value"})
    if doc["status"] == "stopped" and not doc.get("stop_reason"):
        p.append({"field": "stop_reason", "issue": "required"})
    if doc["status"] in ("finished", "stopped", "failed") and not doc.get("finished_at"):
        p.append({"field": "finished_at", "issue": "required"})
    return p


H = make("discovery_run", rules=_rules, order="-created_at", filters=("finder_key", "status"), immutable=("finder_key", "run_mode", "model_id", "prompt_id"))
COLLECTION, create, get, list, update = H.COLLECTION, H.create, H.get, H.list, H.update


def soft_delete(*_a, **_k):
    return failure("validation_failed", [{"field": "op", "issue": "not_supported"}])
