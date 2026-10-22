#!/usr/bin/env python3
"""The urgent "no trainer" notice (P-83 build 2): the receipt line, who is told, what each copy holds (the Inspector's none of the requester's
private data), no repeat on a retry, a completion-link edit that turns a request urgent, and the digest's wording. Real CMS and renderer, a fake
channel: nothing is sent. Run from enjoy_router/:  python3 -B run_coverage_notice_tests.py  (-v lists every check)."""
import json, pathlib, sys
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import comms  # noqa: E402
import registration_service as RS  # noqa: E402
import request_completion as RCMP  # noqa: E402
from comms.channels.fake import FakeChannel  # noqa: E402
from core import Schemas  # noqa: E402
from crud import comms_settings_crud as CS  # noqa: E402
from crud import message_templates_crud as MT  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from launch_comms import coverage_context as CC  # noqa: E402
from launch_comms import kinds as K  # noqa: E402
from launch_comms.directory import IndividualDirectory  # noqa: E402
from launch_comms.stores import LogStore, SettingsStore, TemplateStore  # noqa: E402
from launch_discovery import zip_table  # noqa: E402
from memory_store import MemoryStore  # noqa: E402
from ratelimit import RateLimiter  # noqa: E402
from run_tests import build_body  # noqa: E402

SCHEMAS = HERE.parent / "schemas"
SEED = json.loads((SCHEMAS / "examples" / "message_template.seed.json").read_text())["templates"]
REC = json.loads((SCHEMAS / "examples" / "registration_request.test_records.json").read_text())
NOW = datetime(2026, 10, 22, 15, 0, 0, tzinfo=timezone.utc)
A = "user:admin"
fails, total, clock = [], 0, [0]
def tick():
    clock[0] += 5
    return NOW - timedelta(days=1) + timedelta(seconds=clock[0])
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    if not ok or "-v" in sys.argv: print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")

zip_table.set_table({"54843": ["WI", 46.0, -91.4, "Hayward"], "80301": ["CO", 40.0, -105.2, "Boulder"], "80202": ["CO", 39.7, -105.0, "Denver"],
                     "10001": ["NY", 40.7, -74.0, "New York"]})
s = MemoryDocStore("")
for t in SEED:
    r = MT.create(s, {k: t[k] for k in ("kind", "channel", "audience", "name", "subject", "blocks", "is_active")}, A, now=tick()); assert r.ok, r.problems
    assert MT.publish(s, r.data["id"], A, now=tick()).ok
assert CS.create(s, {}, A, now=tick()).ok
ch = FakeChannel()
comms.configure(comms.Comms(kinds=K.registry(), directory=IndividualDirectory(s), templates=TemplateStore(s), log=LogStore(s), settings=SettingsStore(s),
                            channels=[ch], mode="live", clock=lambda: NOW))

def area(i, kind, name, state, zips=None, active=True):
    d = {"id": i, "kind": kind, "name": name, "state_code": state, "is_active": active, "schema_version": 1}
    if zips is not None: d["zip_codes"] = zips
    return d
for a in (area("s-co", "state", "Colorado", "CO"), area("s-wi", "state", "Wisconsin", "WI"), area("s-ny", "state", "New York", "NY"),
          area("r-bou", "region", "Boulder", "CO", ["80301"])):
    s.create("discovery_areas", a["id"], a)
def role(i, key, sup=False, caps=()):
    s.create("access_roles", i, {"id": i, "key": key, "label": key, "capabilities": list(caps), "is_super_admin": sup, "is_active": True, "schema_version": 1})
def person(i, email, rid, name, grants=None):
    d = {"id": i, "email": email, "role_id": rid, "display_name": name, "is_active": True, "schema_version": 1}
    if grants: d["grants"] = grants
    s.create("access_persons", i, d)
role("ro-sup", "super_admin", True, ("inspect_everything",)); role("ro-adm", "admin", False, ("view_console",))
role("ro-ins", "global_inspector", False, ("view_console", "inspect_everything")); role("ro-mgr", "manager", False, ("view_console",))
person("p-sup", "todd@example.com", "ro-sup", "Todd Beetcher"); person("p-adm", "admin@example.com", "ro-adm", "Ada Admin")
person("p-ins", "eli@example.com", "ro-ins", "Eli Inspector")
person("p-wi", "wi@example.com", "ro-mgr", "Wanda Wisconsin", [{"kind": "state", "state_code": "WI"}])
person("p-co", "co@example.com", "ro-mgr", "Cole Colorado", [{"kind": "state", "state_code": "CO"}])

class Both:
    """The registration store and the access/area documents behind one object, as the deployed store is."""
    def __init__(self, reg, docs): self._r, self._d = reg, docs
    def __getattr__(self, n): return getattr(self._r, n) if hasattr(self._r, n) else getattr(self._d, n)
setup = REC["setup"]
reg = MemoryStore(setup["scheduled_classes"], setup.get("registration_venues", []), setup.get("registration_curriculums", []), [a for a in s.query("discovery_areas", [], limit=100)])
store = Both(reg, s)
schemas = Schemas.load(SCHEMAS)
by_name = {t["name"]: t for t in REC["tests"]}
def body(name, **ov):
    b = dict(build_body(by_name["t47_private_small_ask"], by_name)); b.update(ov); return b
def sent(): return [x for x in ch.sent]
def to(addr): return [x for x in ch.sent if x["to"] == addr]

# ---- an uncovered ZIP: the receipt line and the urgent notices
res = RS.register(body("x", email="barty@example.com", first_name="Barty", last_name="Crouch", postal_code="54843", idempotency_key="2c0d0e0f-0000-5000-8000-000000000501"), store, schemas, NOW)
doc = res.doc
check("a private request from an uncovered ZIP is taken and stamped", res.outcome == "created" and doc["coverage"] == "no_active_region" and doc["coverage_state_code"] == "WI")
rcpt = to("barty@example.com")
check("the receipt carries the securing-a-trainer line", len(rcpt) == 1 and "We're securing the best trainer for your area." in rcpt[0]["content"]["text"], str(rcpt[:1])[:200])
told = sorted(x["to"] for x in sent() if x["to"] != "barty@example.com")
check("told: super admin, admin, Inspector and Wisconsin's state owner (not Colorado's)", told == ["admin@example.com", "eli@example.com", "todd@example.com", "wi@example.com"], str(told))
adm = to("admin@example.com")[0]["content"]
check("the staff subject names the requester and the place", adm["subject"] == "ACTION: no trainer for Barty Crouch in Hayward, WI", adm["subject"])
check("the staff copy has the requester's details", all(x in adm["text"] for x in ("barty@example.com", "54843", "Barty Crouch", doc["confirmation_number"])))
ins = to("eli@example.com")[0]["content"]
check("the Inspector's subject has the town and state, no name", ins["subject"] == "ACTION: no trainer for a request in Hayward, WI", ins["subject"])
blob = ins["subject"] + ins["text"] + ins["html"]
check("BREAK-IT: the Inspector's copy holds no name, email, phone, ZIP or confirmation number", not any(x in blob for x in ("Barty", "Crouch", "barty@", "54843", doc["confirmation_number"], str(doc.get("phone", "no-phone")))), blob[:300])
check("the Inspector's context never held a private fact", set(CC.alert_facts(doc, True, "new", "Eli")) == {"name", "who", "town", "state_code", "reason", "console_url"})
check("an Inspector with a state grant is still sent the masked copy", all(r["masked"] for r in __import__("launch_comms.coverage_recipients", fromlist=["x"]).recipients(s, "WI") if "inspector" in r["reasons"]))
check("each told person got exactly one notice", len(told) == len(set(told)))
check("the notices are logged", len([x for x in s.query("communication_logs", [], limit=100) if x.get("kind") == "no_trainer_alert"]) == 4)

# a retry (the same event) sends nothing more
import coverage_alerts  # noqa: E402
before = len(sent())
coverage_alerts.send(store, doc, "new", doc["created_at"])
check("a retry of the same event is not sent again", len(sent()) == before)

# ---- a covered request: no urgent notice, no receipt line
n = len(sent())
res2 = RS.register(body("x", email="covered@example.com", postal_code="80301", idempotency_key="2c0d0e0f-0000-5000-8000-000000000502"), store, schemas, NOW)
new = sent()[n:]
check("a covered request sends only the ordinary receipt, without the securing line", len(new) == 1 and new[0]["to"] == "covered@example.com" and "securing the best trainer" not in new[0]["content"]["text"])
res3 = RS.register(body("x", email="nozip@example.com", idempotency_key="2c0d0e0f-0000-5000-8000-000000000503"), store, schemas, NOW)
check("a request with nothing to judge sends no urgent notice", len([x for x in sent() if "ACTION" in x["content"]["subject"]]) == 4)

# ---- a completion-link edit that turns a request urgent
lim = RateLimiter(rules=((600, 1000),))
s.create("registration_requests", res2.doc["id"], dict(res2.doc))     # the completion link works on the document store
tok = res2.doc["completion_token"]
n = len(sent())
r = RCMP.handle_completion("POST", {}, json.dumps({"t": tok, "changes": {"postal_code": "80202"}}).encode(), "v", store, schemas, lim, NOW)
check("an edit to an uncovered ZIP is accepted and re-stamped", r.status == 200 and s.get("registration_requests", res2.doc["id"]).get("coverage") == "no_active_region")
now_urgent = [x for x in sent()[n:] if "ACTION" in x["content"]["subject"]]
check("an edit that turns a request urgent sends the notice (Colorado's owner included)", sorted(x["to"] for x in now_urgent) == ["admin@example.com", "co@example.com", "eli@example.com", "todd@example.com"], str([x["to"] for x in now_urgent]))
n = len(sent())
RCMP.handle_completion("POST", {}, json.dumps({"t": tok, "changes": {"phone": "303-555-0100"}}).encode(), "v", store, schemas, lim, NOW + timedelta(seconds=5))
check("an edit that leaves it urgent sends nothing more", len(sent()) == n)

# ---- the digest wording
rec = {"person_id": "p-adm", "email": "admin@example.com", "name": "Ada Admin"}
call = CC.digest_call(rec, [("Hayward", "WI"), ("Hayward", "WI"), ("Denver", "CO")], 4, "2026-10-22")
check("digest facts: count, places most first, oldest", call["context"]["count"] == "3" and call["context"]["places"] == "Hayward, WI (2); Denver, CO (1)" and call["context"]["longest_wait"] == "4 days" and CC.wait_words(0) == "less than a day" and CC.wait_words(1) == "1 day")
check("digest context passes the kind's schema", K.registry().validate("no_trainer_digest", call["context"]) == [])
n = len(sent()); out = comms.notify(**call)
sub = sent()[n]["content"]["subject"] if len(sent()) > n else ""
check("digest renders with an urgent-but-plain subject and no private data", out.status == "sent" and sub == "Reminder: requests still waiting for a trainer (3)" and "@" not in sent()[n]["content"]["text"].replace("admin@example.com", ""))
check("a digest for the same person and day is not repeated, but a hand send is", comms.notify(**call).reason == "duplicate" and comms.notify(**dict(call, trigger="manual")).status == "sent")

print(f"{'OK' if not fails else 'FAILED'}: {total - len(fails)}/{total} checks")
sys.exit(1 if fails else 0)
