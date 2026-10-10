#!/usr/bin/env python3
"""In-memory tests for registration assignments: the handler file, the assignments service (auto decision,
rules, supersede chain, counts), suggest/queue, and the class guards. Run from enjoy_router/:
    python3 run_assignment_tests.py [-v]
Nothing here touches Firebase."""
import copy
import pathlib
import sys
import uuid
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import assignments_service as S  # noqa: E402
from crud import classes_service as CS  # noqa: E402
from crud import registration_assignments_crud as A  # noqa: E402
from crud import scheduled_classes_crud as C  # noqa: E402
from crud import venues_crud as V  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402

START = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
fails: list = []
total = 0


def check(label, ok, detail=""):
    global total
    total += 1
    if not ok:
        fails.append(label)
    if not ok or "-v" in sys.argv:
        print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")


def pairs(problems):
    return sorted(f"{p['field']}:{p['issue']}" for p in problems)


clock = [0]


def tick():
    clock[0] += 5
    return START + timedelta(seconds=clock[0])


VENUE = {"name": "Library", "slug": "library", "status": "active", "is_public_venue": True,
         "street_address": "1 Main St", "city": "Boulder", "state_region": "CO", "postal_code": "80302", "country": "US",
         "time_zone": "America/Denver", "contact_name": "Pat", "contact_email": "pat@example.com",
         "is_accessible": True, "allows_minors": True, "allows_animals": False,
         "rooms": [{"label": "Main room", "max_occupancy": 40}]}


class World:
    """A store with one active venue, helpers to add classes and requests."""
    def __init__(self):
        self.s = MemoryDocStore("test_")
        self.venue = V.create(self.s, copy.deepcopy(VENUE), "user:t", now=tick()).data
        self.n = 0

    def klass(self, target=4, mx=6, waitlist=False, wl_max=None, status="enrolling", slug=None, source_request_id=None, ctype="workshop"):
        self.n += 1
        d = {"title": f"Class {self.n}", "slug": slug or f"class_{self.n}", "class_type": ctype, "program_slug": "launch",
             "status": status, "is_public": True, "capacity_minimum": min(2, target), "capacity_target": target, "capacity_max": mx,
             "starts_at": "2026-11-21T01:00:00Z", "time_zone": "America/Denver", "duration_minutes": 120,
             "venue_id": self.venue["id"], "is_venue_confirmed": True, "price_cents": 5000, "price_basis": "per_person",
             "is_waitlist_enabled": waitlist}
        if wl_max is not None:
            d["waitlist_max"] = wl_max
        r = CS.create(self.s, d, "user:t", now=tick())
        assert r.ok, r.problems
        if source_request_id:  # server-set by the (future) request-processing service, so seed it directly
            self.s.data["test_scheduled_classes"][r.data["id"]]["source_request_id"] = source_request_id
            return self.s.data["test_scheduled_classes"][r.data["id"]]
        return r.data

    def request(self, seats=2, rtype="class", class_id=None, no_fit=False):
        self.n += 1
        rid = str(uuid.uuid4())
        doc = {"id": rid, "registration_type": rtype, "attendee_count": seats, "confirmation_number": f"ICDT-{self.n:06d}",
               "first_name": "Ann", "last_name": f"Tester{self.n}", "email": "a@example.com",
               "created_at": (START + timedelta(seconds=self.n)).strftime("%Y-%m-%dT%H:%M:%SZ"), "processing_status": "not_processed"}
        if class_id:
            doc["scheduled_class_id"] = class_id
        if no_fit:
            doc["no_class_fits"] = True
        self.s.data.setdefault("test_registration_requests", {})[rid] = doc
        return doc

    def assign(self, req, cls, **extra):
        return S.create(self.s, {"request_id": req["id"], "scheduled_class_id": cls["id"], **extra}, "user:todd", now=tick())

    def counts(self, cls):
        c = C.get(self.s, cls["id"]).data
        return c["registered_count"], c["waitlist_count"]


# ---------------------------------------------------------------------------
# 1. Handler alone: schema checks, server stamps, own rules
# ---------------------------------------------------------------------------
w = World()
cls, req = w.klass(), w.request()
ok_data = {"request_id": req["id"], "scheduled_class_id": cls["id"], "status": "accepted", "attendee_count": 2}
h = A.create(w.s, dict(ok_data), "user:todd", now=tick(), server_fields={"program_slug": "launch"})
check("handler: create ok", h.ok, str(h.problems))
d = h.data
check("handler: decided_at/decided_by/stamps set", d["decided_by"] == "user:todd" and d["decided_at"] == d["created_at"]
      and d["schema_version"] == 1 and d["source"] == "dashboard" and d["program_slug"] == "launch")
check("handler: stored the same record", w.s.data["test_registration_assignments"][d["id"]] == d)
for field in ("request_id", "scheduled_class_id", "status", "attendee_count"):
    bad = dict(ok_data)
    del bad[field]
    check(f"handler: {field} required", pairs(A.create(w.s, bad, "user:t", now=tick(), server_fields={"program_slug": "launch"}).problems) == [f"{field}:required"])
check("handler: bad status word", pairs(A.create(w.s, {**ok_data, "status": "yes"}, "user:t", server_fields={"program_slug": "launch"}).problems) == ["status:invalid_value"])
check("handler: seats 0 and 51 refused", all(pairs(A.create(w.s, {**ok_data, "attendee_count": n}, "user:t", server_fields={"program_slug": "launch"}).problems) == ["attendee_count:out_of_range"] for n in (0, 51)))
check("handler: bad request id format", pairs(A.create(w.s, {**ok_data, "request_id": "abc"}, "user:t", server_fields={"program_slug": "launch"}).problems) == ["request_id:invalid_format"])
check("handler: unknown field refused", pairs(A.create(w.s, {**ok_data, "colour": "red"}, "user:t", server_fields={"program_slug": "launch"}).problems) == ["colour:not_allowed"])
for f in ("decided_at", "decided_by", "program_slug", "previous_id", "id", "created_at"):
    check(f"handler: sender cannot set {f}", f"{f}:not_allowed" in pairs(A.create(w.s, {**ok_data, f: "x"}, "user:t", server_fields={"program_slug": "launch"}).problems))
check("handler: note longer than 2000 refused", pairs(A.create(w.s, {**ok_data, "decision_note": "x" * 2001}, "user:t", server_fields={"program_slug": "launch"}).problems) == ["decision_note:out_of_range"])
check("handler: note trimmed, empty note dropped", A.create(w.s, {**ok_data, "decision_note": "  hi  "}, "user:t", server_fields={"program_slug": "launch"}).data["decision_note"] == "hi"
      and "decision_note" not in A.create(w.s, {**ok_data, "decision_note": "   "}, "user:t", server_fields={"program_slug": "launch"}).data)
check("handler: without program_slug it is our bug (server_error)", A.create(w.s, dict(ok_data), "user:t").code == "server_error")
check("handler: a service may not pass other server fields", A.create(w.s, dict(ok_data), "user:t", server_fields={"id": "x"}).code == "server_error")
check("handler: bad actor", pairs(A.create(w.s, dict(ok_data), "todd", server_fields={"program_slug": "launch"}).problems) == ["actor:invalid_format"])
check("handler: problems carry no values", all(set(p) == {"field", "issue"} for p in A.create(w.s, {"status": "x"}, "user:t").problems))

# update: only note / transaction ids
u = A.update(w.s, d["id"], {"decision_note": "Called her"}, "user:todd", d["updated_at"], now=tick())
check("handler: note updates", u.ok and A.get(w.s, d["id"]).data["decision_note"] == "Called her")
for f in ("status", "attendee_count", "request_id", "scheduled_class_id"):
    check(f"handler: {f} immutable", pairs(A.update(w.s, d["id"], {f: "accepted" if f == "status" else 1}, "user:t", now=tick()).problems) == [f"{f}:immutable"])
check("handler: read-only field refused on update", pairs(A.update(w.s, d["id"], {"decided_by": "user:x"}, "user:t").problems) == ["decided_by:not_allowed"])
check("handler: stale expected_updated_at -> conflict (simple path)", A.update(w.s, d["id"], {"decision_note": "x"}, "user:t", "2000-01-01T00:00:00Z", now=tick()).code == "conflict")
check("handler: unknown id on update -> not_found", A.update(w.s, str(uuid.uuid4()), {"decision_note": "x"}, "user:t").code == "not_found")
check("handler: removing the note works", A.update(w.s, d["id"], {"decision_note": ""}, "user:t", now=tick()).ok and "decision_note" not in A.get(w.s, d["id"]).data)
check("handler: transaction ids bad format", pairs(A.update(w.s, d["id"], {"transaction_record_ids": ["x"]}, "user:t").problems) == ["transaction_record_ids:invalid_format"])
# get / list / delete
check("handler: get unknown -> not_found, bad id -> invalid_format", A.get(w.s, str(uuid.uuid4())).code == "not_found" and pairs(A.get(w.s, "x").problems) == ["id:invalid_format"])
lst = A.list(w.s, {"request_id": req["id"]})
check("handler: list by request", lst.ok and lst.data["count"] >= 1)
check("handler: list two filters refused", pairs(A.list(w.s, {"status": "accepted", "request_id": req["id"]}).problems) == ["request_id:not_supported", "status:not_supported"])
check("handler: list unknown filter / order refused", pairs(A.list(w.s, {"colour": 1}).problems) == ["colour:not_supported"] and pairs(A.list(w.s, order="title").problems) == ["order:not_supported"])
check("handler: list bad status value", pairs(A.list(w.s, {"status": "yes"}).problems) == ["status:invalid_value"])
sd = A.soft_delete(w.s, d["id"], "user:todd", now=tick())
check("handler: soft delete keeps record with who/when", sd.ok and "deleted_at" in w.s.data["test_registration_assignments"][d["id"]]
      and w.s.data["test_registration_assignments"][d["id"]]["deleted_by"] == "user:todd")
check("handler: deleted record leaves list and get; second delete not_found", A.get(w.s, d["id"]).code == "not_found" and A.soft_delete(w.s, d["id"], "user:t").code == "not_found")
check("handler: get include_deleted", A.get(w.s, d["id"], True).ok)

# ---------------------------------------------------------------------------
# 2. Service: automatic decision
# ---------------------------------------------------------------------------
w = World()
cls = w.klass(target=4, mx=6, waitlist=True, wl_max=3)
r1, r2, r3, r4, r5 = [w.request(2) for _ in range(5)]
a1 = w.assign(r1, cls)
check("auto: first party accepted", a1.ok and a1.data["status"] == "accepted" and a1.data["attendee_count"] == 2, str(a1.problems))
check("auto: program_slug copied from class", a1.data["program_slug"] == "launch")
check("auto: counts 2/0", w.counts(cls) == (2, 0))
a2 = w.assign(r2, cls)
check("auto: second party fills target -> accepted", a2.data["status"] == "accepted" and w.counts(cls) == (4, 0))
a3 = w.assign(r3, cls)
check("auto: next party lands in overflow", a3.data["status"] == "overflow" and w.counts(cls) == (6, 0))
a4 = w.assign(r4, cls)
check("auto: over max -> waitlisted", a4.data["status"] == "waitlisted" and w.counts(cls) == (6, 2))
a5 = w.assign(r5, cls)
check("auto: waitlist cap (3 seats) would be passed -> conflict status:waitlist_full", a5.code == "conflict" and pairs(a5.problems) == ["status:waitlist_full"], str(a5))
check("auto: refusal wrote nothing, counts unchanged", len(w.s.data["test_registration_assignments"]) == 4 and w.counts(cls) == (6, 2))
w3 = World()
c3 = w3.klass(target=4, mx=6, waitlist=False)
p = [w3.request(3) for _ in range(3)]
x = [w3.assign(q, c3) for q in p]
check("auto: 3 seats accepted, then straddling party goes to overflow whole", x[0].data["status"] == "accepted" and x[1].data["status"] == "overflow" and w3.counts(c3) == (6, 0))
check("auto: no waitlist -> class_full conflict", x[2].code == "conflict" and pairs(x[2].problems) == ["status:class_full"])
w4 = World()
c4 = w4.klass(status="scheduled")
check("auto: class not enrolling -> class_closed", pairs(w4.assign(w4.request(1), c4).problems) == ["status:class_closed"])
check("auto: refusal code is conflict (409)", w4.assign(w4.request(1), c4).code == "conflict")

# ---------------------------------------------------------------------------
# 3. Service: rules
# ---------------------------------------------------------------------------
w = World()
cls = w.klass()
req = w.request(2)
check("rule: unknown request -> request_id:not_found", pairs(S.create(w.s, {"request_id": str(uuid.uuid4()), "scheduled_class_id": cls["id"]}, "user:t", now=tick()).problems) == ["request_id:not_found"])
check("rule: unknown class -> scheduled_class_id:not_found", pairs(S.create(w.s, {"request_id": req["id"], "scheduled_class_id": str(uuid.uuid4())}, "user:t", now=tick()).problems) == ["scheduled_class_id:not_found"])
dead = w.klass()
CS.soft_delete(w.s, dead["id"], "user:t", now=tick())
check("rule: deleted class counts as not found", pairs(w.assign(req, dead).problems) == ["scheduled_class_id:not_found"])
check("rule: seats above the request's count refused", pairs(w.assign(req, cls, attendee_count=3).problems) == ["attendee_count:out_of_range"])
part = w.assign(req, cls, attendee_count=1)
check("rule: fewer seats than asked is fine", part.ok and part.data["attendee_count"] == 1)
check("rule: bad ids go to the handler's field errors", pairs(S.create(w.s, {"request_id": "x", "scheduled_class_id": "y", "status": "accepted", "attendee_count": 1}, "user:t").problems) == ["request_id:invalid_format", "scheduled_class_id:invalid_format"])
check("rule: non-dict body", pairs(S.create(w.s, "x", "user:t").problems) == ["body:invalid_type"])
check("rule: seats not a number -> handler reports it", pairs(S.create(w.s, {"request_id": req["id"], "scheduled_class_id": cls["id"], "attendee_count": "2", "status": "accepted"}, "user:t").problems) == ["attendee_count:invalid_type"])
# private/group go only into the class made from them
w = World()
preq = w.request(3, rtype="private")
made = w.klass(source_request_id=preq["id"], ctype="private")
other = w.klass()
check("rule: private request into another class -> wrong_class", pairs(w.assign(preq, other).problems) == ["scheduled_class_id:wrong_class"])
check("rule: private request into its own class ok", w.assign(preq, made).ok)
greq = w.request(4, rtype="group")
check("rule: group request into a workshop -> wrong_class", pairs(w.assign(greq, other).problems) == ["scheduled_class_id:wrong_class"])
# a person's chosen status
w = World()
cls = w.klass(target=4, mx=6, waitlist=False)
a, b, c = w.request(3), w.request(3), w.request(2)
check("manual: accepted within target ok", w.assign(a, cls, status="accepted").ok)
check("manual: accepted over target -> over_target", pairs(w.assign(b, cls, status="accepted").problems) == ["status:over_target"])
check("manual: overflow within max ok", w.assign(b, cls, status="overflow").ok)
check("manual: overflow over max -> class_full", pairs(w.assign(c, cls, status="overflow").problems) == ["status:class_full"])
check("manual: waitlisted with waitlist off -> waitlist_off", pairs(w.assign(c, cls, status="waitlisted").problems) == ["status:waitlist_off"])
check("manual: declined always allowed", w.assign(c, cls, status="declined").ok)
cl = w.klass(status="scheduled")
d1 = w.request(1)
check("manual: accepted on a closed class -> class_closed", pairs(w.assign(d1, cl, status="accepted").problems) == ["status:class_closed"])
check("manual: declined on a closed class allowed", w.assign(d1, cl, status="declined").ok)
check("manual: bad status word reaches the handler", pairs(w.assign(d1, cl, status="maybe").problems) == ["status:invalid_value"])

# ---------------------------------------------------------------------------
# 4. Supersede chain and counts
# ---------------------------------------------------------------------------
w = World()
cls = w.klass(target=4, mx=6, waitlist=True)
r1, r2, r3 = w.request(3), w.request(3), w.request(2)
x1 = w.assign(r1, cls).data
x2 = w.assign(r2, cls).data
check("chain: 3 accepted, 3 overflow -> counts 6/0", (x1["status"], x2["status"]) == ("accepted", "overflow") and w.counts(cls) == (6, 0))
x3 = w.assign(r3, cls).data
check("chain: third waitlisted -> 6/2", x3["status"] == "waitlisted" and w.counts(cls) == (6, 2))
same = w.assign(r3, cls)
check("chain: identical decision refused (status:unchanged)", pairs(same.problems) == ["status:unchanged"])
canc = w.assign(r1, cls, status="cancelled")
check("chain: cancel writes a NEW record linked by previous_id", canc.ok and canc.data["previous_id"] == x1["id"] and canc.data["id"] != x1["id"])
check("chain: the old record is untouched", w.s.data["test_registration_assignments"][x1["id"]]["status"] == "accepted")
check("chain: counts drop to 3/2 after the cancel", w.counts(cls) == (3, 2))
promote = w.assign(r3, cls)  # the server re-decides: now 3 + 2 fits under the target
check("chain: re-deciding the waitlisted party promotes it (3 seats taken + 2 passes the target -> overflow) and links", promote.ok and promote.data["status"] == "overflow" and promote.data["previous_id"] == x3["id"], str(promote.problems))
check("chain: counts 5/0", w.counts(cls) == (5, 0))
cur = A.current_only(A.for_class(w.s, cls["id"]))
check("chain: current set = r1 cancelled, r2 overflow, r3 overflow", sorted((d["status"]) for d in cur) == ["cancelled", "overflow", "overflow"])
check("chain: history is kept (5 records, 2 superseded)", len(A.for_class(w.s, cls["id"])) == 5)
check("chain: a request has one standing decision per class", len([d for d in cur if d["request_id"] == r1["id"]]) == 1)
check("chain: previous_id is read-only for senders", pairs(S.create(w.s, {"request_id": r1["id"], "scheduled_class_id": cls["id"], "previous_id": x1["id"]}, "user:t").problems) == ["previous_id:not_allowed"])
check("chain: update cannot change a decision", pairs(S.update(w.s, x2["id"], {"status": "accepted"}, "user:t").problems) == ["status:immutable"])
check("chain: note can be updated through the service", S.update(w.s, x2["id"], {"decision_note": "ok"}, "user:t", now=tick()).ok)
check("chain: soft_delete refused (cancel instead)", pairs(S.soft_delete(w.s, x2["id"], "user:t").problems) == ["id:not_allowed"])
check("chain: counts and records unchanged by refusal", w.counts(cls) == (5, 0))

# re-deciding does not count the party's own earlier seats twice
w = World()
cls = w.klass(target=4, mx=6)
ra, rb = w.request(2), w.request(2)
w.assign(ra, cls)
w.assign(rb, cls)
again = w.assign(rb, cls, attendee_count=1)
check("chain: a party's own earlier seats are not counted against it (2 taken by others + 1 = accepted)", again.ok and again.data["status"] == "accepted" and w.counts(cls) == (3, 0), str(again.problems))

# atomicity: if the count write fails the assignment is not stored
w = World()
cls = w.klass()
rq = w.request(1)
orig = C.set_registration_counts
C.set_registration_counts = lambda *a, **k: C.failure("not_found")
try:
    r = w.assign(rq, cls)
finally:
    C.set_registration_counts = orig
check("atomic: a failed count write is a server_error", r.code == "server_error")
check("atomic: nothing stored when counts fail", not w.s.data.get("test_registration_assignments"))

# ---------------------------------------------------------------------------
# 5. Class guards
# ---------------------------------------------------------------------------
w = World()
cls = w.klass(target=4, mx=6)
rq = w.request(2)
asg = w.assign(rq, cls).data
check("guard: class with registrations cannot be deleted (conflict id:in_use)", (lambda r: r.code == "conflict" and pairs(r.problems) == ["id:in_use"])(CS.soft_delete(w.s, cls["id"], "user:t", now=tick())))
check("guard: capacity_max cannot drop below registered seats (order itself is fine)", pairs(CS.update(w.s, cls["id"], {"capacity_minimum": 1, "capacity_target": 1, "capacity_max": 1}, "user:t", now=tick()).problems) == ["capacity_max:out_of_range"])
check("guard: capacity_max down to the registered count is fine (target lowered too)", CS.update(w.s, cls["id"], {"capacity_target": 2, "capacity_max": 2}, "user:t", now=tick()).ok)
w.assign(rq, cls, status="cancelled")
check("guard: once cancelled the class can be deleted", CS.soft_delete(w.s, cls["id"], "user:t", now=tick()).ok)
w2 = World()
c_wait = w2.klass(target=1, mx=1, waitlist=True)
q1, q2 = w2.request(1), w2.request(1)
w2.assign(q1, c_wait)
w2.assign(q2, c_wait)
w2.assign(q1, c_wait, status="cancelled")
check("guard: a waitlisted party holds the class too", CS.soft_delete(w2.s, c_wait["id"], "user:t", now=tick()).code == "conflict")
check("guard: counts are server-kept (sender cannot set registered_count)", pairs(CS.update(w.s, cls["id"], {"registered_count": 9}, "user:t").problems) == ["registered_count:not_allowed"])

# ---------------------------------------------------------------------------
# 6. suggest and queue
# ---------------------------------------------------------------------------
w = World()
cls = w.klass(target=2, mx=3, waitlist=False, ctype="workshop")
closed_cls = w.klass(status="scheduled")
ra = w.request(2, class_id=cls["id"])
rb = w.request(2, class_id=cls["id"])
rc = w.request(1, class_id=closed_cls["id"])
rd = w.request(2, no_fit=True)
re_ = w.request(2, rtype="private")
rf = w.request(2, rtype="group")
gone = w.klass()
rg = w.request(1, class_id=gone["id"])
CS.soft_delete(w.s, gone["id"], "user:t", now=tick())
made = w.klass(source_request_id=rf["id"], ctype="group", target=5, mx=8)
sa = S.suggest(w.s, ra["id"]).data
check("suggest: ready, accepted, names the class", sa["state"] == "ready" and sa["status"] == "accepted" and sa["class_title"] == cls["title"] and sa["seats"] == 2, str(sa))
check("suggest writes nothing", not w.s.data.get("test_registration_assignments") and w.counts(cls) == (0, 0))
check("suggest: unknown request -> not_found", S.suggest(w.s, str(uuid.uuid4())).code == "not_found" and S.suggest(w.s, "x").code == "not_found")
check("suggest: closed class -> needs_attention class_closed", (lambda r: r["state"] == "needs_attention" and r["reason"] == "class_closed")(S.suggest(w.s, rc["id"]).data))
check("suggest: no_class_fits -> no_class", S.suggest(w.s, rd["id"]).data["reason"] == "no_class_fits")
check("suggest: private with no class yet -> no_class_yet", (lambda r: r["state"] == "no_class" and r["reason"] == "no_class_yet")(S.suggest(w.s, re_["id"]).data))
check("suggest: group with its class -> ready", (lambda r: r["state"] == "ready" and r["scheduled_class_id"] == made["id"])(S.suggest(w.s, rf["id"]).data))
check("suggest: deleted class -> needs_attention class_not_found", (lambda r: r["state"] == "needs_attention" and r["reason"] == "class_not_found")(S.suggest(w.s, rg["id"]).data))
w.assign(ra, cls)
sb = S.suggest(w.s, rb["id"]).data
check("suggest: second party now sees the first one's seats (2 taken, 2 more passes the max of 3 -> class_full)", sb["state"] == "needs_attention" and sb["reason"] == "class_full", str(sb))
sa2 = S.suggest(w.s, ra["id"]).data
check("suggest: an assigned request reports assigned", sa2["state"] == "assigned" and sa2["status"] == "accepted" and sa2["class_title"] == cls["title"])
q = S.queue(w.s).data
byid = {i["request_id"]: i for i in q["items"]}
check("queue: all seven requests present, newest first", len(q["items"]) == 7 and [i["created_at"] for i in q["items"]] == sorted((i["created_at"] for i in q["items"]), reverse=True))
check("queue: states", (byid[ra["id"]]["state"], byid[rb["id"]]["state"], byid[rc["id"]]["state"], byid[rd["id"]]["state"], byid[re_["id"]]["state"], byid[rf["id"]]["state"], byid[rg["id"]]["state"]) ==
      ("assigned", "needs_attention", "needs_attention", "no_class", "no_class", "ready", "needs_attention"))
check("queue: counts add up", q["counts"] == {"assigned": 1, "ready": 1, "needs_attention": 3, "no_class": 2, "closed": 0} and sum(q["counts"].values()) == 7, str(q["counts"]))
check("queue: items carry the person's name and type for the card", byid[ra["id"]]["first_name"] == "Ann" and byid[ra["id"]]["registration_type"] == "class")
w.assign(rc, closed_cls, status="declined")
check("queue: a declined request is settled (closed), not attention", S.queue(w.s).data["items"][[i["request_id"] for i in S.queue(w.s).data["items"]].index(rc["id"])]["state"] == "closed")
check("queue: limit works and bad limit refused", len(S.queue(w.s, 2).data["items"]) == 2 and pairs(S.queue(w.s, "x").problems) == ["limit:invalid_type"])
w.s.data["test_registration_requests"][rd["id"]]["deleted_at"] = "2026-10-09T00:00:00Z"
check("queue: soft-deleted request is skipped", rd["id"] not in {i["request_id"] for i in S.queue(w.s).data["items"]})
check("queue: empty store", S.queue(MemoryDocStore("test_")).data == {"items": [], "counts": {"assigned": 0, "ready": 0, "needs_attention": 0, "no_class": 0, "closed": 0}})

print(f"\n{total} checks, {len(fails)} failed")
if fails:
    print("FAILED: " + "; ".join(fails))
sys.exit(1 if fails else 0)
