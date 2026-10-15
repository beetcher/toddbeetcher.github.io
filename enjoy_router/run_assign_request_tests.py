#!/usr/bin/env python3
"""Tests for placing EVERYONE on a registration request in a class (Todd, 2026-10-15: people named as participants were never on the attendance list).
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


import uuid
def request(participants, attending=True, **kw):
    rid = str(uuid.uuid4())
    doc = {"id": rid, "registration_type": "class", "attendee_count": len(participants) + (1 if attending else 0), "confirmation_number": "ICDT-000001",
           "first_name": "Ann", "last_name": "Requester", "email": "ann@example.com", "is_requester_attending": attending,
           "participants": participants, "created_at": "2026-10-14T10:00:00Z", "processing_status": "not_processed", **kw}
    s.data.setdefault("t_registration_requests", {})[rid] = doc
    return doc
ann = person("Ann", "Requester", email="ann@example.com")
ch = wire()
c1 = room("c1", capacity_max=5)
rq = request([{"first_name": "Bob", "last_name": "Guest", "email": "bob@example.com"}, {"first_name": "Cy"}, {"last_name": "Onlylast", "email": "ol@example.com"}])
r = AT.assign_request(s, {"request_id": rq["id"], "scheduled_class_id": c1["id"]}, A, requester={"individual_id": ann["id"]}, now=tick())
check("request: ok", r.ok, str(r.problems))
recs = r.data["records"] if r.ok else []
check("request: four students placed (requester + 3), 3 new people", len(recs) == 4 and r.data["created_people"] == 3, str(len(recs)))
live = [d for d in s.data["t_attendances"].values() if d["scheduled_class_id"] == c1["id"]]
check("request: all four are on the class attendance list as assigned students", len(live) == 4 and all(d["role"] == "student" and d["status"] == "assigned" for d in live))
check("request: every record carries the request id", all(d.get("request_id") == rq["id"] for d in live))
check("request: last-name-only participant is a person", any(x.get("given_name") == "Onlylast" and not x.get("family_name") for x in s.data["t_individuals"].values()))
sent = by_to(ch)
check("request: each person with an email gets the placement email", {"ann@example.com", "bob@example.com", "ol@example.com"} <= set(sent), str(sorted(sent)))
nolog = [l for l in log_of() if l.get("status") == "not_sent"]
check("request: the participant with no email is logged not_sent (no_contact), and nobody else was emailed for them", len(nolog) == 1 and "ann@example.com" in sent and len(sent) == 3, str([(l.get('status'), l.get('reason')) for l in nolog]))
r2 = AT.assign_request(s, {"request_id": rq["id"], "scheduled_class_id": c1["id"]}, A, requester={"individual_id": ann["id"]}, now=tick())
check("again: refused as already in the class, nothing added", not r2.ok and r2.problems == [{"field": "request_id", "issue": "already_in_class"}] and len([d for d in s.data["t_attendances"].values() if d["scheduled_class_id"] == c1["id"]]) == 4, str(r2.problems))

# requester not attending: only the participants
c2 = room("c2", capacity_max=5)
rq2 = request([{"first_name": "Dee", "email": "dee@example.com"}], attending=False)
ch = wire()
r = AT.assign_request(s, {"request_id": rq2["id"], "scheduled_class_id": c2["id"]}, A, now=tick())
check("not attending: only the participant is placed; the requester is not", r.ok and len(r.data["records"]) == 1 and "dee@example.com" in by_to(ch) and "ann@example.com" not in by_to(ch), str(r.problems))

# capacity: waitlist the overflow
c3 = room("c3", capacity_max=2)
rq3 = request([{"first_name": "E1", "email": "e1@example.com"}, {"first_name": "E2", "email": "e2@example.com"}])
r = AT.assign_request(s, {"request_id": rq3["id"], "scheduled_class_id": c3["id"]}, A, requester={"individual_id": ann["id"]}, now=tick())
check("capacity: two seats, three people: first two assigned, the third waitlisted", r.ok and [x["status"] for x in r.data["records"]] == ["assigned", "assigned", "waitlisted"], str(r.problems or [x["status"] for x in r.data["records"]]))

# all or nothing
c4 = room("c4", capacity_max=5)
rq4 = request([{"first_name": "Ok", "email": "ok@example.com"}, {"first_name": "Bad", "email": "not-an-email"}])
before = len(s.data["t_attendances"]); people_before = len(s.data["t_individuals"])
ch = wire()
r = AT.assign_request(s, {"request_id": rq4["id"], "scheduled_class_id": c4["id"]}, A, requester={"individual_id": ann["id"]}, now=tick())
check("all or nothing: a bad participant refuses everything, named by position", not r.ok and any(p["field"].startswith("participant_2.") for p in r.problems) and len(s.data["t_attendances"]) == before and len(s.data["t_individuals"]) == people_before and not ch.sent, str(r.problems))

# refusals
u = str(uuid.uuid4())
check("unknown request / class are refused", AT.assign_request(s, {"request_id": u, "scheduled_class_id": c4["id"]}, A, now=tick()).problems == [{"field": "request_id", "issue": "not_found"}]
      and AT.assign_request(s, {"request_id": rq4["id"], "scheduled_class_id": u}, A, now=tick()).problems == [{"field": "scheduled_class_id", "issue": "not_found"}])
rq5 = request([], attending=False)
check("nobody to place is refused", AT.assign_request(s, {"request_id": rq5["id"], "scheduled_class_id": c4["id"]}, A, now=tick()).problems == [{"field": "request_id", "issue": "no_people"}])
check("requester must choose one of individual_id / person", AT.assign_request(s, {"request_id": rq4["id"], "scheduled_class_id": c4["id"]}, A, requester={}, now=tick()).problems == [{"field": "requester", "issue": "choose_one"}])

# new requester person
c5 = room("c5", capacity_max=5)
rq6 = request([{"first_name": "Fay", "email": "fay@example.com"}])
r = AT.assign_request(s, {"request_id": rq6["id"], "scheduled_class_id": c5["id"]}, A, requester={"person": {"given_name": "New", "family_name": "Req", "email": "newreq@example.com"}}, now=tick())
check("new requester: created and placed with the participant", r.ok and r.data["created_people"] == 2, str(r.problems))

# the instructors are told (Todd, 2026-10-15: no instructor email on assignment was a bug)
ch = wire()
c7 = room("c7", capacity_max=3)
lead, second = person("Lena", "Lead", email="lena@example.com"), person("Sam", "Second", email="sam@example.com"); give_address(s, lead["id"]); give_address(s, second["id"])
r = AT.assign(s, {"scheduled_class_id": c7["id"], "role": "primary_instructor", "individual_id": lead["id"], "order": 1}, A, now=tick())
check("instructor placed: the instructor is told they are assigned, with a calendar file whose UID is the attendance id",
      r.ok and "lena@example.com" in by_to(ch) and by_to(ch)["lena@example.com"]["subject"].startswith("Launch — you are assigned to teach")
      and any(a[0] == "workshop.ics" and r.data["id"].encode() in a[2] and b"METHOD:PUBLISH" in a[2] for a in (ch.sent[-1]["content"].get("attachments") or [])), str(r.problems))
check("instructor placed: the log carries kind instructor_placed", any(l["kind"] == "instructor_placed" for l in log_of()))
r = AT.assign(s, {"scheduled_class_id": c7["id"], "role": "instructor", "individual_id": second["id"], "order": 2}, A, now=tick()); ch.sent.clear()
rq8 = request([{"first_name": "Pia", "email": "pia@example.com"}, {"first_name": "Quin"}, {"first_name": "Rex"}])
r = AT.assign_request(s, {"request_id": rq8["id"], "scheduled_class_id": c7["id"]}, A, requester={"individual_id": ann["id"]}, now=tick())
told = {m["to"]: m["content"] for m in ch.sent if m["content"]["subject"].startswith("Launch — students added")}
check("students added: each instructor gets ONE email for the whole request", r.ok and sorted(told) == ["lena@example.com", "sam@example.com"], str(sorted(told)))
body = json.dumps(told.get("lena@example.com", {}))
check("students added: it lists who was added and who is waiting", "Ann Requester" in body and "Pia" in body and "Quin" in body and "waiting list" in body and "Rex" in body, body[:400])
check("students added: sent again for the same placement is not duplicated", len([m for m in ch.sent if m["to"] == "lena@example.com" and "students added" in m["content"]["subject"]]) == 1)
wl = [l for l in log_of() if l.get("kind") == "placement_confirmation" and l.get("request_id") == rq8["id"]]
check("the placement email log entries carry the request id (for the confirmation number)", len(wl) >= 1, str(len(wl)))
ch.sent.clear()
c8 = klass("c8", title="Idea", status="identified")
check("a class with no date: nobody is told anything", AT.assign_request(s, {"request_id": request([{"first_name": "Zed", "email": "zed@example.com"}], attending=False)["id"], "scheduled_class_id": c8["id"]}, A, now=tick()).ok and not ch.sent, str(ch.sent))

check("students added: the email says how full the class is", "3 of 3 seats taken" in body, body[:600])
# an instructor placed as part of putting a request in a class: the log entry carries that request, the instructor's own record does not
c9 = room("c9", capacity_max=4)
lead2 = person("Mo", "Lead", email="mo@example.com"); give_address(s, lead2["id"])
ch = wire()
r = AT.assign(s, {"scheduled_class_id": c9["id"], "role": "primary_instructor", "individual_id": lead2["id"]}, A, now=tick(), via_request_id=rq8["id"])
ent = [l for l in log_of() if l["kind"] == "instructor_placed" and l.get("attendance_id") == r.data["id"]]
check("instructor placed via a request: the log entry carries the request id", len(ent) == 1 and ent[0].get("request_id") == rq8["id"], str(ent))
check("...and the instructor's own attendance record does not", "request_id" not in s.get("attendances", r.data["id"]) or not s.get("attendances", r.data["id"]).get("request_id"))
lead3 = person("Nia", "Lead", email="nia@example.com"); give_address(s, lead3["id"])
r = AT.assign(s, {"scheduled_class_id": c9["id"], "role": "instructor", "individual_id": lead3["id"]}, A, now=tick(), via_request_id="not-a-uuid")
ent = [l for l in log_of() if l["kind"] == "instructor_placed" and l.get("attendance_id") == r.data["id"]]
check("a bad via_request_id is ignored, not an error", r.ok and len(ent) == 1 and not ent[0].get("request_id"), str(ent))
# the seed script can publish changed wording as a new version
import seed_comms
s2 = MemoryDocStore("r_")
old = [dict(x) for x in SEED if x["kind"] == "students_added"][0]
old = {**old, "blocks": [{**b, "rows": [r_ for r_ in b["rows"] if r_["label"] != "Seats"]} if b["type"] == "facts_table" else b for b in old["blocks"]]}
r0 = MT.create(s2, {k: old[k] for k in ("kind", "channel", "audience", "name", "subject", "blocks", "is_active")}, A, now=tick()); assert r0.ok, r0.problems
assert MT.publish(s2, r0.data["id"], A, now=tick()).ok
check("seed refresh: the changed template is found", [t_["kind"] for _c, t_ in seed_comms.changed(s2)] == ["students_added"] or "students_added" in [t_["kind"] for _c, t_ in seed_comms.changed(s2)])
check("seed refresh: nothing changes for a kind not named", seed_comms.refresh(s2, {"class_cancelled"}) == [])
got = seed_comms.refresh(s2, {"students_added"})
stand = MT.standing(s2, old)
check("seed refresh: a new version is published and the old one is kept", len(got) == 1 and stand["version"] == 2 and any(r_["label"] == "Seats" for b in stand["blocks"] if b["type"] == "facts_table" for r_ in b["rows"]) and len(MT._same_key(s2, old)) == 2, str(got))
check("seed refresh: running it again does nothing", seed_comms.refresh(s2, {"students_added"}) == [])

# the endpoint door
from crud_endpoint import handle_admin  # noqa: E402
c6 = room("c6", capacity_max=5)
rq7 = request([{"first_name": "Gus", "email": "gus@example.com"}])
from crud_endpoint import make_failure_limiter  # noqa: E402
res = handle_admin("POST", "Bearer " + "k" * 16 + "Z" * 16 + "-test", json.dumps({"collection": "attendances", "op": "assign_request", "args": {
    "data": {"request_id": rq7["id"], "scheduled_class_id": c6["id"]}, "requester": {"individual_id": ann["id"]}}}).encode(),
    "k" * 16 + "Z" * 16 + "-test", "v", s, make_failure_limiter(), NOW)
body = json.loads(res.body) if isinstance(res.body, (str, bytes)) else res.body
check("endpoint: assign_request through the admin door places both", res.status == 200 and body.get("ok") and len(body["data"]["records"]) == 2, f"{res.status} {body}")
print(f"\n{total - len(fails)}/{total} checks passed" + ("" if not fails else "\nFAILED:\n - " + "\n - ".join(fails)))
sys.exit(1 if fails else 0)
