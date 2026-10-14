#!/usr/bin/env python3
"""In-memory tests for the public curriculum list (public_curriculums.py). Run from enjoy_router/:  python3 run_public_curriculums_tests.py  (-v lists every check)."""
import pathlib
import sys
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import curriculums_crud as C  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from public_curriculums import handle_public_curriculums, public_list  # noqa: E402
from ratelimit import RateLimiter  # noqa: E402

START = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)
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


def cur(slug, title, status="active", tagline=None):
    data = {"slug": slug, "title": title, "status": status, "description": "Private notes " + slug, "notes": "internal " + slug}
    if tagline:
        data["tagline"] = tagline
    r = C.create(s, data, "user:todd", now=tick())
    assert r.ok, r.problems
    return r.data


z = cur("zeta", "Zeta Basics", tagline="Slow and steady.")
a = cur("alpha", "Alpha Start")
cur("retired", "Retired Course", status="inactive")
gone = cur("gone", "Gone Course")
C.soft_delete(s, gone["id"], "user:todd", now=tick())

got = public_list(s)
check("only active curriculums, sorted by title", [c["title"] for c in got] == ["Alpha Start", "Zeta Basics"], str(got))
check("an item carries id and title, plus tagline when there is one", got[1] == {"id": z["id"], "title": "Zeta Basics", "tagline": "Slow and steady."}, str(got[1]))
check("a curriculum with no tagline is returned without one", got[0] == {"id": a["id"], "title": "Alpha Start"}, str(got[0]))
check("nothing else leaks (no slug, description, notes, status)", all(set(c) <= {"id", "title", "tagline"} for c in got))
check("an inactive curriculum is not listed", "Retired Course" not in [c["title"] for c in got])
check("a deleted curriculum is not listed", "Gone Course" not in [c["title"] for c in got])
check("an empty store gives an empty list", public_list(MemoryDocStore("")) == [])

lim = RateLimiter(rules=((600, 3),))
r = handle_public_curriculums("GET", "v1", s, lim, START)
check("GET answers 200 with the list and a cache header", r.status == 200 and r.body["ok"] and len(r.body["data"]["curriculums"]) == 2 and "max-age" in r.headers["Cache-Control"])
check("POST is refused with 405", handle_public_curriculums("POST", "v1", s, lim, START).status == 405)
lim2 = RateLimiter(rules=((600, 2),))
codes = [handle_public_curriculums("GET", "v2", s, lim2, START).status for _ in range(3)]
check("the rate limit refuses the third call", codes == [200, 200, 429], str(codes))


class Broken:
    def __getattr__(self, name):
        raise RuntimeError("boom")


r = handle_public_curriculums("GET", "v3", Broken(), RateLimiter(rules=((600, 5),)), START)
check("a storage failure gives a plain 500 that reveals nothing", r.status == 500 and "boom" not in str(r.body), str(r.body))

if fails:
    print(f"FAILED {len(fails)} of {total}: " + "; ".join(fails))
    sys.exit(1)
print(f"OK: {total} checks passed")
