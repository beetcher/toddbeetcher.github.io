#!/usr/bin/env python3
"""Tests for territory at the doors (P-60 / P-65, step 3): a person with limited grants sees and changes only what is in reach, through the
Console door (crud_endpoint.handle_admin), the records door (console.py) and the Discovery door (discovery_door.py).
Run from enjoy_router/:  python3 run_territory_door_tests.py   (-v lists every check). Nothing touches Firebase; Google is a fake verifier."""
import json, pathlib, sys
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from console import handle_console, make_failure_limiter  # noqa: E402
from crud import access_persons_crud as PE, access_roles_crud as RO, classes_service as CS, venues_service as VS  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud_endpoint import handle_admin  # noqa: E402
from discovery_door import handle_discovery  # noqa: E402
from launch_discovery import zip_table  # noqa: E402
from memory_store import MemoryStore  # noqa: E402

START = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)
A, KEY = "user:admin", "k" * 16 + "Z" * 16 + "-test-key-not-real"
fails, total, clock = [], 0, [0]
def tick():
    clock[0] += 5
    return START + timedelta(seconds=clock[0])
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    if not ok or "-v" in sys.argv: print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")

zip_table.set_table({**{z: ["CO", 40.0, -105.0, "X"] for z in ("80301", "80302", "80303", "80501")},
                     **{z: ["WI", 43.0, -89.0, "X"] for z in ("53703", "53202")}, "55901": ["MN", 44.0, -92.0, "X"]})
store = MemoryDocStore("")
def uid(n): return f"{n:08d}-0000-4000-8000-000000000000"
def area(n, kind, st, name, **kw):
    store.create("discovery_areas", uid(n), {"id": uid(n), "kind": kind, "state_code": st, "name": name, "is_active": True, "schema_version": 1, "created_at": "2026-10-01T00:00:00Z", "updated_at": "2026-10-01T00:00:00Z", **kw}); return uid(n)
CO, WI, MN = area(1, "state", "CO", "Colorado"), area(2, "state", "WI", "Wisconsin"), area(3, "state", "MN", "Minnesota")
BOULDER = area(10, "region", "CO", "Boulder", zip_codes=["80301", "80302"])
LONGMONT = area(11, "region", "CO", "Longmont", zip_codes=["80501"])
MADISON = area(12, "region", "WI", "Madison", zip_codes=["53703"])

def venue(name, zip_code, status="active"):
    kw = {"address": {"lines": ["1 Main"], "locality": "X", "region": "XX", "postal_code": zip_code, "country": "US"}} if zip_code else {}
    r = VS.create_with_place(store, {"name": name, "slug": name.lower().replace(" ", "_"), "status": "inactive", "is_public_venue": True}, A, now=tick(), **kw)
    assert r.ok, r.problems
    vid = r.data["id"]
    if status == "active" and zip_code:
        assert VS.update(store, vid, {"status": "active"}, A, now=tick()).ok
    return vid
vB, vB2, vL, vU, vW, vN = (venue("Boulder Hall", "80301"), venue("Boulder Two", "80302"), venue("Longmont Hall", "80501"),
                           venue("Unclaimed Hall", "80303"), venue("Madison Hall", "53703"), venue("No Place Hall", None))
def klass(title, vid):
    r = CS.create(store, {"title": title, "slug": title.lower().replace(" ", "_"), "class_type": "workshop", "program_slug": "launch", "status": "scheduled",
                          "starts_at": "2026-12-01T17:00:00Z", "time_zone": "America/Denver", "duration_minutes": 60, "venue_id": vid, "is_public": False,
                          "is_venue_confirmed": False, "capacity_minimum": 2, "capacity_target": 8, "capacity_max": 10}, A, now=tick())
    assert r.ok, r.problems; return r.data["id"]
cB, cL, cW = klass("Boulder Class", vB), klass("Longmont Class", vL), klass("Madison Class", vW)
def raw(coll, n, **kw):
    store.create(coll, uid(n), {"id": uid(n), "schema_version": 1, "created_at": "2026-10-01T00:00:00Z", "updated_at": "2026-10-01T00:00:00Z", **kw}); return uid(n)
rB, rL, rU, rW, rNone, rClassL = (raw("registration_requests", 200, postal_code="80301", first_name="B", registration_type="private", attendee_count=1),
    raw("registration_requests", 201, postal_code="80501", first_name="L", registration_type="private", attendee_count=1),
    raw("registration_requests", 202, postal_code="80303", first_name="U", registration_type="private", attendee_count=1),
    raw("registration_requests", 203, postal_code="53703", first_name="W", registration_type="private", attendee_count=1),
    raw("registration_requests", 204, first_name="None", registration_type="private", attendee_count=1),
    raw("registration_requests", 205, scheduled_class_id=cL, first_name="ClassL", registration_type="class", attendee_count=1))
aB, aL = raw("registration_assignments", 210, request_id=rB, scheduled_class_id=cB, status="registered"), raw("registration_assignments", 211, request_id=rL, scheduled_class_id=cL, status="registered")
tB, tL = raw("attendances", 220, scheduled_class_id=cB, individual_id=uid(231)), raw("attendances", 221, scheduled_class_id=cL, individual_id=uid(232))
pB, pL = raw("individuals", 231, display_name="Boulder Person", status="active"), raw("individuals", 232, display_name="Longmont Person", status="active")
def home(n, person, zip_code):
    raw("locations", n, status="active", name="Home", addresses=[{"usage": "civic", "postal_code": zip_code, "is_primary": True, "country": "US"}])
    raw("location_links", n + 100, subject_type="individual", subject_id=person, location_id=uid(n), relationship="resides_at", status="active", is_primary=True)
home(240, pB, "80301"); home(241, pL, "80501")
irB, irL = raw("instructor_rosters", 250, individual_id=pB, status="active"), raw("instructor_rosters", 251, individual_id=pL, status="active")
orgX = raw("organizations", 260, name="An Organization", status="active")
mB, mL = raw("communication_logs", 270, scheduled_class_id=cB, kind="x"), raw("communication_logs", 271, scheduled_class_id=cL, kind="x")

# ---- people at the door
TERR = ["edit_venues", "activate_venues", "manage_requests", "manage_classes", "manage_instructors", "edit_people", "edit_places", "view_messages"]
member = RO.create(store, {"key": "member", "label": "Member", "is_super_admin": False, "capabilities": ["view_console", "view_spend"]}, A, now=tick()).data
sup = RO.create(store, {"key": "super_admin", "label": "Super", "is_super_admin": True}, A, now=tick()).data
disco_role = RO.create(store, {"key": "runner", "label": "Runner", "is_super_admin": False, "capabilities": ["view_console", "run_discovery", "edit_discovery_settings"]}, A, now=tick()).data
class Fake:
    def __init__(self): self.tokens = {}
    def verify(self, t): return dict(self.tokens[t])
V = Fake()
def tok(n): return f"header{n:03d}.payload{n:03d}.signature{n:03d}" + "x" * 20
def who(n, email, role=member, grants=None):
    r = PE.create(store, {"email": email, "role_id": role["id"], **({"grants": grants} if grants is not None else {})}, A, now=tick()); assert r.ok, r.problems
    V.tokens[tok(n)] = {"uid": f"uid-{n}", "email": email, "email_verified": True, "provider": "google.com", "name": email}
def reg(ids, caps, st="CO", **kw): return {"kind": "regions", "state_code": st, "region_ids": ids, "capabilities": caps, **kw}
who(1, "todd@x.com", sup)
who(2, "boulder@x.com", grants=[reg([BOULDER], TERR)])
who(3, "two@x.com", grants=[reg([BOULDER], ["edit_venues"]), reg([LONGMONT], ["manage_requests"])])
who(4, "co@x.com", grants=[{"kind": "state", "state_code": "CO"}])
who(5, "wi@x.com", grants=[{"kind": "state", "state_code": "WI"}])
who(6, "nobody@x.com", grants=[])
who(7, "regions@x.com", grants=[reg([BOULDER], ["edit_regions"])])
who(8, "us@x.com", grants=[{"kind": "all"}])
who(9, "disco@x.com", disco_role, grants=[reg([BOULDER], ["run_discovery"])])
who(10, "runner@x.com", grants=[reg([BOULDER], ["run_discovery"])])

def call(n, collection, op, args=None, key=False):
    auth = f"Bearer {KEY}" if key else f"Bearer {tok(n)}"
    r = handle_admin("POST", auth, json.dumps({"collection": collection, "op": op, "args": args or {}}).encode(), KEY, "v", store, make_failure_limiter(), tick(), verifier=V)
    return r.status, r.body
def ids(n, collection, **args):
    st, b = call(n, collection, "list", args)
    return (st, sorted(r["id"] for r in b["data"]["records"])) if st == 200 else (st, None)
def code(n, collection, op, args=None): return call(n, collection, op, args)[0]

# ================================================================ venues: reading
check("venues: the super admin sees all six", ids(1, "venues")[1] == sorted([vB, vB2, vL, vU, vW, vN]))
check("venues: a Boulder head sees only Boulder's two", ids(2, "venues") == (200, sorted([vB, vB2])))
check("venues: a head of two regions sees the venues of both (looking), not others", ids(3, "venues") == (200, sorted([vB, vB2, vL])))
check("venues: the Colorado state owner sees every Colorado venue, including the unclaimed ZIP, but not Wisconsin or the one with no place", ids(4, "venues") == (200, sorted([vB, vB2, vL, vU])))
check("venues: the Wisconsin state owner sees only Madison's", ids(5, "venues") == (200, [vW]))
check("venues: a person with no grants sees nothing (empty list, not everything)", ids(6, "venues") == (200, []))
check("venues: an all-US person sees everything, including a venue with no place", ids(8, "venues")[1] == sorted([vB, vB2, vL, vU, vW, vN]))
check("venue get: in reach", code(2, "venues", "get", {"id": vB}) == 200)
check("venue get: out of reach is refused (403)", code(2, "venues", "get", {"id": vL}) == 403 and code(2, "venues", "get", {"id": vN}) == 403 and code(2, "venues", "get", {"id": vU}) == 403)
check("venue get: a person with no grants is refused", code(6, "venues", "get", {"id": vB}) == 403)
check("venue get with expand: in reach ok, out of reach refused", code(2, "venues", "get", {"id": vB, "expand": True}) == 200 and code(2, "venues", "get", {"id": vL, "expand": True}) == 403)
st, b = call(2, "venues", "list", {"expand": True}); check("venue list with expand is filtered too", st == 200 and sorted(r["id"] for r in b["data"]["records"]) == sorted([vB, vB2]))

# ================================================================ venues: writing, capability by region
def upd(n, vid, **changes): return code(n, "venues", "update", {"id": vid, "changes": changes})
check("venue update: in reach with edit_venues", upd(2, vB, description="Updated by the Boulder head") == 200)
check("venue update: really saved", store.get("venues", vB)["description"] == "Updated by the Boulder head")
check("venue update: a venue in another region is refused", upd(2, vL, description="Hacked") == 403 and store.get("venues", vL).get("description") != "Hacked")
check("venue update: a venue in the same state but no region of theirs is refused", upd(2, vU, description="Hacked") == 403)
check("venue update: a venue with no place is refused for a limited person", upd(2, vN, description="Hacked") == 403)
check("venue update: capabilities are per region: edit in Boulder, but only requests in Longmont", upd(3, vB, description="Two edits Boulder") == 200 and upd(3, vL, description="Two edits Longmont") == 403)
check("venue status: switching on/off needs activate_venues in that region", upd(3, vB, status="inactive") == 403 and upd(2, vB, status="inactive") == 200 and upd(2, vB, status="active") == 200)
check("venue update: a state owner can edit anywhere in the state, the unclaimed ZIP included", upd(4, vU, description="State owner") == 200 and upd(4, vL, description="State owner") == 200)
check("venue update: a state owner cannot touch another state", upd(4, vW, description="Hacked") == 403 and upd(5, vB, description="Hacked") == 403)
check("venue update: an all-US person can edit anywhere, a venue with no place too", upd(8, vN, description="All") == 200 and upd(8, vW, description="All") == 200)
check("venue update: a person with no grants cannot", upd(6, vB, description="x") == 403)
check("venue delete stays the super admin's, whoever has the grants", code(4, "venues", "soft_delete", {"id": vB}) == 403 and code(8, "venues", "soft_delete", {"id": vB}) == 403)
check("venue update of an id that does not exist is a plain not-found, not a leak", code(2, "venues", "update", {"id": uid(999), "changes": {"description": "x"}}) == 404)

NEW = lambda zip_code: {"data": {"name": "New Hall", "slug": "new_hall_" + str(zip_code), "status": "inactive", "is_public_venue": True},
                        "address": {"lines": ["9 Elm"], "locality": "X", "region": "XX", "postal_code": zip_code, "country": "US"}}
check("venue create_with_place: an address in reach is allowed", code(2, "venues", "create_with_place", NEW("80302")) == 200)
check("venue create_with_place: an address outside reach is refused", code(2, "venues", "create_with_place", NEW("80501")) == 403 and code(2, "venues", "create_with_place", NEW("53703")) == 403)
check("venue create_with_place: an address with no ZIP is refused for a limited person", code(2, "venues", "create_with_place", {"data": {"name": "N", "slug": "n_1", "status": "inactive", "is_public_venue": True}, "address": {"lines": ["9 Elm"], "country": "US"}}) == 403)
check("venue create (no place at all) is refused for a limited person", code(2, "venues", "create", {"data": {"name": "N", "slug": "n_2", "status": "inactive", "is_public_venue": True}}) == 403)
check("venue create_with_place: a person with no write capability anywhere is refused", code(6, "venues", "create_with_place", NEW("80302")) == 403)
check("venue create_with_place: a state owner may add in the whole state", code(4, "venues", "create_with_place", NEW("80303")) == 200)
check("venue set_place: both the old and the new place must be in reach", code(2, "venues", "set_place", {"id": vB2, "address": NEW("80301")["address"]}) == 200
      and code(2, "venues", "set_place", {"id": vB2, "address": NEW("80501")["address"]}) == 403 and code(2, "venues", "set_place", {"id": vL, "address": NEW("80301")["address"]}) == 403)

# ================================================================ classes
check("classes: a Boulder head sees only the Boulder class", ids(2, "scheduled_classes") == (200, [cB]))
check("classes: the head of two regions sees both Colorado classes", ids(3, "scheduled_classes") == (200, sorted([cB, cL])))
check("class update: in reach with manage_classes", code(2, "scheduled_classes", "update", {"id": cB, "changes": {"description": "ok"}}) == 200)
check("class update: out of reach refused", code(2, "scheduled_classes", "update", {"id": cL, "changes": {"description": "x"}}) == 403)
check("class update: moving a class to a venue outside reach is refused", code(2, "scheduled_classes", "update", {"id": cB, "changes": {"venue_id": vL}}) == 403 and store.get("scheduled_classes", cB)["venue_id"] == vB)
check("class update: moving it to another venue in reach is allowed", code(2, "scheduled_classes", "update", {"id": cB, "changes": {"venue_id": vB2}}) == 200)
check("class update: the head of two regions has no manage_classes anywhere", code(3, "scheduled_classes", "update", {"id": cB, "changes": {"description": "x"}}) == 403)
check("class get: out of reach refused", code(2, "scheduled_classes", "get", {"id": cL}) == 403 and code(2, "scheduled_classes", "get", {"id": cB}) == 200)

# ================================================================ registration requests: the records door and the queue
def records(n=None, key=None, verifier=V):
    auth = f"Bearer {key}" if key else f"Bearer {tok(n)}"
    m = MemoryStore([])
    for rid, zip_code in ((rB, "80301"), (rL, "80501"), (rU, "80303"), (rW, "53703"), (rNone, None), (rClassL, None)):
        d = dict(store.get("registration_requests", rid)); d["created_at"] = f"2026-10-0{1 + len(m.requests)}T00:00:00Z"; m.requests.append(d)
    r = handle_console("GET", auth, {}, KEY, "v", m, make_failure_limiter(), tick(), verifier=verifier, access_store=store)
    return r.status, sorted(x["id"] for x in r.body["data"]["records"]) if r.status == 200 else None
check("records: the super admin sees all six requests", records(1)[1] == sorted([rB, rL, rU, rW, rNone, rClassL]))
check("records: the key sees all six", records(key=KEY)[1] == sorted([rB, rL, rU, rW, rNone, rClassL]))
check("records: a Boulder head sees only the Boulder request (P-65)", records(2) == (200, [rB]))
check("records: ... never the request with no ZIP at all", rNone not in records(2)[1] and rNone not in records(4)[1])
check("records: a Colorado state owner sees every Colorado request, the unclaimed ZIP and the class request included", records(4)[1] == sorted([rB, rL, rU, rClassL]))
check("records: a Wisconsin state owner sees only Wisconsin's", records(5) == (200, [rW]))
check("records: the all-US person sees everything", len(records(8)[1]) == 6)
check("records: a person with grants but no request capability is refused (403)", records(6)[0] == 403 and records(7)[0] == 403)
check("records: the head of two regions sees the Longmont request (manage_requests there), not Boulder's (no request right there)", records(3) == (200, sorted([rL, rClassL])))

def queue(n):
    st, b = call(n, "registration_assignments", "queue")
    return (st, sorted(i["request_id"] for i in b["data"]["items"]), b["data"]["counts"]) if st == 200 else (st, None, None)
q = queue(1)
check("queue: the super admin sees every request", q[0] == 200 and len(q[1]) == 6, q[:2])
q = queue(2)
check("queue: a Boulder head sees only the Boulder request, and the counts are of what is shown", q[1] == [rB] and sum(q[2].values()) == 1, q)
check("queue: a Colorado state owner sees four", queue(4)[1] == sorted([rB, rL, rU, rClassL]))
check("queue: a person with no grants is refused", queue(6)[0] == 403)
check("suggest: for a request in reach ok, out of reach refused", code(2, "registration_assignments", "suggest", {"request_id": rB}) in (200, 404) and code(2, "registration_assignments", "suggest", {"request_id": rL}) == 403)
check("assignments: a Boulder head lists only the Boulder assignment", ids(2, "registration_assignments") == (200, [aB]))

# ================================================================ attendances, rosters, people, messages, organizations
check("assignments: creating one needs the request in reach", code(2, "registration_assignments", "create", {"data": {"request_id": rL, "scheduled_class_id": cB, "status": "registered", "attendee_count": 1}}) == 403
      and code(2, "registration_assignments", "create", {"data": {"request_id": rB, "scheduled_class_id": cB, "status": "registered", "attendee_count": 1}}) != 403)
check("messages: a limited person (even a state owner) cannot write a log entry from scratch", code(4, "communication_logs", "create", {"data": {"kind": "x"}}) == 403)
check("attendances: a Boulder head sees only the Boulder class's", ids(2, "attendances") == (200, [tB]))
check("attendance get: out of reach refused", code(2, "attendances", "get", {"id": tL}) == 403 and code(2, "attendances", "get", {"id": tB}) == 200)
check("attendance update: out of reach refused", code(2, "attendances", "update", {"id": tL, "changes": {"notes": "x"}}) == 403)
check("attendance assign into a class out of reach is refused", code(2, "attendances", "assign", {"data": {"scheduled_class_id": cL, "role": "student", "individual_id": pB}}) == 403)
check("attendance assign_request: both the request and the class must be in reach", code(2, "attendances", "assign_request", {"data": {"request_id": rL, "scheduled_class_id": cB}}) == 403
      and code(2, "attendances", "assign_request", {"data": {"request_id": rB, "scheduled_class_id": cL}}) == 403)
check("attendance delete_request: a request out of reach is refused", code(2, "attendances", "delete_request", {"id": rL}) == 403 and code(2, "attendances", "delete_request", {"id": rNone}) == 403)
check("attendance delete_request: a request in reach goes through to the handler", code(2, "attendances", "delete_request", {"id": rB}) in (200, 400, 409))
check("instructor roster: a Boulder head sees only the instructor who lives in Boulder", ids(2, "instructor_rosters") == (200, [irB]))
check("instructor roster: update out of reach refused, creating one for a new person refused", code(2, "instructor_rosters", "update", {"id": irL, "changes": {"notes": "x"}}) == 403
      and code(2, "instructor_rosters", "create_with_person", {"data": {}, "person": {"given_name": "N", "family_name": "P"}}) == 403)
check("people: a Boulder head sees only the person who lives in Boulder", ids(2, "individuals") == (200, [pB]))
check("people: merging or erasing people is for unlimited people only; creating one needs edit_people in some grant (a Boulder head may, the venues-only person may not)", code(2, "individuals", "create", {"data": {}}) != 403 and code(7, "individuals", "create", {"data": {}}) == 403 and code(3, "individuals", "create", {"data": {}}) == 403 and code(2, "individuals", "merge", {"survivor_id": pB, "duplicate_id": pL, "reason": "x"}) == 403)
check("messages: a Boulder head sees only the Boulder class's message", ids(2, "communication_logs") == (200, [mB]))
check("messages: mark handled out of reach is refused", code(2, "communication_logs", "mark_handled", {"id": mL}) == 403)
check("organizations: no place of their own, so a limited person is refused, the all-US person and super admin are not", code(2, "organizations", "list") == 403 and code(4, "organizations", "list") == 403
      and code(8, "organizations", "list") == 200 and code(1, "organizations", "list") == 200)
check("locations: a head saves a place only in reach", code(2, "locations", "create", {"data": {"name": "P", "kind": "site", "addresses": [{"usage": "civic", "lines": ["1 Main"], "locality": "X", "region": "XX", "postal_code": "80301", "country": "US", "is_primary": True}]}}) == 200
      and code(2, "locations", "create", {"data": {"name": "P", "kind": "site", "addresses": [{"usage": "civic", "lines": ["1 Main"], "locality": "X", "region": "XX", "postal_code": "80501", "country": "US", "is_primary": True}]}}) == 403
      and code(2, "locations", "create", {"data": {"name": "P", "kind": "site"}}) == 403)

# ================================================================ regions and states themselves
def area_ids(n): return ids(n, "discovery_areas")
check("areas: the super admin sees all six", len(area_ids(1)[1]) == 6)
check("areas: a Boulder head sees Colorado's state record and their own region, not Longmont or other states", area_ids(2) == (200, sorted([CO, BOULDER])))
check("areas: the head of two regions sees the state and both regions", area_ids(3) == (200, sorted([CO, BOULDER, LONGMONT])))
check("areas: a Colorado state owner sees the state and every region in it", area_ids(4) == (200, sorted([CO, BOULDER, LONGMONT])))
check("areas: a person with no grants sees none", area_ids(6) == (200, []))
check("areas: the all-US person sees all six", len(area_ids(8)[1]) == 6)
check("area get: out of reach refused, in reach ok", code(2, "discovery_areas", "get", {"id": LONGMONT}) == 403 and code(2, "discovery_areas", "get", {"id": BOULDER}) == 200)
NEWREG = lambda st, name, zips: {"data": {"kind": "region", "state_code": st, "name": name, "zip_codes": zips, "is_active": True}}
check("areas: edit_regions on a region lets that person edit the region", code(7, "discovery_areas", "update", {"id": BOULDER, "changes": {"zip_codes": ["80301", "80302", "80303"]}}) == 200)
check("areas: ... but not another region of the same state, and not another state", code(7, "discovery_areas", "update", {"id": LONGMONT, "changes": {"name": "Hacked"}}) == 403 and code(7, "discovery_areas", "update", {"id": MADISON, "changes": {"name": "Hacked"}}) == 403)
check("areas: ... and a regions grant does not allow creating a region (only a state grant does)", code(7, "discovery_areas", "create", NEWREG("CO", "Newtown", ["80301"])) == 403)
check("areas: a state owner can create a region in their state", code(4, "discovery_areas", "create", NEWREG("CO", "Louisville", ["80303"])) == 200)
check("areas: ... not in another state", code(4, "discovery_areas", "create", NEWREG("WI", "Elsewhere", ["53202"])) == 403)
check("areas: ... and cannot create a state record, even for their own state", code(4, "discovery_areas", "create", {"data": {"kind": "state", "state_code": "CO", "name": "Colorado again", "is_active": True}}) == 403)
check("areas: an update to an area that does not exist is a plain not-found", code(4, "discovery_areas", "update", {"id": uid(998), "changes": {"name": "x"}}) == 404)
check("areas: ... and cannot edit or delete the state record itself", code(4, "discovery_areas", "update", {"id": CO, "changes": {"name": "Hacked"}}) == 403 and code(4, "discovery_areas", "soft_delete", {"id": CO}) == 403)
check("areas: a state owner can edit any region of their state", code(4, "discovery_areas", "update", {"id": LONGMONT, "changes": {"name": "Longmont area"}}) == 200 and code(4, "discovery_areas", "update", {"id": MADISON, "changes": {"name": "x"}}) == 403)
check("areas: a Boulder head without edit_regions cannot edit", code(2, "discovery_areas", "update", {"id": BOULDER, "changes": {"name": "x"}}) == 403)
check("areas: a person with the global Discovery settings capability is not held back", code(9, "discovery_areas", "update", {"id": MADISON, "changes": {"name": "Madison area"}}) == 200)

# ================================================================ what the Console is told about the person
st, b = call(2, "venues", "list", {}); me = handle_admin("POST", f"Bearer {tok(3)}", json.dumps({"op": "me"}).encode(), KEY, "v", store, make_failure_limiter(), tick(), verifier=V).body["data"]
check("me: lists the grants, with the capabilities per region", len(me["grants"]) == 2 and me["grants"][0]["region_ids"] == [BOULDER] and me["grants"][0]["capabilities"] == ["edit_venues"]
      and me["grants"][1]["capabilities"] == ["manage_requests"] and me["unlimited"] is False)
check("me: capabilities are the global ones plus every capability any grant holds", set(me["capabilities"]) == {"view_console", "view_spend", "edit_venues", "manage_requests"}, me["capabilities"])
me1 = handle_admin("POST", f"Bearer {tok(1)}", json.dumps({"op": "me"}).encode(), KEY, "v", store, make_failure_limiter(), tick(), verifier=V).body["data"]
check("me: a super admin is unlimited", me1["unlimited"] is True and me1["grants"][0]["kind"] == "all")

# ================================================================ the Discovery door
class Engine:
    def __init__(self): self.calls = []
    def quote(self, rq): self.calls.append(("quote", rq.area_ids)); return type("R", (), {"ok": True, "data": {"ok": True}})()
    def plan(self, rq, actor): self.calls.append(("plan", rq.area_ids)); return type("R", (), {"ok": True, "data": {"run_id": "r"}})()
    def stop(self, run_id, actor): self.calls.append(("stop", run_id)); return type("R", (), {"ok": True, "data": {"ok": True}})()
eng = Engine()
def disc(n, op, args=None, key=False):
    auth = f"Bearer {KEY}" if key else f"Bearer {tok(n)}"
    r = handle_discovery("POST", auth, json.dumps({"op": op, "args": args or {}}).encode(), KEY, "v", store, eng, {}, make_failure_limiter(), tick(), verifier=V)
    return r.status, r.body
REQ = lambda areas: {"finder_key": "venue", "model_id": "m", "area_ids": areas, "type_keys": ["t"], "max_results": 1, "spend_cap_cents": 1}
check("discovery: quote for a region in reach", disc(9, "quote", REQ([BOULDER]))[0] == 200)
check("discovery: quote for a region outside reach is refused and never reaches the engine", disc(9, "quote", REQ([LONGMONT]))[0] == 403 and ("quote", (LONGMONT,)) not in eng.calls)
check("discovery: a mix of reach and no reach is refused", disc(9, "plan", REQ([BOULDER, LONGMONT]))[0] == 403)
check("discovery: a whole state needs a state grant (the Boulder runner has none)", disc(9, "plan", REQ([CO]))[0] == 403)
run_b = {"id": uid(300), "area_ids": [BOULDER], "created_at": "2026-10-01T00:00:00Z", "finder_key": "venue", "status": "finished"}
run_l = {"id": uid(301), "area_ids": [LONGMONT], "created_at": "2026-10-02T00:00:00Z", "finder_key": "venue", "status": "finished"}
store.create("discovery_runs", run_b["id"], dict(run_b)); store.create("discovery_runs", run_l["id"], dict(run_l))
check("discovery: stopping a run outside reach is refused", disc(9, "stop", {"run_id": run_l["id"]})[0] == 403 and disc(9, "stop", {"run_id": run_b["id"]})[0] == 200)
check("discovery: a runner without the spend capability sees only runs in reach", sorted(r["id"] for r in disc(9, "list_runs")[1]["data"]["records"]) == [run_b["id"]])
check("discovery: ... and cannot read a run outside reach", disc(9, "get_run", {"id": run_l["id"]})[1]["data"].get("area_ids") is None and disc(9, "get_run", {"id": run_b["id"]})[1]["data"]["area_ids"] == [BOULDER])
check("discovery: a head who holds view_spend (transparency) sees every run", sorted(r["id"] for r in disc(3, "list_runs")[1]["data"]["records"]) == sorted([run_b["id"], run_l["id"]]) if disc(3, "list_runs")[0] == 200 else False)
check("discovery: zips (the map) only for a state the person has a grant in, unless they hold the global settings capability", disc(10, "zips", {"state_code": "CO"})[0] == 200
      and disc(10, "zips", {"state_code": "WI"})[0] == 403 and disc(9, "zips", {"state_code": "WI"})[0] == 200)
check("discovery: the super admin is not held back", disc(1, "quote", REQ([MADISON]))[0] == 200 and disc(None, "quote", REQ([MADISON]), key=True)[0] == 200)

# ================================================================ an instructor sees only the classes they teach (P-71)
pT = raw("individuals", 260, display_name="Teaching Person", status="active")
instr_role = RO.create(store, {"key": "instructor", "label": "Instructor", "is_super_admin": False, "capabilities": ["view_console", "manage_classes"]}, A, now=tick()).data
r = PE.create(store, {"email": "teach@x.com", "role_id": instr_role["id"], "grants": [], "individual_id": pT}, A, now=tick()); assert r.ok, r.problems
V.tokens[tok(20)] = {"uid": "uid-20", "email": "teach@x.com", "email_verified": True, "provider": "google.com", "name": "teach@x.com"}
r = PE.create(store, {"email": "plain@x.com", "role_id": instr_role["id"], "grants": []}, A, now=tick()); assert r.ok, r.problems
V.tokens[tok(21)] = {"uid": "uid-21", "email": "plain@x.com", "email_verified": True, "provider": "google.com", "name": "plain@x.com"}
tT = raw("attendances", 222, scheduled_class_id=cL, individual_id=pT, role="instructor")
tS = raw("attendances", 223, scheduled_class_id=cB, individual_id=pT, role="student")
tL2 = raw("attendances", 224, scheduled_class_id=cL, individual_id=uid(232), role="student")
check("own classes: an instructor with no territory sees exactly the class they teach (not the one they only attend)", ids(20, "scheduled_classes") == (200, [cL]))
check("own classes: ...and may open it, but not another class", code(20, "scheduled_classes", "get", {"id": cL}) == 200 and code(20, "scheduled_classes", "get", {"id": cB}) == 403)
check("own classes: ...and sees who is in that class (its roster), no other class's", ids(20, "attendances") == (200, sorted([tT, tL, tL2])))
check("own classes: ...but cannot change anything", code(20, "scheduled_classes", "update", {"id": cL, "changes": {"description": "x"}}) == 403 and code(20, "attendances", "update", {"id": tL2, "changes": {"notes": "x"}}) == 403)
check("own classes: ...and sees no venues, requests or people", ids(20, "venues") == (200, []) and code(20, "individuals", "list") == 403 and code(20, "registration_assignments", "list") == 403)
check("own classes: a signed-in person not linked to anyone sees no classes and no rosters", ids(21, "scheduled_classes") == (200, []) and code(21, "attendances", "list") == 403)
check("own classes: an instructor who stops teaching loses the class", code(1, "attendances", "soft_delete", {"id": tT}) == 200 and ids(20, "scheduled_classes") == (200, []))

# ================================================================ state leads can invite (P-68)
INV = TERR + ["invite_people"]
mgr_role = RO.create(store, {"key": "mgr", "label": "Mgr", "is_super_admin": False, "capabilities": ["view_console", "view_spend", "manage_requests"]}, A, now=tick()).data
rich_role = RO.create(store, {"key": "rich", "label": "Rich", "is_super_admin": False, "capabilities": ["view_console", "manage_curriculums"]}, A, now=tick()).data
who(30, "lead@x.com", mgr_role, grants=[reg([BOULDER, LONGMONT], INV)])
who(31, "bonly@x.com", mgr_role, grants=[reg([BOULDER], INV)])
def add(n, email, role, grants, **kw): return call(n, "access_persons", "create", {"data": {"email": email, "role_id": role["id"], "grants": grants, **kw}})
def pid(email): return next(p["id"] for p in store.query("access_persons", [], limit=500) if p["email"] == email)
check("invite: a person without invite_people anywhere cannot touch the access collections", code(2, "access_persons", "list") == 403 and code(2, "access_roles", "list") == 403)
st, b = add(30, "inv1@x.com", mgr_role, [reg([BOULDER], ["manage_requests", "edit_venues"])]); check("invite: a lead invites someone into one of their regions with capabilities they hold", st == 200)
check("invite: ...the invitation is stamped with who made it", store.get("access_persons", pid("inv1@x.com"))["created_by"] == f"user:{pid('lead@x.com')}")
check("invite: a region outside their territory is refused", add(30, "inv2@x.com", mgr_role, [reg([MADISON], ["manage_requests"], "WI")])[0] == 403 and add(31, "inv3@x.com", mgr_role, [reg([LONGMONT], ["manage_requests"])])[0] == 403)
check("invite: a region grant that mixes an outside region is refused", add(31, "inv4@x.com", mgr_role, [reg([BOULDER, LONGMONT], ["manage_requests"])])[0] == 403)
check("invite: a state grant or an all grant is refused", add(30, "inv5@x.com", mgr_role, [{"kind": "state", "state_code": "CO"}])[0] == 403 and add(30, "inv6@x.com", mgr_role, [{"kind": "all"}])[0] == 403)
check("invite: handing on invite_people is refused (no chains)", add(30, "inv7@x.com", mgr_role, [reg([BOULDER], ["invite_people"])])[0] == 403)
check("invite: giving a capability the lead does not hold in that place is refused", add(30, "inv8@x.com", mgr_role, [reg([BOULDER], ["edit_regions"])])[0] == 403 and add(30, "inv8@x.com", mgr_role, [reg([BOULDER], ["edit_venues"])])[0] == 200)
check("invite: roles: a super admin role, or a role with a global power the lead lacks are refused",
      add(30, "inv9@x.com", sup, [])[0] == 403 and add(30, "inv11@x.com", rich_role, [])[0] == 403)
check("invite: a plain role with no territory yet is fine", add(30, "inv12@x.com", mgr_role, [])[0] == 200)
check("invite: the retired scope_region_id is refused", add(30, "inv13@x.com", mgr_role, [], scope_region_id=BOULDER)[0] == 403)
st, b = call(30, "access_persons", "list"); seen = sorted(p["email"] for p in b["data"]["records"])
check("invite: the lead sees the people inside their territory and those they invited, not themselves, other leads or the super admin", "inv1@x.com" in seen and "inv12@x.com" in seen and "boulder@x.com" in seen and "lead@x.com" not in seen and "bonly@x.com" not in seen and "todd@x.com" not in seen and "co@x.com" not in seen and "wi@x.com" not in seen)
check("invite: ...the Boulder-only lead does not see an invitee who holds a Longmont region", "inv1@x.com" in [p["email"] for p in call(31, "access_persons", "list")[1]["data"]["records"]] and "lead@x.com" not in [p["email"] for p in call(31, "access_persons", "list")[1]["data"]["records"]])
check("invite: a person with no territory who someone else invited is not theirs to see or change", "nobody@x.com" not in seen and code(30, "access_persons", "update", {"id": pid("nobody@x.com"), "changes": {"display_name": "x"}}) == 403)
i1 = pid("inv1@x.com")
check("invite: they can change an invitee (name, switch off)", code(30, "access_persons", "update", {"id": i1, "changes": {"display_name": "Inv One"}}) == 200 and code(30, "access_persons", "update", {"id": i1, "changes": {"is_active": False}}) == 200)
check("invite: moving an invitee out of their territory or to a state grant is refused", code(30, "access_persons", "update", {"id": i1, "changes": {"grants": [reg([MADISON], ["manage_requests"], "WI")]}}) == 403 and code(30, "access_persons", "update", {"id": i1, "changes": {"grants": [{"kind": "all"}]}}) == 403)
check("invite: they cannot change a person outside their territory, a state owner, a super admin or themselves",
      code(31, "access_persons", "update", {"id": pid("lead@x.com"), "changes": {"display_name": "x"}}) == 403
      and code(30, "access_persons", "update", {"id": pid("co@x.com"), "changes": {"display_name": "x"}}) == 403
      and code(30, "access_persons", "update", {"id": pid("todd@x.com"), "changes": {"display_name": "x"}}) == 403
      and code(30, "access_persons", "update", {"id": pid("lead@x.com"), "changes": {"display_name": "x"}}) == 403)
check("invite: they cannot remove a person outside their territory, but can remove their invitee", code(30, "access_persons", "soft_delete", {"id": pid("co@x.com")}) == 403 and code(30, "access_persons", "soft_delete", {"id": i1}) == 200)
st, b = call(30, "access_roles", "list"); names = sorted(r["key"] for r in b["data"]["records"])
check("invite: they list only the roles they may hand out", "mgr" in names and "member" in names and "super_admin" not in names and "rich" not in names and "runner" not in names)
check("invite: they cannot write roles", code(30, "access_roles", "create", {"data": {"key": "zz", "label": "Z", "is_super_admin": False, "capabilities": ["view_console"]}}) == 403)
check("invite: the super admin still sees everyone", len(call(1, "access_persons", "list")[1]["data"]["records"]) >= 15 and "lead@x.com" in [p["email"] for p in call(1, "access_persons", "list")[1]["data"]["records"]])

# ================================================================ instructors placed in regions by id (P-66)
def rid_of(n, coll="instructor_rosters"): return ids(n, coll)[1] or []
def put(n, rid, **changes): return code(n, "instructor_rosters", "update", {"id": rid, "changes": changes})
check("instructors: a Boulder head sees Boulder's instructor and not Longmont's", irB in rid_of(2) and irL not in rid_of(2))
check("instructors: a head cannot put someone else's instructor into their own region (they cannot manage that entry at all)", put(2, irL, region_ids=[BOULDER]) == 403 and "region_ids" not in store.get("instructor_rosters", irL))
check("instructors: a regions id that is not a live region is refused: not_found for the super admin, out of reach for a state owner", put(1, irL, region_ids=[uid(999)]) == 400 and put(1, irL, region_ids=[uid(1)]) == 400 and put(4, irL, region_ids=[uid(999)]) == 403)
check("instructors: the Colorado state owner places Longmont's instructor in the Boulder region", put(4, irL, region_ids=[BOULDER]) == 200 and store.get("instructor_rosters", irL)["region_ids"] == [BOULDER])
check("instructors: the Boulder head now sees that instructor too (by region), still not by ZIP", irL in rid_of(2) and irB in rid_of(2))
check("instructors: ...and may manage the entry", put(2, irL, notes="Boulder manager notes") == 200 and store.get("instructor_rosters", irL)["notes"] == "Boulder manager notes")
st, b = call(2, "instructor_rosters", "get", {"id": irL}); check("instructors: get works for an entry placed in their region", st == 200)
check("instructors: a head with edit_venues only (no manage_instructors) in Boulder cannot manage it", put(3, irL, notes="x") == 403 and irL not in rid_of(3))
check("instructors: the head cannot send an entry into a region they do not manage (Longmont, Madison)", put(2, irB, region_ids=[BOULDER, LONGMONT]) == 403 and put(2, irB, region_ids=[MADISON]) == 403)
check("instructors: but may add one of their own regions", put(2, irB, region_ids=[BOULDER]) == 200)
check("instructors: the Wisconsin state owner does not see them", irL not in rid_of(5) and irB not in rid_of(5))
check("instructors: taking the region away takes the head's reach away", put(4, irL, region_ids=None) == 200 and irL not in rid_of(2) and put(2, irL, notes="x") == 403)
check("instructors: the super admin sees both", {irB, irL} <= set(rid_of(1)))

# ================================================================ limits apply AFTER the territory filter (P-70)
fillers = [venue("Aa %03d Longmont" % i, "80501", status="inactive") for i in range(130)]      # 130 venues of another region that sort first
check("limits: the other region's 130 venues are there", ids(8, "venues", limit=200)[1] is not None and len(ids(8, "venues", limit=200)[1]) >= 130)
check("limits: a Boulder head still sees BOTH Boulder venues in a default list (100 others sort first)", {vB, vB2} <= set(ids(2, "venues")[1]), ids(2, "venues"))
check("limits: and none of the other region's", not (set(ids(2, "venues")[1]) & set(fillers)) and vL not in ids(2, "venues")[1])
st, b = call(2, "venues", "list", {"limit": 1}); check("limits: the limit the person asked for is still honoured after filtering", st == 200 and b["data"]["count"] == 1 and len(b["data"]["records"]) == 1)
check("limits: the Colorado state owner asking for 100 gets 100 of the 130+ they can see", len(ids(4, "venues", limit=100)[1]) == 100)
st, b = call(2, "venues", "list", {"limit": 3}); check("limits: a limit of 3 returns at most 3", st == 200 and len(b["data"]["records"]) <= 3)
st, b = call(1, "venues", "list", {"limit": 5}); check("limits: the super admin is cut exactly as before", st == 200 and len(b["data"]["records"]) == 5)
for i in range(120):
    raw("registration_requests", 5000 + i, postal_code="80501", first_name="Fill%d" % i, registration_type="private", attendee_count=1, created_at="2026-11-01T00:%02d:%02dZ" % (i // 60, i % 60))
st, b = call(2, "registration_assignments", "queue", {"limit": 100})
check("limits: the queue is filtered BEFORE it is cut: a Boulder head still sees their own request among 120 newer Longmont ones", st == 200 and rU in [i["request_id"] for i in b["data"]["items"]] and all(not i["request_id"].startswith("0000500") and not i["request_id"].startswith("0000501") for i in b["data"]["items"]), (st, str(b)[:200]))

print(f"\n{total - len(fails)}/{total} checks passed" + (f"; FAILED: {fails}" if fails else ""))
sys.exit(1 if fails else 0)
