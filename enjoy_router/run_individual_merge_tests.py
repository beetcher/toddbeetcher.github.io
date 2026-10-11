#!/usr/bin/env python3
"""In-memory tests for merge, unmerge and erase of individuals (crud/individual_merges_crud.py, the services and the
endpoint ops). Run from enjoy_router/:  python3 run_individual_merge_tests.py   (add -v to list every check).
Nothing here touches Firebase."""
import copy
import json
import pathlib
import sys
import uuid
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import individual_merges_crud as M  # noqa: E402
from crud import individual_restricted_details_crud as R  # noqa: E402
from crud import individuals_crud as I  # noqa: E402
from crud import individuals_service as S  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud_endpoint import handle_admin, handle_crud_test, make_failure_limiter  # noqa: E402

START = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
KEY = "k" * 16 + "Z" * 16 + "-test-key-not-real"
fails: list = []
total = 0
clock = [0]


def tick():
    clock[0] += 5
    return START + timedelta(seconds=clock[0])


def check(label, ok, detail=""):
    global total
    total += 1
    if not ok:
        fails.append(label)
    if not ok or "-v" in sys.argv:
        print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")


def pairs(problems):
    return sorted(f"{p['field']}:{p['issue']}" for p in problems)


def world():
    return MemoryDocStore("test_")


def person(s, **kw):
    r = I.create(s, {"given_name": "P", **kw}, "user:todd", now=tick())
    assert r.ok, (kw, r.problems)
    return r.data


def merge(s, a, b, reason="same person", **kw):
    return M.merge(s, a["id"], b["id"], reason, "user:ann", now=tick(), **kw)


def raw(s, coll, id):
    return s.get(coll, id)


U = lambda: str(uuid.uuid4())

# ---------------------------------------------------------------------------
# 1. A basic merge
# ---------------------------------------------------------------------------
s = world()
a = person(s, given_name="Ann", birth_date="1961-04-17", birth_date_verification="self")
b = person(s, given_name="Annie", family_name="Lee", preferred_language="es", notes="from the library list")
r = merge(s, a, b)
check("merge ok", r.ok, str(r))
ev = s.get("merge_events", r.data["id"])
sa, sb = s.get("individuals", a["id"]), s.get("individuals", b["id"])
check("duplicate is merged and redirects", sb["status"] == "merged" and sb["merged_into_id"] == a["id"])
check("survivor keeps its own value on a conflict", sa["given_name"] == "Ann")
check("survivor filled from the duplicate", sa["family_name"] == "Lee" and sa["preferred_language"] == "es" and sa["notes"] == "from the library list")
check("display_name recomputed", sa["display_name"] == "Ann Lee")
check("survivor id and created fields unchanged", sa["id"] == a["id"] and sa["created_at"] == a["created_at"])
check("event records both snapshots", ev["survivor_before"]["given_name"] == "Ann" and ev["duplicate_before"]["given_name"] == "Annie")
check("event lists changed fields", sorted(c["field"] for c in ev["changed_fields"]) == ["family_name", "notes", "preferred_language"], str(ev["changed_fields"]))
check("event status merged, by whom", ev["status"] == "merged" and ev["created_by"] == "user:ann" and ev["reason"] == "same person")
check("get follows the redirect", I.get(s, b["id"]).data["id"] == a["id"])
check("list hides the merged duplicate", [x["id"] for x in I.list(s).data["records"]] == [a["id"]])
hist = list(s.data["test_individual_history"].values())
check("history written for both people", {h["individual_id"] for h in hist if h.get("merge_event_id") == ev["id"]} == {a["id"], b["id"]})

# ---------------------------------------------------------------------------
# 2. Refusals write nothing
# ---------------------------------------------------------------------------
s = world()
a, b, c = person(s, given_name="A"), person(s, given_name="B"), person(s, given_name="C")
before = json.dumps(s.data, sort_keys=True)
check("same person refused", pairs(M.merge(s, a["id"], a["id"], "x", "user:a", now=tick()).problems) == ["duplicate_id:same_as_survivor"])
check("unknown duplicate refused", pairs(M.merge(s, a["id"], U(), "x", "user:a", now=tick()).problems) == ["duplicate_id:not_found"])
check("unknown survivor refused", pairs(M.merge(s, U(), a["id"], "x", "user:a", now=tick()).problems) == ["survivor_id:not_found"])
check("missing reason refused", "reason:required" in pairs(M.merge(s, a["id"], b["id"], "", "user:a", now=tick()).problems))
check("bad choice value refused", not M.merge(s, a["id"], b["id"], "x", "user:a", field_choices={"given_name": "both"}, now=tick()).ok)
check("bad actor refused", pairs(M.merge(s, a["id"], b["id"], "x", "ann", now=tick()).problems) == ["actor:invalid_format"])
check("bad id refused", not M.merge(s, "nope", b["id"], "x", "user:a", now=tick()).ok)
I.soft_delete(s, c["id"], "user:todd", now=tick())
before = json.dumps(s.data, sort_keys=True)
check("deleted person refused", pairs(M.merge(s, a["id"], c["id"], "x", "user:a", now=tick()).problems) == ["duplicate_id:not_found"])
check("refusals wrote nothing", json.dumps(s.data, sort_keys=True) == before)
merge(s, a, b)
d_ = person(s, given_name="D")
check("already merged duplicate refused", pairs(M.merge(s, d_["id"], b["id"], "x", "user:a", now=tick()).problems) == ["duplicate_id:not_found"])
check("merging into a merged survivor refused", pairs(M.merge(s, b["id"], d_["id"], "x", "user:a", now=tick()).problems) == ["survivor_id:not_found"])

# ---------------------------------------------------------------------------
# 3. Survivorship
# ---------------------------------------------------------------------------
def sv(sd, dd, **kw):
    s = world()
    a, b = person(s, **sd), person(s, **dd)
    r = merge(s, a, b, **kw)
    assert r.ok, (sd, dd, r)
    return s.get("individuals", a["id"])

x = sv({"birth_date": "1961-04-17", "birth_date_verification": "self"}, {"birth_date": "1961-04-18", "birth_date_verification": "document", "birth_date_certainty": "exact"})
check("document-verified birth date beats self-reported", x["birth_date"] == "1961-04-18" and x["birth_date_verification"] == "document")
x = sv({"birth_date": "1961-04-17", "birth_date_verification": "document"}, {"birth_date": "1961-04-18", "birth_date_verification": "self"})
check("self-reported does not replace a document birth date", x["birth_date"] == "1961-04-17")
x = sv({"birth_date": "1961-04-17"}, {"birth_date": "1961-04-18"})
check("equal verification: the survivor wins (never recency)", x["birth_date"] == "1961-04-17")
x = sv({}, {"birth_date": "1961", "birth_date_certainty": "estimated"})
check("birth group fills a missing birth date whole", x["birth_date"] == "1961" and x["birth_date_certainty"] == "estimated")
x = sv({"birth_date": "1961-04-17"}, {"birth_date": "1961-04-18", "birth_date_verification": "document"}, field_choices={"birth_date": "survivor"})
check("choice survivor keeps birth date", x["birth_date"] == "1961-04-17")
x = sv({"birth_date": "1961-04-17", "birth_date_verification": "document"}, {"birth_date": "1961-04-18", "birth_date_verification": "self"}, field_choices={"birth_date": "duplicate"})
check("choice duplicate takes birth date group", x["birth_date"] == "1961-04-18")
x = sv({}, {"life_status": "deceased", "death_date": "2025", "death_evidence": "document"})
check("authoritative death evidence moves the death group", x["life_status"] == "deceased" and x["death_date"] == "2025" and x["death_evidence"] == "document")
x = sv({}, {"life_status": "deceased", "death_date": "2025", "death_evidence": "family_report"})
check("family report alone does not mark the survivor deceased", x["life_status"] == "alive" and "death_date" not in x)
x = sv({"life_status": "deceased", "death_date": "2024", "death_evidence": "document"}, {"life_status": "alive"})
check("deceased survivor stays deceased", x["life_status"] == "deceased" and x["death_date"] == "2024")
x = sv({"external_refs": [{"system": "stripe", "ref": "cus_1"}], "same_as_urls": ["https://a.example"]},
       {"external_refs": [{"system": "stripe", "ref": "cus_1"}, {"system": "crm", "ref": "7"}], "same_as_urls": ["https://b.example"]})
check("external refs combined without repeats", x["external_refs"] == [{"system": "stripe", "ref": "cus_1"}, {"system": "crm", "ref": "7"}])
check("urls combined", x["same_as_urls"] == ["https://a.example", "https://b.example"])
x = sv({"record_privacy": "confidential"}, {"record_privacy": "sealed"})
check("stricter privacy wins", x["record_privacy"] == "sealed")
x = sv({"record_privacy": "sealed"}, {})
check("sealed survivor stays sealed", x["record_privacy"] == "sealed")
x = sv({"identity_verification": "self_reported"}, {"identity_verification": "document_verified"})
check("stronger identity verification wins", x["identity_verification"] == "document_verified")
x = sv({"given_name": "Ann"}, {"given_name": "Anna"}, field_choices={"given_name": "duplicate"})
check("choice duplicate takes a conflicting value", x["given_name"] == "Anna" and x["display_name"] == "Anna")
x = sv({"given_name": "Ann"}, {"given_name": "Anna"}, field_choices={"given_name": "survivor"})
check("choice survivor keeps the value", x["given_name"] == "Ann")
x = sv({"birth_date": "2015-06-01"}, {})
check("is_minor derived on the merged record", x["is_minor"] is True)
x = sv({}, {"birth_date": "2015-06-01"})
check("is_minor derived when birth date comes from the duplicate", x["is_minor"] is True)

# ---------------------------------------------------------------------------
# 4. Links are re-pointed, and recorded
# ---------------------------------------------------------------------------
def seeded():
    s = world()
    a = person(s, given_name="Ann", birth_date="1961-04-17")
    b = person(s, given_name="Annie", birth_date="1961-04-17")
    other = person(s, given_name="Other")
    ids = {k: U() for k in ("req", "asg", "asg2", "tx", "tx2")}
    s.data.setdefault("test_registration_requests", {})[ids["req"]] = {"id": ids["req"], "individual_id": b["id"], "updated_at": "2026-10-10T11:00:00Z"}
    s.data.setdefault("test_registration_assignments", {})[ids["asg"]] = {"id": ids["asg"], "participant_individual_ids": [other["id"], b["id"], a["id"]], "updated_at": "2026-10-10T11:00:00Z"}
    s.data["test_registration_assignments"][ids["asg2"]] = {"id": ids["asg2"], "participant_individual_ids": [other["id"]], "updated_at": "2026-10-10T11:00:00Z"}
    s.data.setdefault("test_transaction_records", {})[ids["tx"]] = {"id": ids["tx"], "payer": {"party_type": "person", "name": "Annie", "party_id": b["id"]},
        "payee": {"party_type": "program", "name": "LAUNCH"}, "participant_individual_ids": [b["id"]], "updated_at": "2026-10-10T11:00:00Z"}
    s.data["test_transaction_records"][ids["tx2"]] = {"id": ids["tx2"], "payer": {"party_type": "person", "name": "Someone", "party_id": other["id"]},
        "payee": {"party_type": "person", "name": "Annie", "party_id": b["id"]}, "updated_at": "2026-10-10T11:00:00Z"}
    return s, a, b, other, ids


s, a, b, other, ids = seeded()
d = I.create  # silence linters
rd = R.create(s, {"individual_id": b["id"], "purpose": "safety", "consent_ref": "c1", "blood_type_abo": "O"}, "user:todd", now=tick()).data
r = merge(s, a, b)
check("merge with links ok", r.ok, str(r))
g = lambda coll, id: s.data[coll][id]
check("restricted detail moved to the survivor", g("test_individual_restricted_details", rd["id"])["individual_id"] == a["id"])
check("request re-pointed", g("test_registration_requests", ids["req"])["individual_id"] == a["id"])
check("assignment participants replaced and deduplicated", g("test_registration_assignments", ids["asg"])["participant_individual_ids"] == [other["id"], a["id"]])
check("untouched assignment unchanged", g("test_registration_assignments", ids["asg2"])["participant_individual_ids"] == [other["id"]])
check("transaction payer re-pointed (nested)", g("test_transaction_records", ids["tx"])["payer"]["party_id"] == a["id"] and g("test_transaction_records", ids["tx"])["payer"]["name"] == "Annie")
check("transaction participants re-pointed", g("test_transaction_records", ids["tx"])["participant_individual_ids"] == [a["id"]])
check("transaction payee re-pointed", g("test_transaction_records", ids["tx2"])["payee"]["party_id"] == a["id"])
check("someone else's payer untouched", g("test_transaction_records", ids["tx2"])["payer"]["party_id"] == other["id"])
ev = s.get("merge_events", r.data["id"])
check("every moved link is recorded", len(ev["moved_links"]) == 6 and r.data["moved_links"] == 6, str(len(ev["moved_links"])))
mv = next(m for m in ev["moved_links"] if m["id"] == ids["asg"])
check("moved link before/after", mv["before"] == [other["id"], b["id"], a["id"]] and mv["after"] == [other["id"], a["id"]] and mv["field"] == "participant_individual_ids")
check("moved records stamped by the merge", g("test_registration_requests", ids["req"])["updated_by"] == "system:identity_merge")

# both hold restricted details
s2 = world()
a2, b2 = person(s2, given_name="A", birth_date="1961"), person(s2, given_name="B", birth_date="1961")
for p_ in (a2, b2):
    R.create(s2, {"individual_id": p_["id"], "purpose": "safety", "consent_ref": "c", "blood_type_abo": "O"}, "user:t", now=tick())
content = lambda st: json.dumps({k: v for k, v in st.data.items() if v}, sort_keys=True)  # reads may create empty buckets
snap = content(s2)
check("both holding restricted details refused", pairs(merge(s2, a2, b2).problems) == ["duplicate_id:conflict_restricted_detail"])
check("that refusal wrote nothing", content(s2) == snap)
old = M.MAX_LINKS
M.MAX_LINKS = 1
s3, a3, b3, _, _ = seeded()
check("too many links refused", pairs(merge(s3, a3, b3).problems) == ["duplicate_id:too_many_links"])
M.MAX_LINKS = old

# ---------------------------------------------------------------------------
# 5. Unmerge
# ---------------------------------------------------------------------------
s, a, b, other, ids = seeded()
a_before, b_before = copy.deepcopy(s.get("individuals", a["id"])), copy.deepcopy(s.get("individuals", b["id"]))
rd = R.create(s, {"individual_id": b["id"], "purpose": "safety", "consent_ref": "c1", "blood_type_abo": "O"}, "user:todd", now=tick()).data
b_before = copy.deepcopy(s.get("individuals", b["id"]))
a_before = copy.deepcopy(s.get("individuals", a["id"]))
s.update("individuals", b["id"], {"family_name": "Lee", "preferred_language": "es"})
b_before = copy.deepcopy(s.get("individuals", b["id"]))
r = merge(s, a, b)
eid = r.data["id"]
check("merged with changes", s.get("individuals", a["id"])["family_name"] == "Lee")
u = M.unmerge(s, eid, "user:ann", now=tick())
check("unmerge ok", u.ok and u.data["skipped"] == [], str(u))
sa, sb = s.get("individuals", a["id"]), s.get("individuals", b["id"])
check("duplicate restored from snapshot", {k: v for k, v in sb.items() if k not in ("updated_at", "updated_by")} == {k: v for k, v in b_before.items() if k not in ("updated_at", "updated_by")}, str(sb))
check("duplicate no longer redirects", "merged_into_id" not in sb and sb["status"] == "active" and I.get(s, b["id"]).data["id"] == b["id"])
check("survivor fields put back", "family_name" not in sa and "preferred_language" not in sa and sa["display_name"] == "Ann")
check("links put back: request", s.data["test_registration_requests"][ids["req"]]["individual_id"] == b["id"])
check("links put back: participants list", s.data["test_registration_assignments"][ids["asg"]]["participant_individual_ids"] == [other["id"], b["id"], a["id"]])
check("links put back: nested payer", s.data["test_transaction_records"][ids["tx"]]["payer"]["party_id"] == b["id"])
check("restricted detail returned", s.data["test_individual_restricted_details"][rd["id"]]["individual_id"] == b["id"])
evd = s.get("merge_events", eid)
check("event marked unmerged", evd["status"] == "unmerged" and evd["unmerged_by"] == "user:ann" and "unmerged_at" in evd)
check("unmerge twice refused", pairs(M.unmerge(s, eid, "user:ann", now=tick()).problems) == ["id:not_merged"])
check("unknown event", M.unmerge(s, U(), "user:ann").code == "not_found")
check("bad event id", not M.unmerge(s, "nope", "user:ann").ok)

# later legitimate changes survive an unmerge
s, a, b, other, ids = seeded()
s.update("individuals", b["id"], {"family_name": "Lee"})
r = merge(s, a, b)
I.update(s, a["id"], {"family_name": "Smith"}, "user:later", now=tick())                  # changed after the merge
s.update("registration_requests", ids["req"], {"individual_id": U()})  # re-pointed elsewhere after the merge
u = M.unmerge(s, r.data["id"], "user:ann", now=tick())
check("unmerge with later changes ok", u.ok, str(u))
check("changed survivor field is not undone", s.get("individuals", a["id"])["family_name"] == "Smith")
check("skipped entries named", "survivor:family_name" in u.data["skipped"] and any(x.startswith("registration_requests:") for x in u.data["skipped"]), str(u.data))
check("skipped names carry no values", all("Smith" not in x for x in u.data["skipped"]))
check("later-changed link is left alone", s.data["test_registration_requests"][ids["req"]]["individual_id"] not in (a["id"], b["id"]))
check("other links still restored", s.data["test_registration_assignments"][ids["asg"]]["participant_individual_ids"] == [other["id"], b["id"], a["id"]])
check("skipped recorded on the event", s.get("merge_events", r.data["id"])["unmerge_skipped"] == u.data["skipped"])

# unmerge refusals
s, a, b, _, _ = seeded()
r = merge(s, a, b)
s.update("individuals", b["id"], {"status": "erased", "erased_at": "2026-10-10T12:00:00Z"})
check("unmerge refused when the duplicate changed", pairs(M.unmerge(s, r.data["id"], "user:a", now=tick()).problems) == ["duplicate_id:changed"])
s, a, b, _, _ = seeded()
r = merge(s, a, b)
s.update("individuals", a["id"], {"status": "merged", "merged_into_id": U()})
check("unmerge refused when the survivor changed", pairs(M.unmerge(s, r.data["id"], "user:a", now=tick()).problems) == ["survivor_id:changed"])

# ---------------------------------------------------------------------------
# 6. Erase
# ---------------------------------------------------------------------------
s = world()
a = person(s, given_name="Ann", family_name="Lee", birth_date="1961-04-17", eye_color_left="brown", notes="private note", external_refs=[{"system": "stripe", "ref": "cus_9"}])
b = person(s, given_name="Bea")
I.update(s, a["id"], {"family_name": "Smith"}, "user:a", now=tick())
rd = R.create(s, {"individual_id": a["id"], "purpose": "safety", "consent_ref": "c-keep", "blood_type_abo": "AB", "notes": "sensitive note"}, "user:t", now=tick()).data
R.update(s, rd["id"], {"blood_type_abo": "A"}, "user:a", now=tick())
m2 = M.merge(s, b["id"], person(s, given_name="Cy")["id"], "same", "user:a", now=tick())
r = M.erase(s, a["id"], "user:admin", now=tick())
check("erase ok", r.ok, str(r))
t = s.get("individuals", a["id"])
check("tombstone: erased with a timestamp", t["status"] == "erased" and "erased_at" in t and t["updated_by"] == "user:admin")
check("tombstone keeps id and server fields", t["id"] == a["id"] and t["created_by"] == "user:todd" and t["schema_version"] == 1)
check("tombstone holds no personal data", set(t) <= M.TOMBSTONE_KEEP and t["given_name"] == "[erased]" and t["display_name"] == "[erased]", str(sorted(t)))
check("tombstone is still a valid record", not M.check_document(M.INDIVIDUALS, {k: v for k, v in t.items() if k != "display_name"}))
check("no personal value remains anywhere in the record", all(x not in json.dumps(t) for x in ("Lee", "Smith", "1961", "private note", "cus_9")))
d = s.get("individual_restricted_details", rd["id"])
check("restricted details erased and closed", "blood_type_abo" not in d and "notes" not in d and "deleted_at" in d and d["individual_id"] == a["id"])
hs = [h for h in s.data["test_individual_history"].values() if h["individual_id"] == a["id"]]
check("history scrubbed", hs and all(h["before"] == {} and h["after"] == {} for h in hs))
dh = [h for h in s.data["test_individual_restricted_detail_history"].values() if h["individual_id"] == a["id"]]
check("restricted history scrubbed", dh and all(h["before"] == {} and h["after"] == {} for h in dh))
check("get returns the tombstone", I.get(s, a["id"]).data["status"] == "erased")
check("list hides the tombstone", a["id"] not in [x["id"] for x in I.list(s).data["records"]])
check("erase twice refused", pairs(M.erase(s, a["id"], "user:admin").problems) == ["status:already_erased"])
check("erase unknown", M.erase(s, U(), "user:admin").code == "not_found")
check("erased person cannot be updated", I.update(s, a["id"], {"notes": "x"}, "user:a").code == "conflict")
check("erased person cannot be merged", pairs(M.merge(s, b["id"], a["id"], "x", "user:a", now=tick()).problems) == ["duplicate_id:not_found"])

# erase scrubs merge events and blocks unmerge
s = world()
a, b = person(s, given_name="Ann", family_name="Lee"), person(s, given_name="Annie")
r = merge(s, a, b)
M.erase(s, b["id"], "user:admin", now=tick())
ev = s.get("merge_events", r.data["id"])
check("merge event snapshots scrubbed", ev["survivor_before"] == {} and ev["duplicate_before"] == {} and ev["has_erased_snapshots"] is True and ev["reason"] == "[erased]")
check("no personal value left in the event", "Lee" not in json.dumps(ev) and "Annie" not in json.dumps(ev))
check("event still names the ids", ev["survivor_id"] == a["id"] and ev["duplicate_id"] == b["id"])
s.update("individuals", b["id"], {"status": "merged", "merged_into_id": a["id"]})  # as if still merged, to reach the snapshot rule
check("unmerge refused after erasure", pairs(M.unmerge(s, r.data["id"], "user:a", now=tick()).problems) == ["id:snapshots_erased"])

# ---------------------------------------------------------------------------
# 7. Events can be read
# ---------------------------------------------------------------------------
s = world()
a, b, c = person(s, given_name="A"), person(s, given_name="B"), person(s, given_name="C")
r1, r2 = merge(s, a, b), merge(s, a, c)
check("get_event", M.get_event(s, r1.data["id"]).data["duplicate_id"] == b["id"])
check("list_events newest first", [e["id"] for e in M.list_events(s).data["records"]] == [r2.data["id"], r1.data["id"]] or len(M.list_events(s).data["records"]) == 2)
check("list_events by survivor", M.list_events(s, {"survivor_id": a["id"]}).data["count"] == 2)
check("list_events by status", M.list_events(s, {"status": "unmerged"}).data["count"] == 0)
check("list_events bad filter", not M.list_events(s, {"reason": "x"}).ok)
check("get_event missing", M.get_event(s, U()).code == "not_found")

# ---------------------------------------------------------------------------
# 8. Services and endpoint
# ---------------------------------------------------------------------------
s = world()
a, b = person(s, given_name="A"), person(s, given_name="B")
sealed = person(s, given_name="Sealed", record_privacy="sealed")
check("service merge hides sealed", S.merge(s, a["id"], sealed["id"], "x", "user:a", now=tick()).code == "not_found")
check("service erase hides sealed", S.erase(s, sealed["id"], "user:a", now=tick()).code == "not_found")
check("service merge ok for admin", S.merge(s, a["id"], sealed["id"], "x", "user:a", now=tick(), as_admin=True).ok)

store = world()
limiter = make_failure_limiter()
call = lambda fn, coll, op, **a_: fn("POST", f"Bearer {KEY}", json.dumps({"collection": coll, "op": op, "args": a_}).encode(), KEY, "v", store, limiter, START)
test_door = lambda *a_, **k: call(handle_crud_test, *a_, **k)
admin_door = lambda *a_, **k: call(handle_admin, *a_, **k)
pa = test_door("individuals", "create", data={"given_name": "Ann"}).body["data"]
pb = test_door("individuals", "create", data={"given_name": "Annie", "family_name": "Lee"}).body["data"]
pc = test_door("individuals", "create", data={"given_name": "Cy"}).body["data"]
r = admin_door("individuals", "merge", survivor_id=pa["id"], duplicate_id=pb["id"], reason="same person")
check("Console door can merge", r.status == 200 and r.body["data"]["moved_links"] == 0 and r.body["data"]["changed_fields"] == ["family_name"], str(r.body))
eid = r.body["data"]["id"]
check("merge stamped user:admin", store.get("merge_events", eid)["created_by"] == "user:admin")
check("merge event readable on the Console door", admin_door("merge_events", "get", id=eid).body["data"]["id"] == eid)
check("merge events listable", admin_door("merge_events", "list").body["data"]["count"] == 1)
check("merge events not creatable", admin_door("merge_events", "create", data={"survivor_id": pa["id"], "duplicate_id": pc["id"], "reason": "x"}).status == 400)
check("merge events not soft-deletable", admin_door("merge_events", "soft_delete", id=eid).status == 400)
r = admin_door("individuals", "unmerge", id=eid)
check("Console door can unmerge", r.status == 200 and r.body["data"]["skipped"] == [], str(r.body))
check("bad merge args named", admin_door("individuals", "merge", survivor_id=pa["id"]).status == 400)
r = admin_door("individuals", "merge", survivor_id=pa["id"], duplicate_id=pa["id"], reason="x")
check("merge refusal is 400 with problems", r.status == 400 and r.body["error"]["problems"] == [{"field": "duplicate_id", "issue": "same_as_survivor"}])
before = json.dumps(store.data, sort_keys=True)
r = admin_door("individuals", "erase", id=pc["id"])
check("Console door cannot erase", r.status == 400 and "not enabled" in r.body["error"]["message"])
check("that left the store untouched", json.dumps(store.data, sort_keys=True) == before)
r = test_door("individuals", "erase", id=pc["id"])
check("test door can erase", r.status == 200 and r.body["data"]["id"] == pc["id"], str(r.body))
check("merge op on another collection not supported", test_door("venues", "merge", survivor_id=pa["id"], duplicate_id=pb["id"], reason="x").status == 400)

print(f"\n{total - len(fails)}/{total} checks passed")
if fails:
    print("FAILED:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("OK")
