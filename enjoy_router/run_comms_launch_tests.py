#!/usr/bin/env python3
"""Tests for LAUNCH's side of the CMS: launch_comms/ (directory, stores, fact builders) and the three handlers (message_templates,
communication_logs, comms_settings), through the real core and the real renderer. Nothing is sent: a fake channel stands in, and
nothing is wired into main.py yet. Run from enjoy_router/:  python3 run_comms_launch_tests.py  (-v lists every check)."""
import json, pathlib, sys
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import comms  # noqa: E402
from comms import contract_kit  # noqa: E402
from comms.channels.fake import FakeChannel  # noqa: E402
from crud import attendances_service as AT  # noqa: E402
from crud import communication_logs_crud as LG  # noqa: E402
from crud import comms_settings_crud as CS  # noqa: E402
from crud import individuals_service as IS  # noqa: E402
from crud import message_templates_crud as MT  # noqa: E402
from crud import scheduled_classes_crud as CL  # noqa: E402
from crud import venues_service as VS  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud_endpoint import handle_admin, make_failure_limiter  # noqa: E402
from launch_comms import kinds as K  # noqa: E402
from launch_comms import placement_context as PC, request_context as RC  # noqa: E402
from launch_comms.directory import IndividualDirectory, preferred_channel  # noqa: E402
from launch_comms.stores import LogStore, SettingsStore, TemplateStore  # noqa: E402
from test_helpers import give_address  # noqa: E402

SCHEMAS = HERE.parent / "schemas"
GOLD = json.loads((SCHEMAS / "message_kinds" / "golden_masters.json").read_text())
SEED = json.loads((SCHEMAS / "examples" / "message_template.seed.json").read_text())["templates"]
KEY = "k" * 16 + "Z" * 16 + "-test-key-not-real"
A, B = "user:admin", "user:helper"
NOW = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
fails, total, clock = [], 0, [0]
def tick():
    clock[0] += 5
    return NOW - timedelta(days=1) + timedelta(seconds=clock[0])
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    if not ok or "-v" in sys.argv: print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")
def issues(r): return sorted((p["field"], p["issue"]) for p in (r.problems or []))

s = MemoryDocStore("t_")

# ------------------------------------------------------------------ template handler: seed, versions, drafts, publish (R-11, R-21, R-12)
for t in SEED:
    r = MT.create(s, {k: t[k] for k in ("kind", "channel", "audience", "name", "subject", "blocks", "is_active")}, A, now=tick())
    check(f"templates: create the first {t['kind']} draft", r.ok and r.data["status"] == "draft" and r.data["version"] == 1 and "previous_id" not in r.data, r.problems if not r.ok else "")
    check(f"templates: a draft is never found for sending ({t['kind']})", TemplateStore(s).find_published(t["kind"], "email", t["audience"]) is None)
    r2 = MT.publish(s, r.data["id"], A, now=tick())
    check(f"templates: publish the first {t['kind']}", r2.ok and r2.data["version"] == 1, r2.problems if not r2.ok else "")
    check(f"templates: the published one is now found ({t['kind']})", (TemplateStore(s).find_published(t["kind"], "email", t["audience"]) or {}).get("version") == 1)
first = [x for x in s.query("message_templates", [], limit=10) if x["kind"] == "placement_confirmation"][0]
dup = MT.create(s, {k: first[k] for k in ("kind", "channel", "audience", "name", "subject", "blocks", "is_active")}, A, now=tick())
check("templates: a second first-draft for the same key is refused", not dup.ok and ("kind", "duplicate") in issues(dup))
r = MT.update(s, first["id"], {"subject": "x"}, A, now=tick())
check("templates: a published record's wording cannot be edited", not r.ok and ("subject", "not_allowed") in issues(r))
r = MT.update(s, first["id"], {"is_active": False}, A, now=tick())
check("templates: the on/off switch works on a published record and makes no new version", r.ok and MT.get(s, first["id"]).data["version"] == 1 and MT.get(s, first["id"]).data["is_active"] is False)
check("templates: R-11 an inactive template is still the standing record (the CMS refuses it)", (TemplateStore(s).find_published("placement_confirmation", "email", "student") or {}).get("is_active") is False)
MT.update(s, first["id"], {"is_active": True}, A, now=tick())
r = MT.draft_from(s, first["id"], A, now=tick())
check("templates: draft_from copies the content, version 2, previous_id = standing", r.ok and r.data["status"] == "draft" and r.data["version"] == 2 and r.data["previous_id"] == first["id"] and r.data["blocks"] == first["blocks"], r.problems if not r.ok else "")
d2 = r.data
check("templates: only one draft per key", MT.draft_from(s, first["id"], A, now=tick()).code == "conflict")
check("templates: a draft never sends while it exists", (TemplateStore(s).find_published("placement_confirmation", "email", "student") or {}).get("version") == 1)
bad = MT.update(s, d2["id"], {"subject": "Hi {not_a_fact}"}, A, now=tick())
check("templates: R-12 an unknown placeholder is refused", not bad.ok and ("blocks", "unknown_fact") in issues(bad), issues(bad))
bad = MT.update(s, d2["id"], {"subject": "Hi {map_url}"}, A, now=tick())
check("templates: R-12 an optional fact in the subject (unguarded) is refused", not bad.ok and ("blocks", "optional_fact_unguarded") in issues(bad), issues(bad))
bad = MT.update(s, d2["id"], {"subject": "Hi {"}, A, now=tick())
check("templates: a stray brace is refused", not bad.ok and ("blocks", "invalid_format") in issues(bad), issues(bad))
bad = MT.update(s, d2["id"], {"kind": "request_received"}, A, now=tick())
check("templates: kind, channel and audience are immutable", not bad.ok and ("kind", "immutable") in issues(bad))
good = MT.update(s, d2["id"], {"subject": "Launch — you are on: {when_short}"}, A, now=tick())
check("templates: a draft is edited in place", good.ok and MT.get(s, d2["id"]).data["subject"].startswith("Launch — you are on"), good.problems if not good.ok else "")
pub = MT.publish(s, d2["id"], A, now=tick())
check("templates: publish makes version 2 the standing record", pub.ok and pub.data["version"] == 2 and TemplateStore(s).find_published("placement_confirmation", "email", "student")["id"] == d2["id"], pub.problems if not pub.ok else "")
check("templates: version 1 is kept as history", MT.get(s, first["id"]).ok and MT.get(s, first["id"]).data["status"] == "published")
check("templates: publishing a published record is refused", not MT.publish(s, d2["id"], A, now=tick()).ok)
check("templates: a published record cannot be deleted", not MT.soft_delete(s, d2["id"], A, now=tick()).ok)
# revert = draft from the old record, then publish
rv = MT.draft_from(s, first["id"], A, now=tick())
check("templates: revert starts a draft from an older record whose previous_id is the standing one", rv.ok and rv.data["previous_id"] == d2["id"] and rv.data["version"] == 3 and rv.data["subject"] == first["subject"])
# stale publish: two drafts cannot exist, so simulate by making the standing record change under a draft
rv_pub = MT.publish(s, rv.data["id"], A, now=tick())
check("templates: revert publishes as version 3", rv_pub.ok and rv_pub.data["version"] == 3)
r = MT.draft_from(s, d2["id"], A, now=tick())
st = r.data
s.update("message_templates", st["id"], {"previous_id": first["id"]}, (), expected_updated_at=st["updated_at"])   # make it look stale
check("templates: publishing a draft whose standing record changed is refused (conflict)", MT.publish(s, st["id"], A, now=tick()).code == "conflict")
check("templates: a draft can be deleted", MT.soft_delete(s, st["id"], A, now=tick()).ok)
check("templates: list filters by kind", MT.list(s, {"kind": "request_received"}).data["count"] == 1)
check("templates: list takes one filter only", not MT.list(s, {"kind": "request_received", "status": "draft"}).ok)
check("templates: the registry check refuses an unknown kind", not MT.create(s, {"kind": "nope", "channel": "email", "audience": "x", "name": "n", "subject": "s",
      "blocks": [{"type": "paragraph", "text": "t"}], "is_active": True}, A, now=tick()).ok)

# ------------------------------------------------------------------ settings handler
check("settings: none exists before the first create", CS.list(s).data["count"] == 0 and SettingsStore(s).read().sender_name == "Launch")
r = CS.create(s, {}, A, now=tick())
check("settings: create makes the one record with the Launch defaults", r.ok and r.data["settings_key"] == "default" and r.data["sender_name"] == "Launch" and r.data["is_email_on"] is True and r.data["is_text_on"] is False, r.problems if not r.ok else "")
sid = r.data["id"]
check("settings: a second record is refused", not CS.create(s, {}, A, now=tick()).ok)
check("settings: is_text_on true is refused until a text channel exists", ("is_text_on", "invalid_value") in issues(CS.update(s, sid, {"is_text_on": True}, A, now=tick())))
check("settings: settings_key is immutable", ("settings_key", "immutable") in issues(CS.update(s, sid, {"settings_key": "other"}, A, now=tick())))
r = CS.update(s, sid, {"reply_to": "  Todd@Example.com ", "test_redirect_address": "Test@Example.com", "footer": "Be well."}, A, now=tick())
got = SettingsStore(s).read()
check("settings: addresses are trimmed and lowercased", r.ok and got.reply_to == "todd@example.com" and got.test_redirect_address == "test@example.com" and got.footer == "Be well.", r.problems if not r.ok else got)
check("settings: a stale update is refused", CS.update(s, sid, {"sender_name": "X"}, A, expected_updated_at="2020-01-01T00:00:00Z", now=tick()).code == "conflict")
check("settings: delete is refused", not CS.soft_delete(s, sid, A, now=tick()).ok)
CS.update(s, sid, {"footer": None, "reply_to": None, "test_redirect_address": None}, A, now=tick())
check("settings: optional fields can be removed", SettingsStore(s).read().footer is None)

# ------------------------------------------------------------------ people and a class to talk about
def person(g, f="Test", **kw):
    r = IS.create(s, {"given_name": g, "family_name": f, **kw}, A, now=tick()); assert r.ok, r.problems; return r.data
glad = person("Gladys", "Hart", email="gladys@example.com", phone="+13035550100")
todd = person("Todd", "Beetcher", email="todd@example.com"); give_address(s, todd["id"])
lee = person("Lee", "Park", email="lee@example.com")
susan = person("Susan", "Adams", email="susan@example.com"); give_address(s, susan["id"])
bobby = person("Bobby", "Hodgkins", email="bobby@example.com"); give_address(s, bobby["id"])
v = VS.create_with_place(s, {"name": "Ozo's Coffee, East Pearl", "slug": "ozo", "status": "inactive", "is_public_venue": True}, A,
                         address={"street_number": "1500", "street": "Pearl St", "locality": "Boulder", "region": "CO", "postal_code": "80302", "country": "US"})
assert v.ok, v.problems
assert VS.update(s, v.data["id"], {"status": "active"}, A).ok
v2 = VS.create_with_place(s, {"name": "Boulder Public Library", "slug": "bpl", "status": "inactive", "is_public_venue": True}, A,
                          address={"street_number": "1001", "street": "Arapahoe Ave", "locality": "Boulder", "region": "CO", "postal_code": "80302", "country": "US"})
assert v2.ok, v2.problems
assert VS.update(s, v2.data["id"], {"status": "active"}, A).ok
NOTES = GOLD["cases"]["placement_full"]["inputs"]["notes"]
def klass(slug, **kw):
    base = {"title": slug, "slug": slug, "class_type": "private", "program_slug": "launch", "status": "scheduled", "is_public": False, "capacity_minimum": 1,
            "capacity_target": 5, "capacity_max": 20, "venue_id": v.data["id"], "is_venue_confirmed": False}
    r = CL.create(s, {**base, **kw}, A, now=tick()); assert r.ok, r.problems; return r.data
full = klass("full", title="Gladys's AI Happy Hour", starts_at="2026-10-17T23:00:00Z", duration_minutes=90, time_zone="America/Denver",
             venue_room_label="Back room", venue_notes=NOTES)
std = klass("std", title="Intro to AI", starts_at="2026-11-14T16:00:00Z", duration_minutes=120, time_zone="America/Denver", venue_id=v2.data["id"])
def assign(cls, who, role="student", **kw):
    r = AT.assign(s, {"scheduled_class_id": cls["id"], "role": role, "individual_id": who["id"], **kw}, A, now=tick()); assert r.ok, r.problems; return r.data
assign(full, todd, "primary_instructor", order=1); assign(full, susan, "instructor", order=2); assign(full, bobby, "instructor", order=3)
att_full = assign(full, glad)
assign(std, todd, "primary_instructor", order=1)
att_std = assign(std, lee)
def set_conf(att, number):
    cur = s.get("attendances", att["id"]); s.update("attendances", att["id"], {"confirmation_number": number}, (), expected_updated_at=cur["updated_at"])
set_conf(att_full, "ICDT-ABC123"); set_conf(att_std, "ICDT-QQ77ZZ")

# ------------------------------------------------------------------ fact builders against the golden facts (R-5)
def facts_for(att):
    f, ind, reason = PC.build(s, s.get("attendances", att["id"]))
    return f, ind, reason
for label, att, case in (("full", att_full, "placement_full"), ("standard time", att_std, "placement_standard_time")):
    f, ind, reason = facts_for(att)
    want = dict(GOLD["cases"][case]["facts"]); want["uid"] = att["id"]
    check(f"placement facts ({label}) equal the golden facts", f == want, f"{set(f or {}) ^ set(want)} {[k for k in want if (f or {}).get(k) != want[k]]}")
    check(f"placement facts ({label}) satisfy the kind's fact schema", not K.registry().validate("placement_confirmation", f), str(K.registry().validate("placement_confirmation", f)))
    check(f"placement facts ({label}) name the placed person", ind == (glad["id"] if att is att_full else lee["id"]))
tagged = lambda r: (r[2] if r[0] is None else None)
check("placement: a waitlisted student is not eligible (not_placed)", tagged(PC.build(s, {**s.get("attendances", att_full["id"]), "status": "waitlisted"})) == "not_placed")
check("placement: an instructor is not eligible (not_a_student)", tagged(PC.build(s, s.get("attendances", [d for d in s.query("attendances", [], limit=50) if d["role"] == "primary_instructor"][0]["id"]))) == "not_a_student")
idea = klass("idea", status="identified")
att_idea = assign(idea, glad)
check("placement: a class with no date is not eligible (class_not_scheduled)", tagged(PC.build(s, s.get("attendances", att_idea["id"]))) == "class_not_scheduled")
check("placement: unknown attendance is not_found", tagged(PC.build(s, None)) == "not_found")
call, why = PC.call_for(s, att_full["id"], A, manual=True)
check("placement call_for: the R-2 arguments (kind, recipient, trigger, refs, audience)", call and call["kind"] == "placement_confirmation" and call["recipient"] == {"type": "individual", "individual_id": glad["id"]}
      and call["trigger"] == "manual" and call["refs"] == {"attendance_id": att_full["id"], "scheduled_class_id": full["id"]} and call["audience"] == "student", str(call))
check("placement call_for: no call when not eligible", PC.call_for(s, att_idea["id"], A) == (None, "class_not_scheduled"))

RD = {"id": "6c5e1f4b-0d7a-4b82-8e9d-4f5a6b7c8d9e", "first_name": "Maria", "last_name": "O'Brien & Sons", "email": "maria@example.com",
      "confirmation_number": "ICDT-ABC123", "registration_type": "private", "completion_token": "tok123&x=1"}
check("receipt facts: private request with a token carries the completion link", RC.facts(RD) == {"name": "Maria O'Brien & Sons", "confirmation_number": "ICDT-ABC123",
      "completion_link": "https://beetcher.com/enjoy/register/private/?r=tok123&x=1"})
check("receipt facts: no link without a token or for a public request", "completion_link" not in RC.facts({**RD, "completion_token": None}) and "completion_link" not in RC.facts({**RD, "registration_type": "public"}))
check("receipt facts satisfy the kind's fact schema", not K.registry().validate("request_received", RC.facts(RD)))
rc = RC.call_for(RD)
check("receipt call: adhoc recipient from the request, request_id ref, requester audience", rc["recipient"] == {"type": "adhoc", "name": "Maria O'Brien & Sons", "email": "maria@example.com"} and rc["refs"] == {"request_id": RD["id"]} and rc["audience"] == "requester")

# ------------------------------------------------------------------ the whole thing: real stores, real core, fake channel (R-6, R-11, R-13, R-16)
def build(mode="live", channel=None):
    ch = channel or FakeChannel()
    return comms.Comms(kinds=K.registry(), directory=IndividualDirectory(s), templates=TemplateStore(s), log=LogStore(s), settings=SettingsStore(s),
                       channels=[ch], mode=mode, clock=lambda: NOW), ch
c, ch = build()
# the standing placement template is version 3, the revert to the seed wording, so the golden bytes apply
call, _ = PC.call_for(s, att_full["id"], A)
res = c.notify(**call)
sent = ch.sent[0]["content"] if ch.sent else {}
g = GOLD["cases"]["placement_full"]
check("full path: placement confirmation is sent to the individual's email", res.status == "sent" and ch.sent[0]["to"] == "gladys@example.com", str(res))
check("full path: subject, text and HTML are the pre-refactor bytes", (sent.get("subject"), sent.get("text"), sent.get("html")) == (g["expect"]["subject"], g["expect"]["text"], g["expect"]["html"]))
check("full path: the calendar file is the pre-refactor bytes (uid aside)", sent["attachments"][0][2].decode("utf-8") == g["expect"]["ics"].replace(g["facts"]["uid"], att_full["id"]))
log = LG.list(s, {"attendance_id": att_full["id"]}).data["records"]
e = log[0] if log else {}
check("full path: one log entry, sent/ok, with the template version, refs and no body", len(log) == 1 and (e["status"], e["reason"], e["channel"], e["kind"]) == ("sent", "ok", "email", "placement_confirmation")
      and e["template_version"] == 3 and e["scheduled_class_id"] == full["id"] and e["individual_id"] == glad["id"] and "text" not in e and "html" not in e, str(e))
check("full path: the log entry is stamped by the server (created_by is the caller)", e.get("created_by") == A and e.get("source") == "dashboard")
call_again, _ = PC.call_for(s, att_full["id"], A)
res2 = c.notify(**call_again)
check("R-9 a repeated automatic send is skipped as a duplicate", res2.status == "skipped" and res2.reason == "duplicate" and len(ch.sent) == 1, str(res2))
res3 = c.notify(**{**call_again, "trigger": "manual"})
check("R-9 a manual send bypasses duplicate protection", res3.status == "sent" and len(ch.sent) == 2, str(res3))
check("the log holds all three attempts: sent, duplicate, sent", sorted(x["reason"] for x in LG.list(s, {"attendance_id": att_full["id"]}).data["records"]) == ["duplicate", "ok", "ok"])
# receipt
res = c.notify(**RC.call_for(RD))
check("full path: the receipt is sent to the adhoc address", res.status == "sent" and ch.sent[-1]["to"] == "maria@example.com", str(res))
gr = GOLD["cases"]["receipt_with_link"]
check("full path: receipt bytes match the golden receipt", (ch.sent[-1]["content"]["subject"], ch.sent[-1]["content"]["text"], ch.sent[-1]["content"]["html"]) == (gr["expect"]["subject"], gr["expect"]["text"], gr["expect"]["html"]))
check("full path: the receipt log entry carries the request id", LG.list(s, {"request_id": RD["id"]}).data["count"] == 1)
# settings change the wording of the sender, not the code (R-13 test redirect)
CS.update(s, sid, {"test_redirect_address": "redirect@example.com", "footer": "Be well."}, A, now=tick())
res = c.notify(**{**call_again, "trigger": "manual"})
check("R-13 the test redirect from settings sends to the redirect and marks the entry", res.status == "sent" and ch.sent[-1]["to"] == "redirect@example.com"
      and LG.get(s, res.log_id).data.get("is_redirected") is True)
check("settings footer is added to the text by the CMS", ch.sent[-1]["content"]["text"].rstrip().endswith("Be well."), ch.sent[-1]["content"]["text"][-40:])
CS.update(s, sid, {"test_redirect_address": None, "footer": None}, A, now=tick())
CS.update(s, sid, {"is_email_on": False}, A, now=tick())
res = c.notify(**{**call_again, "trigger": "manual"})
check("settings: email off makes a not_sent / channel_unavailable entry", (res.status, res.reason) == ("not_sent", "channel_unavailable"), str(res))
CS.update(s, sid, {"is_email_on": True}, A, now=tick())
# log_only and off through real stores
c2, ch2 = build("log_only")
r = c2.notify(**{**call_again, "trigger": "manual"})
check("R-13 log_only: nothing sent, entry skipped / log_only", (r.status, r.reason) == ("skipped", "log_only") and not ch2.sent)
c3, ch3 = build("off")
r = c3.notify(**{**call_again, "trigger": "manual"})
check("R-13 off: nothing sent, entry skipped / cms_off", (r.status, r.reason) == ("skipped", "cms_off") and not ch3.sent)
# an inactive template and a missing template
std_call, _ = PC.call_for(s, att_std["id"], A)
stand = TemplateStore(s).find_published("placement_confirmation", "email", "student")
MT.update(s, stand["id"], {"is_active": False}, A, now=tick())
r = c.notify(**std_call)
check("R-11 an inactive standing template: not_sent / no_template", (r.status, r.reason) == ("not_sent", "no_template"), str(r))
MT.update(s, stand["id"], {"is_active": True}, A, now=tick())
# the person who prefers a text: no email, hand-contact queue (R-24, R-8)
txt = person("Tex", "Texter", email="tex@example.com", phone="+13035550111", prefers_email=False)
att_tex = assign(std, txt)
tex_call, _ = PC.call_for(s, att_tex["id"], A)
r = c.notify(**tex_call)
check("R-8/R-24 a person who prefers text gets no email: not_sent / channel_unavailable", (r.status, r.reason) == ("not_sent", "channel_unavailable") and not any(x["to"] == "tex@example.com" for x in ch.sent), str(r))
check("the hand-contact entry appears in the log filtered by reason", any(x["individual_id"] == txt["id"] for x in LG.list(s, {"reason": "channel_unavailable"}).data["records"]))
mh = LG.mark_handled(s, r.log_id, B, "Called Tex on the phone", now=tick())
check("mark_handled sets handled_at/by/note once", mh.ok and LG.get(s, r.log_id).data["handled_by"] == B and LG.get(s, r.log_id).data["handled_note"] == "Called Tex on the phone", mh.problems if not mh.ok else "")
check("mark_handled a second time is a conflict", LG.mark_handled(s, r.log_id, B, "again", now=tick()).code == "conflict")
# notes: add only, any status, facts never change
before = dict(LG.get(s, r.log_id).data)
check("mark_handled with a comment also leaves it as a note", [n["text"] for n in before.get("notes", [])] == ["Handled: Called Tex on the phone"] and before["notes"][0]["by"] == B)
sent_first = LG.list(s, {"status": "sent"}).data["records"][0]
n1 = LG.add_note(s, sent_first["id"], B, "  Landed in Promotions; not a bug.  ", now=tick())
n2 = LG.add_note(s, sent_first["id"], "user:other", "Fixed by dropping our Message-ID.", now=tick())
got = LG.get(s, sent_first["id"]).data
check("add_note works on a sent entry, oldest first, trimmed, with author and time", n1.ok and n2.ok and [n["text"] for n in got["notes"]] == ["Landed in Promotions; not a bug.", "Fixed by dropping our Message-ID."] and [n["by"] for n in got["notes"]] == [B, "user:other"] and all(n["at"] for n in got["notes"]))
check("add_note never changes the facts of the entry", all(got.get(k) == sent_first.get(k) for k in ("kind", "to", "subject", "status", "reason", "channel", "trigger", "created_at", "individual_id", "attendance_id")))
check("add_note: empty text is refused", ("text", "required") in issues(LG.add_note(s, sent_first["id"], B, "   ", now=tick())))
check("add_note: 1001 characters is refused, 1000 is fine", ("text", "too_long") in issues(LG.add_note(s, sent_first["id"], B, "x" * 1001, now=tick())) and LG.add_note(s, sent_first["id"], B, "y" * 1000, now=tick()).ok)
check("add_note: unknown or malformed id", LG.add_note(s, "00000000-0000-4000-8000-000000000000", B, "hi", now=tick()).code == "not_found" and ("id", "invalid_format") in issues(LG.add_note(s, "nope", B, "hi", now=tick())))
check("add_note: a bad actor is refused", not LG.add_note(s, sent_first["id"], "", "hi", now=tick()).ok)
full = LG.get(s, sent_first["id"]).data
for i in range(LG.MAX_NOTES - len(full["notes"])):
    LG.add_note(s, sent_first["id"], B, "n%d" % i, now=tick())
check("add_note: the 51st note is refused", ("notes", "too_many") in issues(LG.add_note(s, sent_first["id"], B, "one more", now=tick())) and len(LG.get(s, sent_first["id"]).data["notes"]) == LG.MAX_NOTES)
check("update and soft_delete stay refused, so a note cannot be edited or removed", not LG.update(s).ok and not LG.soft_delete(s).ok)
sent_entry = LG.list(s, {"status": "sent"}).data["records"][0]
check("mark_handled on a sent entry is refused", ("status", "not_allowed") in issues(LG.mark_handled(s, sent_entry["id"], B, None, now=tick())))
# a person with no contact at all
nobody = person("Nobody")
att_nb = assign(std, nobody)
r = c.notify(**PC.call_for(s, att_nb["id"], A)[0])
check("no email and no phone: not_sent / no_contact", (r.status, r.reason) == ("not_sent", "no_contact"), str(r))

# ------------------------------------------------------------------ log handler rules (R-15 create/update/delete refused, filters)
ent = LG.list(s, {}).data["records"][0]
check("log: create, update and soft_delete are refused", all(not f().ok for f in (lambda: LG.create(s, {}, A), lambda: LG.update(s, ent["id"], {"status": "sent"}, A), lambda: LG.soft_delete(s, ent["id"], A))))
check("log: list takes one filter only", not LG.list(s, {"kind": "request_received", "status": "sent"}).ok)
check("log: list refuses an unknown filter", ("to", "not_supported") in issues(LG.list(s, {"to": "x@example.com"})))
check("log: newest first by default", [x["created_at"] for x in LG.list(s, {}).data["records"]] == sorted([x["created_at"] for x in LG.list(s, {}).data["records"]], reverse=True)
      and [x["created_at"] for x in LG.list(s, {}, order="created_at").data["records"]] == sorted(x["created_at"] for x in LG.list(s, {}).data["records"]))
check("log: record refuses a document that breaks the schema (our bug, says nothing about fields)", LG.record(s, {"kind": "k", "channel": "email", "status": "sent", "reason": "cms_off", "trigger": "automatic", "contract_version": 1}, A).code == "server_error")

# ------------------------------------------------------------------ R-24 directory
D = IndividualDirectory(s)
check("R-24 preferred_channel rule table", [preferred_channel("a@x.com", "+1", None), preferred_channel("a@x.com", "+1", False), preferred_channel("a@x.com", None, False),
      preferred_channel(None, "+1", True), preferred_channel(None, "+1", None), preferred_channel(None, None, True), preferred_channel("a@x.com", "+1", True)]
      == ["email", "text", "email", "text", "text", None, "email"])
check("R-24 an erased or unknown person resolves to None", D.lookup({"type": "individual", "individual_id": "00000000-0000-4000-8000-00000000dead"}) is None)
check("R-24 adhoc recipients keep their address", D.lookup({"type": "adhoc", "name": "Pat", "email": "pat@example.com"}).email == "pat@example.com")
check("R-24 the individual's backup phone is carried", IndividualDirectory(s).lookup({"type": "individual", "individual_id": glad["id"]}).preferred_channel == "email")
fl = contract_kit.directory_contract(lambda: IndividualDirectory(s), glad["id"]); check("R-18 IndividualDirectory passes the directory contract", not fl, str(fl))
fl = contract_kit.log_store_contract(lambda: LogStore(MemoryDocStore("c_"))); check("R-18 LogStore passes the log store contract", not fl, str(fl))
def add_tpl(store_obj, rec):
    base = {k: rec[k] for k in ("kind", "channel", "audience", "name", "subject", "blocks", "is_active") if k in rec}
    from crud.schema_kit import stamp_create
    doc = stamp_create(MT.TEMPLATES, {**base, "status": rec["status"], "version": rec["version"], **({"previous_id": rec["previous_id"]} if "previous_id" in rec else {})}, A, "dashboard")
    if rec["status"] == "published":
        doc.update({"published_at": doc["created_at"], "published_by": A})
    store_obj._s.create("message_templates", doc["id"], doc); return doc
class TS(TemplateStore):
    def __init__(self): self._s = MemoryDocStore("tc_"); super().__init__(self._s)
base_rec = {"kind": "placement_confirmation", "channel": "email", "audience": "student", "name": "n", "subject": "s", "blocks": [{"type": "paragraph", "text": "t"}], "is_active": True}
ts = TS(); fl = []
check("R-18 TemplateStore: empty store returns None", ts.find_published("placement_confirmation", "email", "student") is None)
old = add_tpl(ts, {**base_rec, "status": "published", "version": 1}); add_tpl(ts, {**base_rec, "status": "draft", "version": 2, "previous_id": old["id"]})
check("R-18 TemplateStore: a published one is found and a draft never is", ts.find_published("placement_confirmation", "email", "student")["version"] == 1)
add_tpl(ts, {**base_rec, "status": "published", "version": 2, "previous_id": old["id"]})
check("R-18 TemplateStore: the standing version is the one nobody supersedes", ts.find_published("placement_confirmation", "email", "student")["version"] == 2 and ts.find_published("placement_confirmation", "email", "other") is None)

# ------------------------------------------------------------------ R-16 the log is history: a merge and an erase never touch it (Todd, 2026-10-15)
dupe = person("Gladys", "Hart", email="gladys2@example.com")
att_d = assign(std, dupe)
cd, _ = PC.call_for(s, att_d["id"], A); c.notify(**cd)
snap_dupe = {x["id"]: dict(x) for x in LG.list(s, {"individual_id": dupe["id"]}).data["records"]}
m = IS.merge(s, glad["id"], dupe["id"], "same person", A, None, now=tick())
now_dupe = {x["id"]: dict(x) for x in LG.list(s, {"individual_id": dupe["id"]}).data["records"]}
check("R-16 merge leaves the duplicate's log entries exactly as they were (still pointing at the duplicate)", m is not None and m.ok and snap_dupe and now_dupe == snap_dupe,
      (m.problems if m is not None and not m.ok else ""))
ids_before = [x["id"] for x in LG.list(s, {"individual_id": txt["id"]}).data["records"]]
snap_tex = {i: dict(s.get("communication_logs", i)) for i in ids_before}
had_notes = any(d.get("notes") for d in snap_tex.values())
er = IS.erase(s, txt["id"], A, now=tick()) if hasattr(IS, "erase") else None
after_tex = {i: dict(s.get("communication_logs", i)) for i in ids_before}
check("R-16 erase leaves the person's log entries exactly as they were: nothing removed, nothing hidden, notes kept", er is not None and er.ok and ids_before and had_notes and after_tex == snap_tex and not any("deleted_at" in d for d in after_tex.values())
      and all(x["id"] in {y["id"] for y in LG.list(s, {"status": "not_sent"}).data["records"]} for x in snap_tex.values() if x["status"] == "not_sent"),
      (er.problems if er is not None and not er.ok else ""))

# ------------------------------------------------------------------ the endpoint (admin door) reaches the new collections and ops
lim = make_failure_limiter(); ts_ = tick()
def call_ep(coll, op, args): return handle_admin("POST", "Bearer " + KEY, json.dumps({"collection": coll, "op": op, "args": args}).encode(), KEY, "v", s, lim, ts_)
r = call_ep("message_templates", "list", {"filters": {"kind": "request_received"}})
check("endpoint: message_templates list", r.status == 200 and r.body["data"]["count"] >= 1, r.body)
r = call_ep("comms_settings", "list", {})
check("endpoint: comms_settings list", r.status == 200 and r.body["data"]["count"] == 1, r.body)
r = call_ep("communication_logs", "list", {"filters": {"status": "not_sent"}})
check("endpoint: communication_logs list", r.status == 200 and r.body["data"]["count"] >= 1, r.body)
r = call_ep("communication_logs", "create", {"data": {}})
check("endpoint: communication_logs create is refused", r.status == 400, r.body)
unh = [x for x in LG.list(s, {"status": "not_sent"}).data["records"] if "handled_at" not in x][0]
r = call_ep("communication_logs", "mark_handled", {"id": unh["id"], "note": "ok"})
check("endpoint: mark_handled works", r.status == 200 and r.body["data"]["handled_by"] == "user:admin", r.body)
d = call_ep("message_templates", "draft_from", {"id": TemplateStore(s).find_published("request_received", "email", "requester")["id"]})
check("endpoint: draft_from works", d.status == 200 and d.body["data"]["status"] == "draft", d.body)
p = call_ep("message_templates", "publish", {"id": d.body["data"]["id"]})
check("endpoint: publish works", p.status == 200 and p.body["data"]["version"] == 2, p.body)
r = call_ep("venues", "publish", {"id": d.body["data"]["id"]})
check("endpoint: only templates have publish", r.status == 400, r.body)
r = call_ep("venues", "mark_handled", {"id": unh["id"]})
check("endpoint: only the log has mark_handled", r.status == 400, r.body)
r = call_ep("communication_logs", "add_note", {"id": unh["id"], "text": "Checked the Console, phoned her."})
check("endpoint: add_note works and returns the notes", r.status == 200 and r.body["data"]["notes"][-1]["text"] == "Checked the Console, phoned her." and r.body["data"]["notes"][-1]["by"] == "user:admin", r.body)
r = call_ep("communication_logs", "add_note", {"id": unh["id"]})
check("endpoint: add_note needs the text", r.status == 400, r.body)
r = call_ep("venues", "add_note", {"id": unh["id"], "text": "x"})
check("endpoint: only the log has add_note", r.status == 400, r.body)
r = call_ep("communication_logs", "list", {"filters": {"status": "not_sent"}})
check("endpoint: list returns the notes", any(x.get("notes") for x in r.body["data"]["records"]), r.body)

print(f"\n{total - len(fails)}/{total} checks passed" + ("" if not fails else "\nFAILED:\n - " + "\n - ".join(fails)))
sys.exit(1 if fails else 0)
