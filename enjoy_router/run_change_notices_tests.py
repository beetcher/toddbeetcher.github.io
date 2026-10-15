#!/usr/bin/env python3
"""Tests for the change notices, Stage 1 (Todd, 2026-10-15: notify abundantly): a class is cancelled or deleted, or one person's placement ends.
Real stores, the real CMS and renderer, a fake channel. Nothing is sent. Run from enjoy_router/:  python3 run_change_notices_tests.py  (-v lists every check)."""
import json, pathlib, sys
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import comms  # noqa: E402
from comms.calendar_event import make_ics  # noqa: E402
from comms.channels.fake import FakeChannel  # noqa: E402
from crud import attendances_service as AT  # noqa: E402
from crud import classes_service as CLS  # noqa: E402
from crud import communication_logs_crud as LG  # noqa: E402
from crud import comms_settings_crud as CS  # noqa: E402
from crud import individuals_service as IS  # noqa: E402
from crud import message_templates_crud as MT  # noqa: E402
from crud import scheduled_classes_crud as CL  # noqa: E402
from crud import venues_service as VS  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from launch_comms import change_context as CC  # noqa: E402
from launch_comms import kinds as K  # noqa: E402
from launch_comms.directory import IndividualDirectory  # noqa: E402
from launch_comms.stores import LogStore, SettingsStore, TemplateStore  # noqa: E402
from test_helpers import give_address  # noqa: E402

SCHEMAS = HERE.parent / "schemas"
SEED = json.loads((SCHEMAS / "examples" / "message_template.seed.json").read_text())["templates"]
A = "user:admin"
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

s = MemoryDocStore("t_")
for t in SEED:
    r = MT.create(s, {k: t[k] for k in ("kind", "channel", "audience", "name", "subject", "blocks", "is_active")}, A, now=tick()); assert r.ok, r.problems
    assert MT.publish(s, r.data["id"], A, now=tick()).ok
assert CS.create(s, {}, A, now=tick()).ok
def person(g, f="Test", **kw):
    r = IS.create(s, {"given_name": g, "family_name": f, **kw}, A, now=tick()); assert r.ok, r.problems; return r.data
todd = person("Todd", "Beetcher", email="todd@example.com"); give_address(s, todd["id"])
susan = person("Susan", "Adams", email="susan@example.com"); give_address(s, susan["id"])
glad = person("Gladys", "Hart", email="gladys@example.com")
lee = person("Lee", "Park", email="lee@example.com")
wait = person("Wanda", "Waits", email="wanda@example.com")
pat = person("Pat", "Nocontact")
v = VS.create_with_place(s, {"name": "Ozo's Coffee, East Pearl", "slug": "ozo", "status": "inactive", "is_public_venue": True}, A,
                         address={"street_number": "1500", "street": "Pearl St", "locality": "Boulder", "region": "CO", "postal_code": "80302", "country": "US"})
assert v.ok and VS.update(s, v.data["id"], {"status": "active"}, A).ok
assert VS.update(s, v.data["id"], {"rooms": [{"label": "Back room", "max_occupancy": 12}]}, A).ok
def klass(slug, **kw):
    base = {"title": slug, "slug": slug, "class_type": "private", "program_slug": "launch", "status": "scheduled", "is_public": False, "capacity_minimum": 1,
            "capacity_target": 2, "capacity_max": 3, "venue_id": v.data["id"], "is_venue_confirmed": False}
    r = CL.create(s, {**base, **kw}, A, now=tick()); assert r.ok, r.problems; return r.data
def assign(cls, who, role="student", **kw):
    r = AT.assign(s, {"scheduled_class_id": cls["id"], "role": role, "individual_id": who["id"], **kw}, A, now=tick()); assert r.ok, r.problems; return r.data["rec"] if "rec" in r.data else r.data
def room(slug, **kw):
    c = klass(slug, title="Intro to AI", starts_at="2026-11-14T16:00:00Z", duration_minutes=120, time_zone="America/Denver", venue_room_label="Back room", **kw)
    return c

def wire(channel=None, mode="live"):
    ch = channel or FakeChannel()
    comms.configure(comms.Comms(kinds=K.registry(), directory=IndividualDirectory(s), templates=TemplateStore(s), log=LogStore(s), settings=SettingsStore(s),
                                channels=[ch], mode=mode, clock=lambda: NOW))
    return ch
def log_of(**flt): return LG.list(s, flt).data["records"]
def by_to(ch): return {m["to"]: m["content"] for m in ch.sent}

# ---------------------------------------------------------------- the calendar helper: a cancel removes the event the placement added
ev = {"uid": "u1", "title": "T", "start": NOW, "end": NOW + timedelta(hours=1)}
pub, can = make_ics(ev, NOW).decode(), make_ics(ev, NOW, method="CANCEL").decode()
check("ics: a plain event has no SEQUENCE and is CONFIRMED (the placement email is unchanged)", "SEQUENCE" not in pub and "STATUS:CONFIRMED" in pub and "METHOD:PUBLISH" in pub)
check("ics: a cancel is METHOD:CANCEL, STATUS:CANCELLED with a SEQUENCE above any earlier one",
      "METHOD:CANCEL" in can and "STATUS:CANCELLED" in can and f"SEQUENCE:{int(NOW.timestamp())}" in can and "UID:u1@beetcher.com" in can)

# ---------------------------------------------------------------- a class is cancelled
ch = wire()
c1 = room("c1")
t_att = assign(c1, todd, "primary_instructor", order=1); s_att = assign(c1, susan, "instructor", order=2)
g_att = assign(c1, glad); l_att = assign(c1, lee); p_att = assign(c1, pat)
w_att = assign(c1, wait)
check("setup: the fourth student is waitlisted", s.get("attendances", w_att["id"])["status"] == "waitlisted", s.get("attendances", w_att["id"])["status"])
ch.sent.clear()
r = CLS.update(s, c1["id"], {"status": "cancelled"}, A, now=tick())
check("cancel: the class is cancelled", r.ok and s.get("scheduled_classes", c1["id"])["status"] == "cancelled", str(r.problems))
sent = by_to(ch)
check("cancel: every person with an email is told (2 instructors, 2 students, the waitlisted student)", sorted(sent) == sorted(["todd@example.com", "susan@example.com", "gladys@example.com", "lee@example.com", "wanda@example.com"]), str(sorted(sent)))
check("cancel: subject names the original time", sent["gladys@example.com"]["subject"] == "Launch — cancelled: Sat Nov 14, 9:00 AM", sent["gladys@example.com"]["subject"])
check("cancel: the student wording", "this workshop has been cancelled" in sent["gladys@example.com"]["text"] and "Hello Gladys," in sent["gladys@example.com"]["text"])
check("cancel: the instructor wording", "no longer scheduled to teach it" in sent["todd@example.com"]["text"] and "Hello Todd," in sent["todd@example.com"]["text"])
check("cancel: facts show what, when and where", "Was scheduled for: Saturday, November 14, 2026, 9:00 AM to 11:00 AM MST" in sent["lee@example.com"]["text"] and "Where: Ozo's Coffee, East Pearl · Back room" in sent["lee@example.com"]["text"])
att_ics = sent["gladys@example.com"]["attachments"][0]
check("cancel: a calendar cancel file keyed to the placement id", att_ics[0] == "workshop.ics" and "METHOD:CANCEL" in att_ics[2].decode() and f"UID:{g_att['id']}@beetcher.com" in att_ics[2].decode())
logs = log_of(scheduled_class_id=c1["id"])
cc = [x for x in logs if x["kind"] == "class_cancelled"]
check("cancel: one log entry per person (6 attempts: 5 sent, 1 no contact)", len(cc) == 6 and sum(x["status"] == "sent" for x in cc) == 5 and
      sum((x["status"], x["reason"]) == ("not_sent", "no_contact") for x in cc) == 1, str([(x["status"], x["reason"]) for x in cc]))
check("cancel: the log keeps the audience and the attendance id", {x["audience"] for x in cc} == {"student", "instructor"} and all(x.get("attendance_id") for x in cc))
check("cancel: nobody else was told (no leave notices)", not [x for x in logs if x["kind"] in ("placement_ended", "participant_left")])
n = len(ch.sent)
CLS.update(s, c1["id"], {"status": "cancelled"}, A, now=tick())
check("cancel again: nobody is told twice", len(ch.sent) == n)

# ---------------------------------------------------------------- a class is deleted
c2 = room("c2"); assign(c2, todd, "primary_instructor", order=1); assign(c2, lee)
ch.sent.clear()
r = CLS.soft_delete(s, c2["id"], A, now=tick())
check("delete: the class is deleted and its two people are told", r.ok and sorted(by_to(ch)) == ["lee@example.com", "todd@example.com"], str(r.problems))
c3 = klass("idea3", status="identified"); assign(c3, glad); ch.sent.clear()
CLS.update(s, c3["id"], {"status": "cancelled"}, A, now=tick())
check("cancel of a class with no date: nothing to say, nothing sent", not ch.sent)

# ---------------------------------------------------------------- one person's placement ends
c4 = room("c4"); t4 = assign(c4, todd, "primary_instructor", order=1); s4 = assign(c4, susan, "instructor", order=2)
g4 = assign(c4, glad); l4 = assign(c4, lee); assign(c4, pat); w4 = assign(c4, wait)
ch.sent.clear()
r = AT.update(s, g4["id"], {"status": "withdrawn"}, A, now=tick())
sent = by_to(ch)
check("withdraw: the student, and both instructors, are told", r.ok and sorted(sent) == ["gladys@example.com", "susan@example.com", "todd@example.com"], str(sorted(sent)))
check("withdraw: the student's wording", "You are no longer scheduled for this workshop" in sent["gladys@example.com"]["text"])
check("withdraw: the instructors learn who left and how", "Gladys Hart withdrew." in sent["todd@example.com"]["text"] and sent["todd@example.com"]["subject"] == "Launch — a student left: Intro to AI, Sat Nov 14, 9:00 AM", sent["todd@example.com"]["subject"])
check("withdraw: the student gets a calendar cancel, the instructors do not", "METHOD:CANCEL" in sent["gladys@example.com"]["attachments"][0][2].decode() and not sent["todd@example.com"]["attachments"])
ch.sent.clear()
AT.update(s, l4["id"], {"status": "declined"}, A, now=tick())
check("decline: wording for the instructors", "Lee Park declined their place." in by_to(ch)["todd@example.com"]["text"])
ch.sent.clear()
AT.update(s, w4["id"], {"status": "withdrawn"}, A, now=tick())
check("a waitlisted student leaving: only that student is told (no seat was lost)", sorted(by_to(ch)) == ["wanda@example.com"], str(sorted(by_to(ch))))
ch.sent.clear()
AT.update(s, s4["id"], {"status": "cancelled"}, A, now=tick())
check("an instructor leaving: only that instructor is told (the students come in Stage 2)", sorted(by_to(ch)) == ["susan@example.com"] and "no longer assigned to teach" in by_to(ch)["susan@example.com"]["text"], str(sorted(by_to(ch))))
c5 = room("c5"); assign(c5, todd, "primary_instructor", order=1); g5 = assign(c5, glad); ch.sent.clear()
r = AT.soft_delete(s, g5["id"], A, now=tick())
check("remove: the student and the instructor are told, 'was removed'", r.ok and sorted(by_to(ch)) == ["gladys@example.com", "todd@example.com"] and "Gladys Hart was removed." in by_to(ch)["todd@example.com"]["text"], str(sorted(by_to(ch))))
# outcomes and settled placements are not a change anyone needs to hear about
c6 = room("c6"); assign(c6, todd, "primary_instructor", order=1); g6 = assign(c6, glad)
AT.update(s, g6["id"], {"status": "attended"}, A, now=tick()); ch.sent.clear()
AT.update(s, g6["id"], {"status": "cancelled"}, A, now=tick())
check("an attended person later marked cancelled: no notice", not ch.sent)
# placed, left, placed, left: told both times
c7 = room("c7"); assign(c7, todd, "primary_instructor", order=1); g7 = assign(c7, glad); ch.sent.clear()
AT.update(s, g7["id"], {"status": "withdrawn"}, A, now=tick()); AT.update(s, g7["id"], {"status": "assigned"}, A, now=tick()); AT.update(s, g7["id"], {"status": "withdrawn"}, A, now=tick())
check("left twice: told both times (two student notices, two instructor notices)", len([m for m in ch.sent if m["to"] == "gladys@example.com"]) == 2 and len([m for m in ch.sent if m["to"] == "todd@example.com"]) == 2, str(len(ch.sent)))

# ---------------------------------------------------------------- a mail problem or no CMS never blocks the change
bad = wire(FakeChannel(outcome="rejected", error_code="provider_down"))
c8 = room("c8"); assign(c8, todd, "primary_instructor", order=1); g8 = assign(c8, glad)
r = CLS.update(s, c8["id"], {"status": "cancelled"}, A, now=tick())
check("provider down: the cancel still succeeds", r.ok and s.get("attendances", g8["id"])["status"] == "cancelled")
check("provider down: the failures are logged for the Messages station", {x["status"] for x in log_of(scheduled_class_id=c8["id"])} == {"failed"})
comms.configure(None)
c9 = room("c9"); assign(c9, glad); g9 = assign(c9, lee)
r = CLS.update(s, c9["id"], {"status": "cancelled"}, A, now=tick())
check("CMS not configured: the cancel works and nothing is attempted", r.ok and not log_of(scheduled_class_id=c9["id"]))
ch = wire(mode="off"); c10 = room("c10"); assign(c10, glad)
CLS.update(s, c10["id"], {"status": "cancelled"}, A, now=tick())
check("CMS off: logged as skipped, nothing sent", not ch.sent and {x["reason"] for x in log_of(scheduled_class_id=c10["id"])} == {"cms_off"})

# a bug inside the notice code is swallowed: the cancel and the removal still stand
ch = wire(); c11 = room("c11"); assign(c11, todd, "primary_instructor", order=1); g11 = assign(c11, glad); c12 = room("c12"); g12 = assign(c12, lee)
_real = (CC.class_cancelled_items, CC.placement_ended_items)
def boom(*a, **k): raise RuntimeError("bug")
CC.class_cancelled_items = CC.placement_ended_items = boom
r1 = CLS.update(s, c11["id"], {"status": "cancelled"}, A, now=tick()); r2 = AT.update(s, g12["id"], {"status": "withdrawn"}, A, now=tick())
CC.class_cancelled_items, CC.placement_ended_items = _real
check("a bug in the notice builder: the cancel and the withdrawal still succeed", r1.ok and r2.ok and s.get("attendances", g11["id"])["status"] == "cancelled" and s.get("attendances", g12["id"])["status"] == "withdrawn")

# ---------------------------------------------------------------- the builder itself
ch = wire()
check("every built call satisfies its kind's fact schema",
      all(not K.registry().validate(i["kind"], i["context"]) for i in CC.class_cancelled_items(s, s.get("scheduled_classes", c1["id"]), [dict(s.get("attendances", g_att["id"]))], A)))
check("a record with an unknown role gets no notice", CC.class_cancelled_items(s, s.get("scheduled_classes", c1["id"]), [{**s.get("attendances", g_att["id"]), "role": "observer"}], A) == [])
check("an unknown 'how' builds nothing", CC.placement_ended_items(s, dict(s.get("attendances", g_att["id"])), "exploded", A) == [])

print(f"\n{total - len(fails)}/{total} checks passed" + ("" if not fails else "\nFAILED:\n - " + "\n - ".join(fails)))
sys.exit(1 if fails else 0)
