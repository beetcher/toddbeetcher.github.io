#!/usr/bin/env python3
"""In-memory tests for organization_links (crud/organization_links_crud.py, organization_links_service.py, endpoint wiring).
Run from enjoy_router/:  python3 run_organization_link_tests.py   (-v lists every check). Nothing touches Firebase."""
import json, pathlib, sys
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import individuals_crud as I  # noqa: E402
from crud import organization_links_crud as H  # noqa: E402
from crud import organization_links_service as S  # noqa: E402
from crud import organizations_crud as O  # noqa: E402
from crud import venues_crud as V  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud_endpoint import handle_admin, handle_crud_test, make_failure_limiter  # noqa: E402

START = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)
KEY = "k" * 16 + "Z" * 16 + "-test-key-not-real"
A = "user:admin"
EXAMPLES = HERE.parent / "schemas" / "examples" / "organization_link.examples.json"
VENUE = {"name": "Library", "slug": "library", "status": "active", "is_public_venue": True,
         "email": "pat@example.com", "contact_individual_id": "5b1f0c2e-7a4d-4c3b-9e6f-1a2b3c4d5e6f",
         "is_accessible": True, "allows_minors": True, "allows_animals": False,
         "rooms": [{"label": "Main room", "max_occupancy": 40}]}
GHOST = "9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d"
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

# examples: the handler alone (no existence checks)
raw = MemoryDocStore("test_")
ex = json.loads(EXAMPLES.read_text())
for name, rec in ex["valid"].items():
    r = H.create(raw, rec, A, now=tick()); check(f"valid example {name}", r.ok, r.problems)
for name, rec in ex["invalid"].items():
    r = H.create(raw, rec, A, now=tick()); check(f"invalid example {name} refused", not r.ok)

s = MemoryDocStore("test_")
org = O.create(s, {"name": "Ozo Coffee"}, A, now=tick()).data["id"]
org2 = O.create(s, {"name": "BVSD"}, A, now=tick()).data["id"]
todd = I.create(s, {"given_name": "Todd"}, A, now=tick()).data["id"]
venue = V.create(s, dict(VENUE), A, now=tick()).data["id"]
def link(st, sid, rel, oid=None, **kw): return S.create(s, {"subject_type": st, "subject_id": sid, "organization_id": oid or org, "relationship": rel, **kw}, A, now=tick())

r = link("individual", todd, "leads", org2, title="  Superintendent ", valid_from="2021-07")
check("individual leads, title trimmed", r.ok and r.data["title"] == "Superintendent", r.problems)
lid = r.data["id"]
check("server fields stamped", all(k in r.data for k in ("id", "schema_version", "created_at", "created_by", "updated_at", "updated_by", "source")))
check("venue operated_by", link("venue", venue, "operated_by").ok)
check("organization part_of organization", link("organization", org, "part_of", org2).ok)
check("same link twice is allowed (no overlap rule)", link("organization", org, "part_of", org2).ok)
check("a part_of loop is allowed (no loop rule)", link("organization", org2, "part_of", org).ok)
check("dates out of order allowed", link("individual", todd, "member_of", valid_from="2020", valid_to="2010").ok)
check("any word for any subject", link("venue", venue, "leads").ok)
r = link("individual", GHOST, "leads"); check("missing individual refused", ("subject_id", "not_found") in issues(r))
r = link("venue", GHOST, "operated_by"); check("missing venue refused", ("subject_id", "not_found") in issues(r))
r = link("organization", GHOST, "part_of"); check("missing organization subject refused", ("subject_id", "not_found") in issues(r))
r = link("individual", todd, "leads", GHOST); check("missing organization refused", ("organization_id", "not_found") in issues(r))
r = link("organization", org, "part_of", org); check("organization cannot link to itself", ("organization_id", "invalid_value") in issues(r))
check("individual in the wrong collection is not found", ("subject_id", "not_found") in issues(link("individual", venue, "leads")))
check("venue id as organization subject is not found", ("subject_id", "not_found") in issues(link("organization", venue, "part_of")))
check("deleted organization refused", O.soft_delete(s, org2, A, now=tick()).ok and ("organization_id", "not_found") in issues(link("individual", todd, "leads", org2)))
check("bad word refused", not link("individual", todd, "lives_with").ok)
check("server field refused", ("id", "not_allowed") in issues(S.create(s, {"subject_type": "individual", "subject_id": todd, "organization_id": org, "relationship": "leads", "id": "1"}, A, now=tick())))

# merged individual followed to the survivor
a, b = I.create(s, {"given_name": "Ann"}, A, now=tick()).data["id"], I.create(s, {"given_name": "Anne"}, A, now=tick()).data["id"]
from crud import individual_merges_crud as M  # noqa: E402
m = M.merge(s, b, a, "duplicate person", A, now=tick()); check("merge set up", m.ok, m.problems)
r = link("individual", a, "works_for"); check("merged individual followed to survivor", r.ok and r.data["subject_id"] == b, r.problems)

check("get", S.get(s, lid).ok and not S.get(s, "abc").ok)
u = S.update(s, lid, {"title": "Chair", "valid_to": "2024-06", "description": "d"}, A, now=tick()); check("update", u.ok and u.data["changed"] == ["description", "title", "valid_to"], u.problems)
u = S.update(s, lid, {"description": ""}, A, now=tick()); check("empty removes", u.ok and u.data["removed"] == ["description"])
for f, v in (("subject_type", "venue"), ("subject_id", GHOST), ("organization_id", org)):
    check(f"{f} immutable", ("%s" % f, "immutable") in issues(S.update(s, lid, {f: v}, A, now=tick())))
check("relationship can change", S.update(s, lid, {"relationship": "member_of"}, A, now=tick()).ok)
check("relationship cannot be removed", not S.update(s, lid, {"relationship": None}, A, now=tick()).ok)
check("update cannot touch read-only", ("created_by", "not_allowed") in issues(S.update(s, lid, {"created_by": "x"}, A, now=tick())))
check("stale update conflicts", S.update(s, lid, {"title": "x"}, A, expected_updated_at="2020-01-01T00:00:00Z", now=tick()).code == "conflict")
check("list by organization", S.list(s, {"organization_id": org2}).data["count"] >= 1)
check("list by subject and type", all(x["subject_id"] == todd for x in S.list(s, {"subject_id": todd, "subject_type": "individual"}).data["records"]))
check("list other filter refused", not S.list(s, {"title": "x"}).ok)
check("list order valid_from", S.list(s, {"subject_id": todd}, order="valid_from").ok)
check("list bad order refused", not S.list(s, order="zip").ok)
check("delete", S.soft_delete(s, lid, A, now=tick()).ok and not S.get(s, lid).ok and S.get(s, lid, include_deleted=True).ok)
check("deleted left out of list", all(x["id"] != lid for x in S.list(s).data["records"]))
check("delete twice is not_found", S.soft_delete(s, lid, A, now=tick()).code == "not_found")
check("update after delete is not_found", S.update(s, lid, {"title": "y"}, A, now=tick()).code == "not_found")

# endpoint, both doors
lim = make_failure_limiter(); ts = tick()
def call(h, st, body): return h("POST", "Bearer " + KEY, json.dumps(body).encode(), KEY, "v", st, lim, ts)
for door, st in ((handle_crud_test, MemoryDocStore("test_")), (handle_admin, MemoryDocStore(""))):
    r = call(door, st, {"collection": "organizations", "op": "create", "args": {"data": {"name": "E1"}}}); check("endpoint org create", r.status == 200, r.body)
    oid = r.body["data"]["id"]
    r = call(door, st, {"collection": "organization_links", "op": "create", "args": {"data": {"subject_type": "organization", "subject_id": oid, "organization_id": oid, "relationship": "part_of"}}}); check("endpoint self link is 400", r.status == 400, r.body)
    r2 = call(door, st, {"collection": "organizations", "op": "create", "args": {"data": {"name": "E2"}}}); oid2 = r2.body["data"]["id"]
    r = call(door, st, {"collection": "organization_links", "op": "create", "args": {"data": {"subject_type": "organization", "subject_id": oid, "organization_id": oid2, "relationship": "part_of"}}}); check("endpoint link create", r.status == 200, r.body)
    r = call(door, st, {"collection": "organization_links", "op": "list", "args": {"filters": {"organization_id": oid2}}}); check("endpoint list", r.status == 200 and r.body["data"]["count"] == 1, r.body)
    r = call(door, st, {"collection": "organization_links", "op": "create_with_person", "args": {"data": {}}}); check("organization_links refuse create_with_person", r.status == 400)
print(f"\n{total - len(fails)}/{total} checks passed")
if fails: print("FAILED:", *fails, sep="\n  "); sys.exit(1)
print("OK")
