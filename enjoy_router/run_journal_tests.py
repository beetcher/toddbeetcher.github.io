#!/usr/bin/env python3
"""In-memory tests for the journal (crud/journal_events_crud.py) and what writes it: placing, status changes, removal, a class cancelled or
deleted (everyone's open attendance cancelled, requests back to unassigned), the attendance status search, merge, erase, and the endpoint.
Run from enjoy_router/:  python3 run_journal_tests.py   (-v lists every check). Nothing touches Firebase."""
import json, pathlib, sys
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import attendances_service as AT  # noqa: E402
from crud import classes_service as CS  # noqa: E402
from crud import individuals_service as IS  # noqa: E402
from crud import journal_events_crud as JR  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud_endpoint import handle_admin, handle_crud_test, make_failure_limiter  # noqa: E402

START = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)
KEY = "k" * 16 + "Z" * 16 + "-test-key-not-real"
A, B = "user:admin", "user:helper"
fails, total, clock = [], 0, [0]
def tick():
    clock[0] += 5
    return START + timedelta(seconds=clock[0])
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    if not ok or "-v" in sys.argv: print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")

s = MemoryDocStore("test_")
BASE = {"title": "Private", "slug": "p", "class_type": "private", "program_slug": "launch", "status": "identified", "is_public": False,
        "capacity_minimum": 1, "capacity_target": 2, "capacity_max": 2}
def klass(slug, **kw):
    r = CS.create(s, {**BASE, "slug": slug, "title": slug, **kw}, A, now=tick()); assert r.ok, r.problems; return r.data
def person(g): 
    r = IS.create(s, {"given_name": g, "family_name": "X"}, A, now=tick()); assert r.ok, r.problems; return r.data
def events(**f):
    r = JR.list(s, f, order="created_at"); assert r.ok, r.problems; return r.data["records"]
def types(**f): return [e["event_type"] for e in events(**f)]
REQ, REQ2 = "11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"
c1, c2, c3 = klass("c1"), klass("c2"), klass("c3")
ann, bob, ina = person("Ann"), person("Bob"), person("Ina")

# ---- placing writes a journal line
r = AT.assign(s, {"scheduled_class_id": c1["id"], "role": "student", "individual_id": ann["id"], "request_id": REQ}, A, now=tick())
check("assign works and starts assigned", r.ok and r.data["status"] == "assigned", r.problems if not r.ok else "")
a1 = r.data
ev = events(request_id=REQ)
check("a placed line is written", [e["event_type"] for e in ev] == ["placed"] and ev[0]["to_status"] == "assigned" and ev[0]["created_by"] == A and ev[0]["attendance_id"] == a1["id"], ev)
check("the line carries class, person and role", ev[0]["scheduled_class_id"] == c1["id"] and ev[0]["individual_id"] == ann["id"] and ev[0]["role"] == "student")
check("same lines found by class, person and attendance", len(events(scheduled_class_id=c1["id"])) == 1 and len(events(individual_id=ann["id"])) == 1 and len(events(attendance_id=a1["id"])) == 1)

# ---- status change
r = AT.update(s, a1["id"], {"status": "confirmed"}, B, now=tick()); check("status to confirmed", r.ok, r.problems if not r.ok else "")
ev = events(attendance_id=a1["id"])
check("status_changed line has from, to and who", ev[-1]["event_type"] == "status_changed" and ev[-1]["from_status"] == "assigned" and ev[-1]["to_status"] == "confirmed" and ev[-1]["created_by"] == B, ev)
n = len(events(attendance_id=a1["id"]))
AT.update(s, a1["id"], {"notes": "hi"}, A, now=tick()); check("no line when the status does not change", len(events(attendance_id=a1["id"])) == n)
check("old status word enrolled is refused", AT.update(s, a1["id"], {"status": "enrolled"}, A, now=tick()).code == "validation_failed")
check("a stale write writes no journal line", (lambda r: r.code == "conflict" and len(events(attendance_id=a1["id"])) == n)(AT.update(s, a1["id"], {"status": "attended"}, A, expected_updated_at="2020-01-01T00:00:00Z", now=tick())))

# ---- leaving the placement returns the request to unassigned
r = AT.update(s, a1["id"], {"status": "withdrawn"}, A, now=tick())
check("withdrawn writes status_changed then request_unassigned", types(request_id=REQ)[-2:] == ["status_changed", "request_unassigned"], types(request_id=REQ))
AT.update(s, a1["id"], {"status": "assigned"}, A, now=tick())
check("coming back writes no unassigned line", types(request_id=REQ)[-1] == "status_changed")

# ---- two placements: one leaving is not enough
r2 = AT.assign(s, {"scheduled_class_id": c2["id"], "role": "student", "individual_id": bob["id"], "request_id": REQ}, A, now=tick()); a2 = r2.data
AT.update(s, a1["id"], {"status": "declined"}, A, now=tick())
check("another active placement keeps the request assigned (no unassigned line)", "request_unassigned" not in types(request_id=REQ)[-2:], types(request_id=REQ))

# ---- removal as a mistake
r3 = AT.assign(s, {"scheduled_class_id": c3["id"], "role": "student", "individual_id": ann["id"], "request_id": REQ2}, A, now=tick()); a3 = r3.data
AT.soft_delete(s, a3["id"], B, now=tick())
check("removal writes removed then request_unassigned", types(request_id=REQ2)[-2:] == ["removed", "request_unassigned"], types(request_id=REQ2))

# ---- a class cancelled cascades
cl = klass("big", capacity_max=5)
x1 = AT.assign(s, {"scheduled_class_id": cl["id"], "role": "student", "individual_id": ann["id"], "request_id": REQ2}, A, now=tick()).data
x2 = AT.assign(s, {"scheduled_class_id": cl["id"], "role": "primary_instructor", "individual_id": ina["id"]}, A, now=tick()).data
x3 = AT.assign(s, {"scheduled_class_id": cl["id"], "role": "student", "individual_id": bob["id"], "status": "attended"}, A, now=tick()).data
x4 = AT.assign(s, {"scheduled_class_id": c1["id"], "role": "student", "individual_id": ina["id"], "status": "waitlisted"}, A, now=tick()).data
r = CS.update(s, cl["id"], {"status": "cancelled", "cancelled_reason": "Instructor sick"}, B, now=tick())
check("cancelling the class works", r.ok, r.problems if not r.ok else "")
st = lambda a: AT.get(s, a["id"]).data["status"]
check("open attendance is cancelled (student and instructor)", st(x1) == "cancelled" and st(x2) == "cancelled")
check("an outcome already recorded is left alone", st(x3) == "attended")
check("another class is untouched", st(x4) == "waitlisted")
ev = events(scheduled_class_id=cl["id"])
check("one class_cancelled line per cancelled person, by the operator", sorted(e["event_type"] for e in ev if e["event_type"] == "class_cancelled") == ["class_cancelled"] * 2 and all(e["created_by"] == B for e in ev if e["event_type"] == "class_cancelled"), ev)
check("the request is returned to unassigned", types(request_id=REQ2)[-1] == "request_unassigned")
check("history shows cancelled by the operator", AT.get(s, x1["id"]).data["status_history"][-1]["status"] == "cancelled" and AT.get(s, x1["id"]).data["status_history"][-1]["by"] == B)
n = len(events(scheduled_class_id=cl["id"]))
CS.update(s, cl["id"], {"title": "Big again"}, A, now=tick()); check("later edits do not cascade again", len(events(scheduled_class_id=cl["id"])) == n)

# ---- cascade is all or nothing
cl2 = klass("fails")
y = AT.assign(s, {"scheduled_class_id": cl2["id"], "role": "student", "individual_id": ann["id"]}, A, now=tick()).data
r = CS.update(s, cl2["id"], {"status": "cancelled", "cancelled_reason": "x" * 1000}, A, now=tick())
check("a refused class change cancels nobody", not r.ok and st(y) == "assigned" and not [e for e in events(scheduled_class_id=cl2["id"]) if e["event_type"] == "class_cancelled"])

# ---- a class deleted cascades too
cl3 = klass("gone")
z = AT.assign(s, {"scheduled_class_id": cl3["id"], "role": "student", "individual_id": bob["id"], "request_id": REQ}, A, now=tick()).data
r = CS.soft_delete(s, cl3["id"], A, now=tick())
check("deleting the class works and cancels the person", r.ok and st(z) == "cancelled")
check("class_removed line written", "class_removed" in types(attendance_id=z["id"]))

# ---- the status search
check("status search alone", all(d["status"] == "cancelled" for d in AT.list(s, {"status": "cancelled"}).data["records"]) and AT.list(s, {"status": "cancelled"}).data["count"] >= 3)
check("status within a class", AT.list(s, {"scheduled_class_id": cl["id"], "status": "attended"}).data["count"] == 1)
check("two index filters still refused", AT.list(s, {"scheduled_class_id": cl["id"], "request_id": REQ}).code == "validation_failed")
check("a bad status is refused", AT.list(s, {"status": "enrolled"}).code == "validation_failed")

# ---- the journal cannot be written through the endpoints
limiter = make_failure_limiter()
def call(door, st_, body):
    return door("POST", "Bearer " + KEY, json.dumps(body).encode(), KEY, "v", st_, limiter, tick()) if door is handle_admin else \
           door("POST", "Bearer " + KEY, json.dumps(body).encode(), KEY, "v", st_, limiter, tick())
for door, store in ((handle_crud_test, MemoryDocStore("test_")), (handle_admin, MemoryDocStore(""))):
    cls = call(door, store, {"collection": "scheduled_classes", "op": "create", "args": {"data": {**BASE, "slug": "e1"}}}); cid = cls.body["data"]["id"]
    r = call(door, store, {"collection": "attendances", "op": "assign", "args": {"data": {"scheduled_class_id": cid, "role": "student", "request_id": REQ}, "person": {"given_name": "Pat"}}})
    check("endpoint assign", r.status == 200, r.body)
    r = call(door, store, {"collection": "journal_events", "op": "list", "args": {"filters": {"request_id": REQ}, "expand": True}})
    check("endpoint journal list with names and class", r.status == 200 and r.body["data"]["count"] == 1 and r.body["data"]["records"][0]["person"]["display_name"] and r.body["data"]["records"][0]["class"]["title"], r.body)
    jid = r.body["data"]["records"][0]["id"]
    check("endpoint journal get", call(door, store, {"collection": "journal_events", "op": "get", "args": {"id": jid}}).status == 200)
    for op, args in (("create", {"data": {"event_type": "placed"}}), ("update", {"id": jid, "changes": {"note": "x"}}), ("soft_delete", {"id": jid})):
        r = call(door, store, {"collection": "journal_events", "op": op, "args": args})
        check("endpoint journal %s refused" % op, r.status == 400 and r.body["error"]["problems"] == [{"field": "op", "issue": "not_supported"}], r.body)
    r = call(door, store, {"collection": "scheduled_classes", "op": "update", "args": {"id": cid, "changes": {"status": "cancelled", "cancelled_reason": "Rain"}}})
    check("endpoint class cancel", r.status == 200, r.body)
    r = call(door, store, {"collection": "journal_events", "op": "list", "args": {"filters": {"request_id": REQ}}})
    check("endpoint: journal shows placed, class_cancelled, request_unassigned", [e["event_type"] for e in r.body["data"]["records"]][::-1] == ["placed", "class_cancelled", "request_unassigned"], r.body)

# ---- merge and erase
import crud.individual_merges_crud as M
dup = person("Annie")
d1 = AT.assign(s, {"scheduled_class_id": c2["id"], "role": "student", "individual_id": dup["id"]}, A, now=tick()).data
m = M.merge(s, ann["id"], dup["id"], "same person", A, None, now=tick())
check("merge works", m.ok, m.problems if not m.ok else "")
check("merge repoints the journal to the survivor", all(e["individual_id"] == ann["id"] for e in events(attendance_id=d1["id"])) and events(attendance_id=d1["id"]))
er = IS.erase(s, bob["id"], A, now=tick())
check("erase works", er.ok, er.problems if not er.ok else "")
left = [e for e in events(attendance_id=a2["id"])]
check("erase leaves only anonymous tombstones of the journal", not left, left)

allr = AT.list(store, {}, limit=200)
check("attendance lists with no filter at all", allr.ok and allr.data["count"] >= 1, allr.problems if not allr.ok else "")

print(f"\n{total - len(fails)}/{total} checks passed")
if fails: print("FAILED:", *fails, sep="\n  "); sys.exit(1)
print("OK")
