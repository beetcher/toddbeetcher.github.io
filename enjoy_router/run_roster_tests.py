#!/usr/bin/env python3
"""In-memory tests for the instructor and student rosters (crud/roster_kit.py, the two services, merge/erase hooks and the
endpoint ops). Run from enjoy_router/:  python3 run_roster_tests.py   (-v lists every check). Nothing touches Firebase."""
import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import individuals_service as IS  # noqa: E402
from crud import instructor_rosters_service as INS  # noqa: E402
INS.R.needs_address = False   # these checks are about something else; the address rule has its own tests (run_instructor_address_rule_tests.py)
from crud import student_rosters_service as STU  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud_endpoint import handle_admin, handle_crud_test, make_failure_limiter  # noqa: E402

START = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)
KEY = "k" * 16 + "Z" * 16 + "-test-key-not-real"
ACTOR = "user:admin"
fails, total, clock = [], 0, [0]


def tick():
    clock[0] += 5
    return START + timedelta(seconds=clock[0])


def check(label, ok, detail=""):
    global total
    total += 1
    if not ok:
        fails.append(label)
    if not ok or "-v" in sys.argv:
        print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")


def issues(r):
    return sorted((p["field"], p["issue"]) for p in r.problems)


store = MemoryDocStore("test_")


def person(given="Ann", family="Lee", **kw):
    r = IS.create(store, {"given_name": given, "family_name": family, **kw}, ACTOR, now=tick())
    assert r.ok, r.problems
    return r.data


ann, bob = person(), person("Bob", "Ray", email="bob@example.com", phone="+13035550100")
for svc, name in ((INS, "instructor"), (STU, "student")):
    r = svc.create(store, {"individual_id": ann["id"]}, ACTOR, now=tick())
    check(f"{name}: pointer-only create works", r.ok, r.problems)
    check(f"{name}: status defaults to active", r.ok and r.data["status"] == "active")
    rid = r.data["id"]
    check(f"{name}: no null stored", r.ok and all(v is not None for v in r.data.values()))
    d = svc.create(store, {"individual_id": ann["id"]}, ACTOR, now=tick())
    check(f"{name}: a second entry for the same person is refused", not d.ok and ("individual_id", "duplicate") in issues(d), d.problems)
    check(f"{name}: duplicate names the existing entry", not d.ok and d.problems[0].get("existing_id") == rid)
    n = svc.create(store, {"individual_id": "3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b"}, ACTOR, now=tick())
    check(f"{name}: unknown person refused", not n.ok and ("individual_id", "not_found") in issues(n))
    n = svc.create(store, {}, ACTOR, now=tick())
    check(f"{name}: individual_id required", not n.ok and ("individual_id", "required") in issues(n))
    n = svc.create(store, {"individual_id": bob["id"], "status": "retired"}, ACTOR, now=tick())
    check(f"{name}: bad status refused", not n.ok and ("status", "invalid_value") in issues(n))
    n = svc.create(store, {"individual_id": bob["id"], "id": "x"}, ACTOR, now=tick())
    check(f"{name}: server field refused", not n.ok and ("id", "not_allowed") in issues(n))
    n = svc.create(store, {"individual_id": bob["id"], "notes": "x" * 2001}, ACTOR, now=tick())
    check(f"{name}: length limit", not n.ok and ("notes", "out_of_range") in issues(n))
    u = svc.update(store, rid, {"individual_id": bob["id"]}, ACTOR, now=tick())
    check(f"{name}: individual_id immutable", not u.ok and ("individual_id", "immutable") in issues(u))
    u = svc.update(store, rid, {"status": None}, ACTOR, now=tick())
    check(f"{name}: status cannot be removed", not u.ok)
    u = svc.update(store, rid, {"status": "inactive", "notes": "on leave"}, ACTOR, now=tick())
    check(f"{name}: update works", u.ok and u.data["changed"] == ["notes", "status"], u.problems)
    u = svc.update(store, rid, {"notes": ""}, ACTOR, now=tick())
    check(f"{name}: empty removes", u.ok and u.data["removed"] == ["notes"])
    stale = svc.update(store, rid, {"notes": "a"}, ACTOR, expected_updated_at="2020-01-01T00:00:00Z", now=tick())
    check(f"{name}: stale update conflicts", not stale.ok and stale.code == "conflict")
    g = svc.get(store, rid, expand=True)
    check(f"{name}: expand reads the person", g.ok and g.data["person"]["display_name"] == ann["display_name"], g.data)
    lst = svc.list(store, {"status": "inactive"}, order="name", expand=True)
    check(f"{name}: list filter + name order", lst.ok and lst.data["count"] == 1)
    lst = svc.list(store, {"individual_id": ann["id"]})
    check(f"{name}: list by person", lst.ok and lst.data["count"] == 1)
    lst = svc.list(store, {"status": "active", "individual_id": ann["id"]})
    check(f"{name}: two filters not supported", not lst.ok)
    # create with an existing person, then with a new person
    w = svc.create_with_person(store, {"individual_id": bob["id"]}, ACTOR, now=tick())
    check(f"{name}: create_with_person existing", w.ok and not w.data["created_person"] and w.data["person"]["email"] == "bob@example.com", w.problems)
    before = IS.list(store, None).data["count"]
    w2 = svc.create_with_person(store, {}, ACTOR, person={"given_name": "Cy", "family_name": "Day", "email": "CY@Example.com"}, now=tick())
    check(f"{name}: create_with_person new person", w2.ok and w2.data["created_person"] and w2.data["person"]["email"] == "cy@example.com", w2.problems)
    check(f"{name}: new person exists in People", IS.list(store, None).data["count"] == before + 1)
    both = svc.create_with_person(store, {"individual_id": ann["id"]}, ACTOR, person={"given_name": "Z"}, now=tick())
    check(f"{name}: id and person together refused", not both.ok and ("person", "choose_one") in issues(both))
    cnt = IS.list(store, None).data["count"]
    bad = svc.create_with_person(store, {"notes": "x" * 2001}, ACTOR, person={"given_name": "Dee"}, now=tick())
    check(f"{name}: failed roster entry creates no person", not bad.ok and IS.list(store, None).data["count"] == cnt, bad.problems)
    bad = svc.create_with_person(store, {}, ACTOR, person={"family_name": "NoGiven"}, now=tick())
    check(f"{name}: new person needs a given name", not bad.ok and IS.list(store, None).data["count"] == cnt)
    bad = svc.create_with_person(store, {}, ACTOR, person={"given_name": "E", "shoe": 1}, now=tick())
    check(f"{name}: unknown person field refused", not bad.ok)
    # update with person: all or nothing
    up = svc.update_with_person(store, w["data"]["id"] if False else w.data["id"], {"notes": "hi"}, ACTOR,
                                person={"given_name": "Robert", "phone": "+13035550111"}, now=tick())
    check(f"{name}: update_with_person works", up.ok and up.data["person"]["given_name"] == "Robert" and up.data["notes"] == "hi", up.problems)
    up = svc.update_with_person(store, w.data["id"], {"notes": "x" * 2001}, ACTOR, person={"given_name": "Nope"}, now=tick())
    check(f"{name}: bad roster change saves no person change", not up.ok and IS.get(store, bob["id"]).data["given_name"] == "Robert")
    up = svc.update_with_person(store, w.data["id"], {"notes": "ok2"}, ACTOR, person={"email": "not an email"}, now=tick())
    check(f"{name}: bad person change saves no roster change", not up.ok and svc.get(store, w.data["id"]).data["notes"] == "hi", up.problems)
    up = svc.update_with_person(store, w.data["id"], None, ACTOR, person=None, now=tick())
    check(f"{name}: update_with_person needs something", not up.ok)
    # remove, then re-add
    rm = svc.soft_delete(store, w.data["id"], ACTOR, now=tick())
    check(f"{name}: remove works", rm.ok)
    check(f"{name}: removed entry is gone from get and list", not svc.get(store, w.data["id"]).ok and
          all(r["id"] != w.data["id"] for r in svc.list(store).data["records"]))
    check(f"{name}: removing twice is not_found", svc.soft_delete(store, w.data["id"], ACTOR, now=tick()).code == "not_found")
    check(f"{name}: removed entry cannot be edited", svc.update(store, w.data["id"], {"notes": "z"}, ACTOR, now=tick()).code == "not_found")
    back = svc.create(store, {"individual_id": bob["id"]}, ACTOR, now=tick())
    check(f"{name}: person can be added again after removal", back.ok and back.data["id"] != w.data["id"], back.problems)
    check(f"{name}: history kept", svc.get(store, w.data["id"], include_deleted=True).ok)

# instructor-only fields
r = INS.create(store, {"individual_id": bob["id"], "bio": " Hi ", "capabilities": ["A", "a", " b ", ""], "service_area": "Denver",
                       "availability": [{"day_of_week": "monday", "opens_at": "09:00", "closes_at": "12:00"}],
                       "availability_notes": "n"}, ACTOR, now=tick()) if not INS.list(store, {"individual_id": bob["id"]}).data["count"] else None
if r is None:
    INS.soft_delete(store, INS.list(store, {"individual_id": bob["id"]}).data["records"][0]["id"], ACTOR, now=tick())
    r = INS.create(store, {"individual_id": bob["id"], "bio": " Hi ", "capabilities": ["A", "a", " b ", ""], "service_area": "Denver",
                           "availability": [{"day_of_week": "monday", "opens_at": "09:00", "closes_at": "12:00"}],
                           "availability_notes": "n"}, ACTOR, now=tick())
check("instructor: all fields create", r.ok, r.problems)
check("instructor: bio trimmed, tags deduped and blanks dropped", r.ok and r.data["bio"] == "Hi" and r.data["capabilities"] == ["A", "b"], r.data)
bad = INS.update(store, r.data["id"], {"availability": [{"day_of_week": "monday", "opens_at": "13:00", "closes_at": "12:00"}]}, ACTOR, now=tick())
check("instructor: hours must open before they close", not bad.ok and ("availability", "out_of_range") in issues(bad))
check("student: has no bio", not STU.create(store, {"individual_id": person("Q", "Q")["id"], "bio": "x"}, ACTOR, now=tick()).ok)

# one person on both rosters
c = person("Both", "Rosters")
check("a person may be on both rosters", INS.create(store, {"individual_id": c["id"]}, ACTOR, now=tick()).ok and
      STU.create(store, {"individual_id": c["id"]}, ACTOR, now=tick()).ok)

# merge: roster entries follow the survivor; unmerge restores
d1, d2 = person("Dup", "One"), person("Dup", "One")
e1 = INS.create(store, {"individual_id": d2["id"], "notes": "dup entry"}, ACTOR, now=tick()).data
m = IS.merge(store, d1["id"], d2["id"], "same person", ACTOR, now=tick())
check("merge succeeds", m.ok, m.problems)
check("merge repoints roster entry to the survivor", INS.get(store, e1["id"]).data["individual_id"] == d1["id"])
check("expand follows to the survivor", INS.get(store, e1["id"], expand=True).data["person"]["id"] == d1["id"])
um = IS.unmerge(store, m.data["merge_event_id"] if "merge_event_id" in m.data else m.data["id"], ACTOR, now=tick())
check("unmerge succeeds", um.ok, um.problems)
check("unmerge restores the roster pointer", INS.get(store, e1["id"]).data["individual_id"] == d2["id"])
# adding a merged (old) id follows the survivor
d3, d4 = person("Mer", "Ged"), person("Mer", "Ged")
IS.merge(store, d3["id"], d4["id"], "same", ACTOR, now=tick())
r = STU.create(store, {"individual_id": d4["id"]}, ACTOR, now=tick())
check("adding a merged person's old id uses the survivor", r.ok and r.data["individual_id"] == d3["id"], r.problems)

# erase scrubs
x = person("Erase", "Me")
ie = INS.create(store, {"individual_id": x["id"], "bio": "secret bio", "notes": "private"}, ACTOR, now=tick()).data
se = STU.create(store, {"individual_id": x["id"], "notes": "private"}, ACTOR, now=tick()).data
er = IS.erase(store, x["id"], ACTOR, now=tick())
check("erase succeeds", er.ok, er.problems)
check("erase reports roster entries scrubbed", er.ok and er.data.get("roster_entries_scrubbed") == 2, er.data)
check("erased person's entries are off the rosters", not INS.get(store, ie["id"]).ok and not STU.get(store, se["id"]).ok)
raw = INS.get(store, ie["id"], include_deleted=True).data
check("erased entry keeps no personal data", not any(k in raw for k in ("individual_id", "bio", "notes")), raw)
check("an erased person cannot be added", not INS.create(store, {"individual_id": x["id"]}, ACTOR, now=tick()).ok)

# endpoint
lim = make_failure_limiter()
ts = tick()
tstore = MemoryDocStore("test_")


def call(handler, store_, body, k=KEY):
    return handler("POST", "Bearer " + k, json.dumps(body).encode(), KEY, "v", store_, lim, ts)


for door, st in ((handle_crud_test, tstore), (handle_admin, MemoryDocStore(""))):
    p = call(door, st, {"collection": "individuals", "op": "create", "args": {"data": {"given_name": "Pat"}}})
    pid = p.body["data"]["id"]
    for coll in ("instructor_rosters", "student_rosters"):
        r = call(door, st, {"collection": coll, "op": "create", "args": {"data": {"individual_id": pid}}})
        check(f"endpoint {door.__name__} {coll}: create", r.status == 200, r.body)
        r = call(door, st, {"collection": coll, "op": "create", "args": {"data": {"individual_id": pid}}})
        check(f"endpoint {coll}: duplicate is 400 with existing_id", r.status == 400 and r.body["error"]["problems"][0].get("existing_id"), r.body)
        r = call(door, st, {"collection": coll, "op": "list", "args": {"expand": True, "order": "name"}})
        check(f"endpoint {coll}: list expand", r.status == 200 and r.body["data"]["records"][0]["person"]["display_name"], r.body)
        r = call(door, st, {"collection": coll, "op": "create_with_person", "args": {"data": {}, "person": {"given_name": "New", "email": "n@x.com"}}})
        check(f"endpoint {coll}: create_with_person", r.status == 200 and r.body["data"]["created_person"], r.body)
        rid = r.body["data"]["id"]
        r = call(door, st, {"collection": coll, "op": "update_with_person", "args": {"id": rid, "changes": {"notes": "n"}, "person": {"given_name": "Newer"}}})
        check(f"endpoint {coll}: update_with_person", r.status == 200 and r.body["data"]["person"]["given_name"] == "Newer", r.body)
        r = call(door, st, {"collection": coll, "op": "soft_delete", "args": {"id": rid}})
        check(f"endpoint {coll}: soft_delete", r.status == 200, r.body)
    r = call(door, st, {"collection": "venues", "op": "create_with_person", "args": {"data": {}}})
    check("venues refuse create_with_person", r.status == 400, r.body)
    r = call(door, st, {"collection": "instructor_rosters", "op": "set_place", "args": {"id": pid}})
    check("rosters refuse set_place", r.status == 400, r.body)

print(f"\n{total - len(fails)}/{total} checks passed")
if fails:
    print("FAILED:", *fails, sep="\n  ")
    sys.exit(1)
print("OK")
