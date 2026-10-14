#!/usr/bin/env python3
"""In-memory tests for curriculums (crud/curriculums_crud.py, endpoint wiring, and the roster's curriculum_ids).
Run from enjoy_router/:  python3 run_curriculum_tests.py   (-v lists every check). Nothing touches Firebase."""
import json, pathlib, sys
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import curriculums_crud as C  # noqa: E402
from crud import individuals_service as IS  # noqa: E402
from crud import instructor_rosters_service as INS  # noqa: E402
INS.R.needs_address = False   # these checks are about something else; the address rule has its own tests (run_instructor_address_rule_tests.py)
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

store = MemoryDocStore("test_")
r = C.create(store, {"slug": "intro_ai_use", "title": " Introduction to AI Use ", "session_count": 1, "minutes_per_session": 60}, A, now=tick())
check("create", r.ok, r.problems)
check("title trimmed, status defaults to active", r.ok and r.data["title"] == "Introduction to AI Use" and r.data["status"] == "active")
cid = r.data["id"]
check("minimal create", C.create(store, {"slug": "abc", "title": "ABC"}, A, now=tick()).ok)
d = C.create(store, {"slug": "abc", "title": "Other"}, A, now=tick())
check("duplicate slug refused", not d.ok and ("slug", "duplicate") in issues(d))
check("slug required", ("slug", "required") in issues(C.create(store, {"title": "x"}, A, now=tick())))
check("title required", ("title", "required") in issues(C.create(store, {"slug": "zzz"}, A, now=tick())))
check("bad slug refused", not C.create(store, {"slug": "No Good", "title": "x"}, A, now=tick()).ok)
check("sessions below 1 refused", ("session_count", "out_of_range") in issues(C.create(store, {"slug": "q1", "title": "x", "session_count": 0}, A, now=tick())))
check("server field refused", ("id", "not_allowed") in issues(C.create(store, {"slug": "q2", "title": "x", "id": "1"}, A, now=tick())))
u = C.update(store, cid, {"slug": "new"}, A, now=tick()); check("slug immutable", not u.ok and ("slug", "immutable") in issues(u))
u = C.update(store, cid, {"session_count": 3, "minutes_per_session": 90, "description": "d"}, A, now=tick()); check("update", u.ok and u.data["changed"] == ["description", "minutes_per_session", "session_count"], u.problems)
u = C.update(store, cid, {"description": ""}, A, now=tick()); check("empty removes", u.ok and u.data["removed"] == ["description"])
t = C.update(store, cid, {"tagline": "Put down the keyboard. Pick up the conversation."}, A, now=tick()); check("tagline can be set", t.ok and t.data["changed"] == ["tagline"], t.problems)
check("tagline over 120 characters refused", ("tagline", "out_of_range") in issues(C.update(store, cid, {"tagline": "x" * 121}, A, now=tick())))
t = C.update(store, cid, {"tagline": ""}, A, now=tick()); check("empty tagline removes it", t.ok and t.data["removed"] == ["tagline"], t.problems)
check("title cannot be removed", not C.update(store, cid, {"title": None}, A, now=tick()).ok)
check("stale update conflicts", C.update(store, cid, {"notes": "x"}, A, expected_updated_at="2020-01-01T00:00:00Z", now=tick()).code == "conflict")
check("list sorted by title", [x["title"] for x in C.list(store).data["records"]] == ["ABC", "Introduction to AI Use"])
check("list by status", C.list(store, {"status": "inactive"}).data["count"] == 0)
check("list other filter refused", not C.list(store, {"title": "x"}).ok)
check("inactive hides from active list", C.update(store, cid, {"status": "inactive"}, A, now=tick()).ok and C.list(store, {"status": "active"}).data["count"] == 1)
check("delete", C.soft_delete(store, cid, A, now=tick()).ok and not C.get(store, cid).ok and C.get(store, cid, include_deleted=True).ok)
check("deleted slug stays taken", ("slug", "duplicate") in issues(C.create(store, {"slug": "intro_ai_use", "title": "x"}, A, now=tick())))
check("delete twice is not_found", C.soft_delete(store, cid, A, now=tick()).code == "not_found")

# roster curriculum_ids
p = IS.create(store, {"given_name": "Ina"}, A, now=tick()).data
CID = "3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b"
r = INS.create(store, {"individual_id": p["id"], "curriculum_ids": [CID]}, A, now=tick())
check("instructor can hold curriculum_ids (ids are not checked)", r.ok and r.data["curriculum_ids"] == [CID], r.problems)
check("duplicate ids refused by the schema", not INS.update(store, r.data["id"], {"curriculum_ids": [CID, CID]}, A, now=tick()).ok)
check("not-a-uuid refused", not INS.update(store, r.data["id"], {"curriculum_ids": ["abc"]}, A, now=tick()).ok)
check("clearing removes", INS.update(store, r.data["id"], {"curriculum_ids": None}, A, now=tick()).ok and "curriculum_ids" not in INS.get(store, r.data["id"]).data)

# endpoint, both doors
lim = make_failure_limiter(); ts = tick()
def call(h, st, body): return h("POST", "Bearer " + KEY, json.dumps(body).encode(), KEY, "v", st, lim, ts)
for door, st in ((handle_crud_test, MemoryDocStore("test_")), (handle_admin, MemoryDocStore(""))):
    r = call(door, st, {"collection": "curriculums", "op": "create", "args": {"data": {"slug": "e1", "title": "E1"}}}); check("endpoint create", r.status == 200, r.body)
    r = call(door, st, {"collection": "curriculums", "op": "list", "args": {"filters": {"status": "active"}}}); check("endpoint list", r.status == 200 and r.body["data"]["count"] == 1, r.body)
    r = call(door, st, {"collection": "curriculums", "op": "create", "args": {"data": {"slug": "e1", "title": "E1"}}}); check("endpoint duplicate is 400", r.status == 400)
    r = call(door, st, {"collection": "curriculums", "op": "create_with_person", "args": {"data": {}}}); check("curriculums refuse create_with_person", r.status == 400)
print(f"\n{total - len(fails)}/{total} checks passed")
if fails: print("FAILED:", *fails, sep="\n  "); sys.exit(1)
print("OK")
