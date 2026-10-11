#!/usr/bin/env python3
"""In-memory tests for the CRUD test endpoint (crud_endpoint.py). Run from enjoy_router/: python3 run_crud_endpoint_tests.py"""
import json
import pathlib
import sys
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud_endpoint import handle_admin, handle_crud_test, make_failure_limiter  # noqa: E402

KEY = "k" * 16 + "Z" * 16 + "-test-key-not-real"
NOW = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
EX = json.loads((HERE.parent / "schemas" / "examples" / "venue.examples.json").read_text())["valid"]
# the full example, inactive and without the contact pointers (no such individual exists in this store)
INACTIVE_FULL = {k: v for k, v in EX["active_full_detail"].items() if k not in ("contact_individual_id", "backup_contact_individual_id")}
INACTIVE_FULL["status"] = "inactive"
fails = []


def check(label, ok, detail=""):
    print(f"{'ok  ' if ok else 'FAIL'} {label} {'' if ok else detail}")
    if not ok:
        fails.append(label)


store = MemoryDocStore("test_")
limiter = make_failure_limiter()


def call(body, auth=f"Bearer {KEY}", method="POST", key=KEY, raw=None, lim=None, visitor="v"):
    data = raw if raw is not None else json.dumps(body).encode()
    return handle_crud_test(method, auth, data, key, visitor, store, lim or limiter, NOW)


def op(o, **args):
    return call({"collection": "venues", "op": o, "args": args})


r = call({}, auth="")
check("no key: 401, nothing run", r.status == 401 and not store.data)
r = call({}, auth="Bearer wrong")
check("wrong key: 401", r.status == 401 and r.body["error"]["code"] == "unauthorized")
check("GET refused: 405", call({}, method="GET").status == 405)
check("no admin key configured: fails closed", call({}, key="").status == 401)
check("short admin key: fails closed", call({}, key="short", auth="Bearer short").status == 401)

lim = make_failure_limiter()
for _ in range(10):
    call({}, auth="Bearer wrong", lim=lim, visitor="x")
r = call({}, auth="Bearer wrong", lim=lim, visitor="x")
check("11th wrong key: 429 with Retry-After", r.status == 429 and "Retry-After" in r.headers)
r = call({}, lim=lim, visitor="x")
check("blocked visitor is refused even with the right key", r.status == 429)

check("bad JSON: 400", call(None, raw=b"{nope").status == 400)
check("not an object: 400", call(["x"]).status == 400)
check("unknown collection: 400", call({"collection": "people", "op": "get", "args": {}}).status == 400)
check("unknown op: 400", call({"collection": "venues", "op": "drop", "args": {}}).status == 400)
r = op("get")
check("missing arg named: 400", r.status == 400 and "id" in r.body["error"]["message"])
r = op("soft_delete", id="x", extra=1)
check("extra arg refused: 400", r.status == 400 and "extra" in r.body["error"]["message"])
check("oversized body: 413", call(None, raw=b"x" * 100_001).status == 413)
check("nothing written by refused calls", not store.data)

r = op("create", data=INACTIVE_FULL)
check("create: 200 with record", r.status == 200 and r.body["ok"] and r.body["data"]["created_by"] == "system:crud_test")
vid = r.body["data"]["id"]
check("stored only under the test_ prefix", list(store.data) == ["test_venues"])
r = op("create", data=INACTIVE_FULL)
check("duplicate slug: 400 with problem", r.status == 400 and r.body["error"]["problems"] == [{"field": "slug", "issue": "duplicate"}])
r = op("create", data={"name": "x"})
check("invalid: 400, problems name fields only", r.status == 400 and all(set(p) == {"field", "issue"} for p in r.body["error"]["problems"]))
check("get: 200", op("get", id=vid).status == 200)
check("get missing: 404", op("get", id="11111111-1111-4111-8111-111111111111").status == 404)
r = op("update", id=vid, changes={"name": "Renamed"})
check("update: 200 changed name", r.status == 200 and r.body["data"]["changed"] == ["name"])
r = op("update", id=vid, changes={"name": "Again"}, expected_updated_at="2020-01-01T00:00:00Z")
check("stale update: 409 conflict", r.status == 409 and r.body["error"]["code"] == "conflict")
r = op("list")
check("list: 200 count 1", r.status == 200 and r.body["data"]["count"] == 1)
r = op("list", filters={"website_url": "x"})
check("unsupported list: 400", r.status == 400)
check("set_review_summary: 200", op("set_review_summary", id=vid, review_count=2, average_rating=4).status == 200)
check("soft_delete: 200", op("soft_delete", id=vid).status == 200)
check("soft_delete again: 404", op("soft_delete", id=vid).status == 404)
check("no-store on success", op("list").headers.get("Cache-Control") == "no-store")
blob = json.dumps(call({}, auth="Bearer wrong").body)
check("error body never contains the key", KEY not in blob)

# ---------------------------------------------------------------------------
# The admin door (the Console): real collections, only list / get / create
# ---------------------------------------------------------------------------
astore = MemoryDocStore("")
alimiter = make_failure_limiter()


def acall(body, auth=f"Bearer {KEY}", method="POST", key=KEY, lim=None):
    return handle_admin(method, auth, json.dumps(body).encode(), key, "v", astore, lim or alimiter, NOW)


def aop(o, **args):
    return acall({"collection": "venues", "op": o, "args": args})


check("admin: no key 401", acall({}, auth="").status == 401)
check("admin: wrong key 401", acall({}, auth="Bearer nope").status == 401)
check("admin: fails closed without a configured key", acall({}, key="").status == 401)
check("admin: GET refused", acall({}, method="GET").status == 405)
r = aop("create", data={"name": "Admin Test", "slug": "admin_test", "status": "inactive", "is_public_venue": True})
check("admin: create 200, actor user:admin", r.status == 200 and r.body["data"]["created_by"] == "user:admin")
aid = r.body["data"]["id"]
check("admin: record is in the REAL collection, not test_", list(astore.data) == ["venues"])
check("admin: get 200", aop("get", id=aid).status == 200)
r = aop("list", filters={"status": "inactive"})
check("admin: list with filter 200", r.status == 200 and r.body["data"]["count"] == 1)
check("admin: update 200", aop("update", id=aid, changes={"name": "Admin Renamed"}).status == 200)
check("admin: update stamped user:admin", astore.data["venues"][aid]["name"] == "Admin Renamed" and astore.data["venues"][aid]["updated_by"] == "user:admin")
r = aop("update", id=aid, changes={"name": "X"}, expected_updated_at="2020-01-01T00:00:00Z")
check("admin: stale update 409", r.status == 409 and astore.data["venues"][aid]["name"] == "Admin Renamed")
r = aop("update", id=aid, changes={"slug": "other_slug"})
check("admin: slug change refused 400 immutable", r.status == 400 and r.body["error"]["problems"] == [{"field": "slug", "issue": "immutable"}])
r = aop("update", id=aid, changes={"status": "active"})
check("admin: activation without a place refused, names status:place_required", r.status == 400 and r.body["error"]["problems"] == [{"field": "status", "issue": "place_required"}] and astore.data["venues"][aid]["status"] == "inactive")
r = aop("update", id=aid, changes={"website_url": "https://example.com", "phone": "+13035550101"})
check("admin: several simple fields in one update 200", r.status == 200 and astore.data["venues"][aid]["website_url"] == "https://example.com")
r = aop("update", id=aid, changes={"website_url": None})
check("admin: null removes an optional field", r.status == 200 and "website_url" not in astore.data["venues"][aid])
check("admin: update unknown id 404", aop("update", id="11111111-1111-4111-8111-111111111111", changes={"name": "X"}).status == 404)
check("admin: update with wrong key 401", acall({"collection": "venues", "op": "update", "args": {"id": aid, "changes": {"name": "Z"}}}, auth="Bearer nope").status == 401)
check("admin: set_review_summary is not enabled (server-only)", aop("set_review_summary", id=aid, review_count=1, average_rating=5).status == 400)
r = aop("soft_delete", id=aid)
check("admin: soft_delete 200", r.status == 200 and "deleted_at" in astore.data["venues"][aid] and astore.data["venues"][aid]["deleted_by"] == "user:admin")
check("admin: deleted venue is gone from list", aop("list").body["data"]["count"] == 0)
check("admin: deleted venue get 404", aop("get", id=aid).status == 404)
check("admin: delete twice 404", aop("soft_delete", id=aid).status == 404)
check("admin: the record is kept, not removed", aid in astore.data["venues"])
check("admin: unknown op still 400", aop("drop").status == 400)
check("admin: refusal for bad data names fields", aop("create", data={"name": "x"}).body["error"]["problems"] != [])
check("test door still allows update", op("update", id=vid, changes={"name": "Back"}).status in (200, 404))
check("admin store and test store are separate", "venues" not in store.data)


# ---------------------------------------------------------------------------
# Scheduled classes through the admin door, with the venue rules and guards
# ---------------------------------------------------------------------------
def cop(o, **args):
    return acall({"collection": "scheduled_classes", "op": o, "args": args})


import uuid  # noqa: E402


def active_venue(slug, name, rooms):
    """An active venue the way the endpoint requires it: created inactive, linked to a place, then activated."""
    who = acall({"collection": "individuals", "op": "create", "args": {"data": {"given_name": "Pat"}}}).body["data"]["id"]
    vid = aop("create", data={"name": name, "slug": slug, "status": "inactive", "is_public_venue": True}).body["data"]["id"]
    loc = acall({"collection": "locations", "op": "create", "args": {"data": {"name": name, "kind": "site", "addresses": [
        {"usage": "civic", "street": "1 St", "locality": "Boulder", "region": "CO", "postal_code": "80302", "country": "US"}]}}}).body["data"]["id"]
    acall({"collection": "location_links", "op": "create", "args": {"data": {
        "subject_type": "venue", "subject_id": vid, "location_id": loc, "relationship": "operates_at"}}})
    return aop("update", id=vid, changes={"email": "p@example.com", "contact_individual_id": who, "is_accessible": True,
                                          "allows_minors": True, "allows_animals": False, "rooms": rooms, "status": "active"}), vid


r, hid = active_venue("hall", "Hall", [{"label": "Main room", "max_occupancy": 20}])
check("admin classes: venue for the class created and activated", r.status == 200, str(r.body))
CL = {"title": "Intro", "slug": "intro", "class_type": "workshop", "program_slug": "launch", "status": "identified", "is_public": False,
      "capacity_minimum": 6, "capacity_target": 10, "capacity_max": 15}
r = cop("create", data=CL)
check("admin classes: create 200 in the real collection", r.status == 200 and r.body["data"]["created_by"] == "user:admin" and "scheduled_classes" in astore.data, str(r.body))
cid = r.body["data"]["id"]
check("admin classes: counts start at zero", all(r.body["data"][f] == 0 for f in ("registered_count", "waitlist_count", "attended_count", "review_count")))
r = cop("update", id=cid, changes={"status": "scheduled", "starts_at": "2026-11-21T01:00:00Z", "time_zone": "America/Denver", "duration_minutes": 120,
                                   "venue_id": hid, "venue_room_label": "Main room", "is_venue_confirmed": False})
check("admin classes: schedule at an active venue 200", r.status == 200, str(r.body))
r = cop("update", id=cid, changes={"venue_room_label": "Attic"})
check("admin classes: unknown room 400 names the field", r.status == 400 and r.body["error"]["problems"] == [{"field": "venue_room_label", "issue": "not_found"}])
r = cop("update", id=cid, changes={"capacity_max": 25})
check("admin classes: capacity above the room is allowed (no occupancy rule)", r.status == 200)
r = aop("soft_delete", id=hid)
check("admin venues: delete blocked by a live class: 409 with id:in_use", r.status == 409 and r.body["error"]["problems"] == [{"field": "id", "issue": "in_use"}] and "deleted_at" not in astore.data["venues"][hid])
r = aop("update", id=hid, changes={"rooms": [{"label": "Hall room", "max_occupancy": 20}]})
check("admin venues: renaming a used room 400 rooms:in_use", r.status == 400 and r.body["error"]["problems"] == [{"field": "rooms", "issue": "in_use"}])
r = cop("list", filters={"venue_id": hid})
check("admin classes: list by venue", r.status == 200 and r.body["data"]["count"] == 1)
r = cop("list", filters={"status": "scheduled"})
check("admin classes: list by status", r.status == 200 and r.body["data"]["count"] == 1)
check("admin classes: set_review_summary not enabled", cop("set_review_summary", id=cid, review_count=1, average_rating=5).status == 400)
check("admin classes: delete 200", cop("soft_delete", id=cid).status == 200 and "deleted_at" in astore.data["scheduled_classes"][cid])
check("admin venues: delete allowed once the class is gone", aop("soft_delete", id=hid).status == 200)
check("admin classes: bad data names fields only", all(set(p) == {"field", "issue"} for p in cop("create", data={"title": "x"}).body["error"]["problems"]))
r = call({"collection": "scheduled_classes", "op": "create", "args": {"data": CL}})
check("test door: classes go to test_scheduled_classes only", r.status == 200 and "test_scheduled_classes" in store.data and list(astore.data).count("test_scheduled_classes") == 0)

# ---------------------------------------------------------------------------
# Registration assignments through the admin door: auto decision, suggest, queue, guards
# ---------------------------------------------------------------------------
def xop(o, **args):
    return acall({"collection": "registration_assignments", "op": o, "args": args})


r, h2 = active_venue("hall2", "Hall 2", [{"label": "Main room", "max_occupancy": 20}])
r = cop("create", data={**CL, "slug": "enrolling_one", "title": "Enrolling one", "status": "enrolling", "starts_at": "2026-11-21T01:00:00Z",
                        "time_zone": "America/Denver", "duration_minutes": 120, "venue_id": h2, "is_venue_confirmed": True,
                        "price_cents": 5000, "price_basis": "per_person", "capacity_minimum": 2, "capacity_target": 3, "capacity_max": 4})
check("admin assignments: an enrolling class to assign into", r.status == 200, str(r.body))
ecid = r.body["data"]["id"]
rq1, rq2, rq3 = (str(uuid.uuid4()) for _ in range(3))
for i, (rid, seats) in enumerate(((rq1, 2), (rq2, 2), (rq3, 1))):
    astore.data.setdefault("registration_requests", {})[rid] = {
        "id": rid, "registration_type": "class", "attendee_count": seats, "scheduled_class_id": ecid, "confirmation_number": f"ICDT-AAAA{i}{i}",
        "first_name": "Ann", "last_name": f"T{i}", "created_at": f"2026-10-09T12:00:0{i}Z"}
r = xop("suggest", request_id=rq1)
check("admin assignments: suggest says ready/accepted, writes nothing", r.status == 200 and r.body["data"]["state"] == "ready" and r.body["data"]["status"] == "accepted" and not astore.data.get("registration_assignments"), str(r.body))
r = xop("queue")
check("admin assignments: queue 200 with counts", r.status == 200 and r.body["data"]["counts"]["ready"] == 3 and len(r.body["data"]["items"]) == 3, str(r.body))
check("admin assignments: queue with a limit", len(xop("queue", limit=1).body["data"]["items"]) == 1)
r = xop("create", data={"request_id": rq1, "scheduled_class_id": ecid})
check("admin assignments: one-touch create (no status) -> server decides accepted", r.status == 200 and r.body["data"]["status"] == "accepted" and r.body["data"]["decided_by"] == "user:admin", str(r.body))
check("admin assignments: class counts updated", astore.data["scheduled_classes"][ecid]["registered_count"] == 2)
r = xop("create", data={"request_id": rq2, "scheduled_class_id": ecid})
check("admin assignments: second party goes to overflow", r.status == 200 and r.body["data"]["status"] == "overflow" and astore.data["scheduled_classes"][ecid]["registered_count"] == 4)
r = xop("create", data={"request_id": rq3, "scheduled_class_id": ecid})
check("admin assignments: full class -> 409 conflict status:class_full, nothing written", r.status == 409 and r.body["error"]["problems"] == [{"field": "status", "issue": "class_full"}] and len(astore.data["registration_assignments"]) == 2, str(r.body))
r = xop("queue")
check("admin assignments: queue shows the refused one as needs_attention", r.body["data"]["counts"] == {"assigned": 2, "ready": 0, "needs_attention": 1, "no_class": 0, "closed": 0}, str(r.body["data"]["counts"]))
r = cop("soft_delete", id=ecid)
check("admin classes: delete blocked while it holds registrations: 409 id:in_use", r.status == 409 and r.body["error"]["problems"] == [{"field": "id", "issue": "in_use"}])
aid1 = next(a for a in astore.data["registration_assignments"].values() if a["request_id"] == rq1)["id"]
check("admin assignments: delete refused (id:not_allowed)", xop("soft_delete", id=aid1).status == 400 and xop("soft_delete", id=aid1).body["error"]["problems"] == [{"field": "id", "issue": "not_allowed"}])
check("admin assignments: update note 200, status change 400 immutable", xop("update", id=aid1, changes={"decision_note": "hi"}).status == 200 and xop("update", id=aid1, changes={"status": "cancelled"}).body["error"]["problems"] == [{"field": "status", "issue": "immutable"}])
check("admin assignments: set_review_summary not enabled", xop("set_review_summary", id=aid1, review_count=1, average_rating=5).status == 400)
check("admin assignments: list by request", xop("list", filters={"request_id": rq1}).body["data"]["count"] == 1)
check("admin assignments: wrong key 401", acall({"collection": "registration_assignments", "op": "queue", "args": {}}, auth="Bearer nope").status == 401)
check("other collections refuse suggest/queue (400 op:not_supported)", cop("queue").status == 400 and cop("queue").body["error"]["problems"] == [{"field": "op", "issue": "not_supported"}] and aop("suggest", request_id=rq1).status == 400)
check("suggest needs request_id; queue takes only limit", xop("suggest").status == 400 and acall({"collection": "registration_assignments", "op": "queue", "args": {"x": 1}}).status == 400)
r = call({"collection": "registration_assignments", "op": "queue", "args": {}})
check("test door: queue works on test_ collections only", r.status == 200 and r.body["data"]["items"] == [] and not astore.data.get("test_registration_assignments"))


# ---------------------------------------------------------------------------
# Venues: one-window add, move, and read with the records they point at
# ---------------------------------------------------------------------------
ADDR = {"street": "2 Pearl St", "locality": "Boulder", "region": "CO", "postal_code": "80302", "country": "US"}
n0 = (len(astore.data["locations"]), len(astore.data["location_links"]), len(astore.data["venues"]))
r = aop("create_with_place", data={"name": "Amante Coffee", "slug": "amante", "status": "inactive", "is_public_venue": True}, address=ADDR)
check("admin: create_with_place 200, venue inactive, place created", r.status == 200 and r.body["data"]["status"] == "inactive" and r.body["data"]["place"]["address"]["street"] == "2 Pearl St" and r.body["data"]["created_place"], str(r.body))
amid = r.body["data"]["id"]
check("admin: it saved one place, one link and the venue in the REAL collections",
      (len(astore.data["locations"]), len(astore.data["location_links"]), len(astore.data["venues"])) == (n0[0] + 1, n0[1] + 1, n0[2] + 1) and amid in astore.data["venues"])
r = aop("get", id=amid, expand=True)
check("admin: get with expand returns the place", r.status == 200 and r.body["data"]["place"]["name"] == "Amante Coffee")
check("admin: get without expand returns no place", "place" not in aop("get", id=amid).body["data"])
r = aop("list", expand=True)
check("admin: list with expand returns places", r.status == 200 and any(v.get("place") for v in r.body["data"]["records"]))
r = cop("get", id=cid, expand=True)
check("expand on another collection: 400 expand:not_supported", r.status == 400 and r.body["error"]["problems"] == [{"field": "expand", "issue": "not_supported"}])
r = aop("set_place", id=amid, address={**ADDR, "street": "9 New Rd"})
check("admin: set_place moves the venue", r.status == 200 and r.body["data"]["changed"] and r.body["data"]["place"]["address"]["street"] == "9 New Rd", str(r.body))
check("admin: set_place without a destination 400", aop("set_place", id=amid).status == 400)
check("admin: set_place on an unknown venue 404", aop("set_place", id="11111111-1111-4111-8111-111111111111", address=ADDR).status == 404)
r = aop("create_with_place", data={"name": "Bad", "slug": "bad_one", "status": "inactive", "is_public_venue": True}, address={"locality": "x"})
check("admin: a bad address 400 and nothing saved", r.status == 400 and len([v for v in astore.data["venues"].values() if v["slug"] == "bad_one"]) == 0)
check("admin: create_with_place has no extra args", aop("create_with_place", data={}, bogus=1).status == 400)
r = call({"collection": "venues", "op": "create_with_place", "args": {"data": {"name": "T", "slug": "t_venue", "status": "inactive", "is_public_venue": True}, "address": ADDR}})
check("test door: create_with_place works in test_ collections only", r.status == 200 and "test_locations" in store.data and "test_location_links" in store.data)
check("the other collections refuse create_with_place and set_place", cop("create_with_place", data={}).status == 400 and cop("set_place", id=cid, address=ADDR).status == 400)


print()
if fails:
    print("FAILED:", *fails, sep="\n  ")
    sys.exit(1)
print("OK: all CRUD endpoint tests pass (in memory)")
