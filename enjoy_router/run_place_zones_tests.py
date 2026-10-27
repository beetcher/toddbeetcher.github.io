#!/usr/bin/env python3
"""In-memory tests for time zones on places (P-94): the ZIP-to-zone table (spot checks), a place gets its zone from its ZIP when it is saved,
and the fix_place_zones op fills every older place it can (all states) and lists only the ones it cannot; a dry run writes nothing."""
import pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from datetime import datetime, timezone  # noqa: E402
from crud import locations_crud as LOC  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud_endpoint import handle_admin, make_failure_limiter  # noqa: E402
from launch_discovery import zip_zones  # noqa: E402
import place_zones  # noqa: E402

fails = []
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else " " + str(detail)))
    if not ok: fails.append(label)

# ---- the table: real places that are easy to get wrong
SPOTS = {"85001": "America/Phoenix", "85501": "America/Phoenix", "86040": "America/Phoenix", "86515": "America/Denver",   # Phoenix, Globe, Page; Navajo Nation keeps daylight time
         "46201": "America/New_York", "47708": "America/Chicago", "46320": "America/Chicago", "79901": "America/Denver",   # Indianapolis, Evansville, Hammond; El Paso
         "32401": "America/Chicago", "32801": "America/New_York", "99501": "America/Anchorage", "96801": "Pacific/Honolulu", "99546": "America/Adak",
         "80202": "America/Denver", "10001": "America/New_York", "90001": "America/Los_Angeles", "60601": "America/Chicago", "77437": "America/Chicago",
         "83702": "America/Denver", "83501": "America/Los_Angeles", "49855": "America/New_York", "49858": "America/Chicago", "58501": "America/Chicago",
         "57701": "America/Denver", "40202": "America/New_York", "42101": "America/Chicago", "37201": "America/Chicago", "37601": "America/New_York",
         "98101": "America/Los_Angeles", "84101": "America/Denver", "55901": "America/Chicago", "99999": None, "00000": None, "abcde": None, "": None}
bad = {z: (zip_zones.zone_of(z), want) for z, want in SPOTS.items() if zip_zones.zone_of(z) != want}
check("ZIP to zone: %d spot checks (Arizona, Navajo Nation, Indiana, El Paso, panhandle, Alaska, Hawaii, Aleutians, split states, made-up ZIPs)" % len(SPOTS), not bad, bad)
check("ZIP plus four works", zip_zones.zone_of("80202-1234") == "America/Denver")
check("the eight zones the Console offers", zip_zones.zones() == ["America/New_York", "America/Chicago", "America/Denver", "America/Phoenix", "America/Los_Angeles", "America/Anchorage", "America/Adak", "Pacific/Honolulu"])

A = "user:admin"
s = MemoryDocStore("")
def addr(region=None, zip_=None):
    a = {"usage": "civic", "street_number": "1", "street": "Main St", "locality": "Town", "country": "US"}
    if region: a["region"] = region
    if zip_: a["postal_code"] = zip_
    return a
def mk(name, region=None, zip_=None, tz=None):
    d = {"name": name, "addresses": [addr(region, zip_)]}
    if tz: d["time_zone"] = tz
    r = LOC.create(s, d, A); assert r.ok, r.problems; return r.data["id"]
def old(name, region=None, zip_=None):   # an older place saved before the system filled zones: no zone
    i = mk(name, region, zip_); assert LOC.update(s, i, {"time_zone": None}, A).ok; assert not s.get("locations", i).get("time_zone"); return i

# ---- a place gets its zone when it is saved
az_new = mk("Phoenix Hall", "AZ", "85001")
check("a new place with a ZIP gets its zone (Phoenix: no daylight saving)", s.get("locations", az_new)["time_zone"] == "America/Phoenix")
kept = mk("Chosen", "AZ", "85001", "America/Denver")
check("a zone given by a person is kept", s.get("locations", kept)["time_zone"] == "America/Denver")
bare = LOC.create(s, {"name": "No address yet"}, A).data["id"]
check("a place with no address has no zone", not s.get("locations", bare).get("time_zone"))
check("... and gets one when an address with a ZIP is added", LOC.update(s, bare, {"addresses": [addr("ID", "83702")]}, A).ok and s.get("locations", bare)["time_zone"] == "America/Denver")
check("an address change does not overwrite a zone a place already has", LOC.update(s, bare, {"addresses": [addr("ID", "83501")]}, A).ok and s.get("locations", bare)["time_zone"] == "America/Denver")
nozip = mk("Street only", "AZ")
check("an address with no ZIP leaves the zone empty (nothing guessed)", not s.get("locations", nozip).get("time_zone"))

# ---- the fix-up for older places
co = old("Boulder Library", "CO", "80301"); az = old("Phoenix Library", "AZ", "85001"); inn = old("Indy Hall", "IN", "46201"); evv = old("Evansville Hall", "IN", "47708")
navajo = old("Window Rock", "AZ", "86515"); co_nozip = old("Colorado, no ZIP", "CO"); ny = old("New York Hall", "NY", "10001")
dry = place_zones.run(s, A, apply=False)
check("dry run: counts every place with no zone, writes nothing", dry["without_zone"] == 8 and dry["filled"] == 0 and all(not s.get("locations", i).get("time_zone") for i in (co, az, inn, evv)), dry)
check("dry run: fillable is every place with a ZIP the table knows, plus Colorado places without one", dry["fillable"] == 7, dry)
check("dry run lists only the places it cannot work out", sorted(x["name"] for x in dry["needs_a_person"]) == ["Street only"] and dry["needs_count"] == 1, dry["needs_a_person"])
done = place_zones.run(s, A, apply=True)
want = {co: "America/Denver", az: "America/Phoenix", inn: "America/New_York", evv: "America/Chicago", navajo: "America/Denver", co_nozip: "America/Denver", ny: "America/New_York"}
check("apply fills them all from their ZIP (Arizona, both Indiana zones, Navajo Nation, Colorado without a ZIP)", done["filled"] == 7 and all(s.get("locations", i)["time_zone"] == z for i, z in want.items()), done)
check("a place that has a zone is never touched", s.get("locations", kept)["time_zone"] == "America/Denver")
check("a second run finds only the one a person must fix", place_zones.run(s, A)["without_zone"] == 1)

K = "k" * 16 + "Z" * 16 + "-browser-test-key"
def door(body): return handle_admin("POST", "Bearer " + K, body, K, "v", s, make_failure_limiter(), datetime.now(timezone.utc))
r = door(b'{"collection":"locations","op":"fix_place_zones","args":{"apply":false}}')
check("through the admin door (the key is a super admin): a dry run answers with the list", r.status == 200 and r.body["data"]["without_zone"] == 1 and r.body["data"]["applied"] is False and "fillable" in r.body["data"], (r.status, r.body))
check("a bad argument is refused", door(b'{"collection":"locations","op":"fix_place_zones","args":{"apply":"yes"}}').status == 400 and door(b'{"collection":"locations","op":"fix_place_zones","args":{"x":1}}').status == 400)
check("without the key: 401", handle_admin("POST", "Bearer wrong", b'{"collection":"locations","op":"fix_place_zones","args":{}}', K, "v", s, make_failure_limiter(), datetime.now(timezone.utc)).status == 401)

# ---- safety net: the venue's place gets its zone from its ZIP the moment a class needs it (op ensure_zone, venues)
from crud import venues_service as VS  # noqa: E402
from crud import location_links_crud as LKS  # noqa: E402
def venue_at(name, place_id):
    v = VS.create(s, {"name": name, "slug": name.lower().replace(" ", "_"), "status": "inactive", "is_public_venue": False, "is_accessible": True, "allows_minors": True, "allows_animals": False, "rooms": []}, A)
    assert v.ok, v.problems
    lk = LKS.create(s, {"subject_type": "venue", "subject_id": v.data["id"], "location_id": place_id, "relationship": "operates_at", "is_primary": True}, A); assert lk.ok, lk.problems
    return v.data["id"]
zoneless = old("Zoneless Library", "TX", "77437")
vz = venue_at("Zoneless Library", zoneless)
r = door(('{"collection":"venues","op":"ensure_zone","args":{"id":"%s"}}' % vz).encode())
check("ensure_zone: a venue whose place has a ZIP but no zone gets the zone, saved on the place", r.status == 200 and r.body["data"]["time_zone"] == "America/Chicago" and s.get("locations", zoneless)["time_zone"] == "America/Chicago", r.body)
check("ensure_zone: asking again changes nothing", door(('{"collection":"venues","op":"ensure_zone","args":{"id":"%s"}}' % vz).encode()).body["data"]["time_zone"] == "America/Chicago")
nz = venue_at("Nowhere Venue", nozip)
check("ensure_zone: a place with no ZIP answers null, nothing guessed", door(('{"collection":"venues","op":"ensure_zone","args":{"id":"%s"}}' % nz).encode()).body["data"]["time_zone"] is None and not s.get("locations", nozip).get("time_zone"))
check("ensure_zone: an unknown venue is not found", door(b'{"collection":"venues","op":"ensure_zone","args":{"id":"00000000-0000-4000-8000-000000000000"}}').status == 404)

print("\nFAILED: %d" % len(fails) if fails else "\nOK: all place-zone tests pass"); sys.exit(1 if fails else 0)
