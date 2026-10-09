#!/usr/bin/env python3
"""In-memory tests for scheduled classes: the handler file, the class service (venue rules) and the venue guards.
Run from enjoy_router/:  python3 run_class_tests.py      Nothing here touches Firebase."""
import copy
import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import classes_service as CS  # noqa: E402
from crud import scheduled_classes_crud as C  # noqa: E402
from crud import venues_crud as V  # noqa: E402
from crud import venues_service as VS  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402

EX = json.loads((HERE.parent / "schemas" / "examples" / "scheduled_class.examples.json").read_text())
START = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
fails: list = []
total = 0


def check(label, ok, detail=""):
    global total
    total += 1
    if not ok:
        fails.append(label)
    if not ok or "-v" in sys.argv:
        print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")


def pairs(problems):
    return sorted(f"{p['field']}:{p['issue']}" for p in problems)


clock = [0]


def tick():
    clock[0] += 5
    return START + timedelta(seconds=clock[0])


def fresh():
    return MemoryDocStore("test_")


VENUE = {"name": "Library", "slug": "library", "status": "active", "is_public_venue": True,
         "street_address": "1 Main St", "city": "Boulder", "state_region": "CO", "postal_code": "80302", "country": "US",
         "time_zone": "America/Denver", "contact_name": "Pat", "contact_email": "pat@example.com",
         "is_accessible": True, "allows_minors": True, "allows_animals": False,
         "rooms": [{"label": "Main room", "max_occupancy": 20}, {"label": "Side room", "max_occupancy": 8, "preferred_occupancy": 6}]}


def make_venue(store, **over):
    d = {**copy.deepcopy(VENUE), **over}
    r = V.create(store, d, "user:t", now=tick())
    assert r.ok, (r.problems, over)
    return r.data


BASE = {"title": "Intro workshop", "slug": "intro", "class_type": "workshop", "program_slug": "launch", "status": "identified",
        "is_public": False, "capacity_minimum": 6, "capacity_target": 10, "capacity_max": 15}


def klass(**over):
    d = {**BASE, **over}
    return {k: v for k, v in d.items() if v is not None}


def scheduled(venue_id, **over):
    d = dict(status="scheduled", starts_at="2026-11-21T01:00:00Z", time_zone="America/Denver", duration_minutes=120,
             venue_id=venue_id, is_venue_confirmed=False)
    d.update(over)
    return klass(**d)


# ---------------------------------------------------------------------------
# 1. The schema's own examples through the handler (no venue rules)
# ---------------------------------------------------------------------------
for name, body in EX["valid"].items():
    r = C.create(fresh(), copy.deepcopy(body), "user:t", now=tick())
    check(f"valid example creates: {name}", r.ok, str(r.problems))
for name, body in EX["invalid"].items():
    s = fresh()
    r = C.create(s, copy.deepcopy(body), "user:t", now=tick())
    check(f"invalid example refused: {name}", (not r.ok) and r.code == "validation_failed" and r.problems, str(r))
    check(f"invalid example stored nothing: {name}", not s.data.get("test_scheduled_classes"))
    check(f"problems carry no values: {name}", all(set(p) == {"field", "issue"} for p in r.problems))

# ---------------------------------------------------------------------------
# 2. Handler: create
# ---------------------------------------------------------------------------
s = fresh()
r = C.create(s, klass(organizer_email="  Todd@Example.COM ", description="  Hello  "), "user:todd", now=tick())
check("create ok", r.ok, str(r.problems))
d = r.data
check("counts start at zero, source dashboard, stamps set", all(d[f] == 0 for f in C.COUNT_FIELDS) and d["source"] == "dashboard"
      and d["created_by"] == "user:todd" and d["schema_version"] == 2)
check("email lowercased, text trimmed", d["organizer_email"] == "todd@example.com" and d["description"] == "Hello")
check("create stores the same record", s.data["test_scheduled_classes"][d["id"]] == d)
r2 = C.create(s, klass(title="Other"), "user:todd", now=tick())
check("duplicate slug refused (slug:duplicate)", pairs(r2.problems) == ["slug:duplicate"], str(r2))
C.soft_delete(s, d["id"], "user:todd", now=tick())
check("slug stays taken after soft delete", pairs(C.create(s, klass(), "user:todd", now=tick()).problems) == ["slug:duplicate"])
for bad in ("registered_count", "id", "created_at", "average_rating", "deleted_at", "source_request_id"):
    r = C.create(fresh(), klass(**{bad: 1 if bad.endswith("count") else "x"}), "user:t", now=tick())
    check(f"sender cannot set {bad}", f"{bad}:not_allowed" in pairs(r.problems), str(r.problems))
check("bad actor refused", pairs(C.create(fresh(), klass(), "todd", now=tick()).problems) == ["actor:invalid_format"])
check("non-object body refused", pairs(C.create(fresh(), "x", "user:t", now=tick()).problems) == ["body:invalid_type"])
check("capacity min above target", pairs(C.create(fresh(), klass(capacity_minimum=12), "user:t", now=tick()).problems) == ["capacity_minimum:out_of_range"])
check("capacity target above max", pairs(C.create(fresh(), klass(capacity_target=16), "user:t", now=tick()).problems) == ["capacity_max:out_of_range"])
check("capacity equal values allowed", C.create(fresh(), klass(capacity_minimum=5, capacity_target=5, capacity_max=5), "user:t", now=tick()).ok)
check("cancelled_reason only when cancelled", pairs(C.create(fresh(), klass(cancelled_reason="Rain"), "user:t", now=tick()).problems) == ["cancelled_reason:not_allowed"])
check("cancelled with reason ok", C.create(fresh(), klass(status="cancelled", cancelled_reason="Rain"), "user:t", now=tick()).ok)
check("scheduled needs date, venue and the rest", {"starts_at:required", "venue_id:required", "time_zone:required", "duration_minutes:required", "is_venue_confirmed:required"} <= set(pairs(C.create(fresh(), klass(status="scheduled"), "user:t", now=tick()).problems)))
check("enrolling needs a price", "price_cents:required" in pairs(C.create(fresh(), scheduled("4b7c1d2e-5f60-4a71-8b92-a3c4d5e6f701", status="enrolling", is_venue_confirmed=True), "user:t", now=tick()).problems))

# ---------------------------------------------------------------------------
# 3. Handler: get, list
# ---------------------------------------------------------------------------
s = fresh()
a = C.create(s, klass(title="Bravo", slug="bravo", class_type="private"), "user:t", now=tick()).data
b = C.create(s, klass(title="Alpha", slug="alpha", is_public=True), "user:t", now=tick()).data
c = C.create(s, klass(title="Charlie", slug="charlie", status="cancelled"), "user:t", now=tick()).data
check("get works", C.get(s, a["id"]).data == a)
check("get unknown is not_found", C.get(s, "9b2f6a3e-1c4d-4e5f-8a7b-0c1d2e3f4a5b").code == "not_found")
check("get bad id", pairs(C.get(s, "nope").problems) == ["id:invalid_format"])
check("list sorted by title", [x["title"] for x in C.list(s).data["records"]] == ["Alpha", "Bravo", "Charlie"])
check("list newest first", [x["title"] for x in C.list(s, order="-created_at").data["records"]] == ["Charlie", "Alpha", "Bravo"])
check("list by status", [x["title"] for x in C.list(s, {"status": "cancelled"}).data["records"]] == ["Charlie"])
check("list by class_type", [x["title"] for x in C.list(s, {"class_type": "private"}).data["records"]] == ["Bravo"])
check("list by is_public", [x["title"] for x in C.list(s, {"is_public": True}).data["records"]] == ["Alpha"])
check("list by venue_id", C.list(s, {"venue_id": "4b7c1d2e-5f60-4a71-8b92-a3c4d5e6f701"}).data["count"] == 0)
check("two filters refused", set(pairs(C.list(s, {"status": "cancelled", "is_public": True}).problems)) == {"status:not_supported", "is_public:not_supported"})
check("unknown filter refused", pairs(C.list(s, {"title": "x"}).problems) == ["title:not_supported"])
check("bad filter value refused", pairs(C.list(s, {"status": "nope"}).problems) != [])
check("order starts_at not supported", pairs(C.list(s, order="starts_at").problems) == ["order:not_supported"])
check("filter with -created_at not supported", pairs(C.list(s, {"status": "cancelled"}, order="-created_at").problems) == ["order:not_supported"])
check("limit clamps", C.list(s, limit=0).data["count"] == 1 and C.list(s, limit=99999).data["count"] == 3)
check("bool limit refused", pairs(C.list(s, limit=True).problems) == ["limit:invalid_type"])
C.soft_delete(s, b["id"], "user:t", now=tick())
check("soft-deleted hidden from list and get", [x["title"] for x in C.list(s).data["records"]] == ["Bravo", "Charlie"] and C.get(s, b["id"]).code == "not_found")
check("include_deleted shows it", C.get(s, b["id"], include_deleted=True).ok)

# ---------------------------------------------------------------------------
# 4. Handler: update
# ---------------------------------------------------------------------------
s = fresh()
k = C.create(s, klass(), "user:t", now=tick()).data
s.reads.clear()
r = C.update(s, k["id"], {"title": "New title", "description": "x"}, "user:u", now=tick())
check("simple update ok, reports changes", r.ok and r.data["changed"] == ["description", "title"] and r.data["updated_by"] == "user:u", str(r))
check("simple update does not read", not s.reads, str(s.reads))
cur = s.data["test_scheduled_classes"][k["id"]]
check("stored and stamped", cur["title"] == "New title" and cur["updated_by"] == "user:u" and cur["created_by"] == "user:t")
check("slug immutable", pairs(C.update(s, k["id"], {"slug": "x"}, "user:u", now=tick()).problems) == ["slug:immutable"])
check("read-only refused", pairs(C.update(s, k["id"], {"registered_count": 3}, "user:u", now=tick()).problems) == ["registered_count:not_allowed"])
check("unknown field refused", pairs(C.update(s, k["id"], {"flavor": 3}, "user:u", now=tick()).problems) == ["flavor:not_allowed"])
check("required field cannot be removed", pairs(C.update(s, k["id"], {"title": None}, "user:u", now=tick()).problems) == ["title:required"])
check("empty string removes optional field", C.update(s, k["id"], {"description": ""}, "user:u", now=tick()).ok and "description" not in s.data["test_scheduled_classes"][k["id"]])
check("empty changes refused", pairs(C.update(s, k["id"], {}, "user:u", now=tick()).problems) == ["changes:required"])
check("bad value refused", pairs(C.update(s, k["id"], {"duration_minutes": 5}, "user:u", now=tick()).problems) == ["duration_minutes:out_of_range"])
s.reads.clear()
r = C.update(s, k["id"], {"capacity_max": 8}, "user:u", now=tick())
check("capacity max below target refused", pairs(r.problems) == ["capacity_max:out_of_range"], str(r))
check("capacity update read the record once", len([x for x in s.reads if x[0] == "get"]) >= 1)
check("status to scheduled without the date and venue refused", {"starts_at:required", "venue_id:required"} <= set(pairs(C.update(s, k["id"], {"status": "scheduled"}, "user:u", now=tick()).problems)))
r = C.update(s, k["id"], {"status": "scheduled", "starts_at": "2026-11-21T01:00:00Z", "time_zone": "America/Denver", "duration_minutes": 90,
                          "venue_id": "4b7c1d2e-5f60-4a71-8b92-a3c4d5e6f701", "is_venue_confirmed": False}, "user:u", now=tick())
check("status to scheduled with everything ok (handler alone knows no venues)", r.ok, str(r.problems))
check("removing a field the status needs refused", pairs(C.update(s, k["id"], {"starts_at": None}, "user:u", now=tick()).problems) == ["starts_at:required"])
check("cancelled_reason refused while not cancelled", pairs(C.update(s, k["id"], {"cancelled_reason": "x"}, "user:u", now=tick()).problems) == ["cancelled_reason:not_allowed"])
check("cancel with reason in one update ok", C.update(s, k["id"], {"status": "cancelled", "cancelled_reason": "Low sign-ups"}, "user:u", now=tick()).ok)
check("leaving cancelled needs the reason removed", pairs(C.update(s, k["id"], {"status": "identified"}, "user:u", now=tick()).problems) == ["cancelled_reason:not_allowed"])
check("leave cancelled and remove reason together ok", C.update(s, k["id"], {"status": "identified", "cancelled_reason": None}, "user:u", now=tick()).ok)
cur = s.data["test_scheduled_classes"][k["id"]]
check("conflict on stale expected_updated_at", C.update(s, k["id"], {"capacity_max": 20}, "user:u", expected_updated_at="2020-01-01T00:00:00Z", now=tick()).code == "conflict")
check("conflict on stale expected_updated_at (simple path)", C.update(s, k["id"], {"title": "Z"}, "user:u", expected_updated_at="2020-01-01T00:00:00Z", now=tick()).code == "conflict")
check("matching expected_updated_at accepted", C.update(s, k["id"], {"title": "Z"}, "user:u", expected_updated_at=cur["updated_at"], now=tick()).ok)
check("bad expected_updated_at format refused", pairs(C.update(s, k["id"], {"title": "Z"}, "user:u", expected_updated_at="yesterday", now=tick()).problems) == ["expected_updated_at:invalid_format"])
check("update unknown id", C.update(s, "9b2f6a3e-1c4d-4e5f-8a7b-0c1d2e3f4a5b", {"title": "Z"}, "user:u", now=tick()).code == "not_found")
check("update with a bad id", pairs(C.update(s, "x", {"title": "Z"}, "user:u", now=tick()).problems) == ["id:invalid_format"])
check("delete then update on whole path not_found", (C.soft_delete(s, k["id"], "user:u", now=tick()).ok and C.update(s, k["id"], {"capacity_max": 30}, "user:u", now=tick()).code == "not_found"))
r = C.soft_delete(s, k["id"], "user:u", now=tick())
check("delete twice is not_found", r.code == "not_found")
check("deleted record kept with who and when", "deleted_at" in s.data["test_scheduled_classes"][k["id"]] and s.data["test_scheduled_classes"][k["id"]]["deleted_by"] == "user:u")

# review summary
s = fresh()
k = C.create(s, klass(), "user:t", now=tick()).data
check("review summary set", C.set_review_summary(s, k["id"], 3, 4.5, now=tick()).ok and s.data["test_scheduled_classes"][k["id"]]["average_rating"] == 4.5)
check("review summary removes rating", C.set_review_summary(s, k["id"], 0, None, now=tick()).ok and "average_rating" not in s.data["test_scheduled_classes"][k["id"]])
check("review summary bad rating refused", not C.set_review_summary(s, k["id"], 3, 7, now=tick()).ok)
check("review summary unknown id", C.set_review_summary(s, "9b2f6a3e-1c4d-4e5f-8a7b-0c1d2e3f4a5b", 1, 1, now=tick()).code == "not_found")

# ---------------------------------------------------------------------------
# 5. Service: venue rules on create
# ---------------------------------------------------------------------------
s = fresh()
v = make_venue(s)
GHOST = "9b2f6a3e-1c4d-4e5f-8a7b-0c1d2e3f4a5b"
check("class with no venue (idea) ok", CS.create(s, klass(slug="idea"), "user:t", now=tick()).ok)
r = CS.create(s, scheduled(v["id"], slug="s1", venue_room_label="Main room", capacity_max=15), "user:t", now=tick())
check("scheduled class at active venue, valid room ok", r.ok, str(r.problems))
check("room match ignores case", CS.create(s, scheduled(v["id"], slug="s2", venue_room_label="main ROOM", capacity_max=15), "user:t", now=tick()).ok)
check("unknown venue refused", pairs(CS.create(s, scheduled(GHOST, slug="s3"), "user:t", now=tick()).problems) == ["venue_id:not_found"])
check("unknown room refused", pairs(CS.create(s, scheduled(v["id"], slug="s4", venue_room_label="Attic"), "user:t", now=tick()).problems) == ["venue_room_label:not_found"])
check("capacity_max above room max refused", pairs(CS.create(s, scheduled(v["id"], slug="s5", venue_room_label="Side room", capacity_max=15), "user:t", now=tick()).problems) == ["capacity_max:out_of_range"])
check("capacity_max equal to room max ok", CS.create(s, scheduled(v["id"], slug="s6", venue_room_label="Side room", capacity_minimum=2, capacity_target=4, capacity_max=8), "user:t", now=tick()).ok)
check("room label without a venue refused", pairs(CS.create(s, klass(slug="s7", venue_room_label="Main room"), "user:t", now=tick()).problems) == ["venue_id:required"])
check("identified class may name a venue and room", CS.create(s, klass(slug="s8", venue_id=v["id"], venue_room_label="Main room"), "user:t", now=tick()).ok)
inactive = make_venue(s, name="Closed", slug="closed", status="inactive")
check("scheduled at an inactive venue refused", pairs(CS.create(s, scheduled(inactive["id"], slug="s9"), "user:t", now=tick()).problems) == ["venue_id:inactive"])
check("identified at an inactive venue ok", CS.create(s, klass(slug="s10", venue_id=inactive["id"]), "user:t", now=tick()).ok)
check("completed at an inactive venue ok (history)", CS.create(s, scheduled(inactive["id"], slug="s11", status="completed", price_cents=0, price_basis="per_session"), "user:t", now=tick()).ok)
V.soft_delete(s, inactive["id"], "user:t", now=tick())
check("deleted venue is not_found", pairs(CS.create(s, klass(slug="s12", venue_id=inactive["id"]), "user:t", now=tick()).problems) == ["venue_id:not_found"])
check("handler problems come before venue lookup (bad uuid)", pairs(CS.create(s, klass(slug="s13", venue_id="nope"), "user:t", now=tick()).problems) != [] and
      "venue_id:not_found" not in pairs(CS.create(s, klass(slug="s13", venue_id="nope"), "user:t", now=tick()).problems))

# ---------------------------------------------------------------------------
# 6. Service: venue rules on update (and when the venue is not read)
# ---------------------------------------------------------------------------
s = fresh()
v = make_venue(s)
k = CS.create(s, scheduled(v["id"], slug="k1", venue_room_label="Main room", capacity_max=15), "user:t", now=tick()).data
s.reads.clear()
check("title update ok", CS.update(s, k["id"], {"title": "Renamed"}, "user:u", now=tick()).ok)
check("title update did not read the venue or the class", not s.reads, str(s.reads))
check("capacity_max over room refused", pairs(CS.update(s, k["id"], {"capacity_max": 25}, "user:u", now=tick()).problems) == ["capacity_max:out_of_range"])
check("capacity_max within room ok", CS.update(s, k["id"], {"capacity_max": 18}, "user:u", now=tick()).ok)
check("move to a smaller room refused when capacity_max too high", pairs(CS.update(s, k["id"], {"venue_room_label": "Side room"}, "user:u", now=tick()).problems) == ["capacity_max:out_of_range"])
check("move to a smaller room with capacity lowered ok", CS.update(s, k["id"], {"venue_room_label": "Side room", "capacity_minimum": 2, "capacity_target": 4, "capacity_max": 8}, "user:u", now=tick()).ok)
check("room that does not exist refused", pairs(CS.update(s, k["id"], {"venue_room_label": "Attic"}, "user:u", now=tick()).problems) == ["venue_room_label:not_found"])
check("removing the room label ok", CS.update(s, k["id"], {"venue_room_label": None}, "user:u", now=tick()).ok)
other = make_venue(s, name="Hall", slug="hall", rooms=[{"label": "Big hall", "max_occupancy": 100}])
check("moving to another venue leaves the room name behind", CS.update(s, k["id"], {"venue_id": other["id"], "venue_room_label": "Big hall"}, "user:u", now=tick()).ok)
check("changing venue keeps stale room label refused", pairs(CS.update(s, k["id"], {"venue_id": v["id"]}, "user:u", now=tick()).problems) == ["venue_room_label:not_found"])
check("unknown venue refused on update", pairs(CS.update(s, k["id"], {"venue_id": GHOST}, "user:u", now=tick()).problems) == ["venue_id:not_found"])
VS.update(s, other["id"], {"status": "inactive"}, "user:t", now=tick())
check("inactive venue after the fact: title edit still fine", CS.update(s, k["id"], {"title": "Still ok"}, "user:u", now=tick()).ok)
check("inactive venue: re-saving status scheduled refused", pairs(CS.update(s, k["id"], {"status": "scheduled"}, "user:u", now=tick()).problems) == ["venue_id:inactive"])
check("inactive venue: cancel allowed", CS.update(s, k["id"], {"status": "cancelled", "cancelled_reason": "Venue closed"}, "user:u", now=tick()).ok)
check("service get/list/delete pass through", CS.get(s, k["id"]).ok and CS.list(s).ok and CS.soft_delete(s, k["id"], "user:u", now=tick()).ok)

# ---------------------------------------------------------------------------
# 7. Venue guards
# ---------------------------------------------------------------------------
s = fresh()
v = make_venue(s)
k = CS.create(s, scheduled(v["id"], slug="g1", venue_room_label="Main room", capacity_max=15), "user:t", now=tick()).data
r = VS.soft_delete(s, v["id"], "user:t", now=tick())
check("venue with a live class cannot be deleted (409, id:in_use)", r.code == "conflict" and pairs(r.problems) == ["id:in_use"], str(r))
check("venue still there", "deleted_at" not in s.data["test_venues"][v["id"]])
check("setting such a venue inactive is allowed", VS.update(s, v["id"], {"status": "inactive"}, "user:t", now=tick()).ok)
VS.update(s, v["id"], {"status": "active"}, "user:t", now=tick())
check("cannot remove a room a class uses", pairs(VS.update(s, v["id"], {"rooms": [{"label": "Side room", "max_occupancy": 8}]}, "user:t", now=tick()).problems) == ["rooms:in_use"])
check("cannot rename a room a class uses", pairs(VS.update(s, v["id"], {"rooms": [{"label": "Big room", "max_occupancy": 20}, {"label": "Side room", "max_occupancy": 8}]}, "user:t", now=tick()).problems) == ["rooms:in_use"])
check("cannot shrink a room below capacity_max", pairs(VS.update(s, v["id"], {"rooms": [{"label": "Main room", "max_occupancy": 10}, {"label": "Side room", "max_occupancy": 8}]}, "user:t", now=tick()).problems) == ["rooms:in_use"])
check("cannot remove all rooms", pairs(VS.update(s, v["id"], {"rooms": None, "status": "inactive"}, "user:t", now=tick()).problems) == ["rooms:in_use"])
check("rooms unchanged after refusals", len(s.data["test_venues"][v["id"]]["rooms"]) == 2)
check("can add a room", VS.update(s, v["id"], {"rooms": [{"label": "Main room", "max_occupancy": 20}, {"label": "Side room", "max_occupancy": 8}, {"label": "Patio", "max_occupancy": 30}]}, "user:t", now=tick()).ok)
check("can change an unused room", VS.update(s, v["id"], {"rooms": [{"label": "Main room", "max_occupancy": 20}, {"label": "Side room", "max_occupancy": 4}, {"label": "Patio", "max_occupancy": 30}]}, "user:t", now=tick()).ok)
check("can grow the used room", VS.update(s, v["id"], {"rooms": [{"label": "Main room", "max_occupancy": 40}, {"label": "Side room", "max_occupancy": 4}, {"label": "Patio", "max_occupancy": 30}]}, "user:t", now=tick()).ok)
s.reads.clear()
check("unrelated venue edit ok", VS.update(s, v["id"], {"description": "Nice"}, "user:t", now=tick()).ok)
check("unrelated venue edit did not read classes", not [x for x in s.reads if "scheduled" in str(x)], str(s.reads))
C.soft_delete(s, k["id"], "user:t", now=tick())
check("a deleted class no longer blocks the venue rooms", VS.update(s, v["id"], {"rooms": [{"label": "Side room", "max_occupancy": 4}]}, "user:t", now=tick()).ok)
check("or the venue delete", VS.soft_delete(s, v["id"], "user:t", now=tick()).ok)
check("venue service passes get/list/create/summary", VS.get(s, v["id"], True).ok and VS.list(s).ok and VS.create(s, {"name": "N", "slug": "n", "status": "inactive", "is_public_venue": False}, "user:t", now=tick()).ok
      and VS.set_review_summary(s, VS.list(s).data["records"][0]["id"], 1, 5, now=tick()).ok)
check("venue delete with bad id gives the handler's problem", pairs(VS.soft_delete(s, "x", "user:t").problems) == ["id:invalid_format"])

print(f"\n{total - len(fails)}/{total} checks passed")
if fails:
    print("FAILED:", ", ".join(fails))
    sys.exit(1)
