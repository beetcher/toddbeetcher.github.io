#!/usr/bin/env python3
"""Tests for the Console setting (session timeout): the schema examples, the handler (crud/console_settings_crud.py), the capability table
and the Console door end to end, including who may read and who may change it, and that a change lands in the activity log.
Run from enjoy_router/:  python3 run_console_setting_tests.py   (-v lists every check). Nothing touches Firebase; Google is a fake verifier."""
import json, pathlib, sys
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from access import policy  # noqa: E402
from crud import access_persons_crud as PE, access_roles_crud as RO, console_settings_crud as CS  # noqa: E402
from crud.activity_store import ActivityStore  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud_endpoint import HANDLERS, handle_admin, make_failure_limiter  # noqa: E402

START = datetime(2026, 10, 21, 12, 0, 0, tzinfo=timezone.utc)
A = "user:admin"
KEY = "k" * 16 + "Z" * 16 + "-test-key-not-real"
EX = HERE.parent / "schemas" / "examples"
fails, total, clock = [], 0, [0]
def tick():
    clock[0] += 5
    return START + timedelta(seconds=clock[0])
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    if not ok or "-v" in sys.argv: print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")
def issues(r): return sorted((p["field"], p["issue"]) for p in r.problems)
def fresh(): return MemoryDocStore("test_")

# ---------------------------------------------------------------- C1 every example through the handler
ex = json.loads((EX / "console_setting.examples.json").read_text())
for name, rec in ex["valid"].items():
    r = CS.create(fresh(), rec, A, now=tick()); check(f"C1 valid example {name} creates", r.ok, r.problems)
FILLED = {"missing_minutes", "missing_key"}      # the handler fills these with its starting values, so they are valid there
for name, rec in ex["invalid"].items():
    r = CS.create(fresh(), rec, A, now=tick())
    if name in FILLED: check(f"C1 {name}: the handler fills the starting value", r.ok, r.problems)
    else: check(f"C1 invalid example {name} is refused", not r.ok)

# ---------------------------------------------------------------- C2 create
s = fresh()
check("C2 list is empty before create", CS.list(s).data["count"] == 0)
r = CS.create(s, {}, A, now=tick()); sid = r.data["id"] if r.ok else None
check("C2 create with nothing sent makes the one record with 10 minutes", r.ok and r.data["session_timeout_minutes"] == 10 and r.data["settings_key"] == "default", r.problems)
check("C2 a second record is refused", issues(CS.create(s, {}, A, now=tick())) == [("settings_key", "duplicate")])
check("C2 a sender may give the minutes on create", CS.create(fresh(), {"session_timeout_minutes": 25}, A, now=tick()).data["session_timeout_minutes"] == 25)
check("C2 server fields cannot be sent", not CS.create(fresh(), {"id": "a0000000-0000-4000-8000-000000000009"}, A, now=tick()).ok)
check("C2 a missing actor is refused", not CS.create(fresh(), {}, "", now=tick()).ok)

# ---------------------------------------------------------------- C3 update
def minutes(r): return CS.get(s, sid).data["session_timeout_minutes"] if r.ok else None      # what is stored after a change that was accepted
cur = CS.get(s, sid).data
check("C3 set to 30", minutes(CS.update(s, sid, {"session_timeout_minutes": 30}, A, now=tick())) == 30)
check("C3 the shortest, 1, is allowed", minutes(CS.update(s, sid, {"session_timeout_minutes": 1}, A, now=tick())) == 1)
check("C3 the longest, 480, is allowed", minutes(CS.update(s, sid, {"session_timeout_minutes": 480}, A, now=tick())) == 480)
for label, v in (("0 (there is no off)", 0), ("481", 481), ("-5", -5), ("7.5", 7.5), ("text", "10"), ("true", True)):
    check(f"C3 {label} is refused", not CS.update(s, sid, {"session_timeout_minutes": v}, A, now=tick()).ok)
check("C3 removing the minutes is refused", issues(CS.update(s, sid, {"session_timeout_minutes": None}, A, now=tick())) == [("session_timeout_minutes", "required")])
check("C3 settings_key never changes", issues(CS.update(s, sid, {"settings_key": "other"}, A, now=tick())) == [("settings_key", "immutable")])
check("C3 server fields cannot be changed", not CS.update(s, sid, {"created_by": "user:x"}, A, now=tick()).ok and not CS.update(s, sid, {"id": sid}, A, now=tick()).ok)
check("C3 an unknown field is refused", not CS.update(s, sid, {"warn_seconds": 60}, A, now=tick()).ok)
now_rec = CS.get(s, sid).data
check("C3 a stale update is refused", not CS.update(s, sid, {"session_timeout_minutes": 12}, A, expected_updated_at="2026-01-01T00:00:00Z", now=tick()).ok)
check("C3 an update that names the stamp it read works", CS.update(s, sid, {"session_timeout_minutes": 12}, A, expected_updated_at=now_rec["updated_at"], now=tick()).ok)
check("C3 an update of a missing record is not_found", CS.update(s, "a0000000-0000-4000-8000-000000000008", {"session_timeout_minutes": 12}, A, now=tick()).ok is False)
check("C3 the update stamps who changed it", CS.get(s, sid).data["updated_by"] == A)

# ---------------------------------------------------------------- C4 delete, get, list
check("C4 delete is refused", not CS.soft_delete(s, sid, A, now=tick()).ok and CS.get(s, sid).ok)
check("C4 get by id", CS.get(s, sid).ok and CS.get(s, sid).data["settings_key"] == "default")
check("C4 get with a bad id is refused", not CS.get(s, "nope").ok)
check("C4 list returns the one record", CS.list(s).data["count"] == 1)
check("C4 list takes no filters", issues(CS.list(s, {"settings_key": "default"})) == [("settings_key", "not_supported")])

# ---------------------------------------------------------------- C5 wiring and the capability table
check("C5 the handler is registered for the Console door", HANDLERS.get("console_settings") is CS)
check("C5 reading needs only view_console (every signed-in person has it)", policy.READ.get("console_settings") == ("view_console",))
check("C5 changing it is super admin only", policy.WRITE.get("console_settings") == (policy.SUPER_ONLY,))

# ---------------------------------------------------------------- C6 the Console door end to end
class Fake:
    def __init__(self): self.tokens = {}
    def verify(self, token):
        if token not in self.tokens: raise ValueError("bad token")
        return dict(self.tokens[token])
def tok(n): return f"header{n:03d}.payload{n:03d}.signature{n:03d}" + "x" * 20
V = Fake(); inner = MemoryDocStore(""); store = ActivityStore(inner); limiter = make_failure_limiter()
def door(body, token=None, key=None):
    auth = f"Bearer {key}" if key else (f"Bearer {token}" if token else "")
    return handle_admin("POST", auth, json.dumps(body).encode(), KEY, "v", store, limiter, tick(), verifier=V)
def mkrole(key, caps=None, sup=False):
    r = RO.create(store, {"key": key, "label": key, "is_super_admin": sup, **({} if sup else {"capabilities": caps})}, A, now=tick()); assert r.ok, r.problems; return r.data
def mkperson(email, role, n):
    r = PE.create(store, {"email": email, "role_id": role["id"]}, A, now=tick()); assert r.ok, r.problems
    V.tokens[tok(n)] = {"uid": f"uid-{n}", "email": email, "email_verified": True, "provider": "google.com", "name": "G"}; return r.data
sup = mkperson("sup@example.com", mkrole("super_admin", sup=True), 1)
viewer = mkperson("viewer@example.com", mkrole("viewer", ["view_console"]), 2)
nocap = mkperson("nocap@example.com", mkrole("spend_only", ["view_spend"]), 3)
r = door({"collection": "console_settings", "op": "create", "args": {"data": {"session_timeout_minutes": 15}}}, key=KEY)
check("C6 the key may create the record", r.status == 200 and r.body["data"]["session_timeout_minutes"] == 15, r.body)
rec = r.body["data"]
r = door({"collection": "console_settings", "op": "create", "args": {"data": {}}}, token=tok(1))
check("C6 a second create (super admin) is refused by the one-record rule", r.status == 400 or not r.body.get("ok"), r.body)
r = door({"collection": "console_settings", "op": "list", "args": {}}, token=tok(2))
check("C6 a person who can only view the Console may READ it", r.status == 200 and r.body["data"]["records"][0]["session_timeout_minutes"] == 15, r.body)
r = door({"collection": "console_settings", "op": "list", "args": {}}, token=tok(1))
check("C6 a super admin reads it", r.status == 200 and r.body["data"]["count"] == 1)
r = door({"collection": "console_settings", "op": "update", "args": {"id": rec["id"], "changes": {"session_timeout_minutes": 99}, "expected_updated_at": rec["updated_at"]}}, token=tok(2))
check("C6 a viewer may NOT change it (403)", r.status == 403, (r.status, r.body))
check("C6 ...and it did not change", store.get("console_settings", rec["id"])["session_timeout_minutes"] == 15)
r = door({"collection": "console_settings", "op": "update", "args": {"id": rec["id"], "changes": {"session_timeout_minutes": 99}, "expected_updated_at": rec["updated_at"]}}, token=tok(3))
check("C6 a person without view_console may not change it either (403)", r.status == 403)
r = door({"collection": "console_settings", "op": "list", "args": {}}, token=tok(3))
check("C6 a person without view_console may not read it (403)", r.status == 403)
r = door({"collection": "console_settings", "op": "update", "args": {"id": rec["id"], "changes": {"session_timeout_minutes": 20}, "expected_updated_at": rec["updated_at"]}}, token=tok(1))
check("C6 a super admin may change it", r.status == 200 and store.get("console_settings", rec["id"])["session_timeout_minutes"] == 20, r.body)
check("C6 the change is stamped with the signed-in person", r.body["data"]["updated_by"] == f"user:{sup['id']}")
r = door({"collection": "console_settings", "op": "update", "args": {"id": rec["id"], "changes": {"session_timeout_minutes": 0}, "expected_updated_at": r.body["data"]["updated_at"]}}, token=tok(1))
check("C6 zero (off) is refused even for a super admin", r.status == 400, (r.status, r.body))
r = door({"collection": "console_settings", "op": "soft_delete", "args": {"id": rec["id"]}}, key=KEY)
check("C6 it cannot be deleted, even with the key", r.status != 200 or not r.body.get("ok"), r.body)
r = door({"collection": "console_settings", "op": "list", "args": {}})
check("C6 no credential, no reading (401)", r.status == 401)
es = [e for e in inner.query("activity_events", [], limit=500) if e.get("record_type") == "console_setting"]
check("C6 creating and changing it are in the activity log", sorted(e["action"] for e in es) == ["created", "edited"], [e["action"] for e in es])
ed = [e for e in es if e["action"] == "edited"][0]
check("C6 the edit entry shows the old and the new minutes", any(c["field"] == "session_timeout_minutes" and c.get("old_value") == "15" and c.get("new_value") == "20" for c in ed["changes"]), ed["changes"])
check("C6 ...and by whom", ed["created_by"] == f"user:{sup['id']}")

print(f"{total - len(fails)}/{total} checks passed" if not fails else f"FAILED {len(fails)} of {total}: " + "; ".join(fails))
sys.exit(1 if fails else 0)
