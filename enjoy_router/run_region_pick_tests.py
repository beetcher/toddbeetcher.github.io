#!/usr/bin/env python3
"""In-memory tests for P-61: the public region list, the venue list filtered by region, and a request placed by its region.
Run from enjoy_router/:  python3 run_region_pick_tests.py  (-v lists every check)."""
import pathlib
import sys
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from access.places import zip_of_request  # noqa: E402
from crud import venues_service as VS  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from public_regions import handle_public_regions, public_list as regions  # noqa: E402
from public_venues import handle_public_venues, public_list as venues  # noqa: E402
from ratelimit import RateLimiter  # noqa: E402

START = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)
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


def area(i, kind, name, state="CO", active=True, zips=None, deleted=False, state_name=None):
    d = {"id": i, "kind": kind, "name": state_name or name, "state_code": state, "is_active": active, "schema_version": 1}
    if kind == "region":
        d["name"] = name
        d["zip_codes"] = zips or []
    if deleted:
        d["deleted_at"] = "2026-09-01T00:00:00Z"
    s.create("discovery_areas", i, d)


area("s-co", "state", "Colorado", "CO")
area("s-ut", "state", "Utah", "UT", active=False)
area("s-az", "state", "Arizona", "AZ")
area("r-bou", "region", "Boulder", "CO", zips=["80301", "80027"])
area("r-den", "region", "Denver", "CO", zips=["80202"])
area("r-off", "region", "Switched off", "CO", active=False, zips=["80401"])
area("r-gone", "region", "Deleted", "CO", zips=["80501"], deleted=True)
area("r-slc", "region", "Salt Lake", "UT", zips=["84101"])
area("r-phx", "region", "Phoenix", "AZ", zips=["85001"])

got = regions(s)
check("only live regions in live states, by state then region name",
      [(r["state_name"], r["name"]) for r in got] == [("Arizona", "Phoenix"), ("Colorado", "Boulder"), ("Colorado", "Denver")], str(got))
check("each item carries id, name, state_code, state_name only", all(set(r) == {"id", "name", "state_code", "state_name"} for r in got))
check("no ZIP list leaks", all("zip_codes" not in r for r in got))
check("an empty store gives an empty list", regions(MemoryDocStore("")) == [])
lim = RateLimiter(rules=((600, 2),))
check("GET answers 200", handle_public_regions("GET", "v1", s, lim, START).status == 200)
check("POST is refused with 405", handle_public_regions("POST", "v1", s, lim, START).status == 405)
check("the rate limit refuses the third call", handle_public_regions("GET", "v1", s, lim, START).status in (200, 429)
      and handle_public_regions("GET", "v1", s, lim, START).status == 429)

ADDR = lambda z: {"street": "1 Main St", "locality": "Town", "region": "CO", "postal_code": z, "country": "US"}


def venue(name, slug, z):
    r = VS.create_with_place(s, {"name": name, "slug": slug, "status": "inactive", "is_public_venue": True}, "user:todd", address=ADDR(z), now=tick())
    assert r.ok, r.problems
    assert VS.update(s, r.data["id"], {"status": "active"}, "user:todd", now=tick()).ok
    return r.data


vb = venue("Boulder Library", "bl", "80301")
vl = venue("Louisville Hall", "lh", "80027")
vd = venue("Denver Cafe", "dc", "80202")
venue("Golden Hall", "gh", "80401")
venue("Longmont Hall", "lm", "80501")
venue("State Hall", "sh", "80601")
check("no region: every venue", len(venues(s)) == 6)
check("Boulder region keeps only its ZIPs", sorted(v["name"] for v in venues(s, None, "r-bou")) == ["Boulder Library", "Louisville Hall"])
check("Denver region keeps only Denver", [v["name"] for v in venues(s, None, "r-den")] == ["Denver Cafe"])
check("a switched-off region gives an empty list", venues(s, None, "r-off") == [])
check("a deleted region gives an empty list", venues(s, None, "r-gone") == [])
area("s-x", "state", "Odd", "CO", zips=None)
s.create("discovery_areas", "s-odd", {"id": "s-odd", "kind": "state", "name": "Odd", "state_code": "CO", "is_active": True, "zip_codes": ["80601"]})
check("a state id used as a region gives an empty list", venues(s, None, "s-odd") == [])
check("an unknown region gives an empty list", venues(s, None, "nope") == [])
check("region and ZIP together: filtered and ranked", [v["name"] for v in venues(s, "80301", "r-bou")][0] == "Boulder Library")
r = handle_public_venues("GET", "v9", s, RateLimiter(rules=((600, 5),)), START, region_id="r-den")
check("the handler passes the region through", r.status == 200 and [v["name"] for v in r.body["data"]["venues"]] == ["Denver Cafe"])

check("a request with only a region is placed at the region's first ZIP", zip_of_request(s, {"id": "x", "region_id": "r-bou"}) == "80027")
check("a ZIP on the request wins over the region", zip_of_request(s, {"id": "x", "postal_code": "80202", "region_id": "r-bou"}) == "80202")
check("a preferred venue wins over the region", zip_of_request(s, {"id": "x", "preferred_venue_id": vd["id"], "region_id": "r-bou"}) == "80202")
check("a switched-off region still places a stored request (it was valid when sent)", zip_of_request(s, {"id": "x", "region_id": "r-off"}) == "80401")
check("a deleted region does not place", zip_of_request(s, {"id": "x", "region_id": "r-gone"}) is None)
check("a state id does not place a request", zip_of_request(s, {"id": "x", "region_id": "s-odd"}) is None)
check("no region, no ZIP: unplaced", zip_of_request(s, {"id": "x"}) is None)

print(f"{total - len(fails)}/{total} checks pass")
sys.exit(1 if fails else 0)
