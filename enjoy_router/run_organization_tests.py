#!/usr/bin/env python3
"""In-memory tests for organizations (crud/organizations_crud.py and endpoint wiring).
Run from enjoy_router/:  python3 run_organization_tests.py   (-v lists every check). Nothing touches Firebase."""
import json, pathlib, sys
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import organizations_crud as O  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud_endpoint import handle_admin, handle_crud_test, make_failure_limiter  # noqa: E402

START = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)
KEY = "k" * 16 + "Z" * 16 + "-test-key-not-real"
A = "user:admin"
EXAMPLES = HERE.parent / "schemas" / "examples" / "organization.examples.json"
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

# every example record, through the handler
ex = json.loads(EXAMPLES.read_text())
for name, rec in ex["valid"].items():
    r = O.create(store, rec, A, now=tick()); check(f"valid example {name}", r.ok, r.problems)
for name, rec in ex["invalid"].items():
    r = O.create(store, rec, A, now=tick()); check(f"invalid example {name} refused", not r.ok)

store = MemoryDocStore("test_")
r = O.create(store, {"name": "  Ozo Coffee ", "aliases": ["Ozo", "  ", " Ozo Roasters "], "email": "Hello@Example.COM", "phone": "(303)   555-0100",
                     "identifiers": [{"type": "ein", "value": " 00-0000000 ", "description": "  "}]}, A, now=tick())
check("create", r.ok, r.problems)
d = r.data if r.ok else {}
check("name trimmed, status defaults to active", d.get("name") == "Ozo Coffee" and d.get("status") == "active")
check("blank alias dropped", d.get("aliases") == ["Ozo", "Ozo Roasters"])
check("email lowercased, phone spaces collapsed", d.get("email") == "hello@example.com" and d.get("phone") == "(303) 555-0100")
check("blank identifier description dropped", d.get("identifiers") == [{"type": "ein", "value": "00-0000000"}])
check("server fields stamped", all(k in d for k in ("id", "schema_version", "created_at", "created_by", "updated_at", "updated_by", "source")))
oid = d["id"]
check("same name twice is allowed (no duplicate rule)", O.create(store, {"name": "Ozo Coffee"}, A, now=tick()).ok)
check("name required", ("name", "required") in issues(O.create(store, {"kinds": ["business"]}, A, now=tick())))
check("sender cannot set merged", ("status", "not_allowed") in issues(O.create(store, {"name": "x", "status": "merged"}, A, now=tick())))
check("sender cannot set merged_into_id", ("merged_into_id", "not_allowed") in issues(O.create(store, {"name": "x", "merged_into_id": "3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b"}, A, now=tick())))
check("server field refused", ("id", "not_allowed") in issues(O.create(store, {"name": "x", "id": "1"}, A, now=tick())))
check("closed before founded is allowed", O.create(store, {"name": "Old Club", "founded_date": "2010", "closed_date": "2005"}, A, now=tick()).ok)
check("get", O.get(store, oid).ok and not O.get(store, "abc").ok)
u = O.update(store, oid, {"kinds": ["business", "nonprofit"], "website_url": "https://example.com", "short_name": "Ozo"}, A, now=tick())
check("update", u.ok and u.data["changed"] == ["kinds", "short_name", "website_url"], u.problems)
u = O.update(store, oid, {"short_name": ""}, A, now=tick()); check("empty removes", u.ok and u.data["removed"] == ["short_name"])
check("name cannot be removed", not O.update(store, oid, {"name": None}, A, now=tick()).ok)
check("status cannot be removed", not O.update(store, oid, {"status": ""}, A, now=tick()).ok)
check("update cannot set merged", ("status", "not_allowed") in issues(O.update(store, oid, {"status": "merged"}, A, now=tick())))
check("update cannot touch read-only", ("created_by", "not_allowed") in issues(O.update(store, oid, {"created_by": "x"}, A, now=tick())))
check("update bad value refused", not O.update(store, oid, {"email": "nope"}, A, now=tick()).ok)
check("update unknown field refused", not O.update(store, oid, {"ein": "1"}, A, now=tick()).ok)
check("stale update conflicts", O.update(store, oid, {"notes": "x"}, A, expected_updated_at="2020-01-01T00:00:00Z", now=tick()).code == "conflict")
cur = O.get(store, oid).data["updated_at"]
check("matching expected_updated_at works", O.update(store, oid, {"notes": "x"}, A, expected_updated_at=cur, now=tick()).ok)
check("status change to closed", O.update(store, oid, {"status": "closed", "closed_date": "2026-09"}, A, now=tick()).ok)
check("list sorted by name", [x["name"] for x in O.list(store).data["records"]][:2] == ["Old Club", "Ozo Coffee"])
check("list by status", O.list(store, {"status": "closed"}).data["count"] == 1 and O.list(store, {"status": "merged"}).data["count"] == 0)
check("list other filter refused", not O.list(store, {"name": "x"}).ok)
check("list bad order refused", not O.list(store, order="zip").ok)
check("delete", O.soft_delete(store, oid, A, now=tick()).ok and not O.get(store, oid).ok and O.get(store, oid, include_deleted=True).ok)
check("deleted left out of list", all(x["id"] != oid for x in O.list(store).data["records"]))
check("delete twice is not_found", O.soft_delete(store, oid, A, now=tick()).code == "not_found")
check("update after delete is not_found", O.update(store, oid, {"notes": "y"}, A, now=tick()).code == "not_found")

# endpoint, both doors
lim = make_failure_limiter(); ts = tick()
def call(h, st, body): return h("POST", "Bearer " + KEY, json.dumps(body).encode(), KEY, "v", st, lim, ts)
for door, st in ((handle_crud_test, MemoryDocStore("test_")), (handle_admin, MemoryDocStore(""))):
    r = call(door, st, {"collection": "organizations", "op": "create", "args": {"data": {"name": "E1"}}}); check("endpoint create", r.status == 200, r.body)
    r = call(door, st, {"collection": "organizations", "op": "list", "args": {"filters": {"status": "active"}}}); check("endpoint list", r.status == 200 and r.body["data"]["count"] == 1, r.body)
    r = call(door, st, {"collection": "organizations", "op": "create", "args": {"data": {}}}); check("endpoint invalid is 400", r.status == 400)
    r = call(door, st, {"collection": "organizations", "op": "create_with_person", "args": {"data": {}}}); check("organizations refuse create_with_person", r.status == 400)
print(f"\n{total - len(fails)}/{total} checks passed")
if fails: print("FAILED:", *fails, sep="\n  "); sys.exit(1)
print("OK")
