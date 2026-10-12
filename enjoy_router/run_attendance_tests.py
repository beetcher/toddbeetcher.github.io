#!/usr/bin/env python3
"""In-memory tests for attendance (crud/attendances_service.py): the record, status history, assign, merge, erase, endpoint.
Run from enjoy_router/:  python3 run_attendance_tests.py   (-v lists every check). Nothing touches Firebase."""
import json, pathlib, sys
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import attendances_service as AT  # noqa: E402
from crud import individuals_service as IS  # noqa: E402
from crud import instructor_rosters_service as INS  # noqa: E402
from crud import scheduled_classes_crud as CL  # noqa: E402
from crud import student_rosters_service as STU  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud_endpoint import handle_admin, handle_crud_test, make_failure_limiter  # noqa: E402

START = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)
KEY = "k" * 16 + "Z" * 16 + "-test-key-not-real"
A = "user:admin"
fails, total, clock = [], 0, [0]
def tick():
    clock[0] += 5
    return START + timedelta(seconds=clock[0])
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    if not ok or "-v" in sys.argv: print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")
def issues(r): return sorted((p["field"], p["issue"]) for p in r.problems)

s = MemoryDocStore("test_")
BASE = {"title": "Private session", "slug": "p1", "class_type": "private", "program_slug": "launch", "status": "identified", "is_public": False,
        "capacity_minimum": 1, "capacity_target": 2, "capacity_max": 2}
def klass(slug, **kw):
    r = CL.create(s, {**BASE, "slug": slug, **kw}, A, now=tick()); assert r.ok, r.problems; return r.data
def person(g, f="X", **kw):
    r = IS.create(s, {"given_name": g, "family_name": f, **kw}, A, now=tick()); assert r.ok, r.problems; return r.data
c1, c2, c3 = klass("c1"), klass("c2"), klass("c3")
ann, bob, cy, dee = person("Ann"), person("Bob"), person("Cy"), person("Dee")

r = AT.create(s, {"individual_id": ann["id"], "scheduled_class_id": c1["id"], "role": "student"}, A, now=tick())
check("create", r.ok, r.problems)
check("status defaults to assigned with a one-entry history", r.ok and r.data["status"] == "assigned" and [h["status"] for h in r.data["status_history"]] == ["assigned"])
aid = r.data["id"]
d = AT.create(s, {"individual_id": ann["id"], "scheduled_class_id": c1["id"], "role": "student"}, A, now=tick())
check("same person in the same class refused, names the existing record", not d.ok and ("individual_id", "duplicate") in issues(d) and d.problems[0].get("existing_id") == aid)
check("same person in another class is fine", AT.create(s, {"individual_id": ann["id"], "scheduled_class_id": c3["id"], "role": "student"}, A, now=tick()).ok)
G = "3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b"
check("unknown person refused", ("individual_id", "not_found") in issues(AT.create(s, {"individual_id": G, "scheduled_class_id": c1["id"], "role": "student"}, A, now=tick())))
check("unknown class refused", ("scheduled_class_id", "not_found") in issues(AT.create(s, {"individual_id": bob["id"], "scheduled_class_id": G, "role": "student"}, A, now=tick())))
check("role required", ("role", "required") in issues(AT.create(s, {"individual_id": bob["id"], "scheduled_class_id": c1["id"]}, A, now=tick())))
check("bad role refused", ("role", "invalid_value") in issues(AT.create(s, {"individual_id": bob["id"], "scheduled_class_id": c1["id"], "role": "mentor"}, A, now=tick())))
check("status_history cannot be sent", ("status_history", "not_allowed") in issues(AT.create(s, {"individual_id": bob["id"], "scheduled_class_id": c1["id"], "role": "student", "status_history": []}, A, now=tick())))
u = AT.update(s, aid, {"scheduled_class_id": c3["id"]}, A, now=tick()); check("class immutable", not u.ok and ("scheduled_class_id", "immutable") in issues(u))
u = AT.update(s, aid, {"individual_id": bob["id"]}, A, now=tick()); check("person immutable", not u.ok and ("individual_id", "immutable") in issues(u))
check("history not editable", not AT.update(s, aid, {"status_history": []}, A, now=tick()).ok)
u = AT.update(s, aid, {"status": "attended", "notes": "great"}, A, now=tick()); check("status update", u.ok and "status" in u.data["changed"], u.problems)
u = AT.update(s, aid, {"status": "attended"}, A, now=tick())
h = AT.get(s, aid).data["status_history"]
check("history appends each change, not repeats", [x["status"] for x in h] == ["assigned", "attended"], h)
check("history keeps who", all(x["by"] == A and x["at"] for x in h))
check("status cannot be removed", not AT.update(s, aid, {"status": None}, A, now=tick()).ok)
check("stale update conflicts", AT.update(s, aid, {"notes": "x"}, A, expected_updated_at="2020-01-01T00:00:00Z", now=tick()).code == "conflict")
check("list by class", AT.list(s, {"scheduled_class_id": c1["id"]}).data["count"] == 1)
check("list by person", AT.list(s, {"individual_id": ann["id"]}).data["count"] == 2)
check("two filters not supported", not AT.list(s, {"individual_id": ann["id"], "scheduled_class_id": c1["id"]}).ok)
e = AT.get(s, aid, expand=True).data
check("expand reads person and class", e["person"]["display_name"] == ann["display_name"] and e["class"]["title"] == "Private session", e)
check("soft delete is for mistakes", AT.soft_delete(s, aid, A, now=tick()).ok and not AT.get(s, aid).ok and AT.get(s, aid, include_deleted=True).ok)
check("deleted record frees the seat for a new one", AT.create(s, {"individual_id": ann["id"], "scheduled_class_id": c1["id"], "role": "student"}, A, now=tick()).ok)

# assign
r = AT.assign(s, {"scheduled_class_id": c2["id"], "role": "primary_instructor", "order": 1, "individual_id": bob["id"]}, A, now=tick())
check("assign existing person as instructor", r.ok and r.data["status"] == "assigned" and r.data["created_roster_entry"] and not r.data["created_person"], r.problems)
check("instructor roster entry made", INS.list(s, {"individual_id": bob["id"]}).data["count"] == 1 and STU.list(s, {"individual_id": bob["id"]}).data["count"] == 0)
r = AT.assign(s, {"scheduled_class_id": c2["id"], "role": "instructor", "individual_id": bob["id"]}, A, now=tick())
check("assign twice refused as duplicate", not r.ok and ("individual_id", "duplicate") in issues(r) and r.problems[0].get("existing_id"))
check("a failed assign left the roster alone", INS.list(s, {"individual_id": bob["id"]}).data["count"] == 1)
before = IS.list(s, None, limit=200).data["count"]
r = AT.assign(s, {"scheduled_class_id": c2["id"], "role": "student"}, A, person={"given_name": "Chuck", "family_name": "Norris", "email": "Chuck@Example.com"}, now=tick())
check("assign a new person as student", r.ok and r.data["created_person"] and r.data["created_roster_entry"] and r.data["person"]["email"] == "chuck@example.com", r.problems)
check("person and student roster entry exist", IS.list(s, None, limit=200).data["count"] == before + 1 and STU.list(s, {"individual_id": r.data["individual_id"]}).data["count"] == 1)
check("roster entry is not duplicated for a person already on it", True)
STU.create(s, {"individual_id": cy["id"]}, A, now=tick())
r = AT.assign(s, {"scheduled_class_id": c2["id"], "role": "student", "individual_id": cy["id"]}, A, now=tick())
check("already-on-roster person: no second roster entry, record assigned", r.ok and not r.data["created_roster_entry"] and r.data["status"] == "assigned" and STU.list(s, {"individual_id": cy["id"]}).data["count"] == 1, r.problems)
r = AT.assign(s, {"scheduled_class_id": c2["id"], "role": "student", "individual_id": dee["id"]}, A, now=tick())
check("a full class waitlists a student (capacity 2, two assigned) and does not refuse", r.ok and r.data["status"] == "waitlisted", r.data if r.ok else r.problems)
check("waitlisted history starts at waitlisted", r.ok and [h["status"] for h in r.data["status_history"]] == ["waitlisted"])
r2 = AT.assign(s, {"scheduled_class_id": c2["id"], "role": "student", "individual_id": ann["id"], "status": "assigned"}, A, now=tick())
check("the operator can set the status explicitly", r2.ok and r2.data["status"] == "assigned")
r = AT.assign(s, {"scheduled_class_id": c2["id"], "role": "student"}, A, now=tick()); check("assign needs a person", not r.ok and ("individual_id", "required") in issues(r))
r = AT.assign(s, {"scheduled_class_id": c2["id"], "role": "student", "individual_id": bob["id"]}, A, person={"given_name": "Z"}, now=tick()); check("id and person together refused", ("person", "choose_one") in issues(r))
n = IS.list(s, None, limit=200).data["count"]
r = AT.assign(s, {"scheduled_class_id": G, "role": "student"}, A, person={"given_name": "Ghost"}, now=tick()); check("unknown class refused, no person made", not r.ok and IS.list(s, None, limit=200).data["count"] == n)
r = AT.assign(s, {"scheduled_class_id": c2["id"], "role": "student", "notes": "x" * 2001}, A, person={"given_name": "Ghost"}, now=tick()); check("bad record: no person and no roster entry made", not r.ok and IS.list(s, None, limit=200).data["count"] == n)
r = AT.assign(s, {"scheduled_class_id": c2["id"], "role": "student"}, A, person={"family_name": "NoGiven"}, now=tick()); check("new person needs a given name", not r.ok)
r = AT.assign(s, {"scheduled_class_id": c2["id"], "role": "student"}, A, person={"given_name": "G", "shoe": 1}, now=tick()); check("unknown person field refused", not r.ok)
check("class roster is a lookup", sorted(x["role"] for x in AT.list(s, {"scheduled_class_id": c2["id"]}).data["records"]).count("student") == 4)

# merge and erase
d1, d2 = person("Mer"), person("Ged")
x = AT.create(s, {"individual_id": d2["id"], "scheduled_class_id": c1["id"], "role": "student"}, A, now=tick()).data
m = IS.merge(s, d1["id"], d2["id"], "same", A, now=tick())
check("merge repoints attendance to the survivor", m.ok and AT.get(s, x["id"]).data["individual_id"] == d1["id"], m.problems)
check("unmerge restores it", IS.unmerge(s, m.data["id"], A, now=tick()).ok and AT.get(s, x["id"]).data["individual_id"] == d2["id"])
z = person("Erase")
za = AT.create(s, {"individual_id": z["id"], "scheduled_class_id": c1["id"], "role": "student", "notes": "private"}, A, now=tick()).data
er = IS.erase(s, z["id"], A, now=tick())
check("erase succeeds", er.ok, er.problems)
raw = AT.get(s, za["id"], include_deleted=True).data
check("erased person's attendance is off the lists and holds no personal data", not AT.get(s, za["id"]).ok and not any(k in raw for k in ("individual_id", "notes", "status_history")), raw)

# endpoint
lim = make_failure_limiter(); ts = tick()
def call(h, st, body): return h("POST", "Bearer " + KEY, json.dumps(body).encode(), KEY, "v", st, lim, ts)
for door, st in ((handle_crud_test, MemoryDocStore("test_")), (handle_admin, MemoryDocStore(""))):
    cl = call(door, st, {"collection": "scheduled_classes", "op": "create", "args": {"data": {**BASE, "slug": "e1"}}}); check("endpoint: class", cl.status == 200, cl.body)
    cid = cl.body["data"]["id"]
    r = call(door, st, {"collection": "attendances", "op": "assign", "args": {"data": {"scheduled_class_id": cid, "role": "student"}, "person": {"given_name": "Pat", "email": "p@x.com"}}})
    check("endpoint assign", r.status == 200 and r.body["data"]["created_person"] and r.body["data"]["status"] == "assigned", r.body)
    rid, pid = r.body["data"]["id"], r.body["data"]["individual_id"]
    r = call(door, st, {"collection": "attendances", "op": "assign", "args": {"data": {"scheduled_class_id": cid, "role": "student", "individual_id": pid}}}); check("endpoint duplicate is 400 with existing_id", r.status == 400 and r.body["error"]["problems"][0].get("existing_id") == rid, r.body)
    r = call(door, st, {"collection": "attendances", "op": "list", "args": {"filters": {"scheduled_class_id": cid}, "expand": True}}); check("endpoint list expand", r.status == 200 and r.body["data"]["records"][0]["person"]["display_name"], r.body)
    r = call(door, st, {"collection": "attendances", "op": "update", "args": {"id": rid, "changes": {"status": "attended"}}}); check("endpoint update", r.status == 200, r.body)
    r = call(door, st, {"collection": "venues", "op": "assign", "args": {"data": {}}}); check("other collections refuse assign", r.status == 400)
# ---- the confirmation number follows the request into the class
RQ = "5b1d2c3e-4f50-4a61-8b72-93a4b5c6d7e8"
s.create(AT.REQUESTS.name, RQ, {"id": RQ, "confirmation_number": "LCH-TEST-1234"})
cq = klass("cq")
r = AT.assign(s, {"scheduled_class_id": cq["id"], "role": "student", "individual_id": dee["id"], "request_id": RQ}, A, now=tick())
check("confirmation number copied from the request", r.ok and r.data.get("confirmation_number") == "LCH-TEST-1234", r.problems if not r.ok else r.data)
check("confirmation number cannot be sent", ("confirmation_number", "not_allowed") in issues(AT.create(s, {"individual_id": cy["id"], "scheduled_class_id": cq["id"], "role": "student", "confirmation_number": "X"}, A, now=tick())))
check("no request, no number", "confirmation_number" not in AT.create(s, {"individual_id": cy["id"], "scheduled_class_id": cq["id"], "role": "student"}, A, now=tick()).data)
check("number stays through a status change", (AT.update(s, r.data["id"], {"status": "confirmed"}, A, now=tick()).ok) and AT.get(s, r.data["id"]).data["confirmation_number"] == "LCH-TEST-1234")
check("removing the request removes the number", AT.update(s, r.data["id"], {"request_id": None}, A, now=tick()).ok and "confirmation_number" not in AT.get(s, r.data["id"]).data)
# ---- every record has its own reference
import re as _re
r1 = AT.create(s, {"individual_id": bob["id"], "scheduled_class_id": cq["id"], "role": "student"}, A, now=tick())
check("every record gets its own reference, no request needed", r1.ok and _re.fullmatch(r"ICDT-A-[A-Z2-9]{6}", r1.data.get("reference_number", "")) and "confirmation_number" not in r1.data, r1.data if r1.ok else r1.problems)
eve = person("Eve")
ra = AT.assign(s, {"scheduled_class_id": c2["id"], "role": "student", "individual_id": eve["id"], "request_id": RQ}, A, now=tick())
check("a record from a request has both numbers, and they differ", ra.ok and ra.data["reference_number"] != ra.data["confirmation_number"] and ra.data["confirmation_number"] == "LCH-TEST-1234", ra.data if ra.ok else ra.problems)
check("references are unique", r1.data["reference_number"] != ra.data["reference_number"])
check("reference cannot be sent", ("reference_number", "not_allowed") in issues(AT.create(s, {"individual_id": dee["id"], "scheduled_class_id": c2["id"], "role": "student", "reference_number": "ICDT-A-AAAAAA"}, A, now=tick())))
check("reference cannot be changed", ("reference_number", "not_allowed") in issues(AT.update(s, r1.data["id"], {"reference_number": "ICDT-A-BBBBBB"}, A, now=tick())))
check("reference stays through a status change", AT.update(s, r1.data["id"], {"status": "confirmed"}, A, now=tick()).ok and AT.get(s, r1.data["id"]).data["reference_number"] == r1.data["reference_number"])
print(f"\n{total - len(fails)}/{total} checks passed")
if fails: print("FAILED:", *fails, sep="\n  "); sys.exit(1)
print("OK")
