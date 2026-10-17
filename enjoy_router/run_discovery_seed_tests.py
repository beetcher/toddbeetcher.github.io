#!/usr/bin/env python3
"""Dry run of seed_discovery.py against an in-memory store through the real admin door (no network, no key).
Run from enjoy_router/:  python3 run_discovery_seed_tests.py   (-v lists every check)."""
import json, pathlib, sys
from datetime import datetime, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud.memory_doc_store import MemoryDocStore
from crud_endpoint import handle_admin, make_failure_limiter
from launch_discovery import zip_table
import seed_discovery as S

KEY = "k" * 16 + "Z" * 16 + "-dry-run-key"
fails, total = [], 0
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    if not ok or "-v" in sys.argv: print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")
store, limiter = MemoryDocStore(""), make_failure_limiter()
def call(coll, op, **args):
    r = handle_admin("POST", "Bearer " + KEY, json.dumps({"collection": coll, "op": op, "args": args}).encode(), KEY, "v", store, limiter, datetime.now(timezone.utc))
    return r.status, r.body
quiet = lambda *_: None
res = S.seed(call, say=quiet)
rec = lambda coll, **f: S._records(call, coll, **f)
check("seed: no errors", res["errors"] == [], res["errors"])
check("seed: 51 areas (50 states and DC), only Colorado on", len(rec("discovery_areas")) == 51 and [a["state_code"] for a in rec("discovery_areas") if a["is_active"]] == ["CO"])
check("seed: five models, two on (Gemini), three off until keys are set", len(rec("discovery_models")) == 5 and
      sorted(m["model_name"] for m in rec("discovery_models") if m["is_active"]) == ["gemini-3.5-flash-lite", "gemini-3.8-flash"])
import re
check("seed: model records name a key setting (ICDT_..._KEY), never hold a key", all(
    (m.get("key_name") is None) == (m["provider"] == "gemini") and re.fullmatch(r"ICDT_[A-Z]+_KEY", m.get("key_name") or "ICDT_X_KEY")
    and not re.search(r"sk-[A-Za-z0-9]|AIza", json.dumps(m)) for m in rec("discovery_models")))
check("seed: four venue types, Panera is the chain", [t["key"] for t in rec("discovery_types")] == ["coffee_shops", "libraries", "panera", "community_centers"]
      and [t["key"] for t in rec("discovery_types") if t["is_chain"]] == ["panera"])
p = rec("discovery_prompts")
check("seed: the venue prompt is published as version 1", len(p) == 1 and p[0]["status"] == "published" and p[0]["version"] == 1)
check("seed: the settings record has the starting values", [(s["default_spend_cap_cents"], s["max_spend_cap_cents"], s["max_results_per_run"], s["results_per_step"]) for s in rec("discovery_settings")] == [(10, 10, 10, 10)])
res2 = S.seed(call, say=quiet)
check("seed: running it again adds nothing", res2["added"] == {} and res2["errors"] == [] and len(rec("discovery_areas")) == 51)
res3 = S.seed(call, say=quiet, regions=True)
check("seed regions: refused while the ZIP table is missing (never trust unchecked ZIPs)", len(res3["errors"]) == 3 and not rec("discovery_areas", kind="region"))
zip_table.set_table({z: ["CO", 40.0, -105.0, "X"] for r in S.REGIONS for z in r["zip_codes"]})
res4 = S.seed(call, say=quiet, regions=True)
check("seed regions: added once the table is loaded, and again adds nothing", res4["added"] == {"discovery_areas": 3} and not res4["errors"]
      and S.seed(call, say=quiet, regions=True)["added"] == {})
print(f"{total - len(fails)}/{total} checks passed" + (f"; FAILED: {fails}" if fails else ""))
sys.exit(1 if fails else 0)
