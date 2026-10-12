#!/usr/bin/env python3
"""Live test of the journal, the cancel cascade and the attendance status search on the deployed functions. Run from enjoy_router/:  python3 run_journal_live_test.py
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

import uuid
stamp = str(int(time.time()))
REQ = str(uuid.uuid4())
cls = T("scheduled_classes", "create", data={"title": "Livetest journal class", "slug": "livejournal_" + stamp, "class_type": "private", "program_slug": "launch",
        "status": "identified", "is_public": False, "capacity_minimum": 1, "capacity_target": 2, "capacity_max": 2})
check("create a test class", cls[0] == 200, cls)
cid = data(cls).get("id")
r = T("attendances", "assign", data={"scheduled_class_id": cid, "role": "student", "request_id": REQ}, person={"given_name": "Livetest", "family_name": "Journal", "email": "livej@example.com"})
check("assign a student from a request", r[0] == 200 and data(r).get("status") == "assigned", r)
a1, p1 = data(r).get("id"), data(r).get("individual_id")
r = T("attendances", "assign", data={"scheduled_class_id": cid, "role": "primary_instructor", "order": 1}, person={"given_name": "Livetest", "family_name": "Teacher"})
a2, p2 = data(r).get("id"), data(r).get("individual_id")
check("assign an instructor", r[0] == 200, r)
r = T("attendances", "update", id=a1, changes={"status": "confirmed"}); check("status change to confirmed", r[0] == 200, r)
r = T("attendances", "list", filters={"status": "confirmed", "scheduled_class_id": cid}); check("status search inside a class", r[0] == 200 and data(r).get("count") == 1, r)
r = T("attendances", "list", filters={"status": "confirmed"}); check("status search alone", r[0] == 200 and data(r).get("count") >= 1, r)
r = T("attendances", "list", filters={}); check("attendance list with no filter", r[0] == 200, r)
check("old status word is refused", T("attendances", "update", id=a1, changes={"status": "enrolled"})[0] == 400)
r = T("journal_events", "list", filters={"request_id": REQ}, order="created_at")
types = [e["event_type"] for e in data(r).get("records", [])]
check("journal for the request shows placed then status_changed", r[0] == 200 and types == ["placed", "status_changed"], types)
for op, args in (("create", {"data": {"event_type": "placed"}}), ("update", {"id": a1, "changes": {"note": "x"}}), ("soft_delete", {"id": a1})):
    check("journal refuses " + op, T("journal_events", op, **args)[0] == 400)
r = T("scheduled_classes", "update", id=cid, changes={"status": "cancelled", "cancelled_reason": "Livetest"}); check("cancel the class", r[0] == 200, r)
r = T("attendances", "list", filters={"scheduled_class_id": cid}); st = sorted(x["status"] for x in data(r).get("records", []))
check("everyone in it is cancelled", st == ["cancelled", "cancelled"], st)
r = T("journal_events", "list", filters={"request_id": REQ}, order="created_at", expand=True)
types = [e["event_type"] for e in data(r).get("records", [])]
check("journal shows class_cancelled then request_unassigned", types[-2:] == ["class_cancelled", "request_unassigned"], types)
r = A("journal_events", "list", filters={"scheduled_class_id": cid}); check("the Console door can read the journal (it reads the real collection, so test lines are not in it)", r[0] == 200 and "records" in data(r), r)
check("remove class", T("scheduled_classes", "soft_delete", id=cid)[0] == 200)
for rid in (a1, a2): T("attendances", "soft_delete", id=rid)
for pid in (p1, p2):
    for rec in data(T("student_rosters", "list", filters={"individual_id": pid})).get("records", []): T("student_rosters", "soft_delete", id=rec["id"])
    for rec in data(T("instructor_rosters", "list", filters={"individual_id": pid})).get("records", []): T("instructor_rosters", "soft_delete", id=rec["id"])
    check("clean up person", T("individuals", "soft_delete", id=pid)[0] == 200)
# journal lines are append-only and cannot be removed; they sit in the test_ collection and are harmless
print(f"\n{total - len(fails)}/{total} checks passed")
print("OK" if not fails else "FAILED: " + ", ".join(fails))
sys.exit(1 if fails else 0)
