#!/usr/bin/env python3
"""Live test of the venue GPS lookup (US Census geocoder) on the deployed functions. Run from enjoy_router/:  python3 run_gps_live_test.py
Writes ONLY through the test door (enjoy_crud_test, collections prefixed test_) and cleans up after itself. The key is read from
.env.launch-ai-workshop and never printed. This is the one test that proves the deployed function can reach the Census service."""
import json, pathlib, sys, time, urllib.request, urllib.error

HERE = pathlib.Path(__file__).resolve().parent
BASE = "https://us-central1-launch-ai-workshop.cloudfunctions.net/"
KEY = next((l.split("=", 1)[1].strip().strip('"\'') for l in (HERE / ".env.launch-ai-workshop").read_text().splitlines() if l.startswith("ICDT_ADMIN_KEY=")), "")
if len(KEY) < 32:
    sys.exit("no admin key found")
fails, total = [], 0

def call(coll, op, **args):
    req = urllib.request.Request(BASE + "enjoy_crud_test", data=json.dumps({"collection": coll, "op": op, "args": args}).encode(),
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read() or b"{}")
        except ValueError: return e.code, {}
    except Exception as e:
        return 0, {"error": type(e).__name__}

data = lambda r: (r[1] or {}).get("data") or {}
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else "  " + str(detail)[:300]))

stamp = str(int(time.time()))
made = []
def venue(slug, address, public=True):
    r = call("venues", "create_with_place", data={"name": "GPS livetest " + slug, "slug": "gpslive_" + slug + "_" + stamp, "status": "inactive", "is_public_venue": public}, address=address)
    if r[0] == 200 and data(r).get("id"): made.append(data(r)["id"])
    return r

LIB = {"street_number": "950", "street": "Spruce St", "locality": "Louisville", "region": "CO", "postal_code": "80027", "country": "US"}
r = venue("library", LIB)
check("create a public venue at a real Louisville address", r[0] == 200, r)
pl = data(r).get("place") or {}
check("the place now has GPS, marked looked up", pl.get("has_gps") is True and pl.get("gps_source") == "looked_up", pl)
loc = call("locations", "get", id=pl.get("location_id")) if pl.get("location_id") else (0, {})
g = ((data(loc).get("geometries") or [{}])[0])
lon, lat = (g.get("geometry") or {}).get("coordinates", [0, 0])[:2]
check("the point is in Louisville, Colorado (lat 39.9 to 40.1, lon -105.3 to -105.0)", 39.9 < lat < 40.1 and -105.3 < lon < -105.0, (lat, lon))
check("it is a center point from the geocoder with a date", g.get("role") == "center" and g.get("source") == "geocoder" and bool(g.get("as_of")), g)

r2 = venue("nomatch", {"street_number": "1", "street": "Zzzzzz Nowhere Qqq", "locality": "Louisville", "region": "CO", "postal_code": "80027", "country": "US"})
check("an address the lookup cannot find still saves the venue, without GPS", r2[0] == 200 and (data(r2).get("place") or {}).get("has_gps") is False, r2)
fg = call("venues", "find_gps", id=data(r2).get("id")) if data(r2).get("id") else (0, {})
check("find_gps says no_match", fg[0] == 200 and data(fg).get("gps") == "no_match", fg)

r3 = venue("private", LIB, public=False)
check("a private space is never looked up", r3[0] == 200 and (data(r3).get("place") or {}).get("has_gps") is False, r3)
fg3 = call("venues", "find_gps", id=data(r3).get("id")) if data(r3).get("id") else (0, {})
check("find_gps says skipped_not_public", fg3[0] == 200 and data(fg3).get("gps") == "skipped_not_public", fg3)

fg1 = call("venues", "find_gps", id=data(r).get("id"))
check("find_gps again on the looked-up venue refreshes it (found)", fg1[0] == 200 and data(fg1).get("gps") == "found", fg1)

for vid in made:
    call("venues", "soft_delete", id=vid)
print(f"\n{'OK' if not fails else 'FAILED'}: {total - len(fails)}/{total} live checks passed")
sys.exit(1 if fails else 0)
