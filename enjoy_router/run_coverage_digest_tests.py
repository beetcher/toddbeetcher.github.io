#!/usr/bin/env python3
"""The daily reminder and Send reminders now (P-83 build 4): who gets which list, nothing when nothing waits, once a day, a hand send always goes,
no private data in any copy, and who may press the button (break-it checks). Real CMS and renderer, a fake channel: nothing is sent.
Run from enjoy_router/:  python3 -B run_coverage_digest_tests.py  (-v lists every check)."""
import json, pathlib, sys
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import comms  # noqa: E402
import coverage_digest as CD  # noqa: E402
from comms.channels.fake import FakeChannel  # noqa: E402
from console import make_failure_limiter  # noqa: E402
from crud import access_persons_crud as PE, access_roles_crud as RO, comms_settings_crud as CS, message_templates_crud as MT  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud_endpoint import handle_admin  # noqa: E402
from launch_comms import kinds as K  # noqa: E402
from launch_comms.directory import IndividualDirectory  # noqa: E402
from launch_comms.stores import LogStore, SettingsStore, TemplateStore  # noqa: E402
from launch_discovery import zip_table  # noqa: E402

SCHEMAS = HERE.parent / "schemas"
SEED = json.loads((SCHEMAS / "examples" / "message_template.seed.json").read_text())["templates"]
NOW = datetime(2026, 10, 22, 14, 0, 0, tzinfo=timezone.utc)      # 8:00 Mountain
A, KEY = "user:admin", "k" * 16 + "Z" * 16 + "-test-key-not-real"
fails, total, clock = [], 0, [0]
def tick():
    clock[0] += 5
    return NOW - timedelta(days=2) + timedelta(seconds=clock[0])
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    if not ok or "-v" in sys.argv: print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")

zip_table.set_table({"80301": ["CO", 40.0, -105.2, "Boulder"], "80202": ["CO", 39.7, -105.0, "Denver"], "54843": ["WI", 46.0, -91.4, "Hayward"]})
s = MemoryDocStore("")
for t in SEED:
    r = MT.create(s, {k: t[k] for k in ("kind", "channel", "audience", "name", "subject", "blocks", "is_active")}, A, now=tick()); assert r.ok, r.problems
    assert MT.publish(s, r.data["id"], A, now=tick()).ok
assert CS.create(s, {}, A, now=tick()).ok
ch = FakeChannel()
comms.configure(comms.Comms(kinds=K.registry(), directory=IndividualDirectory(s), templates=TemplateStore(s), log=LogStore(s), settings=SettingsStore(s),
                            channels=[ch], mode="live", clock=lambda: NOW))
def uid(n): return f"{n:08d}-0000-4000-8000-000000000000"
def raw(coll, n, **kw):
    s.create(coll, uid(n), {"id": uid(n), "schema_version": 1, "created_at": "2026-10-20T00:00:00Z", "updated_at": "2026-10-20T00:00:00Z", **kw}); return uid(n)
def area(n, kind, st, name, **kw): return raw("discovery_areas", n, kind=kind, state_code=st, name=name, is_active=True, **kw)
area(1, "state", "CO", "Colorado"); area(2, "state", "WI", "Wisconsin"); area(10, "region", "CO", "Boulder", zip_codes=["80301"])

# ---- nobody waiting: nothing sent
sup = RO.create(s, {"key": "super_admin", "label": "Super", "is_super_admin": True}, A, now=tick()).data
adm = RO.create(s, {"key": "admin", "label": "Admin", "is_super_admin": False, "capabilities": ["view_console", "manage_requests"]}, A, now=tick()).data
mgr = RO.create(s, {"key": "manager", "label": "Manager", "is_super_admin": False, "capabilities": ["view_console", "manage_requests"]}, A, now=tick()).data
insp = RO.create(s, {"key": "global_inspector", "label": "Global Inspector", "is_super_admin": False, "capabilities": ["inspect_everything"]}, A, now=tick()).data
class Fake:
    def __init__(self): self.tokens = {}
    def verify(self, t): return dict(self.tokens[t])
V = Fake()
def tok(n): return f"header{n:03d}.payload{n:03d}.signature{n:03d}" + "x" * 20
def who(n, email, role, name, grants=None):
    r = PE.create(s, {"email": email, "display_name": name, "role_id": role["id"], **({"grants": grants} if grants is not None else {})}, A, now=tick()); assert r.ok, r.problems
    V.tokens[tok(n)] = {"uid": f"uid-{n}", "email": email, "email_verified": True, "provider": "google.com", "name": name}
who(1, "todd@x.com", sup, "Todd Beetcher")
who(2, "admin@x.com", adm, "Ada Admin", [{"kind": "all"}])
who(3, "eli@x.com", insp, "Eli Inspector", [])
who(4, "co@x.com", mgr, "Cole Colorado", [{"kind": "state", "state_code": "CO"}])
who(5, "wi@x.com", mgr, "Wanda Wisconsin", [{"kind": "state", "state_code": "WI"}])
who(6, "head@x.com", mgr, "Rhea Head", [{"kind": "regions", "state_code": "CO", "region_ids": [uid(10)], "capabilities": ["manage_requests"]}])
who(7, "plain@x.com", mgr, "Pat Plain", [])
P = dict(registration_type="private", attendee_count=1, last_name="Secretname", phone="303-555-0188", confirmation_number="ICDT-ZZZZZZ")
out = CD.run(s, NOW)
check("nothing waiting: nothing is sent", out == {"waiting": 0, "people": 0, "sent": 0, "not_sent": 0} and not ch.sent, str(out))

raw("registration_requests", 100, first_name="Den1", email="den1.private@example.com", postal_code="80202", coverage="no_active_region", coverage_state_code="CO", **P)
raw("registration_requests", 101, first_name="Den2", email="den2.private@example.com", postal_code="80202", coverage="no_active_region", coverage_state_code="CO", **P)
raw("registration_requests", 102, first_name="Hay1", email="hay1.private@example.com", postal_code="54843", coverage="no_active_region", coverage_state_code="WI", **P)
raw("registration_requests", 103, first_name="Cov", email="cov@example.com", postal_code="80301", coverage="covered", coverage_state_code="CO", **P)
raw("registration_requests", 104, first_name="Done", email="done@example.com", postal_code="80202", coverage="no_active_region", coverage_state_code="CO", coverage_handled_at="2026-10-21T00:00:00Z", **P)
raw("registration_requests", 105, first_name="Gone", email="gone@example.com", postal_code="80202", coverage="no_active_region", coverage_state_code="CO", deleted_at="2026-10-21T00:00:00Z", **P)

out = CD.run(s, NOW)
by = {x["to"]: x["content"] for x in ch.sent}
check("three are waiting (the covered, handled and deleted ones are not); five people are told", out["waiting"] == 3 and out["people"] == 5 and out["sent"] == 5, str(out))
check("told: super admin, admin, Inspector, Colorado's owner, Wisconsin's owner; not a region head or a person with no grant", sorted(by) == ["admin@x.com", "co@x.com", "eli@x.com", "todd@x.com", "wi@x.com"], str(sorted(by)))
check("super admin, admin and Inspector see every state", all("Denver, CO (2); Hayward, WI (1)" in by[a]["text"] and "(3)" in by[a]["subject"] for a in ("todd@x.com", "admin@x.com", "eli@x.com")), by["todd@x.com"]["text"])
check("BREAK-IT: Colorado's owner sees only Colorado", "Denver, CO (2)" in by["co@x.com"]["text"] and "Hayward" not in by["co@x.com"]["text"] and "(2)" in by["co@x.com"]["subject"])
check("BREAK-IT: Wisconsin's owner sees only Wisconsin", "Hayward, WI (1)" in by["wi@x.com"]["text"] and "Denver" not in by["wi@x.com"]["text"] and "(1)" in by["wi@x.com"]["subject"])
blob = " ".join(c["subject"] + c["text"] + c["html"] for c in by.values())
check("BREAK-IT: no copy holds a requester's name, email, phone, ZIP or confirmation number", not any(x in blob for x in ("Den1", "Hay1", "Secretname", "private@example", "303-555", "80202", "54843", "ICDT-ZZZZZZ")), blob[:200])
check("the longest wait is told in words", "Longest wait so far: 2 days." in by["todd@x.com"]["text"], by["todd@x.com"]["text"])

# ---- once a day, a hand send always goes
n = len(ch.sent)
out = CD.run(s, NOW + timedelta(minutes=5))
check("the same day again: nobody is told twice", len(ch.sent) == n and out["sent"] == 0 and out["not_sent"] == 5, str(out))
out = CD.run(s, NOW + timedelta(minutes=6), manual=True)
check("a hand send (Send reminders now) goes anyway", out["sent"] == 5 and len(ch.sent) == n + 5, str(out))
out = CD.run(s, NOW + timedelta(days=1))
check("the next day it is sent again", out["sent"] == 5)
# a region takes the ZIP: it closes itself
area(11, "region", "CO", "Denver", zip_codes=["80202"])
n = len(ch.sent); out = CD.run(s, NOW + timedelta(days=2))
check("once an active region holds the Denver ZIP only Hayward is left: Colorado's owner hears nothing", out["waiting"] == 1 and sorted(x["to"] for x in ch.sent[n:]) == ["admin@x.com", "eli@x.com", "todd@x.com", "wi@x.com"], str(out))

# ---- who may press Send reminders now (break-it)
def press(n, collection="attendances"):
    r = handle_admin("POST", f"Bearer {tok(n)}", json.dumps({"collection": collection, "op": "send_coverage_reminders", "args": {}}).encode(), KEY, "v", s, make_failure_limiter(), NOW + timedelta(days=3), verifier=V)
    return r.status, r.body
n = len(ch.sent)
st, b = press(1); check("the super admin may press it", st == 200 and b["data"]["waiting"] == 1 and len(ch.sent) > n, f"{st} {b}")
n = len(ch.sent)
st, b = press(2); check("an admin may press it", st == 200 and len(ch.sent) > n, f"{st} {b}")
for num, label in ((3, "the Global Inspector"), (4, "a state owner (manager role)"), (6, "a region head"), (7, "a person with no grant")):
    n = len(ch.sent); st, b = press(num)
    check(f"BREAK-IT: {label} may NOT press it, and nothing is sent", st == 403 and len(ch.sent) == n, f"{st} {b}")
r = handle_admin("POST", "Bearer " + KEY, json.dumps({"collection": "attendances", "op": "send_coverage_reminders", "args": {}}).encode(), KEY, "v", s, make_failure_limiter(), NOW + timedelta(days=3), verifier=V)
check("the admin key (a super admin) may", r.status == 200)
from crud_endpoint import handle_crud_test  # noqa: E402
r = handle_crud_test("POST", "Bearer " + KEY, json.dumps({"collection": "attendances", "op": "send_coverage_reminders", "args": {}}).encode(), KEY, "v", s, make_failure_limiter(), NOW)
check("the test door does not offer it", r.status == 400)

print(f"{'OK' if not fails else 'FAILED'}: {total - len(fails)}/{total} checks")
sys.exit(1 if fails else 0)
