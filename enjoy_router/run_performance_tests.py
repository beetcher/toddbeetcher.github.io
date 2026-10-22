#!/usr/bin/env python3
"""Tests for the timing log (P-80): the record_timing op, who may write and read performance_events, and the server timing on `me`.
Run from enjoy_router/:  python3 run_performance_tests.py   (-v lists every check). Nothing touches Firebase; Google is a fake verifier."""
import json, pathlib, sys
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import seed_access  # noqa: E402
from console import make_failure_limiter  # noqa: E402
from crud import access_persons_crud as PE, access_roles_crud as RO, performance_service as PS  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
import crud_endpoint  # noqa: E402
from crud_endpoint import handle_admin  # noqa: E402

START = datetime(2026, 10, 22, 12, 0, 0, tzinfo=timezone.utc)
A, KEY = "user:admin", "k" * 16 + "Z" * 16 + "-test-key-not-real"
fails, total, clock = [], 0, [0]
def tick():
    clock[0] += 5
    return START + timedelta(seconds=clock[0])
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    if not ok or "-v" in sys.argv: print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")

from crud.activity_store import ActivityStore  # noqa: E402
inner = MemoryDocStore("")
store = ActivityStore(inner)         # the real wrapper: every change is logged unless the collection is excluded
class Fake:
    def __init__(self): self.tokens = {}
    def verify(self, t): return dict(self.tokens[t])
V = Fake()
def tok(n): return f"header{n:03d}.payload{n:03d}.signature{n:03d}" + "x" * 20
def role(key, caps=None, sup=False):
    r = RO.create(store, {"key": key, "label": key, "is_super_admin": sup, **({} if sup else {"capabilities": caps})}, A, now=tick()); assert r.ok, r.problems; return r.data
def who(n, email, r):
    p = PE.create(store, {"email": email, "role_id": r["id"], "display_name": email.split("@")[0]}, A, now=tick()); assert p.ok, p.problems
    V.tokens[tok(n)] = {"uid": f"uid-{n}", "email": email, "email_verified": True, "provider": "google.com", "name": email}; return p.data
SEED = {r["key"]: r for r in seed_access.ROLES}
sup_r = role("super_admin", sup=True)
admin_r = role("admin", [c for c in SEED["admin"]["capabilities"]] + ["view_performance"]) if "admin" in SEED else role("admin", ["view_console", "view_performance"])
mgr_r = role("manager", SEED["manager"]["capabilities"])
insp_r = role("global_inspector", SEED["global_inspector"]["capabilities"])
inst_r = role("instructor", SEED["instructor"]["capabilities"])
todd, adm, mgr, insp, inst = who(1, "todd@x.com", sup_r), who(2, "admin@x.com", admin_r), who(3, "mgr@x.com", mgr_r), who(4, "insp@x.com", insp_r), who(5, "inst@x.com", inst_r)

def post(n, body, key=False):
    auth = f"Bearer {KEY}" if key else f"Bearer {tok(n)}"
    r = handle_admin("POST", auth, json.dumps(body).encode(), KEY, "v", store, make_failure_limiter(), tick(), verifier=V)
    return r.status, r.body
GOOD = {"kind": "sign_in", "device": "desktop", "method": "google", "total_ms": 3200, "check_ms": 2500, "load_ms": 600, "server_ms": 180, "cold": True}
def rec(n, args=None, key=False): PS.reset_limiter(); return post(n, {"op": "record_timing", "args": GOOD if args is None else args}, key)
def rows(n): return post(n, {"collection": "performance_events", "op": "list", "args": {"limit": 200}})
def count(): return len([d for d in inner.data.get("performance_events", {}).values()])

# ---- who may send one
st, b = rec(3); check("a manager can record a sign-in timing", st == 200 and b["data"]["recorded"] is True, (st, b))
check("it is stored with the numbers and the server's own stamps", count() == 1 and (lambda d: d["total_ms"] == 3200 and d["created_by"] == "user:" + mgr["id"] and d["role_key"] == "manager" and d["cold"] is True)(list(inner.data["performance_events"].values())[0]))
check("an instructor can record one", rec(5)[0] == 200)
check("the admin key can record one", rec(0, key=True)[0] == 200)
check("a super admin can record one", rec(1)[0] == 200)
st, b = rec(4); check("the view-only Inspector cannot (the server refuses every write)", st == 403, (st, b)); n0 = count(); rec(4); check("...and nothing was stored", count() == n0)
st, b = post(None, {"op": "record_timing", "args": GOOD}, key=False) if False else (0, {})
r = handle_admin("POST", "Bearer nonsense", json.dumps({"op": "record_timing", "args": GOOD}).encode(), KEY, "v", store, make_failure_limiter(), tick(), verifier=V)
check("nobody who is not signed in can record", r.status == 401, r.status)
# ---- the sender cannot choose who it is for, or send anything else
st, b = rec(3, {**GOOD, "role_key": "super_admin"}); check("a sender-chosen role is not accepted", st == 200 and list(inner.data["performance_events"].values())[-1]["role_key"] == "manager" or st >= 400, (st, b))
last = list(inner.data["performance_events"].values())[-1]; check("...the stored role is always the sender's real one", last["role_key"] == "manager" or last["role_key"] in ("manager",), last["role_key"])
for label, extra in [("created_by", {"created_by": "user:someone-else"}), ("an email", {"email": "a@b.example"}), ("an id", {"id": "x"}), ("a name", {"name": "Ann"})]:
    n0 = count(); st, b = rec(3, {**GOOD, **extra}); check(f"a sender-supplied {label} is refused and nothing stored", st == 400 and count() == n0, (st, b))
for label, bad in [("unknown kind", {"kind": "page_view"}), ("unknown device", {"device": "tablet"}), ("unknown method", {"method": "sms"}), ("negative", {"total_ms": -1}),
                   ("too big", {"total_ms": 600001}), ("decimal", {"total_ms": 10.5}), ("text number", {"total_ms": "10"}), ("true as a number", {"check_ms": True}), ("cold not a boolean", {"cold": "yes"})]:
    n0 = count(); st, b = rec(3, {**GOOD, **bad}); check(f"bad value refused: {label}", st == 400 and count() == n0, (st, b))
n0 = count(); st, b = rec(3, {"kind": "sign_in", "device": "desktop", "method": "google"}); check("total_ms is required", st == 400 and count() == n0, (st, b))
n0 = count(); st, b = rec(3, {"kind": "sign_in", "device": "phone", "method": "key", "total_ms": 0}); check("the smallest valid timing is accepted", st == 200 and count() == n0 + 1, (st, b))
check("args must be an object", post(3, {"op": "record_timing", "args": [1]})[0] == 400)
# ---- one per person per 10 seconds
PS.reset_limiter(); n0 = count(); a = post(3, {"op": "record_timing", "args": GOOD}); b2 = post(3, {"op": "record_timing", "args": GOOD})
check("a second one straight after is dropped quietly (not an error)", a[1]["data"]["recorded"] is True and b2[0] == 200 and b2[1]["data"]["recorded"] is False and count() == n0 + 1, (a, b2))
c = post(5, {"op": "record_timing", "args": GOOD}); check("...and the limit is per person (another person is still recorded)", c[1]["data"]["recorded"] is True)
# ---- who may read
st, b = rows(1); check("a super admin reads the log", st == 200 and len(b["data"]["records"]) >= 4, st)
st, b = rows(2); check("an Admin who holds view_performance reads it", st == 200, (st, b))
check("a manager cannot read it", rows(3)[0] == 403)
check("an instructor cannot read it", rows(5)[0] == 403)
st, b = rows(4); check("the Inspector reads it (view only)", st == 200 and len(b["data"]["records"]) >= 4, st)
check("the admin key reads it", post(0, {"collection": "performance_events", "op": "list", "args": {}}, key=True)[0] == 200)
# ---- nobody can change or remove one, through any door
rid = list(inner.data["performance_events"].keys())[0]; before = json.dumps(inner.data["performance_events"], sort_keys=True)
for n, nm in ((1, "super admin"), (2, "admin"), (3, "manager")):
    for op, args in (("create", {"data": GOOD}), ("update", {"id": rid, "data": {"total_ms": 1}, "expected_updated_at": list(inner.data["performance_events"].values())[0]["updated_at"]}), ("soft_delete", {"id": rid})):
        st, b = post(n, {"collection": "performance_events", "op": op, "args": args}); check(f"{nm}: {op} through the Console is refused", st in (400, 403), (st, b))
check("...and the log did not change", json.dumps(inner.data["performance_events"], sort_keys=True) == before)
check("it is not in the activity log (while other changes are: a person was created above)", any(d.get("record_type") == "access_person" for d in inner.data.get("activity_events", {}).values()) and not any(d.get("record_type") == "performance_event" for d in inner.data.get("activity_events", {}).values()))
# ---- the server's own timing on the who-am-I call
st, b = post(3, {"op": "me"}); d = b["data"]
check("me carries server_ms (a whole number) and cold (true or false)", isinstance(d.get("server_ms"), int) and d["server_ms"] >= 0 and isinstance(d.get("cold"), bool), d)
crud_endpoint._FIRST_REQUEST = True; st, b = post(3, {"op": "me"}); check("the first request an instance handles says cold: true", b["data"]["cold"] is True)
st, b = post(3, {"op": "me"}); check("the next one says cold: false", b["data"]["cold"] is False)
# ---- the capability is a real, global capability and the roles are right
from access import CAPABILITIES  # noqa: E402
from access.capabilities import GLOBAL  # noqa: E402
check("view_performance is a capability and a global one (it comes from the role)", "view_performance" in CAPABILITIES and "view_performance" in GLOBAL)
check("a super admin has it without being given it", "view_performance" in post(1, {"op": "me"})[1]["data"]["capabilities"])
check("a manager does not have it", "view_performance" not in post(3, {"op": "me"})[1]["data"]["capabilities"])
print(f"\n{total - len(fails)}/{total} checks passed" + ("" if not fails else "  FAILED: " + "; ".join(fails)))
sys.exit(1 if fails else 0)
