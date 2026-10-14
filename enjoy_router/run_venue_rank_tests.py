#!/usr/bin/env python3
"""In-memory tests for the operator venue list ranked by a request's ZIP (venues_service.list with expand and near_zip,
and the admin endpoint argument). Run from enjoy_router/:  python3 run_venue_rank_tests.py  (-v lists every check)."""
import pathlib
import sys
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import venues_service as VS  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud_endpoint import handle_admin, make_failure_limiter  # noqa: E402
import json  # noqa: E402

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


def venue(name, slug, zip_code, public=True, status="active"):
    addr = {"street": "1 Main St", "locality": "Town", "region": "CO", "postal_code": zip_code, "country": "US"} if zip_code else {"street": "1 Main St", "region": "CO", "country": "US"}
    r = VS.create_with_place(s, {"name": name, "slug": slug, "status": "inactive", "is_public_venue": public}, "user:todd", address=addr, now=tick())
    assert r.ok, r.problems
    if status == "active":
        assert VS.update(s, r.data["id"], {"status": "active"}, "user:todd", now=tick()).ok
    return r.data


lou = venue("Zed Louisville Library", "lou", "80027")
bou = venue("Boulder Hall", "bou", "80301")
den = venue("Denver Den", "den", "80202", public=False)
dur = venue("Durango Hall", "dur", "81301")
nopos = venue("No Position Park", "nop", None)

got = VS.list(s, {"status": "active"}, expand=True, near_zip="80027")
names = [d["name"] for d in got.data["records"]]
check("near a Louisville ZIP: Louisville first, Boulder next, Denver after, Durango last, no-position venue at the very end",
      names == ["Zed Louisville Library", "Boulder Hall", "Denver Den", "Durango Hall", "No Position Park"], str(names))
rec = {d["name"]: d for d in got.data["records"]}
check("each record with a position carries miles", all("miles" in rec[n] for n in names[:4]) and "miles" not in rec["No Position Park"])
check("a venue in the same ZIP is under 1 mile", rec["Zed Louisville Library"]["miles"] < 1, str(rec["Zed Louisville Library"].get("miles")))
check("non-public venues are in the operator list too", "Denver Den" in names)
check("a record is still the full expanded venue (place included)", rec["Boulder Hall"].get("place", {}).get("address", {}).get("postal_code") == "80301")

plain = VS.list(s, {"status": "active"}, expand=True)
check("no near_zip: alphabetical, no miles", [d["name"] for d in plain.data["records"]] == sorted(names, key=str.lower) and not any("miles" in d for d in plain.data["records"]))
for bad in ("99999", "abcde", "", "9021"):
    r = VS.list(s, {"status": "active"}, expand=True, near_zip=bad)
    check(f"an unknown or invalid ZIP {bad!r} is ignored: alphabetical, no miles", r.ok and not any("miles" in d for d in r.data["records"]) and [d["name"] for d in r.data["records"]] == sorted(names, key=str.lower))
check("near_zip without expand is refused", not VS.list(s, {"status": "active"}, near_zip="80027").ok)

KEY = "k" * 16 + "Z" * 16 + "-rank-test-key"
lim = make_failure_limiter()
def admin(args, coll="venues"):
    body = json.dumps({"op": "list", "collection": coll, "args": args}).encode()
    return handle_admin("POST", "Bearer " + KEY, body, KEY, "v", s, lim, START)
r = admin({"expand": True, "near_zip": "80301", "filters": {"status": "active"}})
check("the admin endpoint accepts near_zip for venues", r.status == 200 and r.body["data"]["records"][0]["name"] == "Boulder Hall", str(r.body)[:200])
r = admin({"expand": True, "near_zip": 80301})
check("a non-text near_zip is refused", r.status == 400, str(r.status))
r = admin({"expand": True, "near_zip": "80301"}, coll="curriculums")
check("near_zip on another collection is refused", r.status == 400, str(r.status))

print(f"\n{'OK' if not fails else 'FAILED'}: {total - len(fails)}/{total} checks" + ("" if not fails else "  failed: " + "; ".join(fails)))
sys.exit(1 if fails else 0)
