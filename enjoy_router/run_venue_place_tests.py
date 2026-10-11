#!/usr/bin/env python3
"""In-memory tests for the venue's new shape: no address of its own, a place through an operates_at location_link,
contact people as pointers to individuals. Covers the rules in venues_service.py.
Run from enjoy_router/:  python3 run_venue_place_tests.py   (add -v to list every check)."""
import pathlib
import sys
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import individual_merges_crud as M  # noqa: E402
from crud import individuals_crud as I  # noqa: E402
from crud import individuals_service as IS  # noqa: E402
from crud import location_links_crud as H  # noqa: E402
from crud import location_links_service as LS  # noqa: E402
from crud import locations_crud as L  # noqa: E402
from crud import venues_service as VS  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402

START = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)
fails: list = []
total = 0
clock = [0]
ACT = "user:todd"


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


def pairs(problems):
    return sorted(f"{p['field']}:{p['issue']}" for p in problems)


s = MemoryDocStore("test_")
ADDR = {"usage": "civic", "street": "1 Main St", "locality": "Boulder", "region": "CO", "postal_code": "80302", "country": "US"}
FULL = {"email": "front@example.com", "is_accessible": True, "allows_minors": True, "allows_animals": False,
        "rooms": [{"label": "Main room", "max_occupancy": 20}]}
n = [0]


def person(name="Sue"):
    return I.create(s, {"given_name": name}, ACT, now=tick()).data


def draft(**kw):
    n[0] += 1
    r = VS.create(s, {"name": f"Venue {n[0]}", "slug": f"venue_{n[0]}", "status": "inactive", "is_public_venue": True, **kw}, ACT, now=tick())
    assert r.ok, r.problems
    return r.data


def place(**kw):
    r = L.create(s, {"name": "Place", "addresses": [ADDR], **kw}, ACT, now=tick())
    assert r.ok, r.problems
    return r.data


def link(v, loc, rel="operates_at", **kw):
    r = LS.create(s, {"subject_type": "venue", "subject_id": v["id"], "location_id": loc["id"], "relationship": rel, **kw}, ACT, now=tick())
    assert r.ok, r.problems
    return r.data


def activate(v, **extra):
    return VS.update(s, v["id"], {"status": "active", **extra}, ACT, now=tick())


sue = person()

# ---- a draft is just a name
d = draft()
check("a draft venue needs only name, slug, status, is_public_venue", d["status"] == "inactive" and "contact_individual_id" not in d)
check("the venue has no address fields", all(f not in d for f in ("street_address", "city", "time_zone", "latitude")))
for f, v in (("street_address", "1 Main"), ("city", "Boulder"), ("time_zone", "America/Denver"), ("latitude", 40.0), ("contact_name", "Pat")):
    r = VS.create(s, {"name": "X", "slug": f"x_{f}", "status": "inactive", "is_public_venue": True, f: v}, ACT, now=tick())
    check(f"old field {f} is refused on create", not r.ok and pairs(r.problems) == [f"{f}:not_allowed"], str(r.problems))

# ---- email is the venue's own, lowercased
r = VS.create(s, {"name": "Cafe", "slug": "cafe", "status": "inactive", "is_public_venue": True, "email": " Front@Example.COM "}, ACT, now=tick())
check("email is trimmed and lowercased", r.ok and r.data["email"] == "front@example.com")

# ---- creating active is refused
r = VS.create(s, {"name": "A", "slug": "a_active", "status": "active", "is_public_venue": True, **FULL, "contact_individual_id": sue["id"]}, ACT, now=tick())
check("create active is refused: place_required", not r.ok and "status:place_required" in pairs(r.problems), str(r.problems))

# ---- contact pointers
r = VS.create(s, {"name": "B", "slug": "b_contact", "status": "inactive", "is_public_venue": True, "contact_individual_id": "11111111-1111-4111-8111-111111111111"}, ACT, now=tick())
check("a contact that does not exist is refused", not r.ok and pairs(r.problems) == ["contact_individual_id:not_found"], str(r.problems))
gone = person("Gone")
M.erase(s, gone["id"], ACT, now=tick())
r = VS.create(s, {"name": "C", "slug": "c_contact", "status": "inactive", "is_public_venue": True, "backup_contact_individual_id": gone["id"]}, ACT, now=tick())
check("an erased contact is refused", not r.ok and pairs(r.problems) == ["backup_contact_individual_id:not_found"], str(r.problems))
r = VS.create(s, {"name": "D", "slug": "d_contact", "status": "inactive", "is_public_venue": True, "contact_individual_id": sue["id"]}, ACT, now=tick())
check("a real contact is accepted and stored as an id only", r.ok and r.data["contact_individual_id"] == sue["id"] and "contact_name" not in r.data)
r = VS.update(s, d["id"], {"contact_individual_id": "not-a-uuid"}, ACT, now=tick())
check("a malformed contact id is refused", not r.ok and pairs(r.problems) == ["contact_individual_id:invalid_format"], str(r.problems))
r = VS.update(s, d["id"], {"contact_individual_id": sue["id"], "backup_contact_individual_id": sue["id"]}, ACT, now=tick())
check("update sets both contact pointers", r.ok and r.data["changed"] == ["backup_contact_individual_id", "contact_individual_id"])
r = VS.update(s, d["id"], {"contact_individual_id": gone["id"]}, ACT, now=tick())
check("update to an erased contact is refused", not r.ok and pairs(r.problems) == ["contact_individual_id:not_found"], str(r.problems))
r = VS.update(s, d["id"], {"backup_contact_individual_id": None}, ACT, now=tick())
check("the backup contact can be removed", r.ok and "backup_contact_individual_id" not in s.get("venues", d["id"]))

# ---- the activation gate
v = draft(**FULL, contact_individual_id=sue["id"])
r = activate(v)
check("no place: activation refused with place_required", not r.ok and pairs(r.problems) == ["status:place_required"], str(r.problems))
check("and the venue is still inactive", s.get("venues", v["id"])["status"] == "inactive")
nameonly = L.create(s, {"name": "Just a name"}, ACT, now=tick()).data
lk0 = link(v, nameonly)
r = activate(v)
check("a place with neither an address nor a GPS point does not count", not r.ok and pairs(r.problems) == ["status:place_required"], str(r.problems))
LS.end(s, lk0["id"], ACT, now=tick())
owns = link(v, place(), "owns")
r = activate(v)
check("only an operates_at link counts", not r.ok and pairs(r.problems) == ["status:place_required"], str(r.problems))
LS.end(s, owns["id"], ACT, now=tick())
former = place(addresses=[{**ADDR, "usage": "former"}])
lk1 = link(v, former)
r = activate(v)
check("a place with only a former address does not count", not r.ok and pairs(r.problems) == ["status:place_required"], str(r.problems))
LS.end(s, lk1["id"], ACT, now=tick())
good = place()
lk2 = link(v, good)
r = activate(v)
check("with a live operates_at link to a place with an address, activation works", r.ok, str(r.problems))
check("the venue is now active", s.get("venues", v["id"])["status"] == "active")

# ---- nothing else is required (a city park)
park = draft()
pin = L.create(s, {"name": "City park", "geometries": [{"role": "center", "geometry": {"type": "Point", "coordinates": [-105.27, 40.01]}}]}, ACT, now=tick()).data
link(park, pin)
r = activate(park)
check("a venue with only a GPS place is active: no contact, no email, no rooms, no answers needed", r.ok, str(r.problems))
rec = s.get("venues", park["id"])
check("and it stored nothing else", rec["status"] == "active" and not any(f in rec for f in ("email", "phone", "contact_individual_id", "rooms", "is_accessible", "allows_minors", "allows_animals")))
v2 = draft()
link(v2, place())
check("an address-only venue with nothing else activates", activate(v2).ok)

# ---- a retired place does not count
v5 = draft(**FULL, contact_individual_id=sue["id"])
retire_me = place()
lk5 = link(v5, retire_me)
LS.end(s, lk5["id"], ACT, now=tick())
check("retire works once the link is ended", L.update(s, retire_me["id"], {"status": "retired"}, ACT, now=tick()).ok)
r = LS.create(s, {"subject_type": "venue", "subject_id": v5["id"], "location_id": retire_me["id"], "relationship": "operates_at"}, ACT, now=tick())
check("a retired place cannot be linked again", not r.ok and pairs(r.problems) == ["location_id:retired"], str(r.problems))

# ---- editing an active venue does not re-check an old contact
r = erased = person("Soon")
M.erase(s, erased["id"], ACT, now=tick())
raw = s.get("venues", v["id"])
s.update("venues", v["id"], {"backup_contact_individual_id": erased["id"]}, [])
r = VS.update(s, v["id"], {"rooms": [{"label": "Main room", "max_occupancy": 25}]}, ACT, now=tick())
check("a stale contact pointer does not block an unrelated edit", r.ok, str(r.problems))

# ---- merge repoints a contact; unmerge restores it
a, b = person("Keep"), person("Dup")
vm = draft(contact_individual_id=b["id"])
m = IS.merge(s, a["id"], b["id"], "same person", ACT, now=tick())
check("merge succeeds", m.ok, str(m.problems))
check("merge re-points the venue's contact to the survivor", s.get("venues", vm["id"])["contact_individual_id"] == a["id"])
u = IS.unmerge(s, m.data["id"], ACT, now=tick())
check("unmerge succeeds", u.ok, str(u.problems))
check("unmerge puts the contact back", s.get("venues", vm["id"])["contact_individual_id"] == b["id"])

# ---- expand: the venue read together with the records it points at
bob = person("Bob")
vx = draft(**FULL, contact_individual_id=sue["id"], backup_contact_individual_id=bob["id"])
lx = place(name="Amante Coffee")
link(vx, lx)
r = VS.get(s, vx["id"], expand=True)
check("expand: place carries name, address and the link id", r.ok and r.data["place"]["name"] == "Amante Coffee" and r.data["place"]["address"]["locality"] == "Boulder" and r.data["place"]["link_id"], str(r.data))
check("expand: contacts carry names read from the people", r.data["main_contact"] == {"id": sue["id"], "display_name": "Sue"} and r.data["backup_contact"]["display_name"] == "Bob")
check("expand: the stored venue still holds only ids", "place" not in s.get("venues", vx["id"]) and "main_contact" not in s.get("venues", vx["id"]))
check("no expand: the record is unchanged", "place" not in VS.get(s, vx["id"]).data)
lst = VS.list(s, {"status": "inactive"}, expand=True)
check("expand works on list", lst.ok and all("place" in d or d["id"] != vx["id"] for d in lst.data["records"]) and any(d.get("place") for d in lst.data["records"]))
M.erase(s, bob["id"], ACT, now=tick())
check("an erased contact shows as unavailable, no name", VS.get(s, vx["id"], expand=True).data["backup_contact"] == {"id": bob["id"], "unavailable": True})
lone = draft()
check("a venue with no place or contacts expands to nothing extra", set(VS.get(s, lone["id"], expand=True).data) == set(VS.get(s, lone["id"]).data))
TZ = place(name="Zoned", time_zone="America/Denver")
vz = draft(); link(vz, TZ)
check("expand: the place's time zone is passed along", VS.get(s, vz["id"], expand=True).data["place"]["time_zone"] == "America/Denver")

# ---- create_with_place
ADDR_IN = {"street": "2 Pearl St", "locality": "Boulder", "region": "CO", "postal_code": "80302", "country": "US"}
r = VS.create_with_place(s, {"name": "Amante Pearl", "slug": "amante_pearl", "status": "inactive", "is_public_venue": True}, ACT, address=ADDR_IN, now=tick())
check("create_with_place: ok, inactive, place created and named after the venue", r.ok and r.data["status"] == "inactive" and r.data["created_place"] and r.data["place"]["name"] == "Amante Pearl", str(r.problems))
check("create_with_place: the address is the primary civic address", r.data["place"]["address"]["street"] == "2 Pearl St" and r.data["place"]["address"]["usage"] == "civic")
vid2 = r.data["id"]
check("create_with_place: a live operates_at link exists", any(l["relationship"] == "operates_at" and l["status"] == "active" for l in s.query("location_links", [("subject_id", "==", vid2)])))
check("...and the venue can now be activated with nothing else", activate({"id": vid2}).ok)
r = VS.create_with_place(s, {"name": "Draft Only", "slug": "draft_only", "status": "inactive", "is_public_venue": True}, ACT, now=tick())
check("create_with_place with no address saves just the venue", r.ok and "place" not in r.data and not r.data["created_place"])
r = VS.create_with_place(s, {"name": "On Saved", "slug": "on_saved", "status": "inactive", "is_public_venue": True}, ACT, location_id=good["id"], now=tick())
check("create_with_place with a saved place uses it, creates no new place", r.ok and r.data["place"]["location_id"] == good["id"] and not r.data["created_place"])
before = (len(s.data["test_locations"]), len(s.data["test_venues"]), len(s.data["test_location_links"]))
r = VS.create_with_place(s, {"name": "Dup", "slug": "amante_pearl", "status": "inactive", "is_public_venue": True}, ACT, address=ADDR_IN, now=tick())
check("a failing venue saves nothing, not even the place", not r.ok and pairs(r.problems) == ["slug:duplicate"] and before == (len(s.data["test_locations"]), len(s.data["test_venues"]), len(s.data["test_location_links"])), str(r.problems))
r = VS.create_with_place(s, {"name": "Bad Addr", "slug": "bad_addr", "status": "inactive", "is_public_venue": True}, ACT, address={"locality": "Boulder"}, now=tick())
check("a bad address saves nothing and names the address", not r.ok and any(p["field"] == "address" for p in r.problems) and before == (len(s.data["test_locations"]), len(s.data["test_venues"]), len(s.data["test_location_links"])), str(r.problems))
check("both an address and a saved place: choose_one", pairs(VS.create_with_place(s, {"name": "X", "slug": "x_both", "status": "inactive", "is_public_venue": True}, ACT, address=ADDR_IN, location_id=good["id"], now=tick()).problems) == ["address:choose_one"])
check("an unknown saved place is refused", pairs(VS.create_with_place(s, {"name": "X", "slug": "x_unknown", "status": "inactive", "is_public_venue": True}, ACT, location_id="11111111-1111-4111-8111-111111111111", now=tick()).problems) == ["location_id:not_found"])
check("created active is still refused", "status:place_required" in pairs(VS.create_with_place(s, {"name": "X", "slug": "x_active", "status": "active", "is_public_venue": True}, ACT, address=ADDR_IN, now=tick()).problems))

# ---- set_place
vs = VS.create_with_place(s, {"name": "Mover", "slug": "mover", "status": "inactive", "is_public_venue": True}, ACT, address=ADDR_IN, now=tick()).data
old_loc = vs["place"]["location_id"]
r = VS.set_place(s, vs["id"], ACT, address={**ADDR_IN, "street": "9 New Rd"}, now=tick())
check("set_place with an address: moved", r.ok and r.data["changed"] and r.data["place"]["address"]["street"] == "9 New Rd" and r.data["place"]["location_id"] != old_loc, str(r.problems))
old_links = [l for l in s.query("location_links", [("subject_id", "==", vs["id"])]) if l["location_id"] == old_loc]
check("the old link is ended, not deleted, and the old place is kept", len(old_links) == 1 and old_links[0]["status"] == "ended" and "valid_to" in old_links[0] and "deleted_at" not in old_links[0] and s.get("locations", old_loc))
live = [l for l in s.query("location_links", [("subject_id", "==", vs["id"])]) if l["status"] == "active"]
check("exactly one live place link remains", len(live) == 1 and live[0]["is_primary"])
r = VS.set_place(s, vs["id"], ACT, location_id=good["id"], now=tick())
check("set_place to a saved place", r.ok and r.data["place"]["location_id"] == good["id"])
r = VS.set_place(s, vs["id"], ACT, location_id=good["id"], now=tick())
check("setting the place it already has changes nothing", r.ok and r.data["changed"] is False)
check("set_place needs an address or a place", pairs(VS.set_place(s, vs["id"], ACT, now=tick()).problems) == ["address:required"])
check("set_place on a missing venue: not_found", VS.set_place(s, "11111111-1111-4111-8111-111111111111", ACT, address=ADDR_IN, now=tick()).code == "not_found")
check("set_place with a failing address changes nothing", not VS.set_place(s, vs["id"], ACT, address={"locality": "x"}, now=tick()).ok and VS.get(s, vs["id"], expand=True).data["place"]["location_id"] == good["id"])
activate(vs)
blank = L.create(s, {"name": "Blank"}, ACT, now=tick()).data
check("an active venue cannot move to a place with no address or GPS", pairs(VS.set_place(s, vs["id"], ACT, location_id=blank["id"], now=tick()).problems) == ["status:place_required"])
check("an inactive venue can", VS.set_place(s, lone["id"], ACT, location_id=blank["id"], now=tick()).ok)

if fails:
    print(f"\n{total - len(fails)}/{total} checks passed\nFAILED:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print(f"\n{total}/{total} checks passed\nOK")
