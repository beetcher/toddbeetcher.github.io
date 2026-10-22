#!/usr/bin/env python3
"""In-memory tests for the public venue list (public_venues.py). Run from enjoy_router/:  python3 run_public_venues_tests.py  (-v lists every check)."""
import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import venues_service as VS  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from public_venues import handle_public_venues, public_list  # noqa: E402
from ratelimit import RateLimiter  # noqa: E402

START = datetime(2026, 10, 13, 12, 0, 0, tzinfo=timezone.utc)
clock = [0]
fails, total = [], 0


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


s = MemoryDocStore("")
ADDR = lambda town: {"street": "1 Main St", "locality": town, "region": "CO", "postal_code": "80027", "country": "US"} if town else {"street": "1 Main St", "region": "CO", "country": "US"}


def venue(name, slug, status, public, town="Louisville"):
    r = VS.create_with_place(s, {"name": name, "slug": slug, "status": "inactive", "is_public_venue": public}, "user:todd", address=ADDR(town), now=tick())
    assert r.ok, r.problems
    if status == "active":
        u = VS.update(s, r.data["id"], {"status": "active"}, "user:todd", now=tick())
        assert u.ok, u.problems
    return r.data


b = venue("Boulder Library", "boulder_library", "active", True, "Boulder")
a = venue("Aspen Hall", "aspen_hall", "active", True, "Louisville")
venue("Idea Cafe", "idea_cafe", "inactive", True)
venue("Private Studio", "private_studio", "active", False)
nt = venue("No Town Park", "no_town_park", "active", True, None)
gone = venue("Deleted Hall", "deleted_hall", "active", True)
VS.soft_delete(s, gone["id"], "user:todd", now=tick())

got = public_list(s)
names = [v["name"] for v in got]
check("only active public venues, sorted by name", names == ["Aspen Hall", "Boulder Library", "No Town Park"], str(names))
check("each item carries id, name and town only", got[0] == {"id": a["id"], "name": "Aspen Hall", "town": "Louisville"}, str(got[0]))
check("town comes from the venue's place", got[1]["town"] == "Boulder")
check("a venue with no town is returned with name alone", got[2] == {"id": nt["id"], "name": "No Town Park"}, str(got[2]))
check("nothing else leaks (no address, slug, status)", all(set(v) <= {"id", "name", "town"} for v in got))
check("an empty store gives an empty list", public_list(MemoryDocStore("")) == [])

lim = RateLimiter(rules=((600, 3),))
r = handle_public_venues("GET", "v1", s, lim, START)
check("GET answers 200 with the list and a cache header", r.status == 200 and r.body["ok"] and len(r.body["data"]["venues"]) == 3 and "max-age" in r.headers["Cache-Control"])
check("POST is refused with 405", handle_public_venues("POST", "v1", s, lim, START).status == 405)
lim2 = RateLimiter(rules=((600, 2),))
codes = [handle_public_venues("GET", "v2", s, lim2, START).status for _ in range(3)]
check("the rate limit refuses the third call", codes == [200, 200, 429], str(codes))
check("a different visitor is counted separately", handle_public_venues("GET", "v3", s, lim2, START).status == 200)


class Boom:
    def query(self, *a, **k):
        raise RuntimeError("x")


r = handle_public_venues("GET", "v4", Boom(), RateLimiter(rules=((600, 5),)), START)
check("a crash gives a plain 500 that reveals nothing", r.status == 500 and "x" not in json.dumps(r.body).replace("Could not load the list.", ""))


# ---- ranking by ZIP
from crud import locations_crud as L
from crud import location_links_crud as H


def venue_at(name, slug, zip_code, gps=None, public=True):
    addr = {"street": "1 Main St", "locality": "Town", "region": "CO", "postal_code": zip_code, "country": "US", "usage": "civic"}
    r = VS.create_with_place(s, {"name": name, "slug": slug, "status": "inactive", "is_public_venue": public}, "user:todd", address={k: v for k, v in addr.items() if k != "usage"}, now=tick())
    assert r.ok, r.problems
    if gps:
        loc = r.data["place"]["location_id"]
        u = L.update(s, loc, {"geometries": [{"role": "center", "geometry": {"type": "Point", "coordinates": [gps[1], gps[0]]}}]}, "user:todd", now=tick())
        assert u.ok, u.problems
    assert VS.update(s, r.data["id"], {"status": "active"}, "user:todd", now=tick()).ok
    return r.data


r2 = MemoryDocStore("")
s_main = s
s = r2
near = venue_at("Near Louisville", "near_lou", "80027")
mid = venue_at("Mid Denver", "mid_den", "80202")
far = venue_at("Far Grand Junction", "far_gj", "81501")
gps = venue_at("Gps Boulder Spot", "gps_bou", "81501", gps=(40.015, -105.27))   # ZIP says Grand Junction, GPS says Boulder
nopos = venue_at("Nowhere Hall", "nowhere", "99999")
def area(i, kind, name, state="CO", active=True, zips=None, deleted=False):
    d = {"id": i, "kind": kind, "name": name, "state_code": state, "is_active": active, "schema_version": 1}
    if kind == "region":
        d["zip_codes"] = zips or []
    if deleted:
        d["deleted_at"] = "2026-09-01T00:00:00Z"
    s.create("discovery_areas", i, d)


area("s-co", "state", "Colorado")
area("s-ca", "state", "California", "CA")
area("r-all", "region", "Everywhere test region", "CO", zips=["80301", "80027", "80202", "81501", "99999", "90210", "90211"])
ranked = public_list(s, "80301")
nm = [v["name"] for v in ranked]
check("a ZIP puts the nearest first (Boulder area before Denver before Grand Junction)", nm[:4] == ["Gps Boulder Spot", "Near Louisville", "Mid Denver", "Far Grand Junction"], str(nm))
check("a venue with no known position goes last, with no miles", nm[-1] == "Nowhere Hall" and "miles" not in ranked[-1], str(ranked[-1]))
check("GPS beats the ZIP centre (miles are small for the GPS venue)", ranked[0]["miles"] < 5, str(ranked[0]))
check("miles are numbers with one decimal", all(isinstance(v["miles"], float) for v in ranked[:-1]))
check("Louisville is about 12 miles from 80301", 5 < ranked[1]["miles"] < 20, str(ranked[1]))
check("no ZIP: alphabetical and no miles", [v["name"] for v in public_list(s)] == sorted(v["name"] for v in public_list(s)) and all("miles" not in v for v in public_list(s)))
check("a ZIP no active region holds lists nothing", public_list(s, "80999") == [])
check("a ZIP in another state is ranked too (from the US table), far from Colorado", all("miles" in v and v["miles"] > 500 for v in public_list(s, "90210") if v["name"] != "Nowhere Hall"))
la = venue_at("Beverly Hall", "bev", "90211")
check("a venue in the visitor's own state comes first for that state's ZIP", public_list(s, "90210")[0]["name"] == "Beverly Hall" and public_list(s, "90210")[0]["miles"] < 5, str(public_list(s, "90210")[0]))
check("a ZIP that is not five digits is ignored", all("miles" not in v for v in public_list(s, "9021")))
check("junk in the ZIP is ignored", all("miles" not in v for v in public_list(s, "80301; drop")))
res = handle_public_venues("GET", "z1", s, RateLimiter(rules=((600, 5),)), START, zip_code="80301")
check("the handler passes the ZIP through", res.status == 200 and "miles" in res.body["data"]["venues"][0])
s = s_main

# ---- a ZIP means its own active region, and nothing else
s = MemoryDocStore("")
area("s-co", "state", "Colorado")
area("s-ut", "state", "Utah", "UT", active=False)
area("r-bou", "region", "Boulder", "CO", zips=["80301", "80027"])
area("r-den", "region", "Denver", "CO", zips=["80202", "80203", "80204"])
area("r-off", "region", "Switched off", "CO", active=False, zips=["80401"])
area("r-gone", "region", "Deleted", "CO", zips=["80501"], deleted=True)
area("r-ut", "region", "Salt Lake", "UT", zips=["84101"])
area("r-empty", "region", "Empty", "CO", zips=["80601"])
venue_at("Boulder Lib", "bou_lib", "80301")
venue_at("Louisville Hall", "lou_hall", "80027")
for i in range(8):
    venue_at("Denver Spot %d" % (i + 1), "den_%d" % i, ["80202", "80203", "80204"][i % 3])
venue_at("Golden Cafe", "golden", "80401")      # in the switched-off region
venue_at("Fort Collins Cafe", "fc", "80501")    # in the deleted region
venue_at("Salt Lake Cafe", "slc", "84101")      # in the inactive state
venue_at("Lone Pine", "lone", "81999")          # in no region
res = handle_public_venues("GET", "q1", s, RateLimiter(rules=((600, 50),)), START, zip_code="80301")
d = res.body["data"]
check("a ZIP lists only its region's venues", {v["name"] for v in d["venues"]} == {"Boulder Lib", "Louisville Hall"}, str(d))
check("nearest first: the ZIP's own venue before the next town", [v["name"] for v in d["venues"]][0] == "Boulder Lib", str(d["venues"]))
check("the reply says covered and names the region", d["covered"] is True and d["region"]["name"] == "Boulder", str(d))
d = handle_public_venues("GET", "q2", s, RateLimiter(rules=((600, 50),)), START, zip_code="80203").body["data"]
check("a big region lists every venue in it (the page shows five and a More list)", len(d["venues"]) == 8 and d["covered"] is True, str(len(d["venues"])))
check("another region's venues never appear", all(v["name"].startswith("Denver") for v in d["venues"]))
for label, z in (("no region holds it", "81999"), ("the region is switched off", "80401"), ("the region is deleted", "80501"), ("the region's state is switched off", "84101"), ("not a ZIP anyone knows", "12345")):
    d = handle_public_venues("GET", "q3", s, RateLimiter(rules=((600, 50),)), START, zip_code=z).body["data"]
    check("not covered: " + label, d["venues"] == [] and d["covered"] is False and "region" not in d, str(d))
d = handle_public_venues("GET", "q4", s, RateLimiter(rules=((600, 50),)), START, zip_code="80601").body["data"]
check("a covered ZIP in a region with no venues: covered, empty list", d["covered"] is True and d["venues"] == [], str(d))
d = handle_public_venues("GET", "q5", s, RateLimiter(rules=((600, 50),)), START, zip_code="80301", region_id="r-den").body["data"]
check("a ZIP wins over a region sent with it", {v["name"] for v in d["venues"]} == {"Boulder Lib", "Louisville Hall"}, str(d))
d = handle_public_venues("GET", "q6", s, RateLimiter(rules=((600, 50),)), START, region_id="r-bou").body["data"]
check("a region alone still works and carries no covered flag", {v["name"] for v in d["venues"]} == {"Boulder Lib", "Louisville Hall"} and "covered" not in d, str(d))
d = handle_public_venues("GET", "q7", s, RateLimiter(rules=((600, 50),)), START, zip_code="8030").body["data"]
check("a ZIP that is not five digits is ignored: everything, no covered flag", "covered" not in d and len(d["venues"]) >= 12, str(d)[:120])
check("no ZIP, no region: unchanged, everything, no covered flag", "covered" not in handle_public_venues("GET", "q8", s, RateLimiter(rules=((600, 50),)), START).body["data"])
s = s_main

print(f"{'OK' if not fails else 'FAILED'}: {total - len(fails)}/{total} checks")
sys.exit(1 if fails else 0)
