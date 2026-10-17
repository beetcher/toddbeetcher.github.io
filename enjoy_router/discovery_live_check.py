#!/usr/bin/env python3
"""The live check for Discovery (step 5), run from Todd's Mac. Talks to the DEPLOYED doors with the admin key from .env.launch-ai-workshop
(never printed). Each command is small and says what it did.

    python3 enjoy_router/discovery_live_check.py status            the mode, which model keys exist, the ZIP table (no AI call, no cost)
    python3 enjoy_router/discovery_live_check.py dry               an estimate + a dry run for Boulder coffee shops (no AI call, no cost)
    python3 enjoy_router/discovery_live_check.py live [model] [cap]  a TINY live run (3 results, cap in cents, default 10) on that model name
                                                                   (default gemini-3.5-flash-lite), then lists what it saved. A call with 5 web searches can cost up to 7 cents on Gemini, so a cap under about 9 stops with cap_reached before any call.
    python3 enjoy_router/discovery_live_check.py withdraw RUN_ID   takes a run's untouched candidates back

The live command needs ICDT_DISCOVERY_MODE=live on the server. It never contacts a venue; candidates are saved inactive."""
import json, pathlib, sys, time, urllib.error, urllib.request
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run_org_test_suite import make_call, read_key, BASE

KEY = read_key()
admin = make_call(KEY)


def disc(op, **args):
    body = json.dumps({"op": op, "args": args}).encode()
    req = urllib.request.Request(BASE + "enjoy_discovery", data=body, method="POST", headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=170) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}
    except Exception as e:
        return 0, {"error": {"code": type(e).__name__, "message": "No answer (it may still have finished: check Runs in the Console)."}}


def say(*a):
    print(*a, flush=True)


def problem(res):
    status, body = res
    e = body.get("error", {}) if isinstance(body, dict) else {}
    return f"HTTP {status} {e.get('code', '')}: {e.get('message', '')} {json.dumps(e.get('problems', ''))}".strip()


def records(coll, **flt):
    s, b = admin(coll, "list", limit=200, **({"filters": flt} if flt else {}))
    return b["data"]["records"] if s == 200 and b.get("ok") else []


def status():
    s, b = disc("status")
    if s != 200:
        say("STATUS FAILED:", problem((s, b))); return None
    d = b["data"]
    say(f"mode: {d['mode']}   project: {d['project']}   ZIP table: {'loaded, %d ZIPs, %d states' % (d['zip_table']['zip_count'], len(d['zip_table']['states'])) if d['zip_table']['loaded'] else 'NOT LOADED'}")
    say("model keys on the server:", ", ".join(f"{k}={'yes' if v else 'NO'}" for k, v in d["keys"].items()) or "(none needed yet)")
    return d


def request(model_name, max_results, cap):
    m = [x for x in records("discovery_models") if x["model_name"] == model_name]
    if not m:
        say("No model named", model_name, "in the Console's Models list."); return None
    if not m[0]["is_active"]:
        say("That model is switched OFF in Settings > Models. Switch it on first."); return None
    co = [a for a in records("discovery_areas", kind="state") if a["state_code"] == "CO"]
    reg = [a for a in records("discovery_areas", kind="region") if a["name"] == "Boulder" and a["state_code"] == "CO"]
    if not co or not co[0]["is_active"]:
        say("Colorado is not switched on."); return None
    if not reg:
        say("There is no Boulder region yet. Run: python3 enjoy_router/seed_discovery.py regions   (after the ZIP table is built and deployed)"); return None
    return dict(finder_key="venue", model_id=m[0]["id"], area_ids=[reg[0]["id"]], type_keys=["coffee_shops"], max_results=max_results, spend_cap_cents=cap)


def show_run(rid):
    s, b = disc("get_run", id=rid)
    if s != 200:
        say(problem((s, b))); return None
    r = b["data"]
    say(f"run {rid}: {r['status']}{' (' + r['stop_reason'] + ')' if r.get('stop_reason') else ''}   found {r.get('found_count', 0)}, saved {r.get('created_count', 0)}, "
        f"duplicates {r.get('duplicate_count', 0)}, rejected {r.get('rejected_count', 0)}, need attention {r.get('attention_count', 0)}   "
        f"spent {r.get('actual_cost_cents', 0)} of {r['spend_cap_cents']} cents   tokens in {r.get('input_tokens', 0)} out {r.get('output_tokens', 0)} searches {r.get('search_count', 0)}")
    for st in r.get("steps", []):
        say(f"   call {st['step_number']}: {st['status']}{' ' + st['error_code'] if st.get('error_code') else ''}, {st.get('result_count', 0)} results, {st.get('cost_cents', 0)} cents")
    for x in r.get("rejections", []):
        say(f"   rejected: {x.get('name') or '(no name)'} - {x.get('reason')} {x.get('fields', '')}")
    return r


def run(model_name, max_results, cap, want_mode):
    d = status()
    if not d:
        return 1
    if d["mode"] != want_mode:
        say(f"The server mode is '{d['mode']}', this check needs '{want_mode}'. Set ICDT_DISCOVERY_MODE={want_mode} in enjoy_router/.env.launch-ai-workshop and redeploy enjoy_discovery."); return 1
    rq = request(model_name, max_results, cap)
    if not rq:
        return 1
    s, b = disc("quote", **rq)
    if s != 200:
        say("QUOTE FAILED:", problem((s, b))); return 1
    q = b["data"]
    say(f"quote: {q['steps_planned']} call(s) with {q['model_name']}, expected {q['estimated_cost_low_cents']} to {q['estimated_cost_high_cents']} cents, cap {cap}, prompt version {q['prompt_version']}")
    say("--- the exact prompt that will be sent (call 1) ---"); say(q["prompts"][0]["prompt_text"]); say("--- end of prompt ---")
    s, b = disc("plan", **rq)
    if s != 200:
        say("PLAN FAILED:", problem((s, b))); return 1
    rid = b["data"]["run_id"]; say("planned run", rid)
    for _ in range(45):
        t0 = time.time(); s, b = disc("step", run_id=rid)
        if s != 200:
            say("STEP FAILED:", problem((s, b))); break
        d2 = b["data"]; say(f"  step done in {time.time() - t0:.1f}s: {d2.get('step_status', d2.get('status'))}")
        if d2.get("done"):
            break
    r = show_run(rid)
    if r and r.get("created_venue_ids"):
        say("saved candidates (inactive) - open the Console, Venues, to look:")
        for vid in r["created_venue_ids"]:
            s, vb = admin("venues", "get", id=vid)
            v = vb.get("data", {}) if s == 200 else {}
            dd = v.get("discovery", {})
            say(f"   {v.get('name')}   marks: {json.dumps(dd.get('marks', {}))}   attention: {dd.get('attention_reasons', [])}")
        say(f"To take them back:  python3 enjoy_router/discovery_live_check.py withdraw {rid}")
    return 0


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "status":
        return 0 if status() else 1
    if cmd == "dry":
        return run("gemini-3.5-flash-lite", 3, 10, "dry_run")
    if cmd == "live":
        return run(argv[2] if len(argv) > 2 else "gemini-3.5-flash-lite", 3, int(argv[3]) if len(argv) > 3 else 10, "live")
    if cmd == "withdraw" and len(argv) > 2:
        s, b = disc("withdraw", run_id=argv[2])
        say(problem((s, b)) if s != 200 else f"withdrawn: removed {json.dumps(b['data'].get('removed'))}, kept (a person used them) {b['data'].get('kept')}"); return 0 if s == 200 else 1
    say(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
