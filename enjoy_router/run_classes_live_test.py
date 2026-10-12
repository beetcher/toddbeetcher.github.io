#!/usr/bin/env python3
"""Live test of the class changes (curriculum_id, series_id, session_number) on the deployed functions. Run from enjoy_router/:  python3 run_classes_live_test.py
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

import time, uuid
tag = str(int(time.time()))
BASE_C = {"class_type": "private", "program_slug": "launch", "status": "identified", "is_public": False, "capacity_minimum": 1, "capacity_target": 2, "capacity_max": 3}
r = T("curriculums", "create", data={"slug": "livecls_" + tag, "title": "Livetest series", "session_count": 2, "minutes_per_session": 60})
cid = data(r).get("id"); check("curriculum for the test", r[0] == 200 and cid, r)
sid = str(uuid.uuid4()); made = []
def mk(slug, **kw):
    r = T("scheduled_classes", "create", data={**BASE_C, "title": "Live " + slug, "slug": slug + "_" + tag, **kw})
    if r[0] == 200: made.append(data(r)["id"])
    return r
r1 = mk("s1", curriculum_id=cid, series_id=sid, session_number=1); check("class with curriculum, series and session 1", r1[0] == 200, r1)
r = mk("bad_cur", curriculum_id=str(uuid.uuid4())); check("unknown curriculum refused", r[0] == 400 and "curriculum_id" in json.dumps(r[1]), r)
r = mk("no_series", session_number=2); check("session number without a series refused", r[0] == 400 and "series_id" in json.dumps(r[1]), r)
r = mk("dup", series_id=sid, session_number=1); check("same session number refused", r[0] == 400 and "duplicate" in json.dumps(r[1]), r)
r2 = mk("s2", series_id=sid, session_number=2); check("session 2 ok", r2[0] == 200, r2)
if r2[0] == 200:
    r = T("scheduled_classes", "update", id=data(r2)["id"], changes={"session_number": 1}); check("update to a taken number refused", r[0] == 400, r)
    r = T("scheduled_classes", "get", id=data(r2)["id"]); check("fields stored", data(r).get("series_id") == sid and data(r).get("session_number") == 2, r)
for i in made: T("scheduled_classes", "soft_delete", id=i)
T("curriculums", "soft_delete", id=cid)
print(f"\n{total - len(fails)}/{total} checks passed")
print("OK" if not fails else "FAILED: " + ", ".join(fails))
sys.exit(1 if fails else 0)
