"""Dry run of the organization test suite loader against an in-memory store (nothing touches Firebase, no key needed).
Run from enjoy_router/:  python3 run_org_test_suite_tests.py"""
import json, pathlib, sys
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud.memory_doc_store import MemoryDocStore
from crud_endpoint import handle_admin, make_failure_limiter
import bulk_load, org_test_suite_data as D

KEY = "k" * 16 + "Z" * 16 + "-dry-run-key"
fails, total = [], 0


def check(label, ok, detail=""):
    global total
    total += 1
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else "  " + str(detail)[:300]))
    if not ok:
        fails.append(label)


def make_call():
    store, limiter = MemoryDocStore(""), make_failure_limiter()
    def call(coll, op, **args):
        r = handle_admin("POST", "Bearer " + KEY, json.dumps({"collection": coll, "op": op, "args": args}).encode(), KEY, "v", store, limiter,
                         datetime.now(timezone.utc))
        return r.status, r.body
    return call


call = make_call()
plan = D.build()
quiet = lambda *_: None
data = lambda r: (r[1] or {}).get("data") or {}


def live(coll):
    return [x for x in data(call(coll, "list", limit=200)).get("records", [])]


# --- the plan itself
keys = [o["key"] for o in plan["orgs"]]
check("organization keys are unique", len(keys) == len(set(keys)))
check("place keys are unique", len({p["key"] for p in plan["places"]}) == len(plan["places"]))
check("venue slugs are unique", len({v["data"]["slug"] for v in plan["venues"]}) == len(plan["venues"]))
check("every record carries the marker", all(D.MARKER in o["data"]["notes"] for o in plan["orgs"])
      and all(D.MARKER in p["data"]["description"] for p in plan["places"]) and all(D.MARKER in v["data"]["notes"] for v in plan["venues"]))
check("no test venue is public", all(v["data"]["is_public_venue"] is False for v in plan["venues"]))
check("BVSD has the 55 state-list schools", len(D.BVSD_SCHOOLS) == 55 and len(set(D.BVSD_SCHOOLS)) == 55)
check("every Boulder-address school is on the state list", set(D.BOULDER_SCHOOL_ADDRESSES) <= set(D.BVSD_SCHOOLS))
check("St. Vrain has 20 schools", len(D.SVVSD_SCHOOLS) == 20 and len(set(D.SVVSD_SCHOOLS)) == 20)

# --- load
res = bulk_load.load(plan, call, say=quiet)
check("load reports no refusals", res["errors"] == [], res["errors"][:5])
c = res["counts"]
check("organizations created", c["organizations"] == len(plan["orgs"]), c)
check("venues created", c["venues"] == len(plan["venues"]), c)
check("organization links created", c["organization_links"] == len([l for l in plan["links"] if l[2].startswith("o:")]) + 0
      + len([1 for l in plan["links"] if False]), c)
n_venue_links = len(plan["venues"])
check("location links = org-to-place links + one operates_at per venue",
      c["location_links"] == len([l for l in plan["links"] if l[2].startswith("p:")]) + n_venue_links, c)
check("places = planned places + one new place per venue with a typed address",
      c["places"] == len(plan["places"]) + len([v for v in plan["venues"] if v.get("address")]), c)
print("     counts:", c)

orgs = live("organizations")
byname = {o["name"]: o for o in orgs}
check("all organizations are readable", len(orgs) == len(plan["orgs"]))
check("every organization has the marker", all(D.MARKER in o.get("notes", "") for o in orgs))
check("Breads of the World is inactive", byname["Breads of the World, LLC"]["status"] == "inactive")

venues = {v["name"]: v for v in live("venues")}
check("cafes with a place are active, Baseline (closed) and Norlin (no address) are not",
      venues["OZO Coffee Arapahoe"]["status"] == "active" and venues["Amante Coffee Baseline"]["status"] == "inactive"
      and venues["The Laughing Goat (Norlin Commons)"]["status"] == "inactive", {k: v["status"] for k, v in venues.items()})
check("no loaded venue is public", all(v["is_public_venue"] is False for v in venues.values()))

# the shared building: one place, two school links
aurora = [p for p in live("locations") if "3995 E Aurora" in p.get("name", "")]
check("High Peaks and BCSIS share one place", len(aurora) == 1)
if aurora:
    lk = data(call("location_links", "list", filters={"location_id": aurora[0]["id"]}, limit=50)).get("records", [])
    check("that place has two live operates_at links from two organizations",
          len(lk) == 2 and {l["subject_type"] for l in lk} == {"organization"}, lk)
# Roastery: org and cafe share one place
roast = [p for p in live("locations") if p.get("name") == "OZO Roastery and Lab"]
if roast:
    lk = data(call("location_links", "list", filters={"location_id": roast[0]["id"]}, limit=50)).get("records", [])
    check("Ozo (organization) and the Roastery Cafe (venue) both operate at the roastery place",
          {l["subject_type"] for l in lk} == {"organization", "venue"}, lk)
# Norlin is inside the campus
norlin = [p for p in live("locations") if p.get("name") == "Norlin Library"]
campus = [p for p in live("locations") if p.get("name") == "CU Boulder campus"]
check("Norlin Library is a place inside the CU Boulder campus place",
      norlin and campus and norlin[0].get("part_of_location_id") == campus[0]["id"])
# Panera chain
def links_from(name):
    return [(l["relationship"], l["organization_id"]) for l in
            data(call("organization_links", "list", filters={"subject_id": byname[name]["id"]}, limit=50)).get("records", [])]
check("Breads of the World is succeeded by Manna", ("succeeded_by", byname["Manna Development Group"]["id"]) in links_from("Breads of the World, LLC"))
check("Panera Bread Company is part of Panera Brands and affiliated with JAB",
      {("part_of", byname["Panera Brands"]["id"]), ("affiliated_with", byname["JAB Holding Company"]["id"])} <= set(links_from("Panera Bread Company")))
check("Norlin Commons venue is operated by the Goat and part of CU Boulder",
      {("operated_by", byname["The Laughing Goat"]["id"]), ("part_of", byname["University of Colorado Boulder"]["id"])}
      <= set((l["relationship"], l["organization_id"]) for l in data(call("organization_links", "list", filters={"subject_id": venues["The Laughing Goat (Norlin Commons)"]["id"]}, limit=50)).get("records", [])))
check("BVSD has 56 organizations part of it (55 schools + the board)",
      len(data(call("organization_links", "list", filters={"organization_id": byname["Boulder Valley School District"]["id"], "relationship": "part_of"}, limit=200)).get("records", [])) == 56)

# --- a second load is refused by the CLI guard (find_existing)
check("find_existing sees the loaded records", len(bulk_load.find_existing(call, D.MARKER)) == len(plan["orgs"]) + len(plan["venues"]))

# --- cleanup
out = bulk_load.cleanup(call, res["ids"], say=quiet)
check("cleanup reports no errors", out["errors"] == [], out["errors"][:5])
for coll in ("organizations", "venues", "locations", "organization_links", "location_links"):
    check(f"nothing live left in {coll}", live(coll) == [], len(live(coll)))
check("find_existing is empty after cleanup", bulk_load.find_existing(call, D.MARKER) == [])

# --- cleanup without a saved manifest (scan by marker)
call2 = make_call()
res2 = bulk_load.load(plan, call2, say=quiet)
keep = call2("organizations", "create", data={"name": "A real organization", "notes": "not a test record"})
check("an unmarked organization is created alongside", keep[0] == 200)
found = bulk_load.scan_manifest(call2, D.MARKER, say=quiet)
check("scan finds every loaded organization, venue and link",
      len(found["orgs"]) == res2["counts"]["organizations"] and len(found["venues"]) == res2["counts"]["venues"]
      and len(set(found["org_links"])) == res2["counts"]["organization_links"]
      and len(set(found["loc_links"])) == res2["counts"]["location_links"], {k: len(v) for k, v in found.items()})
check("scan finds every place", len(found["places"]) == res2["counts"]["places"], len(found["places"]))
out2 = bulk_load.cleanup(call2, found, say=quiet)
check("scan cleanup reports no errors", out2["errors"] == [], out2["errors"][:5])
left = data(call2("organizations", "list", limit=200)).get("records", [])
check("only the unmarked organization remains", [o["name"] for o in left] == ["A real organization"], [o["name"] for o in left][:5])
for coll in ("venues", "locations", "organization_links", "location_links"):
    check(f"nothing live left in {coll} (scan cleanup)", data(call2(coll, "list", limit=200)).get("records", []) == [])

# --- load, remove, load again on the same store (a removed venue keeps its slug)
call3 = make_call()
r1 = bulk_load.load(plan, call3, say=quiet)
bulk_load.cleanup(call3, r1["ids"], say=quiet)
r2 = bulk_load.load(plan, call3, say=quiet)
check("loading again after a cleanup works (slugs get a suffix)", r2["errors"] == [] and r2["counts"] == r1["counts"], r2["errors"][:3])
slugs = [v["slug"] for v in data(call3("venues", "list", limit=200)).get("records", [])]
check("reloaded venues have _2 slugs", len(slugs) == 13 and all(s.endswith("_2") for s in slugs), slugs[:3])

print(f"\n{total - len(fails)}/{total} passed")
sys.exit(1 if fails else 0)
