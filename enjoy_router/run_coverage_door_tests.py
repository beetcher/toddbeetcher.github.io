#!/usr/bin/env python3
"""Mark handled and the waiting flag (P-83 build 3): who may mark a no-trainer request handled (break-it checks on who-can-write), that the
note is required, that the Inspector can neither mark nor read the note, and that the Console's list says which requests still wait.
Run from enjoy_router/:  python3 -B run_coverage_door_tests.py  (-v lists every check). Nothing touches Firebase; Google is a fake verifier."""
import json, pathlib, sys
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from console import handle_console, make_failure_limiter  # noqa: E402
from crud import access_persons_crud as PE, access_roles_crud as RO  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud_endpoint import handle_admin  # noqa: E402
from launch_discovery import zip_table  # noqa: E402
from memory_store import MemoryStore  # noqa: E402

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

zip_table.set_table({"80301": ["CO", 40.0, -105.2, "Boulder"], "80202": ["CO", 39.7, -105.0, "Denver"], "54843": ["WI", 46.0, -91.4, "Hayward"], "53703": ["WI", 43.0, -89.4, "Madison"]})
store = MemoryDocStore("")
def uid(n): return f"{n:08d}-0000-4000-8000-000000000000"
def raw(coll, n, **kw):
    store.create(coll, uid(n), {"id": uid(n), "schema_version": 1, "created_at": "2026-10-20T00:00:00Z", "updated_at": "2026-10-20T00:00:00Z", **kw}); return uid(n)
def area(n, kind, st, name, **kw): return raw("discovery_areas", n, kind=kind, state_code=st, name=name, is_active=True, **kw)
area(1, "state", "CO", "Colorado"); area(2, "state", "WI", "Wisconsin")
BOULDER = area(10, "region", "CO", "Boulder", zip_codes=["80301"])
P = dict(registration_type="private", attendee_count=1, first_name="P", last_name="Q", email="p@example.com", confirmation_number="ICDT-AAAAAA")
rDen = raw("registration_requests", 100, postal_code="80202", coverage="no_active_region", coverage_state_code="CO", **P)
rDen2 = raw("registration_requests", 101, postal_code="80202", coverage="no_active_region", coverage_state_code="CO", **P)
rHay = raw("registration_requests", 102, postal_code="54843", coverage="no_active_region", coverage_state_code="WI", **P)
rBou = raw("registration_requests", 103, postal_code="80301", coverage="covered", coverage_state_code="CO", **P)
rPlain = raw("registration_requests", 104, postal_code="80202", **P)
rDen3 = raw("registration_requests", 105, postal_code="80202", coverage="no_active_region", coverage_state_code="CO", **P)
rDen4 = raw("registration_requests", 106, postal_code="80202", coverage="no_active_region", coverage_state_code="CO", **P)

sup = RO.create(store, {"key": "super_admin", "label": "Super", "is_super_admin": True}, A, now=tick()).data
mgr = RO.create(store, {"key": "manager", "label": "Manager", "is_super_admin": False, "capabilities": ["view_console", "manage_requests"]}, A, now=tick()).data
viewer = RO.create(store, {"key": "viewer", "label": "Viewer", "is_super_admin": False, "capabilities": ["view_console"]}, A, now=tick()).data
insp = RO.create(store, {"key": "global_inspector", "label": "Global Inspector", "is_super_admin": False, "capabilities": ["inspect_everything"]}, A, now=tick()).data
class Fake:
    def __init__(self): self.tokens = {}
    def verify(self, t): return dict(self.tokens[t])
V = Fake()
def tok(n): return f"header{n:03d}.payload{n:03d}.signature{n:03d}" + "x" * 20
def who(n, email, role, grants=None):
    r = PE.create(store, {"email": email, "role_id": role["id"], **({"grants": grants} if grants is not None else {})}, A, now=tick()); assert r.ok, r.problems
    V.tokens[tok(n)] = {"uid": f"uid-{n}", "email": email, "email_verified": True, "provider": "google.com", "name": email}
CAP = ["manage_requests"]
who(1, "todd@x.com", sup)
who(2, "co.owner@x.com", mgr, [{"kind": "state", "state_code": "CO"}])
who(3, "wi.owner@x.com", mgr, [{"kind": "state", "state_code": "WI"}])
who(4, "boulder@x.com", mgr, [{"kind": "regions", "state_code": "CO", "region_ids": [BOULDER], "capabilities": CAP}])
who(5, "nobody@x.com", mgr, [])
who(6, "look.only@x.com", viewer, [])
who(7, "eli@x.com", insp, [])
who(8, "all@x.com", mgr, [{"kind": "all"}])
def call(n, op, args, collection="attendances"):
    r = handle_admin("POST", f"Bearer {tok(n)}", json.dumps({"collection": collection, "op": op, "args": args}).encode(), KEY, "v", store, make_failure_limiter(), tick(), verifier=V)
    return r.status, r.body
def mark(n, rid, note="Called the family; a trainer from the next state will go."): return call(n, "mark_request_handled", {"id": rid, "note": note})
def doc(rid): return store.get("registration_requests", rid)

# ---- who may mark handled
st, b = mark(1, rDen)
check("the super admin marks a waiting request handled", st == 200 and doc(rDen).get("coverage_handled_note", "").startswith("Called") and doc(rDen)["coverage_handled_by"].startswith("user:") and doc(rDen).get("coverage_handled_at"), f"{st} {b}")
check("the request's other fields are untouched", doc(rDen)["coverage"] == "no_active_region" and doc(rDen)["postal_code"] == "80202")
st, b = mark(2, rDen2)
check("a state owner marks a request in their state handled", st == 200, f"{st} {b}")
check("BREAK-IT: a state owner may NOT mark another state's request", mark(2, rHay)[0] == 403 and "coverage_handled_at" not in doc(rHay))
check("BREAK-IT: the other state's owner may", mark(3, rHay)[0] == 200)
check("BREAK-IT: a region head (regions grant) may not mark a state's request", mark(4, rDen3)[0] == 403 and "coverage_handled_at" not in doc(rDen3))
check("BREAK-IT: a person with no grant may not", mark(5, rDen3)[0] == 403)
check("BREAK-IT: a viewer role with no grant may not", mark(6, rDen3)[0] == 403)
st, b = mark(7, rDen3)
check("BREAK-IT: the Global Inspector may not, and nothing changes", st == 403 and "coverage_handled_at" not in doc(rDen3) and "coverage_handled_note" not in doc(rDen3), f"{st} {b}")
check("a person with an all-territory grant may", mark(8, rDen3)[0] == 200)

# ---- what a mark needs
for label, note in (("no note", None), ("an empty note", ""), ("a note of spaces", "   "), ("a note over 2000 characters", "x" * 2001)):
    st, b = call(1, "mark_request_handled", {"id": rDen4, **({"note": note} if note is not None else {})}) if note is not None else call(1, "mark_request_handled", {"id": rDen4})
    check(f"{label} is refused and nothing is stamped", st == 400 and "coverage_handled_at" not in doc(rDen4), f"{st} {b}")
st, b = mark(1, rDen)
check("marking an already handled request is refused", st == 400 and any(p["issue"] == "not_waiting" for p in b["error"]["problems"]), f"{st} {b}")
st, b = mark(1, rBou)
check("a covered request is not waiting", st == 400 and any(p["issue"] == "not_waiting" for p in b["error"]["problems"]))
check("a request with no coverage stamp is not waiting", mark(1, rPlain)[0] == 400)
check("an unknown request is not found", mark(1, uid(999))[0] == 404 and mark(1, "nope")[0] in (400, 404))
raw("discovery_areas", 11, kind="region", state_code="CO", name="Denver", is_active=True, zip_codes=["80202"])
st, b = mark(1, rDen4)
check("a request whose ZIP a region now holds has closed itself: not waiting", st == 400 and any(p["issue"] == "not_waiting" for p in b["error"]["problems"]), f"{st} {b}")

# ---- the Console list says which requests still wait
store.delete("discovery_areas", uid(11)) if hasattr(store, "delete") else store.data["discovery_areas"].pop(uid(11), None)
reg = MemoryStore([], [], [], [dict(a) for a in store.query("discovery_areas", [], limit=100)])
reg.requests = [dict(store.get("registration_requests", r)) for r in (rDen, rDen2, rHay, rBou, rPlain, rDen3, rDen4)]
def records(n):
    r = handle_console("GET", f"Bearer {tok(n)}", {}, KEY, "v", reg, make_failure_limiter(), tick(), verifier=V, access_store=store)
    return r.status, ({x["id"]: x for x in r.body["data"]["records"]} if r.status == 200 else {})
st, recs = records(1)
check("the list flags exactly the urgent, unhandled requests", st == 200 and sorted(i for i, x in recs.items() if x.get("coverage_waiting")) == [rDen4], str(sorted(i for i, x in recs.items() if x.get("coverage_waiting"))))
check("a handled request is not flagged but shows when it was handled", "coverage_waiting" not in recs[rDen] and recs[rDen].get("coverage_handled_at"))
raw("discovery_areas", 12, kind="region", state_code="CO", name="Denver", is_active=True, zip_codes=["80202"])
reg2 = MemoryStore([], [], [], [dict(a) for a in store.query("discovery_areas", [], limit=100)]); reg2.requests = reg.requests
reg_saved, reg = reg, reg2
st, recs = records(1)
check("once an active region holds the ZIP, the request is no longer flagged", not any(x.get("coverage_waiting") for x in recs.values()))
reg = reg_saved
st, recs = records(2)
check("a state owner's list: Colorado's flagged request only", st == 200 and rHay not in recs and recs[rDen4].get("coverage_waiting") is True, str(sorted(recs)))
st, recs = records(7)
check("the Inspector sees the flag but not the note, and the ZIP is masked", st == 200 and recs[rDen4].get("coverage_waiting") is True and "coverage_handled_note" not in recs[rDen] and recs[rDen4]["postal_code"] == "(hidden)", str(recs.get(rDen)))

print(f"{'OK' if not fails else 'FAILED'}: {total - len(fails)}/{total} checks")
sys.exit(1 if fails else 0)
