#!/usr/bin/env python3
"""Live test of the instructor and student rosters on the deployed functions. Run from enjoy_router/:  python3 run_rosters_live_test.py
Writes ONLY through the test door (enjoy_crud_test, collections prefixed test_) and cleans up after itself. The Console door
(enjoy_admin) is used for READS and refusals only. The key is read from .env.launch-ai-workshop and never printed."""
import json, pathlib, sys, urllib.request, urllib.error

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
data = lambda r: (r[1] or {}).get("data") or {}
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else "  " + str(detail)[:300]))

made_people = []
for coll, name in (("instructor_rosters", "instructor"), ("student_rosters", "student")):
    r = T(coll, "create_with_person", data={}, person={"given_name": "Livetest", "family_name": name.title(), "email": "Live@Example.com"})
    check(f"{name}: create_with_person makes the person and the entry", r[0] == 200 and data(r).get("created_person") is True, r)
    d = data(r); rid = d.get("id"); pid = d.get("individual_id")
    if pid: made_people.append(pid)
    check(f"{name}: person read in with lowercased email", d.get("person", {}).get("email") == "live@example.com", d)
    r = T(coll, "create", data={"individual_id": pid}); check(f"{name}: second entry for the person is refused", r[0] == 400 and "duplicate" in json.dumps(r[1]), r)
    r = T(coll, "list", filters={"status": "active"}, expand=True, order="name"); check(f"{name}: list by status with expand", r[0] == 200 and data(r).get("count", 0) >= 1, r)
    r = T(coll, "list", filters={"individual_id": pid}); check(f"{name}: list by person", r[0] == 200 and data(r).get("count") == 1, r)
    r = T(coll, "update_with_person", id=rid, changes={"notes": "live test"}, person={"phone": "303-555-0142"})
    check(f"{name}: update_with_person", r[0] == 200 and data(r).get("notes") == "live test" and data(r).get("person", {}).get("phone"), r)
    check(f"{name}: the Console door can read it", A(coll, "list", expand=True)[0] == 200)
    check(f"{name}: remove", T(coll, "soft_delete", id=rid)[0] == 200)
    r = T(coll, "create", data={"individual_id": pid}); check(f"{name}: added again after removal", r[0] == 200, r)
    if r[0] == 200: T(coll, "soft_delete", id=data(r)["id"])
for pid in made_people:
    check("clean up person", T("individuals", "soft_delete", id=pid)[0] == 200)
print(f"\n{total - len(fails)}/{total} checks passed")
print("OK" if not fails else "FAILED: " + ", ".join(fails))
sys.exit(1 if fails else 0)
