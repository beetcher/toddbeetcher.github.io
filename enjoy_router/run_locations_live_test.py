#!/usr/bin/env python3
"""Live test of locations and location links on the deployed functions. Run from enjoy_router/:  python3 run_locations_live_test.py
Writes ONLY through the test door (enjoy_crud_test, collections prefixed test_) and cleans up after itself. The Console door
(enjoy_admin) is used for READS and refusals only (it reads the real collections, which proves their indexes exist).
The key is read from .env.launch-ai-workshop and never printed."""
import json, pathlib, sys, time, urllib.request, urllib.error

HERE = pathlib.Path(__file__).resolve().parent
BASE = "https://us-central1-launch-ai-workshop.cloudfunctions.net/"
KEY = next((l.split("=", 1)[1].strip().strip('"\'') for l in (HERE / ".env.launch-ai-workshop").read_text().splitlines() if l.startswith("ICDT_ADMIN_KEY=")), "")
if len(KEY) < 32:
    sys.exit("no admin key found")
fails, total = [], 0

def call(fn, coll, op, **args):
    req = urllib.request.Request(BASE + fn, data=json.dumps({"collection": coll, "op": op, "args": args}).encode(),
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read() or b"{}")
        except ValueError: return e.code, {}
    except Exception as e:
        return 0, {"error": type(e).__name__}

T = lambda coll, op, **a: call("enjoy_crud_test", coll, op, **a)
A = lambda coll, op, **a: call("enjoy_admin", coll, op, **a)

def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else "  " + str(detail)[:300]))

data = lambda r: (r[1] or {}).get("data") or {}
probs = lambda r: sorted(f"{p['field']}:{p['issue']}" for p in ((r[1] or {}).get("error") or {}).get("problems", []))
people, places, links = [], [], []

def person(name, **kw):
    r = T("individuals", "create", data={"given_name": name, **kw}); check("create person " + name, r[0] == 200, r)
    if r[0] == 200: people.append(data(r)["id"])
    return data(r)

def place(**kw):
    r = T("locations", "create", data=kw); check("create location " + str(kw.get("name", "(unnamed)")), r[0] == 200, r)
    if r[0] == 200: places.append(data(r)["id"])
    return data(r)

def link(p, loc, rel="resides_at", **kw):
    r = T("location_links", "create", data={"subject_type": "individual", "subject_id": p["id"], "location_id": loc["id"], "relationship": rel, **kw})
    if r[0] == 200: links.append(data(r)["id"])
    return r

ann, bob, cy = person("Livetest Ann"), person("Livetest Bob"), person("Livetest Cy")
addr = {"usage": "civic", "street_number": "9001", "street": "Livetest Road", "locality": "Boulder", "region": "CO", "postal_code": "80302", "country": "US", "is_primary": True}
home = place(name="Livetest home", addresses=[addr],
             geometries=[{"role": "center", "geometry": {"type": "Point", "coordinates": [-105.27, 40.01]}}, {"role": "entrance", "label": "gate", "geometry": {"type": "Point", "coordinates": [-105.271, 40.011]}},
                         {"role": "boundary", "geometry": {"type": "Polygon", "coordinates": [[[-105.272, 40.009], [-105.268, 40.009], [-105.268, 40.012], [-105.272, 40.012], [-105.272, 40.009]]]}}],
             time_zone="America/Denver")
got = data(T("locations", "get", id=home["id"])).get("geometries", [])
check("location stored with all its GPS shapes", len(got) == 3)
check("the polygon boundary came back as plain GeoJSON (Firestore refuses arrays inside arrays; the store wraps them)",
      got and got[2]["geometry"]["coordinates"] == [[[-105.272, 40.009], [-105.268, 40.009], [-105.268, 40.012], [-105.272, 40.012], [-105.272, 40.009]]], got)
check("address key built", len(home.get("address_keys", [])) == 1)
r = T("locations", "create", data={"name": "Livetest twin", "addresses": [dict(addr, street="LIVETEST RD.", is_primary=False)]}); 
if r[0] == 200: places.append(data(r)["id"])
check("same address is reported, not merged", r[0] == 200 and data(r).get("address_matches") == [home["id"]], r)
r = T("locations", "find_by_address", address=dict(addr, street="livetest road")); check("find_by_address (array_contains)", r[0] == 200 and data(r).get("count") == 2, r)
check("bad GPS refused", probs(T("locations", "create", data={"name": "x", "geometries": [{"role": "center", "geometry": {"type": "Point", "coordinates": [999, 1]}}]})) == ["geometries:invalid_value"])
check("no identity refused", T("locations", "create", data={"description": "only words"})[0] == 400)

r = link(ann, home, is_primary=True, valid_from="2019-06"); check("link Ann to the home", r[0] == 200, r)
la = data(r)
check("home is now residential", data(T("locations", "get", id=home["id"])).get("is_residential") is True)
check("overlapping duplicate link is 400", probs(link(ann, home, valid_from="2020")) == ["location_id:duplicate"])
check("retire refused while linked (409)", T("locations", "update", id=home["id"], changes={"status": "retired"})[0] == 409)
check("delete refused while linked (409)", T("locations", "soft_delete", id=home["id"])[0] == 409)
lb = data(link(bob, home, valid_from="2021"))
time.sleep(1.2)  # updated_at has one-second resolution
r = T("location_links", "end", id=la["id"], valid_to="2026-03-31"); check("end Ann's link", r[0] == 200, r)
check("ending twice is 409", T("location_links", "end", id=la["id"])[0] == 409)
check("home still residential through Bob", data(T("locations", "get", id=home["id"])).get("is_residential") is True)
new = place(name="Livetest new home")
r = link(ann, new, is_primary=True, valid_from="2026-04"); check("link Ann to the new home", r[0] == 200, r)

# merge repoints links, unmerge puts them back
lc = data(link(cy, new, "owns"))
r = T("individuals", "merge", survivor_id=ann["id"], duplicate_id=cy["id"], reason="live test"); check("merge Cy into Ann", r[0] == 200, r)
ev = data(r).get("id")
check("Cy's link now belongs to Ann", data(T("location_links", "get", id=lc["id"])).get("subject_id") == ann["id"])
if ev:
    check("unmerge", T("individuals", "unmerge", id=ev)[0] == 200)
    check("Cy's link is back with Cy", data(T("location_links", "get", id=lc["id"])).get("subject_id") == cy["id"])

# erase scrubs the person's links and a location nobody else is linked to
r = T("individuals", "erase", id=cy["id"]); check("erase Cy", r[0] == 200 and data(r).get("links_scrubbed") == 1, r)
check("Cy's link is gone from reads", T("location_links", "get", id=lc["id"])[0] == 404)
r = T("individuals", "erase", id=ann["id"]); check("erase Ann", r[0] == 200 and data(r).get("links_scrubbed") == 2, r)
check("Ann's sole new home was scrubbed", data(T("locations", "get", id=new["id"])).get("status") == "retired" and "name" not in data(T("locations", "get", id=new["id"])))
check("the shared home keeps its details for Bob", data(T("locations", "get", id=home["id"])).get("name") == "Livetest home")

# every list filter needs its own index, on the test collections and on the real ones
for f in ({"status": "active"}, {"kind": "site"}, {"is_residential": True}):
    check("test list locations by " + list(f)[0] + " (index)", T("locations", "list", filters=f)[0] == 200)
    check("Console list locations by " + list(f)[0] + " (index, real collection)", A("locations", "list", filters=f)[0] == 200)
for f in ({"subject_id": bob["id"]}, {"location_id": home["id"]}, {"subject_type": "individual"}, {"relationship": "resides_at"}, {"status": "active"}):
    check("test list links by " + list(f)[0] + " (index)", T("location_links", "list", filters=f)[0] == 200)
    check("Console list links by " + list(f)[0] + " (index, real collection)", A("location_links", "list", filters=f)[0] == 200)
check("unfiltered lists", T("locations", "list")[0] == 200 and A("locations", "list")[0] == 200 and A("location_links", "list")[0] == 200)
check("Console find_by_address (real collection)", A("locations", "find_by_address", address=addr)[0] == 200)
check("Console cannot erase", A("individuals", "erase", id=bob["id"])[0] == 400)
check("end is only for links", T("locations", "end", id=home["id"])[0] == 400)

# venues on places: one-window add, expand, move, activation gate, contact pointer
venues = []
stamp = str(int(time.time()))
vaddr = {"usage": "civic", "street_number": "9002", "street": "Livetest Venue Way", "locality": "Boulder", "region": "CO", "postal_code": "80302", "country": "US", "is_primary": True}
vdata = lambda n, **kw: {"name": "Livetest " + n, "slug": "livetest_" + n.lower() + "_" + stamp, "status": "inactive", "is_public_venue": True, **kw}
r = T("venues", "create_with_place", data=vdata("Venue", email="Livetest@Example.com", contact_individual_id=bob["id"]), address=vaddr)
check("create_with_place 200", r[0] == 200, r)
v = data(r)
if v.get("id"): venues.append(v["id"])
if v.get("place", {}).get("location_id"): places.append(v["place"]["location_id"])
check("venue starts inactive, email lowercased, place and contact shown",
      v.get("status") == "inactive" and v.get("email") == "livetest@example.com" and v.get("place", {}).get("address", {}).get("street") == "Livetest Venue Way"
      and v.get("main_contact", {}).get("id") == bob["id"], v)
check("expand on get shows the place", data(T("venues", "get", id=v["id"], expand=True)).get("place", {}).get("name") == "Livetest Venue")
check("get without expand has no place", "place" not in data(T("venues", "get", id=v["id"])))
r = T("venues", "update", id=v["id"], changes={"status": "active"}, expected_updated_at=v["updated_at"])
check("activate with a place works", r[0] == 200 and "status" in data(r).get("changed", []), r)
check("venue reads back as active", data(T("venues", "get", id=v["id"])).get("status") == "active")
r = T("venues", "create", data=vdata("Active", status="active"))
check("create already active is refused (place_required)", r[0] == 400 and "status:place_required" in probs(r), r)
if r[0] == 200: venues.append(data(r)["id"])
r = T("venues", "create_with_place", data=vdata("Bad"), address={"locality": "x"})
check("bad address is refused", r[0] == 400, r)
if r[0] == 200: venues.append(data(r)["id"])
r = T("venues", "set_place", id=v["id"], address={**vaddr, "street_number": "9003"}); check("set_place to a new address", r[0] == 200, r)
if data(r).get("place", {}).get("location_id"): places.append(data(r)["place"]["location_id"])
spot = place(name="Livetest saved spot", addresses=[{**addr, "street_number": "9004"}])
r = T("venues", "set_place", id=v["id"], location_id=spot["id"]); check("set_place to a saved place", r[0] == 200 and data(r).get("place", {}).get("location_id") == spot["id"], r)
r = T("venues", "set_place", id=v["id"], location_id=spot["id"]); check("same place again changes nothing", r[0] == 200 and data(r).get("changed") is False, r)
for l in (data(T("location_links", "list", filters={"subject_id": v["id"]})).get("records") or []):
    links.append(l["id"])
check("Console door: list venues with expand (real collection)", A("venues", "list", expand=True)[0] == 200)
check("Console door: set_place needs an id", A("venues", "set_place")[0] == 400)
check("expand is refused on other modules", T("locations", "list", expand=True)[0] == 400)

# clean up
for i in links:
    T("location_links", "soft_delete", id=i)
for i in venues:
    T("venues", "soft_delete", id=i)
for i in places:
    T("locations", "soft_delete", id=i)
for i in people:
    T("individuals", "soft_delete", id=i)
check("clean up: the home deletes once its links are gone", T("locations", "get", id=home["id"])[0] == 404)
print(f"\n{total - len(fails)}/{total} checks passed")
print("OK" if not fails else "FAILED: " + ", ".join(fails))
sys.exit(1 if fails else 0)
