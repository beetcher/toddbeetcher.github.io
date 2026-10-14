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

print(f"{'OK' if not fails else 'FAILED'}: {total - len(fails)}/{total} checks")
sys.exit(1 if fails else 0)
