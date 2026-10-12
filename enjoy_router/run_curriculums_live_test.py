#!/usr/bin/env python3
"""Live test of the instructor and student curriculums on the deployed functions. Run from enjoy_router/:  python3 run_curriculums_live_test.py
Writes ONLY through the test door (enjoy_crud_test, collections prefixed test_) and cleans up after itself. The Console door
(enjoy_admin) is used for READS and refusals only. The key is read from .env.launch-ai-workshop and never printed."""
import json, pathlib, sys, urllib.request, urllib.error

HERE = pathlib.Path(__file__).resolve().parent
BASE = "https://us-central1-launch-ai-workshop.cloudfunctions.net/"
KEY = next((l.split("=", 1)[1].strip().strip('"\'') for l in (HERE / ".env.launch-ai-workshop").read_text().splitlines() if l.startswith("ICDT_ADMIN_KEY=")), "")
if len(KEY) < 32:
    sys.exit("no admin key found")
fails, total = [], 0

def call(fn, coll, op, **args):
    req = urllib.request.Request(BASE + fn, data=json.dumps({"collection": coll, "op": op, "args": args}).encode(),
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read() or b"{}")
        except ValueError: return e.code, {}
    except Exception as e:
        return 0, {"error": type(e).__name__}

T = lambda coll, op, **a: call("enjoy_crud_test", coll, op, **a)
A = lambda coll, op, **a: call("enjoy_admin", coll, op, **a)
data = lambda r: (r[1] or {}).get("data") or {}
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else "  " + str(detail)[:300]))

import time
r = T("curriculums", "create", data={"slug": "livetest_" + str(int(time.time())), "title": "Livetest Curriculum", "session_count": 3, "minutes_per_session": 90, "tagline": "Livetest tagline"})
check("create", r[0] == 200 and data(r).get("status") == "active", r)
cid = data(r).get("id"); slug = data(r).get("slug")
r = T("curriculums", "create", data={"slug": slug, "title": "Again"}); check("duplicate slug refused", r[0] == 400 and "duplicate" in json.dumps(r[1]), r)
r = T("curriculums", "list", filters={"status": "active"}); check("list by status", r[0] == 200 and data(r).get("count", 0) >= 1, r)
r = T("curriculums", "update", id=cid, changes={"minutes_per_session": 45}); check("update", r[0] == 200, r)
r = T("curriculums", "update", id=cid, changes={"slug": "other"}); check("slug immutable", r[0] == 400, r)
check("Console door can read", A("curriculums", "list")[0] == 200)
check("delete", T("curriculums", "soft_delete", id=cid)[0] == 200)
check("deleted is not_found", T("curriculums", "get", id=cid)[0] == 404)
print(f"\n{total - len(fails)}/{total} checks passed")
print("OK" if not fails else "FAILED: " + ", ".join(fails))
sys.exit(1 if fails else 0)
