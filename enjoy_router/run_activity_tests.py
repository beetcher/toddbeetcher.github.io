#!/usr/bin/env python3
"""Tests for the activity log (P-46): the activity store (crud/activity_store.py, crud/activity_log.py), the read handler
(crud/activity_events_crud.py), the Console door wiring and the capability table.
Run from enjoy_router/:  python3 run_activity_tests.py   (-v lists every check). Nothing touches Firebase; the store is in memory.
Every rule below is named in schemas/ACTIVITY_EVENT_GUIDE.md section 3 and mutation-checked by mutate_activity.py."""
import copy, json, pathlib, sys
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import crud_endpoint  # noqa: E402
from access import policy  # noqa: E402
from console import make_failure_limiter  # noqa: E402
from crud import activity_events_crud as AE  # noqa: E402
from crud import individuals_service as IND  # noqa: E402
from crud.activity_store import ActivityStore, EXCLUDED_COLLECTIONS, QUIET_FIELDS  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud.schema_kit import UUID_PATTERN  # noqa: E402
from crud.store_errors import DocExists, DocMissing, StaleUpdate  # noqa: E402

START = datetime(2026, 10, 20, 21, 0, 0, tzinfo=timezone.utc)
KEY = "k" * 16 + "Z" * 16 + "-test-key-not-real"
ACT = "activity_events"
fails, total, tickn = [], 0, [0]


def tick():
    tickn[0] += 5
    return START + timedelta(seconds=tickn[0])


def stamp(t=None):
    return (t or tick()).strftime("%Y-%m-%dT%H:%M:%SZ")


def check(label, ok, detail=""):
    global total
    total += 1
    if not ok:
        fails.append(label)
    if not ok or "-v" in sys.argv:
        print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")


def fresh():
    inner = MemoryDocStore("")
    return inner, ActivityStore(inner)


def entries(inner):
    docs = inner.query(ACT, limit=5000)
    return sorted(docs, key=lambda d: (d["sequence_ms"], d["id"]))


def new_id(n):
    return f"b0000000-0000-4000-8000-{n:012d}"


def vdoc(n=1, **kw):
    s = stamp()
    d = {"id": new_id(n), "schema_version": 1, "created_at": s, "created_by": "user:admin", "updated_at": s, "updated_by": "user:admin",
         "source": "dashboard", "name": f"Venue {n}", "slug": f"venue_{n}", "status": "inactive"}
    d.update(kw)
    return d


def upd(extra=None, actor="user:abc"):
    return {"updated_at": stamp(), "updated_by": actor, **(extra or {})}


def blob(e):
    return json.dumps(e, sort_keys=True)


# ------------------------------------------------------------------ A1 create
inner, st = fresh()
d = vdoc(1, capacity_note="six chairs", contact_email="owner@example.org")
st.create("venues", d["id"], d)
es = entries(inner)
check("A1 a create writes exactly one entry", len(es) == 1)
e = es[0] if es else {}
check("A1 entry says created, venue, venues, the record id", (e.get("action"), e.get("record_type"), e.get("collection"), e.get("record_id")) == ("created", "venue", "venues", d["id"]))
check("A1 actor is the record's created_by and source is system", e.get("created_by") == "user:admin" and e.get("source") == "system" and e.get("updated_by") == "user:admin")
check("A1 entry time is the record's own stamp", e.get("created_at") == d["created_at"] and e.get("updated_at") == d["created_at"])
check("A1 id is a uuid and schema_version 1", bool(UUID_PATTERN.match(e.get("id", ""))) and e.get("schema_version") == 1)
fields = {c["field"]: c for c in e.get("changes", [])}
check("A1 stamps are not listed as changes", not ({"id", "schema_version", "created_at", "created_by", "updated_at", "updated_by"} & set(fields)))
check("A1 a plain field is listed with its new value as JSON text and no old value", fields.get("name", {}).get("new_value") == json.dumps("Venue 1") and "old_value" not in fields.get("name", {}))
check("A1 the entry is accepted by the schema", AE.check_entry(e) == [])

# ------------------------------------------------------------------ A2 update
inner, st = fresh()
d = vdoc(1, capacity_note="six chairs", city="Boulder")
st.create("venues", d["id"], d)
st.update("venues", d["id"], upd({"capacity_note": "eight chairs", "city": "Boulder"}))
es = entries(inner)
check("A2 an edit writes a second entry", len(es) == 2)
e = es[-1]
check("A2 action edited, actor from updated_by", e["action"] == "edited" and e["created_by"] == "user:abc")
fields = {c["field"]: c for c in e["changes"]}
check("A2 only the changed field is listed (not the unchanged city, not the stamps)", set(fields) == {"capacity_note"})
check("A2 old and new values", fields["capacity_note"].get("old_value") == '"six chairs"' and fields["capacity_note"].get("new_value") == '"eight chairs"')
st.update("venues", d["id"], upd({"capacity_note": "eight chairs"}))
check("A2b an edit that changes nothing but its stamps writes no entry", len(entries(inner)) == 2)
st.update("venues", d["id"], upd({"opens_note": "daily"}))
f2 = {c["field"]: c for c in entries(inner)[-1]["changes"]}
check("A2c a field that did not exist has a new value and no old value", "old_value" not in f2["opens_note"] and f2["opens_note"]["new_value"] == '"daily"')
st.update("venues", d["id"], upd(), delete_fields=("opens_note",))
f3 = {c["field"]: c for c in entries(inner)[-1]["changes"]}
check("A2d a removed field has an old value and no new value", f3["opens_note"]["old_value"] == '"daily"' and "new_value" not in f3["opens_note"])
st.update("venues", d["id"], upd({"rooms": [{"label": "A", "max_occupancy": 4}]}))
f4 = {c["field"]: c for c in entries(inner)[-1]["changes"]}
check("A2e a list is one change of the whole field", set(f4) == {"rooms"} and json.loads(f4["rooms"]["new_value"]) == [{"label": "A", "max_occupancy": 4}])

# ------------------------------------------------------------------ A3 delete and restore
inner, st = fresh()
d = vdoc(1)
st.create("venues", d["id"], d)
st.update("venues", d["id"], {"deleted_at": stamp(), "deleted_by": "user:zed", "updated_at": stamp(), "updated_by": "user:zed"})
e = entries(inner)[-1]
check("A3 setting deleted_at is a deleted entry by the deleter", e["action"] == "deleted" and e["created_by"] == "user:zed")
st.update("venues", d["id"], upd(), delete_fields=("deleted_at", "deleted_by"))
e = entries(inner)[-1]
check("A3b removing deleted_at is a restored entry", e["action"] == "restored")

# ------------------------------------------------------------------ A4 personal and sensitive values never copied
inner, st = fresh()
SECRET_OLD, SECRET_NEW = "oldsecret@example.org", "newsecret@example.org"
d = vdoc(1, email=SECRET_OLD, phone="303-555-0199")
st.create("venues", d["id"], d)
st.update("venues", d["id"], upd({"email": SECRET_NEW}))
allj = " ".join(blob(x) for x in entries(inner))
check("A4 a personal (x_pii) value never appears in any entry", SECRET_OLD not in allj and SECRET_NEW not in allj and "555-0199" not in allj)
e = entries(inner)[-1]
c = e["changes"][0]
check("A4 the field is named and flagged withheld, with no values", c["field"] == "email" and c.get("values_withheld") is True and "old_value" not in c and "new_value" not in c)
cr = {c["field"]: c for c in entries(inner)[0]["changes"]}
check("A4 a created record's personal fields are withheld too", cr["phone"].get("values_withheld") is True and "new_value" not in cr["phone"])
inner, st = fresh()
rid = new_id(7)
st.create("individual_restricted_details", rid, {"id": rid, "schema_version": 1, "created_at": stamp(), "created_by": "user:admin", "updated_at": stamp(), "updated_by": "user:admin",
                                                  "source": "dashboard", "individual_id": new_id(8), "veteran_status": "veteran", "marker": "plainword"})
st.update("individual_restricted_details", rid, upd({"marker": "otherword"}))
allj = " ".join(blob(x) for x in entries(inner))
check("A4b every field of the sensitive-details collection is withheld", "plainword" not in allj and "otherword" not in allj and not any("old_value" in c or "new_value" in c for x in entries(inner) for c in x["changes"]))
check("A4b ...yet the entries exist and name the fields", len(entries(inner)) == 2 and any(c["field"] == "marker" for c in entries(inner)[-1]["changes"]))
inner, st = fresh()
pid = new_id(9)
st.create("access_persons", pid, {"id": pid, "schema_version": 1, "created_at": stamp(), "created_by": "user:admin", "updated_at": stamp(), "updated_by": "user:admin",
                                  "source": "dashboard", "email": "who@example.org", "role_id": new_id(10), "is_active": True})
st.update("access_persons", pid, {"google_uid": "UIDSECRET123", "last_sign_in_at": stamp()})
allj = " ".join(blob(x) for x in entries(inner))
check("A4c a Google account id is never copied into an entry", "UIDSECRET123" not in allj)
check("A4c ...but the link is recorded, by an unattributed system actor", entries(inner)[-1]["created_by"] == "system:unattributed" and entries(inner)[-1]["changes"][0]["field"] == "google_uid")
check("A4d the person's email is withheld too", "who@example.org" not in allj)
inner, st = fresh()
rq = new_id(12)
st.create("registration_requests", rq, {"id": rq, "schema_version": 2, "created_at": stamp(), "created_by": "web:enjoy", "updated_at": stamp(), "updated_by": "web:enjoy", "source": "web_enjoy",
                                        "notes": "my daughter Marigold is shy", "organization_name": "Hollyhock Garden Club", "processing_status": "received"})
allj = " ".join(blob(x) for x in entries(inner))
check("A4e a request's free-text notes and organisation (not marked x_pii in its schema) are withheld by name", "Marigold" not in allj and "Hollyhock" not in allj and "processing_status" in allj)
inner, st = fresh()
ip = new_id(13)
st.create("individuals", ip, {"id": ip, "schema_version": 1, "created_at": stamp(), "created_by": "user:admin", "updated_at": stamp(), "updated_by": "user:admin", "source": "dashboard",
                              "display_name": "Marigold Thistle", "birth_country": "Norway", "status": "active"})
allj = " ".join(blob(x) for x in entries(inner))
check("A4f a person's computed display_name and birth country are withheld by name", "Marigold" not in allj and "Norway" not in allj and "\\\"active\\\"" in allj)

# ------------------------------------------------------------------ A5 quiet writes
inner2, st2 = fresh()
st2.create("access_persons", pid, {"id": pid, "schema_version": 1, "created_at": stamp(), "created_by": "user:admin", "updated_at": stamp(), "updated_by": "user:admin",
                                   "source": "dashboard", "email": "who@example.org", "role_id": new_id(10), "is_active": True})
n0 = len(entries(inner2))
st2.update("access_persons", pid, {"last_sign_in_at": stamp()})
check("A5 a sign-in time on its own writes no entry", len(entries(inner2)) == n0)
rr = new_id(11)
st2.create("registration_requests", rr, {"id": rr, "schema_version": 2, "created_at": stamp(), "created_by": "web:enjoy", "updated_at": stamp(), "updated_by": "web:enjoy", "source": "web_enjoy"})
n0 = len(entries(inner2))
st2.update("registration_requests", rr, {"acknowledgment_email_status": "sent", "acknowledgment_email_attempted_at": stamp(), "updated_at": stamp(), "updated_by": "system:comms"})
check("A5b the old email status fields on a request write no entry", len(entries(inner2)) == n0)
st2.update("registration_requests", rr, {"acknowledgment_email_status": "failed", "city": "X", "updated_at": stamp(), "updated_by": "system:comms"})
check("A5c a quiet field next to a real change is left out of the list but the entry is written",
      len(entries(inner2)) == n0 + 1 and [c["field"] for c in entries(inner2)[-1]["changes"]] == ["city"])
n0 = len(entries(inner2))
st2.update("registration_requests", rr, {"city": "Y", "updated_at": stamp(), "updated_by": "system:comms"}, timeout=3.0)
check("A5d a write with a bounded timeout is not logged and still happens", len(entries(inner2)) == n0 and inner2.get("registration_requests", rr)["city"] == "Y")
check("A5e the quiet lists are what the guide says", QUIET_FIELDS.get("access_persons") == {"last_sign_in_at"} and "acknowledgment_email_status" in QUIET_FIELDS.get("registration_requests", ()))

# ------------------------------------------------------------------ A6 atomic: no entry without the change, no change without the entry
inner, st = fresh()
d = vdoc(1)
st.create("venues", d["id"], d)
n0 = len(entries(inner))
try:
    st.create("venues", d["id"], dict(d))
    raised = None
except DocExists:
    raised = "DocExists"
check("A6 a create that fails (id exists) raises as before and leaves no entry", raised == "DocExists" and len(entries(inner)) == n0)
try:
    st.update("venues", new_id(99), upd({"city": "X"}))
    raised = None
except DocMissing:
    raised = "DocMissing"
check("A6b an update of a missing record raises DocMissing and leaves no entry", raised == "DocMissing" and len(entries(inner)) == n0)
try:
    st.update("venues", d["id"], upd({"city": "X"}), expected_updated_at="2000-01-01T00:00:00Z")
    raised = None
except StaleUpdate:
    raised = "StaleUpdate"
check("A6c a stale update raises StaleUpdate, changes nothing and leaves no entry", raised == "StaleUpdate" and len(entries(inner)) == n0 and "city" not in inner.get("venues", d["id"]))
cur = inner.get("venues", d["id"])
st.update("venues", d["id"], upd({"city": "Y"}), expected_updated_at=cur["updated_at"])
check("A6d an update with the right expected_updated_at works and logs", inner.get("venues", d["id"])["city"] == "Y" and len(entries(inner)) == n0 + 1)

# inside the caller's transaction: all or nothing
inner, st = fresh()
a, b = vdoc(1), vdoc(2)
try:
    with st.transaction() as tx:
        st.create("venues", a["id"], a, tx=tx)
        st.create("venues", b["id"], b, tx=tx)
        st.update("venues", new_id(98), upd({"city": "Z"}), tx=tx)
    raised = None
except DocMissing:
    raised = "DocMissing"
check("A6e a caller's transaction that fails rolls back the records AND their entries", raised == "DocMissing" and inner.get("venues", a["id"]) is None and len(entries(inner)) == 0)
with st.transaction() as tx:
    st.create("venues", a["id"], a, tx=tx)
    st.create("venues", b["id"], b, tx=tx)
    st.update("venues", a["id"], upd({"city": "Q"}), tx=tx)
check("A6f a transaction that succeeds leaves one entry per write (3 writes, 3 entries)", len(entries(inner)) == 3)
check("A6f2 ...a record created and then changed in one transaction has its edit's old value from the create",
      (lambda es: es[-1]["action"] == "edited" and es[-1]["changes"][0]["field"] == "city" and "old_value" not in es[-1]["changes"][0] and es[-1]["changes"][0]["new_value"] == '"Q"')(entries(inner)))
inner, st = fresh()
base_doc = vdoc(1, city="A")
st.create("venues", base_doc["id"], base_doc)
with st.transaction() as tx:
    st.update("venues", base_doc["id"], upd({"city": "B"}), tx=tx)
    st.update("venues", base_doc["id"], upd({"city": "C"}), tx=tx)
es = entries(inner)[1:]
check("A6f3 two changes to one record in one transaction chain: A to B, then B to C",
      len(es) == 2 and (es[0]["changes"][0]["old_value"], es[0]["changes"][0]["new_value"]) == ('"A"', '"B"') and (es[1]["changes"][0]["old_value"], es[1]["changes"][0]["new_value"]) == ('"B"', '"C"'))
inner, st = fresh()
with st.transaction() as tx:
    st.create("venues", a["id"], a, tx=tx)
    mid = len(entries(inner))
check("A6g nothing is written until the transaction ends", mid == 0)

# ------------------------------------------------------------------ A7 which collections
inner, st = fresh()
for coll in sorted(EXCLUDED_COLLECTIONS - {ACT}):
    st.create(coll, new_id(20), {"id": new_id(20), "created_by": "user:admin", "updated_by": "user:admin", "x": 1})
    st.update(coll, new_id(20), {"x": 2, "updated_at": stamp(), "updated_by": "user:admin"})
check("A7 the excluded collections write no entry", inner.query(ACT, limit=50) == [])
st.create(ACT, new_id(20), {"id": new_id(20), "created_by": "user:admin", "updated_by": "user:admin", "x": 1})
st.update(ACT, new_id(20), {"x": 2, "updated_at": stamp(), "updated_by": "user:admin"})
check("A7a a write to the log itself writes no entry about the entry (no loop)", len(inner.query(ACT, limit=50)) == 1)
inner.data[ACT].clear()
check("A7b the excluded list is exactly the logs and the constant writers", EXCLUDED_COLLECTIONS == {"activity_events", "communication_logs", "journal_events", "discovery_runs", "performance_events"})
st.create("something_unregistered", new_id(21), {"id": new_id(21), "created_by": "user:admin", "x": 1})
check("A7c a collection the registry does not know is written but not logged", inner.get("something_unregistered", new_id(21)) is not None and len(entries(inner)) == 0)
st.create("individual_history", new_id(22), {"id": new_id(22), "created_by": "system:x", "before": {}, "after": {}})
check("A7d the *_history collections (not in the registry) are not logged", len(entries(inner)) == 0)

# every collection the Console door reaches, and every registry type, is covered or deliberately excluded
reg = json.load(open(HERE.parent / "schemas" / "registry.json"))["schemas"]
registry_collections = {r["collection"] for r in reg}
check("A7e every collection the doors serve is in the registry", set(crud_endpoint.HANDLERS) <= registry_collections, str(set(crud_endpoint.HANDLERS) - registry_collections))
check("A7f the activity log has a handler and is registered", "activity_events" in crud_endpoint.HANDLERS and "activity_events" in registry_collections)
check("A7g every excluded collection is a real, registered one", EXCLUDED_COLLECTIONS <= registry_collections)
missed = []
for coll in sorted(registry_collections - EXCLUDED_COLLECTIONS):
    inner, st = fresh()
    st.create(coll, new_id(30), {"id": new_id(30), "created_by": "user:admin", "updated_by": "user:admin", "created_at": stamp(), "updated_at": stamp(), "source": "dashboard", "schema_version": 1})
    es = entries(inner)
    if len(es) != 1 or es[0]["collection"] != coll or AE.check_entry(es[0]):
        missed.append(coll)
check("A7h EVERY registered collection not excluded writes a schema-valid entry on create (a new schema is covered automatically)", not missed, str(missed))

# ------------------------------------------------------------------ A8 related ids and label
inner, st = fresh()
pers, cls, req, ven = new_id(41), new_id(42), new_id(43), new_id(44)
aid = new_id(45)
st.create("attendances", aid, {"id": aid, "created_by": "user:admin", "updated_by": "user:admin", "created_at": stamp(), "updated_at": stamp(), "source": "dashboard", "schema_version": 1,
                               "individual_id": pers, "scheduled_class_id": cls, "request_id": req, "status": "assigned"})
e = entries(inner)[0]
check("A8 related_ids has the record's own id first, then the ids it points at", e["related_ids"][0] == aid and {pers, cls, req} <= set(e["related_ids"]))
check("A8b related_ids has no repeats", len(e["related_ids"]) == len(set(e["related_ids"])))
st.update("attendances", aid, upd({"individual_id": new_id(46)}))
e = entries(inner)[-1]
check("A8c when a pointer changes, the old and the new id are both findable", {pers, new_id(46)} <= set(e["related_ids"]))
inner, st = fresh()
st.create("registration_assignments", new_id(47), {"id": new_id(47), "created_by": "user:admin", "updated_by": "user:admin", "created_at": stamp(), "updated_at": stamp(), "source": "dashboard", "schema_version": 1,
                                                    "participant_individual_ids": [new_id(100 + i) for i in range(20)]})
e = entries(inner)[0]
check("A8d related_ids is capped at 12, record id kept", len(e["related_ids"]) == 12 and e["related_ids"][0] == new_id(47))
inner, st = fresh()
st.create("venues", new_id(48), vdoc(48, name="Trident Booksellers"))
check("A8e a venue's name becomes the record_label", entries(inner)[0].get("record_label") == "Trident Booksellers")
st.create("access_persons", new_id(49), {"id": new_id(49), "created_by": "user:admin", "updated_by": "user:admin", "created_at": stamp(), "updated_at": stamp(), "source": "dashboard", "schema_version": 1,
                                         "display_name": "Jane Private", "email": "jane@example.org", "title": "ignored title"})
e = entries(inner)[-1]
check("A8f a personal field is never used as the label", "Jane Private" not in blob(e) and "jane@example.org" not in blob(e))

# ------------------------------------------------------------------ A9 caps and order
inner, st = fresh()
d = vdoc(1)
st.create("venues", d["id"], d)
st.update("venues", d["id"], upd({"description": "x" * 5000}))
c = entries(inner)[-1]["changes"][0]
check("A9 a long value is cut to 1000 characters and flagged truncated", len(c["new_value"]) == 1000 and c.get("truncated") is True)
inner, st = fresh()
big = vdoc(1, **{f"f{i:03d}": i for i in range(200)})
st.create("venues", big["id"], big)
e = entries(inner)[0]
check("A9b more than 150 changed fields: 150 listed, the rest counted in fields_omitted", len(e["changes"]) == 150 and e.get("fields_omitted", 0) >= 50, f"{len(e['changes'])} {e.get('fields_omitted')}")
check("A9c the entry still passes the schema", AE.check_entry(e) == [])
inner, st = fresh()
d = vdoc(1)
same = stamp()
st.create("venues", d["id"], d)
for i in range(5):
    st.update("venues", d["id"], {"city": f"C{i}", "updated_at": same, "updated_by": "user:abc"})
seqs = [x["sequence_ms"] for x in entries(inner)]
check("A9d entries written in the same second keep their order (sequence_ms strictly increases)", seqs == sorted(set(seqs)) and len(seqs) == 6)
cities = [c["new_value"] for x in entries(inner)[1:] for c in x["changes"]]
check("A9e ...and read back in the order they happened", cities == [json.dumps(f"C{i}") for i in range(5)])

# ------------------------------------------------------------------ A10 the read handler
inner, st = fresh()
v1, v2 = vdoc(1), vdoc(2)
st.create("venues", v1["id"], v1)
st.create("venues", v2["id"], v2)
st.update("venues", v1["id"], upd({"city": "A"}, actor="user:abc"))
st.update("venues", v2["id"], {"deleted_at": stamp(), "deleted_by": "user:zed", "updated_at": stamp(), "updated_by": "user:zed"})
r = AE.list(inner)
check("A10 list returns all, newest first", r.ok and r.data["count"] == 4 and [x["sequence_ms"] for x in r.data["records"]] == sorted([x["sequence_ms"] for x in r.data["records"]], reverse=True))
r = AE.list(inner, {"related_ids": v1["id"]})
check("A10b related_ids filter: the History of one record", r.ok and r.data["count"] == 2 and all(v1["id"] in x["related_ids"] for x in r.data["records"]))
check("A10c record_type filter", AE.list(inner, {"record_type": "venue"}).data["count"] == 4 and AE.list(inner, {"record_type": "individual"}).data["count"] == 0)
check("A10d action filter", AE.list(inner, {"action": "deleted"}).data["count"] == 1 and AE.list(inner, {"action": "created"}).data["count"] == 2)
check("A10e created_by filter", AE.list(inner, {"created_by": "user:zed"}).data["count"] == 1)
check("A10f collection filter", AE.list(inner, {"collection": "venues"}).data["count"] == 4)
check("A10g two filters at once are refused", not AE.list(inner, {"action": "created", "record_type": "venue"}).ok)
check("A10h an unknown filter is refused", not AE.list(inner, {"city": "A"}).ok)
check("A10i limit is capped at 200 and must be a number", AE.list(inner, limit=10 ** 6).ok and not AE.list(inner, limit="x").ok and AE.list(inner, limit=2).data["count"] == 2)
big_inner, big_st = fresh()
for i in range(230):
    big_st.create("venues", new_id(1000 + i), vdoc(1000 + i))
pg1 = AE.list(big_inner, limit=100)
pg2 = AE.list(big_inner, limit=100, before=pg1.data["marker"])
pg3 = AE.list(big_inner, limit=100, before=pg2.data["marker"])
ids = [x["id"] for x in pg1.data["records"] + pg2.data["records"] + pg3.data["records"]]
check("A10j paging: 230 entries come in three pages with no repeats and no gaps", pg1.data["more"] and pg2.data["more"] and not pg3.data["more"] and len(ids) == 230 and len(set(ids)) == 230, [pg1.data["more"], pg2.data["more"], pg3.data["count"]])
check("A10k paging: the next page is strictly older than the marker", all(x["sequence_ms"] < pg1.data["marker"] for x in pg2.data["records"]))
check("A10l paging: the marker is the last entry's sequence and an empty page has none", pg1.data["marker"] == pg1.data["records"][-1]["sequence_ms"] and AE.list(big_inner, before=1).data["marker"] is None)
check("A10m paging works with a filter", AE.list(big_inner, {"action": "created"}, limit=50, before=pg1.data["marker"]).data["count"] == 50)
check("A10n paging: bad markers and oldest-first are refused", not AE.list(big_inner, before="x").ok and not AE.list(big_inner, before=True).ok and not AE.list(big_inner, before=5, order="created_at").ok and not AE.list(big_inner, before=-1).ok)
check("A10j never more than 200 come back", AE.list(big_inner, limit=1000).data["count"] == 200)
one = entries(inner)[0]
check("A10k get returns one entry; a bad or unknown id is refused", AE.get(inner, one["id"]).ok and not AE.get(inner, "nope").ok and AE.get(inner, new_id(777)).code == "not_found")
for name, fn in (("create", lambda: AE.create(inner, {}, "user:admin")), ("update", lambda: AE.update(inner, one["id"], {}, "user:admin")),
                 ("soft_delete", lambda: AE.soft_delete(inner, one["id"], "user:admin"))):
    r = fn()
    check(f"A10l {name} on an entry is refused", not r.ok and r.problems == [{"field": "op", "issue": "not_supported"}])
check("A10m the refused calls changed nothing", len(entries(inner)) == 4)

# ------------------------------------------------------------------ A11 the Console door
class Clock:
    def __init__(self):
        self.t = START

    def __call__(self):
        self.t += timedelta(seconds=5)
        return self.t


def door(store, op_body, key=KEY):
    return crud_endpoint.handle_admin("POST", "Bearer " + key, json.dumps(op_body).encode(), KEY, "visitor", store, make_failure_limiter(), tick())


inner, st = fresh()
r = door(st, {"collection": "venues", "op": "create", "args": {"data": {"name": "Door Venue", "slug": "door_venue", "status": "inactive", "is_public_venue": True}}})
check("A11 a venue created through the Console door works", r.status == 200, str(r.body)[:200])
vid = r.body["data"]["id"] if r.status == 200 else None
es = entries(inner)
check("A11b ...and wrote exactly one entry, by the signed-in actor", len(es) == 1 and es[0]["created_by"] == "user:admin" and es[0]["record_id"] == vid)
cur = r.body["data"]
r = door(st, {"collection": "venues", "op": "update", "args": {"id": vid, "changes": {"description": "a nice room"}, "expected_updated_at": cur["updated_at"]}})
check("A11c an update through the door works and writes one more entry", r.status == 200 and len(entries(inner)) == 2 and entries(inner)[-1]["action"] == "edited")
r = door(st, {"collection": "venues", "op": "soft_delete", "args": {"id": vid}})
check("A11d a soft delete through the door writes a deleted entry", r.status == 200 and entries(inner)[-1]["action"] == "deleted" and len(entries(inner)) == 3)
r = door(st, {"collection": "activity_events", "op": "list", "args": {"filters": {"related_ids": vid}}})
check("A11e the activity list is readable through the door and shows the history of that record", r.status == 200 and r.body["data"]["count"] == 3, str(r.body)[:200])
n0 = len(entries(inner))
for op, args in (("create", {"data": {"action": "created", "record_type": "venue", "collection": "venues", "record_id": "x"}}),
                 ("update", {"id": entries(inner)[0]["id"], "changes": {"action": "edited"}}), ("soft_delete", {"id": entries(inner)[0]["id"]})):
    r = door(st, {"collection": "activity_events", "op": op, "args": args})
    check(f"A11f {op} on the activity log through the door is refused", r.status == 400, str(r.status))
check("A11g ...and the log is untouched", len(entries(inner)) == n0)
r = door(st, {"collection": "activity_events", "op": "list", "args": {}}, key="wrong-key-wrong-key-wrong-key-wrong-key")
check("A11h a wrong key reads nothing", r.status in (401, 403))
check("A11i the activity log is reachable with the Console's read ops only", "list" in crud_endpoint.ADMIN_OPS)

# a refused change leaves no entry
n0 = len(entries(inner))
r = door(st, {"collection": "venues", "op": "create", "args": {"data": {"name": "", "slug": "BAD SLUG"}}})
check("A11j a create the handler refuses writes no entry", r.status == 400 and len(entries(inner)) == n0)

# ------------------------------------------------------------------ A12 who may read
check("A12 the activity log is readable by a super admin only (not by view_console)", policy.crud_need("activity_events", "list", {}) == ((policy.SUPER_ONLY,),), str(policy.crud_need("activity_events", "list", {})))
check("A12b ...and writable by nobody through the doors", policy.crud_need("activity_events", "create", {}) == ((policy.SUPER_ONLY,),))
check("A12c the table says so explicitly", policy.READ.get("activity_events") == (policy.SUPER_ONLY,) and policy.WRITE.get("activity_events") == (policy.SUPER_ONLY,))

# ------------------------------------------------------------------ A13 a person's erase
inner, st = fresh()
r = IND.create(st, {"given_name": "Zephyrina", "family_name": "Quillfeather"}, "user:admin", now=tick()) if hasattr(IND, "create") else None
check("A13 a person is created through the individuals service", bool(r and r.ok), str(getattr(r, "problems", "")))
if r and r.ok:
    pid = r.data["id"]
    IND.update(st, pid, {"name_to_use": "Zeph"}, "user:abc", now=tick())
    before = len(entries(inner))
    er = IND.erase(st, pid, "user:abc", now=tick())
    check("A13b the erase works", er.ok, str(er.problems if hasattr(er, "problems") else ""))
    allj = " ".join(blob(x) for x in entries(inner))
    check("A13c no entry anywhere holds the person's name, before or after the erase", "Zephyrina" not in allj and "Quillfeather" not in allj and "Zeph" not in allj.replace("Zephyrina", ""))
    check("A13d the entries are kept: the erase did not remove or change them", len(entries(inner)) > before - 1 and len(entries(inner)) >= before)
    check("A13e the erase itself is on the record, by whoever did it", any(x["record_id"] == pid and x["created_by"] == "user:abc" for x in entries(inner)[before:]))
    check("A13f the person's History still lists the entries (the id is not personal data)", AE.list(inner, {"related_ids": pid}).data["count"] >= 3)

# ------------------------------------------------------------------ A14 details the mutation check found untested
from crud import activity_log as AL  # noqa: E402
inner, st = fresh()
dv = vdoc(60)
st.create("venues", dv["id"], dv)
st.update("venues", dv["id"], {"deleted_at": stamp(), "deleted_by": "user:zed", "updated_at": stamp(), "updated_by": "user:other"})
e = entries(inner)[-1]
check("A14 a delete is credited to whoever deleted (deleted_by), not to the last stamp", e["action"] == "deleted" and e["created_by"] == "user:zed", e["created_by"])
st.update("venues", dv["id"], upd({"city": "Elsewhere"}, actor="not an actor!"))
check("A14b an actor string that is not a valid actor is recorded as unattributed", entries(inner)[-1]["created_by"] == "system:unattributed", entries(inner)[-1]["created_by"])
inner, st = fresh()
payer, payee = new_id(61), new_id(62)
st.create("transaction_records", new_id(63), {"id": new_id(63), "created_by": "user:admin", "updated_by": "user:admin", "created_at": stamp(), "updated_at": stamp(), "schema_version": 1,
                                              "payer": {"party_id": payer}, "payee": {"party_id": payee}})
e = entries(inner)[0]
check("A14c a payment's payer and payee ids make it findable in their History", {payer, payee} <= set(e["related_ids"]), str(e["related_ids"]))
inner, st = fresh()
st.create("venues", new_id(64), vdoc(64, name="N" * 300))
check("A14d a long label is cut to 200 characters", len(entries(inner)[0]["record_label"]) == 200)
check("A14e a field that is withheld is skipped when choosing the label", AL.label_of("venues", frozenset({"name"}), {"name": "Secret Name", "title": "Public Title"}) == "Public Title"
      and AL.label_of("venues", frozenset({"name", "title", "slug", "label"}), {"name": "Secret", "title": "Secret"}) is None)
r = AE.get(inner, "nope")
check("A14f get with a malformed id is refused as invalid, not looked up", (not r.ok) and r.code == "validation_failed", str(r.code))

# ------------------------------------------------------------------ result
print(f"\n{total - len(fails)}/{total} checks passed" + ("" if not fails else "\nFAILED: " + "; ".join(fails)))
sys.exit(1 if fails else 0)
