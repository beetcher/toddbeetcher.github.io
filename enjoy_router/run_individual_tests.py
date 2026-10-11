#!/usr/bin/env python3
"""In-memory tests for the individual handler files (crud/individuals_crud.py, crud/individual_restricted_details_crud.py).
Run from enjoy_router/:  python3 run_individual_tests.py   (add -v to list every check)

Needs the `jsonschema` library. Reads schemas/examples/individual*.examples.json. Nothing here touches Firebase."""
import copy
import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import individual_restricted_details_crud as R  # noqa: E402
from crud import individuals_crud as I  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402

EX = json.loads((HERE.parent / "schemas" / "examples" / "individual.examples.json").read_text())
RX = json.loads((HERE.parent / "schemas" / "examples" / "individual_restricted_detail.examples.json").read_text())
START = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
later = lambda m: START + timedelta(minutes=m)
fails: list = []
total = 0


def check(label, ok, detail=""):
    global total
    total += 1
    if not ok:
        fails.append(label)
    if not ok or "-v" in sys.argv:
        print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")


def fresh():
    return MemoryDocStore("test_")


def pairs(problems):
    return sorted(f"{p['field']}:{p['issue']}" for p in problems)


def mk(store, body, **kw):
    r = I.create(store, copy.deepcopy(body), "user:todd", now=START, **kw)
    assert r.ok, (body, r)
    return r.data


# ---------------------------------------------------------------------------
# 1. Every example in individual.examples.json, through create()
# ---------------------------------------------------------------------------
for name, body in EX["valid"].items():
    r = I.create(fresh(), copy.deepcopy(body), "user:todd", now=START)
    check(f"valid example creates: {name}", r.ok, str(r.problems))
for name, body in EX["invalid"].items():
    s = fresh()
    r = I.create(s, copy.deepcopy(body), "user:todd", now=START)
    if name == "null_value":  # the handler treats null like blank: the field is left out (SCHEMA_RULES section 3); only the bare schema refuses null
        check("null is dropped like blank, not stored", r.ok and "family_name" not in r.data)
        continue
    check(f"invalid example refused: {name}", (not r.ok) and r.code == "validation_failed" and r.problems, str(r))
    check(f"invalid example stored nothing: {name}", not s.data.get("test_individuals"))
    check(f"problems carry no values: {name}", all(set(p) == {"field", "issue"} for p in r.problems))

# ---------------------------------------------------------------------------
# 2. Defaults and derived fields
# ---------------------------------------------------------------------------
s = fresh()
d = mk(s, {"given_name": "Pat"})
check("defaults: status active", d["status"] == "active")
check("defaults: life_status alive", d["life_status"] == "alive")
check("defaults: display_name from given_name", d["display_name"] == "Pat")
check("defaults: retention active_participant", d["retention_class"] == "active_participant")
check("defaults: no is_minor without birth_date", "is_minor" not in d)
check("server fields stamped", all(k in d for k in I.INDIVIDUALS.server_required), str(d.keys()))
check("source recorded", d["source"] == "dashboard" and d["created_by"] == "user:todd")
check("schema_version 1", d["schema_version"] == 1)
check("id is the document id", s.get("individuals", d["id"])["id"] == d["id"])
check("no nulls stored", None not in d.values())
check("display_name: given and family", mk(fresh(), {"given_name": "Maria", "family_name": "Garcia Lopez"})["display_name"] == "Maria Garcia Lopez")
check("display_name: name_to_use wins", mk(fresh(), {"given_name": "Maria", "family_name": "Garcia", "name_to_use": "Mari"})["display_name"] == "Mari")
check("blank strings dropped", "family_name" not in mk(fresh(), {"given_name": " Pat ", "family_name": "   "}))
check("given_name trimmed", mk(fresh(), {"given_name": " Pat "})["given_name"] == "Pat")
check("country uppercased", mk(fresh(), {"given_name": "Pat", "birth_country": "mx"})["birth_country"] == "MX")
check("web_enjoy source allowed", I.create(fresh(), {"given_name": "Pat"}, "web:enjoy", source="web_enjoy", now=START).ok)
check("bad source refused", not I.create(fresh(), {"given_name": "Pat"}, "user:todd", source="hacker", now=START).ok)
check("bad actor refused", pairs(I.create(fresh(), {"given_name": "Pat"}, "todd", now=START).problems) == ["actor:invalid_format"])
check("body must be an object", pairs(I.create(fresh(), "x", "user:todd", now=START).problems) == ["body:invalid_type"])

# minors and retention
check("minor by full date", mk(fresh(), {"given_name": "K", "birth_date": "2015-06-01"})["is_minor"] is True)
check("adult by full date", mk(fresh(), {"given_name": "A", "birth_date": "1961-04-17"})["is_minor"] is False)
check("turns 18 today is adult", I.is_minor_from("2008-10-10", START) is False)
check("turns 18 tomorrow is minor", I.is_minor_from("2008-10-11", START) is True)
check("year only, could be 17: minor", I.is_minor_from("2008", START) is True)
check("year only, surely adult", I.is_minor_from("2007", START) is False)
check("month only, birth month not over: minor", I.is_minor_from("2008-10", START) is True)
check("month only, 18 plus a month: adult", I.is_minor_from("2008-09", START) is False)
check("no date: unknown", I.is_minor_from(None, START) is None)
check("minor retention class", mk(fresh(), {"given_name": "K", "birth_date": "2015"})["retention_class"] == "minor_review_at_18")
check("deceased retention class", mk(fresh(), {"given_name": "E", "life_status": "deceased", "death_date": "2025", "death_evidence": "document"})["retention_class"] == "deceased_review")
check("explicit retention kept", mk(fresh(), {"given_name": "A", "retention_class": "financial_7y"})["retention_class"] == "financial_7y")

# ---------------------------------------------------------------------------
# 3. Rules the schema cannot say
# ---------------------------------------------------------------------------
def create_issue(body):
    return pairs(I.create(fresh(), body, "user:todd", now=START).problems)

check("Feb 30 refused", create_issue({"given_name": "P", "birth_date": "1961-02-30"}) == ["birth_date:invalid_format"])
check("Feb 29 leap year ok", I.create(fresh(), {"given_name": "P", "birth_date": "1960-02-29"}, "user:todd", now=START).ok)
check("Feb 29 non leap refused", create_issue({"given_name": "P", "birth_date": "1961-02-29"}) == ["birth_date:invalid_format"])
check("future birth date refused", create_issue({"given_name": "P", "birth_date": "2026-10-11"}) == ["birth_date:out_of_range"])
check("future birth year refused", create_issue({"given_name": "P", "birth_date": "2027"}) == ["birth_date:out_of_range"])
check("this year ok", I.create(fresh(), {"given_name": "P", "birth_date": "2026"}, "user:todd", now=START).ok)
check("death before birth refused", create_issue({"given_name": "P", "birth_date": "1961-04-17", "life_status": "deceased", "death_evidence": "document", "death_date": "1961-04-16"}) == ["death_date:out_of_range"])
check("death same year as birth (year precision) ok", I.create(fresh(), {"given_name": "P", "birth_date": "1961-04-17", "life_status": "deceased", "death_evidence": "document", "death_date": "1961"}, "user:todd", now=START).ok)
check("future death refused", create_issue({"given_name": "P", "life_status": "deceased", "death_evidence": "document", "death_date": "2030"}) == ["death_date:out_of_range"])
check("sender cannot set merged", create_issue({"given_name": "P", "status": "merged"}) == ["status:invalid_value"])
check("sender cannot set erased", create_issue({"given_name": "P", "status": "erased"}) == ["status:invalid_value"])
check("sender may set inactive", mk(fresh(), {"given_name": "P", "status": "inactive"})["status"] == "inactive")
check("sender cannot send is_minor", create_issue({"given_name": "P", "is_minor": False}) == ["is_minor:not_allowed"])
check("sender cannot send merged_into_id", create_issue({"given_name": "P", "merged_into_id": "3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b"}) == ["merged_into_id:not_allowed"])

# ---------------------------------------------------------------------------
# 4. get / list / merged redirect
# ---------------------------------------------------------------------------
s = fresh()
a = mk(s, {"given_name": "Zed"})
b = mk(s, {"given_name": "Amy"})
c = mk(s, {"given_name": "Ina", "status": "inactive"})
check("get returns record", I.get(s, a["id"]).data["given_name"] == "Zed")
check("get bad id", pairs(I.get(s, "nope").problems) == ["id:invalid_format"])
check("get missing", I.get(s, "3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b").code == "not_found")
check("list ordered by display_name", [x["given_name"] for x in I.list(s).data["records"]] == ["Amy", "Ina", "Zed"])
check("list filter status", [x["given_name"] for x in I.list(s, {"status": "inactive"}).data["records"]] == ["Ina"])
check("list newest first", I.list(s, order="-created_at").ok)
check("list two filters refused", not I.list(s, {"status": "active", "life_status": "alive"}).ok)
check("list unknown filter refused", pairs(I.list(s, {"given_name": "Amy"}).problems) == ["given_name:not_supported"])
check("list bad status value", pairs(I.list(s, {"status": "gone"}).problems) == ["status:invalid_value"])
check("list filter with -created_at refused", not I.list(s, {"status": "active"}, order="-created_at").ok)
check("list limit type", pairs(I.list(s, limit="5").problems) == ["limit:invalid_type"])
# merged redirect (the merge handler does not exist yet; set the fields the way it will)
s.update("individuals", b["id"], {"status": "merged", "merged_into_id": a["id"]})
check("get follows merged", I.get(s, b["id"]).data["id"] == a["id"])
check("get can show the merged record itself", I.get(s, b["id"], follow_merged=False).data["status"] == "merged")
check("list hides merged by default", b["id"] not in [x["id"] for x in I.list(s).data["records"]])
check("list status merged shows them", [x["id"] for x in I.list(s, {"status": "merged"}).data["records"]] == [b["id"]])
r = I.update(s, b["id"], {"notes": "x"}, "user:todd", now=later(5))
check("merged record is locked", (not r.ok) and r.code == "conflict" and pairs(r.problems) == ["status:locked"], str(r))
s.update("individuals", a["id"], {"merged_into_id": b["id"], "status": "merged"})
check("merge loop ends in server_error", I.get(s, a["id"]).code == "server_error")

# ---------------------------------------------------------------------------
# 5. update
# ---------------------------------------------------------------------------
s = fresh()
d = mk(s, {"given_name": "Maria", "family_name": "Garcia", "birth_date": "1961-04-17", "eye_color_left": "brown"})
r = I.update(s, d["id"], {"family_name": "Lopez", "eye_color_left": "hazel"}, "user:ann", now=later(10))
check("update ok", r.ok, str(r))
cur = s.get("individuals", d["id"])
check("update recomputes display_name", cur["display_name"] == "Maria Lopez")
check("update stamps actor and time", cur["updated_by"] == "user:ann" and cur["updated_at"] != d["updated_at"])
check("update keeps created fields", cur["created_by"] == "user:todd" and cur["created_at"] == d["created_at"])
hist = list(s.data["test_individual_history"].values())
check("update wrote one history record", len(hist) == 1)
h = hist[0]
check("history before/after", h["before"] == {"family_name": "Garcia", "eye_color_left": "brown"} and h["after"] == {"family_name": "Lopez", "eye_color_left": "hazel"}, str(h))
check("history names who and which person", h["changed_by"] == "user:ann" and h["individual_id"] == d["id"])
r = I.update(s, d["id"], {"eye_color_left": None, "name_to_use": "Mari"}, "user:ann", now=later(11))
cur = s.get("individuals", d["id"])
check("None removes optional field", r.ok and "eye_color_left" not in cur and r.data["removed"] == ["eye_color_left"])
check("name_to_use sets display_name", cur["display_name"] == "Mari")
r = I.update(s, d["id"], {"name_to_use": ""}, "user:ann", now=later(12))
check("blank removes name_to_use, display_name reverts", r.ok and s.get("individuals", d["id"])["display_name"] == "Maria Lopez")
check("history keeps every update", len(s.data["test_individual_history"]) == 3)
r = I.update(s, d["id"], {"birth_date": "2015-06-01"}, "user:ann", now=later(13))
check("birth date change recomputes is_minor", r.ok and s.get("individuals", d["id"])["is_minor"] is True)
r = I.update(s, d["id"], {"birth_date": None}, "user:ann", now=later(14))
check("removing birth date drops is_minor", r.ok and "is_minor" not in s.get("individuals", d["id"]))
n = len(s.data["test_individual_history"])
bad = lambda ch: I.update(s, d["id"], ch, "user:ann", now=later(20))
check("cannot remove given_name", pairs(bad({"given_name": None}).problems) == ["given_name:required"])
check("cannot set readOnly", pairs(bad({"id": "x"}).problems) == ["id:not_allowed"])
check("cannot set display_name", pairs(bad({"display_name": "x"}).problems) == ["display_name:not_allowed"])
check("cannot set unknown field", pairs(bad({"shoe_size": 9}).problems) == ["shoe_size:not_allowed"])
check("cannot set merged status", pairs(bad({"status": "merged"}).problems) == ["status:invalid_value"])
check("bad value refused", pairs(bad({"eye_color_left": "purple"}).problems) == ["eye_color_left:invalid_value"])
check("bad calendar date refused", pairs(bad({"birth_date": "1961-02-30"}).problems) == ["birth_date:invalid_format"])
check("death field while alive refused", pairs(bad({"death_date": "2020"}).problems) == ["life_status:invalid_value"])
check("deceased needs evidence", pairs(bad({"life_status": "deceased"}).problems) == ["death_evidence:required"])
check("deceased with evidence ok", bad({"life_status": "deceased", "death_evidence": "document"}).ok)
check("empty changes refused", pairs(bad({}).problems) == ["changes:required"])
check("missing id", I.update(s, "3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b", {"notes": "x"}, "user:a", now=later(21)).code == "not_found")
check("failed updates wrote no history", len(s.data["test_individual_history"]) == n + 1)  # only the one deceased update
cur = s.get("individuals", d["id"])
r = I.update(s, d["id"], {"notes": "later"}, "user:bob", expected_updated_at="2000-01-01T00:00:00Z", now=later(30))
check("stale expected_updated_at conflicts", (not r.ok) and r.code == "conflict")
r = I.update(s, d["id"], {"notes": "later"}, "user:bob", expected_updated_at=cur["updated_at"], now=later(31))
check("matching expected_updated_at ok", r.ok)
check("bad expected_updated_at format", pairs(I.update(s, d["id"], {"notes": "x"}, "user:bob", expected_updated_at="yesterday").problems) == ["expected_updated_at:invalid_format"])

# transaction: an update joins the caller's transaction
s2 = fresh()
e = mk(s2, {"given_name": "Tx"})
with s2.transaction() as tx:
    I.update(s2, e["id"], {"notes": "in tx"}, "user:a", tx=tx, now=later(5))
    check("update inside tx not applied until commit", "notes" not in s2.get("individuals", e["id"]))
check("update inside tx applied at commit", s2.get("individuals", e["id"]).get("notes") == "in tx")
check("history written with the tx", len(s2.data["test_individual_history"]) == 1)

# ---------------------------------------------------------------------------
# 6. soft delete
# ---------------------------------------------------------------------------
s = fresh()
d = mk(s, {"given_name": "Del"})
r = I.soft_delete(s, d["id"], "user:todd", now=later(1))
check("soft delete ok", r.ok)
check("deleted record hidden from get", I.get(s, d["id"]).code == "not_found")
check("deleted record visible with include_deleted", I.get(s, d["id"], include_deleted=True).ok)
check("deleted record hidden from list", I.list(s).data["count"] == 0)
check("delete twice is not_found", I.soft_delete(s, d["id"], "user:todd").code == "not_found")
check("update of deleted is not_found", I.update(s, d["id"], {"notes": "x"}, "user:a").code == "not_found")
check("record still stored", s.get("individuals", d["id"]) is not None)

# ---------------------------------------------------------------------------
# 7. Restricted details
# ---------------------------------------------------------------------------
def with_person(body=None):
    s = fresh()
    p = mk(s, body or {"given_name": "Adult", "birth_date": "1961-04-17"})
    return s, p["id"]


def rbody(spec, pid):
    b = copy.deepcopy(spec)
    if "individual_id" in b and b["individual_id"] == "3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b":
        b["individual_id"] = pid
    return b


for name, spec in RX["valid"].items():
    s, pid = with_person()
    r = R.create(s, rbody(spec, pid), "user:todd", now=START)
    check(f"valid restricted example creates: {name}", r.ok, str(r.problems))
for name, spec in RX["invalid"].items():
    s, pid = with_person()
    r = R.create(s, rbody(spec, pid), "user:todd", now=START)
    check(f"invalid restricted example refused: {name}", (not r.ok) and r.code == "validation_failed" and r.problems, str(r))
    check(f"invalid restricted example stored nothing: {name}", not s.data.get("test_individual_restricted_details"))
    check(f"restricted problems carry no values: {name}", all(set(p) == {"field", "issue"} for p in r.problems))

s, pid = with_person()
good = {"individual_id": pid, "purpose": "safety", "consent_ref": "c1", "blood_type_abo": "O", "blood_type_rh": "positive"}
r = R.create(s, dict(good), "user:todd", now=START)
check("restricted create ok", r.ok and r.data["individual_id"] == pid and r.data["source"] == "dashboard")
rid = r.data["id"]
check("restricted server fields", all(k in r.data for k in R.DETAILS.server_required))
check("second record for same individual refused", pairs(R.create(s, dict(good), "user:todd", now=START).problems) == ["individual_id:duplicate"])
check("get_for_individual", R.get_for_individual(s, pid).data["id"] == rid)
check("get_for_individual none", R.get_for_individual(s, "3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b").code == "not_found")
check("restricted get", R.get(s, rid).ok)
check("restricted list by individual", R.list(s, {"individual_id": pid}).data["count"] == 1)
check("restricted list unfiltered", R.list(s).data["count"] == 1)
check("restricted list by purpose", R.list(s, {"purpose": "billing"}).data["count"] == 0)
check("restricted list bad filter", not R.list(s, {"blood_type_abo": "O"}).ok)

# purpose rules
for field, value, purpose in [("blood_type_abo", "A", "registration"), ("skin_tone_scale", "type_2", "billing"),
                              ("sex_recorded", "male", "safety"), ("veteran_status", "yes", "health_care"),
                              ("death_cause", "x", "registration"), ("gender_identity", "x", "billing")]:
    s, pid = with_person()
    r = R.create(s, {"individual_id": pid, "purpose": purpose, "consent_ref": "c1", field: value}, "user:todd", now=START)
    check(f"purpose {purpose} not allowed for {field}", pairs(r.problems) == [f"{field}:purpose_not_allowed"], str(r.problems))
s, pid = with_person()
check("notes allowed for any purpose", R.create(s, {"individual_id": pid, "purpose": "billing", "consent_ref": "c1", "notes": "n"}, "user:todd", now=START).ok)

# individual rules
s = fresh()
check("unknown individual refused", pairs(R.create(s, {"individual_id": "3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b", "purpose": "safety", "consent_ref": "c", "blood_type_abo": "A"}, "user:todd", now=START).problems) == ["individual_id:not_found"])
kid = mk(s, {"given_name": "Kid", "birth_date": "2015"})
check("minor refused (no guardianship yet)", pairs(R.create(s, {"individual_id": kid["id"], "purpose": "safety", "consent_ref": "c", "blood_type_abo": "A"}, "user:todd", now=START).problems) == ["individual_id:minor_needs_guardian"])
gone = mk(s, {"given_name": "Gone"})
I.soft_delete(s, gone["id"], "user:todd", now=START)
check("deleted individual refused", pairs(R.create(s, {"individual_id": gone["id"], "purpose": "safety", "consent_ref": "c", "blood_type_abo": "A"}, "user:todd", now=START).problems) == ["individual_id:not_found"])
check("restricted source web_enjoy refused", not R.create(s, {"individual_id": gone["id"], "purpose": "safety", "consent_ref": "c"}, "web:enjoy", source="web_enjoy", now=START).ok)

# update
s, pid = with_person()
rid = R.create(s, dict(good, individual_id=pid), "user:todd", now=START).data["id"]
r = R.update(s, rid, {"blood_type_abo": "A"}, "user:ann", now=later(5))
check("restricted update ok", r.ok, str(r))
hh = list(s.data["test_individual_restricted_detail_history"].values())
check("restricted history written", len(hh) == 1 and hh[0]["before"] == {"blood_type_abo": "O"} and hh[0]["after"] == {"blood_type_abo": "A"} and hh[0]["individual_id"] == pid, str(hh))
check("individual_id immutable", pairs(R.update(s, rid, {"individual_id": pid}, "user:ann").problems) == ["individual_id:immutable"])
check("cannot remove purpose", pairs(R.update(s, rid, {"purpose": None}, "user:ann").problems) == ["purpose:required"])
check("purpose change that disallows a field refused", pairs(R.update(s, rid, {"purpose": "billing"}, "user:ann").problems) == ["blood_type_abo:purpose_not_allowed", "blood_type_rh:purpose_not_allowed"])
check("cannot drop the whole basis", pairs(R.update(s, rid, {"consent_ref": None}, "user:ann").problems) == ["consent_ref:choose_one", "legal_basis:choose_one"])
check("switching basis in one update ok", R.update(s, rid, {"consent_ref": None, "legal_basis": "vital_interests"}, "user:ann", now=later(6)).ok)
check("cannot set readOnly (restricted)", pairs(R.update(s, rid, {"id": "x"}, "user:ann").problems) == ["id:not_allowed"])
cur = s.get("individual_restricted_details", rid)
check("restricted stale conflict", R.update(s, rid, {"notes": "x"}, "user:a", expected_updated_at="2000-01-01T00:00:00Z", now=later(9)).code == "conflict")
check("restricted update ok with matching stamp", R.update(s, rid, {"notes": "x"}, "user:a", expected_updated_at=cur["updated_at"], now=later(10)).ok)

# soft delete then recreate
r = R.soft_delete(s, rid, "user:todd", now=later(20))
check("restricted soft delete ok", r.ok)
check("restricted deleted hidden", R.get(s, rid).code == "not_found" and R.get_for_individual(s, pid).code == "not_found")
check("new record allowed after delete", R.create(s, dict(good, individual_id=pid, consent_ref="c2"), "user:todd", now=later(21)).ok)
check("restricted delete twice not_found", R.soft_delete(s, rid, "user:todd").code == "not_found")

# ---------------------------------------------------------------------------
# Contact fields: how to reach the person (email, phone, backups, preference). Todd: only format refusals.
from crud import individual_merges_crud as CM  # noqa: E402

s = fresh()
r = I.create(s, {"given_name": "Pat", "email": "Pat@Example.COM", "backup_email": "ALT@Example.org", "phone": "+1 (303) 555-0142", "backup_phone": "303-555-0177", "prefers_email": False}, "user:todd", now=START)
check("contact: all five fields save", r.ok, str(r))
pid = r.data["id"]
rec = s.get("individuals", pid)
check("contact: emails stored lowercase", rec["email"] == "pat@example.com" and rec["backup_email"] == "alt@example.org")
check("contact: phone stored as typed", rec["phone"] == "+1 (303) 555-0142" and rec["prefers_email"] is False)
check("contact: a person with nothing saves (all optional)", I.create(s, {"given_name": "Sam"}, "user:todd", now=START).ok)
check("contact: only an email saves", I.create(s, {"given_name": "Lee", "email": "lee@example.com"}, "user:todd", now=START).ok)
check("contact: bad email refused", pairs(I.create(s, {"given_name": "A", "email": "nope"}, "user:todd", now=START).problems) == ["email:invalid_format"])
check("contact: bad backup email refused", pairs(I.create(s, {"given_name": "A", "backup_email": "nope"}, "user:todd", now=START).problems) == ["backup_email:invalid_format"])
check("contact: bad phone refused", pairs(I.create(s, {"given_name": "A", "phone": "call me"}, "user:todd", now=START).problems) == ["phone:invalid_format"])
check("contact: prefers_email must be true or false", pairs(I.create(s, {"given_name": "A", "prefers_email": "email"}, "user:todd", now=START).problems) == ["prefers_email:invalid_type"])
check("contact: preference with no matching contact is NOT refused", I.create(s, {"given_name": "B", "prefers_email": True, "phone": "303-555-0100"}, "user:todd", now=START).ok)
check("contact: two people may share one email", I.create(s, {"given_name": "C", "email": "pat@example.com"}, "user:todd", now=START).ok)
r = I.update(s, pid, {"email": "NEW@Example.com", "prefers_email": None}, "user:todd", expected_updated_at=rec["updated_at"], now=later(1))
check("contact: update lowercases and a null removes the preference", r.ok and s.get("individuals", pid)["email"] == "new@example.com" and "prefers_email" not in s.get("individuals", pid), str(r))
check("contact: update refuses a bad email", pairs(I.update(s, pid, {"email": "x"}, "user:todd", now=later(2)).problems) == ["email:invalid_format"])

order = lambda d: [(x["kind"], x["to"]) for x in I.contact_order(d)]
check("reach: nothing given, nothing to try", order({}) == [])
check("reach: only an email", order({"email": "a@x.com"}) == [("email", "a@x.com")])
check("reach: only a phone is the preference", order({"phone": "3035550100"}) == [("text", "3035550100")])
check("reach: both given, no preference: email first", order({"email": "a@x.com", "phone": "3035550100"}) == [("email", "a@x.com"), ("text", "3035550100")])
check("reach: prefers text", order({"email": "a@x.com", "phone": "3035550100", "prefers_email": False}) == [("text", "3035550100"), ("email", "a@x.com")])
check("reach: prefers email but has none, so the phone is used", order({"phone": "3035550100", "prefers_email": True}) == [("text", "3035550100")])
check("reach: prefers text but has no phone, so the email is used", order({"email": "a@x.com", "prefers_email": False}) == [("email", "a@x.com")])
check("reach: backups follow their primary", order({"email": "a@x.com", "backup_email": "b@x.com", "phone": "1", "backup_phone": "2"}) == [("email", "a@x.com"), ("email", "b@x.com"), ("text", "1"), ("text", "2")])
check("reach: a missing primary falls back to the backup", order({"backup_email": "b@x.com"}) == [("email", "b@x.com")])

s = fresh()
a = mk(s, {"given_name": "Pat", "family_name": "Rivera", "email": "pat@example.com"})
b = mk(s, {"given_name": "Pat", "family_name": "Rivera", "phone": "303-555-0142", "backup_email": "pat2@example.com", "prefers_email": False})
m = CM.merge(s, a["id"], b["id"], "same person", "user:todd", now=later(5))
got = s.get("individuals", a["id"])
check("merge: survivor keeps its email and gains the duplicate's missing contacts", m.ok and got["email"] == "pat@example.com" and got["phone"] == "303-555-0142" and got["backup_email"] == "pat2@example.com", str(m))
x = mk(s, {"given_name": "Zed", "email": "zed@example.com", "phone": "303-555-0100", "prefers_email": False})
e = CM.erase(s, x["id"], "user:todd", now=later(6))
tomb = s.get("individuals", x["id"])
check("erase: contact fields are removed with the person", e.ok and not any(k in tomb for k in ("email", "phone", "backup_email", "backup_phone", "prefers_email")), str(tomb))

print(f"\n{total - len(fails)}/{total} checks passed")
if fails:
    print("FAILED:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("OK")
