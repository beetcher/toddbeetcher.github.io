#!/usr/bin/env python3
"""Tests for the change notices, Stage 2 (Todd, 2026-10-15: notify abundantly): a class, its lead instructor, its venue or its place changes.
Real stores, the real CMS and renderer, a fake channel. Nothing is sent. Run from enjoy_router/:  python3 run_class_changed_tests.py  (-v lists every check)."""
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
from crud import locations_service as LS  # noqa: E402
from crud import venues_service as VS  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from launch_comms import change_context as CC  # noqa: E402
from launch_comms import kinds as K  # noqa: E402
from launch_comms.directory import IndividualDirectory  # noqa: E402
from launch_comms.stores import LogStore, SettingsStore, TemplateStore  # noqa: E402
from test_helpers import give_address  # noqa: E402

CC._now = lambda: NOW      # "now" for the builders is fixed, so the tests do not age
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


OZO = {"street_number": "1500", "street": "Pearl St", "locality": "Boulder", "region": "CO", "postal_code": "80302", "country": "US"}
assert VS.update(s, v.data["id"], {"rooms": [{"label": "Back room", "max_occupancy": 12}, {"label": "Front room", "max_occupancy": 20}]}, A).ok
bob = person("Bobby", "Hodgkins", email="bobby@example.com"); give_address(s, bob["id"])
def full(slug, **kw):
    c = room(slug, **kw)
    assign(c, todd, "primary_instructor", order=1); assign(c, susan, "instructor", order=2)
    a = {"g": assign(c, glad), "l": assign(c, lee), "p": assign(c, pat), "w": assign(c, wait)}
    return c, a
def to_changed(ch): return {m["to"]: m["content"] for m in ch.sent if m["content"]["subject"].startswith("Launch — class changed")}
ALL = sorted(["todd@example.com", "susan@example.com", "gladys@example.com", "lee@example.com", "wanda@example.com"])
ch = wire()
check("seed: the class_changed templates exist for student and instructor", {(t["audience"]) for t in SEED if t["kind"] == "class_changed"} == {"student", "instructor"})

# ---------------------------------------------------------------- a class is moved to another day
c1, a1 = full("c1")
check("setup: the fourth student is on the waiting list", s.get("attendances", a1["w"]["id"])["status"] == "waitlisted")
ch.sent.clear()
r = CLS.update(s, c1["id"], {"starts_at": "2026-11-15T16:00:00Z"}, A, now=tick())
sent = to_changed(ch)
check("date: the save works", r.ok, str(r.problems))
check("date: all five people with an email are told, one message each", sorted(sent) == ALL and len(ch.sent) == 5, str(sorted(sent)))
g = sent["gladys@example.com"]
check("date: subject carries the new day", g["subject"] == "Launch — class changed: Intro to AI, Sun Nov 15, 9:00 AM", g["subject"])
check("date: says what changed, was and now", "The date and time changed." in g["text"] and "Saturday, November 14, 2026, 9:00 AM to 11:00 AM MST \u2192 Sunday, November 15, 2026, 9:00 AM to 11:00 AM MST" in g["text"], g["text"][:600])
check("date: rows for what did not change are left out", "Place:" not in g["text"] and "Room:" not in g["text"] and "Lead instructor:" not in g["text"])
check("date: the class as it now stands is listed", "When: Sunday, November 15, 2026, 9:00 AM to 11:00 AM MST" in g["text"] and "Where: Ozo's Coffee, East Pearl · Back room" in g["text"])
ics = g["attachments"][0][2].decode()
check("date: a calendar update, same UID as the placement, with a SEQUENCE", "METHOD:PUBLISH" in ics and f"UID:{a1['g']['id']}@beetcher.com" in ics and f"SEQUENCE:{int(NOW.timestamp())}" in ics and "DTSTART:20261115T160000Z" in ics, ics[:300])
check("date: the instructor gets the same, with the instructor greeting and a calendar update", "Hello Todd," in sent["todd@example.com"]["text"] and sent["todd@example.com"]["attachments"] and f"UID:{s.query('attendances', [('individual_id', '==', todd['id']), ('scheduled_class_id', '==', c1['id'])])[0]['id']}@beetcher.com" in sent["todd@example.com"]["attachments"][0][2].decode())
w = sent["wanda@example.com"]
check("date: the waitlisted student is told too, with no calendar file, and that she is still waitlisted", not w["attachments"] and "still on the waiting list" in w["text"] and "calendar file" not in w["text"], w["text"][-300:])
check("date: a student with a seat is told about the calendar file", "attached calendar file updates your calendar" in g["text"])
logs = [x for x in log_of(scheduled_class_id=c1["id"]) if x["kind"] == "class_changed"]
check("date: six log entries (5 sent, the person with no email is not_sent / no_contact)", len(logs) == 6 and sum(x["status"] == "sent" for x in logs) == 5 and sum((x["status"], x["reason"]) == ("not_sent", "no_contact") for x in logs) == 1, str([(x["status"], x["reason"]) for x in logs]))
check("date: log entries carry the class and attendance ids", all(x.get("attendance_id") and x.get("scheduled_class_id") == c1["id"] for x in logs))

# ---------------------------------------------------------------- length, room, notes, all at once = ONE message per person
ch.sent.clear()
r = CLS.update(s, c1["id"], {"duration_minutes": 90, "venue_room_label": "Front room", "venue_notes": "Park behind the building"}, A, now=tick())
sent = to_changed(ch); g = sent["gladys@example.com"]
check("combined: one message per person for one save", r.ok and sorted(sent) == ALL and len(ch.sent) == 5, str(len(ch.sent)))
check("combined: the summary names all three", "The date and time, the room and the notes changed." in g["text"], g["text"][:300])
check("combined: room, notes and the new length lines", "Room: Back room \u2192 Front room" in g["text"] and "Notes: none \u2192 Park behind the building" in g["text"] and "Sunday, November 15, 2026, 9:00 AM to 11:00 AM MST \u2192 Sunday, November 15, 2026, 9:00 AM to 10:30 AM MST" in g["text"], g["text"][:700])
check("combined: the current notes are shown", "Notes: Park behind the building" in g["text"].split("Here is the class")[1])

# ---------------------------------------------------------------- saves that change nothing a person sees
ch.sent.clear()
CLS.update(s, c1["id"], {"title": "Intro to AI v2", "capacity_max": 4}, A, now=tick())
CLS.update(s, c1["id"], {"starts_at": "2026-11-15T16:00:00Z"}, A, now=tick())          # same value again
CLS.update(s, c1["id"], {"status": "enrolling", "price_cents": 1000, "price_basis": "per_person"}, A, now=tick())
check("a title, capacity, status or unchanged value: nobody is told", not ch.sent, str([m["to"] for m in ch.sent]))
past = klass("past", title="Past", starts_at="2026-10-01T16:00:00Z", duration_minutes=60, time_zone="America/Denver"); assign(past, glad); ch.sent.clear()
CLS.update(s, past["id"], {"starts_at": "2026-10-02T16:00:00Z"}, A, now=tick())
check("a class that has already started: nobody is told", not ch.sent)
canc = room("canc"); assign(canc, glad); CLS.update(s, canc["id"], {"status": "cancelled"}, A, now=tick()); ch.sent.clear()
CLS.update(s, canc["id"], {"venue_notes": "x"}, A, now=tick())
check("a cancelled class: no change notice", not ch.sent)

# ---------------------------------------------------------------- A -> B -> A is three messages; a repeat of one call is not
c2 = room("c2"); g2 = assign(c2, glad); ch.sent.clear()
for st in ("2026-11-20T16:00:00Z", "2026-11-14T16:00:00Z", "2026-11-20T16:00:00Z"):
    CLS.update(s, c2["id"], {"starts_at": st}, A, now=tick())
check("A to B to A: three messages, none swallowed as a duplicate", len(to_changed(ch) and [m for m in ch.sent if m["to"] == "gladys@example.com"]) == 3, str(len(ch.sent)))
before = CC.class_state(s, c2["id"]); CLS.update(s, c2["id"], {"starts_at": "2026-11-21T16:00:00Z"}, A, now=tick())
after = CC.class_state(s, c2["id"]); n = len(ch.sent)
items = CC.class_changed_items(s, before, after, A, "STAMP-1"); comms.notify_many(items, 30); comms.notify_many(items, 30)
check("the same call repeated with the same save stamp: sent once", len(ch.sent) == n + 1, str(len(ch.sent) - n))

# ---------------------------------------------------------------- a class given its first date: people already placed get the normal emails
c3 = klass("idea", title="Idea class", status="identified", capacity_max=3)
t3 = assign(c3, todd, "primary_instructor", order=1); g3 = assign(c3, glad); l3 = assign(c3, lee); w3 = assign(c3, wait); x3 = assign(c3, pat)
w3r = s.get("attendances", w3["id"]); ch.sent.clear()
r = CLS.update(s, c3["id"], {"status": "scheduled", "starts_at": "2026-11-18T16:00:00Z", "duration_minutes": 60, "time_zone": "America/Denver", "is_venue_confirmed": True}, A, now=tick())
subj = {m["to"]: m["content"]["subject"] for m in ch.sent}
check("first date: the save works", r.ok, str(r.problems))
check("first date: the seated students get their placement email, the instructor the assigned-to-teach email",
      subj.get("gladys@example.com", "").startswith("Launch — you're scheduled") and subj.get("lee@example.com", "").startswith("Launch — you're scheduled") and subj.get("todd@example.com", "").startswith("Launch — you are assigned to teach"), str(subj))
check("first date: nobody is told it 'changed' (they were never told anything before)", not any("class changed" in x for x in subj.values()))
check("first date: a waitlisted student is not told (as when first placed)", "wanda@example.com" not in subj or w3r["status"] != "waitlisted", str(subj))

# ---------------------------------------------------------------- the lead instructor changes
c4 = room("c4"); t4 = assign(c4, todd, "primary_instructor", order=2); s4 = assign(c4, susan, "instructor", order=3); g4 = assign(c4, glad); w4 = assign(c4, lee)
ch.sent.clear()
b4 = assign(c4, bob, "primary_instructor", order=1)
subj = {m["to"]: m["content"] for m in ch.sent}
changed = to_changed(ch)
check("new lead placed: the new lead gets the 'assigned to teach' email and not a change notice", "bobby@example.com" in subj and "bobby@example.com" not in changed and subj["bobby@example.com"]["subject"].startswith("Launch — you are assigned to teach"), str(sorted(subj)))
check("new lead placed: the old lead, the other instructor and both students are told", sorted(changed) == ["gladys@example.com", "lee@example.com", "susan@example.com", "todd@example.com"], str(sorted(changed)))
check("new lead placed: wording", "The lead instructor changed." in changed["gladys@example.com"]["text"] and "Lead instructor: Todd Beetcher \u2192 Bobby Hodgkins" in changed["gladys@example.com"]["text"], changed["gladys@example.com"]["text"][:400])
ch.sent.clear()
AT.update(s, b4["id"], {"status": "withdrawn"}, A, now=tick())
subj = {m["to"]: m["content"] for m in ch.sent}; changed = to_changed(ch)
check("lead leaves: the lead is told they are off the class, everyone else that the lead changed back", subj["bobby@example.com"]["subject"].startswith("Launch — you are no longer assigned") and sorted(changed) == ["gladys@example.com", "lee@example.com", "susan@example.com", "todd@example.com"], str(sorted(subj)))
check("lead leaves: names the old and new lead", "Lead instructor: Bobby Hodgkins \u2192 Todd Beetcher" in changed["lee@example.com"]["text"])
ch.sent.clear()
AT.update(s, s4["id"], {"role": "primary_instructor", "order": 1}, A, now=tick())
check("a role change that makes someone the lead is a change too", "Lead instructor: Todd Beetcher \u2192 Susan Adams" in to_changed(ch).get("gladys@example.com", {}).get("text", ""), str(sorted(to_changed(ch))))
ch.sent.clear()
AT.update(s, s4["id"], {"notes": "just a note"}, A, now=tick())
check("a note on an instructor's record changes nothing anyone sees", not ch.sent)
ch.sent.clear()
c4b = room("c4b"); assign(c4b, glad); assign(c4b, lee)
check("placing a student is not a lead change (the student gets only the placement email)", not [m for m in ch.sent if "class changed" in m["content"]["subject"]])
ch.sent.clear()
AT.soft_delete(s, s4["id"], A, now=tick())
check("removing the lead (a mistake): the rest are told who leads now", "Lead instructor: Susan Adams \u2192 Todd Beetcher" in to_changed(ch).get("lee@example.com", {}).get("text", ""), str(sorted(to_changed(ch))))

# ---------------------------------------------------------------- a venue changes its name
c5, a5 = full("c5"); ch.sent.clear()
r = VS.update(s, v.data["id"], {"name": "Ozo's Coffee, Pearl Street"}, A, now=tick())
sent = to_changed(ch)
check("venue renamed: everyone in every upcoming class here is told", r.ok and "gladys@example.com" in sent and "todd@example.com" in sent and "wanda@example.com" in sent, str(sorted(sent)))
check("venue renamed: the place line says old and new", "Place: Ozo's Coffee, East Pearl, 1500 Pearl St, Boulder, CO 80302 \u2192 Ozo's Coffee, Pearl Street, 1500 Pearl St, Boulder, CO 80302" in sent["gladys@example.com"]["text"], sent["gladys@example.com"]["text"][:500])
check("venue renamed: the past class and the cancelled class here were not mentioned", not [x for x in log_of(scheduled_class_id=past["id"]) if x["kind"] == "class_changed"] and not [x for x in log_of(scheduled_class_id=canc["id"]) if x["kind"] == "class_changed"])
ch.sent.clear()
VS.update(s, v.data["id"], {"is_public_venue": False}, A, now=tick())
check("a venue edit nobody sees (a flag): nobody is told", not ch.sent)
# a person in two classes at the venue gets one message per class
ch.sent.clear(); VS.update(s, v.data["id"], {"name": "Ozo's Coffee"}, A, now=tick())
glads = [m for m in ch.sent if m["to"] == "gladys@example.com" and m["content"]["subject"].startswith("Launch — class changed")]
check("two classes at one venue: a person in both gets one message for each", len(glads) >= 2, str(len(glads)))

# ---------------------------------------------------------------- a venue moves, or its place's address is edited
ch.sent.clear()
r = VS.set_place(s, v.data["id"], A, address={**OZO, "street_number": "2000", "street": "Walnut St", "postal_code": "80302"}, now=tick())
check("venue moved: everyone is told, with the new address", r.ok and "gladys@example.com" in to_changed(ch) and "2000 Walnut St" in to_changed(ch)["gladys@example.com"]["text"] and "1500 Pearl St" in to_changed(ch)["gladys@example.com"]["text"], str(r.problems))
place = VS.get(s, v.data["id"], expand=True).data["place"]
ch.sent.clear()
r = LS.update(s, place["location_id"], {"addresses": [{**place["address"], "street_number": "2020"}]}, A, now=tick())
check("a place's address edited: everyone in upcoming classes at venues there is told", r.ok and "gladys@example.com" in to_changed(ch) and "2020 Walnut St" in to_changed(ch)["gladys@example.com"]["text"], str(r.problems) + str(sorted(to_changed(ch))))
ch.sent.clear()
LS.update(s, place["location_id"], {"name": "A new nickname"}, A, now=tick())
check("a place's name edited (not in any message): nobody is told", not ch.sent)
v2 = VS.create_with_place(s, {"name": "Second Venue", "slug": "second", "status": "inactive", "is_public_venue": True}, A, location_id=place["location_id"]); assert v2.ok
assert VS.update(s, v2.data["id"], {"status": "active"}, A).ok
c6 = klass("c6", title="At the second venue", starts_at="2026-11-25T16:00:00Z", duration_minutes=60, time_zone="America/Denver", venue_id=v2.data["id"]); assign(c6, bob)
ch.sent.clear()
cur = LS.get(s, place["location_id"]).data
LS.update(s, place["location_id"], {"addresses": [{**cur["addresses"][0], "street_number": "2040"}]}, A, now=tick())
check("a shared place: people at BOTH venues' classes are told", {"gladys@example.com", "bobby@example.com"} <= set(to_changed(ch)), str(sorted(to_changed(ch))))
# the venue's class moves venue
ch.sent.clear()
CLS.update(s, c6["id"], {"venue_id": v.data["id"], "venue_room_label": "Back room"}, A, now=tick())
check("a class moved to another venue: told, naming both places", "Place: Second Venue" in to_changed(ch)["bobby@example.com"]["text"] and "Room: none \u2192 Back room" in to_changed(ch)["bobby@example.com"]["text"], to_changed(ch)["bobby@example.com"]["text"][:500])

# ---------------------------------------------------------------- failures never undo the change
bad = wire(FakeChannel(outcome="rejected", error_code="provider_down"))
c7, a7 = full("c7")
r = CLS.update(s, c7["id"], {"starts_at": "2026-11-16T16:00:00Z"}, A, now=tick())
check("provider down: the edit still succeeds and the failures are logged", r.ok and s.get("scheduled_classes", c7["id"])["starts_at"] == "2026-11-16T16:00:00Z" and {x["status"] for x in log_of(scheduled_class_id=c7["id"]) if x["kind"] == "class_changed"} >= {"failed"})
comms.configure(None)
c8, a8 = full("c8"); r = CLS.update(s, c8["id"], {"starts_at": "2026-11-16T16:00:00Z"}, A, now=tick())
check("CMS not configured: the edit works and nothing is attempted", r.ok and all(x["kind"] != "class_changed" for x in log_of(scheduled_class_id=c8["id"])))
ch = wire(mode="off"); c9, a9 = full("c9"); CLS.update(s, c9["id"], {"starts_at": "2026-11-16T16:00:00Z"}, A, now=tick())
check("CMS off: logged skipped, nothing sent", not ch.sent and {x["reason"] for x in log_of(scheduled_class_id=c9["id"]) if x["kind"] == "class_changed"} == {"cms_off"})
ch = wire(); c10, a10 = full("c10")
_real = CC.class_changed_items
def boom(*a, **k): raise RuntimeError("bug")
CC.class_changed_items = boom
r = CLS.update(s, c10["id"], {"starts_at": "2026-11-16T16:00:00Z"}, A, now=tick())
CC.class_changed_items = _real
check("a bug in the builder: the edit still succeeds", r.ok and s.get("scheduled_classes", c10["id"])["starts_at"] == "2026-11-16T16:00:00Z")

print(f"\n{total - len(fails)}/{total} checks passed" + (f"; FAILED: {fails}" if fails else ""))
sys.exit(1 if fails else 0)
