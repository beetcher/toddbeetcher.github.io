#!/usr/bin/env python3
"""Coverage of private requests (P-83 builds 1 and 2): the stamp, the open test, the completion re-stamp and the recipients of the urgent notice.
Run from enjoy_router/:  python3 -B run_coverage_tests.py  (-v lists every check)."""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from launch_comms import coverage_recipients as CR  # noqa: E402
import request_coverage as RC  # noqa: E402

fails, total = [], 0


def check(label, ok, detail=""):
    global total
    total += 1
    if not ok:
        fails.append(label)
    if not ok or "-v" in sys.argv:
        print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")


def area(i, kind, name, state="CO", active=True, zips=None, deleted=False):
    d = {"id": i, "kind": kind, "name": name, "state_code": state, "is_active": active, "schema_version": 1}
    if kind == "region":
        d["zip_codes"] = zips or []
    if deleted:
        d["deleted_at"] = "2026-09-01T00:00:00Z"
    return d


AREAS = [area("s-co", "state", "Colorado"), area("s-wi", "state", "Wisconsin", "WI"), area("s-ut", "state", "Utah", "UT", active=False),
         area("r-bou", "region", "Boulder", "CO", zips=["80301"]), area("r-hay", "region", "Hayward", "WI", zips=["54843"]),
         area("r-off", "region", "Off", "CO", active=False, zips=["80401"]), area("r-gone", "region", "Gone", "CO", zips=["80501"], deleted=True),
         area("r-ut", "region", "Salt Lake", "UT", zips=["84101"])]
P = lambda **k: dict({"registration_type": "private"}, **k)  # noqa: E731

# ---- the stamp
f = RC.fields_for
check("ZIP in an active region: covered, with the state", f(AREAS, P(postal_code="54843")) == {"coverage": "covered", "coverage_state_code": "WI"})
check("ZIP in no region: no_active_region, with the ZIP table's state", f(AREAS, P(postal_code="80202")) == {"coverage": "no_active_region", "coverage_state_code": "CO"})
check("ZIP only in a switched-off region: not covered", f(AREAS, P(postal_code="80401"))["coverage"] == "no_active_region")
check("ZIP only in a deleted region: not covered", f(AREAS, P(postal_code="80501"))["coverage"] == "no_active_region")
check("ZIP in a region of a switched-off state: not covered", f(AREAS, P(postal_code="84101")) == {"coverage": "no_active_region", "coverage_state_code": "UT"})
check("no ZIP, a picked active region: covered", f(AREAS, P(region_id="r-bou")) == {"coverage": "covered", "coverage_state_code": "CO"})
check("a ZIP wins over a picked region", f(AREAS, P(region_id="r-bou", postal_code="80202"))["coverage"] == "no_active_region")
check("no ZIP, a region that is no longer active: nothing said", f(AREAS, P(region_id="r-off")) == {})
check("no ZIP and no region: nothing said", f(AREAS, P()) == {})
check("group and class requests are not judged", f(AREAS, {"registration_type": "group", "postal_code": "80202"}) == {} and f(AREAS, {"registration_type": "workshop", "postal_code": "80202"}) == {})
check("a ZIP not in the table still counts (state unknown)", f(AREAS, P(postal_code="00001")) == {"coverage": "no_active_region"})
check("no areas at all: any ZIP is not covered", f([], P(postal_code="80301"))["coverage"] == "no_active_region")

# ---- open means still waiting
urgent = P(coverage="no_active_region", postal_code="80202")
check("open: urgent, not handled, nobody holds the ZIP", RC.is_open(AREAS, urgent))
check("not open once handled", not RC.is_open(AREAS, dict(urgent, coverage_handled_at="2026-10-22T16:00:00Z")))
check("not open when deleted", not RC.is_open(AREAS, dict(urgent, deleted_at="2026-10-22T16:00:00Z")))
check("a covered request is not open", not RC.is_open(AREAS, P(coverage="covered", postal_code="54843")))
check("not open any more when a region now holds the ZIP", not RC.is_open(AREAS + [area("r-den", "region", "Denver", "CO", zips=["80202"])], urgent))
check("a request with no coverage is not open", not RC.is_open(AREAS, P(postal_code="80202")))

# ---- recipients
s = MemoryDocStore("")


def role(i, key, sup=False, caps=(), active=True, deleted=False):
    d = {"id": i, "key": key, "label": key, "capabilities": list(caps), "is_super_admin": sup, "is_active": active, "schema_version": 1}
    if deleted:
        d["deleted_at"] = "2026-09-01T00:00:00Z"
    s.create("access_roles", i, d)


def person(i, email, role_id, grants=None, active=True, deleted=False, name=""):
    d = {"id": i, "email": email, "role_id": role_id, "is_active": active, "display_name": name or email.split("@")[0], "schema_version": 1}
    if grants is not None:
        d["grants"] = grants
    if deleted:
        d["deleted_at"] = "2026-09-01T00:00:00Z"
    s.create("access_persons", i, d)


role("ro-sup", "super_admin", sup=True, caps=("inspect_everything",))   # a super admin lists every capability, inspect included
role("ro-adm", "admin", caps=("view_console", "manage_access"))
role("ro-ins", "global_inspector", caps=("view_console", "inspect_everything"))
role("ro-mgr", "manager", caps=("view_console",))
role("ro-off", "retired", caps=("view_console",), active=False)
role("ro-gone", "removed", caps=("view_console",), deleted=True)
person("p-sup", "todd@example.com", "ro-sup")
person("p-adm", "admin@example.com", "ro-adm")
person("p-ins", "eli@example.com", "ro-ins")
person("p-wi", "wi.owner@example.com", "ro-mgr", [{"kind": "state", "state_code": "WI"}])
person("p-co", "co.owner@example.com", "ro-mgr", [{"kind": "state", "state_code": "CO"}])
person("p-reg", "region.head@example.com", "ro-mgr", [{"kind": "regions", "state_code": "WI", "region_ids": ["r-hay"]}])
person("p-all", "all.manager@example.com", "ro-mgr", [{"kind": "all"}])
person("p-plain", "plain@example.com", "ro-mgr")
person("p-offp", "off@example.com", "ro-adm", active=False)
person("p-del", "deleted@example.com", "ro-adm", deleted=True)
person("p-oldrole", "oldrole@example.com", "ro-off", [{"kind": "state", "state_code": "WI"}])
person("p-gonerole", "gonerole@example.com", "ro-gone", [{"kind": "state", "state_code": "WI"}])
person("p-wi-ins", "wi.inspector@example.com", "ro-ins", [{"kind": "state", "state_code": "WI"}])

got = CR.recipients(s, "WI")
emails = [r["email"] for r in got]
check("Wisconsin: super admin, admin, inspectors and Wisconsin's state owner", emails == ["admin@example.com", "eli@example.com", "todd@example.com", "wi.inspector@example.com", "wi.owner@example.com"], str(emails))
by = {r["email"]: r for r in got}
check("the super admin is not an inspector even though inspect is listed", by["todd@example.com"]["reasons"] == ["super_admin"] and by["todd@example.com"]["masked"] is False)
check("the admin gets the full copy", by["admin@example.com"]["reasons"] == ["admin"] and by["admin@example.com"]["masked"] is False)
check("the Global Inspector gets the masked copy", by["eli@example.com"]["reasons"] == ["inspector"] and by["eli@example.com"]["masked"] is True)
check("an Inspector who also holds the state grant is still masked", by["wi.inspector@example.com"]["masked"] is True and "state_owner" in by["wi.inspector@example.com"]["reasons"])
check("the state owner gets the full copy", by["wi.owner@example.com"]["reasons"] == ["state_owner"] and by["wi.owner@example.com"]["masked"] is False)
check("another state's owner is not told", "co.owner@example.com" not in emails)
check("a region head, an all-territory manager and a plain person are not told", not {"region.head@example.com", "all.manager@example.com", "plain@example.com"} & set(emails))
check("a switched-off person, a deleted person, a person with a retired or deleted role are not told", not {"off@example.com", "deleted@example.com", "oldrole@example.com", "gonerole@example.com"} & set(emails))
co = [r["email"] for r in CR.recipients(s, "CO")]
check("Colorado: the same three always, and Colorado's owner instead", co == ["admin@example.com", "co.owner@example.com", "eli@example.com", "todd@example.com", "wi.inspector@example.com"], str(co))
nostate = [r["email"] for r in CR.recipients(s, None)]
check("a ZIP whose state is unknown: staff and inspectors only, no state owner", nostate == ["admin@example.com", "eli@example.com", "todd@example.com", "wi.inspector@example.com"], str(nostate))
check("one entry per person (no duplicates)", len(emails) == len(set(emails)))

print(f"{'OK' if not fails else 'FAILED'}: {total - len(fails)}/{total} checks")
sys.exit(1 if fails else 0)
