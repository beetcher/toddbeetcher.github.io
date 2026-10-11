#!/usr/bin/env python3
"""Live test of the individuals backend on the deployed functions. Run from enjoy_router/:  python3 run_individuals_live_test.py
Writes ONLY through the test door (enjoy_crud_test, collections prefixed test_) and cleans up after itself. The Console door
(enjoy_admin) is used for READS and for refusals only. The key is read from .env.launch-ai-workshop and never printed."""
import json, pathlib, sys, time, urllib.request, urllib.error

HERE = pathlib.Path(__file__).resolve().parent
BASE = "https://us-central1-launch-ai-workshop.cloudfunctions.net/"
KEY = next((l.split("=", 1)[1].strip().strip('"\'') for l in (HERE / ".env.launch-ai-workshop").read_text().splitlines() if l.startswith("ICDT_ADMIN_KEY=")), "")
if len(KEY) < 32:
    sys.exit("no admin key found")
fails, total = [], 0

def call(fn, coll, op, **args):
    req = urllib.request.Request(BASE + fn, data=json.dumps({"collection": coll, "op": op, "args": args}).encode(),
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read() or b"{}")
        except ValueError: return e.code, {}
    except Exception as e:
        return 0, {"error": type(e).__name__}

T = lambda coll, op, **a: call("enjoy_crud_test", coll, op, **a)
A = lambda coll, op, **a: call("enjoy_admin", coll, op, **a)

def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else "  " + str(detail)[:300]))

data = lambda r: (r[1] or {}).get("data") or {}
made = []
def person(**kw):
    r = T("individuals", "create", data=kw); check("create " + kw["given_name"], r[0] == 200, r)
    if r[0] == 200: made.append(data(r)["id"])
    return data(r)

a = person(given_name="Livetest", family_name="Ann", birth_date="1961-04-17")
b = person(given_name="Livetest", family_name="Annie")
check("display_name derived", a.get("display_name") == "Livetest Ann")
check("get", T("individuals", "get", id=a["id"])[0] == 200)
time.sleep(1.2)  # updated_at has one-second resolution: two edits inside the same second cannot be told apart
r = T("individuals", "update", id=a["id"], changes={"notes": "live test"}, expected_updated_at=a["updated_at"]); check("update with matching updated_at", r[0] == 200, r)
time.sleep(1.2)
check("stale update is 409", T("individuals", "update", id=a["id"], changes={"notes": "x"}, expected_updated_at=a["updated_at"])[0] == 409)
for f in ({"status": "active"}, {"life_status": "alive"}, {"is_minor": False}):
    r = T("individuals", "list", filters=f); check("list filtered by " + list(f)[0] + " (needs its index)", r[0] == 200, r)
check("list unfiltered", T("individuals", "list")[0] == 200)

r = T("individuals", "merge", survivor_id=a["id"], duplicate_id=b["id"], reason="live test"); check("merge", r[0] == 200, r)
ev = data(r).get("id")
if ev:
    check("merge event readable", T("merge_events", "get", id=ev)[0] == 200)
    check("merge events list", T("merge_events", "list")[0] == 200)
    check("reading the duplicate now returns the survivor", data(T("individuals", "get", id=b["id"])).get("id") == a["id"])
    r = T("individuals", "unmerge", id=ev); check("unmerge", r[0] == 200, r)
    check("duplicate active again", data(T("individuals", "get", id=b["id"])).get("status") == "active")
    check("second unmerge refused (409)", T("individuals", "unmerge", id=ev)[0] == 409)

r = T("individual_restricted_details", "create", data={"individual_id": a["id"], "purpose": "safety", "consent_ref": "live-test", "blood_type_abo": "O"}); check("restricted create", r[0] == 200, r)
rid = data(r).get("id")
check("restricted get_for_individual", T("individual_restricted_details", "get_for_individual", individual_id=a["id"])[0] == 200)
check("delete refused while restricted record is live (409)", T("individuals", "soft_delete", id=a["id"])[0] == 409)
if rid: check("restricted soft delete", T("individual_restricted_details", "soft_delete", id=rid)[0] == 200)
c = person(given_name="Livetest", family_name="Erase")
r = T("individuals", "erase", id=c["id"]); check("erase on the test door", r[0] == 200, r)
for i in (a["id"], b["id"]):
    check("soft delete", T("individuals", "soft_delete", id=i)[0] == 200)

# the Console door: reads and refusals only
check("Console list individuals (real collection)", A("individuals", "list")[0] == 200)
check("Console list by status (real collection, needs its index)", A("individuals", "list", filters={"status": "active"})[0] == 200)
check("Console list merge events", A("merge_events", "list")[0] == 200)
check("Console cannot erase", A("individuals", "erase", id=a["id"])[0] == 400)
check("Console cannot reach restricted details", A("individual_restricted_details", "list")[0] == 400)
check("Console cannot create merge events", A("merge_events", "create", data={"survivor_id": a["id"], "duplicate_id": b["id"], "reason": "x"})[0] == 400)
try:
    urllib.request.urlopen(urllib.request.Request(BASE + "enjoy_admin", data=b"{}", method="POST"), timeout=30); code = 200
except urllib.error.HTTPError as e:
    code = e.code
check("a request with no key is refused (401)", code == 401, code)
print(f"\n{total - len(fails)}/{total} checks passed")
print("OK" if not fails else "FAILED: " + ", ".join(fails))
sys.exit(1 if fails else 0)
