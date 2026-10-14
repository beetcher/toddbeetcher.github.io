#!/usr/bin/env python3
"""Live test of the public venue list on the deployed functions. Run from enjoy_router/:  python3 run_public_venues_live_test.py
Reads the public list (no key), compares it with the real venues (Console door, READ only), and sends ONE registration with a
venue that does not exist to prove it is refused (nothing is stored). Creates and changes nothing. The key is read from
.env.launch-ai-workshop and never printed."""
import json, pathlib, sys, uuid, urllib.request, urllib.error

HERE = pathlib.Path(__file__).resolve().parent
BASE = "https://us-central1-launch-ai-workshop.cloudfunctions.net/"
KEY = next((l.split("=", 1)[1].strip().strip('"\'') for l in (HERE / ".env.launch-ai-workshop").read_text().splitlines() if l.startswith("ICDT_ADMIN_KEY=")), "")
if len(KEY) < 32:
    sys.exit("no admin key found")
fails, total = [], 0

def http(url, body=None, headers=None, method=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}"), dict(r.headers)
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read() or b"{}"), dict(e.headers)
        except ValueError: return e.code, {}, {}
    except Exception as e:
        return 0, {"error": type(e).__name__}, {}

def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else "  " + str(detail)[:300]))

st, body, hdr = http(BASE + "enjoy_public_venues", method="GET")
check("GET the public list: 200 and ok", st == 200 and body.get("ok") is True, (st, body))
venues = (body.get("data") or {}).get("venues")
check("the list is an array", isinstance(venues, list), body)
venues = venues or []
check("every item has only id, name and optional town", all(set(v) <= {"id", "name", "town"} and "id" in v and "name" in v for v in venues), venues[:3])
check("sorted by name", [v["name"] for v in venues] == sorted(v["name"] for v in venues), [v["name"] for v in venues])
check("a cache header is set", "max-age" in (hdr.get("Cache-Control") or hdr.get("cache-control") or ""), hdr)

st2, real, _ = http(BASE + "enjoy_admin", {"collection": "venues", "op": "list", "args": {"limit": 200}},
                    {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}, "POST")
recs = ((real.get("data") or {}).get("records")) or []
expect = sorted(v["id"] for v in recs if v.get("status") == "active" and v.get("is_public_venue") is True)
check("exactly the active public venues are listed (%d)" % len(expect), sorted(v["id"] for v in venues) == expect, (len(venues), len(expect)))
check("no inactive or private venue leaks", not ({v["id"] for v in venues} & {v["id"] for v in recs if v.get("status") != "active" or v.get("is_public_venue") is not True}))
check("POST is refused", http(BASE + "enjoy_public_venues", {}, {"Content-Type": "application/json"}, "POST")[0] == 405)

example = json.loads((HERE.parent / "schemas" / "examples" / "registration_request.test_records.json").read_text())["tests"][0]["request"]
bad = {**example, "idempotency_key": str(uuid.uuid4()), "email": "livetest-venue@example.com", "location_type": "off_site", "preferred_venue_id": str(uuid.uuid4())}
st3, b3, _ = http(BASE + "enjoy_registration_request", bad, {"Content-Type": "application/json"}, "POST")
check("a venue that does not exist is refused: 404 venue_not_found", st3 == 404 and (b3.get("error") or {}).get("code") == "venue_not_found", (st3, b3))
home = {**example, "idempotency_key": str(uuid.uuid4()), "email": "livetest-venue@example.com", "location_type": "home", "preferred_venue_id": str(uuid.uuid4())}
st4, b4, _ = http(BASE + "enjoy_registration_request", home, {"Content-Type": "application/json"}, "POST")
check("a home request with a venue is refused: 400 validation_failed", st4 == 400 and (b4.get("error") or {}).get("code") == "validation_failed", (st4, b4))

st5, z, _ = http(BASE + "enjoy_public_venues?zip=80027", method="GET")
zv = (z.get("data") or {}).get("venues") or []
check("GET with a ZIP: 200 and the same venues", st5 == 200 and sorted(v["id"] for v in zv) == expect, (st5, len(zv)))
ms = [v["miles"] for v in zv if "miles" in v]
check("with a ZIP the venues are nearest first, with miles", ms == sorted(ms) and (not zv or len(ms) >= 1), ms)
check("a venue with no known position (if any) comes last", all("miles" in v for v in zv[:len(ms)]) and all("miles" not in v for v in zv[len(ms):]))
st6, z2, _ = http(BASE + "enjoy_public_venues?zip=90210", method="GET")
check("a non-Colorado ZIP is ignored: alphabetical, no miles", st6 == 200 and all("miles" not in v for v in (z2.get("data") or {}).get("venues", [])), z2)
badzip = {**example, "idempotency_key": str(uuid.uuid4()), "email": "livetest-venue@example.com", "location_type": "home", "postal_code": "90210"}
st7, b7, _ = http(BASE + "enjoy_registration_request", badzip, {"Content-Type": "application/json"}, "POST")
check("a ZIP outside Colorado on a request is refused: 400 validation_failed", st7 == 400 and (b7.get("error") or {}).get("code") == "validation_failed", (st7, b7))

print(f"\n{'OK' if not fails else 'FAILED'}: {total - len(fails)}/{total} live checks passed")
sys.exit(1 if fails else 0)
