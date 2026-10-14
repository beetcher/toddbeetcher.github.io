#!/usr/bin/env python3
"""In-memory tests for slice B: nobody joins the instructor roster, or is set active again, without a live Lives-here place that has a
state. Grandfathered entries keep working. Run from enjoy_router/:  python3 run_instructor_address_rule_tests.py"""
import json, pathlib, sys
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import attendances_service as AT, individuals_service as IS, instructor_rosters_service as INS, student_rosters_service as STU  # noqa: E402
from crud import location_links_service as LKS, scheduled_classes_crud as CL  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud_endpoint import handle_admin, make_failure_limiter  # noqa: E402
from test_helpers import give_address  # noqa: E402

START = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)
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
NEED = ("individual_id", "address_required")

s = MemoryDocStore("test_")
def person(g): r = IS.create(s, {"given_name": g, "family_name": "X"}, A, now=tick()); assert r.ok, r.problems; return r.data
def klass(slug):
    r = CL.create(s, {"title": "Private session", "slug": slug, "class_type": "private", "program_slug": "launch", "status": "identified", "is_public": False,
                      "capacity_minimum": 1, "capacity_target": 2, "capacity_max": 2}, A, now=tick()); assert r.ok, r.problems; return r.data
def n_people(): return IS.list(s, None, limit=200).data["count"]

# ---- create
ann, bo, cy = person("Ann"), person("Bo"), person("Cy")
r = INS.create(s, {"individual_id": ann["id"]}, A, now=tick())
check("no address: instructor entry refused", not r.ok and NEED in issues(r), r.problems)
check("nothing was written", INS.list(s, {"individual_id": ann["id"]}).data["count"] == 0)
give_address(s, ann["id"], "CO")
r = INS.create(s, {"individual_id": ann["id"]}, A, now=tick())
check("Lives-here address with a state: accepted", r.ok, r.problems)
check("the student roster has no such rule", STU.create(s, {"individual_id": bo["id"]}, A, now=tick()).ok)

# an ended Lives-here link does not count
g = give_address(s, bo["id"], "CO")
assert LKS.end(s, g["id"], A, now=tick()).ok
r = INS.create(s, {"individual_id": bo["id"]}, A, now=tick())
check("an ended address does not count", not r.ok and NEED in issues(r), r.problems)

# a link of another kind does not count
lk = LKS.list(s, {"subject_id": cy["id"]}, limit=5).data["records"]
check("sanity: Cy has no links", lk == [])

# new person path cannot work for instructors (a new person has no address)
before = n_people()
r = INS.create_with_person(s, {}, A, person={"given_name": "New", "family_name": "Face"}, now=tick())
check("someone new cannot be made an instructor in one step", not r.ok and NEED in issues(r), r.problems)
check("and no stray person is left behind", n_people() == before)

# ---- reactivation and grandfathering
INS.R.needs_address = False
old = INS.create(s, {"individual_id": cy["id"]}, A, now=tick()).data      # an instructor from before the rule
INS.R.needs_address = True
check("grandfathered instructor can still be edited", INS.update(s, old["id"], {"notes": "hello"}, A, now=tick()).ok)
check("and set inactive", INS.update(s, old["id"], {"status": "inactive"}, A, now=tick()).ok)
r = INS.update(s, old["id"], {"status": "active"}, A, now=tick())
check("but not set active again without an address", not r.ok and NEED in issues(r), r.problems)
check("still inactive", INS.get(s, old["id"]).data["status"] == "inactive")
give_address(s, cy["id"], "CO")
check("with an address it can be reactivated", INS.update(s, old["id"], {"status": "active"}, A, now=tick()).ok)
check("active to active is not blocked", INS.update(s, old["id"], {"notes": "again"}, A, now=tick()).ok)

# ---- one-step assign from Attendance
c1 = klass("c1"); dee, eve = person("Dee"), person("Eve")
r = AT.assign(s, {"scheduled_class_id": c1["id"], "role": "primary_instructor", "individual_id": dee["id"]}, A, now=tick())
check("assign an addressless person as instructor is refused", not r.ok and NEED in issues(r), r.problems)
check("no roster entry and no attendance came of it", INS.list(s, {"individual_id": dee["id"]}).data["count"] == 0 and AT.list(s, {"individual_id": dee["id"]}).data["count"] == 0)
before = n_people()
r = AT.assign(s, {"scheduled_class_id": c1["id"], "role": "primary_instructor"}, A, person={"given_name": "Zed", "family_name": "New"}, now=tick())
check("assign a brand-new person as instructor is refused", not r.ok and NEED in issues(r), r.problems)
check("and no person was created", n_people() == before)
give_address(s, eve["id"], "CO")
r = AT.assign(s, {"scheduled_class_id": c1["id"], "role": "primary_instructor", "individual_id": eve["id"]}, A, now=tick())
check("a person with an address can be assigned", r.ok and r.data["created_roster_entry"], r.problems)
fay = person("Fay"); STU.create(s, {"individual_id": fay["id"]}, A, now=tick())
r = AT.assign(s, {"scheduled_class_id": c1["id"], "role": "student", "individual_id": fay["id"]}, A, now=tick())
check("students need no address", r.ok, r.problems)
# a grandfathered instructor who already has an entry can still be assigned
r = AT.assign(s, {"scheduled_class_id": klass("c2")["id"], "role": "primary_instructor", "individual_id": cy["id"]}, A, now=tick())
check("an existing entry is not re-checked on assign", r.ok and not r.data["created_roster_entry"], r.problems)

# ---- through the admin door, with the issue code the Console maps
st = MemoryDocStore("door_"); lim = make_failure_limiter(); gus = IS.create(st, {"given_name": "Gus", "family_name": "X"}, A, now=tick()).data
def door(op, args, coll):
    r = handle_admin("POST", "Bearer " + KEY, json.dumps({"collection": coll, "op": op, "args": args}).encode(), KEY, "v", st, lim, datetime.now(timezone.utc))
    return r.status, r.body
code, body = door("create", {"data": {"individual_id": gus["id"]}}, "instructor_rosters")
probs = (body.get("error") or {}).get("problems") or []
check("the admin door refuses with address_required", code != 200 and any(p.get("issue") == "address_required" for p in probs), (code, body))

print(f"\n{total - len(fails)}/{total} checks passed" + (" OK" if not fails else "  FAILED: " + "; ".join(fails)))
sys.exit(1 if fails else 0)
