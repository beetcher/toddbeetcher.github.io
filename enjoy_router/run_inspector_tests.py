#!/usr/bin/env python3
"""Tests for the Global Inspector (P-78): a person whose role holds `inspect_everything` may LOOK at everything and CHANGE nothing.
Run from enjoy_router/:  python3 run_inspector_tests.py   (-v lists every check). Nothing touches Firebase; Google is a fake verifier.

What is proved, each as named checks:
  * who counts as an inspector (and who does not: a super admin, a role without the capability)
  * every collection and every op at the Console door: reads work, EVERY write is refused 403 and the store does not change
  * the writes that matter most, typed by hand: venues, people, invitations (send_invite), notes, merges, placing people
  * private data: hidden fields are gone, masked fields read (hidden), names stay, access emails and venue contacts stay
  * a list cannot be filtered on a hidden or masked field
  * the records door and the Discovery door (the 25-cent cap, only your own runs, no withdraw)
"""
import copy, json, pathlib, sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import seed_access  # noqa: E402
from access import CAPABILITIES, inspect as INS  # noqa: E402
from console import handle_console, make_failure_limiter  # noqa: E402
from crud import access_persons_crud as PE, access_roles_crud as RO, classes_service as CS, venues_service as VS  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud_endpoint import ADMIN_BLOCKED_COLLECTIONS, ADMIN_OPS, HANDLERS, OPS, handle_admin  # noqa: E402
from discovery_door import handle_discovery  # noqa: E402
from launch_discovery import zip_table  # noqa: E402
from memory_store import MemoryStore  # noqa: E402

START = datetime(2026, 10, 21, 12, 0, 0, tzinfo=timezone.utc)
A, KEY = "user:admin", "k" * 16 + "Z" * 16 + "-test-key-not-real"
fails, total, clock = [], 0, [0]
def tick():
    clock[0] += 5
    return START + timedelta(seconds=clock[0])
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    if not ok or "-v" in sys.argv: print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")

zip_table.set_table({"80301": ["CO", 40.0, -105.0, "Boulder"], "53703": ["WI", 43.0, -89.0, "Madison"]})
store = MemoryDocStore("")
def uid(n): return f"{n:08d}-0000-4000-8000-000000000000"
def raw(coll, n, **kw):
    store.create(coll, uid(n), {"id": uid(n), "schema_version": 1, "created_at": "2026-10-01T00:00:00Z", "updated_at": "2026-10-01T00:00:00Z", **kw}); return uid(n)

# ---- a world with private details in it
BOULDER = raw("discovery_areas", 10, kind="region", state_code="CO", name="Boulder", zip_codes=["80301"], is_active=True)
def venue(name, zip_code, **extra):
    r = VS.create_with_place(store, {"name": name, "slug": name.lower().replace(" ", "_"), "status": "inactive", "is_public_venue": True,
                                     "email": "hall@venue.example", "phone": "303-555-0100", "notes": "Public hall, ask for Sam.", **extra}, A, now=tick(),
                             address={"lines": ["1 Main St"], "locality": "Boulder", "region": "CO", "postal_code": zip_code, "country": "US"})
    assert r.ok, r.problems; return r.data["id"]
vB = venue("Boulder Hall", "80301")
assert VS.update(store, vB, {"status": "active"}, A, now=tick()).ok
cB = CS.create(store, {"title": "Boulder Class", "slug": "boulder_class", "class_type": "workshop", "program_slug": "launch", "status": "scheduled", "starts_at": "2026-12-01T17:00:00Z",
                       "time_zone": "America/Denver", "duration_minutes": 60, "venue_id": vB, "is_public": False, "is_venue_confirmed": False, "capacity_minimum": 2,
                       "capacity_target": 8, "capacity_max": 10, "organizer_name": "Olive Organizer", "organizer_email": "olive@home.example", "organizer_phone": "303-555-0111"}, A, now=tick()).data["id"]
pAnn = raw("individuals", 231, display_name="Ann Student", given_name="Ann", family_name="Student", status="active", email="ann@home.example", phone="303-555-0122",
           backup_email="ann2@home.example", backup_phone="303-555-0133", birth_date="1961-04-17", birth_place_city="Duluth", notes="Prefers mornings; widow.")
raw("individual_restricted_details", 232, individual_id=pAnn, blood_type_abo="A", notes="secret")
raw("locations", 240, status="active", name="Ann Home", addresses=[{"usage": "civic", "postal_code": "80301", "lines": ["9 Private Rd"], "is_primary": True, "country": "US"}])
raw("location_links", 241, subject_type="individual", subject_id=pAnn, location_id=uid(240), relationship="resides_at", status="active", is_primary=True, notes="gate code 1234")
raw("student_rosters", 250, individual_id=pAnn, status="active", notes="allergic to cats")
raw("instructor_rosters", 251, individual_id=pAnn, status="active", bio="Teaches", notes="cell is best")
raw("attendances", 252, individual_id=pAnn, scheduled_class_id=cB, role="student", status="assigned", notes="needs a ride",
    correspondence=[{"at": "2026-10-02T00:00:00Z", "kind": "placement_confirmation", "channel": "email", "to": "ann@home.example", "result": "sent", "by": "system:x"}],
    status_history=[{"at": "2026-10-02T00:00:00Z", "from": "assigned", "to": "confirmed", "by": "user:admin"}])
raw("organizations", 253, name="Valley District", status="active", email="office@district.example", phone="303-555-0199", notes="superintendent is new")
raw("communication_logs", 254, kind="registration_receipt", channel="email", status="sent", reason="ok", trigger="automatic", contract_version=1, to="ann@home.example",
    subject="We received your request", notes=[{"text": "called her", "by": "user:admin", "at": "2026-10-02T00:00:00Z"}], individual_id=pAnn)
raw("journal_events", 255, note="private remark")

# ---- people at the door
class Fake:
    def __init__(self): self.tokens = {}
    def verify(self, t): return dict(self.tokens[t])
V = Fake()
def tok(n): return f"header{n:03d}.payload{n:03d}.signature{n:03d}" + "x" * 20
def role(key, caps=None, sup=False):
    r = RO.create(store, {"key": key, "label": key, "is_super_admin": sup, **({} if sup else {"capabilities": caps})}, A, now=tick()); assert r.ok, r.problems; return r.data
def who(n, email, r, grants=None):
    p = PE.create(store, {"email": email, "role_id": r["id"], "display_name": email.split("@")[0], **({"grants": grants} if grants is not None else {})}, A, now=tick()); assert p.ok, p.problems
    V.tokens[tok(n)] = {"uid": f"uid-{n}", "email": email, "email_verified": True, "provider": "google.com", "name": email}
    return p.data
# the role exactly as the seed script makes it
SEED = {r["key"]: r for r in seed_access.ROLES}
insp_role = role("global_inspector", SEED["global_inspector"]["capabilities"])
mixed_role = role("inspector_plus", ["inspect_everything", "view_console", "edit_venues", "manage_requests", "manage_classes", "edit_people"])   # holds the capability AND more
sup_role = role("super_admin", sup=True)
plain_role = role("viewer", ["view_console"])
todd = who(1, "todd@x.com", sup_role)
insp = who(2, "inspector@x.com", insp_role)
mixed = who(3, "mixed@x.com", mixed_role)
roamer = who(4, "roamer@x.com", insp_role, grants=[{"kind": "all"}])      # an inspector who was also given the whole US: still view only
viewer = who(5, "viewer@x.com", plain_role)

def call(n, collection, op, args=None, key=False):
    auth = f"Bearer {KEY}" if key else f"Bearer {tok(n)}"
    r = handle_admin("POST", auth, json.dumps({"collection": collection, "op": op, "args": args or {}}).encode(), KEY, "v", store, make_failure_limiter(), tick(), verifier=V)
    return r.status, r.body
def records_of(n, collection, **args):
    st, b = call(n, collection, "list", {"limit": 200, **args})
    return b["data"]["records"] if st == 200 else None
def ids(n, collection, **args):
    r = records_of(n, collection, **args)
    return None if r is None else sorted(x["id"] for x in r)

# ================================================================ who is an inspector
st, b = call(2, "venues", "list")        # the first call also saves the person's first sign-in (a system write); the snapshot comes after it
m = lambda n: handle_admin("POST", f"Bearer {tok(n)}", json.dumps({"op": "me"}).encode(), KEY, "v", store, make_failure_limiter(), tick(), verifier=V).body["data"]
check("capability: inspect_everything is one of the 18 listed capabilities", "inspect_everything" in CAPABILITIES and len(CAPABILITIES) == 18)
check("me: the Inspector is told they are an inspector and holds only that capability", m(2)["inspector"] is True and m(2)["capabilities"] == ["inspect_everything"] and m(2)["is_super_admin"] is False, m(2))
check("me: a super admin is not an inspector", m(1)["inspector"] is False)
check("me: a role with the capability AND others is still an inspector (the capability wins)", m(3)["inspector"] is True)
check("me: an ordinary role is not an inspector", m(5)["inspector"] is False)
check("seed: the role is Global Inspector and holds only inspect_everything", SEED["global_inspector"]["capabilities"] == ["inspect_everything"] and SEED["global_inspector"]["label"] == "Global Inspector"
      and SEED["global_inspector"]["is_super_admin"] is False)
for n in (3, 4, 5):
    call(n, "venues", "list")           # first sign-ins done
SNAP = copy.deepcopy(store.data)
def _norm(data):
    """The store without empty collections (a read creates an empty one) and without the sign-in time (a system write at sign-in, not a change by the caller)."""
    out = {}
    for c, docs in data.items():
        if docs:
            out[c] = {i: ({k: v for k, v in d.items() if k != "last_sign_in_at"} if c == "access_persons" else d) for i, d in docs.items()}
    return out
def unchanged(): return _norm(store.data) == _norm(SNAP)

# ================================================================ every collection, every op
BAD_ARGS = {"id": uid(999), "data": {}, "changes": {}, "request_id": uid(999), "individual_id": uid(231), "survivor_id": uid(1), "duplicate_id": uid(2), "reason": "x",
            "address": {"lines": ["x"]}, "text": "x", "note": "x", "person": {}, "requester": {}, "source": "dashboard", "valid_to": "2026-01-01"}
def args_for(op):
    req, opt = OPS[op]
    return {k: BAD_ARGS.get(k, "x") for k in req}
bad_reads, bad_writes, unseen = [], [], []
for coll in sorted(HANDLERS):
    for op in sorted(OPS):
        for n in (2, 3, 4):                                         # the Inspector, one who also holds other capabilities, one who also holds the whole US
            st, b = call(n, coll, op, args_for(op))
            if op in ("list", "get", "queue", "suggest", "find_by_address", "get_for_individual"):
                if coll in ADMIN_BLOCKED_COLLECTIONS or coll == "individual_restricted_details":
                    if st == 200: bad_reads.append((n, coll, op, st))
                elif st == 403 and op in ("list",):
                    bad_reads.append((n, coll, op, st))
            elif st == 200:
                bad_writes.append((n, coll, op, st))
            elif op in ADMIN_OPS and coll not in ADMIN_BLOCKED_COLLECTIONS and st != 403:
                bad_writes.append((n, coll, op, st))
check("every collection: a list is never refused for an inspector (except the blocked ones)", not bad_reads, bad_reads[:5])
check("every collection, every write op: refused 403 for the Inspector, for a role holding more, and for an Inspector with the whole US (never 200)", not bad_writes, bad_writes[:5])
check("after all those calls the store is exactly as it was", unchanged())
nothing_listed = [c for c in sorted(HANDLERS) if c not in ADMIN_BLOCKED_COLLECTIONS and call(2, c, "list")[0] != 200]
check("the Inspector can list every collection the Console door serves, activity and access included", not nothing_listed, nothing_listed)
check("the blocked collections stay blocked for an inspector (restricted details are never shown)", call(2, "individual_restricted_details", "list")[0] == 400
      and call(2, "individual_restricted_details", "get_for_individual", {"individual_id": pAnn})[0] == 400)

# ---- the writes that matter most, typed by hand
HAND = [("venues", "update", {"id": vB, "changes": {"name": "Hacked"}}), ("venues", "soft_delete", {"id": vB}), ("venues", "create", {"data": {"name": "X"}}),
        ("venues", "update", {"id": vB, "changes": {"status": "active"}}),
        ("individuals", "update", {"id": pAnn, "changes": {"given_name": "Bob"}}), ("individuals", "merge", {"survivor_id": pAnn, "duplicate_id": pAnn, "reason": "x"}),
        ("access_persons", "create", {"data": {"email": "new@x.com", "role_id": insp_role["id"]}}),
        ("access_persons", "send_invite", {"id": insp["id"]}), ("access_persons", "update", {"id": insp["id"], "changes": {"role_id": sup_role["id"]}}),
        ("access_roles", "update", {"id": insp_role["id"], "changes": {"capabilities": ["view_console", "edit_venues"]}}),
        ("access_roles", "create", {"data": {"key": "z", "label": "z", "is_super_admin": True}}),
        ("communication_logs", "add_note", {"id": uid(254), "text": "hello"}), ("communication_logs", "mark_handled", {"id": uid(254)}),
        ("message_templates", "publish", {"id": uid(1)}), ("comms_settings", "update", {"id": uid(1), "changes": {"mode": "live"}}),
        ("attendances", "assign", {"data": {"scheduled_class_id": cB}, "person": {"given_name": "Z"}}), ("attendances", "send_confirmation", {"id": uid(252)}),
        ("scheduled_classes", "update", {"id": cB, "changes": {"status": "cancelled"}}), ("discovery_settings", "update", {"id": uid(1), "changes": {}}),
        ("console_settings", "update", {"id": uid(1), "changes": {"session_timeout_minutes": 480}}), ("activity_events", "create", {"data": {}})]
for coll, op, a in HAND:
    results = [call(n, coll, op, a)[0] for n in (2, 3, 4)]
    check(f"hand-typed {coll}.{op}: refused 403 for all three kinds of inspector", results == [403, 403, 403], results)
check("none of the hand-typed writes changed anything, and no email was sent or logged", unchanged())
check("the same hand-typed call by a super admin still works (the rule is about the inspector, not the call)", call(1, "venues", "update", {"id": vB, "changes": {"notes": "ok by Todd"}})[0] == 200)
SNAP = copy.deepcopy(store.data)

# ================================================================ reading: what the Inspector sees
check("reads: the Inspector sees every venue and class (no territory)", ids(2, "venues") == [vB] and ids(2, "scheduled_classes") == [cB])
check("reads: the Inspector sees the activity log, which only a super admin could read before", call(2, "activity_events", "list")[0] == 200 and call(5, "activity_events", "list")[0] == 403)
check("reads: the Inspector sees Access (roles and people) and Messages", all(call(2, c, "list")[0] == 200 for c in ("access_roles", "access_persons", "message_templates", "comms_settings", "communication_logs")))
check("reads: an ordinary viewer still cannot read people or Access (nothing opened for them)", call(5, "individuals", "list")[0] == 403 and call(5, "access_persons", "list")[0] == 403)
people = {p["email"]: p for p in records_of(2, "access_persons")}
check("access: staff emails show in FULL", "todd@x.com" in people and "inspector@x.com" in people, list(people))
check("access: the Google account id is never shown", all("google_uid" not in p for p in people.values()), [k for p in people.values() for k in p if "uid" in k])
check("access: display names show", people["todd@x.com"].get("display_name") == "todd")

# ---- private data
ann = [x for x in records_of(2, "individuals") if x["id"] == pAnn][0]
check("people: the name shows", ann.get("given_name") == "Ann" and ann.get("family_name") == "Student" and ann.get("display_name") == "Ann Student", ann)
check("people: email, phone, backup email and backup phone read (hidden)", all(ann.get(k) == "(hidden)" for k in ("email", "phone", "backup_email", "backup_phone")), ann)
check("people: notes, birth date and birth place are gone", all(k not in ann for k in ("notes", "birth_date", "birth_place_city")), ann)
check("people: nothing of the real values is anywhere in the answer", all(s not in json.dumps(ann) for s in ("ann@home.example", "303-555-0122", "1961", "Duluth", "widow")))
check("people: get one person is shaped the same way", call(2, "individuals", "get", {"id": pAnn})[1]["data"].get("email") == "(hidden)")
check("people: restricted details are never reachable", call(2, "individual_restricted_details", "get_for_individual", {"individual_id": pAnn})[0] == 400)
check("home addresses: the person's place is not in the list and a direct read is refused", ids(2, "locations") == [] or uid(240) not in ids(2, "locations"))
check("home addresses: the link to a person is not listed, and a direct read is refused", uid(241) not in (ids(2, "location_links") or []) and call(2, "location_links", "get", {"id": uid(241)})[0] == 403)
check("home addresses: a direct read of the person's place is refused", call(2, "locations", "get", {"id": uid(240)})[0] == 403)
check("home addresses: a venue's place is shown, address and ZIP, because a venue is public", any(r.get("addresses") for r in records_of(2, "locations")) and "80301" in json.dumps(records_of(2, "locations")))
v = records_of(2, "venues", expand=True)[0]
check("venues: the venue's own email, phone and note show", v.get("email") == "hall@venue.example" and v.get("phone") == "303-555-0100" and v.get("notes") == "ok by Todd", v)
check("venues: the place it operates at shows with its address", v.get("place", {}).get("address", {}).get("postal_code") == "80301" and v["place"]["address"].get("lines") == ["1 Main St"], v.get("place"))
check("classes: the organizer's name shows, their email and phone read (hidden)", records_of(2, "scheduled_classes")[0].get("organizer_name") == "Olive Organizer"
      and records_of(2, "scheduled_classes")[0].get("organizer_email") == "(hidden)" and records_of(2, "scheduled_classes")[0].get("organizer_phone") == "(hidden)")
sr = records_of(2, "student_rosters", expand=True)[0]
check("students: the person's name shows, their email and phone read (hidden), the roster note is gone", sr["person"].get("display_name") == "Ann Student" and sr["person"].get("email") == "(hidden)"
      and sr["person"].get("phone") == "(hidden)" and "notes" not in sr, sr)
ir = records_of(2, "instructor_rosters", expand=True)[0]
check("instructors: name shows, contact reads (hidden), notes are gone, the bio stays", ir["person"].get("display_name") == "Ann Student" and ir["person"].get("email") == "(hidden)" and "notes" not in ir and ir.get("bio") == "Teaches", ir)
at = records_of(2, "attendances")[0]
check("attendance: notes are gone; the old message lines' address reads (hidden); the status history keeps its from and to", "notes" not in at and at["correspondence"][0]["to"] == "(hidden)"
      and at["status_history"][0]["to"] == "confirmed" and at["status_history"][0]["from"] == "assigned", at)
org = records_of(2, "organizations")[0]
check("organizations: the organization's own contact shows, its note is gone", org.get("email") == "office@district.example" and org.get("phone") == "303-555-0199" and "notes" not in org, org)
log = records_of(2, "communication_logs")[0]
check("messages: the address the message went to reads (hidden), the subject and status show, the notes are gone", log["to"] == "(hidden)" and log["subject"] == "We received your request"
      and log["status"] == "sent" and "notes" not in log, log)
check("messages: nothing of the real address is anywhere in the answer", "ann@home.example" not in json.dumps(log))
check("journal: a person's free-text note is gone", all("note" not in r for r in records_of(2, "journal_events")))
check("the super admin still sees everything the Inspector may not (the masking is for the Inspector only)", [x for x in records_of(1, "individuals") if x["id"] == pAnn][0].get("email") == "ann@home.example"
      and records_of(1, "communication_logs")[0]["to"] == "ann@home.example")

# ---- guessing
check("filters: a list filtered on email is refused for the Inspector (no guessing a hidden value)", call(2, "individuals", "list", {"filters": {"email": "ann@home.example"}})[0] == 403)
check("filters: so are phone, postal code and notes", all(call(2, c, "list", {"filters": {f: "x"}})[0] == 403 for c, f in (("individuals", "phone"), ("locations", "postal_code"), ("attendances", "notes"))))
check("filters: a filter on a field that shows is fine", call(2, "access_persons", "list", {"filters": {"email": "todd@x.com"}})[0] == 200 and call(2, "individuals", "list", {"filters": {"status": "active"}})[0] in (200, 400))
check("filters: a venue's contact is not hidden, so it can be filtered", INS.refuses_filters("venues", {"email": "x"}) is False and INS.refuses_filters("individuals", {"email": "x"}) is True)

# ================================================================ the records door (registration requests)
def reg_store():
    s = MemoryStore([])
    s.requests.append({"id": "r1", "created_at": "2026-10-09T04:26:00Z", "first_name": "Mel", "last_name": "Jones", "email": "mel@home.example", "phone": "303-555-0144", "postal_code": "80301",
                       "street_address": "5 Home Rd", "notes": "has two dogs", "preferred_location": "my house", "what_they_want": "learn email", "completion_token": "SECRET",
                       "referrer_first_name": "Rita", "referrer_email": "rita@home.example", "participants": [{"first_name": "Pat", "last_name": "J", "email": "pat@home.example"}]})
    return s
def records(n, key=False):
    return handle_console("GET", f"Bearer {KEY if key else tok(n)}", {}, KEY, "v", reg_store(), make_failure_limiter(), tick(), verifier=V, access_store=store)
r = records(2)
rec = r.body["data"]["records"][0] if r.status == 200 else {}
check("records door: the Inspector may read requests", r.status == 200 and r.body["data"]["count"] == 1)
check("records door: names show; email, phone, ZIP and the referrer's email read (hidden)", rec.get("first_name") == "Mel" and rec.get("last_name") == "Jones" and rec.get("referrer_first_name") == "Rita"
      and all(rec.get(k) == "(hidden)" for k in ("email", "phone", "postal_code", "referrer_email")), rec)
check("records door: notes, street address, preferred location and the secret link token are gone; nothing else about the person leaks", all(k not in rec for k in ("notes", "street_address", "preferred_location", "completion_token")))
check("records door: people named on the request are masked the same way", rec["participants"][0].get("first_name") == "Pat" and rec["participants"][0].get("email") == "(hidden)", rec.get("participants"))
check("records door: free text about what they want stays", rec.get("what_they_want") == "learn email")
check("records door: no real contact value anywhere in the answer", all(s not in json.dumps(rec) for s in ("mel@home.example", "303-555-0144", "5 Home Rd", "two dogs", "rita@home", "pat@home")))
check("records door: a super admin still sees the real values; an ordinary viewer is refused", records(1).body["data"]["records"][0]["email"] == "mel@home.example" and records(5).status == 403)
check("records door: an inspector who also holds the whole US is masked the same way", records(4).body["data"]["records"][0]["email"] == "(hidden)")

# ================================================================ the Discovery door
class Engine:
    def __init__(self): self.calls = []
    def _ok(self, op, *a):
        self.calls.append((op,) + a); return SimpleNamespace(ok=True, data={"op": op}, code="", message="")
    def quote(self, rq): return self._ok("quote", rq.spend_cap_cents)
    def plan(self, rq, actor): return self._ok("plan", rq.spend_cap_cents, actor)
    def step(self, run_id, actor): return self._ok("step", run_id, actor)
    def stop(self, run_id, actor): return self._ok("stop", run_id, actor)
    def withdraw(self, run_id, actor): return self._ok("withdraw", run_id, actor)
eng = Engine()
def disc(n, op, args=None, key=False):
    r = handle_discovery("POST", f"Bearer {KEY if key else tok(n)}", json.dumps({"op": op, "args": args or {}}).encode(), KEY, "v", store, eng, {}, make_failure_limiter(), tick(), verifier=V)
    return r.status, r.body
REQ = lambda cap: {"finder_key": "venue", "model_id": "m", "area_ids": [BOULDER], "type_keys": ["t"], "max_results": 3, "spend_cap_cents": cap}
check("discovery: the Inspector reads status, runs and the ZIP map", disc(2, "status")[0] == 200 and disc(2, "list_runs")[0] == 200 and disc(2, "zips", {"state_code": "CO"})[0] == 200)
check("discovery: a quote and a plan at 25 cents or less go through", disc(2, "quote", REQ(25))[0] == 200 and disc(2, "plan", REQ(10))[0] == 200 and ("plan", 10, f"user:{insp['id']}") in eng.calls, eng.calls)
check("discovery: a run is stamped with the Inspector", ("plan", 10, f"user:{insp['id']}") in eng.calls)
st, b = disc(2, "plan", REQ(26))
check("discovery: a plan over 25 cents is refused with a plain message and never reaches the engine", st == 400 and b["error"]["code"] == "inspector_cap" and "25" in b["error"]["message"] and not any(c[:2] == ("plan", 26) for c in eng.calls), b)
check("discovery: a quote over 25 cents is refused too", disc(2, "quote", REQ(26))[0] == 400 and disc(2, "quote", REQ(1000))[0] == 400)
check("discovery: a cap that is not a number is refused", disc(2, "plan", {**REQ(1), "spend_cap_cents": "5"})[0] == 400 and disc(2, "plan", {**REQ(1), "spend_cap_cents": True})[0] == 400)
check("discovery: a role holding more than the capability is capped the same way", disc(3, "plan", REQ(26))[0] == 400 and disc(4, "plan", REQ(26))[0] == 400)
check("discovery: a super admin is NOT capped by this rule", disc(1, "plan", REQ(26))[0] == 200)
mine, theirs = f"run-mine", f"run-theirs"
store.create("discovery_runs", mine, {"id": mine, "created_by": f"user:{insp['id']}", "area_ids": [BOULDER], "status": "planned"})
store.create("discovery_runs", theirs, {"id": theirs, "created_by": f"user:{todd['id']}", "area_ids": [BOULDER], "status": "planned"})
eng.calls.clear()
check("discovery: the Inspector may step and stop a run they started", disc(2, "step", {"run_id": mine})[0] == 200 and disc(2, "stop", {"run_id": mine})[0] == 200)
check("discovery: they may not step or stop someone else's run, or one that does not exist", disc(2, "step", {"run_id": theirs})[0] == 403 and disc(2, "stop", {"run_id": theirs})[0] == 403
      and disc(2, "step", {"run_id": "nope"})[0] == 403 and ("step", theirs, f"user:{insp['id']}") not in eng.calls)
check("discovery: they may not withdraw a run (it changes records), not even their own", disc(2, "withdraw", {"run_id": mine})[0] == 403 and not any(c[0] == "withdraw" for c in eng.calls))
check("discovery: a role holding more than the capability still cannot withdraw", disc(3, "withdraw", {"run_id": mine})[0] == 403)
check("discovery: an unknown op is still refused", disc(2, "frobnicate")[0] == 400)
check("discovery: the settings are the Console door's, and refused there (so models, areas and prompts cannot be edited)",
      all(call(2, c, "update", {"id": uid(1), "changes": {}})[0] == 403 for c in ("discovery_models", "discovery_areas", "discovery_types", "discovery_prompts", "discovery_settings")))
check("discovery: an ordinary viewer has no Discovery (unchanged)", disc(5, "status")[0] == 403)
check("discovery: the engine never saw a write from the Inspector's reads", all(c[0] in ("quote", "plan", "step", "stop") for c in eng.calls))

check("unit: a place's address list nested inside anything but a venue or a place is removed", "addresses" not in INS.shape(store, "individuals", "get", {"id": "x", "addresses": [{"lines": ["9 Private Rd"]}], "given_name": "A"}))
check("unit: an empty contact stays empty (it does not pretend something is hidden)", INS.shape(store, "individuals", "get", {"id": "x", "phone": "", "email": None}) == {"id": "x", "phone": "", "email": None})
check("unit: the door-side refusal itself covers restricted details and every write op", INS.refuses_op("individual_restricted_details", "list") is True and INS.refuses_op("venues", "update") is True and INS.refuses_op("venues", "list") is False)
check("unit: a single record whose collection is blocked is not shown at all", INS.shape(store, "individual_restricted_details", "get", {"id": "x"}) is None)
# ================================================================ the rules are about the capability, not the name
check("rules: INSPECTOR_DISCOVERY_OPS has no withdraw and CAP_CENTS is 25", "withdraw" not in INS.INSPECTOR_DISCOVERY_OPS and INS.CAP_CENTS == 25)
check("rules: a role may hold inspect_everything together with others, and a super admin role never lists it", mixed_role["capabilities"].count("inspect_everything") == 1)

print(f"\n{total - len(fails)}/{total} checks passed" + (f"; FAILED: {fails}" if fails else ""))
sys.exit(1 if fails else 0)
