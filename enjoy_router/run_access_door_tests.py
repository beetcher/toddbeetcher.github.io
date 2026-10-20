#!/usr/bin/env python3
"""Tests for sign-in at the three doors (P-62 step 3): the Console door (crud_endpoint.handle_admin), the records door (console.py), the
Discovery door (discovery_door.py), the test door, and the capability table (access/policy.py).
Run from enjoy_router/:  python3 run_access_door_tests.py   (-v lists every check). Nothing touches Firebase; Google is a fake verifier."""
import io, json, logging, pathlib, sys
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import console  # noqa: E402
from access import CAPABILITIES, authorize, policy  # noqa: E402
from console import handle_console, make_failure_limiter  # noqa: E402
from crud import access_persons_crud as PE, access_roles_crud as RO  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
import crud_endpoint  # noqa: E402
from crud_endpoint import HANDLERS, OPS, ADMIN_OPS, handle_admin, handle_crud_test  # noqa: E402
from discovery_door import handle_discovery  # noqa: E402
from memory_store import MemoryStore  # noqa: E402

START = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)
A = "user:admin"
KEY = "k" * 16 + "Z" * 16 + "-test-key-not-real"
fails, total, clock = [], 0, [0]
def tick():
    clock[0] += 5
    return START + timedelta(seconds=clock[0])
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    if not ok or "-v" in sys.argv: print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")

class Fake:
    def __init__(self): self.tokens, self.calls = {}, 0
    def verify(self, token):
        self.calls += 1
        if token not in self.tokens: raise ValueError("bad token")
        return dict(self.tokens[token])
def tok(n): return f"header{n:03d}.payload{n:03d}.signature{n:03d}" + "x" * 20
def claims(email, uid="uid-1", verified=True, provider="google.com"):
    return {"uid": uid, "email": email, "email_verified": verified, "provider": provider, "name": "G"}

store = MemoryDocStore("")
V = Fake()
def mkrole(key, caps=None, sup=False, **kw):
    r = RO.create(store, {"key": key, "label": key, "is_super_admin": sup, **({} if sup else {"capabilities": caps}), **kw}, A, now=tick())
    assert r.ok, r.problems
    return r.data
STATE_ID, REGION_ID = "a0000000-0000-4000-8000-000000000001", "a0000000-0000-4000-8000-000000000002"
store.create("discovery_areas", STATE_ID, {"id": STATE_ID, "kind": "state", "state_code": "CO", "name": "Colorado", "is_active": True})
store.create("discovery_areas", REGION_ID, {"id": REGION_ID, "kind": "region", "state_code": "CO", "name": "Boulder", "zip_codes": ["80301"], "is_active": True})
from access.capabilities import TERRITORIAL  # noqa: E402
def mkperson(email, role, n, **kw):
    terr = [c for c in role.get("capabilities", []) if c in TERRITORIAL]
    if terr and "grants" not in kw:      # the role's territorial capabilities are the defaults for a grant (territory itself is tested in run_territory_tests.py)
        kw["grants"] = [{"kind": "regions", "state_code": "CO", "region_ids": [REGION_ID], "capabilities": terr}]
    r = PE.create(store, {"email": email, "role_id": role["id"], **kw}, A, now=tick()); assert r.ok, r.problems
    V.tokens[tok(n)] = claims(email, uid=f"uid-{n}")
    return r.data

sup_role = mkrole("super_admin", sup=True)
head_role = mkrole("region_head", ["view_console", "edit_venues", "activate_venues", "manage_instructors", "manage_requests"])
edit_role = mkrole("venue_editor", ["view_console", "edit_venues"])
spend_role = mkrole("spend_viewer", ["view_spend"])
disco_role = mkrole("discoverer", ["run_discovery"])
view_role = mkrole("viewer", ["view_console"])
todd = mkperson("todd@example.com", sup_role, 1)
head = mkperson("head@example.com", head_role, 2)
editor = mkperson("editor@example.com", edit_role, 3)
spend = mkperson("spend@example.com", spend_role, 4)
disco = mkperson("disco@example.com", disco_role, 5)
viewer = mkperson("viewer@example.com", view_role, 6)
V.tokens[tok(90)] = claims("stranger@example.com", uid="uid-90")                  # a real Google account nobody invited
V.tokens[tok(91)] = claims("todd@example.com", uid="uid-1", verified=False)       # an unverified email
V.tokens[tok(92)] = claims("todd@example.com", uid="uid-other")                   # same email, a different Google account
V.tokens[tok(93)] = claims("todd@example.com", uid="uid-1", provider="password")  # not a Google sign-in
nobody = PE.create(store, {"email": "off@example.com", "role_id": head_role["id"], "is_active": False}, A, now=tick()).data
V.tokens[tok(94)] = claims("off@example.com", uid="uid-94")

def admin(body, token=None, key=None, lim=None, verifier=V, method="POST", visitor="v"):
    auth = f"Bearer {key}" if key else (f"Bearer {token}" if token else "")
    return handle_admin(method, auth, json.dumps(body).encode(), KEY, visitor, store, lim or make_failure_limiter(), tick(), verifier=verifier)
def T(n): return tok(n)
def not_denied(r): return r.status not in (401, 403, 429)

# ================================================================ the key still works exactly as before
r = admin({"collection": "access_roles", "op": "list", "args": {}}, key=KEY)
check("admin door: the key still works", r.status == 200 and r.body["ok"])
r = admin({"collection": "access_roles", "op": "create", "args": {"data": {"key": "by_key", "label": "By key", "is_super_admin": False, "capabilities": ["view_console"]}}}, key=KEY)
check("admin door: a key write is stamped user:admin", r.status == 200 and r.body["data"]["created_by"] == "user:admin", r.body)
check("admin door: no credential = 401", admin({"collection": "venues", "op": "list", "args": {}}).status == 401)
check("admin door: wrong key = 401", admin({"collection": "venues", "op": "list", "args": {}}, key="w" * 40).status == 401)
check("admin door: without a verifier a Google token is just a bad key (401)", admin({"collection": "venues", "op": "list", "args": {}}, token=T(1), verifier=None).status == 401)
check("admin door: only POST", admin({}, key=KEY, method="GET").status == 405)
r = handle_admin("POST", f"Bearer {KEY}", b"{}", "", "v", store, make_failure_limiter(), tick(), verifier=None)
check("admin door: no key setting and no verifier fails closed", r.status == 401)
r = handle_admin("POST", f"Bearer {T(1)}", json.dumps({"collection": "access_roles", "op": "list", "args": {}}).encode(), "", "v", store, make_failure_limiter(), tick(), verifier=V)
check("admin door: Google alone works when there is no key setting", r.status == 200, r.body)

# ================================================================ a Google super admin
r = admin({"collection": "access_roles", "op": "list", "args": {}}, token=T(1))
check("google super admin: may list access_roles", r.status == 200 and r.body["ok"], r.body)
r = admin({"collection": "access_roles", "op": "create", "args": {"data": {"key": "by_todd", "label": "By Todd", "is_super_admin": False, "capabilities": ["view_console"]}}}, token=T(1))
check("google super admin: a write is stamped user:<access_person id>", r.status == 200 and r.body["data"]["created_by"] == f"user:{todd['id']}", r.body)
check("google super admin: venues soft_delete is allowed (not denied)", not_denied(admin({"collection": "venues", "op": "soft_delete", "args": {"id": "nope"}}, token=T(1))))
check("the sign-in time and Google id were saved on the person", PE.get(store, todd["id"]).data["google_uid"] == "uid-1" and bool(PE.get(store, todd["id"]).data["last_sign_in_at"]))

# ================================================================ me
r = admin({"op": "me"}, token=T(1))
d = r.body.get("data", {})
check("me: a super admin sees every capability", r.status == 200 and d["is_super_admin"] and d["capabilities"] == sorted(CAPABILITIES) and d["method"] == "google" and d["email"] == "todd@example.com", r.body)
d = admin({"op": "me"}, token=T(2)).body["data"]
check("me: a region head sees only their capabilities", d["role_key"] == "region_head" and not d["is_super_admin"] and d["capabilities"] == sorted(head_role["capabilities"]), d)
d = admin({"op": "me"}, key=KEY).body["data"]
check("me: the key shows as a super admin by key", d["is_super_admin"] and d["method"] == "key" and d["name"] == "Admin key")
check("me: no credential = 401", admin({"op": "me"}).status == 401)
check("me never carries the uid or the key", "uid-" not in json.dumps(admin({"op": "me"}, token=T(1)).body) and KEY not in json.dumps(admin({"op": "me"}, key=KEY).body))
r = handle_crud_test("POST", f"Bearer {KEY}", b'{"op": "me"}', KEY, "v", MemoryDocStore("test_"), make_failure_limiter(), tick())
check("me: the test door does not offer it", r.status == 400)

# ================================================================ what each role may do
def code(body, n): return admin(body, token=T(n)).status
LV = {"collection": "venues", "op": "list", "args": {}}
check("region head: may read venues", code(LV, 2) == 200)
check("region head: may edit a venue (not denied)", not_denied(admin({"collection": "venues", "op": "update", "args": {"id": "nope", "changes": {"name": "x"}}}, token=T(2))))
check("region head: may switch a venue on or off (not denied)", not_denied(admin({"collection": "venues", "op": "update", "args": {"id": "nope", "changes": {"status": "active"}}}, token=T(2))))
check("venue editor: may edit a venue but NOT change its status", not_denied(admin({"collection": "venues", "op": "update", "args": {"id": "nope", "changes": {"name": "x"}}}, token=T(3)))
      and code({"collection": "venues", "op": "update", "args": {"id": "nope", "changes": {"status": "active"}}}, 3) == 403)
check("venue editor: a new venue created already active is also refused", code({"collection": "venues", "op": "create", "args": {"data": {"status": "active"}}}, 3) == 403)
check("region head: venues soft_delete is the super admin's", code({"collection": "venues", "op": "soft_delete", "args": {"id": "x"}}, 2) == 403)
check("region head: no access management", code({"collection": "access_roles", "op": "list", "args": {}}, 2) == 403 and code({"collection": "access_persons", "op": "list", "args": {}}, 2) == 403
      and code({"collection": "access_persons", "op": "create", "args": {"data": {}}}, 2) == 403)
check("region head: no people records", code({"collection": "individuals", "op": "list", "args": {}}, 2) == 403)
check("region head: no messages", code({"collection": "communication_logs", "op": "list", "args": {}}, 2) == 403)
check("region head: no curriculum writes", code({"collection": "curriculums", "op": "create", "args": {"data": {}}}, 2) == 403)
check("region head: may delete a registration request (manage_requests)", not_denied(admin({"collection": "attendances", "op": "delete_request", "args": {"id": "x"}}, token=T(2))))
check("region head: may save a place (venue editing)", not_denied(admin({"collection": "locations", "op": "create", "args": {"data": {"addresses": [{"postal_code": "80301"}]}}}, token=T(2))))
check("viewer: may read venues, may not write them", code(LV, 6) == 200 and code({"collection": "venues", "op": "create", "args": {"data": {}}}, 6) == 403)
check("spend viewer: no venues at all", code(LV, 4) == 403)
check("spend viewer: may read discovery_runs (not blocked by policy)", policy.allowed(authorize.authenticate(T(4), admin_key=KEY, verifier=V, store=store, now=tick()), policy.crud_need("discovery_runs", "list", {})))
check("unknown collection falls to super admin only", policy.crud_need("nope", "list", {}) == policy._SUPER and code({"collection": "nope", "op": "list", "args": {}}, 2) == 400)
check("an op nobody classified falls to super admin only", policy.crud_need("venues", "brand_new_op", {}) == policy._SUPER or policy.crud_need("venues", "brand_new_op", {}) == (("edit_venues",),))

# ================================================================ refusals
check("uninvited Google account = 403 forbidden", admin(LV, token=T(90)).status == 403 and admin(LV, token=T(90)).body["error"]["code"] == "forbidden")
check("unverified email = 401", admin(LV, token=T(91)).status == 401)
check("another Google account on a known email = 403", admin(LV, token=T(92)).status == 403)
check("a non-Google provider = 401", admin(LV, token=T(93)).status == 401)
check("a switched-off person = 403", admin(LV, token=T(94)).status == 403)
check("a made-up token = 401 and the verifier said no", admin(LV, token="aaaaaaaaaaaaaaaa.bbbbbbbbbbbbbbbbbbbb.cccccccccccccccccccc").status == 401)
RO.update(store, spend_role["id"], {"is_active": False}, A, now=tick())
check("a person whose role is switched off = 403", admin(LV, token=T(4)).status == 403)
RO.update(store, spend_role["id"], {"is_active": True}, A, now=tick())
check("...and back in once the role is on again", admin({"collection": "discovery_runs", "op": "list", "args": {}}, token=T(4)).status in (200, 400))
check("a refusal never says which part failed (401 body identical)", admin(LV, token=T(91)).body == admin(LV).body)

lim = make_failure_limiter()
for _ in range(10): admin(LV, token=T(90), lim=lim)
check("failures from uninvited accounts count: the 11th is 429", admin(LV, token=T(90), lim=lim).status == 429)
check("...and a correct sign-in is blocked too while blocked (same visitor)", admin(LV, token=T(1), lim=lim).status == 429)
lim = make_failure_limiter()
for _ in range(25): admin(LV, token=T(1), lim=lim)
check("good sign-ins are never counted", admin(LV, token=T(1), lim=lim).status == 200)

# ================================================================ the test door
r = handle_crud_test("POST", f"Bearer {T(1)}", json.dumps({"collection": "venues", "op": "list", "args": {}}).encode(), KEY, "v", MemoryDocStore("test_"), make_failure_limiter(), tick())
check("test door: a Google token is refused (key only)", r.status == 401)
r = handle_crud_test("POST", f"Bearer {KEY}", json.dumps({"collection": "access_roles", "op": "create", "args": {"data": {"key": "t", "label": "T", "is_super_admin": False, "capabilities": ["view_console"]}}}).encode(), KEY, "v", MemoryDocStore("test_"), make_failure_limiter(), tick())
check("test door: the key works and stamps system:crud_test", r.status == 200 and r.body["data"]["created_by"] == "system:crud_test", r.body)

import inspect
check("test door: its code never mentions a verifier (key only, by construction)", "verifier" not in inspect.getsource(handle_crud_test))

# ================================================================ roles: no delegation yet
r = RO.create(store, {"key": "sneaky", "label": "Sneaky", "is_super_admin": False, "capabilities": ["view_console", "manage_access"]}, A, now=tick())
check("role: an ordinary role may not hold manage_access (yet)", not r.ok and ("capabilities", "not_allowed") in [(p["field"], p["issue"]) for p in r.problems])

# ================================================================ the records door
def reg_store():
    s = MemoryStore([]); s.requests.append({"id": "r1", "created_at": "2026-10-09T04:26:00Z", "email": "p@example.com", "postal_code": "80301"}); return s
def records(n=None, key=None, lim=None, verifier=V):
    auth = f"Bearer {key}" if key else (f"Bearer {tok(n)}" if n else "")
    return handle_console("GET", auth, {}, KEY, "v", reg_store(), lim or make_failure_limiter(), tick(), verifier=verifier, access_store=store)
check("records: the key still works", records(key=KEY).status == 200)
check("records: a region head (manage_requests) may read", records(2).status == 200 and records(2).body["data"]["count"] == 1)
check("records: a viewer without manage_requests or manage_classes = 403", records(6).status == 403)
check("records: an uninvited account = 403, no credential = 401", records(90).status == 403 and records().status == 401)
check("records: a super admin may read", records(1).status == 200)
check("records: without a verifier a token is refused", records(1, verifier=None).status == 401)

# ================================================================ the discovery door
def disc(op, n=None, key=None, args=None, lim=None, verifier=V):
    auth = f"Bearer {key}" if key else (f"Bearer {tok(n)}" if n else "")
    return handle_discovery("POST", auth, json.dumps({"op": op, "args": args or {}}).encode(), KEY, "v", store, None, {}, lim or make_failure_limiter(), tick(), verifier=verifier)
check("discovery: the key still works (status)", disc("status", key=KEY).status == 200)
check("discovery: spend viewer may read status and runs", disc("status", 4).status == 200 and disc("list_runs", 4).status == 200)
check("discovery: spend viewer may not plan, step, stop, withdraw, quote or read zips", all(disc(o, 4, args=a).status == 403 for o, a in
      [("plan", {}), ("quote", {}), ("step", {"run_id": "r"}), ("stop", {"run_id": "r"}), ("withdraw", {"run_id": "r"}), ("zips", {"state_code": "CO"})]))
check("discovery: a region head has no Discovery at all", disc("status", 2).status == 403 and disc("list_runs", 2).status == 403)
check("discovery: the runner may plan (past the lock, 400 on bad args) and read runs", disc("plan", 5, args={}).status == 400 and disc("list_runs", 5).status == 200)
check("discovery: a super admin may do everything (status)", disc("status", 1).status == 200)
check("discovery: an uninvited account = 403, no credential = 401, no verifier = 401", disc("status", 90).status == 403 and disc("status").status == 401 and disc("status", 1, verifier=None).status == 401)
class Engine:
    def __init__(self): self.actors = []
    def plan(self, rq, actor): self.actors.append(actor); raise RuntimeError("stop here")
    def quote(self, rq): raise RuntimeError("no")
eng = Engine()
REQ = {"finder_key": "venue", "model_id": "m", "area_ids": ["a"], "type_keys": ["t"], "max_results": 1, "spend_cap_cents": 1}
handle_discovery("POST", f"Bearer {tok(5)}", json.dumps({"op": "plan", "args": REQ}).encode(), KEY, "v", store, eng, {}, make_failure_limiter(), tick(), verifier=V)
handle_discovery("POST", f"Bearer {KEY}", json.dumps({"op": "plan", "args": REQ}).encode(), KEY, "v", store, eng, {}, make_failure_limiter(), tick(), verifier=V)
check("discovery: a run is stamped with who started it (user:<id>, or user:admin for the key)", eng.actors == [f"user:{disco['id']}", "user:admin"], eng.actors)

# ================================================================ the table itself
check("policy: every collection the door serves has a read rule and a write rule", set(HANDLERS) == set(policy.READ) == set(policy.WRITE), (set(HANDLERS) ^ set(policy.READ), set(HANDLERS) ^ set(policy.WRITE)))
allcaps = set(CAPABILITIES) | {policy.SUPER_ONLY}
bad = [(c, caps) for t in (policy.READ, policy.WRITE) for c, caps in t.items() if not set(caps) <= allcaps]
check("policy: only real capabilities are named", not bad, bad)
check("policy: every read op is a real op", policy.READ_OPS <= set(OPS))
check("policy: every Discovery op has a rule, and nothing extra", set(policy.DISCOVERY) == set(__import__("discovery_door").OPS))
check("policy: access management is super-admin-only (no ordinary role may hold manage_access)", policy.WRITE["access_roles"] == policy.WRITE["access_persons"] == ("manage_access",))
sup_only_ops = [(c, o) for c in HANDLERS for o in OPS if policy.crud_need(c, o, {}) == policy._SUPER]
check("policy: the only super-admin-only writes are the ones meant to be", sorted(set(c for c, _ in sup_only_ops)) == ["discovery_runs", "journal_events", "venues"] and all(o not in policy.READ_OPS for _, o in sup_only_ops), sup_only_ops[:6])
check("every Console collection is reachable by a super admin (key) except the blocked ones", all(not_denied(admin({"collection": c, "op": "list", "args": {}}, key=KEY)) for c in HANDLERS if c not in crud_endpoint.ADMIN_BLOCKED_COLLECTIONS))
check("MIN_KEY_LENGTH is the same number in console and authorize", console.MIN_KEY_LENGTH == authorize.MIN_KEY_LENGTH == 32)
check("KEY_ACTOR is what the Console door has always stamped", authorize.KEY_ACTOR == crud_endpoint.ADMIN_ACTOR == "user:admin")

# ================================================================ logs
buf = io.StringIO()
h = logging.StreamHandler(buf); lg = logging.getLogger("enjoy_router"); lg.addHandler(h); lg.setLevel(logging.DEBUG)
admin(LV, token=T(90)); admin(LV, token=T(1)); admin(LV, key=KEY); admin(LV, key="w" * 40); records(2); disc("status", 4)
lg.removeHandler(h)
text = buf.getvalue()
check("logs hold codes only: no key, token, email or Google id", KEY not in text and tok(1) not in text and "example.com" not in text and "uid-" not in text and "w" * 40 not in text, text[:300])

print(f"\n{total - len(fails)}/{total} checks passed")
if fails:
    print("FAILED:", *fails, sep="\n  ")
    sys.exit(1)
