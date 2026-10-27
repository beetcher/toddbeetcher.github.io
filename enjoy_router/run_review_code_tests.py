#!/usr/bin/env python3
"""Tests for the 24-hour review code (REVIEW_CODE_GUIDE.md): a super admin sets ONE temporary code; it signs in as the view-only Global Inspector.
Run from enjoy_router/:  python3 run_review_code_tests.py   (-v lists every check). Nothing touches Firebase.

Demo level: the rules, then break-it checks only on who may read or write and on private data (the hash must never leave the server).
"""
import json, pathlib, sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import seed_access  # noqa: E402
from access import review_code as RC  # noqa: E402
from console import make_failure_limiter  # noqa: E402
from crud import access_persons_crud as PE, access_roles_crud as RO  # noqa: E402
from crud.activity_store import ActivityStore  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud_endpoint import handle_admin  # noqa: E402
from discovery_door import handle_discovery  # noqa: E402
from launch_discovery import zip_table  # noqa: E402

T0 = datetime(2026, 10, 22, 12, 0, 0, tzinfo=timezone.utc)
A, KEY = "user:admin", "k" * 16 + "Z" * 16 + "-test-key-not-real"
CODE, CODE2 = "council review 2026", "second funny phrase"
fails, total = [], 0
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    if not ok or "-v" in sys.argv: print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")

zip_table.set_table({"80301": ["CO", 40.0, -105.0, "Boulder"]})
raw = MemoryDocStore("")
store = ActivityStore(raw)                       # as the real Console door: every write leaves an activity entry
def role(key, caps=None, sup=False):
    r = RO.create(store, {"key": key, "label": key, "is_super_admin": sup, **({} if sup else {"capabilities": caps})}, A, now=T0); assert r.ok, r.problems; return r.data
SEED = {r["key"]: r for r in seed_access.ROLES}
insp_role = role("global_inspector", SEED["global_inspector"]["capabilities"])
sup_role = role("super_admin", sup=True)
admin_role = role("admin", SEED["admin"]["capabilities"]) if "admin" in SEED else role("admin", ["view_console", "edit_venues"])
viewer_role = role("viewer", ["view_console"])
mgr_role = role("manager", SEED["manager"]["capabilities"]) if "manager" in SEED else role("manager", ["view_console", "edit_venues"])

class Fake:
    def __init__(self): self.tokens = {}
    def verify(self, t): return dict(self.tokens[t])
V = Fake()
def tok(n): return f"header{n:03d}.payload{n:03d}.signature{n:03d}" + "x" * 20
def person(n, email, r, **kw):
    p = PE.create(store, {"email": email, "role_id": r["id"], "display_name": email.split("@")[0], **kw}, A, now=T0); assert p.ok, p.problems
    V.tokens[tok(n)] = {"uid": f"uid-{n}", "email": email, "email_verified": True, "provider": "google.com", "name": email}
    return p.data
person(1, "super@example.com", sup_role)
person(2, "admin@example.com", admin_role)
person(3, "viewer@example.com", viewer_role)
person(4, "insp@example.com", insp_role)
person(5, "mgr@example.com", mgr_role)

clock = [T0]
def now(): return clock[0]
def call(bearer, op, args=None, collection=None, limiter=None):
    body = {"op": op, "args": args or {}}
    if collection: body["collection"] = collection
    r = handle_admin("POST", f"Bearer {bearer}", json.dumps(body).encode(), KEY, "v", store, limiter or make_failure_limiter(), now(), verifier=V)
    return r.status, r.body
def setcode(bearer, code): return call(bearer, "set_review_code", {"code": code})
def status(bearer): return call(bearer, "review_code_status")
def me(code): return call(code, "me")

# ================================================================ setting a code
check("no code is active to begin with", status(KEY) == (200, {"ok": True, "data": {"active": False}}))
st, b = setcode(tok(1), CODE)
exp = (T0 + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
check("a super admin sets a code; the reply holds only the expiry, 24 hours on", st == 200 and b["data"] == {"expires_at": exp}, str((st, b)))
recs = raw.query("review_codes", [], limit=10)
check("exactly one record is stored, holding a hash and a salt and never the code", len(recs) == 1 and CODE not in json.dumps(recs) and len(recs[0]["code_hash"]) == 64 and recs[0]["access_key"] == "current", str(recs))
st, b = status(tok(1))
check("the status says active, until when, and who set it, with no hash or salt", st == 200 and b["data"]["active"] is True and b["data"]["expires_at"] == exp and b["data"]["set_by"].startswith("user:")
      and "code_hash" not in json.dumps(b) and "salt" not in json.dumps(b), str(b))
check("the admin key may also set and read it", status(KEY)[0] == 200 and setcode(KEY, "key sets this one")[0] == 200)
setcode(tok(1), CODE)                              # back to the first code

# ================================================================ signing in with it
st, b = me(CODE)
check("the code signs in as the view-only Global Inspector", st == 200 and b["data"]["inspector"] is True and b["data"]["role_key"] == "global_inspector"
      and b["data"]["method"] == "code" and b["data"]["name"] == "Review access" and b["data"]["is_super_admin"] is False, str(b))
check("it works with surrounding spaces (a paste)", me("  " + CODE + " ")[0] == 200)
check("a list reads", call(CODE, "list", {"limit": 5}, "venues")[0] == 200 and call(CODE, "list", {"limit": 5}, "access_persons")[0] == 200)
check("a wrong code is refused (401)", me("council review 2027")[0] == 401 and me("")[0] == 401 and me("x")[0] == 401)

# ================================================================ view only everywhere (BREAK-IT: who may write)
before = json.dumps(raw._c("venues") if hasattr(raw, "_c") else "", sort_keys=True, default=str)
writes = [("create", {"data": {"name": "Hack Hall", "slug": "hack", "status": "inactive", "is_public_venue": True}}, "venues"),
          ("create", {"data": {"email": "evil@example.com", "role_id": sup_role["id"]}}, "access_persons"),
          ("update", {"id": "00000000-0000-4000-8000-000000000000", "changes": {"status": "active"}, "expected_updated_at": "2026-01-01T00:00:00Z"}, "venues"),
          ("soft_delete", {"id": "00000000-0000-4000-8000-000000000000"}, "venues")]
check("BREAK-IT: every write by hand is refused for a code sign-in (403)", all(call(CODE, op, a, c)[0] == 403 for op, a, c in writes), str([call(CODE, op, a, c)[0] for op, a, c in writes]))
check("BREAK-IT: send reminders, record timing and invite email are refused", call(CODE, "send_coverage_reminders")[0] == 403 and call(CODE, "record_timing", {"total_ms": 1})[0] == 403)
check("BREAK-IT: nothing changed in the venues", before == json.dumps(raw._c("venues") if hasattr(raw, "_c") else "", sort_keys=True, default=str))

# ================================================================ who may set or read (BREAK-IT)
refused = {n: (setcode(tok(n), "attempt by " + str(n))[0], status(tok(n))[0]) for n in (2, 3, 4, 5)}
check("BREAK-IT: admin, viewer, Inspector and manager can neither set nor read the code (403)", all(v == (403, 403) for v in refused.values()), str(refused))
check("BREAK-IT: a sign-in by code can neither set nor read it", setcode(CODE, "i will make my own")[0] == 403 and status(CODE)[0] == 403)
check("BREAK-IT: the code still works after those refused attempts (nothing was replaced)", me(CODE)[0] == 200)
st, b = call(tok(1), "list", {"limit": 5}, "review_codes")
check("BREAK-IT: the generic doors cannot list the record, even for a super admin or the admin key", st == 400 and call(KEY, "get", {"id": recs[0]["id"]}, "review_codes")[0] == 400 and "code_hash" not in json.dumps(b))
st, b = call(tok(1), "list", {"limit": 5}, "activity_events")
acts = [r for r in (b["data"]["records"] if st == 200 else []) if "review_code" in json.dumps(r)]
check("setting a code is in the activity log, with the hash, the salt and the code withheld", len(acts) >= 1 and CODE not in json.dumps(acts) and recs[0]["code_hash"] not in json.dumps(acts) and recs[0]["salt"] not in json.dumps(acts), str(acts)[:300])
check("BREAK-IT: the hash and salt are in no reply of the code sign-in (me, lists)", recs[0]["code_hash"] not in json.dumps([me(CODE)[1], call(CODE, "list", {"limit": 50}, "activity_events")[1]]))

# ================================================================ rules on a new code
bad = {"short": "abc", "empty": "", "long": "x" * 65, "token_shaped": "aaaaaaaaa.bbbbbbbbb.ccccccccc", "control": "tab\there please", "admin_key": KEY}
res = {k: setcode(tok(1), v)[0] for k, v in bad.items()}
check("a code that is too short, empty, too long, token-shaped, has control characters, or equals the admin key is refused (400)", all(v == 400 for v in res.values()), str(res))
check("a refused attempt did not replace the working code", me(CODE)[0] == 200)
st, b = call(tok(1), "set_review_code", {"code": "okay code!", "extra": 1})
check("extra args and non-text codes are refused", st == 400 and call(tok(1), "set_review_code", {"code": 12345678})[0] == 400 and call(tok(1), "set_review_code", {})[0] == 400)

# ================================================================ replacing: one at a time, clock restarts
clock[0] = T0 + timedelta(hours=10)
check("ten hours later the first code still works", me(CODE)[0] == 200)
st, b = setcode(tok(1), CODE2)
exp2 = (clock[0] + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
check("a new code replaces the old one and restarts the 24 hours", st == 200 and b["data"]["expires_at"] == exp2)
check("the OLD code stops working at once; the NEW one works", me(CODE)[0] == 401 and me(CODE2)[0] == 200)
check("there is still exactly one record", len(raw.query("review_codes", [], limit=10)) == 1)
clock[0] = T0 + timedelta(hours=10) + timedelta(hours=23, minutes=59)
check("just before the end of the second 24 hours it still works", me(CODE2)[0] == 200)
clock[0] = T0 + timedelta(hours=10) + timedelta(hours=24)
check("at 24 hours it is refused, and the status says not active", me(CODE2)[0] == 401 and status(tok(1))[1]["data"] == {"active": False})
clock[0] = T0 + timedelta(hours=11)
setcode(tok(1), CODE)
check("setting the same words again later works and restarts the clock", me(CODE)[0] == 200 and status(KEY)[1]["data"]["expires_at"] == (clock[0] + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ"))

# ================================================================ the role must be there
for p in raw.query("access_roles", [("key", "==", "global_inspector")], limit=5):
    raw.update("access_roles", p["id"], {"is_active": False}, ())
check("if the Global Inspector role is switched off the code is refused", me(CODE)[0] == 401)
for p in raw.query("access_roles", [("key", "==", "global_inspector")], limit=5):
    raw.update("access_roles", p["id"], {"is_active": True}, ())
check("and works again when the role is back on", me(CODE)[0] == 200)

# ================================================================ Discovery: no spend by a code
class Engine:
    def __init__(self): self.calls = []
    def _ok(self, op, *a): self.calls.append((op,) + a); return SimpleNamespace(ok=True, data={"op": op}, code="", message="")
    def quote(self, rq): return self._ok("quote")
    def plan(self, rq, actor): return self._ok("plan")
    def step(self, run_id, actor): return self._ok("step")
    def stop(self, run_id, actor): return self._ok("stop")
    def withdraw(self, run_id, actor): return self._ok("withdraw")
eng = Engine()
def disc(bearer, op, args=None): return handle_discovery("POST", f"Bearer {bearer}", json.dumps({"op": op, "args": args or {}}).encode(), KEY, "v", store, eng, {}, make_failure_limiter(), now(), verifier=V).status
RUN = {"finder_key": "venue", "model_id": "m", "area_ids": ["x"], "type_keys": ["t"], "max_results": 3, "spend_cap_cents": 10}
check("a code may read Discovery (status, runs, ZIP map)", disc(CODE, "status") == 200 and disc(CODE, "list_runs") == 200 and disc(CODE, "zips", {"state_code": "CO"}) == 200)
check("BREAK-IT: a code may not plan, step, stop or withdraw a run (403), and the engine was never called", all(disc(CODE, op, a) == 403 for op, a in (("plan", RUN), ("step", {"run_id": "r"}), ("stop", {"run_id": "r"}), ("withdraw", {"run_id": "r"}))) and not [c for c in eng.calls if c[0] != "quote"], str(eng.calls))
check("an Inspector who signed in with Google still may plan a run (unchanged)", disc(tok(4), "plan", RUN) == 200)

# ================================================================ turning it off now
def clear(bearer): return call(bearer, "clear_review_code")
check("BREAK-IT: only a super admin or the admin key may turn the code off (403 for the rest, and the code still works)", all(clear(tok(n))[0] == 403 for n in (2, 3, 4, 5)) and clear(CODE)[0] == 403 and me(CODE)[0] == 200)
st, b = clear(tok(1))
check("Turn off now: the reply says no code is active, and the code stops working at once", st == 200 and b["data"] == {"active": False} and me(CODE)[0] == 401 and status(tok(1))[1]["data"] == {"active": False}, str((st, b)))
recs2 = raw.query("review_codes", [], limit=10)
check("Turn off now: the record keeps no hash or salt, and turning off twice is fine", len(recs2) == 1 and recs2[0]["code_hash"] == "" and recs2[0]["salt"] == "" and clear(tok(1))[0] == 200 and clear(KEY)[0] == 200)
check("a new code can be set after turning it off", setcode(tok(1), CODE)[0] == 200 and me(CODE)[0] == 200)

# ================================================================ wrong guesses cost time
lim = make_failure_limiter()
codes = [call("guess number %02d" % i, "me", limiter=lim)[0] for i in range(14)]
check("repeated wrong codes from one visitor are slowed (429 after ten)", codes[:10] == [401] * 10 and 429 in codes[10:], str(codes))
check("a visitor who is slowed cannot get in even with the right code", call(CODE, "me", limiter=lim)[0] == 429)

print(f"{'OK' if not fails else 'FAILED'}: {total - len(fails)}/{total} checks")
sys.exit(1 if fails else 0)
