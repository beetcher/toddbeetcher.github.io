#!/usr/bin/env python3
"""Live test of attendance on the deployed functions. Run from enjoy_router/:  python3 run_attendances_live_test.py
Writes ONLY through the test door (enjoy_crud_test, collections prefixed test_) and cleans up after itself. The Console door
(enjoy_admin) is used for READS only. The key is read from .env.launch-ai-workshop and never printed."""
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
data = lambda r: (r[1] or {}).get("data") or {}
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else "  " + str(detail)[:300]))

stamp = str(int(time.time()))
cls = T("scheduled_classes", "create", data={"title": "Livetest class", "slug": "livetest_" + stamp, "class_type": "private", "program_slug": "launch",
        "status": "identified", "is_public": False, "capacity_minimum": 1, "capacity_target": 1, "capacity_max": 1})
check("create a test class", cls[0] == 200, cls)
cid = data(cls).get("id")
r = T("attendances", "assign", data={"scheduled_class_id": cid, "role": "student"}, person={"given_name": "Livetest", "family_name": "Student", "email": "Live@Example.com"})
check("assign a new person: person, roster entry and record together", r[0] == 200 and data(r).get("created_person") and data(r).get("created_roster_entry") and data(r).get("status") == "enrolled", r)
a1, p1 = data(r).get("id"), data(r).get("individual_id")
r = T("attendances", "assign", data={"scheduled_class_id": cid, "role": "student", "individual_id": p1}); check("same person again is refused", r[0] == 400 and "duplicate" in json.dumps(r[1]), r)
r = T("attendances", "assign", data={"scheduled_class_id": cid, "role": "student"}, person={"given_name": "Livetest", "family_name": "Second"})
check("a full class waitlists the next student (capacity 1)", r[0] == 200 and data(r).get("status") == "waitlisted", r)
a2, p2 = data(r).get("id"), data(r).get("individual_id")
r = T("attendances", "assign", data={"scheduled_class_id": cid, "role": "primary_instructor", "order": 1, "individual_id": p1})
check("the same person in the same class is refused even in another role", r[0] == 400, r)
r = T("attendances", "update", id=a1, changes={"status": "attended"}); check("status update", r[0] == 200, r)
r = T("attendances", "get", id=a1, expand=True); check("get with expand: person, class and two history entries", r[0] == 200 and len(data(r).get("status_history", [])) == 2 and data(r).get("class", {}).get("title") == "Livetest class" and data(r).get("person", {}).get("email") == "live@example.com", r)
r = T("attendances", "list", filters={"scheduled_class_id": cid}, expand=True); check("class list by class", r[0] == 200 and data(r).get("count") == 2, r)
r = T("attendances", "list", filters={"individual_id": p1}); check("list by person", r[0] == 200 and data(r).get("count") == 1, r)
check("the Console door can read", A("attendances", "list", filters={"scheduled_class_id": cid})[0] == 200)
for rid in (a1, a2): check("remove record", T("attendances", "soft_delete", id=rid)[0] == 200)
for coll in ("student_rosters",):
    for pid in (p1, p2):
        for rec in data(T(coll, "list", filters={"individual_id": pid})).get("records", []): T(coll, "soft_delete", id=rec["id"])
for pid in (p1, p2): check("clean up person", T("individuals", "soft_delete", id=pid)[0] == 200)
check("clean up class", T("scheduled_classes", "soft_delete", id=cid)[0] == 200)
print(f"\n{total - len(fails)}/{total} checks passed")
print("OK" if not fails else "FAILED: " + ", ".join(fails))
sys.exit(1 if fails else 0)
