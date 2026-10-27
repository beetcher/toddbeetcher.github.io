#!/usr/bin/env python3
"""In-memory tests for P-93 / P-86 stage A: the public place lookup (public_zip.py).
Run from enjoy_router/:  python3 run_public_zip_tests.py  (-v lists every check)."""
import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from public_zip import handle_public_zip, lookup_zip, region_zips, state_cities  # noqa: E402
from ratelimit import RateLimiter  # noqa: E402

START = datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone.utc)
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
SECRET = "PRIVATE-NOTE-DO-NOT-LEAK"


def area(i, kind, name, state="CO", active=True, zips=None, deleted=False):
    d = {"id": i, "kind": kind, "name": name, "state_code": state, "is_active": active, "schema_version": 1,
         "notes": SECRET, "created_at": "2026-09-01T00:00:00Z", "updated_by": "someone@example.com"}
    if kind == "region":
        d["zip_codes"] = zips or []
    if deleted:
        d["deleted_at"] = "2026-09-01T00:00:00Z"
    s.create("discovery_areas", i, d)


area("s-co", "state", "Colorado", "CO")
area("s-mn", "state", "Minnesota", "MN")
area("s-ut", "state", "Utah", "UT", active=False)
area("r-bou", "region", "Boulder", "CO", zips=["80301", "80027", "80301 "])
area("r-den", "region", "Denver", "CO", zips=["80202"])
area("r-den2", "region", "Denver Metro", "CO", zips=["80202", "80203"])
area("r-off", "region", "Switched off", "CO", active=False, zips=["80401"])
area("r-gone", "region", "Deleted", "CO", zips=["80501"], deleted=True)
area("r-slc", "region", "Salt Lake", "UT", zips=["84101"])
area("r-roc", "region", "Rochester MN", "MN", zips=["55901", "55902"])

# --- ZIP lookup
d = lookup_zip(s, "80202")
check("covered ZIP: found, Denver, CO, covered, first region by name", d["found"] and d["town"] == "Denver" and d["state_code"] == "CO"
      and d["state_name"] == "Colorado" and d["covered"] is True and d["region"] == {"id": "r-den", "name": "Denver", "state_code": "CO"}, d)
d = lookup_zip(s, "55901")
check("Rochester MN ZIP: Minnesota and its region", d["found"] and d["state_code"] == "MN" and d["region"]["id"] == "r-roc" and d["town"] == "Rochester", d)
d = lookup_zip(s, " 80301 ")
check("spaces around a ZIP are tolerated", d["found"] and d["region"]["id"] == "r-bou", d)
d = lookup_zip(s, "80401")
check("ZIP in a switched-off region: found, NOT covered, no region", d["found"] and d["covered"] is False and d["region"] is None and d["town"], d)
d = lookup_zip(s, "80501")
check("ZIP in a deleted region: not covered", d["found"] and d["covered"] is False and d["region"] is None, d)
d = lookup_zip(s, "84101")
check("ZIP in a region of a switched-off state: not covered, still gets town and state", d["found"] and d["covered"] is False
      and d["state_code"] == "UT" and d["town"] == "Salt Lake City", d)
d = lookup_zip(s, "10001")
check("ZIP no region holds: town and state from the table", d["found"] and d["state_code"] == "NY" and d["covered"] is False and d["region"] is None, d)
for bad in ["", "abc", "8020", "802022", "80 202", "8020a", None, 80202, ["80202"], "00000"]:
    check(f"bad or unknown ZIP {bad!r} answers found false only", lookup_zip(s, bad) == {"found": False}, lookup_zip(s, bad))

# --- region ZIPs
r = region_zips(s, "r-bou")
check("region ZIPs: sorted, no duplicates, with towns, region ref", [x["zip"] for x in r["zips"]] == ["80027", "80301"]
      and r["region"] == {"id": "r-bou", "name": "Boulder", "state_code": "CO"} and all(x["town"] for x in r["zips"]), r)
for rid in ["r-off", "r-gone", "r-slc", "s-co", "nope", "", None, 5]:
    check(f"region {rid!r} (off, deleted, off state, not a region, unknown) gives no ZIPs", region_zips(s, rid) == {"zips": []}, region_zips(s, rid))

# --- state cities
c = state_cities("MN")
check("state cities: MN has cities with names and ZIPs, Minneapolis among them", c["state_code"] == "MN" and c["state_name"] == "Minnesota"
      and 0 < len(c["cities"]) <= 10 and any(x["name"] == "Minneapolis" and "55401" in x["zips"] for x in c["cities"]), str(c)[:200])
check("state code in lower case works", state_cities("mn")["state_code"] == "MN")
check("DC works", state_cities("DC")["state_name"] == "District of Columbia" and state_cities("DC")["cities"])
for bad in ["", "ZZ", "M", "MNN", "1A", None, 7]:
    check(f"bad state {bad!r} gives no cities", state_cities(bad) == {"cities": []}, state_cities(bad))

# --- the door
lim = RateLimiter(rules=((600, 120), (86400, 1000)))


def call(method="GET", visitor="v1", **kw):
    return handle_public_zip(method, visitor, s, lim, tick(), **kw)


res = call(zip_code="80202")
check("door: 200 ok with the ZIP reply and a short public cache", res.status == 200 and res.body["ok"] and res.body["data"]["covered"]
      and res.headers.get("Cache-Control", "").startswith("public"), res.body)
check("door: ZIP wins over region and state sent with it", call(zip_code="80202", region_id="r-bou", state_code="MN").body["data"]["zip"] == "80202")
check("door: region wins over state", "zips" in call(region_id="r-bou", state_code="MN").body["data"])
check("door: state alone", call(state_code="CO").body["data"]["state_code"] == "CO")
check("door: nothing asked answers found false, not an error", call().body == {"ok": True, "data": {"found": False}}, call().body)
check("door: bad ZIP is ok with found false, never an error", call(zip_code="abc").status == 200 and call(zip_code="abc").body["data"] == {"found": False})
check("door: POST refused 405 with Allow GET", call("POST", zip_code="80202").status == 405 and call("POST", zip_code="80202").headers.get("Allow") == "GET")
check("door: PUT and DELETE refused", call("PUT", zip_code="80202").status == 405 and call("DELETE", zip_code="80202").status == 405)

# --- break-it: nothing private leaves the server
ZIP_KEYS = {"found", "zip", "town", "state_code", "state_name", "covered", "region"}
bodies = [call(zip_code=z).body for z in ["80202", "80401", "84101", "10001", "55901", "abc"]] + [call(region_id=r).body for r in ["r-bou", "r-roc", "r-off"]] \
    + [call(state_code=x).body for x in ["CO", "MN", "ZZ"]]
dump = json.dumps(bodies)
check("break-it: no note, timestamp, e-mail or ZIP list of a region leaks in any reply", SECRET not in dump and "created_at" not in dump and "someone@example.com" not in dump
      and "zip_codes" not in dump and "updated_by" not in dump and "is_active" not in dump and "deleted_at" not in dump, dump[:200])
check("break-it: a ZIP reply holds exactly the public fields", all(set(b["data"]) <= ZIP_KEYS for b in bodies[:6]), [sorted(b["data"]) for b in bodies[:6]])
check("break-it: a ZIP reply never lists the region's other ZIPs", "80203" not in json.dumps(call(zip_code="80202").body))
check("break-it: a region ref holds only id, name, state_code", set(call(zip_code="80202").body["data"]["region"]) == {"id", "name", "state_code"})

# --- rate limit
tight = RateLimiter(rules=((600, 3), (86400, 10)))
codes = [handle_public_zip("GET", "spam", s, tight, tick(), zip_code="80202").status for _ in range(5)]
check("rate limit: the fourth request in ten minutes is refused 429 with Retry-After", codes[:3] == [200] * 3 and codes[3] == 429
      and "Retry-After" in handle_public_zip("GET", "spam", s, tight, tick(), zip_code="80202").headers, codes)
check("rate limit: another visitor is not affected", handle_public_zip("GET", "other", s, tight, tick(), zip_code="80202").status == 200)


class Boom:
    def query(self, *a, **k):
        raise RuntimeError("store down")


res = handle_public_zip("GET", "v9", Boom(), lim, tick(), zip_code="80202")
check("a failing store answers 500 server_error without internals", res.status == 500 and "store down" not in json.dumps(res.body), res.body)

print(f"{total - len(fails)}/{total} public_zip checks passed" + (f"; FAILED: {fails}" if fails else ""))
sys.exit(1 if fails else 0)
