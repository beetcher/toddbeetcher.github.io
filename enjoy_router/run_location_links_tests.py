#!/usr/bin/env python3
"""In-memory tests for location links: the link handler, the link service and the location service.
Run from enjoy_router/:  python3 run_location_links_tests.py   (add -v to list every check). Nothing touches Firebase."""
import copy
import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import individual_merges_crud as M  # noqa: E402
from crud import individuals_crud as I  # noqa: E402
from crud import location_links_crud as H  # noqa: E402
from crud import location_links_service as S  # noqa: E402
from crud import locations_crud as L  # noqa: E402
from crud import locations_service as LS  # noqa: E402
from crud import venues_crud as V  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud.schema_kit import find_schema_dir  # noqa: E402

START = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)
fails: list = []
total = 0
clock = [0]
ACT = "user:todd"
NOPE = "3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b"


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


s = MemoryDocStore("test_")
ex = json.load(open(find_schema_dir() / "examples" / "location_link.examples.json"))
VENUE = {"name": "Library", "slug": "library", "status": "active", "is_public_venue": True,
         "email": "pat@example.com", "contact_individual_id": "5b1f0c2e-7a4d-4c3b-9e6f-1a2b3c4d5e6f",
         "is_accessible": True, "allows_minors": True, "allows_animals": False,
         "rooms": [{"label": "Main room", "max_occupancy": 40}]}


def person(name="Todd", **kw):
    return I.create(s, {"given_name": name, **kw}, ACT, now=tick()).data


def place(name="Home", **kw):
    return L.create(s, {"name": name, **kw}, ACT, now=tick()).data


def link(subj, loc, rel="resides_at", st="individual", **kw):
    return S.create(s, {"subject_type": st, "subject_id": subj["id"], "location_id": loc["id"], "relationship": rel, **kw}, ACT, now=tick())


def raw(base, id):
    return s.get(base, id)


todd, ann, venue = person("Todd"), person("Ann"), V.create(s, copy.deepcopy(VENUE), ACT, now=tick()).data
home, cabin, lib = place("Home"), place("Cabin"), place("Library building")

# ============================ handler ============================
for label, doc in ex["valid"].items():
    r = H.create(s, copy.deepcopy(doc), ACT, now=tick())
    check(f"handler: valid example '{label}' created", r.ok, str(r))
    if r.ok:
        check(f"handler: status follows valid_to for '{label}'", r.data["status"] == ("ended" if "valid_to" in doc else "active"))
before = sum(len(v) for v in s.data.values())
for label, doc in ex["invalid"].items():
    r = H.create(s, copy.deepcopy(doc), ACT, now=tick())
    check(f"handler: invalid example '{label}' refused", (not r.ok) and r.code == "validation_failed", str(r))
check("handler: refusals wrote nothing", sum(len(v) for v in s.data.values()) == before)
check("handler: dates out of order", pairs(H.create(s, {**ex["valid"]["home"], "valid_from": "2020-05", "valid_to": "2020-01"}, ACT).problems) == ["valid_to:out_of_range"])
check("handler: same month is fine", H.create(s, {**ex["valid"]["home"], "valid_from": "2020-05", "valid_to": "2020-05"}, ACT, now=tick()).ok)
check("handler: bad actor", pairs(H.create(s, ex["valid"]["home"], "todd").problems) == ["actor:invalid_format"])
check("handler: bad source", pairs(H.create(s, ex["valid"]["home"], ACT, source="web_enjoy").problems) == ["source:invalid_value"])
check("handler: body must be object", pairs(H.create(s, [], ACT).problems) == ["body:invalid_type"])
check("handler: problems never carry values", all(set(p) == {"field", "issue"} for p in H.create(s, {**ex["valid"]["home"], "notes": 5}, ACT).problems))

# periods
P = lambda f=None, t=None: {k: v for k, v in (("valid_from", f), ("valid_to", t)) if v}
check("overlap: open and open", H.overlaps(P(), P()))
check("overlap: year contains month", H.overlaps(P("2020", "2020"), P("2020-06", "2020-06")))
check("overlap: adjacent days do not", not H.overlaps(P("2020-01-01", "2020-01-31"), P("2020-02-01", "2020-02-28")))
check("overlap: touching day does", H.overlaps(P("2020-01-01", "2020-02-01"), P("2020-02-01", "2020-03-01")))
check("overlap: ended before the open one begins", not H.overlaps(P(None, "2019-05-31"), P("2019-06")))
check("overlap: open end vs later start", H.overlaps(P("2019"), P("2025-01-01", "2025-02-01")))

lk = H.create(s, {**ex["valid"]["home"], "subject_id": todd["id"], "location_id": home["id"]}, ACT, now=tick()).data
check("handler: get", H.get(s, lk["id"]).data["id"] == lk["id"] and H.get(s, "x").code == "validation_failed" and H.get(s, NOPE).code == "not_found")
for f in H.IMMUTABLE:
    check(f"handler: {f} is immutable", pairs(H.update(s, lk["id"], {f: NOPE if f.endswith("_id") else "owns"}, ACT).problems) == [f"{f}:immutable"])
for label, ch, want in [("status", {"status": "ended"}, ["status:not_allowed"]), ("unknown", {"household": 1}, ["household:not_allowed"]),
                        ("bad date", {"valid_to": "June"}, ["valid_to:invalid_format"]), ("bad enum", {"verification": "sure"}, ["verification:invalid_value"])]:
    check(f"handler: update refuses {label}", pairs(H.update(s, lk["id"], ch, ACT).problems) == want)
check("handler: empty changes", pairs(H.update(s, lk["id"], {}, ACT).problems) == ["changes:required"])
n0 = len(s.reads)
check("handler: simple update does not read", H.update(s, lk["id"], {"notes": "n"}, ACT, now=tick()).ok and len(s.reads) == n0)
r = H.update(s, lk["id"], {"valid_to": "2024-12-31"}, ACT, now=tick())
check("handler: setting valid_to ends the link", r.ok and raw("location_links", lk["id"])["status"] == "ended", str(r))
r = H.update(s, lk["id"], {"valid_to": None}, ACT, now=tick())
check("handler: removing valid_to reopens", r.ok and raw("location_links", lk["id"])["status"] == "active" and "valid_to" not in raw("location_links", lk["id"]), str(r))
check("handler: valid_to before valid_from refused", pairs(H.update(s, lk["id"], {"valid_to": "2010"}, ACT).problems) == ["valid_to:out_of_range"])
cur = raw("location_links", lk["id"])
check("handler: stale is conflict", H.update(s, lk["id"], {"valid_to": "2025"}, ACT, expected_updated_at="2020-01-01T00:00:00Z").code == "conflict")
check("handler: bad expected_updated_at", pairs(H.update(s, lk["id"], {"notes": "z"}, ACT, expected_updated_at="soon").problems) == ["expected_updated_at:invalid_format"])
check("handler: update unknown id", H.update(s, NOPE, {"valid_to": "2025"}, ACT).code == "not_found")
check("handler: set_primary", H.set_primary(s, lk["id"], True, ACT, now=tick()).ok and raw("location_links", lk["id"]).get("is_primary") is True
      and H.set_primary(s, lk["id"], False, ACT, now=tick()).ok and "is_primary" not in raw("location_links", lk["id"]))
check("handler: set_primary type", pairs(H.set_primary(s, lk["id"], "yes", ACT).problems) == ["is_primary:invalid_type"])
check("handler: list newest first, one filter, no order by name",
      H.list(s).ok and H.list(s, {"relationship": "resides_at"}).ok and pairs(H.list(s, {"relationship": "owns", "status": "active"}).problems) == ["relationship:not_supported", "status:not_supported"]
      and pairs(H.list(s, order="name").problems) == ["order:not_supported"] and pairs(H.list(s, {"relationship": "friend"}).problems) == ["relationship:invalid_value"])
d = H.create(s, {**ex["valid"]["home"], "subject_id": ann["id"], "location_id": home["id"]}, ACT, now=tick()).data
check("handler: soft delete", H.soft_delete(s, d["id"], ACT, now=tick()).ok and H.soft_delete(s, d["id"], ACT).code == "not_found" and H.get(s, d["id"]).code == "not_found")
check("handler: deleted left out of list and live_for", d["id"] not in [x["id"] for x in H.list(s).data["records"]] and d["id"] not in [x["id"] for x in H.live_for(s, "subject_id", ann["id"])])

# ============================ link service: create ============================
s = MemoryDocStore("test_")
todd, ann, venue = person("Todd"), person("Ann"), V.create(s, copy.deepcopy(VENUE), ACT, now=tick()).data
home, cabin, lib = place("Home"), place("Cabin"), place("Library building")
check("location starts not residential", raw("locations", home["id"])["is_residential"] is False)
r = link(todd, home, is_primary=True, valid_from="2019-06")
check("service: residence link created", r.ok and r.data["status"] == "active", str(r))
t_home = r.data
check("service: residence makes the location residential", raw("locations", home["id"])["is_residential"] is True)
r = link(venue, lib, "operates_at", "venue", valid_from="2005")
check("service: venue operates_at created", r.ok, str(r))
v_lib = r.data
check("service: venue link does not make it residential", raw("locations", lib["id"])["is_residential"] is False)
check("service: organization reserved", pairs(link({"id": NOPE}, home, "owns", st="organization").problems) == ["subject_type:not_supported"])
check("service: resides_at needs an individual", pairs(link(venue, home, "resides_at", "venue").problems) == ["relationship:invalid_value"])
check("service: operates_at needs a venue", pairs(link(todd, home, "operates_at").problems) == ["relationship:invalid_value"])
check("service: owns fits both", link(venue, cabin, "owns", "venue").ok and link(todd, cabin, "owns").ok)
check("service: unknown individual", pairs(link({"id": NOPE}, home).problems) == ["subject_id:not_found"])
check("service: unknown venue", pairs(link({"id": NOPE}, lib, "operates_at", "venue").problems) == ["subject_id:not_found"])
check("service: an individual id used as a venue", pairs(link(todd, lib, "owns", "venue").problems) == ["subject_id:not_found"])
check("service: unknown location", pairs(link(ann, {"id": NOPE}).problems) == ["location_id:not_found"])
gone = place("Gone"); L.soft_delete(s, gone["id"], ACT, now=tick())
check("service: deleted location", pairs(link(ann, gone).problems) == ["location_id:not_found"])
old = place("Old"); L.update(s, old["id"], {"status": "retired"}, ACT, now=tick())
check("service: retired location", pairs(link(ann, old).problems) == ["location_id:retired"])
check("service: shape problems come from the handler", pairs(S.create(s, {"subject_type": "individual"}, ACT).problems) == ["location_id:required", "relationship:required", "subject_id:required"])
check("service: bad actor", pairs(S.create(s, {}, "x").problems) == ["actor:invalid_format"])
check("service: dates in order", pairs(link(ann, home, valid_from="2020", valid_to="2019").problems) == ["valid_to:out_of_range"])
erased = person("Gone")
M.erase(s, erased["id"], ACT, now=tick())
check("service: erased individual", pairs(link(erased, home).problems) == ["subject_id:not_found"])
dele = person("Del"); I.soft_delete(s, dele["id"], ACT, now=tick())
check("service: deleted individual", pairs(link(dele, home).problems) == ["subject_id:not_found"])
sealed = person("Sealed", record_privacy="sealed")
check("service: sealed individual not found for a non-admin", pairs(link(sealed, home).problems) == ["subject_id:not_found"])
r = S.create(s, {"subject_type": "individual", "subject_id": sealed["id"], "location_id": home["id"], "relationship": "resides_at"}, ACT, now=tick(), as_admin=True)
check("service: sealed individual allowed for an admin", r.ok, str(r))
# merged individual followed
dupe = person("Todd Dup")
M.merge(s, todd["id"], dupe["id"], "same person", ACT, now=tick())
r = link(dupe, lib, "owns")
check("service: a merged individual is followed to the survivor", r.ok and r.data["subject_id"] == todd["id"], str(r))

# ============================ overlaps and primary ============================
r = link(todd, home, valid_from="2019-06")
check("service: identical open link refused", pairs(r.problems) == ["location_id:duplicate"], str(r))
check("service: different relationship at the same place fine", link(todd, home, "mailing_address_for").ok)
check("service: another person at the same place fine", link(ann, home, valid_from="2021").ok)
p = person("Pat")
a1 = link(p, home, valid_from="2000", valid_to="2009-12-31")
check("service: ended link created as ended", a1.ok and a1.data["status"] == "ended", str(a1))
check("service: the next period after it is fine", link(p, home, valid_from="2010").ok)
check("service: overlapping period refused", pairs(link(p, home, valid_from="2005", valid_to="2006").problems) == ["location_id:duplicate"])
check("service: same dates at another place fine", link(p, cabin, valid_from="2005", valid_to="2006").ok)
# primary
q = person("Quinn")
h1, h2 = place("H1"), place("H2")
l1 = link(q, h1, is_primary=True, valid_from="2000", valid_to="2009")
check("service: ended primary stays", l1.ok and raw("location_links", l1.data["id"]).get("is_primary") is True)
l2 = link(q, h2, is_primary=True, valid_from="2010")
check("service: active primary does not demote an ended one", l2.ok and "demoted_link_ids" not in l2.data and raw("location_links", l1.data["id"]).get("is_primary") is True, str(l2))
h3 = place("H3")
l3 = link(q, h3, is_primary=True, valid_from="2015")
check("service: new primary demotes the old active one", l3.ok and l3.data["demoted_link_ids"] == [l2.data["id"]] and "is_primary" not in raw("location_links", l2.data["id"]), str(l3))
check("service: exactly one active primary remains", sum(1 for x in H.live_for(s, "subject_id", q["id"]) if x.get("is_primary") and x["status"] == "active") == 1)
check("service: a primary of another relationship is untouched", link(q, h3, "mailing_address_for", is_primary=True).ok and raw("location_links", l3.data["id"]).get("is_primary") is True)
r = S.update(s, l2.data["id"], {"is_primary": True}, ACT, now=tick())
check("service: update to primary demotes the other", r.ok and r.data["demoted_link_ids"] == [l3.data["id"]] and "is_primary" not in raw("location_links", l3.data["id"]), str(r))

# ============================ update / end / delete / residential ============================
b = place("B"); c = person("Cy"); d = person("Di")
lc = link(c, b).data
ld = link(d, b).data
check("service: two residents", raw("locations", b["id"])["is_residential"] is True)
r = S.end(s, lc["id"], ACT, valid_to="2026-01-31", now=tick())
check("service: end sets valid_to and status", r.ok and raw("location_links", lc["id"])["status"] == "ended" and raw("location_links", lc["id"])["valid_to"] == "2026-01-31", str(r))
check("service: still residential with the other resident", raw("locations", b["id"])["is_residential"] is True)
check("service: ending twice is a conflict", S.end(s, lc["id"], ACT).code == "conflict")
r = S.end(s, ld["id"], ACT, now=tick())
today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
check("service: end defaults to today", r.ok and raw("location_links", ld["id"])["valid_to"] == today, str(r))
check("service: no active residents leaves the location non-residential", raw("locations", b["id"])["is_residential"] is False)
r = S.update(s, ld["id"], {"valid_to": None}, ACT, now=tick())
check("service: reopening restores residential", r.ok and raw("locations", b["id"])["is_residential"] is True and raw("location_links", ld["id"])["status"] == "active", str(r))
# reopen overlapping an existing later link
e = person("Eve"); b2 = place("B2")
x1 = link(e, b2, valid_from="2000", valid_to="2009").data
x2 = link(e, b2, valid_from="2010").data
r = S.update(s, x1["id"], {"valid_to": None}, ACT, now=tick())
check("service: reopening into an overlap is refused", pairs(r.problems) == ["location_id:duplicate"], str(r))
check("service: update of a missing link", S.update(s, NOPE, {"notes": "x"}, ACT).code == "not_found")
check("service: update immutable still refused", pairs(S.update(s, x2["id"], {"relationship": "owns"}, ACT).problems) == ["relationship:immutable"])
check("service: update bad dates", pairs(S.update(s, x2["id"], {"valid_to": "2005"}, ACT).problems) == ["valid_to:out_of_range"])
check("service: stale is conflict", S.update(s, x2["id"], {"valid_to": "2030"}, ACT, expected_updated_at="2020-01-01T00:00:00Z").code == "conflict")
check("service: simple note update", S.update(s, x2["id"], {"notes": "hi"}, ACT, now=tick()).ok)
b3 = place("B3"); f = person("Fay")
lf = link(f, b3).data
check("service: soft delete a link clears residential", S.soft_delete(s, lf["id"], ACT, now=tick()).ok and raw("locations", b3["id"])["is_residential"] is False)
check("service: delete twice", S.soft_delete(s, lf["id"], ACT).code == "not_found")
check("service: the deleted link is gone from get and list", S.get(s, lf["id"]).code == "not_found" and lf["id"] not in [z["id"] for z in S.list(s, as_admin=True).data["records"]])
check("service: delete bad id", S.soft_delete(s, "x", ACT).code == "validation_failed")
# a deleted link can be remade
check("service: a deleted link can be made again", link(f, b3).ok)

# ============================ privacy ============================
g = person("Gus", record_privacy="confidential"); bg = place("BG")
lg = link(g, bg).data
check("privacy: confidential resident's link hidden from get", S.get(s, lg["id"]).code == "not_found" and S.get(s, lg["id"], as_admin=True).ok)
check("privacy: and from lists", lg["id"] not in [z["id"] for z in S.list(s).data["records"]] and lg["id"] in [z["id"] for z in S.list(s, as_admin=True).data["records"]])
check("privacy: a venue link is visible", S.get(s, v_lib["id"]).ok)
check("privacy: a normal resident's link is visible", S.get(s, t_home["id"]).ok)
sl = S.create(s, {"subject_type": "individual", "subject_id": sealed["id"], "location_id": bg["id"], "relationship": "resides_at"}, ACT, now=tick(), as_admin=True).data
check("privacy: sealed link cannot be updated by a non-admin", S.update(s, sl["id"], {"notes": "x"}, ACT).code == "not_found" and S.soft_delete(s, sl["id"], ACT).code == "not_found")

# ============================ location service ============================
check("locations: an ordinary person's home is visible", LS.get(s, h2["id"]).ok and h2["id"] in [z["id"] for z in LS.list(s).data["records"]])
check("locations: a confidential person's home is hidden from get", LS.get(s, bg["id"]).code == "not_found" and LS.get(s, bg["id"], as_admin=True).ok)
check("locations: and from lists", bg["id"] not in [z["id"] for z in LS.list(s).data["records"]] and bg["id"] in [z["id"] for z in LS.list(s, as_admin=True).data["records"]])
check("locations: update and delete of a hidden location are not_found", LS.update(s, bg["id"], {"description": "x"}, ACT).code == "not_found" and LS.soft_delete(s, bg["id"], ACT).code == "not_found")
bgaddr = {"usage": "civic", "street_number": "77", "street": "Hidden Way", "locality": "Boulder", "postal_code": "80302", "country": "US"}
L.update(s, bg["id"], {"addresses": [bgaddr]}, ACT, now=tick())
check("locations: find by address finds it for an admin but hides it otherwise", [z["id"] for z in LS.find_by_address(s, bgaddr, as_admin=True).data["records"]] == [bg["id"]] and LS.find_by_address(s, bgaddr).data["count"] == 0)
check("locations: a venue's location is visible", LS.get(s, lib["id"]).ok)
check("locations: retire refused while a live link exists", pairs(LS.update(s, lib["id"], {"status": "retired"}, ACT).problems) == ["id:in_use"])
check("locations: delete refused while a live link exists", pairs(LS.soft_delete(s, lib["id"], ACT).problems) == ["id:in_use"] and LS.soft_delete(s, lib["id"], ACT).code == "conflict")
S.end(s, v_lib["id"], ACT, now=tick())
check("locations: still in use while a second live link remains", pairs(LS.update(s, lib["id"], {"status": "retired"}, ACT).problems) == ["id:in_use"])
for other in LS.live_links_at(s, lib["id"]):
    S.end(s, other["id"], ACT, now=tick())
check("locations: retire allowed once the link is ended", LS.update(s, lib["id"], {"status": "retired"}, ACT, now=tick()).ok)
check("locations: a retired location accepts no new link", pairs(link(venue, lib, "operates_at", "venue").problems) == ["location_id:retired"])
free = place("Free")
check("locations: delete a location with no links", LS.soft_delete(s, free["id"], ACT, now=tick()).ok)
check("locations: unrelated updates unaffected", LS.update(s, cabin["id"], {"description": "cabin"}, ACT, now=tick()).ok)
addr = {"usage": "civic", "street_number": "9", "street": "Elm Street", "locality": "Boulder", "postal_code": "80302", "country": "US"}
first = LS.create(s, {"name": "Nine Elm", "addresses": [addr]}, ACT, now=tick())
check("locations: first use of an address has no matches", first.ok and "address_matches" not in first.data, str(first))
second = LS.create(s, {"name": "Nine Elm again", "addresses": [dict(addr, street="ELM ST.")]}, ACT, now=tick())
check("locations: same address reported as a match, never merged", second.ok and second.data["address_matches"] == [first.data["id"]] and second.data["id"] != first.data["id"], str(second))
check("locations: matches are not stored", "address_matches" not in raw("locations", second.data["id"]))
check("locations: find by address returns the visible matches", sorted(z["id"] for z in LS.find_by_address(s, addr).data["records"]) == sorted([first.data["id"], second.data["id"]]))

# ============================ erase support ============================
sole, sh1, sh2 = person("Sole"), person("Share1"), person("Share2")
home_sole, home_shared, home_venue = place("Sole home", addresses=[addr]), place("Shared home"), place("Venue and resident")
for subj, loc in ((sole, home_sole), (sh1, home_shared), (sh2, home_shared), (sh1, home_venue)):
    assert link(subj, loc).ok
assert link(venue, home_venue, "operates_at", "venue").ok
n_before = len(H.live_for(s, "subject_id", sole["id"]))
with s.transaction() as tx:
    out1 = S.scrub_for_individual(s, sole["id"], "system:erase", tx, now=tick())
check("erase: sole resident's link and location scrubbed", out1 == {"links_scrubbed": 1, "locations_scrubbed": 1}, str(out1))
sl_ = raw("locations", home_sole["id"])
check("erase: location retired with its details removed", sl_["status"] == "retired" and "name" not in sl_ and "addresses" not in sl_ and "address_keys" not in sl_ and sl_["is_residential"] is False, str(sl_))
ll = raw("location_links", H.live_for(s, "subject_id", sole["id"])[0]["id"]) if H.live_for(s, "subject_id", sole["id"]) else None
check("erase: the link is a tombstone", ll is None, str(ll))
tomb = [x for x in s.data["test_location_links"].values() if x["subject_id"] == sole["id"]][0]
check("erase: tombstone keeps ids, drops the description", "deleted_at" in tomb and tomb["status"] == "ended" and not any(k in tomb for k in H.SCRUB_FIELDS) and tomb["location_id"] == home_sole["id"], str(tomb))
with s.transaction() as tx:
    out2 = S.scrub_for_individual(s, sh1["id"], "system:erase", tx, now=tick())
check("erase: shared home stays with the other resident", out2["links_scrubbed"] == 2 and out2["locations_scrubbed"] == 0, str(out2))
check("erase: shared home details kept and still residential", raw("locations", home_shared["id"]).get("name") == "Shared home" and raw("locations", home_shared["id"])["is_residential"] is True)
check("erase: a venue's location is kept and no longer residential", raw("locations", home_venue["id"]).get("name") == "Venue and resident" and raw("locations", home_venue["id"])["is_residential"] is False)
with s.transaction() as tx:
    out3 = S.scrub_for_individual(s, sh2["id"], "system:erase", tx, now=tick())
check("erase: last resident leaves the shared home scrubbed", out3["locations_scrubbed"] == 1 and raw("locations", home_shared["id"])["status"] == "retired")
with s.transaction() as tx:
    out4 = S.scrub_for_individual(s, NOPE, "system:erase", tx, now=tick())
check("erase: a person with no links is a no-op", out4 == {"links_scrubbed": 0, "locations_scrubbed": 0})

print(f"\n{total - len(fails)}/{total} checks passed")
if fails:
    print("FAILED:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("OK")
