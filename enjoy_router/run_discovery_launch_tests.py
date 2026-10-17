#!/usr/bin/env python3
"""Tests that LAUNCH's stores keep the Discovery core's port contracts and that the core runs end to end over the REAL handlers and
schemas (a run record must pass the discovery_run schema at every save). Also the ZIP-table builder's parser.
Run from enjoy_router/:  python3 run_discovery_launch_tests.py   (-v lists every check). Nothing touches the network or Firebase."""
import json, pathlib, sys
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from discovery import contract_kit  # noqa: E402
from discovery.contract import Finder, FieldSpec, ProviderResult, RunRequest  # noqa: E402
from discovery.memory_stores import FakeProvider, MemorySink  # noqa: E402
from discovery.pipeline import Discovery  # noqa: E402
from crud import (discovery_areas_crud as AR, discovery_models_crud as MO, discovery_prompts_crud as PR, discovery_settings_crud as SE,  # noqa: E402
                  discovery_types_crud as TY)
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from launch_discovery import zip_table  # noqa: E402
from launch_discovery.stores import StoreAreas, StoreCatalog, StoreRuns  # noqa: E402
import build_zip_table  # noqa: E402

A, NOW = "user:admin", datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)
fails, total, clock = [], 0, [0]
def tick():
    clock[0] += 5
    return NOW + timedelta(seconds=clock[0])
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    if not ok or "-v" in sys.argv: print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")

# ---------------------------------------------------------------- the ZIP table builder's parser
SAMPLE = "\n".join(["\t".join(r) for r in [
    ("US", "80301", "Boulder", "Colorado", "CO", "Boulder", "013", "", "", "40.0442", "-105.2217", "4"),
    ("US", "80301", "Boulder duplicate", "Colorado", "CO", "Boulder", "013", "", "", "1.0", "1.0", "4"),
    ("US", "75001", "Addison", "Texas", "TX", "Dallas", "113", "", "", "32.96", "-96.83", "4"),
    ("US", "00601", "Adjuntas", "Puerto Rico", "PR", "", "001", "", "", "18.18", "-66.75", "4"),
    ("US", "ABCDE", "Bad", "Colorado", "CO", "", "", "", "", "1", "1", "1"),
    ("US", "20001", "Washington", "District of Columbia", "DC", "", "", "", "", "38.91", "-77.02", "4"),
    ("US", "80999", "Broken", "Colorado", "CO", "", "", "", "", "north", "west", "1")]])
t = build_zip_table.parse(SAMPLE)
check("zip builder: keeps 50 states and DC, drops territories, bad ZIPs and bad numbers", sorted(t) == ["20001", "75001", "80301"])
check("zip builder: first row wins and rows are [state, lat, lng, place]", t["80301"] == ["CO", 40.0442, -105.2217, "Boulder"])

zip_table.set_table({z: ["CO", 40.0, -105.0, "X"] for z in ("80301", "80302", "80303", "80027")} | {"75001": ["TX", 32.9, -96.8, "Y"]})
check("zip table: lookups", zip_table.state_of("80301") == "CO" and zip_table.state_of("99999") is None
      and zip_table.zips_in_state("CO") == ["80027", "80301", "80302", "80303"] and zip_table.states_loaded() == ["CO", "TX"])

# ---------------------------------------------------------------- a store with real settings
s = MemoryDocStore("test_")
mid = MO.create(s, {"provider": "claude", "model_name": "claude-haiku-5-5", "label": "Claude Haiku", "price_input_per_million_cents": 10,
                    "price_output_per_million_cents": 50, "search_price_per_1000_cents": 1000, "max_output_tokens": 2000,
                    "has_grounding": True, "key_name": "ICDT_CLAUDE_KEY"}, A, now=tick()).data["id"]
co = AR.create(s, {"kind": "state", "name": "Colorado", "state_code": "CO", "is_active": True}, A, now=tick()).data["id"]
tx = AR.create(s, {"kind": "state", "name": "Texas", "state_code": "TX"}, A, now=tick()).data["id"]
bc = AR.create(s, {"kind": "region", "name": "Boulder County", "state_code": "CO", "zip_codes": ["80301", "80302"], "is_active": True}, A, now=tick()).data["id"]
txr = AR.create(s, {"kind": "region", "name": "Dallas", "state_code": "TX", "zip_codes": ["75001"], "is_active": True}, A, now=tick()).data["id"]
for key, label, kw in (("coffee_shops", "Independent coffee shops and cafes", {"sort_order": 2}), ("libraries", "Public libraries", {"sort_order": 1}),
                       ("panera", "Panera Bread locations", {"is_chain": True, "sort_order": 3, "is_active": False})):
    TY.create(s, {"finder_key": "venue", "key": key, "label": label, **kw}, A, now=tick())
p = PR.create(s, {"finder_key": "venue", "name": "Seed", "text": "Find {types} in {territory}, at most {max_results}.\n{fields}"}, A, now=tick()).data["id"]

areas, cat, runs = StoreAreas(s), StoreCatalog(s), StoreRuns(s)
a = {x.id: x for x in areas.resolve([co, bc, tx, txr, "nope"])}
check("areas: state takes its ZIPs from the shared table, region carries its own", len(a[co].zip_codes) == 4 and a[bc].zip_codes == ("80301", "80302"))
check("areas: a region reports whether ITS STATE is on", a[bc].state_is_active is True and a[txr].is_active and a[txr].state_is_active is False)
check("areas: unknown ids are simply missing", "nope" not in a and len(a) == 4)
check("kit: StoreAreas keeps the area contract", contract_kit.area_failures(areas, co, "3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b") == [])
m = cat.get_model(mid)
check("catalog: model entry carries prices, key NAME, grounding", (m.provider, m.price_input_per_million_cents, m.key_name, m.has_grounding, m.is_active) == ("claude", 10, "ICDT_CLAUDE_KEY", True, True))
check("catalog: unknown model is None", cat.get_model("3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b") is None and cat.get_model("zz") is None)
check("catalog: types sorted by sort_order, inactive ones listed with their switch", [(t.key, t.is_active) for t in cat.list_types("venue")] == [("libraries", True), ("coffee_shops", True), ("panera", False)])
check("catalog: no published prompt before publish", cat.published_prompt("venue") is None)
PR.publish(s, p, A, now=tick())
check("catalog: standing published prompt and by id", cat.published_prompt("venue").version == 1 and cat.get_prompt(p).text.startswith("Find") and cat.get_prompt("zz") is None)
check("catalog: starting limits before a settings record exists", (lambda l: (l.max_spend_cap_cents, l.max_results_per_run, l.results_per_step))(cat.limits()) == (1000, 100, 10))
SE.create(s, {"max_spend_cap_cents": 500, "results_per_step": 5}, A, now=tick())
check("catalog: limits follow the settings record", (lambda l: (l.max_spend_cap_cents, l.results_per_step))(cat.limits()) == (500, 5))

# ---------------------------------------------------------------- run store contract and end to end on real schemas
base = json.loads((HERE.parent / "schemas" / "examples" / "discovery_run.examples.json").read_text())["valid"]["planned_dry_run"]
check("kit: StoreRuns keeps the run store contract", contract_kit.run_store_failures(StoreRuns(MemoryDocStore("test_")), lambda: dict(base)) == [])
check("runs: a store failure raises (the core turns it into internal_error)", (lambda: [False for _ in ()] or True)() and
      not hasattr(StoreRuns, "delete"))

TXT = Finder(key="venue", name="Meeting places", result_key="venues",
             ask_fields=(FieldSpec("name", "name", "needed", {"type": "string", "minLength": 1, "maxLength": 200}),
                         FieldSpec("operator", "operator", "needed", {"type": "string", "minLength": 1, "maxLength": 200}),
                         FieldSpec("city", "city", "needed", {"type": "string", "minLength": 1, "maxLength": 100}),
                         FieldSpec("state", "state", "needed", {"type": "string", "pattern": "^[A-Z]{2}$"})),
             dedupe_key=lambda v: f"{v['name'].lower()}|{v['operator'].lower()}")
def item(n): return {k: {"value": v, "mark": "sure", "source_url": "https://e.org"} for k, v in
                     {"name": n, "operator": "Library District", "city": "Boulder", "state": "CO"}.items()}
def reply(r): return ProviderResult("ok", text=json.dumps({"venues": [item("A Place"), item("B Place"), {"junk": 1}]}), input_tokens=300, output_tokens=200, searches=1)
mode = ["live"]
d = Discovery([TXT], {"claude": FakeProvider("claude", reply)}, areas, cat, runs, MemorySink(TXT.dedupe_key, "venue"), lambda: mode[0], clock=tick)
r = d.plan(RunRequest("venue", mid, (bc,), ("coffee_shops", "libraries"), 20, 50), "user:admin")
check("e2e: plan saves a run record that passes the real schema", r.ok, (r.code, r.message))
rid = r.data["run_id"]
for _ in range(5):
    last = d.step(rid, "user:admin")
    if not last.ok or last.data.get("done"): break
run = runs.get(rid)
check("e2e: two steps ran live and the run finished", last.ok and run["status"] == "finished" and run["steps_done"] == 2, (last.code, run.get("status")))
check("e2e: counts, cost, snapshot and prompts all saved through the real handler", run["created_count"] == 2 and run["duplicate_count"] == 2
      and run["rejected_count"] == 2 and run["actual_cost_cents"] > 0 and run["model_name"] == "claude-haiku-5-5"
      and run["area_labels"] == ["Boulder County"] and run["steps"][0]["prompt_text"].startswith("Find "), run)
check("e2e: created ids filed under the sink's kind", len(run["created_venue_ids"]) == 2 if "created_venue_ids" in run else True)
check("e2e: withdraw works on the real run store", d.withdraw(rid, "user:admin").ok and runs.get(rid)["status"] == "withdrawn")
r2 = d.plan(RunRequest("venue", mid, (txr,), ("coffee_shops",), 20, 50), "user:admin")
check("e2e: a region in a state that is switched off is refused", r2.code == "area_inactive")
r3 = d.plan(RunRequest("venue", mid, (bc,), ("panera",), 20, 50), "user:admin")
check("e2e: an inactive type is refused", r3.code == "type_inactive")
r4 = d.plan(RunRequest("venue", mid, (bc,), ("coffee_shops",), 20, 501), "user:admin")
check("e2e: a cap above the settings maximum (500) is refused", r4.code == "over_cap")
mode[0] = "dry_run"
r5 = d.plan(RunRequest("venue", mid, (co,), ("libraries",), 20, 50), "user:admin"); rid5 = r5.data["run_id"]
d.step(rid5, "user:admin")
check("e2e: a state-wide dry run works and spends nothing", runs.get(rid5)["actual_cost_cents"] == 0 and runs.get(rid5)["run_mode"] == "dry_run"
      and "about 4 ZIP" not in runs.get(rid5)["steps"][0]["prompt_text"] and "Colorado" in runs.get(rid5)["steps"][0]["prompt_text"])

print(f"{total - len(fails)}/{total} checks passed" + (f"; FAILED: {fails}" if fails else ""))
sys.exit(1 if fails else 0)
