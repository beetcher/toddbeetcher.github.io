#!/usr/bin/env python3
"""Tests for the invitation email (P-64): inviting someone in Access sends them the access_invite email; Resend invite email sends it again.
Real stores, the real CMS and renderer, a fake channel, the real Console door with a fake Google verifier. Nothing is sent.
Run from enjoy_router/:  python3 run_access_invite_tests.py   (-v lists every check)."""
import json, pathlib, sys
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import comms  # noqa: E402
from comms.channels.fake import FakeChannel  # noqa: E402
from console import make_failure_limiter  # noqa: E402
from crud import access_persons_service as AP  # noqa: E402
from crud import access_roles_crud as RO  # noqa: E402
from crud import communication_logs_crud as LG  # noqa: E402
from crud import comms_settings_crud as CS  # noqa: E402
from crud import message_templates_crud as MT  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
import crud_endpoint  # noqa: E402
from crud_endpoint import ADMIN_OPS, OPS, handle_admin, handle_crud_test  # noqa: E402
from launch_comms import invite_context as IC  # noqa: E402
from launch_comms import kinds as K  # noqa: E402
from launch_comms.directory import IndividualDirectory  # noqa: E402
from launch_comms.stores import LogStore, SettingsStore, TemplateStore  # noqa: E402

SCHEMAS = HERE.parent / "schemas"
SEED = json.loads((SCHEMAS / "examples" / "message_template.seed.json").read_text())["templates"]
NOW = datetime(2026, 10, 21, 12, 0, 0, tzinfo=timezone.utc)
A = "user:admin"
KEY = "k" * 16 + "Z" * 16 + "-test-key-not-real"
fails, total, clock = [], 0, [0]
def tick():
    clock[0] += 5
    return NOW - timedelta(days=1) + timedelta(seconds=clock[0])
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    if not ok or "-v" in sys.argv: print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")

s = MemoryDocStore("")
for t in SEED:
    r = MT.create(s, {k: t[k] for k in ("kind", "channel", "audience", "name", "subject", "blocks", "is_active")}, A, now=tick()); assert r.ok, r.problems
    assert MT.publish(s, r.data["id"], A, now=tick()).ok
assert CS.create(s, {}, A, now=tick()).ok

def wire(channel=None, mode="live", store=None):
    ch = channel or FakeChannel()
    st = store or s
    comms.configure(comms.Comms(kinds=K.registry(), directory=IndividualDirectory(st), templates=TemplateStore(st), log=LogStore(st), settings=SettingsStore(st),
                                channels=[ch], mode=mode, clock=lambda: NOW))
    return ch
def log_of(**flt): return LG.list(s, flt).data["records"]
def invites(): return [x for x in log_of() if x["kind"] == "access_invite"]

# ---- the people and roles
CO, BOULDER, MADISON = ("a0000000-0000-4000-8000-00000000000%d" % i for i in (1, 2, 3))
s.create("discovery_areas", CO, {"id": CO, "kind": "state", "state_code": "CO", "name": "Colorado", "is_active": True})
s.create("discovery_areas", BOULDER, {"id": BOULDER, "kind": "region", "state_code": "CO", "name": "Boulder", "zip_codes": ["80301"], "is_active": True})
s.create("discovery_areas", MADISON, {"id": MADISON, "kind": "region", "state_code": "WI", "name": "Madison", "zip_codes": ["53703"], "is_active": True})
def mkrole(key, caps=None, sup=False, **kw):
    r = RO.create(s, {"key": key, "label": kw.pop("label", key.title()), "is_super_admin": sup, **({} if sup else {"capabilities": caps}), **kw}, A, now=tick()); assert r.ok, r.problems
    return r.data
sup_role = mkrole("super_admin", sup=True, label="Super admin")
mgr_role = mkrole("manager", ["view_console", "manage_requests"], label="Manager", description="Runs classes and requests in their own regions.")
bare_role = mkrole("bare", ["view_console"], label="Viewer")
def reg(rids, caps, st="CO"): return {"kind": "regions", "state_code": st, "region_ids": rids, "capabilities": caps}
class Fake:
    def __init__(self): self.tokens = {}
    def verify(self, token):
        if token not in self.tokens: raise ValueError("bad token")
        return dict(self.tokens[token])
V = Fake()
def tok(n): return f"header{n:03d}.payload{n:03d}.signature{n:03d}" + "x" * 20
def person(n, email, role, **kw):
    r = AP.H.create(s, {"email": email, "role_id": role["id"], **kw}, A, now=tick()); assert r.ok, r.problems
    V.tokens[tok(n)] = {"uid": f"uid-{n}", "email": email, "email_verified": True, "provider": "google.com", "name": email}
    return r.data
todd = person(1, "todd@example.com", sup_role, display_name="Todd Beetcher")
lead = person(2, "lead@example.com", mgr_role, display_name="Lee Lead", grants=[reg([BOULDER], ["invite_people", "manage_requests"])])
outsider = person(3, "madison@example.com", mgr_role, display_name="Mad Ison", grants=[reg([MADISON], ["manage_requests"], "WI")])
plain = person(4, "plain@example.com", mgr_role, display_name="Plain Person", grants=[reg([BOULDER], ["manage_requests"])])
nameless = person(5, "nameless@example.com", bare_role)

# ================================================================ the kind and the template
kd = K.registry().get("access_invite")
check("kind: access_invite is registered with the audience invitee", kd is not None and kd.audiences == ("invitee",))
check("kind: its needed facts are name, inviter, role_name, email, console_url", set(kd.required) == {"name", "inviter", "role_name", "email", "console_url"})
check("kind: role_description is optional", "role_description" in kd.facts and "role_description" not in kd.required)
good = {"name": "Dana", "inviter": "Todd", "role_name": "Manager", "email": "d@example.com", "console_url": "https://beetcher.com/console/"}
check("kind: a full context passes the fact schema", K.registry().validate("access_invite", good) == [])
check("kind: a missing needed fact is refused", K.registry().validate("access_invite", {k: v for k, v in good.items() if k != "email"}) != [])
check("kind: a fact the kind does not know is refused", K.registry().validate("access_invite", {**good, "api_key": "x"}) != [])
tmpl = [t for t in SEED if t["kind"] == "access_invite"]
check("seed: exactly one access_invite template, for the invitee, by email, active", len(tmpl) == 1 and tmpl[0]["audience"] == "invitee" and tmpl[0]["channel"] == "email" and tmpl[0]["is_active"])
check("seed: the template passes the kind's own check (no unknown fact, optional facts guarded)", K.registry().check_template(tmpl[0]) == [])
check("seed: the subject is the one Todd approved", tmpl[0]["subject"] == "You're invited to the LAUNCH Console")

# ================================================================ the facts
f, why = IC.facts(s, AP.get(s, nameless["id"]).data | {"display_name": "Dana Smith"}, f"user:{todd['id']}")
check("facts: first name for the greeting, inviter by name, role label, role description, address and Console link",
      why is None and f["name"] == "Dana" and f["inviter"] == "Todd Beetcher" and f["role_name"] == "Viewer" and f["email"] == "nameless@example.com"
      and f["console_url"] == "https://beetcher.com/console/" and "role_description" not in f, str(f))
f, _ = IC.facts(s, lead, A)
check("facts: a role with a description gives it", f["role_description"] == "Runs classes and requests in their own regions.")
f, _ = IC.facts(s, nameless, A)
check("facts: no name given means the greeting word there", f["name"] == "there")
check("facts: the admin key has no person: The LAUNCH team", f["inviter"] == "The LAUNCH team")
check("facts: an inviter with no name shows their Google email", IC.inviter_of(s, f"user:{nameless['id']}") == "nameless@example.com")
check("facts: an unknown inviter id falls back to The LAUNCH team", IC.inviter_of(s, "user:00000000-0000-4000-8000-000000000000") == "The LAUNCH team")
check("facts: a system actor is not a person", IC.inviter_of(s, "system:cms_seed") == "The LAUNCH team")
ghost = dict(lead, role_id="00000000-0000-4000-8000-000000000009")
check("facts: a person whose role cannot be found cannot be described", IC.facts(s, ghost, A) == (None, "role_not_found"))
call, _ = IC.call_for(s, lead, A, manual=False)
check("call: automatic, to the Google address, audience invitee, a fixed key per person",
      call["trigger"] == "automatic" and call["audience"] == "invitee" and call["recipient"]["email"] == "lead@example.com" and call["dedupe_key"] == f"access_invite:{lead['id']}" and call["kind"] == "access_invite")
call, _ = IC.call_for(s, lead, A, manual=True)
check("call: a hand send is manual", call["trigger"] == "manual")

# ================================================================ inviting sends the email
ch = wire()
me = f"user:{todd['id']}"
r = AP.create(s, {"email": "New.Dana@Example.com", "display_name": "Dana Smith", "role_id": mgr_role["id"]}, me, now=tick())
check("invite: the person is saved", r.ok and r.data["email"] == "new.dana@example.com", str(r.problems if not r.ok else ""))
check("invite: the answer says the email was sent", r.data.get("invite_email") == {"status": "sent", "reason": "ok"}, str(r.data.get("invite_email")))
check("invite: exactly one email went, to the invited address", [m["to"] for m in ch.sent] == ["new.dana@example.com"])
m = ch.sent[0]["content"]
check("invite: subject", m["subject"] == "You're invited to the LAUNCH Console", m["subject"])
txt, html = m["text"], m["html"]
check("invite: greets by first name and says who invited them, as which role", "Hello Dana," in txt and "Todd Beetcher has invited you to the LAUNCH Console as Manager." in txt, txt)
check("invite: says what the role is for", "Runs classes and requests in their own regions." in txt)
check("invite: has the Console address, in the text and as a button", "https://beetcher.com/console/" in txt and 'href="https://beetcher.com/console/"' in html)
check("invite: names the exact Google account to use and the Sign in with Google step", "new.dana@example.com" in txt and "Sign in with Google" in txt)
check("invite: explains that a different account is refused and how to make a Google account", "different Google account will be refused" in txt and "accounts.google.com" in txt)
check("invite: mentions the automatic sign-out", "signs you out after a period of inactivity" in txt)
check("invite: no key, token or placeholder leaks into the message", not any(w in txt + html for w in ("Bearer", "ICDT", "AIza", "{", "}", "None")), txt)
check("invite: no calendar file", m["attachments"] == [])
lg = invites()
check("invite: exactly one log entry: access_invite, sent, automatic, invitee, to the address, no person id",
      len(lg) == 1 and lg[0]["status"] == "sent" and lg[0]["trigger"] == "automatic" and lg[0]["audience"] == "invitee" and lg[0]["to"] == "new.dana@example.com" and "individual_id" not in lg[0], str(lg))
check("invite: the log keeps no message text", "Hello" not in json.dumps(lg))

n_before = len(ch.sent)
r2 = AP.create(s, {"email": "nameless2@example.com", "role_id": bare_role["id"]}, me, now=tick())
check("invite: a person with no name and a role with no description still gets the email (greeting there, no empty paragraph)",
      r2.ok and r2.data["invite_email"]["status"] == "sent" and "Hello there," in ch.sent[-1]["content"]["text"] and "None" not in ch.sent[-1]["content"]["text"])

# ================================================================ when nothing is sent
n = len(ch.sent)
r = AP.create(s, {"email": "seeded@example.com", "role_id": bare_role["id"]}, "system:cms_seed", now=tick())
check("no email: a person made by a system actor (a seed script) gets none", r.ok and "invite_email" not in r.data and len(ch.sent) == n)
r = AP.create(s, {"email": "testdoor@example.com", "role_id": bare_role["id"]}, "system:crud_test", now=tick())
check("no email: the test door's actor sends nothing", r.ok and "invite_email" not in r.data and len(ch.sent) == n)
r = AP.create(s, {"email": "off@example.com", "role_id": bare_role["id"], "is_active": False}, me, now=tick())
check("no email: a person invited already switched off gets none", r.ok and "invite_email" not in r.data and len(ch.sent) == n)
r = AP.create(s, {"email": "new.dana@example.com", "role_id": bare_role["id"]}, me, now=tick())
check("no email: a refused invitation (duplicate address) sends nothing and says so", not r.ok and len(ch.sent) == n and any(p["issue"] == "duplicate" for p in r.problems))
r = AP.create(s, {"email": "not-an-email", "role_id": bare_role["id"]}, me, now=tick())
check("no email: an invalid invitation sends nothing", not r.ok and len(ch.sent) == n)
with s.transaction() as tx:
    r = AP.create(s, {"email": "intx@example.com", "role_id": bare_role["id"]}, me, tx=tx, now=tick())
check("no email: inside a caller's transaction nothing is sent (the change is not saved yet)", r.ok and "invite_email" not in r.data and len(ch.sent) == n)
check("no email: the refused and system cases left no log entry", len(invites()) == 2, str(len(invites())))

# ================================================================ a problem with the email never undoes the invitation
bad_ch = wire(FakeChannel(outcome="rejected", error_code="provider_refused"))
r = AP.create(s, {"email": "refused@example.com", "role_id": bare_role["id"]}, me, now=tick())
check("provider refuses: the person is still saved and the answer says failed", r.ok and r.data["invite_email"]["status"] == "failed" and r.data["invite_email"]["reason"] == "adapter_error")
check("provider refuses: ...and the person is in the store", AP.get(s, r.data["id"]).ok)
check("provider refuses: ...and the failure is in the log", [x for x in invites() if x.get("to") == "refused@example.com"][0]["status"] == "failed")
silent = wire(FakeChannel(outcome="no_answer"))
r = AP.create(s, {"email": "silent@example.com", "role_id": bare_role["id"]}, me, now=tick())
check("provider gives no answer: saved; the answer says unknown", r.ok and r.data["invite_email"]["status"] == "unknown")
off = wire(FakeChannel(), mode="off")
r = AP.create(s, {"email": "modeoff@example.com", "role_id": bare_role["id"]}, me, now=tick())
check("CMS off: saved; skipped, nothing sent", r.ok and r.data["invite_email"] == {"status": "skipped", "reason": "cms_off"} and off.sent == [])
lo = wire(FakeChannel(), mode="log_only")
r = AP.create(s, {"email": "logonly@example.com", "role_id": bare_role["id"]}, me, now=tick())
check("CMS log only: saved; skipped, logged, nothing sent", r.ok and r.data["invite_email"] == {"status": "skipped", "reason": "log_only"} and lo.sent == [])
empty = MemoryDocStore("")
assert CS.create(empty, {}, A, now=tick()).ok
nt = wire(FakeChannel(), store=empty)
r = AP.create(s, {"email": "notemplate@example.com", "role_id": bare_role["id"]}, me, now=tick())
check("no wording seeded yet: saved; not sent with the reason no_template, nothing sent", r.ok and r.data["invite_email"] == {"status": "not_sent", "reason": "no_template"} and nt.sent == [])
comms.configure(None)
r = AP.create(s, {"email": "unconfigured@example.com", "role_id": bare_role["id"]}, me, now=tick())
check("CMS not configured (tests, local runs): saved; skipped", r.ok and r.data["invite_email"] == {"status": "skipped", "reason": "cms_off"})
ch = wire()
_real_notify = comms.notify
def boom(**kw): raise RuntimeError("provider exploded")
comms.notify = boom
r = AP.create(s, {"email": "exploded@example.com", "role_id": bare_role["id"]}, me, now=tick())
comms.notify = _real_notify
check("a crash inside the CMS: the invitation is still saved, the answer says not sent", r.ok and r.data["invite_email"] == {"status": "not_sent", "reason": "internal_error"} and AP.get(s, r.data["id"]).ok)

# ================================================================ Resend invite email
ch = wire()
dana = AP.list(s, {"email": "new.dana@example.com"}).data["records"][0]
before = len(invites())
r = AP.send_invite(s, dana["id"], me, now=tick())
check("resend: sends the email again and says so", r.ok and r.data["status"] == "sent" and r.data["id"] == dana["id"] and [m["to"] for m in ch.sent] == ["new.dana@example.com"], str(r.data if r.ok else r.problems))
check("resend: the same wording", "Hello Dana," in ch.sent[0]["content"]["text"] and "new.dana@example.com" in ch.sent[0]["content"]["text"])
lg = [x for x in invites() if x.get("to") == "new.dana@example.com"]
check("resend: logged as a hand send next to the automatic one", len(invites()) == before + 1 and sorted(x["trigger"] for x in lg) == ["automatic", "manual"], str([x["trigger"] for x in lg]))
r = AP.send_invite(s, dana["id"], me, now=tick())
check("resend: pressing it again sends again (a hand send ignores duplicate protection)", r.ok and r.data["status"] == "sent" and len(ch.sent) == 2)
call, _ = IC.call_for(s, dana, me, manual=False)
first = comms.notify(**call)
second = comms.notify(**call)
check("automatic sends are once per person: after the first automatic email, a second automatic try is a duplicate and sends nothing",
      first.reason == "duplicate" and second.reason == "duplicate" and second.status == "skipped" and len(ch.sent) == 2, f"{first} {second} {len(ch.sent)}")
r = AP.send_invite(s, dana["id"], "system:cms_seed", now=tick())
check("resend: a system actor may call the function (the door decides who may), and it sends", r.ok)
check("resend: an actor that is not a valid actor is refused", not AP.send_invite(s, dana["id"], "nobody", now=tick()).ok)
check("resend: a bad id is refused as invalid", AP.send_invite(s, "not-an-id", me).problems == [{"field": "id", "issue": "invalid_format"}])
check("resend: an unknown person is not_found", AP.send_invite(s, "00000000-0000-4000-8000-000000000042", me).code == "not_found")
sw = AP.update(s, dana["id"], {"is_active": False}, me, now=tick()); assert sw.ok, sw.problems
n = len(ch.sent)
r = AP.send_invite(s, dana["id"], me, now=tick())
check("resend: a switched-off person is refused (switched_off) and nothing is sent", not r.ok and r.problems == [{"field": "is_active", "issue": "switched_off"}] and len(ch.sent) == n)
assert AP.update(s, dana["id"], {"is_active": True}, me, now=tick()).ok
gone = AP.create(s, {"email": "gone@example.com", "role_id": bare_role["id"]}, me, now=tick()).data
assert AP.soft_delete(s, gone["id"], me, now=tick()).ok
check("resend: a deleted person is not_found", AP.send_invite(s, gone["id"], me).code == "not_found")
roleless = {"id": "b0000000-0000-4000-8000-000000000001", "email": "roleless@example.com", "role_id": "00000000-0000-4000-8000-000000000009", "is_active": True, "schema_version": 1, "created_at": "2026-10-01T00:00:00Z", "updated_at": "2026-10-01T00:00:00Z"}
s.create("access_persons", roleless["id"], roleless)
r = AP.send_invite(s, roleless["id"], me, now=tick())
check("resend: a person whose role is gone is not sent to (not_sent role_not_found)", r.ok and r.data["status"] == "not_sent" and r.data["reason"] == "role_not_found")
comms.configure(None)
check("resend: with the CMS not configured it says not enabled", AP.send_invite(s, dana["id"], me).problems == [{"field": "email", "issue": "not_enabled"}])
ch = wire()

# ================================================================ through the Console door
def door(token, body, key=False):
    auth = f"Bearer {KEY}" if key else f"Bearer {tok(token)}"
    return handle_admin("POST", auth, json.dumps(body).encode(), KEY, f"v{token}", s, make_failure_limiter(), tick(), verifier=V)
def create_via(token, email, role, key=False, **kw):
    return door(token, {"collection": "access_persons", "op": "create", "args": {"data": {"email": email, "role_id": role["id"], **kw}}}, key=key)
def last_text(): return ch.sent[-1]["content"]["text"]
check("door: send_invite is a Console op and a known op", "send_invite" in OPS and "send_invite" in ADMIN_OPS and OPS["send_invite"] == ({"id"}, set()))
n = len(ch.sent)
r = create_via(1, "door1@example.com", mgr_role, display_name="Door One")
check("door: a super admin's invitation answers with invite_email sent and one email goes", r.status == 200 and r.body["data"]["invite_email"]["status"] == "sent" and len(ch.sent) == n + 1, str(r.body))
check("door: ...naming the super admin as the inviter", "Todd Beetcher has invited you" in last_text())
r = create_via(0, "door2@example.com", mgr_role, key=True)
check("door: an invitation made with the admin key says The LAUNCH team", r.status == 200 and "The LAUNCH team has invited you" in last_text() and r.body["data"]["invite_email"]["status"] == "sent")
r = create_via(2, "door3@example.com", mgr_role, grants=[reg([BOULDER], ["manage_requests"])])
check("door: a lead with Invite people invites inside their region and the email goes out, naming them", r.status == 200 and r.body["data"]["invite_email"]["status"] == "sent" and "Lee Lead has invited you" in last_text(), str(r.body))
door3 = AP.list(s, {"email": "door3@example.com"}).data["records"][0]
n = len(ch.sent)
r = door(2, {"collection": "access_persons", "op": "send_invite", "args": {"id": door3["id"]}})
check("door: ...and may resend to the person they invited", r.status == 200 and r.body["data"]["status"] == "sent" and len(ch.sent) == n + 1, str(r.body))
n = len(ch.sent)
r = create_via(2, "door4@example.com", mgr_role, grants=[reg([MADISON], ["manage_requests"], "WI")])
check("door: a lead inviting outside their region is refused and nothing is sent", r.status == 403 and len(ch.sent) == n)
r = door(2, {"collection": "access_persons", "op": "send_invite", "args": {"id": outsider["id"]}})
check("door: a lead cannot resend to someone outside their territory", r.status == 403 and len(ch.sent) == n)
r = door(2, {"collection": "access_persons", "op": "send_invite", "args": {"id": todd["id"]}})
check("door: a lead cannot resend to a super admin", r.status == 403 and len(ch.sent) == n)
r = door(2, {"collection": "access_persons", "op": "send_invite", "args": {"id": lead["id"]}})
check("door: a lead cannot resend to themselves", r.status == 403 and len(ch.sent) == n)
r = door(4, {"collection": "access_persons", "op": "send_invite", "args": {"id": door3["id"]}})
check("door: a person without Invite people or Access cannot resend", r.status == 403 and len(ch.sent) == n)
r = create_via(4, "door5@example.com", mgr_role)
check("door: ...nor invite", r.status == 403 and len(ch.sent) == n)
r = door(5, {"collection": "access_persons", "op": "send_invite", "args": {"id": door3["id"]}})
check("door: a viewer cannot resend", r.status == 403 and len(ch.sent) == n)
r = door(1, {"collection": "venues", "op": "send_invite", "args": {"id": door3["id"]}})
check("door: send_invite belongs to access_persons only", r.status == 400 and len(ch.sent) == n)
r = door(1, {"collection": "access_persons", "op": "send_invite", "args": {"id": door3["id"], "extra": 1}})
check("door: an unexpected argument is refused", r.status == 400 and len(ch.sent) == n)
r = door(1, {"collection": "access_persons", "op": "send_invite", "args": {}})
check("door: a missing id is refused", r.status == 400)
r = door(1, {"collection": "access_persons", "op": "send_invite", "args": {"id": "00000000-0000-4000-8000-000000000042"}})
check("door: an unknown person is 404", r.status == 404)
r = handle_crud_test("POST", f"Bearer {KEY}", json.dumps({"collection": "access_persons", "op": "create", "args": {"data": {"email": "viatest@example.com", "role_id": bare_role["id"]}}}).encode(),
                     KEY, "vt", s, make_failure_limiter(), tick())
check("test door: creating an access person there sends no email", r.status == 200 and "invite_email" not in r.body["data"] and len(ch.sent) == n)
r = door(1, {"collection": "access_persons", "op": "update", "args": {"id": door3["id"], "changes": {"display_name": "Renamed"}}})
check("door: an ordinary edit of a person sends no email", r.status == 200 and len(ch.sent) == n)
r = door(1, {"collection": "access_persons", "op": "list", "args": {}})
check("door: the person list is unchanged (no invite_email stored on a person)", r.status == 200 and all("invite_email" not in p for p in r.body["data"]["records"]))
check("door: the stored person has no invite_email either", "invite_email" not in AP.get(s, door3["id"]).data)

print(f"\n{total - len(fails)}/{total} checks passed")
if fails:
    print("FAILED:", *fails, sep="\n  ")
    sys.exit(1)
