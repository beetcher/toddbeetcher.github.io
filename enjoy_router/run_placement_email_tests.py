#!/usr/bin/env python3
"""In-memory tests for the placement confirmation email (placement_email.py) and the attendance correspondence log.
A fake transport stands in for Brevo: nothing is sent. Run from enjoy_router/:  python3 run_placement_email_tests.py  (-v lists every check)."""
import json, pathlib, sys, re
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import smtp_transport as T  # noqa: E402
import placement_email as PE  # noqa: E402
from crud import attendances_service as AT  # noqa: E402
from crud import individuals_service as IS  # noqa: E402
from crud import scheduled_classes_crud as CL  # noqa: E402
from crud import venues_service as VS  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud_endpoint import handle_admin, make_failure_limiter  # noqa: E402
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
def fake(key, to, subject, body, html=None, attachments=None):
    sent.append({"to": to, "subject": subject, "body": body, "html": html, "att": attachments})
    return {"accept": T.SendResult(True, "accepted"), "reject": T.SendResult(False, "recipient_rejected"), "unknown": T.SendResult(False, "unknown")}[mode[0]]
T.transport = fake
AT.notify = lambda store, id, actor, now, manual: PE.send_for(store, id, actor, "key", now, manual)

s = MemoryDocStore("")
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
check("placing an instructor sends nothing", r.ok and not sent, r.problems)

r = AT.assign(s, {"scheduled_class_id": sched["id"], "role": "student", "individual_id": pat["id"]}, A, now=tick())
check("placing a student in a scheduled class sends one email", r.ok and len(sent) == 1 and sent[0]["to"] == "pat@example.com", (r.problems, sent))
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
rec = r.data
log = rec.get("correspondence") or []
check("the placement returns the record with one log line", len(log) == 1, log)
e = log[0] if log else {}
check("log line: kind, channel, to, result, trigger, by", (e.get("kind"), e.get("channel"), e.get("to"), e.get("result"), e.get("trigger"), e.get("by")) == ("placement_confirmation", "email", "pat@example.com", "sent", "automatic", A), e)
check("log line has the subject and a time but no body", e.get("subject") == m["subject"] and e.get("at") and not any(k in e for k in ("body", "text", "html")))
check("the stored record validates (log is a legal read-only field)", AT.get(s, rec["id"]).data.get("correspondence") == log)
check("a client cannot write the log", ("correspondence", "not_allowed") in sorted((p["field"], p["issue"]) for p in AT.update(s, rec["id"], {"correspondence": []}, A, now=tick()).problems))
check("a client cannot create with a log", not AT.create(s, {"individual_id": nomail["id"], "scheduled_class_id": idea["id"], "role": "student", "correspondence": []}, A, now=tick()).ok)

# manual send
before = len(sent)
out = AT.send_confirmation(s, rec["id"], A, now=tick())
check("manual send works and adds a second line", out.ok and len(sent) == before + 1 and len(out.data["correspondence"]) == 2 and out.data["correspondence"][1]["trigger"] == "manual", out.problems if not out.ok else out.data)
check("the log keeps oldest first", [x["trigger"] for x in AT.get(s, rec["id"]).data["correspondence"]] == ["automatic", "manual"])

# not eligible: nothing sent, no log line
n = len(sent)
r2 = AT.assign(s, {"scheduled_class_id": idea["id"], "role": "student", "individual_id": pat["id"]}, A, now=tick())
check("an idea class (no date) sends nothing and logs nothing", r2.ok and len(sent) == n and not r2.data.get("correspondence"), r2.data if r2.ok else r2.problems)
x = AT.send_confirmation(s, r2.data["id"], A, now=tick())
check("manual send on an idea class says why", not x.ok and ("id", "class_not_scheduled") in sorted((p["field"], p["issue"]) for p in x.problems))
r3 = AT.assign(s, {"scheduled_class_id": sched["id"], "role": "student", "individual_id": nomail["id"]}, A, now=tick())
check("a person with no email: placed, nothing sent", r3.ok and len(sent) == n and not r3.data.get("correspondence"))
x = AT.send_confirmation(s, r3.data["id"], A, now=tick())
check("manual send for no email says no_email", not x.ok and ("id", "no_email") in sorted((p["field"], p["issue"]) for p in x.problems))
x = AT.send_confirmation(s, rec["id"], "bad actor!!", now=tick())
check("bad actor refused", not x.ok)

# waitlisted student and cancelled status
w = person("Wanda", email="wanda@example.com")
n = len(sent)
r4 = AT.assign(s, {"scheduled_class_id": sched["id"], "role": "student", "individual_id": w["id"], "status": "waitlisted"}, A, now=tick())
check("a waitlisted student gets no email", r4.ok and len(sent) == n)
x = AT.send_confirmation(s, r4.data["id"], A, now=tick())
check("manual send on a waitlisted student says not_placed", not x.ok and ("id", "not_placed") in sorted((p["field"], p["issue"]) for p in x.problems))

# transport failures never undo the placement
b = person("Bea", email="bea@example.com")
mode[0] = "reject"
r5 = AT.assign(s, {"scheduled_class_id": sched["id"], "role": "student", "individual_id": b["id"], "status": "assigned"}, A, now=tick())
e5 = (r5.data.get("correspondence") or [{}])[0] if r5.ok else {}
check("a rejected email still places the person, and the log says failed with a code", r5.ok and e5.get("result") == "failed" and e5.get("error_code") == "recipient_rejected", r5.problems if not r5.ok else e5)
mode[0] = "unknown"
cy = person("Cy", email="cy@example.com")
r6 = AT.assign(s, {"scheduled_class_id": sched["id"], "role": "student", "individual_id": cy["id"]}, A, now=tick())
e6 = (r6.data.get("correspondence") or [{}])[0] if r6.ok else {}
check("an unknown result is logged as unknown", r6.ok and e6.get("result") == "unknown", e6)
mode[0] = "accept"
boom_calls = []
def boom(*a): boom_calls.append(1); raise RuntimeError("secret detail")
AT.notify = boom
dd = person("Dee", email="dee@example.com")
r7 = AT.assign(s, {"scheduled_class_id": sched["id"], "role": "student", "individual_id": dd["id"]}, A, now=tick())
check("a crashing sender never fails a placement", r7.ok and boom_calls)
AT.notify = lambda store, id, actor, now, manual: PE.send_for(store, id, actor, "key", now, manual)

# direct create path (not the assign window) also sends
ee = person("Eve", email="eve@example.com")
n = len(sent)
r8 = AT.create(s, {"individual_id": ee["id"], "scheduled_class_id": sched["id"], "role": "student"}, A, now=tick())
check("create (no transaction) also sends and returns the log", r8.ok and len(sent) == n + 1 and len(r8.data.get("correspondence", [])) == 1)

# email turned off: nothing happens, the button says so
AT.notify = None
ff = person("Fay", email="fay@example.com")
n = len(sent)
r9 = AT.assign(s, {"scheduled_class_id": sched["id"], "role": "student", "individual_id": ff["id"]}, A, now=tick())
check("with email off, placement works and nothing is sent", r9.ok and len(sent) == n and not r9.data.get("correspondence"))
x = AT.send_confirmation(s, r9.data["id"], A, now=tick())
check("with email off, Send says it is not enabled", not x.ok and ("email", "not_enabled") in sorted((p["field"], p["issue"]) for p in x.problems))
AT.notify = lambda store, id, actor, now, manual: PE.send_for(store, id, actor, "key", now, manual)

# the endpoint
lim = make_failure_limiter(); ts = tick()
def call(body): return handle_admin("POST", "Bearer " + KEY, json.dumps(body).encode(), KEY, "v", s, lim, ts)
r = call({"collection": "attendances", "op": "send_confirmation", "args": {"id": rec["id"]}})
check("endpoint send_confirmation works", r.status == 200 and r.body["data"]["result"] == "sent" and len(r.body["data"]["correspondence"]) == 3, r.body)
r = call({"collection": "attendances", "op": "send_confirmation", "args": {"id": r4.data["id"]}})
check("endpoint refusal is a 400 with the reason", r.status == 400 and r.body["error"]["problems"][0]["issue"] == "not_placed", r.body)
r = call({"collection": "scheduled_classes", "op": "send_confirmation", "args": {"id": rec["id"]}})
check("only attendances have the operation", r.status == 400, r.body)

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
check("a plain message (no attachment) is unchanged", plain.ok and "text/calendar" not in [p.get_content_type() for p in FakeSMTP.msgs[1].walk()])
print(f"\n{total - len(fails)}/{total} passed" + ("" if not fails else "  FAILED: " + "; ".join(fails)))
sys.exit(1 if fails else 0)
