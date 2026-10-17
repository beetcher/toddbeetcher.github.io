#!/usr/bin/env python3
"""Step 7 proof, offline: the SAME small job is run on Gemini, Claude (two models) and OpenAI through the real adapters, the real engine, the
real sink and the real door, with a fake network. The only thing that changes between runs is the model chosen. Checks that each vendor
gets its own correctly shaped request and key, that the saved candidates are identical apart from the model name, that each run is priced
with ITS model's prices and stays under the cap, and that no key ever appears in a run, a prompt or a reply.
This proves the wiring, not the vendors: the live proof (a tiny real run on Claude) is run by Todd on his Mac.
Run from enjoy_router/:  python3 run_discovery_swap_test.py   (-v lists every check)."""
import json, pathlib, sys
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import (discovery_models_crud as MO, discovery_runs_crud as RU, venues_crud as VE)
from crud.memory_doc_store import MemoryDocStore
from crud_endpoint import handle_admin, make_failure_limiter
from console import make_failure_limiter as door_limiter
from discovery_door import handle_discovery
from launch_discovery import wiring, zip_table
from launch_discovery.providers.build import build_providers
import seed_discovery as SEED

KEY = "k" * 16 + "Z" * 16 + "-swap-test-key"
SECRETS = {"ICDT_CLAUDE_KEY": "sk-ant-SECRET-CLAUDE-1234567890", "ICDT_OPENAI_KEY": "sk-SECRET-OPENAI-1234567890"}
TOKEN = "ya29.SECRET-GOOGLE-TOKEN"
fails, total, clock = [], 0, [0]
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    if not ok or "-v" in sys.argv: print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")
def tick():
    clock[0] += 3
    return datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=clock[0])

zip_table.set_table({z: ["CO", 40.0 + i / 100, -105.0, "Boulder"] for i, z in enumerate(("80301", "80302", "80303", "80304", "80305", "80027", "80026", "80501", "80503", "80504"))})
store, limiter, dlimiter = MemoryDocStore(""), make_failure_limiter(), door_limiter()
def seed_call(coll, op, **args):
    r = handle_admin("POST", "Bearer " + KEY, json.dumps({"collection": coll, "op": op, "args": args}).encode(), KEY, "v", store, limiter, tick())
    return r.status, r.body
SEED.seed(seed_call, say=lambda *_: None); SEED.seed(seed_call, say=lambda *_: None, regions=True)
for m in SEED._records(seed_call, "discovery_models"):                       # switch every model on: only the key decides who can run
    if not m["is_active"]:
        MO.update(store, m["id"], {"is_active": True}, "user:admin", now=tick())
models = {m["model_name"]: m for m in SEED._records(seed_call, "discovery_models")}
boulder = [a for a in SEED._records(seed_call, "discovery_areas", kind="region") if a["name"] == "Boulder"][0]

def item(**kw): return {k: {"value": v, "mark": "sure", "source_url": "https://example.org/" + k} for k, v in kw.items()}
VENUES = [item(name="Ozo Coffee", operator="Ozo Coffee Company", city="Boulder", state="CO", is_public_venue=True, street="1825 Pearl St"),
          item(name="Corner Table Cafe", operator="Corner Table LLC", city="Boulder", state="CO", is_public_venue=True)]
TEXT = json.dumps({"venues": VENUES})
calls = []
def net(url, headers, body, timeout_s):
    calls.append((url, dict(headers), body, timeout_s))
    if "aiplatform.googleapis.com" in url:
        return 200, {"candidates": [{"content": {"parts": [{"text": TEXT}]}, "groundingMetadata": {"webSearchQueries": ["q"]}}],
                     "usageMetadata": {"promptTokenCount": 10000, "candidatesTokenCount": 3000, "thoughtsTokenCount": 0}}
    if "anthropic.com" in url:
        return 200, {"content": [{"type": "text", "text": TEXT}], "usage": {"input_tokens": 10000, "output_tokens": 3000, "server_tool_use": {"web_search_requests": 1}}}
    if "openai.com" in url:
        return 200, {"output": [{"type": "web_search_call"}, {"type": "message", "content": [{"type": "output_text", "text": TEXT}]}], "usage": {"input_tokens": 10000, "output_tokens": 3000}}
    return 404, None
ENV = {"ICDT_DISCOVERY_MODE": "live", **SECRETS}
providers = build_providers("test-project", transport=net, secret_fn=lambda n: ENV.get(n), token_fn=lambda: TOKEN)
engine = wiring.build_engine(store, ENV, providers=providers, clock=tick)
def door(op, args=None): return handle_discovery("POST", "Bearer " + KEY, json.dumps({"op": op, "args": args or {}}).encode(), KEY, "v", store, engine, ENV, dlimiter, tick())

def run_on(model_name, env_ok=True):
    """One run with the model as the ONLY difference. Returns (run record, calls made during it)."""
    start = len(calls)
    req = {"finder_key": "venue", "model_id": models[model_name]["id"], "area_ids": [boulder["id"]], "type_keys": ["coffee_shops"], "max_results": 10, "spend_cap_cents": 10}
    q = door("quote", req); p = door("plan", req)
    if p.status != 200: return None, calls[start:], p
    rid = p.body["data"]["run_id"]
    for _ in range(10):
        s = door("step", {"run_id": rid})
        if s.status != 200 or s.body["data"]["done"]: break
    return door("get_run", {"id": rid}).body["data"], calls[start:], q

results = {}
for name in ("gemini-3.8-flash", "claude-haiku-5-5", "claude-sonnet-5-5", "gpt-6-luna"):
    run, made, _ = run_on(name)
    results[name] = (run, made)
    vs = [VE.get(store, i).data for i in (run or {}).get("created_venue_ids", [])]
    results[name] += ({v["name"]: v for v in vs},)
    check(f"{name}: the run finished, made one call, saved both candidates inactive", run is not None and run["status"] == "finished" and len(made) == 1 and run["created_count"] == 2
          and all(v["status"] == "inactive" for v in vs), run and (run["status"], run.get("created_count"), len(made)))
    door("withdraw", {"run_id": run["id"]}) if run else None                       # take them back so the next model starts clean

g, c, s, o = (results[n][1][0] for n in ("gemini-3.8-flash", "claude-haiku-5-5", "claude-sonnet-5-5", "gpt-6-luna"))
check("each vendor gets its own endpoint", "aiplatform.googleapis.com/v1/projects/test-project/" in g[0] and g[0].endswith("gemini-3.8-flash:generateContent")
      and c[0] == "https://api.anthropic.com/v1/messages" and o[0].startswith("https://api.openai.com/"), [g[0], c[0], o[0]])
check("each vendor is signed in its own way, with its own secret", g[1] == {"Authorization": "Bearer " + TOKEN} and c[1]["x-api-key"] == SECRETS["ICDT_CLAUDE_KEY"]
      and "SECRET-OPENAI" in json.dumps(o[1]) and SECRETS["ICDT_CLAUDE_KEY"] not in json.dumps(o[1]) and TOKEN not in json.dumps(c[1]))
check("the model name sent is the model chosen", c[2]["model"] == "claude-haiku-5-5" and s[2]["model"] == "claude-sonnet-5-5" and o[2]["model"] == "gpt-6-luna")
sent = {"gemini": g[2]["contents"][0]["parts"][0]["text"], "claude": c[2]["messages"][0]["content"], "openai": o[2]["input"] if isinstance(o[2].get("input"), str) else json.dumps(o[2].get("input"))}
check("the same prompt text reaches every vendor", len({sent["gemini"], sent["claude"]}) == 1 and sent["claude"] in sent["openai"], [len(v) for v in sent.values()])
check("the stored prompt is exactly what Claude was sent", results["claude-haiku-5-5"][0]["steps"][0]["prompt_text"] == c[2]["messages"][0]["content"])

def stripped(v): return {k: v[k] for k in ("name", "status", "is_public_venue", "slug") if k in v}
base = results["gemini-3.8-flash"][2]
for n in ("claude-haiku-5-5", "claude-sonnet-5-5", "gpt-6-luna"):
    other = results[n][2]
    check(f"{n}: the saved candidates match the Gemini ones apart from the model name", sorted(other) == sorted(base)
          and all(other[k]["status"] == base[k]["status"] and other[k]["is_public_venue"] == base[k]["is_public_venue"] and other[k]["discovery"]["marks"] == base[k]["discovery"]["marks"]
                  and other[k]["discovery"]["needs_attention"] == base[k]["discovery"]["needs_attention"] for k in base)
          and all(other[k]["discovery"]["model_name"] == n for k in other) and all(base[k]["discovery"]["model_name"] == "gemini-3.8-flash" for k in base))
costs = {n: results[n][0]["actual_cost_cents"] for n in results}
check("every run was priced with its own model's prices and stayed under the cap", all(0 < costs[n] <= 10 for n in costs)
      and all(results[n][0]["model_price_input_per_million_cents"] == models[n]["price_input_per_million_cents"] for n in results), costs)
from fractions import Fraction
import math
def expect(m): return math.ceil(Fraction(10000 * m["price_input_per_million_cents"], 1_000_000) + Fraction(3000 * m["price_output_per_million_cents"], 1_000_000) + Fraction(1 * (m.get("search_price_per_1000_cents") or 0), 1000))
check("each run cost exactly what its own model's prices make it", all(costs[n] == expect(models[n]) for n in costs), {n: (costs[n], expect(models[n])) for n in costs})
check("the dearer model costs more for the same tokens", costs["claude-sonnet-5-5"] > costs["claude-haiku-5-5"], costs)
check("the run records say which model made them", [results[n][0]["model_name"] for n in results] == list(results))

# a model whose key is not set cannot run, says so, and nothing is sent
del ENV["ICDT_CLAUDE_KEY"]
before = len(calls)
run, made, _ = run_on("claude-haiku-5-5")
check("no Claude key: the run does not call anyone and records the reason", len(calls) == before and (run is None or (run["created_count"] == 0 and any(st["error_code"] == "key_missing" for st in run["steps"]))), run and [st.get("error_code") for st in run["steps"]])
ENV["ICDT_CLAUDE_KEY"] = SECRETS["ICDT_CLAUDE_KEY"]
st = door("status").body["data"]
check("status reports key presence as yes/no only", st["keys"] == {"ICDT_CLAUDE_KEY": True, "ICDT_OPENAI_KEY": True} and not any(v in json.dumps(st) for v in list(SECRETS.values()) + [TOKEN]))
everything = json.dumps([RU.list(store, None, "-created_at", 50).data, [door("get_run", {"id": r["id"]}).body for r in RU.list(store, None, "-created_at", 50).data["records"]]])
check("no key or token appears in any run record or reply", not any(v in everything for v in list(SECRETS.values()) + [TOKEN]))
print(f"\n{total - len(fails)}/{total} checks passed" + ("" if not fails else "  FAILED: " + "; ".join(fails)))
sys.exit(1 if fails else 0)
