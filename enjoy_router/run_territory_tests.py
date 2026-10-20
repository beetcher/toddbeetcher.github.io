#!/usr/bin/env python3
"""Tests for territory (P-60 / P-65, step 2): which ZIPs a person's grants cover (access/territory.py), where a record is (access/places.py)
and how grants reach the sign-in result (access/authorize.py). Run from enjoy_router/:  python3 run_territory_tests.py   (-v lists every check).
Nothing touches Firebase."""
import pathlib, sys
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from access import authenticate  # noqa: E402
from access.capabilities import GLOBAL, TERRITORIAL  # noqa: E402
from access.places import zip_of, zip_of_location  # noqa: E402
from access.territory import Scope, Territory, norm_zip  # noqa: E402
from crud import access_persons_crud as PE, access_roles_crud as RO  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from launch_discovery import zip_table  # noqa: E402

START = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)
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

# a small ZIP table: Boulder-area CO ZIPs, two Wisconsin ZIPs, two Minnesota ZIPs
zip_table.set_table({**{z: ["CO", 40.0, -105.0, "X"] for z in ("80301", "80302", "80303", "80501")},
                     **{z: ["WI", 43.0, -89.0, "X"] for z in ("53703", "53202", "53704")},
                     **{z: ["MN", 44.0, -92.0, "X"] for z in ("55901", "55902")}})

s = MemoryDocStore("")
def uid(n): return f"{n:08d}-0000-4000-8000-000000000000"
def area(n, kind, st, name, **kw):
    s.create("discovery_areas", uid(n), {"id": uid(n), "kind": kind, "state_code": st, "name": name, "is_active": True, **kw}); return uid(n)
CO, WI, MN = area(1, "state", "CO", "Colorado"), area(2, "state", "WI", "Wisconsin"), area(3, "state", "MN", "Minnesota")
BOULDER = area(10, "region", "CO", "Boulder", zip_codes=["80301", "80302"])
LONGMONT = area(11, "region", "CO", "Longmont", zip_codes=["80301", "80501"])          # shares 80301 with Boulder
MADISON = area(12, "region", "WI", "Madison", zip_codes=["53703"])
MILWAUKEE = area(13, "region", "WI", "Milwaukee", zip_codes=["53202"])
ROCHESTER = area(14, "region", "MN", "Rochester", zip_codes=["55901"])
GONE = area(15, "region", "CO", "Old", zip_codes=["80303"]); s.update("discovery_areas", GONE, {"deleted_at": "2026-10-01T00:00:00Z"}, ())

# ================================================================ norm_zip
check("norm_zip: five digits", norm_zip("80301") == "80301")
check("norm_zip: ZIP+4 is trimmed", norm_zip("80301-1234") == "80301" and norm_zip(" 80301 1234") == "80301")
check("norm_zip: junk gives None", all(norm_zip(x) is None for x in ("", "8030", "abcde", None, 80301, "1234567", "A80301")))

# ================================================================ Territory.covers
T = Territory(s)
g_all = {"kind": "all"}
g_co = {"kind": "state", "state_code": "CO"}
g_boulder = {"kind": "regions", "state_code": "CO", "region_ids": frozenset([BOULDER])}
g_two = {"kind": "regions", "state_code": "WI", "region_ids": frozenset([MADISON, MILWAUKEE])}
check("regions_of_zip: a shared ZIP is in both regions", T.regions_of_zip("80301") == {BOULDER, LONGMONT})
check("regions_of_zip: a deleted region claims nothing", T.regions_of_zip("80303") == frozenset())
check("state_of_zip: from the ZIP table, even when no region claims the ZIP", T.state_of_zip("80303") == "CO" and T.state_of_zip("53704") == "WI")
check("state_of_zip: a ZIP nobody knows has no state", T.state_of_zip("99999") is None)
check("all: covers every ZIP and also a record with no ZIP", T.covers(g_all, "80301") and T.covers(g_all, None) and T.covers(g_all, "99999"))
check("state: covers a ZIP in a region of the state", T.covers(g_co, "80301"))
check("state: covers an UNASSIGNED ZIP in the state (no region lists it)", T.covers(g_co, "80303") and T.covers(g_co, "80302-9999") is True)
check("state: does not cover another state", not T.covers(g_co, "53703") and not T.covers(g_co, "55901"))
check("state: a record with no ZIP, or an unplaceable ZIP, is not covered", not T.covers(g_co, None) and not T.covers(g_co, "") and not T.covers(g_co, "99999"))
check("regions: covers a ZIP the region lists", T.covers(g_boulder, "80301") and T.covers(g_boulder, "80302"))
check("regions: does not cover an unassigned ZIP of the same state", not T.covers(g_boulder, "80303"))
check("regions: does not cover a ZIP of a region the person was not given", not T.covers(g_boulder, "80501"))
check("regions: a shared ZIP is covered through either region", T.covers({"kind": "regions", "state_code": "CO", "region_ids": frozenset([LONGMONT])}, "80301"))
check("regions: a subset of regions in one state", T.covers(g_two, "53703") and T.covers(g_two, "53202") and not T.covers(g_two, "53704"))
check("regions: no ZIP is not covered", not T.covers(g_boulder, None))
check("unknown grant kind covers nothing", not T.covers({"kind": "county"}, "80301") and not T.covers({}, "80301"))
zip_table.set_table(None); zip_table.DEFAULT_PATH = pathlib.Path("/nonexistent")
T2 = Territory(s)
check("without a ZIP table the state of a ZIP falls back to the regions that list it", T2.state_of_zip("80301") == "CO" and T2.covers(g_co, "80301") and not T2.covers(g_co, "80303"))
zip_table.set_table({**{z: ["CO", 40.0, -105.0, "X"] for z in ("80301", "80302", "80303", "80501")}, **{z: ["WI", 43.0, -89.0, "X"] for z in ("53703", "53202", "53704")},
                     **{z: ["MN", 44.0, -92.0, "X"] for z in ("55901", "55902")}})

# ================================================================ sign-in carries grants
sup = RO.create(s, {"key": "super_admin", "label": "Super", "is_super_admin": True}, A, now=tick()).data
head_role = RO.create(s, {"key": "region_head", "label": "Head", "is_super_admin": False,
                          "capabilities": ["view_console", "edit_venues", "manage_requests", "view_spend"]}, A, now=tick()).data
def person(email, role=head_role, **kw):
    r = PE.create(s, {"email": email, "role_id": role["id"], **kw}, A, now=tick()); assert r.ok, r.problems; return r.data
class Fake:
    def __init__(self): self.tokens = {}
    def verify(self, t): return dict(self.tokens[t])
V = Fake(); KEY = "k" * 40; n = [100]
def sign(email, store=None):
    n[0] += 1; t = f"header{n[0]:03d}.payload{n[0]:03d}.signature{n[0]:03d}" + "x" * 20
    V.tokens[t] = {"uid": f"uid-{email}", "email": email, "email_verified": True, "provider": "google.com", "name": "G"}
    return authenticate(t, admin_key=KEY, verifier=V, store=store or s, now=tick())

person("todd@x.com", sup)
a = sign("todd@x.com")
check("super admin: one all grant with every territorial capability", len(a.grants) == 1 and a.grants[0]["kind"] == "all" and a.grants[0]["capabilities"] == frozenset(TERRITORIAL))
k = authenticate(KEY, admin_key=KEY, verifier=V, store=s, now=tick())
check("the key: also unlimited", k.grants[0]["kind"] == "all" and Scope(k, T).unlimited)

person("nogrants@x.com")
a = sign("nogrants@x.com")
check("a person with a role but no grants: role's territorial capabilities give nothing", not a.can("edit_venues") and not a.can("manage_requests") and a.grants == ())
check("... but the role's global capabilities still count", a.can("view_console") and a.can("view_spend"))
check("... and they see and do nothing anywhere", not Scope(a, T).sees("80301") and not Scope(a, T).has("edit_venues", "80301") and not Scope(a, T).unlimited)

person("multi@x.com", grants=[
    {"kind": "regions", "state_code": "WI", "region_ids": [MADISON], "capabilities": ["edit_venues", "manage_requests"], "group": "Wisconsin team"},
    {"kind": "regions", "state_code": "WI", "region_ids": [MILWAUKEE], "capabilities": ["manage_requests"]},
    {"kind": "regions", "state_code": "MN", "region_ids": [ROCHESTER], "capabilities": ["edit_venues"]},
    {"kind": "state", "state_code": "CO"}])
a = sign("multi@x.com"); sc = Scope(a, T)
check("grants: all four reach the sign-in result", len(a.grants) == 4 and {g["kind"] for g in a.grants} == {"regions", "state"})
check("grants: a state grant carries every territorial capability", [g for g in a.grants if g["kind"] == "state"][0]["capabilities"] == frozenset(TERRITORIAL))
check("grants: group label is carried", a.grants[0]["group"] == "Wisconsin team")
check("each region has its own capabilities: edit venues in Madison but not in Milwaukee", sc.has("edit_venues", "53703") and not sc.has("edit_venues", "53202"))
check("each region has its own capabilities: requests in both Wisconsin regions", sc.has("manage_requests", "53703") and sc.has("manage_requests", "53202"))
check("rights in one region do not leak into another state's region", sc.has("edit_venues", "55901") and not sc.has("manage_requests", "55901"))
check("a state grant is administrator of that state: every territorial capability, unassigned ZIPs included", all(sc.has(c, "80303") for c in TERRITORIAL))
check("a state grant is not another state", not sc.has("edit_venues", "53704"))
check("looking: any covering grant lets the person see the place", sc.sees("53202") and sc.sees("80303") and not sc.sees("53704") and not sc.sees(None))
check("global capabilities come from the role", sc.has("view_spend", "99999") and sc.has("view_spend", None) and not sc.has("manage_access", "80301"))
check("a capability that does not exist is never held", not sc.has("brand_new", "80301"))
check("union of capabilities for the Console's station gating", a.can("edit_venues") and a.can("manage_requests") and a.can("edit_regions") and not a.can("manage_access"))
check("not unlimited with only a state and regions", not sc.unlimited)
sc_sup = Scope(sign("todd@x.com"), T)
check("super admin: unlimited, sees and does everything everywhere, even a record with no place", sc_sup.unlimited and sc_sup.has("edit_venues", None) and sc_sup.sees(None) and sc_sup.has("manage_access", None))
check("satisfies: all groups, any capability in a group", sc.satisfies((("edit_venues",), ("manage_requests",)), "53703") and not sc.satisfies((("edit_venues",), ("manage_requests",)), "53202")
      and sc.satisfies((("edit_venues", "manage_requests"),), "53202"))
check("can_read: needs the read capability AND a covering grant", sc.can_read((("view_console",),), "53202") and not sc.can_read((("view_console",),), "53704")
      and not sc.can_read((("view_console",),), None) and sc.can_read((("manage_requests",),), "53202") and not sc.can_read((("edit_venues",),), "53202"))

person("whole@x.com", grants=[{"kind": "all"}])
a = sign("whole@x.com"); sc_all = Scope(a, T)
check("an all grant on an ordinary role: every territorial capability everywhere, but only the role's global ones", sc_all.unlimited and sc_all.has("edit_venues", None)
      and not sc_all.has("manage_access", None) and not a.is_super_admin and sc_all.has("view_spend", None))

# legacy scope_region_id
person("legacy@x.com", scope_region_id=BOULDER)
a = sign("legacy@x.com"); sc = Scope(a, T)
check("legacy scope_region_id: one regions grant with the role's territorial capabilities", len(a.grants) == 1 and a.grants[0]["region_ids"] == frozenset([BOULDER])
      and a.grants[0]["capabilities"] == frozenset({"edit_venues", "manage_requests"}) and sc.has("edit_venues", "80301") and not sc.has("edit_venues", "80501"))
person("both@x.com", scope_region_id=BOULDER, grants=[{"kind": "state", "state_code": "WI"}])
a = sign("both@x.com")
check("real grants win over the retired scope_region_id", len(a.grants) == 1 and a.grants[0]["kind"] == "state")
s.update("discovery_areas", BOULDER, {"deleted_at": "2026-10-20T00:00:00Z"}, ())
check("a legacy region that was deleted gives no territory", sign("legacy@x.com").grants == ())
s.update("discovery_areas", BOULDER, {}, ("deleted_at",))

person("deleted-region@x.com", grants=[{"kind": "regions", "state_code": "CO", "region_ids": [LONGMONT], "capabilities": ["edit_venues"]}])
s.update("discovery_areas", LONGMONT, {"deleted_at": "2026-10-20T00:00:00Z"}, ())
a = sign("deleted-region@x.com"); T3 = Territory(s)
check("a region deleted after the grant covers nothing", not Scope(a, T3).sees("80501") and not Scope(a, T3).has("edit_venues", "80501"))
s.update("discovery_areas", LONGMONT, {}, ("deleted_at",))

# ================================================================ places
def doc(coll, i, **kw):
    d = {"id": uid(i), **kw}; s.create(coll, d["id"], d); return d
def place(i, zip_code, **kw):
    return doc("locations", i, status="active", addresses=[{"usage": "business", "postal_code": zip_code, "is_primary": True, **kw}])
def link(i, subject_type, subject_id, loc_id, rel, **kw):
    return doc("location_links", i, **{"subject_type": subject_type, "subject_id": subject_id, "location_id": loc_id, "relationship": rel,
                                         "status": "active", "is_primary": True, **kw})

v1, v2, v3, v4 = doc("venues", 100, name="A"), doc("venues", 101, name="B"), doc("venues", 102, name="No place"), doc("venues", 103, name="GPS only")
place(200, "80301"); link(300, "venue", v1["id"], uid(200), "operates_at")
place(201, "53703-4455"); link(301, "venue", v2["id"], uid(201), "operates_at")
doc("locations", 202, status="active", addresses=[], geometries=[{"lat": 1, "lon": 2}]); link(302, "venue", v4["id"], uid(202), "operates_at")
check("venue: ZIP from its operates_at place", zip_of(s, "venues", v1) == "80301")
check("venue: ZIP+4 is trimmed", zip_of(s, "venues", v2) == "53703")
check("venue: no place gives None", zip_of(s, "venues", v3) is None)
check("venue: a place with only GPS gives None", zip_of(s, "venues", v4) is None)
place(203, "80501"); link(303, "venue", v1["id"], uid(203), "operates_at", is_primary=False)
check("venue: the primary place wins", zip_of(s, "venues", v1) == "80301")
s.update("location_links", uid(300), {"status": "ended"}, ())
check("venue: an ended link is ignored (the other live place is used)", zip_of(s, "venues", v1) == "80501")
s.update("location_links", uid(303), {"deleted_at": "2026-10-20T00:00:00Z"}, ())
check("venue: a deleted link is ignored", zip_of(s, "venues", v1) is None)
s.update("location_links", uid(300), {"status": "active"}, ()); s.update("location_links", uid(303), {}, ("deleted_at",))
check("venue: a link of another kind (resides_at) is not a venue's place", zip_of(s, "venues", doc("venues", 104)) is None)
v5 = doc("venues", 105, name="Two places"); place(206, "80302"); place(207, "80303")
link(306, "venue", v5["id"], uid(206), "operates_at", is_primary=False); link(307, "venue", v5["id"], uid(207), "operates_at", is_primary=True)
check("venue: the primary link wins even when it was made second", zip_of(s, "venues", v5) == "80303")
check("location: former addresses are ignored", zip_of_location({"addresses": [{"usage": "former", "postal_code": "80301"}]}) is None)
check("location: primary first, else any current address", zip_of_location({"addresses": [{"postal_code": "80302"}, {"postal_code": "80301", "is_primary": True}]}) == "80301"
      and zip_of_location({"addresses": [{"postal_code": "80302"}]}) == "80302")

c1 = doc("scheduled_classes", 110, venue_id=v1["id"], title="C1"); c2 = doc("scheduled_classes", 111, venue_id=v3["id"], title="C2")
check("class: ZIP of its venue", zip_of(s, "scheduled_classes", c1) == "80301")
check("class: venue without a place gives None", zip_of(s, "scheduled_classes", c2) is None)

r1 = doc("registration_requests", 120, postal_code="80302")
r2 = doc("registration_requests", 121, scheduled_class_id=c1["id"])
r3 = doc("registration_requests", 122, preferred_venue_id=v2["id"])
r4 = doc("registration_requests", 123, first_name="No place")
r5 = doc("registration_requests", 124, postal_code="80302", scheduled_class_id=uid(111))
check("request: its own postal_code", zip_of(s, "registration_requests", r1) == "80302")
check("request: a class request through the class's venue", zip_of(s, "registration_requests", r2) == "80301")
check("request: through the venue asked for", zip_of(s, "registration_requests", r3) == "53703")
r6 = doc("registration_requests", 125, registration_type="private")
c3 = doc("scheduled_classes", 112, venue_id=v2["id"], source_request_id=r6["id"], title="Built from the request")
check("request: a class built from it gives the place (private and group requests)", zip_of(s, "registration_requests", r6) == "53703")
check("request: nothing to go on gives None", zip_of(s, "registration_requests", r4) is None)
check("request: its own ZIP wins over its class", zip_of(s, "registration_requests", r5) == "80302")

asg = doc("registration_assignments", 130, request_id=r1["id"], scheduled_class_id=c1["id"])
check("assignment: through its request first", zip_of(s, "registration_assignments", asg) == "80302")
asg2 = doc("registration_assignments", 131, request_id=r4["id"], scheduled_class_id=c1["id"])
check("assignment: else through its class", zip_of(s, "registration_assignments", asg2) == "80301")
att = doc("attendances", 140, scheduled_class_id=c1["id"], request_id=r3["id"])
check("attendance: through its class first, else its request", zip_of(s, "attendances", att) == "80301" and zip_of(s, "attendances", {"id": "x", "request_id": r3["id"]}) == "53703")
p1 = doc("individuals", 150, display_name="P"); place(204, "55901"); link(304, "individual", p1["id"], uid(204), "resides_at")
check("person: ZIP of where they live", zip_of(s, "individuals", p1) == "55901")
p2 = doc("individuals", 151, display_name="Works"); place(205, "55902"); link(305, "individual", p2["id"], uid(205), "works_at")
check("person: a work address is not where they live", zip_of(s, "individuals", p2) is None)
ir = doc("instructor_rosters", 160, individual_id=p1["id"]); sr = doc("student_rosters", 161, individual_id=p2["id"])
check("rosters: the person's ZIP", zip_of(s, "instructor_rosters", ir) == "55901" and zip_of(s, "student_rosters", sr) is None)
log = doc("communication_logs", 170, scheduled_class_id=c1["id"])
check("communication log: through its class, else request, else person", zip_of(s, "communication_logs", log) == "80301"
      and zip_of(s, "communication_logs", {"id": "l", "request_id": r3["id"]}) == "53703" and zip_of(s, "communication_logs", {"id": "l", "individual_id": p1["id"]}) == "55901")
check("location and link: through the location", zip_of(s, "locations", s.get("locations", uid(200))) == "80301" and zip_of(s, "location_links", s.get("location_links", uid(300))) == "80301")
check("an unknown collection or a non-record has no place", zip_of(s, "curriculums", {"id": "z"}) is None and zip_of(s, "venues", None) is None)

print(f"\n{total - len(fails)}/{total} checks passed" + (f"; FAILED: {fails}" if fails else ""))
sys.exit(1 if fails else 0)
