#!/usr/bin/env python3
"""Tests for the Discovery door (discovery_door.py) and the wiring (launch_discovery/wiring.py): the key, the ops, the mode from the
environment, and the run mode. A fake AI stands in; nothing touches the network or Firebase.
Run from enjoy_router/:  python3 run_discovery_door_tests.py   (-v lists every check)."""
import json, pathlib, sys
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import (discovery_areas_crud as AR, discovery_models_crud as MO, discovery_prompts_crud as PR, discovery_types_crud as TY)  # noqa: E402
from crud import geocoder  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from console import make_failure_limiter  # noqa: E402
from discovery.contract import ProviderResult  # noqa: E402
from discovery.memory_stores import FakeProvider  # noqa: E402
from discovery_door import handle_discovery  # noqa: E402
from launch_discovery import wiring, zip_table  # noqa: E402

START = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)
KEY = "k" * 16 + "Z" * 16 + "-test-key-not-real"
SECRET = "sk-REAL-LOOKING-SECRET-1234567890"
A = "user:admin"
fails, total, clock = [], 0, [0]
def tick():
    clock[0] += 3
    return START + timedelta(seconds=clock[0])
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    if not ok or "-v" in sys.argv: print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")

zip_table.set_table({z: ["CO", 40.0, -105.0, "X"] for z in ("80301", "80302")})
store = MemoryDocStore("")
mid = MO.create(store, {"provider": "gemini", "model_name": "gemini-3.8-flash", "label": "Gemini", "price_input_per_million_cents": 75,
                        "price_output_per_million_cents": 375, "has_grounding": False}, A, now=tick()).data["id"]
MO.create(store, {"provider": "claude", "model_name": "claude-haiku-5-5", "label": "Haiku", "price_input_per_million_cents": 10, "price_output_per_million_cents": 50,
                  "has_grounding": False, "key_name": "ICDT_CLAUDE_KEY", "is_active": False}, A, now=tick())
AR.create(store, {"kind": "state", "name": "Colorado", "state_code": "CO", "is_active": True}, A, now=tick())
reg = AR.create(store, {"kind": "region", "name": "Boulder", "state_code": "CO", "zip_codes": ["80301", "80302"], "is_active": True}, A, now=tick()).data["id"]
TY.create(store, {"finder_key": "venue", "key": "cafes", "label": "Cafes"}, A, now=tick())
seed = json.loads((HERE.parent / "schemas" / "examples" / "discovery_prompt.examples.json").read_text())["valid"]["venue_seed_prompt"]
PR.publish(store, PR.create(store, {"finder_key": "venue", "name": "Seed", "text": seed["text"]}, A, now=tick()).data["id"], A, now=tick())

seen_gps = []
def ai(req):
    seen_gps.append(geocoder.lookup)
    item = {k: {"value": v, "mark": "sure", "source_url": "https://e.org"} for k, v in
            {"name": "Ozo Coffee", "operator": "Ozo Co", "city": "Boulder", "state": "CO", "is_public_venue": True, "street": "1825 Pearl St"}.items()}
    return ProviderResult("ok", text=json.dumps({"venues": [item]}), input_tokens=500, output_tokens=300)
ENV = {"ICDT_DISCOVERY_MODE": "live", "ICDT_CLAUDE_KEY": SECRET}
engine = wiring.build_engine(store, ENV, providers={"gemini": FakeProvider("gemini", ai)}, clock=tick)
limiter = make_failure_limiter()

def call(op, args=None, key=KEY, method="POST", env=ENV, eng=None, raw=None):
    body = raw if raw is not None else json.dumps({"op": op, "args": args or {}}).encode()
    return handle_discovery(method, f"Bearer {key}" if key else "", body, KEY, "visitor", store, eng or engine, env, limiter, tick())
REQ = {"finder_key": "venue", "model_id": mid, "area_ids": [reg], "type_keys": ["cafes"], "max_results": 10, "spend_cap_cents": 50}

# ---------------------------------------------------------------- the lock
check("door: no key setting means nothing is allowed", handle_discovery("POST", "Bearer x", b"{}", "", "v", store, engine, ENV, limiter, tick()).status == 401
      and handle_discovery("POST", "Bearer x", b"{}", "short", "v", store, engine, ENV, limiter, tick()).status == 401)
check("door: a key under 32 characters is refused even when it matches", handle_discovery("POST", "Bearer short", b'{"op": "status"}', "short", "v", store, engine, ENV, limiter, tick()).status == 401)
check("door: no key / wrong key = 401", call("status", key=None).status == 401 and call("status", key="w" * 40).status == 401)
check("door: only POST", call("status", method="GET").status == 405)
check("door: bad JSON, unknown op, extra args, missing args are 400", call("x", raw=b"{nope").status == 400 and call("nope").status == 400
      and call("step", {"run_id": "r", "extra": 1}).status == 400 and call("step").status == 400)
check("door: too large a body", call("status", raw=b"{" + b" " * 30000 + b"}").status == 413)
check("door: bad shapes in a plan are 400 bad_request", call("plan", {**REQ, "area_ids": "x"}).status == 400 and call("plan", {**REQ, "max_results": True}).status == 400
      and call("plan", {**REQ, "type_keys": []}).status == 400)

# ---------------------------------------------------------------- status
r = call("status")
st = r.body["data"]
check("status: mode from the environment, key presence as yes/no, ZIP table, project", r.status == 200 and st["mode"] == "live" and st["keys"] == {"ICDT_CLAUDE_KEY": True}
      and st["zip_table"]["loaded"] and st["project"] == "launch-ai-workshop", st)
check("status: never contains a key", SECRET not in json.dumps(r.body))
check("status: a missing key shows False, an unknown mode shows off", call("status", env={"ICDT_DISCOVERY_MODE": "go"}).body["data"]["keys"] == {"ICDT_CLAUDE_KEY": False}
      and call("status", env={"ICDT_DISCOVERY_MODE": "go"}).body["data"]["mode"] == "off")

# ---------------------------------------------------------------- quote, plan, step, read, withdraw
r = call("quote", REQ)
check("quote: cost range and the exact prompt, nothing saved", r.status == 200 and r.body["data"]["prompts"][0]["prompt_text"].count("Cafes") >= 1
      and not store.query("discovery_runs", [], limit=5))
r = call("plan", REQ); rid = r.body["data"]["run_id"]
check("plan: saves the run, returns its id and the estimate", r.status == 200 and rid and r.body["data"]["steps_planned"] == 1)
geocoder.lookup = "SENTINEL"
r = call("step", {"run_id": rid})
check("step: one chunk, then done", r.status == 200 and r.body["data"]["done"] is True and r.body["data"]["status"] == "finished", r.body)
check("step: no GPS lookup while saving, and the hook is put back afterwards", seen_gps == [None] and geocoder.lookup == "SENTINEL"); geocoder.lookup = None
g = call("get_run", {"id": rid}).body["data"]
check("get_run: counts, cost and the stored prompt", (g["created_count"], g["status"]) == (1, "finished") and g["actual_cost_cents"] > 0 and g["steps"][0]["prompt_text"])
check("get_run: unknown id is 404", call("get_run", {"id": "3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b"}).status == 404)
ls = call("list_runs", {"limit": 5}).body["data"]
check("list_runs: newest first", ls["count"] == 1 and ls["records"][0]["id"] == rid and call("list_runs", {"limit": "x"}).status == 400)
check("step on a finished run is 409", call("step", {"run_id": rid}).status == 409 and call("step", {"run_id": "nope"}).status == 404)
r = call("withdraw", {"run_id": rid})
check("withdraw: takes the venue back", r.status == 200 and r.body["data"]["removed"].get("venue") == 1 and not [v for v in store.query("venues", [], limit=9) if "deleted_at" not in v])
check("withdraw twice is 409", call("withdraw", {"run_id": rid}).status == 409)
r = call("plan", REQ); rid2 = r.body["data"]["run_id"]
check("stop: ends a planned run as the operator's choice", call("stop", {"run_id": rid2}).status == 200 and call("get_run", {"id": rid2}).body["data"]["stop_reason"] == "operator")

# ---------------------------------------------------------------- refusals and the mode
check("plan with the mode off (default) is 409 mode_off", call("plan", REQ, env={}, eng=wiring.build_engine(store, {}, providers={"gemini": FakeProvider()})).status == 409)
check("plan: inactive model 400 / unknown model 404 / cap above maximum 400", call("plan", {**REQ, "model_id": MO.list(store, {"provider": "claude"}).data["records"][0]["id"]}).status == 400
      and call("plan", {**REQ, "model_id": "zz"}).status == 404 and call("plan", {**REQ, "spend_cap_cents": 5000}).status == 400)
r = call("plan", {**REQ, "area_ids": ["nope"]})
check("plan: refusals carry a code and a plain message, nothing else", r.status == 404 and r.body["error"]["code"] == "unknown_area" and set(r.body["error"]) == {"code", "message"})
dry = wiring.build_engine(store, {"ICDT_DISCOVERY_MODE": "dry_run"}, providers={"gemini": FakeProvider("gemini", ai)}, clock=tick)
n_before = len(seen_gps)
rid3 = call("plan", REQ, eng=dry, env={"ICDT_DISCOVERY_MODE": "dry_run"}).body["data"]["run_id"]; call("step", {"run_id": rid3}, eng=dry)
check("dry_run through the door: prompts built, no AI call, nothing spent", len(seen_gps) == n_before and call("get_run", {"id": rid3}).body["data"]["actual_cost_cents"] == 0)
check("nothing the door returns contains the key", all(SECRET not in json.dumps(x.body) for x in (call("status"), call("list_runs"), call("get_run", {"id": rid}))))

print(f"{total - len(fails)}/{total} checks passed" + (f"; FAILED: {fails}" if fails else ""))
sys.exit(1 if fails else 0)
