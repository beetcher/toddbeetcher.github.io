#!/usr/bin/env python3
"""In-memory tests for the derived residence_state on instructor roster entries (crud/roster_kit.py).
Run from enjoy_router/:  python3 run_instructor_state_tests.py  (-v lists every check)."""
import pathlib
import sys
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import individuals_crud as I  # noqa: E402
from crud import instructor_rosters_service as INS  # noqa: E402
INS.R.needs_address = False   # these checks are about something else; the address rule has its own tests (run_instructor_address_rule_tests.py)
from crud import location_links_service as S  # noqa: E402
from crud import locations_crud as L  # noqa: E402
from crud import student_rosters_service as STU  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402

START = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)
clock = [0]
fails, total = [], 0
ACT = "user:todd"
s = MemoryDocStore("")


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


def person(name):
    return I.create(s, {"given_name": name}, ACT, now=tick()).data


def home(name, region, **kw):
    addr = {"usage": "civic", "street_number": "1", "street": "Main St", "locality": "Town", "region": region, "postal_code": "80027", "country": "US", **kw}
    r = L.create(s, {"name": name, "addresses": [addr]}, ACT, now=tick())
    assert r.ok, r.problems
    return r.data


def live(p, loc, **kw):
    r = S.create(s, {"subject_type": "individual", "subject_id": p["id"], "location_id": loc["id"], "relationship": "resides_at", **kw}, ACT, now=tick())
    assert r.ok, r.problems
    return r.data


def instructor(p):
    r = INS.create(s, {"individual_id": p["id"]}, ACT, now=tick())
    assert r.ok, r.problems
    return r.data


def state_of(p):
    rows = INS.list(s, {"status": "active"}, expand=True).data["records"]
    return next(d for d in rows if d["individual_id"] == p["id"]).get("residence_state")


co, ca, none, two, ended, lower = person("Colo"), person("Cali"), person("Nowhere"), person("Two"), person("Ended"), person("Lower")
live(co, home("Co home", "CO")); live(ca, home("Ca home", "CA")); live(lower, home("Lower home", "co"))
live(two, home("Two second", "CA")); live(two, home("Two primary", "CO"), is_primary=True)
old = live(ended, home("Ended home", "CA")); S.end(s, old["id"], ACT, valid_to="2020-01-01", now=tick())
for p in (co, ca, none, two, ended, lower):
    instructor(p)

check("a Colorado address gives CO", state_of(co) == "CO")
check("a California address gives CA", state_of(ca) == "CA")
check("a lower-case region is read as its capital letters", state_of(lower) == "CO")
check("no address: no residence_state", state_of(none) is None)
check("two homes: the primary one decides", state_of(two) == "CO")
check("an ended link no longer counts", state_of(ended) is None)
rec = next(d for d in INS.list(s, {"status": "active"}, expand=True).data["records"] if d["individual_id"] == co["id"])
check("only the state leaves, no street or town", "Main St" not in str(rec) and "Town" not in str(rec))
check("it is not stored on the roster record", "residence_state" not in s.get("instructor_rosters", rec["id"]) if s.get("instructor_rosters", rec["id"]) else True)
plain = INS.list(s, {"status": "active"}).data["records"]
check("without expand there is no residence_state", not any("residence_state" in d for d in plain))
w = person("Student Sam"); live(w, home("Sam home", "CO")); STU.create(s, {"individual_id": w["id"]}, ACT, now=tick())
check("the student roster does not get residence_state", not any("residence_state" in d for d in STU.list(s, expand=True).data["records"]))
g = INS.get(s, rec["id"], expand=True)
check("get with expand carries it too", g.ok and g.data.get("residence_state") == "CO")

print(f"\n{'OK' if not fails else 'FAILED'}: {total - len(fails)}/{total} checks" + ("" if not fails else "  failed: " + "; ".join(fails)))
sys.exit(1 if fails else 0)
