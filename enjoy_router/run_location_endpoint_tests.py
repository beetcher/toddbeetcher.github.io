#!/usr/bin/env python3
"""In-memory tests for the location endpoint wiring: both doors, the new ops, privacy, merge and erase through the doors.
Run from enjoy_router/:  python3 run_location_endpoint_tests.py   (add -v to list every check). Nothing touches Firebase."""
import json
import logging
import pathlib
import sys
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud_endpoint import ADMIN_OPS, OPS, handle_admin, handle_crud_test, make_failure_limiter  # noqa: E402

KEY = "k" * 16 + "Z" * 16 + "-test-key-not-real"
NOW = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)
fails: list = []
total = 0


def check(label, ok, detail=""):
    global total
    total += 1
    if not ok:
        fails.append(label)
    if not ok or "-v" in sys.argv:
        print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")


store = MemoryDocStore("test_")
limiter = make_failure_limiter()
grab = type("G", (logging.Handler,), {"lines": [], "emit": lambda self, r: self.lines.append(r.getMessage())})()
logging.getLogger("enjoy_router").addHandler(grab)
logging.getLogger("enjoy_router").setLevel(logging.INFO)


def door(fn, body):
    return fn("POST", f"Bearer {KEY}", json.dumps(body).encode(), KEY, "v", store, limiter, NOW)


T = lambda coll, op, **a: door(handle_crud_test, {"collection": coll, "op": op, "args": a})
A = lambda coll, op, **a: door(handle_admin, {"collection": coll, "op": op, "args": a})
prob = lambda r: sorted(f"{p['field']}:{p['issue']}" for p in r.body["error"]["problems"])

check("ops registered", {"end", "find_by_address"} <= set(OPS) and {"end", "find_by_address"} <= ADMIN_OPS and "erase" not in ADMIN_OPS)

# ---- locations through the test door
r = T("locations", "create", data={"name": "Home on Elm", "addresses": [{"usage": "civic", "street_number": "9", "street": "Elm St", "locality": "Boulder", "postal_code": "80302", "country": "US", "is_primary": True}],
                                   "geometries": [{"role": "center", "geometry": {"type": "Point", "coordinates": [-105.27, 40.01]}}, {"role": "entrance", "label": "door", "geometry": {"type": "Point", "coordinates": [-105.2701, 40.0101]}}]})
check("test door: create location", r.status == 200 and r.body["data"]["created_by"] == "system:crud_test" and len(r.body["data"]["geometries"]) == 2, str(r.body))
loc = r.body["data"]
check("test door: stored under test_ only", sorted(store.data) == ["test_locations"], str(list(store.data)))
check("test door: get", T("locations", "get", id=loc["id"]).body["data"]["id"] == loc["id"])
r = T("locations", "create", data={"name": "Elm again", "addresses": [{"usage": "civic", "street_number": "9", "street": "ELM STREET", "locality": "Boulder", "postal_code": "80302", "country": "US"}]})
check("test door: duplicate address is reported, not merged", r.status == 200 and r.body["data"]["address_matches"] == [loc["id"]], str(r.body))
r = T("locations", "create", data={"description": "no identity"})
check("test door: refused create is 400 with problems", r.status == 400 and r.body["error"]["code"] == "validation_failed", str(r.body))
r = T("locations", "create", data={"name": "x", "is_residential": True})
check("test door: readOnly field refused", r.status == 400 and prob(r) == ["is_residential:not_allowed"])
r = T("locations", "create", data={"name": "G", "geometries": [{"role": "center", "geometry": {"type": "Point", "coordinates": [500, 40]}}]})
check("test door: bad GPS refused", r.status == 400 and prob(r) == ["geometries:invalid_value"])
r = T("locations", "list", filters={"status": "active"})
check("test door: list", r.status == 200 and r.body["data"]["count"] == 2)
r = T("locations", "find_by_address", address={"usage": "civic", "street_number": "9", "street": "Elm St.", "locality": "Boulder", "postal_code": "80302-0001", "country": "US"})
check("test door: find_by_address", r.status == 200 and r.body["data"]["count"] == 2, str(r.body))
check("test door: find_by_address on another collection is not supported", T("venues", "find_by_address", address={"street": "x"}).status == 400)
check("test door: end on locations is not supported", T("locations", "end", id=loc["id"]).status == 400)
check("test door: merge on locations is not supported", T("locations", "merge", survivor_id=loc["id"], duplicate_id=loc["id"], reason="x").status == 400)
check("test door: unknown arg refused", T("locations", "get", id=loc["id"], extra=1).status == 400)

# ---- links
pid = T("individuals", "create", data={"given_name": "Maria", "family_name": "Garcia"}).body["data"]["id"]
r = T("location_links", "create", data={"subject_type": "individual", "subject_id": pid, "location_id": loc["id"], "relationship": "resides_at", "is_primary": True, "valid_from": "2019-06"})
check("test door: create link", r.status == 200 and r.body["data"]["status"] == "active", str(r.body))
lk = r.body["data"]
check("test door: location became residential", T("locations", "get", id=loc["id"]).body["data"]["is_residential"] is True)
r = T("location_links", "create", data={"subject_type": "individual", "subject_id": pid, "location_id": loc["id"], "relationship": "resides_at"})
check("test door: overlapping duplicate is 400 with the field named", r.status == 400 and prob(r) == ["location_id:duplicate"], str(r.body))
check("test door: unknown subject", prob(T("location_links", "create", data={"subject_type": "individual", "subject_id": loc["id"], "location_id": loc["id"], "relationship": "resides_at"})) == ["subject_id:not_found"])
check("test door: location_links list by subject", T("location_links", "list", filters={"subject_id": pid}).body["data"]["count"] == 1)
check("test door: location_links list by location", T("location_links", "list", filters={"location_id": loc["id"]}).body["data"]["count"] == 1)
check("test door: two filters not supported", T("location_links", "list", filters={"subject_id": pid, "status": "active"}).status == 400)
check("test door: update notes", T("location_links", "update", id=lk["id"], changes={"notes": "ring twice"}).status == 200)
check("test door: immutable relationship", prob(T("location_links", "update", id=lk["id"], changes={"relationship": "owns"})) == ["relationship:immutable"])
r = T("locations", "update", id=loc["id"], changes={"status": "retired"})
check("test door: retire refused while linked: 409", r.status == 409 and prob(r) == ["id:in_use"], str(r.body))
check("test door: delete refused while linked: 409", T("locations", "soft_delete", id=loc["id"]).status == 409)
r = T("location_links", "end", id=lk["id"], valid_to="2026-03-31")
check("test door: end the link", r.status == 200 and r.body["data"]["changed"] == ["status", "valid_to"], str(r.body))
check("test door: ended link left the location non-residential", T("locations", "get", id=loc["id"]).body["data"]["is_residential"] is False)
check("test door: ending again is 409", T("location_links", "end", id=lk["id"]).status == 409)
check("test door: retire allowed once ended", T("locations", "update", id=loc["id"], changes={"status": "retired"}).status == 200)
r = T("location_links", "end", id=lk["id"], valid_to="soon")
check("test door: ending with a bad date still refused", r.status in (400, 409))
check("test door: link soft delete", T("location_links", "soft_delete", id=lk["id"]).status == 200 and T("location_links", "get", id=lk["id"]).status == 404)

# ---- erase through the test door scrubs links and the home
store2 = MemoryDocStore("test_")
store = store2
pid2 = T("individuals", "create", data={"given_name": "Erin"}).body["data"]["id"]
home = T("locations", "create", data={"name": "Erin's home", "addresses": [{"usage": "civic", "street": "3 Oak St", "country": "US"}]}).body["data"]
T("location_links", "create", data={"subject_type": "individual", "subject_id": pid2, "location_id": home["id"], "relationship": "resides_at", "notes": "n"})
r = T("individuals", "erase", id=pid2)
check("test door: erase reports scrubbed links and locations", r.status == 200 and r.body["data"]["links_scrubbed"] == 1 and r.body["data"]["locations_scrubbed"] == 1, str(r.body))
after = T("locations", "get", id=home["id"])
check("test door: the home is retired and empty", after.status == 200 and after.body["data"]["status"] == "retired" and "addresses" not in after.body["data"] and "name" not in after.body["data"])

# ---- admin door
store = MemoryDocStore("")
r = A("locations", "create", data={"name": "Library", "kind": "site", "time_zone": "America/Denver"})
check("admin door: create location in the real collection", r.status == 200 and r.body["data"]["created_by"] == "user:admin" and sorted(store.data) == ["locations"], str(r.body))
lib = r.body["data"]
vid = A("venues", "create", data={"name": "Library", "slug": "library", "status": "active", "is_public_venue": True, "street_address": "1 Main St", "city": "Boulder", "state_region": "CO",
                                   "postal_code": "80302", "country": "US", "time_zone": "America/Denver", "contact_name": "Pat", "contact_email": "pat@example.com",
                                   "is_accessible": True, "allows_minors": True, "allows_animals": False, "rooms": [{"label": "Main", "max_occupancy": 40}]}).body["data"]["id"]
r = A("location_links", "create", data={"subject_type": "venue", "subject_id": vid, "location_id": lib["id"], "relationship": "operates_at", "valid_from": "2005"})
check("admin door: venue operates_at link", r.status == 200, str(r.body))
vl = r.body["data"]
check("admin door: erase is not enabled", A("individuals", "erase", id=vid).status == 400)
# moving buildings: end one link, start another; the locations never change
new = A("locations", "create", data={"name": "New library building"}).body["data"]
A("location_links", "end", id=vl["id"], valid_to="2026-08-31")
r = A("location_links", "create", data={"subject_type": "venue", "subject_id": vid, "location_id": new["id"], "relationship": "operates_at", "valid_from": "2026-09-01"})
check("admin door: a moved venue gets a new link", r.status == 200, str(r.body))
check("admin door: the old location is unchanged by the move", A("locations", "get", id=lib["id"]).body["data"] == {**lib, "updated_at": A("locations", "get", id=lib["id"]).body["data"]["updated_at"]} or
      all(A("locations", "get", id=lib["id"]).body["data"].get(k) == v for k, v in lib.items() if k != "updated_at"))
check("admin door: the venue has two links, one ended one active", sorted(x["status"] for x in A("location_links", "list", filters={"subject_id": vid}).body["data"]["records"]) == ["active", "ended"])

# privacy through the admin door (no roles yet): a confidential person's home is hidden
cid = A("individuals", "create", data={"given_name": "Cora", "record_privacy": "confidential"}).body["data"]["id"]
ch = A("locations", "create", data={"name": "Cora's house"}).body["data"]
A("location_links", "create", data={"subject_type": "individual", "subject_id": cid, "location_id": ch["id"], "relationship": "resides_at"})
check("admin door: a confidential resident's home is not found", A("locations", "get", id=ch["id"]).status == 404)
check("admin door: and left out of the list", ch["id"] not in [z["id"] for z in A("locations", "list").body["data"]["records"]])
check("admin door: and her link is hidden", A("location_links", "list", filters={"subject_id": cid}).body["data"]["count"] == 0)
oid = A("individuals", "create", data={"given_name": "Ollie"}).body["data"]["id"]
oh = A("locations", "create", data={"name": "Ollie's house"}).body["data"]
A("location_links", "create", data={"subject_type": "individual", "subject_id": oid, "location_id": oh["id"], "relationship": "resides_at"})
check("admin door: an ordinary person's home is visible", A("locations", "get", id=oh["id"]).status == 200 and A("location_links", "list", filters={"subject_id": oid}).body["data"]["count"] == 1)

# merge through the door repoints links
dup = A("individuals", "create", data={"given_name": "Ollie", "family_name": "Dup"}).body["data"]["id"]
dh = A("locations", "create", data={"name": "Dup place"}).body["data"]
dl = A("location_links", "create", data={"subject_type": "individual", "subject_id": dup, "location_id": dh["id"], "relationship": "owns"}).body["data"]
m = A("individuals", "merge", survivor_id=oid, duplicate_id=dup, reason="same person")
check("admin door: merge repoints the link", m.status == 200 and A("location_links", "get", id=dl["id"]).body["data"]["subject_id"] == oid, str(m.body))
check("admin door: unmerge restores it", A("individuals", "unmerge", id=m.body["data"]["id"]).status == 200 and A("location_links", "get", id=dl["id"]).body["data"]["subject_id"] == dup)

# no addresses in the log
text = "\n".join(grab.lines)
check("audit: ops logged, no values", "collection=locations op=create code=ok" in text and "collection=location_links op=end" in text
      and not any(v in text for v in ("Elm", "Oak St", "Cora", "Ollie", "ring twice", "80302")), text[:300])

print(f"\n{total - len(fails)}/{total} checks passed")
if fails:
    print("FAILED:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("OK")
