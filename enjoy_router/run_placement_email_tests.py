#!/usr/bin/env python3
"""In-memory tests for the placement confirmation email as it now runs: attendances_service asks the CMS (comms/, launch_comms/), which finds the
seed template, renders it, sends it through smtp_transport and writes one communication_log entry per try. A fake transport stands in for Brevo:
nothing is sent. Run from enjoy_router/:  python3 run_placement_email_tests.py  (-v lists every check)."""
import json, pathlib, sys, re
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import comms  # noqa: E402
import seed_comms  # noqa: E402
import smtp_transport as T  # noqa: E402
from crud import attendances_service as AT  # noqa: E402
from crud import communication_logs_crud as LG  # noqa: E402
from crud import individuals_service as IS  # noqa: E402
from crud import scheduled_classes_crud as CL  # noqa: E402
from crud import venues_service as VS  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud_endpoint import handle_admin, make_failure_limiter  # noqa: E402
from launch_comms import wiring  # noqa: E402
from test_helpers import give_address  # noqa: E402
from crud import instructor_rosters_service as INS  # noqa: E402

START = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)
KEY = "k" * 16 + "Z" * 16 + "-test-key-not-real"
A = "user:admin"
fails, total, clock = [], 0, [0]
def tick():
    clock[0] += 5
    return START + timedelta(seconds=clock[0])
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    if not ok or "-v" in sys.argv: print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")

sent, mode = [], ["accept"]
def fake(key, to, subject, body, html=None, attachments=None, headers=None):
    if mode[0] == "raise":
        raise RuntimeError("secret detail")
    sent.append({"to": to, "subject": subject, "body": body, "html": html, "att": attachments, "headers": headers})
    return {"accept": T.SendResult(True, "accepted"), "reject": T.SendResult(False, "recipient_rejected"), "unknown": T.SendResult(False, "unknown")}[mode[0]]
T.transport = fake

s = MemoryDocStore("")
need, todo = seed_comms.plan(s); seed_comms.apply(s, need, todo)          # the settings record and the two seed templates, as the seed script writes them
def turn_on(mode_word="live"):
    comms.configure(wiring.build(s, lambda: "key", {"ICDT_COMMS_MODE": mode_word}, clock=lambda: START))
def log_for(att_id):
    r = LG.list(s, {"attendance_id": att_id}, order="created_at"); assert r.ok, r.problems
    return sorted(r.data["records"], key=lambda e: (e["created_at"], e["trigger"] != "automatic"))
turn_on()
v = VS.create_with_place(s, {"name": "Louisville Library", "slug": "lou", "status": "inactive", "is_public_venue": True}, A,
                         address={"street": "951 Spruce St", "locality": "Louisville", "region": "CO", "postal_code": "80027", "country": "US"})
assert v.ok, v.problems
assert VS.update(s, v.data["id"], {"status": "active"}, A).ok
ven = v.data
def klass(slug, **kw):
    base = {"title": "Private session for Pat", "slug": slug, "class_type": "private", "program_slug": "launch", "status": "identified", "is_public": False,
            "capacity_minimum": 1, "capacity_target": 2, "capacity_max": 2}
    r = CL.create(s, {**base, **kw}, A, now=tick()); assert r.ok, r.problems; return r.data
SCHED = dict(status="scheduled", venue_id=ven["id"], starts_at="2026-11-04T01:00:00Z", time_zone="America/Denver", duration_minutes=60, is_venue_confirmed=False,
             venue_room_label=None)
SCHED.pop("venue_room_label")
sched = klass("sched", capacity_max=20, capacity_target=10, **SCHED)
idea = klass("idea")
def person(g, f="Test", **kw):
    r = IS.create(s, {"given_name": g, "family_name": f, **kw}, A, now=tick()); assert r.ok, r.problems; return r.data
pat = person("Pat", email="pat@example.com")
nomail = person("Nomail")
ins = person("Ingrid", "Teach", email="ingrid@example.com"); give_address(s, ins["id"])


# the lead instructor is placed first, so the student's email can name them
r = AT.assign(s, {"scheduled_class_id": sched["id"], "role": "primary_instructor", "order": 1, "individual_id": ins["id"]}, A, now=tick())
check("placing an instructor sends only their own assignment email (no placement confirmation)", r.ok and len(sent) == 1 and sent[0]["to"] == "ingrid@example.com" and "assigned to teach" in sent[0]["subject"], (r.problems, [m["to"] for m in sent]))
sent.clear()

r = AT.assign(s, {"scheduled_class_id": sched["id"], "role": "student", "individual_id": pat["id"]}, A, now=tick())
check("placing a student in a scheduled class sends the student one email and tells the instructor", r.ok and len(sent) == 2 and sent[0]["to"] == "pat@example.com" and sent[1]["to"] == "ingrid@example.com" and "students added" in sent[1]["subject"], (r.problems, [m["to"] for m in sent]))
m = sent[0]
check("subject has the local date and time", "Tue Nov 3, 6:00 PM" in m["subject"], m["subject"])
check("body: when, where, address, instructor", all(x in m["body"] for x in ("Tuesday, November 3, 2026, 6:00 PM to 7:00 PM MST", "Louisville Library", "951 Spruce St", "Lead instructor: Ingrid Teach")), m["body"])
check("body names the title and greets by first name", "Private session for Pat" in m["body"] and m["body"].startswith("Hello Pat,"))
check("html carries the details and a map button", "Ingrid Teach" in m["html"] and "google.com/maps/search" in m["html"] and "Open the map" in m["html"])
name, mime, data = m["att"][0]
ics = data.decode()
check("calendar file attached as text/calendar", name == "workshop.ics" and mime == "text/calendar")
check("ics has the UTC start and end", "DTSTART:20261104T010000Z" in ics and "DTEND:20261104T020000Z" in ics and ics.startswith("BEGIN:VCALENDAR\r\n") and ics.endswith("END:VCALENDAR\r\n"), ics)
check("ics has summary, location, instructor, CRLF only", "SUMMARY:Private session for Pat" in ics and "LOCATION:Louisville Library\\, 951 Spruce St\\, Louisville\\, CO 80027" in ics.replace("\r\n ", "") and "Lead instructor: Ingrid Teach" in ics.replace("\r\n ", "") and "\n" not in ics.replace("\r\n", ""), ics)
check("ics lines are folded to 75 octets", all(len(x.encode()) <= 75 for x in ics.split("\r\n")))
check("the message carries the sender name and leaves the Message-ID to the provider", m["headers"]["from_name"] == "Launch" and "message_id" not in m["headers"], m["headers"])
rec = r.data
log = log_for(rec["id"])
check("the placement is logged once", len(log) == 1, log)
e = log[0] if log else {}
check("log entry: kind, channel, to, status, reason, trigger, created_by", (e.get("kind"), e.get("channel"), e.get("to"), e.get("status"), e.get("reason"), e.get("trigger"), e.get("created_by")) == ("placement_confirmation", "email", "pat@example.com", "sent", "ok", "automatic", A), e)
check("log entry has the subject and template version, no body, and no Message-ID is forced on the provider", e.get("subject") == m["subject"] and e.get("template_version") == 1 and not e.get("message_ref") and "message_id" not in m["headers"] and not any(k in e for k in ("body", "text", "html")))
check("log entry points at the attendance, the class and the person", (e.get("attendance_id"), e.get("scheduled_class_id"), e.get("individual_id")) == (rec["id"], sched["id"], pat["id"]))
check("the attendance record no longer gets a correspondence list (retired)", "correspondence" not in AT.get(s, rec["id"]).data)
check("a client cannot write the old log field any more", ("correspondence", "not_allowed") in sorted((p["field"], p["issue"]) for p in AT.update(s, rec["id"], {"correspondence": []}, A, now=tick()).problems))

# manual send
before = len(sent)
out = AT.send_confirmation(s, rec["id"], A, now=tick())
check("manual send works (bypasses duplicate protection) and adds a second entry", out.ok and out.data["status"] == "sent" and len(sent) == before + 1 and len(log_for(rec["id"])) == 2, out.problems if not out.ok else out.data)
check("the second entry is marked as sent by hand", [x["trigger"] for x in log_for(rec["id"])] == ["automatic", "manual"])
n = len(sent)
dup = comms.notify(**__import__("launch_comms.placement_context", fromlist=["x"]).call_for(s, rec["id"], A)[0])
check("an automatic repeat is skipped as a duplicate and sends nothing", (dup.status, dup.reason) == ("skipped", "duplicate") and len(sent) == n)

# not eligible: nothing sent, nothing logged
n, nlog = len(sent), LG.list(s, {}).data["count"]
r2 = AT.assign(s, {"scheduled_class_id": idea["id"], "role": "student", "individual_id": pat["id"]}, A, now=tick())
check("an idea class (no date) sends nothing and logs nothing", r2.ok and len(sent) == n and LG.list(s, {}).data["count"] == nlog, r2.data if r2.ok else r2.problems)
x = AT.send_confirmation(s, r2.data["id"], A, now=tick())
check("manual send on an idea class says why", not x.ok and ("id", "class_not_scheduled") in sorted((p["field"], p["issue"]) for p in x.problems))
# no time zone (Todd 2026-10-23: no silent Denver): a class with no zone, in a place with none, tells nobody a time
from launch_comms import placement_context as PC, change_context as CC  # noqa: E402
check("zone_name: the class's own zone wins, then the place's, a made-up name or nothing is None",
      PC.zone_name({"time_zone": "America/Phoenix"}, {"time_zone": "America/Denver"}) == "America/Phoenix" and PC.zone_name({}, {"time_zone": "America/Indiana/Indianapolis"}) == "America/Indiana/Indianapolis"
      and PC.zone_name({"time_zone": "Mars/Base"}, {"time_zone": "America/Denver"}) is None and PC.zone_name({}, {}) is None and PC.zone_name(None, None) is None)
from crud import locations_crud as _LOCS  # noqa: E402
for _p in s.query("locations", [], limit=100):   # places now get a zone from their ZIP when saved; this check needs an older place with none
    if _p.get("time_zone"): _LOCS.update(s, _p["id"], {"time_zone": None}, A)
nozone_cls = {"id": "x", "title": "T", "starts_at": "2026-11-04T01:00:00Z", "duration_minutes": 60, "venue_id": ven["id"]}
check("a change notice is not built for a class with no zone and a place with none", CC.class_view(s, nozone_cls) is None)
check("...but is built when the class has its zone", (CC.class_view(s, {**nozone_cls, "time_zone": "America/Denver"}) or {}).get("time_zone") == "America/Denver")
r3 = AT.assign(s, {"scheduled_class_id": sched["id"], "role": "student", "individual_id": nomail["id"]}, A, now=tick())
l3 = log_for(r3.data["id"])
check("a person with no email: placed, nothing sent, and the log says not_sent / no_contact", r3.ok and len([m for m in sent if m['to'] != 'ingrid@example.com']) == len([m for m in sent[:n] if m['to'] != 'ingrid@example.com']) and [(x["status"], x["reason"], x["channel"]) for x in l3] == [("not_sent", "no_contact", "none")], l3)
x = AT.send_confirmation(s, r3.data["id"], A, now=tick())
check("manual send for no email is logged too and reported as not_sent / no_contact", x.ok and (x.data["status"], x.data["reason"]) == ("not_sent", "no_contact") and len(log_for(r3.data["id"])) == 2, x.problems if not x.ok else x.data)
x = AT.send_confirmation(s, rec["id"], "bad actor!!", now=tick())
check("bad actor refused", not x.ok)

# waitlisted student and cancelled status
w = person("Wanda", email="wanda@example.com")
n = len(sent)
r4 = AT.assign(s, {"scheduled_class_id": sched["id"], "role": "student", "individual_id": w["id"], "status": "waitlisted"}, A, now=tick())
check("a waitlisted student gets no email", r4.ok and len([m for m in sent if m['to'] != 'ingrid@example.com']) == len([m for m in sent[:n] if m['to'] != 'ingrid@example.com']) and not log_for(r4.data["id"]))
x = AT.send_confirmation(s, r4.data["id"], A, now=tick())
check("manual send on a waitlisted student says not_placed", not x.ok and ("id", "not_placed") in sorted((p["field"], p["issue"]) for p in x.problems))

# transport failures never undo the placement
b = person("Bea", email="bea@example.com")
mode[0] = "reject"
r5 = AT.assign(s, {"scheduled_class_id": sched["id"], "role": "student", "individual_id": b["id"], "status": "assigned"}, A, now=tick())
e5 = (log_for(r5.data["id"]) or [{}])[0] if r5.ok else {}
check("a rejected email still places the person, and the log says failed / adapter_error with a code", r5.ok and (e5.get("status"), e5.get("reason"), e5.get("error_code")) == ("failed", "adapter_error", "recipient_rejected"), r5.problems if not r5.ok else e5)
mode[0] = "unknown"
cy = person("Cy", email="cy@example.com")
r6 = AT.assign(s, {"scheduled_class_id": sched["id"], "role": "student", "individual_id": cy["id"]}, A, now=tick())
e6 = (log_for(r6.data["id"]) or [{}])[0] if r6.ok else {}
check("an unknown result is logged as unknown / timeout", r6.ok and (e6.get("status"), e6.get("reason")) == ("unknown", "timeout"), e6)
mode[0] = "raise"
dd = person("Dee", email="dee@example.com")
r7 = AT.assign(s, {"scheduled_class_id": sched["id"], "role": "student", "individual_id": dd["id"]}, A, now=tick())
e7 = (log_for(r7.data["id"]) or [{}])[0] if r7.ok else {}
check("a crashing provider never fails a placement and its text is never stored", r7.ok and e7.get("status") == "unknown" and "secret" not in json.dumps(e7), e7)
mode[0] = "accept"
real_notify, boom_calls = comms.notify, []
def boom(**kw): boom_calls.append(1); raise RuntimeError("secret detail")
comms.notify = boom
ee0 = person("Ed", email="ed@example.com")
r7b = AT.assign(s, {"scheduled_class_id": sched["id"], "role": "student", "individual_id": ee0["id"]}, A, now=tick())
comms.notify = real_notify
check("a crash inside the CMS call never fails a placement", r7b.ok and boom_calls)

# direct create path (not the assign window) also sends
ee = person("Eve", email="eve@example.com")
n = len(sent)
r8 = AT.create(s, {"individual_id": ee["id"], "scheduled_class_id": sched["id"], "role": "student"}, A, now=tick())
check("create (no transaction) also sends and logs", r8.ok and len(sent) == n + 1 and len(log_for(r8.data["id"])) == 1)

# the CMS not switched on: nothing happens, the button says so
comms.configure(None)
ff = person("Fay", email="fay@example.com")
n, nlog = len(sent), LG.list(s, {}).data["count"]
r9 = AT.assign(s, {"scheduled_class_id": sched["id"], "role": "student", "individual_id": ff["id"]}, A, now=tick())
check("with the CMS off, placement works and nothing is sent or logged", r9.ok and len(sent) == n and LG.list(s, {}).data["count"] == nlog)
x = AT.send_confirmation(s, r9.data["id"], A, now=tick())
check("with the CMS off, Send says it is not enabled", not x.ok and ("email", "not_enabled") in sorted((p["field"], p["issue"]) for p in x.problems))
turn_on("log_only")
gg = person("Gus", email="gus@example.com")
r10 = AT.assign(s, {"scheduled_class_id": sched["id"], "role": "student", "individual_id": gg["id"]}, A, now=tick())
check("log_only mode: nothing is sent but the try is logged skipped / log_only", r10.ok and len(sent) == n and [(x["status"], x["reason"]) for x in log_for(r10.data["id"])] == [("skipped", "log_only")])
turn_on()

# the endpoint
lim = make_failure_limiter(); ts = tick()
def call(body): return handle_admin("POST", "Bearer " + KEY, json.dumps(body).encode(), KEY, "v", s, lim, ts)
r = call({"collection": "attendances", "op": "send_confirmation", "args": {"id": rec["id"]}})
check("endpoint send_confirmation works", r.status == 200 and r.body["data"]["status"] == "sent" and r.body["data"]["reason"] == "ok" and len(log_for(rec["id"])) == 4, r.body)
r = call({"collection": "attendances", "op": "send_confirmation", "args": {"id": r4.data["id"]}})
check("endpoint refusal is a 400 with the reason", r.status == 400 and r.body["error"]["problems"][0]["issue"] == "not_placed", r.body)
r = call({"collection": "scheduled_classes", "op": "send_confirmation", "args": {"id": rec["id"]}})
check("only attendances have the operation", r.status == 400, r.body)
r = call({"collection": "communication_logs", "op": "list", "args": {"filters": {"attendance_id": rec["id"]}}})
check("the Console reads a placement's messages from the log by attendance_id", r.status == 200 and r.body["data"]["count"] == 4, r.body)

# the transport itself: the attachment travels with the message
import email as _email
from unittest import mock
class FakeSMTP:
    msgs = []
    def __init__(self, *a, **k): pass
    def set_debuglevel(self, n): pass
    def ehlo_or_helo_if_needed(self): pass
    def starttls(self, context=None): pass
    def ehlo(self): pass
    def login(self, u, k): pass
    def send_message(self, m, from_addr=None, to_addrs=None): FakeSMTP.msgs.append(m); return {}
    def close(self): pass
with mock.patch("smtplib.SMTP", FakeSMTP):
    res = T._send_once("key", "pat@example.com", "Hi", "text", "<p>html</p>", [("workshop.ics", "text/calendar", b"BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n")])
    plain = T._send_once("key", "pat@example.com", "Hi", "text", "<p>html</p>")
msg = FakeSMTP.msgs[0]
parts = [p.get_content_type() for p in msg.walk()]
check("the real transport builds a message with a calendar part", res.ok and "text/calendar" in parts and "text/plain" in parts and "text/html" in parts, parts)
check("the calendar part is an attachment named workshop.ics, method PUBLISH", any(p.get_filename() == "workshop.ics" and p.get_param("method") == "PUBLISH" for p in msg.walk()))
with mock.patch("smtplib.SMTP", FakeSMTP):
    T._send_once("key", "pat@example.com", "Hi", "text", "<p>html</p>", None, {"from_name": "Launch Team", "from_address": "hi@example.com", "reply_to": "reply@example.com", "message_id": "<abc@beetcher.com>"})
hm = FakeSMTP.msgs[2]
check("headers: from name, from address, reply-to and Message-ID are set when given", (hm["From"], hm["Reply-To"], hm["Message-ID"]) == ("Launch Team <hi@example.com>", "reply@example.com", "<abc@beetcher.com>"), (hm["From"], hm["Reply-To"], hm["Message-ID"]))
check("headers: without them the message is exactly as before", plain.ok and FakeSMTP.msgs[1]["From"] == "Launch <toddbeetcher17@gmail.com>" and FakeSMTP.msgs[1]["Reply-To"] == "toddbeetcher17@gmail.com" and FakeSMTP.msgs[1]["Message-ID"] is None)
check("a plain message (no attachment) is unchanged", plain.ok and "text/calendar" not in [p.get_content_type() for p in FakeSMTP.msgs[1].walk()])
print(f"\n{total - len(fails)}/{total} passed" + ("" if not fails else "  FAILED: " + "; ".join(fails)))
sys.exit(1 if fails else 0)
