#!/usr/bin/env python3
"""Live test of the public curriculum list on the deployed functions. Run from enjoy_router/:  python3 run_public_curriculums_live_test.py
Reads the public list (no key), compares it with the real curriculums (Console door, READ only), and sends registrations that are
all refused (an unknown curriculum, a class carrying one) so nothing is stored. Creates and changes nothing. The key is read from
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

st, body, hdr = http(BASE + "enjoy_public_curriculums", method="GET")
check("GET the public list: 200 and ok", st == 200 and body.get("ok") is True, (st, body))
items = (body.get("data") or {}).get("curriculums")
check("the list is an array", isinstance(items, list), body)
items = items or []
check("every item has only id, title and optional tagline", all(set(c) <= {"id", "title", "tagline"} and "id" in c and "title" in c for c in items), items[:3])
check("sorted by title", [c["title"] for c in items] == sorted(c["title"] for c in items), [c["title"] for c in items])
check("a cache header is set", "max-age" in (hdr.get("Cache-Control") or hdr.get("cache-control") or ""), hdr)

st2, real, _ = http(BASE + "enjoy_admin", {"collection": "curriculums", "op": "list", "args": {"limit": 200}},
                    {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}, "POST")
recs = ((real.get("data") or {}).get("records")) or []
expect = sorted(c["id"] for c in recs if c.get("status") == "active")
check("exactly the active curriculums are listed (%d)" % len(expect), sorted(c["id"] for c in items) == expect, (len(items), len(expect)))
check("no inactive curriculum leaks", not ({c["id"] for c in items} & {c["id"] for c in recs if c.get("status") != "active"}))
check("POST is refused", http(BASE + "enjoy_public_curriculums", {}, {"Content-Type": "application/json"}, "POST")[0] == 405)

tests = json.loads((HERE.parent / "schemas" / "examples" / "registration_request.test_records.json").read_text())["tests"]
small = next(t for t in tests if t["name"] == "t47_private_small_ask")
base = json.loads((HERE.parent / "schemas" / "examples" / "registration_request.test_records.json").read_text())["tests"][0]["request"]
base = {k: v for k, v in base.items() if k not in small["remove"]}
base.update(small["override"])
bad = {**base, "idempotency_key": str(uuid.uuid4()), "email": "livetest-curriculum@example.com", "curriculum_id": str(uuid.uuid4())}
st3, b3, _ = http(BASE + "enjoy_registration_request", bad, {"Content-Type": "application/json"}, "POST")
check("a curriculum that does not exist is refused: 404 curriculum_not_found", st3 == 404 and (b3.get("error") or {}).get("code") == "curriculum_not_found", (st3, b3))
cls = next(t for t in tests if t["name"] == "t52_class_with_curriculum")
by = {t["name"]: t for t in tests}
cbase = dict(by["t05_class_pick_with_space"]["request"])
cbase.update(cls["override"]); cbase["idempotency_key"] = str(uuid.uuid4()); cbase["email"] = "livetest-curriculum@example.com"
st4, b4, _ = http(BASE + "enjoy_registration_request", cbase, {"Content-Type": "application/json"}, "POST")
check("a class request carrying a curriculum is refused: 400 validation_failed", st4 == 400 and (b4.get("error") or {}).get("code") == "validation_failed", (st4, b4))

print("\n%s: %d of %d live checks passed" % ("OK" if not fails else "FAILED", total - len(fails), total))
sys.exit(1 if fails else 0)
