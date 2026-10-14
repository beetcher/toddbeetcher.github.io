#!/usr/bin/env python3
"""In-memory tests for the venue GPS lookup (crud/geocoder.py and venues_service.find_gps) with a FAKE geocoder: no network.
Run from enjoy_router/:  python3 run_gps_tests.py  (-v lists every check)."""
import pathlib
import sys
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import geocoder  # noqa: E402
from crud import locations_crud as L  # noqa: E402
from crud import venues_service as VS  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402

START = datetime(2026, 10, 13, 12, 0, 0, tzinfo=timezone.utc)
clock = [0]
fails, total = [], 0
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


calls = []
mode = ["found"]


def fake(address):
    calls.append(address)
    if mode[0] == "found":
        return (40.0, -105.0)
    if mode[0] == "boom":
        raise RuntimeError("down")
    return None


ADDR = {"street_number": "1", "street": "Main St", "locality": "Louisville", "region": "CO", "postal_code": "80027", "country": "US"}
s = MemoryDocStore("")


def new_venue(slug, public=True, address=ADDR):
    return VS.create_with_place(s, {"name": slug, "slug": slug, "status": "inactive", "is_public_venue": public}, ACT, address=address, now=tick())


def geoms(venue):
    return VS.get(s, venue["id"], expand=True).data["place"]


# ---- the address line
check("one_line builds 'number street, town, ST zip'", geocoder.one_line(ADDR) == "1 Main St, Louisville, CO 80027")
check("one_line is empty without a street", geocoder.one_line({**ADDR, "street": None}) == "")
check("one_line is empty without a town", geocoder.one_line({k: v for k, v in ADDR.items() if k != "locality"}) == "")
check("the lookup is off by default (None), so tests never touch the network", geocoder.lookup is None)

# ---- off: nothing happens, nothing breaks
v = new_venue("off_one").data
check("with the lookup off, create_with_place still works and has no GPS", v["place"]["has_gps"] is False)
r = VS.find_gps(s, v["id"], ACT, now=tick())
check("find_gps with the lookup off says skipped_off", r.ok and r.data["gps"] == "skipped_off")

geocoder.lookup = fake
# ---- found on create
calls.clear()
v = new_venue("found_one").data
check("create_with_place with an address looks up GPS once", len(calls) == 1 and calls[0]["street"] == "Main St", calls)
pl = geoms(v)
check("the place now has GPS, marked looked up", pl["has_gps"] is True and pl["gps_source"] == "looked_up", pl)
loc = L.get(s, pl["location_id"]).data
g = loc["geometries"][0]
check("saved as a center point, GeoJSON lon then lat, source geocoder, dated", g["role"] == "center" and g["geometry"] == {"type": "Point", "coordinates": [-105.0, 40.0]} and g["source"] == "geocoder" and g["as_of"] == "2026-10-13", g)

# ---- not found / failure never block the save
mode[0] = "none"
v2 = new_venue("nomatch_one").data
check("no match: the venue is still saved, with no GPS", v2["id"] and geoms(v2)["has_gps"] is False)
r = VS.find_gps(s, v2["id"], ACT, now=tick())
check("find_gps says no_match", r.ok and r.data["gps"] == "no_match")
mode[0] = "boom"
v3 = new_venue("boom_one").data
check("a crash in the lookup never fails the save", v3["id"] and geoms(v3)["has_gps"] is False)
r = VS.find_gps(s, v3["id"], ACT, now=tick()) if False else None

# ---- private venues are skipped
mode[0] = "found"; calls.clear()
v4 = new_venue("private_one", public=False).data
check("a non-public venue is never sent to the lookup", not calls and geoms(v4)["has_gps"] is False)
r = VS.find_gps(s, v4["id"], ACT, now=tick())
check("find_gps says skipped_not_public", r.ok and r.data["gps"] == "skipped_not_public" and not calls)

# ---- an entered point is kept
v5 = new_venue("manual_one").data   # got a looked-up point
loc5 = geoms(v5)["location_id"]
VS_up = L.update(s, loc5, {"geometries": [{"role": "center", "geometry": {"type": "Point", "coordinates": [-104.9, 39.9]}, "source": "map_click"}]}, ACT, now=tick())
check("setup: an entered point replaced it", VS_up.ok and geoms(v5)["gps_source"] == "entered", VS_up.problems if not VS_up.ok else "")
calls.clear()
r = VS.find_gps(s, v5["id"], ACT, now=tick())
check("find_gps keeps an entered point (skipped_entered) and does not call the lookup", r.ok and r.data["gps"] == "skipped_entered" and not calls)
check("the entered point is untouched", L.get(s, loc5).data["geometries"][0]["geometry"]["coordinates"] == [-104.9, 39.9])
# an entered point with no source at all counts as entered too
L.update(s, loc5, {"geometries": [{"role": "center", "geometry": {"type": "Point", "coordinates": [-104.9, 39.9]}}]}, ACT, now=tick())
check("a point with no source counts as entered", VS.find_gps(s, v5["id"], ACT, now=tick()).data["gps"] == "skipped_entered")

# ---- refresh replaces only a looked-up point
v6 = new_venue("refresh_one").data
loc6 = geoms(v6)["location_id"]
mode[0] = "found"
fake_pt = [(41.0, -106.0)]
geocoder.lookup = lambda a: fake_pt[0]
r = VS.find_gps(s, v6["id"], ACT, now=tick())
check("a looked-up point is refreshed in place (one point, new coordinates)", r.data["gps"] == "found" and len(L.get(s, loc6).data["geometries"]) == 1 and L.get(s, loc6).data["geometries"][0]["geometry"]["coordinates"] == [-106.0, 41.0])
geocoder.lookup = fake

# ---- a place with no street address
pobox = L.create(s, {"name": "Box only", "addresses": [{"usage": "po_box", "po_box": "12", "locality": "Louisville", "region": "CO", "postal_code": "80027", "country": "US"}]}, ACT, now=tick())
check("setup: a place with only a PO box", pobox.ok, pobox.problems if not pobox.ok else "")
v7 = VS.create_with_place(s, {"name": "nostreet_one", "slug": "nostreet_one", "status": "inactive", "is_public_venue": True}, ACT, location_id=pobox.data["id"], now=tick())
check("setup: venue on that place", v7.ok, v7.problems if not v7.ok else "")
check("a place with no street address is skipped, not guessed", VS.find_gps(s, v7.data["id"], ACT, now=tick()).data["gps"] == "skipped_no_address")

# ---- set_place looks up the new place
v8 = new_venue("mover_one").data
calls.clear()
r = VS.set_place(s, v8["id"], ACT, address={**ADDR, "street": "9 New Rd"}, now=tick())
check("moving a venue looks up its new place", r.ok and len(calls) == 1 and calls[0]["street"] == "9 New Rd" and r.data["place"]["has_gps"] is True, calls)

# ---- unknown venue
r = VS.find_gps(s, "00000000-0000-4000-8000-000000000000", ACT, now=tick())
check("find_gps on an unknown venue is not_found", not r.ok)

# ---- the Census response parser (no network: a fake urlopen)
import io, json, urllib.request  # noqa: E402
real = urllib.request.urlopen


def serve(payload):
    return lambda url, timeout=0: io.BytesIO(json.dumps(payload).encode())


urllib.request.urlopen = serve({"result": {"addressMatches": [{"coordinates": {"x": -105.13, "y": 39.97}}]}})
check("census_lookup reads x as longitude and y as latitude", geocoder.census_lookup(ADDR) == (39.97, -105.13))
urllib.request.urlopen = serve({"result": {"addressMatches": []}})
check("census_lookup: no matches gives None", geocoder.census_lookup(ADDR) is None)
urllib.request.urlopen = serve({"unexpected": 1})
check("census_lookup: an odd answer gives None", geocoder.census_lookup(ADDR) is None)
urllib.request.urlopen = serve({"result": {"addressMatches": [{"coordinates": {"x": -500, "y": 39.97}}]}})
check("census_lookup: an impossible coordinate gives None", geocoder.census_lookup(ADDR) is None)


def boom(url, timeout=0):
    raise TimeoutError("slow")


urllib.request.urlopen = boom
check("census_lookup: a timeout gives None, not an error", geocoder.census_lookup(ADDR) is None)
urllib.request.urlopen = real
check("census_lookup without a street makes no request", geocoder.census_lookup({"locality": "X", "region": "CO"}) is None)

print(f"{'OK' if not fails else 'FAILED'}: {total - len(fails)}/{total} checks")
sys.exit(1 if fails else 0)
