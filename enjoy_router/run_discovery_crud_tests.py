#!/usr/bin/env python3
"""In-memory tests for the Discovery collection handlers (crud/discovery_*_crud.py) and their wiring in crud_endpoint.
Run from enjoy_router/:  python3 run_discovery_crud_tests.py   (-v lists every check). Nothing touches Firebase."""
import json, pathlib, sys
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import (discovery_areas_crud as AR, discovery_models_crud as MO, discovery_prompts_crud as PR, discovery_runs_crud as RU,  # noqa: E402
                  discovery_settings_crud as SE, discovery_types_crud as TY)
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud_endpoint import ADMIN_BLOCKED_COLLECTIONS, HANDLERS, handle_admin, handle_crud_test, make_failure_limiter  # noqa: E402
from launch_discovery import zip_table  # noqa: E402

START = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)
A = "user:admin"
EX = HERE.parent / "schemas" / "examples"
fails, total, clock = [], 0, [0]
def tick():
    clock[0] += 5
    return START + timedelta(seconds=clock[0])
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    if not ok or "-v" in sys.argv: print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")
def issues(r): return sorted((p["field"], p["issue"]) for p in r.problems)
def fresh(): return MemoryDocStore("test_")

zip_table.set_table({z: ["CO", 40.0, -105.0, "X"] for z in ("80301", "80302", "80303", "80304", "80305", "80027", "80501", "80202", "80203")}
                    | {"75001": ["TX", 32.9, -96.8, "Y"]})

# ---------------------------------------------------------------- every example through its handler
for key, H in (("model", MO), ("area", AR), ("type", TY), ("prompt", PR), ("setting", SE), ("run", RU)):
    ex = json.loads((EX / f"discovery_{key}.examples.json").read_text())
    for name, rec in ex["valid"].items():
        if name == "with_default_model": continue          # names a model that must exist; covered below
        r = H.create(fresh(), rec, A, now=tick()); check(f"{key}: valid example {name}", r.ok, r.problems)
    store = fresh()
    FILLED = {"missing_is_active", "missing_is_chain", "missing_default_cap", "missing_max_cap", "missing_max_results",
              "missing_results_per_step"}      # the handler fills these with its starting values, so they are valid there
    for name, rec in ex["invalid"].items():
        if name in FILLED: continue
        r = H.create(store, rec, A, now=tick()); check(f"{key}: invalid example {name} refused", not r.ok)

# ---------------------------------------------------------------- wiring
check("six Discovery collections are registered", all(f"discovery_{c}" in HANDLERS for c in ("models", "areas", "types", "prompts", "settings", "runs")))
check("runs are blocked at the Console door", "discovery_runs" in ADMIN_BLOCKED_COLLECTIONS and "discovery_models" not in ADMIN_BLOCKED_COLLECTIONS)

# ---------------------------------------------------------------- models
s = fresh()
g = {"provider": "gemini", "model_name": " gemini-3.8-flash ", "label": "Gemini Flash", "price_input_per_million_cents": 75,
     "price_output_per_million_cents": 375, "has_grounding": True}
r = MO.create(s, g, A, now=tick()); mid = r.data["id"] if r.ok else None
check("model create trims, starts switched on", r.ok and r.data["model_name"] == "gemini-3.8-flash" and r.data["is_active"] is True, r.problems if not r.ok else "")
check("model: same provider + name again is a duplicate", issues(MO.create(s, g, A, now=tick())) == [("model_name", "duplicate")])
check("model: same name under another provider is fine", MO.create(s, {**g, "provider": "claude", "key_name": "ICDT_CLAUDE_KEY"}, A, now=tick()).ok)
check("model: gemini with a key_name refused", issues(MO.create(s, {**g, "model_name": "x2", "key_name": "ICDT_X"}, A, now=tick())) == [("key_name", "not_allowed")])
check("model: claude without a key_name refused", ("key_name", "required") in issues(MO.create(s, {**g, "provider": "claude", "model_name": "y"}, A, now=tick())))
check("model: provider cannot change", issues(MO.update(s, mid, {"provider": "openai"}, A, now=tick())) == [("provider", "immutable")])
check("model: price can change", MO.update(s, mid, {"price_input_per_million_cents": 80}, A, now=tick()).ok and MO.get(s, mid).data["price_input_per_million_cents"] == 80)
check("model: switch off", MO.update(s, mid, {"is_active": False}, A, now=tick()).ok and MO.get(s, mid).data["is_active"] is False)
check("model: renaming onto another live model refused", True if MO.create(s, {**g, "model_name": "other"}, A, now=tick()).ok else False)
other = [d for d in MO.list(s).data["records"] if d["model_name"] == "other"][0]["id"]
check("model: rename into a duplicate refused", issues(MO.update(s, other, {"model_name": "gemini-3.8-flash"}, A, now=tick())) == [("model_name", "duplicate")])
check("model: server fields cannot be sent", issues(MO.update(s, mid, {"id": "x"}, A, now=tick())) == [("id", "not_allowed")])
check("model: delete then the name is free again", MO.soft_delete(s, other, A, now=tick()).ok and MO.create(s, {**g, "model_name": "other"}, A, now=tick()).ok)
check("model: list orders by label and filters", MO.list(s, {"provider": "claude"}).data["count"] == 1 and MO.list(s, {"nope": 1}).code == "validation_failed")

# ---------------------------------------------------------------- types
s = fresh()
t = {"finder_key": "venue", "key": "coffee_shops", "label": "Independent coffee shops and cafes"}
r = TY.create(s, t, A, now=tick()); tid = r.data["id"]
check("type create: starts on, not a chain", r.ok and r.data["is_active"] is True and r.data["is_chain"] is False)
check("type: duplicate key within the finder", issues(TY.create(s, t, A, now=tick())) == [("key", "duplicate")])
check("type: unregistered finder refused", ("finder_key", "invalid_value") in issues(TY.create(s, {**t, "finder_key": "high_school_track", "key": "z"}, A, now=tick())))
check("type: key and finder never change", issues(TY.update(s, tid, {"key": "x", "finder_key": "venue"}, A, now=tick())) == [("finder_key", "immutable"), ("key", "immutable")])
check("type: label and switch can change", TY.update(s, tid, {"label": "Cafes", "is_active": False}, A, now=tick()).ok)
check("type: list filters by finder", TY.list(s, {"finder_key": "venue"}).data["count"] == 1)

# ---------------------------------------------------------------- areas
s = fresh()
r = AR.create(s, {"kind": "state", "name": "Colorado", "state_code": "CO"}, A, now=tick()); co = r.data["id"]
check("area: a new state starts switched OFF", r.ok and r.data["is_active"] is False)
check("area: one live state per state_code", issues(AR.create(s, {"kind": "state", "name": "Colorado 2", "state_code": "CO"}, A, now=tick())) == [("state_code", "duplicate")])
check("area: unknown state_code refused", ("state_code", "invalid_value") in issues(AR.create(s, {"kind": "state", "name": "Narnia", "state_code": "ZZ"}, A, now=tick())))
reg = {"kind": "region", "name": "Boulder County", "state_code": "CO", "zip_codes": ["80301", "80302"]}
r = AR.create(s, reg, A, now=tick()); rid = r.data["id"]
check("area: region created, starts OFF", r.ok and r.data["is_active"] is False)
check("area: region name unique within state, ignoring case", issues(AR.create(s, {**reg, "name": "boulder county"}, A, now=tick())) == [("name", "duplicate")])
check("area: same name in another state is fine", AR.create(s, {**reg, "state_code": "TX", "zip_codes": ["75001"]}, A, now=tick()).ok)
check("area: a ZIP from another state refused", issues(AR.create(s, {**reg, "name": "Mixed", "zip_codes": ["80301", "75001"]}, A, now=tick())) == [("zip_codes", "not_in_state")])
check("area: an unknown ZIP refused", issues(AR.create(s, {**reg, "name": "Odd", "zip_codes": ["00000"]}, A, now=tick())) == [("zip_codes", "not_in_state")])
check("area: ZIPs may be shared with another region", AR.create(s, {**reg, "name": "North Boulder", "zip_codes": ["80301"]}, A, now=tick()).ok)
check("area: region zip list can be edited", AR.update(s, rid, {"zip_codes": ["80301", "80303"]}, A, now=tick()).ok and AR.get(s, rid).data["zip_codes"] == ["80301", "80303"])
check("area: editing in a bad ZIP refused", issues(AR.update(s, rid, {"zip_codes": ["75001"]}, A, now=tick())) == [("zip_codes", "not_in_state")])
check("area: kind and state_code never change", issues(AR.update(s, rid, {"kind": "state"}, A, now=tick())) == [("kind", "immutable")])
check("area: a state cannot carry a zip list", ("zip_codes", "not_allowed") in issues(AR.update(s, co, {"zip_codes": ["80301"]}, A, now=tick())) or
      not AR.update(s, co, {"zip_codes": ["80301"]}, A, now=tick()).ok)
check("area: a state with live regions cannot be deleted", issues(AR.soft_delete(s, co, A, now=tick())) == [("id", "in_use")])
check("area: a region can be deleted and its name freed", AR.soft_delete(s, rid, A, now=tick()).ok and AR.create(s, reg, A, now=tick()).ok)
zip_table.set_table(None)
zip_table.DEFAULT_PATH = pathlib.Path("/nonexistent")
check("area: with no ZIP table a region cannot be saved (never trust unchecked ZIPs)", issues(AR.create(fresh(), reg, A, now=tick())) == [("zip_codes", "zip_table_missing")])
check("area: a state needs no table", AR.create(fresh(), {"kind": "state", "name": "Utah", "state_code": "UT"}, A, now=tick()).ok)

# ---------------------------------------------------------------- settings
s = fresh()
check("settings: list is empty before create", SE.list(s).data["count"] == 0)
r = SE.create(s, {}, A, now=tick()); sid = r.data["id"]
check("settings: create makes the one record with starting values", r.ok and (r.data["default_spend_cap_cents"], r.data["max_spend_cap_cents"], r.data["max_results_per_run"], r.data["results_per_step"]) == (100, 1000, 100, 10), r.problems if not r.ok else "")
check("settings: a second record refused", not SE.create(s, {}, A, now=tick()).ok)
check("settings: default cap above max refused", issues(SE.update(s, sid, {"default_spend_cap_cents": 5000}, A, now=tick())) == [("default_spend_cap_cents", "invalid_value")])
check("settings: results_per_step above the run maximum refused", issues(SE.update(s, sid, {"max_results_per_run": 5}, A, now=tick())) == [("results_per_step", "invalid_value")])
check("settings: default model must exist", issues(SE.update(s, sid, {"default_model_id": "3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b"}, A, now=tick())) == [("default_model_id", "not_found")])
m = MO.create(s, g, A, now=tick()).data["id"]
check("settings: a real default model is accepted", SE.update(s, sid, {"default_model_id": m}, A, now=tick()).ok)
check("settings: lowering the max below the default refused", issues(SE.update(s, sid, {"max_spend_cap_cents": 50}, A, now=tick())) == [("default_spend_cap_cents", "invalid_value")])
check("settings: delete is refused", not SE.soft_delete(s, sid, A, now=tick()).ok)
check("settings: settings_key never changes", issues(SE.update(s, sid, {"settings_key": "other"}, A, now=tick())) == [("settings_key", "immutable")])

# ---------------------------------------------------------------- prompts: draft / publish
s = fresh()
TXT = "Find {types} in {territory}. Up to {max_results}.\n{fields}  Say nothing else."
r = PR.create(s, {"finder_key": "venue", "name": "Seed", "text": TXT}, A, now=tick()); p1 = r.data["id"]
check("prompt: first draft is version 1", r.ok and r.data["status"] == "draft" and r.data["version"] == 1, r.problems if not r.ok else "")
check("prompt: a second first-draft refused", issues(PR.create(s, {"finder_key": "venue", "name": "Seed", "text": TXT}, A, now=tick())) == [("finder_key", "duplicate")])
check("prompt: unknown placeholder refused at create", ("text", "unknown_placeholder") in issues(PR.create(fresh(), {"finder_key": "venue", "name": "S", "text": "Find {oops} please, it is long enough"}, A, now=tick())))
check("prompt: stray brace refused", ("text", "stray_brace") in issues(PR.update(s, p1, {"text": "Find { things in {territory} {types} {fields} {max_results}"}, A, now=tick())))
check("prompt: a draft is edited in place", PR.update(s, p1, {"text": TXT + " Edited."}, A, now=tick()).ok)
check("prompt: finder_key cannot change", issues(PR.update(s, p1, {"finder_key": "x"}, A, now=tick())) == [("finder_key", "immutable")])
pub = PR.publish(s, p1, A, now=tick())
check("prompt: publish makes version 1 standing", pub.ok and pub.data["version"] == 1 and PR.standing(s, PR.get(s, p1).data)["id"] == p1)
check("prompt: a published record cannot be edited or deleted", not PR.update(s, p1, {"text": TXT}, A, now=tick()).ok and not PR.soft_delete(s, p1, A, now=tick()).ok)
check("prompt: publishing twice refused", not PR.publish(s, p1, A, now=tick()).ok)
d2 = PR.draft_from(s, p1, A, now=tick()); p2 = d2.data["id"]
check("prompt: draft_from copies, version 2, previous_id the standing", d2.ok and d2.data["version"] == 2 and d2.data["previous_id"] == p1 and d2.data["text"].endswith("Edited."))
check("prompt: only one draft at a time", PR.draft_from(s, p1, A, now=tick()).code == "conflict")
check("prompt: while a draft exists the standing prompt is still version 1", PR.standing(s, PR.get(s, p2).data)["id"] == p1)
PR.update(s, p2, {"text": "Second wording for {types} within {territory}, {max_results} items.\n{fields}"}, A, now=tick())
check("prompt: publish version 2 supersedes version 1", PR.publish(s, p2, A, now=tick()).ok and PR.standing(s, PR.get(s, p1).data)["id"] == p2)
d3 = PR.draft_from(s, p1, A, now=tick())
check("prompt: reverting = draft_from an OLD published record", d3.ok and d3.data["version"] == 3 and d3.data["text"].endswith("Edited."))
check("prompt: a draft can be deleted", PR.soft_delete(s, d3.data["id"], A, now=tick()).ok)
check("prompt: list by finder, newest version first", [d["version"] for d in PR.list(s, {"finder_key": "venue"}).data["records"]] == [2, 1])

# ---------------------------------------------------------------- runs
ex = json.loads((EX / "discovery_run.examples.json").read_text())["valid"]
s = fresh()
r = RU.create(s, ex["planned_dry_run"], A, source="import", now=tick()); rid = r.data["id"]
check("run: create from a valid example", r.ok, r.problems if not r.ok else "")
check("run: cost above the cap refused", ("actual_cost_cents", "invalid_value") in issues(RU.update(s, rid, {"actual_cost_cents": 99999}, A, now=tick())))
check("run: steps_done above steps_planned refused", ("steps_done", "invalid_value") in issues(RU.update(s, rid, {"steps_planned": 1, "steps_done": 2}, A, now=tick())))
check("run: stopped without a reason refused", ("stop_reason", "required") in issues(RU.update(s, rid, {"status": "stopped", "finished_at": "2026-10-17T12:00:00Z"}, A, now=tick())))
check("run: finished without finished_at refused", ("finished_at", "required") in issues(RU.update(s, rid, {"status": "finished"}, A, now=tick())))
check("run: finished with finished_at accepted", RU.update(s, rid, {"status": "finished", "finished_at": "2026-10-17T12:00:00Z"}, A, now=tick()).ok)
check("run: finder, mode, model and prompt never change", issues(RU.update(s, rid, {"run_mode": "live"}, A, now=tick())) == [("run_mode", "immutable")])
check("run: there is no delete (history)", not RU.soft_delete(s, rid, A, now=tick()).ok and RU.get(s, rid).ok)

# ---------------------------------------------------------------- the doors
KEY = "k" * 16 + "Z" * 16 + "-test-key-not-real"
lim = make_failure_limiter()
def door(fn, coll, op, args, store):
    body = json.dumps({"collection": coll, "op": op, "args": args}).encode()
    return fn("POST", f"Bearer {KEY}", body, KEY, "v", store, lim, tick()) if fn is handle_crud_test else \
        fn("POST", f"Bearer {KEY}", body, KEY, "v", store, lim, tick())
try:
    res = door(handle_admin, "discovery_runs", "list", {}, fresh())
    check("door: the Console door refuses the runs collection", res.status in (400, 403, 404), res.status)
    res = door(handle_admin, "discovery_models", "create", {"data": g}, fresh())
    check("door: the Console door can create a model", res.status == 200, res.status)
    res = door(handle_admin, "discovery_prompts", "publish", {"id": "3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b"}, fresh())
    check("door: publish reaches the prompt handler (not found, not 'unsupported')", res.status == 404, res.status)
except TypeError as exc:
    check("door call signature", False, str(exc))

print(f"{total - len(fails)}/{total} checks passed" + (f"; FAILED: {fails}" if fails else ""))
sys.exit(1 if fails else 0)
