#!/usr/bin/env python3
"""In-memory tests for sign-in access (P-62 step 2): the two handlers (crud/access_roles_crud.py, crud/access_persons_crud.py), the shared
sign-in check (access/authorize.py) and the seed script. Run from enjoy_router/:  python3 run_access_tests.py   (-v lists every check).
Nothing touches Firebase; Google is a fake verifier."""
import json, pathlib, sys
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import seed_access  # noqa: E402
from access import CAPABILITIES, KEY_ACTOR, authenticate  # noqa: E402
from access.capabilities import GLOBAL, TERRITORIAL  # noqa: E402
from crud import access_persons_crud as PE, access_roles_crud as RO  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402

START = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)
A = "user:admin"
KEY = "k" * 40
EX = HERE.parent / "schemas" / "examples"
SCHEMAS = HERE.parent / "schemas"
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

class Fake:
    """A fake Google verifier: token -> claims, or raises. Counts calls."""
    def __init__(self): self.tokens, self.calls = {}, 0
    def verify(self, token):
        self.calls += 1
        if token not in self.tokens: raise ValueError("bad token")
        return dict(self.tokens[token])
def tok(n): return f"header{n:03d}.payload{n:03d}.signature{n:03d}" + "x" * 20     # three parts, long enough
def claims(email, uid="uid-1", verified=True, provider="google.com", name="G Name"):
    return {"uid": uid, "email": email, "email_verified": verified, "provider": provider, "name": name}

def role(s, key, label=None, **kw):
    base = dict(key=key, label=label or key.title(), is_super_admin=False, capabilities=["view_console"])
    r = RO.create(s, {**base, **kw}, A, now=tick()); assert r.ok, r.problems; return r.data
def person(s, email, role_id, **kw):
    r = PE.create(s, {"email": email, "role_id": role_id, **kw}, A, now=tick()); assert r.ok, r.problems; return r.data

# ================================================================ the capability list
schema = json.loads((SCHEMAS / "access_role.schema.json").read_text())
check("CAPABILITIES is read from the schema enum", CAPABILITIES == tuple(schema["properties"]["capabilities"]["items"]["enum"]) and len(CAPABILITIES) == 16)
guide = (SCHEMAS / "ACCESS_ROLE_GUIDE.md").read_text()
check("every capability is explained in the role guide", all(f"| `{c}` |" in guide for c in CAPABILITIES), [c for c in CAPABILITIES if f"| `{c}` |" not in guide])
check("every capability is territorial or global, never both, and the grant schema offers exactly the territorial ones",
      set(TERRITORIAL) | set(GLOBAL) == set(CAPABILITIES) and not set(TERRITORIAL) & set(GLOBAL) and "manage_access" in GLOBAL and "view_console" in GLOBAL
      and set(json.loads((SCHEMAS / "access_person.schema.json").read_text())["properties"]["grants"]["items"]["properties"]["capabilities"]["items"]["enum"]) == set(TERRITORIAL))
check("manage_access and view_console exist", "manage_access" in CAPABILITIES and "view_console" in CAPABILITIES)

# ================================================================ roles: examples
ex = json.loads((EX / "access_role.examples.json").read_text())
for name, rec in ex["valid"].items():
    check(f"role: valid example {name}", RO.create(fresh(), rec, A, now=tick()).ok)
s = fresh()
FILLED = {"missing_is_active"}          # the handler fills is_active with True
for name, rec in ex["invalid"].items():
    if name in FILLED: continue
    check(f"role: invalid example {name} refused", not RO.create(s, rec, A, now=tick()).ok)

# ================================================================ roles: rules
s = fresh()
r = RO.create(s, {"key": "super_admin", "label": " Super admin ", "is_super_admin": True}, A, now=tick())
sup_id = r.data["id"] if r.ok else None
check("role: create trims and starts switched on", r.ok and r.data["label"] == "Super admin" and r.data["is_active"] is True, r.problems)
check("role: stamps the standard fields", r.ok and r.data["created_by"] == A and r.data["schema_version"] == 1 and r.data["source"] == "dashboard")
check("role: duplicate key refused", issues(RO.create(s, {"key": "super_admin", "label": "X", "is_super_admin": True}, A, now=tick())) == [("key", "duplicate")])
check("role: key cannot change", issues(RO.update(s, sup_id, {"key": "owner"}, A, now=tick())) == [("key", "immutable")])
check("role: super admin with capabilities refused", issues(RO.create(s, {"key": "s2", "label": "S2", "is_super_admin": True, "capabilities": ["view_console"]}, A, now=tick())) == [("capabilities", "not_allowed")])
check("role: ordinary role without capabilities refused", issues(RO.create(s, {"key": "empty", "label": "E", "is_super_admin": False}, A, now=tick())) == [("capabilities", "required")])
check("role: ordinary role with an empty list refused", issues(RO.create(s, {"key": "empty", "label": "E", "is_super_admin": False, "capabilities": []}, A, now=tick())) == [("capabilities", "required")])
check("role: unknown capability refused", not RO.create(s, {"key": "x", "label": "X", "is_super_admin": False, "capabilities": ["delete_everything"]}, A, now=tick()).ok)
check("role: read-only field from a sender refused", issues(RO.create(s, {"key": "y", "label": "Y", "is_super_admin": True, "created_by": "user:x"}, A, now=tick())) == [("created_by", "not_allowed")])
rh = role(s, "region_head", capabilities=["view_console", "edit_venues"])
check("role: ordinary role created", rh["capabilities"] == ["view_console", "edit_venues"])
check("role: list is ordered by key", [x["key"] for x in RO.list(s).data["records"]] == ["region_head", "super_admin"])
check("role: update capabilities", RO.update(s, rh["id"], {"capabilities": ["view_console", "edit_venues", "activate_venues"]}, A, now=tick()).ok)
check("role: ordinary role cannot become super admin while keeping capabilities", issues(RO.update(s, rh["id"], {"is_super_admin": True}, A, now=tick())) == [("capabilities", "not_allowed")])
# last super admin role
check("role: last active super admin role cannot be switched off", issues(RO.update(s, sup_id, {"is_active": False}, A, now=tick())) == [("is_active", "last_super_admin")])
check("role: last active super admin role cannot be made ordinary", ("is_super_admin", "last_super_admin") in issues(RO.update(s, sup_id, {"is_super_admin": False, "capabilities": ["view_console"]}, A, now=tick())))
check("role: last active super admin role cannot be deleted", ("id", "last_super_admin") in issues(RO.soft_delete(s, sup_id, A, now=tick())))
sup2 = RO.create(s, {"key": "owner2", "label": "Owner two", "is_super_admin": True}, A, now=tick()).data
check("role: with a second super admin role, the first can be switched off", RO.update(s, sup_id, {"is_active": False}, A, now=tick()).ok)
check("role: the second is now the last and is protected", issues(RO.update(s, sup2["id"], {"is_active": False}, A, now=tick())) == [("is_active", "last_super_admin")])
check("role: a switched-off role can be deleted when nobody holds it", RO.soft_delete(s, sup_id, A, now=tick()).ok and RO.get(s, sup_id).code == "not_found")
check("role: a deleted key can be used again", RO.create(s, {"key": "super_admin", "label": "Back", "is_super_admin": True}, A, now=tick()).ok)
# in use
s = fresh()
sa = RO.create(s, {"key": "super_admin", "label": "Super", "is_super_admin": True}, A, now=tick()).data
rh = role(s, "region_head")
p = person(s, "head@example.com", rh["id"])
check("role: a role people hold cannot be deleted", issues(RO.soft_delete(s, rh["id"], A, now=tick())) == [("id", "in_use")])
check("role: but it can be switched off while held", RO.update(s, rh["id"], {"is_active": False}, A, now=tick()).ok)
PE.soft_delete(s, p["id"], A, now=tick())
check("role: after the person is removed the role can be deleted", RO.soft_delete(s, rh["id"], A, now=tick()).ok)

# ================================================================ persons
s = fresh()
sa = RO.create(s, {"key": "super_admin", "label": "Super", "is_super_admin": True}, A, now=tick()).data
rh = role(s, "region_head", capabilities=["view_console", "edit_venues", "manage_instructors"])
off = RO.create(s, {"key": "retired", "label": "Retired", "is_super_admin": False, "capabilities": ["view_console"], "is_active": False}, A, now=tick()).data
region = {"id": "11111111-1111-4111-8111-111111111111", "kind": "region", "name": "Royal Oak", "state_code": "MI", "is_active": True}
state = {"id": "22222222-2222-4222-8222-222222222222", "kind": "state", "name": "Colorado", "state_code": "CO", "is_active": True}
s.create("discovery_areas", region["id"], region); s.create("discovery_areas", state["id"], state)
indiv = {"id": "33333333-3333-4333-8333-333333333333", "status": "active"}
gone = {"id": "44444444-4444-4444-8444-444444444444", "status": "erased"}
s.create("individuals", indiv["id"], indiv); s.create("individuals", gone["id"], gone)

pex = json.loads((EX / "access_person.examples.json").read_text())
# the examples name roles, a region and a person that must exist, so each valid one runs in a store that has them
for name, rec in pex["valid"].items():
    st = fresh(); r_ = RO.create(st, {"key": "r", "label": "R", "is_super_admin": False, "capabilities": ["view_console"]}, A, now=tick()).data
    st.create("discovery_areas", rec.get("scope_region_id", "x"), {"id": rec.get("scope_region_id", "x"), "kind": "region"}) if rec.get("scope_region_id") else None
    st.create("individuals", rec.get("individual_id", "y"), {"id": rec.get("individual_id", "y"), "status": "active"}) if rec.get("individual_id") else None
    for g in rec.get("grants", []):       # the grants name states and regions that must exist
        if g.get("state_code"): st.create("discovery_areas", f"st-{g['state_code']}", {"id": f"st-{g['state_code']}", "kind": "state", "state_code": g["state_code"]})
        for rid in g.get("region_ids", []): st.create("discovery_areas", rid, {"id": rid, "kind": "region", "state_code": g["state_code"]})
    check(f"person: valid example {name} creates", PE.create(st, dict(rec, role_id=r_["id"]), A, now=tick()).ok)
for name, rec in pex["invalid"].items():
    if name == "missing_is_active": continue          # filled by the handler
    check(f"person: invalid example {name} refused", not PE.create(s, rec, A, now=tick()).ok)

r = PE.create(s, {"email": "  Todd@Gmail.COM ", "display_name": " Todd ", "role_id": sa["id"]}, A, now=tick())
todd = r.data if r.ok else {}
check("person: email trimmed and lowercased, starts switched on", r.ok and todd["email"] == "todd@gmail.com" and todd["display_name"] == "Todd" and todd["is_active"] is True, r.problems)
check("person: no google_uid until first sign-in", "google_uid" not in todd and "last_sign_in_at" not in todd)
check("person: duplicate email refused (any case)", issues(PE.create(s, {"email": "TODD@gmail.com", "role_id": rh["id"]}, A, now=tick())) == [("email", "duplicate")])
check("person: unknown role refused", issues(PE.create(s, {"email": "a@x.com", "role_id": "55555555-5555-4555-8555-555555555555"}, A, now=tick())) == [("role_id", "not_found")])
check("person: switched-off role refused", issues(PE.create(s, {"email": "a@x.com", "role_id": off["id"]}, A, now=tick())) == [("role_id", "not_found")])
check("person: google_uid cannot be sent", issues(PE.create(s, {"email": "a@x.com", "role_id": rh["id"], "google_uid": "abc"}, A, now=tick())) == [("google_uid", "not_allowed")])
check("person: last_sign_in_at cannot be sent", issues(PE.create(s, {"email": "a@x.com", "role_id": rh["id"], "last_sign_in_at": "2026-10-19T00:00:00Z"}, A, now=tick())) == [("last_sign_in_at", "not_allowed")])
check("person: region must exist", issues(PE.create(s, {"email": "a@x.com", "role_id": rh["id"], "scope_region_id": "66666666-6666-4666-8666-666666666666"}, A, now=tick())) == [("scope_region_id", "not_found")])
check("person: a state is not a region", issues(PE.create(s, {"email": "a@x.com", "role_id": rh["id"], "scope_region_id": state["id"]}, A, now=tick())) == [("scope_region_id", "not_found")])
check("person: individual must exist", issues(PE.create(s, {"email": "a@x.com", "role_id": rh["id"], "individual_id": "77777777-7777-4777-8777-777777777777"}, A, now=tick())) == [("individual_id", "not_found")])
check("person: erased individual refused", issues(PE.create(s, {"email": "a@x.com", "role_id": rh["id"], "individual_id": gone["id"]}, A, now=tick())) == [("individual_id", "not_found")])
head = PE.create(s, {"email": "head@example.com", "display_name": "Region Head", "role_id": rh["id"], "scope_region_id": region["id"], "individual_id": indiv["id"]}, A, now=tick())
check("person: region head with territory and person link", head.ok, head.problems)
head = head.data
check("person: list ordered by email", [x["email"] for x in PE.list(s).data["records"]] == ["head@example.com", "todd@gmail.com"])
check("person: list can filter by switched on", PE.list(s, {"is_active": False}).data["count"] == 0)
# role-change rules
check("person: role change checks the new role", issues(PE.update(s, head["id"], {"role_id": off["id"]}, A, now=tick())) == [("role_id", "not_found")])
check("person: change to a good role", PE.update(s, head["id"], {"role_id": rh["id"], "display_name": "RH"}, A, now=tick()).ok)
# a person whose role was switched off can still be switched off (role is only checked when it changes)
r2 = RO.create(s, {"key": "temp", "label": "Temp", "is_super_admin": False, "capabilities": ["view_console"]}, A, now=tick()).data
tp = person(s, "temp@example.com", r2["id"])
RO.update(s, r2["id"], {"is_active": False}, A, now=tick())
check("person: can be switched off even when their role is already off", PE.update(s, tp["id"], {"is_active": False}, A, now=tick()).ok)
check("person: can be removed when their role is off", PE.soft_delete(s, tp["id"], A, now=tick()).ok)
# email immutability after sign-in
check("person: email can change before first sign-in", PE.update(s, head["id"], {"email": "head2@example.com"}, A, now=tick()).ok)
cur = PE.get(s, head["id"]).data
PE.record_sign_in(s, cur, "uid-head", tick())
cur = PE.get(s, head["id"]).data
check("record_sign_in saves google_uid and time without touching updated_at", cur["google_uid"] == "uid-head" and cur["updated_at"] == PE.get(s, head["id"]).data["updated_at"] and "last_sign_in_at" in cur)
check("person: email cannot change after first sign-in", issues(PE.update(s, head["id"], {"email": "head3@example.com"}, A, now=tick())) == [("email", "immutable")])
check("person: google_uid cannot be edited", issues(PE.update(s, head["id"], {"google_uid": "other"}, A, now=tick())) == [("google_uid", "not_allowed")])
before = PE.get(s, head["id"]).data
PE.record_sign_in(s, before, "uid-DIFFERENT", tick())
check("record_sign_in never overwrites an existing google_uid", PE.get(s, head["id"]).data["google_uid"] == "uid-head")
# last super admin
check("person: last super admin cannot be switched off", issues(PE.update(s, todd["id"], {"is_active": False}, A, now=tick())) == [("is_active", "last_super_admin")])
check("person: last super admin cannot move to an ordinary role", issues(PE.update(s, todd["id"], {"role_id": rh["id"]}, A, now=tick())) == [("role_id", "last_super_admin")])
check("person: last super admin cannot be deleted", issues(PE.soft_delete(s, todd["id"], A, now=tick())) == [("id", "last_super_admin")])
other = person(s, "second@example.com", sa["id"])
check("person: with a second super admin the first can be switched off", PE.update(s, todd["id"], {"is_active": False}, A, now=tick()).ok)
check("person: the second is then protected", issues(PE.update(s, other["id"], {"is_active": False}, A, now=tick())) == [("is_active", "last_super_admin")])
check("person: switching the first back on", PE.update(s, todd["id"], {"is_active": True}, A, now=tick()).ok)
PE.update(s, todd["id"], {"is_active": False}, A, now=tick())
check("person: ... the one still on stays protected after that", issues(PE.soft_delete(s, other["id"], A, now=tick())) == [("id", "last_super_admin")])
PE.update(s, todd["id"], {"is_active": True}, A, now=tick())
check("person: a second super admin can be deleted when another remains", PE.soft_delete(s, other["id"], A, now=tick()).ok)
# self protection
me = f"user:{head['id']}"
for f, v in (("role_id", sa["id"]), ("is_active", False), ("scope_region_id", region["id"]), ("email", "mine@example.com")):
    check(f"person: cannot change own {f}", issues(PE.update(s, head["id"], {f: v}, me, now=tick())) == [(f, "not_allowed")])
check("person: can change own display name", PE.update(s, head["id"], {"display_name": "Me"}, me, now=tick()).ok)
check("person: cannot delete themselves", issues(PE.soft_delete(s, head["id"], me, now=tick())) == [("id", "not_allowed")])
check("person: a super admin can change another person", PE.update(s, head["id"], {"is_active": False}, f"user:{todd['id']}", now=tick()).ok)
check("person: removed person is kept and hidden", PE.soft_delete(s, head["id"], A, now=tick()).ok and PE.get(s, head["id"]).code == "not_found"
      and PE.get(s, head["id"], include_deleted=True).data["deleted_at"])
check("person: removed person's email can be invited again", PE.create(s, {"email": "head2@example.com", "role_id": rh["id"]}, A, now=tick()).ok)

# ================================================================ persons: grants (territory)
s = fresh()
sa = RO.create(s, {"key": "super_admin", "label": "Super", "is_super_admin": True}, A, now=tick()).data
rh = role(s, "region_head", capabilities=["view_console", "edit_venues"])
def area(i, kind, st, name, **kw):
    rid = f"{i:08d}-0000-4000-8000-000000000000"
    s.create("discovery_areas", rid, {"id": rid, "kind": kind, "name": name, "state_code": st, "is_active": True, **kw}); return rid
wi_state, mn_state = area(1, "state", "WI", "Wisconsin"), area(2, "state", "MN", "Minnesota")
wi1, wi2, mn1 = area(3, "region", "WI", "Madison", zip_codes=["53703"]), area(4, "region", "WI", "Milwaukee", zip_codes=["53202"]), area(5, "region", "MN", "Rochester", zip_codes=["55901"])
gone_region = area(6, "region", "MN", "Gone", zip_codes=["55902"]); s.update("discovery_areas", gone_region, {"deleted_at": "2026-10-19T00:00:00Z"}, ())
def mk(email, grants, **kw): return PE.create(s, {"email": email, "role_id": rh["id"], "grants": grants, **kw}, A, now=tick())
def regions(ids, caps, st, **kw): return {"kind": "regions", "state_code": st, "region_ids": ids, "capabilities": caps, **kw}
r = mk("a@x.com", [{"kind": "state", "state_code": "WI", "group": "Wisconsin"}, regions([mn1], ["edit_venues", "manage_requests"], "MN")])
check("grants: a whole state plus regions in another state are accepted", r.ok and len(r.data["grants"]) == 2, r.problems)
check("grants: stored as sent (group kept)", r.ok and r.data["grants"][0]["group"] == "Wisconsin" and r.data["grants"][1]["capabilities"] == ["edit_venues", "manage_requests"])
check("grants: a regions grant may hold several regions of its own state", mk("b@x.com", [regions([wi1, wi2], ["manage_requests"], "WI")]).ok)
check("grants: two regions of one state may be in two grants with different capabilities", mk("c@x.com", [regions([wi1], ["edit_venues"], "WI"), regions([wi2], ["manage_requests"], "WI")]).ok)
check("grants: the whole US", mk("d@x.com", [{"kind": "all"}]).ok)
check("grants: none at all is fine (no territory)", mk("e@x.com", []).ok and PE.create(s, {"email": "f@x.com", "role_id": rh["id"]}, A, now=tick()).ok)
az_state = area(7, "state", "AZ", "Arizona"); s.update("discovery_areas", az_state, {"is_active": False}, ())
az_reg = area(8, "region", "AZ", "Tucson", zip_codes=["85701"]); s.update("discovery_areas", az_reg, {"is_active": False}, ())
check("grants: a state that is switched off can still be owned", mk("h@x.com", [{"kind": "state", "state_code": "AZ"}]).ok)
check("grants: a region that is switched off can still be given", mk("i@x.com", [regions([az_reg], ["edit_venues"], "AZ")]).ok)
check("grants: a state with no state record is refused", issues(mk("g@x.com", [{"kind": "state", "state_code": "NV"}])) == [("grants", "not_found")])
check("grants: an unknown region is refused", issues(mk("g@x.com", [regions(["99999999-0000-4000-8000-000000000000"], ["edit_venues"], "WI")])) == [("grants", "not_found")])
check("grants: a deleted region is refused", issues(mk("g@x.com", [regions([gone_region], ["edit_venues"], "MN")])) == [("grants", "not_found")])
check("grants: a state record is not a region", issues(mk("g@x.com", [regions([wi_state], ["edit_venues"], "WI")])) == [("grants", "not_found")])
check("grants: a region in another state is refused", issues(mk("g@x.com", [regions([mn1], ["edit_venues"], "WI")])) == [("grants", "wrong_state")])
check("grants: a global capability is refused in a grant", not mk("g@x.com", [regions([wi1], ["view_spend"], "WI")]).ok and not mk("g@x.com", [regions([wi1], ["manage_access"], "WI")]).ok)
check("grants: the handler itself also refuses a global capability (defence behind the schema)", PE.grant_problems(s, [regions([wi1], ["view_spend"], "WI")]) == [{"field": "grants", "issue": "not_territorial"}])
check("grants: the same region in two grants of one person is refused", issues(mk("g@x.com", [regions([wi1], ["edit_venues"], "WI"), regions([wi1, wi2], ["manage_requests"], "WI")])) == [("grants", "duplicate_region")])
check("grants: shape errors come from the schema (no capabilities on a state grant)", not mk("g@x.com", [{"kind": "state", "state_code": "WI", "capabilities": ["edit_venues"]}]).ok)
check("grants: shape errors come from the schema (regions without capabilities)", not mk("g@x.com", [{"kind": "regions", "state_code": "WI", "region_ids": [wi1]}]).ok)
who = PE.find_live_by_email(s, "a@x.com")
r = PE.update(s, who["id"], {"grants": [regions([wi1], ["edit_venues"], "WI")]}, A, now=tick())
check("grants: a person's grants can be replaced", r.ok and PE.get(s, who["id"]).data["grants"][0]["region_ids"] == [wi1], r.problems)
check("grants: a bad replacement is refused and nothing changes", not PE.update(s, who["id"], {"grants": [regions([mn1], ["edit_venues"], "WI")]}, A, now=tick()).ok and PE.get(s, who["id"]).data["grants"][0]["region_ids"] == [wi1])
check("grants: a person cannot change their own grants", issues(PE.update(s, who["id"], {"grants": [{"kind": "all"}]}, f"user:{who['id']}", now=tick())) == [("grants", "not_allowed")])
s.update("discovery_areas", wi1, {"deleted_at": "2026-10-19T01:00:00Z"}, ())
check("grants: a region removed later does not block other edits to the person", PE.update(s, who["id"], {"display_name": "Still fine"}, A, now=tick()).ok)

# ================================================================ the shared sign-in check
s = fresh()
sa = RO.create(s, {"key": "super_admin", "label": "Super", "is_super_admin": True}, A, now=tick()).data
rh = RO.create(s, {"key": "region_head", "label": "Region head", "is_super_admin": False, "capabilities": ["view_console", "edit_venues"]}, A, now=tick()).data
todd = person(s, "toddbeetcher17@gmail.com", sa["id"], display_name="Todd Beetcher")
s.create("discovery_areas", region["id"], region)
head = person(s, "head@example.com", rh["id"], display_name="Head", scope_region_id=region["id"])
v = Fake()
def auth(given, key=KEY, verifier=v, now=None, store=None):
    return authenticate(given, admin_key=key, verifier=verifier, store=store or s, now=now or tick())

a = auth(KEY)
check("key: ok, acts as a super admin with the old actor", a.ok and a.actor == KEY_ACTOR == "user:admin" and a.is_super_admin and a.method == "key")
check("key: holds every capability", all(a.can(c) for c in CAPABILITIES) and a.can("anything_added_later"))
check("key: verifier is never asked about the key", v.calls == 0)
check("key: wrong key refused", auth("w" * 40).code == "unauthorized" and not auth("w" * 40).ok)
check("key: empty and missing credentials refused", auth("").code == "unauthorized" and auth(None).code == "unauthorized")
check("key: a short key setting is no key (fails closed)", auth("k" * 20, key="k" * 20).code == "unauthorized")
check("nothing configured at all fails closed", authenticate(KEY, admin_key="", verifier=None, store=s, now=tick()).code == "not_configured")
check("key not set but verifier present: key path is closed", auth(KEY, key="").code == "unauthorized")
check("verifier absent: the key still works", authenticate(KEY, admin_key=KEY, verifier=None, store=s, now=tick()).ok)
check("verifier absent: a token-shaped value is just refused", authenticate(tok(1), admin_key=KEY, verifier=None, store=s, now=tick()).code == "unauthorized")

v.tokens[tok(1)] = claims("toddbeetcher17@gmail.com", "uid-todd", name="Google Name")
t0 = START + timedelta(hours=1)
a = auth(tok(1), now=t0)
check("google: invited super admin gets in", a.ok and a.method == "google" and a.is_super_admin and a.email == "toddbeetcher17@gmail.com", a.code)
check("google: a super admin's capabilities list is every capability (the Console reads it)", a.capabilities == frozenset(CAPABILITIES))
check("google: actor is user:<access_person id>", a.actor == f"user:{todd['id']}")
check("google: name comes from the record", a.name == "Todd Beetcher")
check("google: super admin can do anything, listed or not", a.can("manage_access") and a.can("brand_new_capability"))
cur = PE.get(s, todd["id"]).data
check("google: first sign-in saves the Google account id and time", cur["google_uid"] == "uid-todd" and cur["last_sign_in_at"] == t0.strftime("%Y-%m-%dT%H:%M:%SZ"))
a = auth(tok(1), now=t0 + timedelta(minutes=2))
check("google: a repeat within 10 minutes does not write again", PE.get(s, todd["id"]).data["last_sign_in_at"] == t0.strftime("%Y-%m-%dT%H:%M:%SZ") and a.ok)
a = auth(tok(1), now=t0 + timedelta(minutes=11))
check("google: after 10 minutes the time is refreshed", PE.get(s, todd["id"]).data["last_sign_in_at"] == (t0 + timedelta(minutes=11)).strftime("%Y-%m-%dT%H:%M:%SZ") and a.ok)
check("google: a person's sign-in leaves updated_at alone", PE.get(s, todd["id"]).data["updated_at"] == todd["updated_at"])
v.tokens[tok(2)] = claims("TODDBEETCHER17@Gmail.com", "uid-todd")
check("google: email match ignores case", auth(tok(2)).ok)
v.tokens[tok(3)] = claims("toddbeetcher17@gmail.com", "uid-OTHER")
check("google: same email from a different Google account is refused", auth(tok(3)).code == "account_changed")
v.tokens[tok(4)] = claims("stranger@gmail.com", "uid-s")
check("google: an uninvited account is refused", auth(tok(4)).code == "not_invited")
v.tokens[tok(5)] = claims("toddbeetcher17@gmail.com", "uid-todd", verified=False)
check("google: an unverified email is refused", auth(tok(5)).code == "unauthorized")
v.tokens[tok(6)] = claims("toddbeetcher17@gmail.com", "uid-todd", provider="password")
check("google: a non-Google provider is refused", auth(tok(6)).code == "unauthorized")
v.tokens[tok(7)] = {"uid": "u", "email": "", "email_verified": True, "provider": "google.com"}
check("google: a token with no email is refused", auth(tok(7)).code == "unauthorized")
v.tokens[tok(8)] = {"email": "toddbeetcher17@gmail.com", "email_verified": True, "provider": "google.com"}
check("google: a token with no uid is refused", auth(tok(8)).code == "unauthorized")
check("google: a token the verifier rejects is refused", auth(tok(99)).code == "unauthorized")
n = v.calls
check("google: a value that is not token-shaped never reaches the verifier", auth("not-a-token").code == "unauthorized" and v.calls == n)
v.tokens[tok(9)] = claims("head@example.com", "uid-head")
a = auth(tok(9))
check("google: region head gets only the role's capabilities", a.ok and not a.is_super_admin and a.can("edit_venues") and a.can("view_console"))
check("google: region head cannot run Discovery or manage access", not a.can("run_discovery") and not a.can("manage_access") and not a.can("brand_new_capability"))
check("google: scope and role are carried", a.scope_region_id == region["id"] and a.role_key == "region_head")
check("google: capabilities cannot be changed on the result", isinstance(a.capabilities, frozenset))
check("a refused result can do nothing", not auth("w" * 40).can("view_console"))
# switching things off takes effect on the next request
PE.update(s, head_id := PE.find_live_by_email(s, "head@example.com")["id"], {"is_active": False}, A, now=tick())
check("google: a person switched off is refused at once", auth(tok(9)).code == "not_invited")
PE.update(s, head_id, {"is_active": True}, A, now=tick())
check("google: switched back on, they are in again", auth(tok(9)).ok)
RO.update(s, rh["id"], {"is_active": False}, A, now=tick())
check("google: a role switched off refuses everyone who holds it", auth(tok(9)).code == "not_invited")
RO.update(s, rh["id"], {"is_active": True}, A, now=tick())
PE.soft_delete(s, head_id, A, now=tick())
check("google: a removed person is refused", auth(tok(9)).code == "not_invited")
RO.update(s, rh["id"], {"capabilities": ["view_console", "edit_venues", "activate_venues"]}, A, now=tick())
h2 = person(s, "head@example.com", rh["id"], scope_region_id=region["id"])
check("google: a re-invited email starts fresh (new id, new Google binding)", auth(tok(9)).ok and auth(tok(9)).actor == f"user:{h2['id']}" and h2["id"] != head_id)
check("google: role changes show at the next request", auth(tok(9)).can("activate_venues"))
check("no secret appears in the result", KEY not in repr(auth(tok(9))) and KEY not in repr(auth(KEY).capabilities))

# ================================================================ the seed script
s = fresh()
todo, need = seed_access.plan(s, "toddbeetcher17@gmail.com")
check("seed: empty store needs both roles and the person", [r["key"] for r in todo] == ["super_admin", "region_head"] and need)
done = seed_access.apply(s, "toddbeetcher17@gmail.com", "Todd Beetcher")
check("seed: creates two roles and the person", len(done) == 3 and RO.list(s).data["count"] == 2 and PE.list(s).data["count"] == 1, done)
check("seed: nothing left to do afterwards", seed_access.plan(s, "toddbeetcher17@gmail.com") == ([], False))
check("seed: running again adds nothing", seed_access.apply(s, "toddbeetcher17@gmail.com", "Todd Beetcher") == [] and RO.list(s).data["count"] == 2 and PE.list(s).data["count"] == 1)
rec = PE.find_live_by_email(s, "toddbeetcher17@gmail.com")
check("seed: records are marked import by the seed actor", rec["source"] == "import" and rec["created_by"] == "system:access_seed")
v = Fake(); v.tokens[tok(1)] = claims("toddbeetcher17@gmail.com", "uid-todd")
a = authenticate(tok(1), admin_key=KEY, verifier=v, store=s, now=tick())
check("seed: the seeded person signs in as a super admin", a.ok and a.is_super_admin and a.name == "Todd Beetcher")
rh = RO.list(s, {"key": "region_head"}).data["records"][0]
check("seed: region head bundle is as documented", rh["capabilities"] == ["view_console", "edit_venues", "activate_venues", "manage_instructors", "manage_requests"] and not rh["is_super_admin"])
src = (HERE / "seed_access.py").read_text()
check("seed: carries no key, token or password", "password" not in src.lower().replace("no password", "") and "ICDT_ADMIN_KEY" not in src and "Bearer" not in src)
s2 = fresh()
check("seed: another email can be seeded first", seed_access.apply(s2, "other@example.com", "Other") and PE.find_live_by_email(s2, "other@example.com") is not None)

print(f"\n{total - len(fails)}/{total} checks passed" + (f"; FAILED: {fails}" if fails else ""))
sys.exit(1 if fails else 0)
