#!/usr/bin/env python3
"""In-memory tests for the completion link (request_completion.py): the token, GET, POST, the locks, and the Console staying blind to the token.
Run from enjoy_router/:  python3 run_completion_tests.py   (-v lists every check). Nothing touches Firebase."""
import json, pathlib, sys, uuid
from datetime import datetime, timedelta, timezone
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from core import Schemas, handle_registration_request  # noqa: E402
from crud import attendances_service as AT, individuals_service as IS, scheduled_classes_crud as CL  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from memory_store import MemoryStore  # noqa: E402
from ratelimit import RateLimiter  # noqa: E402
import request_completion as RC  # noqa: E402
import console as CON  # noqa: E402

NOW = datetime(2026, 10, 14, 18, 0, 0, tzinfo=timezone.utc)
fails, total = [], 0
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    if not ok or "-v" in sys.argv: print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")

schemas = Schemas.load()
reg_store = MemoryStore([])
ds = MemoryDocStore("")
limiter = RateLimiter(rules=((600, 1000),))
def body(email="sam@example.com", **kw):
    b = {"registration_type": "private", "idempotency_key": str(uuid.uuid4()), "first_name": "Sam", "last_name": "Test", "email": email,
         "consent_to_contact": True, "presented_cost_cents": 50000, "presented_cost_basis": "per_session", "duration_minutes_requested": 120}
    b.update(kw); return b
def make(**kw):
    r = handle_registration_request(body(**kw), reg_store, schemas, now=NOW)
    assert r.outcome == "created", (r.error_code, r.field_errors)
    ds.create(RC.COLLECTION, r.doc["id"], dict(r.doc))
    return r
def call(method, params=None, payload=None, now=NOW):
    raw = json.dumps(payload).encode() if payload is not None else b""
    return RC.handle_completion(method, params or {}, raw, "visitor", ds, schemas, limiter, now)
def post(token, changes, **extra): return call("POST", payload={"t": token, "changes": changes, **extra})
def stored(r): return ds.get(RC.COLLECTION, r.doc["id"])

# ---- the token
r = make()
tok = r.doc["completion_token"]
check("a saved request carries a 43-character token", isinstance(tok, str) and len(tok) == 43 and RC.TOKEN.match(tok))
check("the reply to the page carries no token", "completion_token" not in json.dumps(r.envelope), r.envelope)
check("two requests get two different tokens", make(email="b@example.com").doc["completion_token"] != tok)
bad = handle_registration_request(body(completion_token="x" * 43), reg_store, schemas, now=NOW)
check("a browser cannot set the token", bad.outcome == "rejected" and any(f["field"] == "completion_token" for f in bad.envelope["error"].get("field_errors", [])), bad.envelope)

# ---- GET
g = call("GET", {"t": tok})
d = g.body.get("data", {})
check("GET with the token shows the answers", g.status == 200 and d["confirmation_number"] == r.doc["confirmation_number"] and d["answers"]["first_name"] == "Sam" and d["answers"]["email"] == "sam@example.com", g.body)
check("the answers include the duration but never the token, the key or server fields", d["answers"].get("duration_minutes_requested") == 120 and not any(k in d["answers"] for k in ("completion_token", "idempotency_key", "id", "processing_status", "created_at")), d)
check("a fresh request is editable", d["editable"] is True)
check("GET is not cached", g.headers.get("Cache-Control") == "no-store")
for label, t in (("no token", None), ("a short token", "abc"), ("a wrong token", "A" * 43), ("a token of the wrong shape", "!" * 43)):
    check(f"GET with {label}: not found", call("GET", {"t": t}).status == 404)
grp = handle_registration_request({**body(), "registration_type": "group", "attendee_count": 3, "is_requester_attending": True, "has_minors_present": False, "location_type": "off_site"}, reg_store, schemas, now=NOW)
if grp.outcome == "created":
    ds.create(RC.COLLECTION, grp.doc["id"], dict(grp.doc))
    check("a group request's token does not open anything (private only in M1)", call("GET", {"t": grp.doc["completion_token"]}).status == 404)
check("other methods are refused", call("PUT").status == 405)

# ---- POST
before = len(ds.query(RC.COLLECTION, [], limit=500))
u = post(tok, {"attendee_count": 2, "what_they_want": "Learn to use ChatGPT", "postal_code": "80026", "is_requester_attending": True})
check("POST fills in optional details", u.status == 200 and u.body["data"]["updated"] is True, u.body)
s = stored(r)
check("the details are saved on the same request", s["attendee_count"] == 2 and s["what_they_want"] == "Learn to use ChatGPT" and s["postal_code"] == "80026", s)
check("no second request was made", len(ds.query(RC.COLLECTION, [], limit=500)) == before)
check("confirmation number, name and email are unchanged", s["confirmation_number"] == r.doc["confirmation_number"] and s["email"] == "sam@example.com" and s["first_name"] == "Sam")
check("updated_by says it came through the link", s["updated_by"] == "web:completion" and s["updated_at"] >= r.doc["updated_at"])
g = call("GET", {"t": tok}).body["data"]["answers"]
check("GET now shows what was filled in", g["postal_code"] == "80026" and g["attendee_count"] == 2)

for k, v in (("email", "x@example.com"), ("first_name", "Z"), ("registration_type", "group"), ("consent_to_contact", False), ("scheduled_class_id", str(uuid.uuid4())), ("completion_token", "x" * 43), ("confirmation_number", "ICDT-AAAAAA")):
    u = post(tok, {k: v})
    check(f"the link cannot change {k}", u.status == 400 and any(f["field"] == k and f["issue"] == "not_allowed" for f in u.body["error"]["field_errors"]), u.body)
check("and nothing changed", stored(r)["email"] == "sam@example.com" and stored(r)["registration_type"] == "private")
u = post(tok, {"postal_code": "9021"})
check("a ZIP that is not five digits is refused with the field named", u.status == 400 and any(f["field"] == "postal_code" for f in u.body["error"]["field_errors"]), u.body)
u = post(tok, {"postal_code": "90210"})
check("a ZIP in another state is accepted and stored", u.status == 200 and stored(r)["postal_code"] == "90210", u.body)
u = post(tok, {"requested_date": "2026-10-01"})
check("a date in the past is refused", u.status == 400 and any(f["field"] == "requested_date" for f in u.body["error"]["field_errors"]), u.body)
u = post(tok, {"requested_date": "2026-11-05", "requested_time_of_day": "morning"})
check("a future date is accepted", u.status == 200 and stored(r)["requested_date"] == "2026-11-05")
u = post(tok, {"attendee_count": 1, "participants": [{"first_name": "A", "last_name": "B", "age_band": "adult"}, {"first_name": "C", "last_name": "D", "age_band": "adult"}]})
check("more people named than the headcount is refused", u.status == 400, u.body)
u = post(tok, {"preferred_venue_id": str(uuid.uuid4())})
check("an unknown venue is refused", u.status == 404 and u.body["error"]["code"] == "venue_not_found", u.body)
u = post(tok, {"curriculum_id": str(uuid.uuid4())})
check("an unknown curriculum is refused", u.status == 404 and u.body["error"]["code"] == "curriculum_not_found", u.body)
vid, cid = str(uuid.uuid4()), str(uuid.uuid4())
ds.create("venues", vid, {"id": vid, "status": "active", "is_public_venue": True})
ds.create("curriculums", cid, {"id": cid, "status": "active"})
u = post(tok, {"preferred_venue_id": vid, "curriculum_id": cid})
check("a real public venue and an active curriculum are accepted", u.status == 200 and stored(r)["preferred_venue_id"] == vid and stored(r)["curriculum_id"] == cid, u.body)
u = post(tok, {"what_they_want": None})
check("null clears an answer", u.status == 200 and "what_they_want" not in stored(r), u.body)
u = post(tok, {})
check("nothing to change is a quiet no-op", u.status == 200 and u.body["data"]["updated"] is False)
u = post(tok, {"notes": "hello"}, website="http://spam")
check("the honeypot looks successful and changes nothing", u.status == 200 and "notes" not in stored(r))
check("a wrong token on POST is not found", post("B" * 43, {"notes": "x"}).status == 404)
check("a body that is not an object is refused", call("POST", payload=[1]).status == 400)

# ---- locked once placed in a class
ind = IS.create(ds, {"given_name": "Sam", "family_name": "Test"}, "user:admin", now=NOW).data
cls = CL.create(ds, {"title": "Private session", "slug": "p1", "class_type": "private", "program_slug": "launch", "status": "identified", "is_public": False,
                     "capacity_minimum": 1, "capacity_target": 2, "capacity_max": 2}, "user:admin", now=NOW).data
att = AT.create(ds, {"individual_id": ind["id"], "scheduled_class_id": cls["id"], "role": "student", "request_id": r.doc["id"]}, "user:admin", now=NOW)
assert att.ok, att.problems
check("placed in a class: GET says not editable", call("GET", {"t": tok}).body["data"]["editable"] is False)
u = post(tok, {"notes": "too late"})
check("placed in a class: POST is refused as already scheduled", u.status == 409 and u.body["error"]["code"] == "already_scheduled" and "notes" not in stored(r), u.body)
AT.update(ds, att.data["id"], {"status": "withdrawn"}, "user:admin", now=NOW)
check("if the placement is withdrawn the link works again", call("GET", {"t": tok}).body["data"]["editable"] is True and post(tok, {"notes": "back"}).status == 200)

# ---- deleted request, rate limit, Console, email
ds.update(RC.COLLECTION, r.doc["id"], {"deleted_at": "2026-10-14T19:00:00Z"})
check("a removed request's link stops working", call("GET", {"t": tok}).status == 404)
tight = RateLimiter(rules=((600, 2),))
codes = [RC.handle_completion("GET", {"t": "A" * 43}, b"", "v2", ds, schemas, tight, NOW).status for _ in range(3)]
check("rate limited after too many tries", codes == [404, 404, 429], codes)
recs = CON.list_registration_requests(reg_store, 50)
check("the Console list never carries the token", recs and not any("completion_token" in x for x in recs))
check("the store still has it", all("completion_token" in x for x in reg_store.list_requests(50)))

sent = []
import smtp_transport
import comms, seed_comms
from crud.memory_doc_store import MemoryDocStore as _MDS
from launch_comms import request_context, wiring
smtp_transport.transport = lambda key, to, subject, text, html=None, attachments=None, headers=None: sent.append((text, html)) or smtp_transport.SendResult(True, "accepted")
cs = _MDS(""); need, todo = seed_comms.plan(cs); seed_comms.apply(cs, need, todo)
comms.configure(wiring.build(cs, lambda: "k", {"ICDT_COMMS_MODE": "live"}))
LINK = "https://beetcher.com/enjoy/register/private/?r=" + tok
base_doc = {"id": "6c5e1f4b-0d7a-4b82-8e9d-4f5a6b7c8d9e", "first_name": "Sam", "last_name": "Test", "email": "sam@example.com", "confirmation_number": "ICDT-ABCDEF"}
comms.notify(**request_context.call_for({**base_doc, "registration_type": "private", "completion_token": tok}))
comms.notify(**request_context.call_for({**base_doc, "id": "7c5e1f4b-0d7a-4b82-8e9d-4f5a6b7c8d9e", "registration_type": "private"}))
comms.configure(None)
check("the email carries the link as a button and as plain text", LINK in sent[0][0] and LINK in sent[0][1] and "Finish your request" in sent[0][1] and "ICDT-ABCDEF" in sent[0][0])
check("with no link the email is as before", "Finish your request" not in sent[1][1] and "https://" not in sent[1][0] and "ICDT-ABCDEF" in sent[1][0])

print(f"\n{total - len(fails)}/{total} checks passed" + (" OK" if not fails else "  FAILED: " + "; ".join(fails)))
sys.exit(1 if fails else 0)
