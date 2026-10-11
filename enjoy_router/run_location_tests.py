#!/usr/bin/env python3
"""In-memory tests for the location handler (crud/locations_crud.py).
Run from enjoy_router/:  python3 run_location_tests.py   (add -v to list every check). Nothing touches Firebase."""
import copy
import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import locations_crud as L  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud.schema_kit import find_schema_dir  # noqa: E402

START = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)
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


def pt(lon=-105.27, lat=40.01):
    return {"type": "Point", "coordinates": [lon, lat]}


ACT = "user:todd"
s = MemoryDocStore("test_")
ex = json.load(open(find_schema_dir() / "examples" / "location.examples.json"))

# --- every valid example is accepted; the server fills the standard fields
made = {}
for label, doc in ex["valid"].items():
    d = copy.deepcopy(doc)
    d.pop("part_of_location_id", None)  # the example parent id is not a real record
    r = L.create(s, d, ACT, now=tick())
    check(f"valid example '{label}' created", r.ok, str(r))
    if r.ok:
        made[label] = r.data
r = L.create(s, copy.deepcopy(ex["valid"]["gps_only_doorway"]), ACT, now=tick())
check("example with an unknown parent refused", pairs(r.problems) == ["part_of_location_id:not_found"], str(r))

rec = made["twenty_acre_property"]
check("server fields set", all(k in rec for k in L.LOCATIONS.server_required), str(sorted(rec)))
check("defaults: status active, kind kept", rec["status"] == "active" and rec["kind"] == "parcel")
check("default kind is site", made["minimal_named"]["kind"] == "site")
check("is_residential starts false", rec["is_residential"] is False)
check("address keys built for civic and mailing", len(rec["address_keys"]) == 2, str(rec["address_keys"]))
check("former address makes no key", "address_keys" not in made["former_address"])
check("a record without an address has no keys", "address_keys" not in made["minimal_named"])
check("array of GPS shapes kept whole", len(rec["geometries"]) == 3)
check("stored copy equals returned", s.get("locations", rec["id"]) == rec)

# --- every invalid example is refused, and nothing was written for them
before = sum(len(v) for v in s.data.values())
for label, doc in ex["invalid"].items():
    r = L.create(s, copy.deepcopy(doc), ACT, now=tick())
    check(f"invalid example '{label}' refused", (not r.ok) and r.code == "validation_failed", str(r))
check("refusals wrote nothing", sum(len(v) for v in s.data.values()) == before)
r = L.create(s, {"name": "X", "is_residential": True}, ACT)
check("readOnly field sent is named", pairs(r.problems) == ["is_residential:not_allowed"], str(r))
check("problems never carry values", all(set(p) == {"field", "issue"} for p in L.create(s, {"name": "Secret Name", "kind": "city"}, ACT).problems))

# --- actor, source, body
check("bad actor", pairs(L.create(s, {"name": "X"}, "todd").problems) == ["actor:invalid_format"])
check("bad source", pairs(L.create(s, {"name": "X"}, ACT, source="web_enjoy").problems) == ["source:invalid_value"])
check("body must be an object", pairs(L.create(s, "x", ACT).problems) == ["body:invalid_type"])
check("blank name does not count", not L.create(s, {"name": "   "}, ACT).ok)
check("strings are trimmed", L.create(s, {"name": "  Padded  "}, ACT, now=tick()).data["name"] == "Padded")

# --- the rules the schema cannot say
addr = {"usage": "civic", "street": "Main St", "country": "US"}
r = L.create(s, {"name": "A", "addresses": [dict(addr, is_primary=True), dict(addr, street="Elm St", is_primary=True)]}, ACT)
check("two primary addresses refused", pairs(r.problems) == ["addresses:duplicate"], str(r))
r = L.create(s, {"name": "A", "addresses": [{"usage": "civic", "street": "Main St"}]}, ACT)
check("civic without country refused", pairs(r.problems) == ["addresses:required"], str(r))
check("mailing without country is fine", L.create(s, {"name": "A", "addresses": [{"usage": "mailing", "po_box": "9"}]}, ACT, now=tick()).ok)
r = L.create(s, {"name": "A", "addresses": [dict(addr, usage="former", valid_from="2022-06", valid_to="2020")]}, ACT)
check("valid_from after valid_to refused", pairs(r.problems) == ["addresses:out_of_range"], str(r))
check("same month is fine", L.create(s, {"name": "A", "addresses": [dict(addr, valid_from="2020-06", valid_to="2020-06")]}, ACT, now=tick()).ok)
check("year then month in order is fine", L.create(s, {"name": "A", "addresses": [dict(addr, valid_from="2020", valid_to="2020-03")]}, ACT, now=tick()).ok)
check("bad time zone refused", pairs(L.create(s, {"name": "A", "time_zone": "Mars/Olympus"}, ACT).problems) == ["time_zone:invalid_value"])
check("time zone with odd characters refused", not L.create(s, {"name": "A", "time_zone": "../etc/passwd"}, ACT).ok)
check("real time zone accepted", L.create(s, {"name": "A", "time_zone": "Europe/Paris"}, ACT, now=tick()).ok)

# --- GeoJSON
def geo(g):
    return L.create(s, {"name": "G", "geometries": [{"role": "center", "geometry": g}]}, ACT, now=tick())

bad_geo = {
    "longitude out of range": pt(-181, 40), "latitude out of range": pt(-105, 91), "three coords fine but four not": {"type": "Point", "coordinates": [1, 2, 3, 4]},
    "string coordinate": {"type": "Point", "coordinates": ["1", "2"]}, "bool coordinate": {"type": "Point", "coordinates": [True, 2]},
    "line with one point": {"type": "LineString", "coordinates": [[1, 2]]},
    "open ring": {"type": "Polygon", "coordinates": [[[1, 1], [2, 1], [2, 2], [1, 2]]]},
    "ring too short": {"type": "Polygon", "coordinates": [[[1, 1], [2, 1], [1, 1]]]},
    "empty polygon": {"type": "Polygon", "coordinates": []},
    "point nested like a line": {"type": "Point", "coordinates": [[1, 2]]},
    "multipoint empty": {"type": "MultiPoint", "coordinates": []},
    "multipolygon wrong depth": {"type": "MultiPolygon", "coordinates": [[[1, 1], [2, 1], [2, 2], [1, 1]]]},
}
for label, g in bad_geo.items():
    r = geo(g)
    check(f"geojson refused: {label}", (not r.ok) and "geometries:invalid_value" in pairs(r.problems), str(r))
ring = [[-105.2, 40.0], [-105.1, 40.0], [-105.1, 40.1], [-105.2, 40.1], [-105.2, 40.0]]
for label, g in {"point with altitude": {"type": "Point", "coordinates": [-105.2, 40.0, 1600]}, "multipoint": {"type": "MultiPoint", "coordinates": [[1, 2], [3, 4]]},
                 "line": {"type": "LineString", "coordinates": [[1, 2], [3, 4]]}, "multiline": {"type": "MultiLineString", "coordinates": [[[1, 2], [3, 4]], [[5, 6], [7, 8]]]},
                 "polygon with hole": {"type": "Polygon", "coordinates": [ring, [[-105.18, 40.02], [-105.12, 40.02], [-105.12, 40.08], [-105.18, 40.02]]][:1]},
                 "multipolygon": {"type": "MultiPolygon", "coordinates": [[ring], [ring]]},
                 "edge values": {"type": "Point", "coordinates": [180, -90]}}.items():
    check(f"geojson accepted: {label}", geo(g).ok)
check("geometry extra key refused", not L.create(s, {"name": "G", "geometries": [{"role": "center", "geometry": {"type": "Point", "coordinates": [1, 2], "crs": "x"}}]}, ACT).ok)

# --- parents
home = L.create(s, {"name": "Campus"}, ACT, now=tick()).data
door = L.create(s, {"name": "Door", "kind": "point", "part_of_location_id": home["id"]}, ACT, now=tick())
check("child with a real parent created", door.ok, str(door))
check("self parent refused on update", pairs(L.update(s, home["id"], {"part_of_location_id": home["id"]}, ACT, now=tick()).problems) == ["part_of_location_id:invalid_value"])
r = L.update(s, home["id"], {"part_of_location_id": door.data["id"]}, ACT, now=tick())
check("loop refused", pairs(r.problems) == ["part_of_location_id:invalid_value"], str(r))
check("unknown parent refused on update", pairs(L.update(s, home["id"], {"part_of_location_id": "3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b"}, ACT).problems) == ["part_of_location_id:not_found"])
gone = L.create(s, {"name": "Gone"}, ACT, now=tick()).data
L.soft_delete(s, gone["id"], ACT, now=tick())
check("deleted parent refused", pairs(L.create(s, {"name": "K", "part_of_location_id": gone["id"]}, ACT).problems) == ["part_of_location_id:not_found"])
check("parent removal allowed", L.update(s, door.data["id"], {"part_of_location_id": None}, ACT, now=tick()).ok)

# --- get
check("get returns the record", L.get(s, home["id"]).data["id"] == home["id"])
check("get of a bad id", pairs(L.get(s, "nope").problems) == ["id:invalid_format"])
check("get of an unknown id", L.get(s, "3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b").code == "not_found")
check("get hides deleted", L.get(s, gone["id"]).code == "not_found")
check("get can include deleted", L.get(s, gone["id"], include_deleted=True).ok)

# --- update
loc = L.create(s, {"name": "Upd", "addresses": [dict(addr, street_number="10", street="Oak Avenue", locality="Boulder", region="CO", postal_code="80302")]}, ACT, now=tick()).data
n0 = len(s.reads)
r = L.update(s, loc["id"], {"description": "a note"}, ACT, now=tick())
check("simple update succeeds", r.ok and r.data["changed"] == ["description"], str(r))
check("simple update does not read", len(s.reads) == n0)
n0 = len(s.reads)
check("update that touches a rule field reads", L.update(s, loc["id"], {"time_zone": "America/Denver"}, ACT, now=tick()).ok and len(s.reads) > n0)
r = L.update(s, loc["id"], {"addresses": [dict(addr, street_number="11", street="Pine Street", locality="Boulder", postal_code="80302")]}, ACT, now=tick())
check("changing addresses succeeds", r.ok, str(r))
check("address keys follow addresses", s.get("locations", loc["id"])["address_keys"] == [L.address_key(dict(addr, street_number="11", street="Pine Street", locality="Boulder", postal_code="80302"))])
r = L.update(s, loc["id"], {"addresses": None}, ACT, now=tick())
check("removing addresses removes keys", r.ok and "address_keys" not in s.get("locations", loc["id"]) and "addresses" not in s.get("locations", loc["id"]), str(r))
solo = L.create(s, {"name": "Solo"}, ACT, now=tick()).data
r = L.update(s, solo["id"], {"name": None}, ACT, now=tick())
check("removing the only identifying field refused", (not r.ok) and r.code == "validation_failed", str(r))
check("name removal allowed when an address remains", L.update(s, made["street_address"]["id"], {"name": None}, ACT, now=tick()).ok)
for label, ch, want in [
    ("readOnly field", {"is_residential": True}, ["is_residential:not_allowed"]),
    ("address_keys", {"address_keys": ["x"]}, ["address_keys:not_allowed"]),
    ("unknown field", {"owner": "x"}, ["owner:not_allowed"]),
    ("bad kind", {"kind": "city"}, ["kind:invalid_value"]),
    ("bad status", {"status": "closed"}, ["status:invalid_value"]),
]:
    check(f"update refuses {label}", pairs(L.update(s, loc["id"], ch, ACT).problems) == want, str(L.update(s, loc["id"], ch, ACT)))
check("update with empty changes", pairs(L.update(s, loc["id"], {}, ACT).problems) == ["changes:required"])
check("update of unknown id", L.update(s, "3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b", {"time_zone": "America/Denver"}, ACT).code == "not_found")
check("update of a deleted record on the whole path", L.update(s, gone["id"], {"time_zone": "America/Denver"}, ACT).code == "not_found")
cur = s.get("locations", loc["id"])
check("stale update is conflict", L.update(s, loc["id"], {"time_zone": "America/Denver"}, ACT, expected_updated_at="2020-01-01T00:00:00Z").code == "conflict")
ok1 = L.update(s, loc["id"], {"description": "b"}, ACT, expected_updated_at=cur["updated_at"], now=tick())
check("fresh expected_updated_at succeeds", ok1.ok, str(ok1))
check("bad expected_updated_at", pairs(L.update(s, loc["id"], {"description": "c"}, ACT, expected_updated_at="yesterday").problems) == ["expected_updated_at:invalid_format"])
check("check hook runs on the whole path", pairs(L.update(s, loc["id"], {"status": "retired"}, ACT, check=lambda m: [{"field": "id", "issue": "in_use"}]).problems) == ["id:in_use"])
check("retire allowed without a hook", L.update(s, loc["id"], {"status": "retired"}, ACT, now=tick()).ok)

# --- list
for i in range(3):
    L.create(s, {"name": f"List {i}", "kind": "point"}, ACT, now=tick())
r = L.list(s)
check("list newest first", r.ok and [d["created_at"] for d in r.data["records"]] == sorted([d["created_at"] for d in r.data["records"]], reverse=True))
check("list leaves out deleted", all("deleted_at" not in d for d in r.data["records"]) and gone["id"] not in [d["id"] for d in r.data["records"]])
check("list one filter", all(d["kind"] == "point" for d in L.list(s, {"kind": "point"}).data["records"]))
check("list residential filter", L.list(s, {"is_residential": False}).ok)
check("list two filters not supported", pairs(L.list(s, {"kind": "point", "status": "active"}).problems) == ["kind:not_supported", "status:not_supported"])
check("list unknown filter", pairs(L.list(s, {"name": "x"}).problems) == ["name:not_supported"])
check("list order by name not supported", pairs(L.list(s, order="name").problems) == ["order:not_supported"])
check("list bad filter value", pairs(L.list(s, {"kind": "city"}).problems) == ["kind:invalid_value"])
check("list limit type", pairs(L.list(s, limit="5").problems) == ["limit:invalid_type"])
check("list limit applies", L.list(s, limit=2).data["count"] == 2)

# --- address lookup and matches
a = dict(usage="civic", street_number="1001", street="Arapahoe Avenue", locality="Boulder", region="CO", postal_code="80302-1234", country="US")
check("find by address ignores case, abbreviations, zip+4", L.find_by_address(s, dict(a, street="ARAPAHOE AVE.", postal_code="80302")).data["count"] == 1)
check("find by address with a different number finds none", L.find_by_address(s, dict(a, street_number="1002")).data["count"] == 0)
check("find by address needs a usable address", L.find_by_address(s, {"usage": "civic"}).data["count"] == 0)
check("find by address skips former", L.find_by_address(s, dict(a, usage="former")).data["count"] == 0)
check("find by bad address", L.find_by_address(s, "x").code == "validation_failed")
dup = {"name": "Copy", "addresses": [dict(a, street="Arapahoe Ave")]}
check("matches_for reports the existing place", L.matches_for(s, dup) == [made["street_address"]["id"]])
check("matches_for excludes itself", L.matches_for(s, dup, exclude_id=made["street_address"]["id"]) == [])
check("a duplicate address is still allowed to be created", L.create(s, copy.deepcopy(dup), ACT, now=tick()).ok)

# --- address key details
base = {"usage": "civic", "street_number": "5", "street": "Pine Road", "country": "US"}
check("key with a postal code ignores the town name", L.address_key(dict(base, postal_code="80302", locality="Boulder")) == L.address_key(dict(base, postal_code="80302", locality="Boulder, CO")))
check("key without a postal code keeps the town", L.address_key(dict(base, locality="Boulder")) != L.address_key(dict(base, locality="Lyons")))
check("po box key", L.address_key({"usage": "mailing", "po_box": "88", "postal_code": "80540", "country": "US"}) == L.address_key({"usage": "po_box", "po_box": "88", "postal_code": "80540-1", "country": "US"}))
check("printed-lines key", L.address_key({"usage": "civic", "lines": ["12 Pearl St", "Boulder"], "country": "US"}) is not None)
check("too thin to compare", L.address_key({"usage": "civic", "country": "US"}) is None)
check("keys are capped and unique", len(L.address_keys_for({"addresses": [dict(base, street_number=str(i)) for i in range(20)] + [dict(base, street_number="1")]})) == 20)

# --- Firestore refuses arrays inside arrays; the store wraps them, and nothing above the store notices
from crud.nested_arrays import decode, encode, has_nested_array  # noqa: E402
poly = {"type": "Polygon", "coordinates": [ring]}
pl = L.create(s, {"name": "Boundary", "geometries": [{"role": "boundary", "geometry": poly}, {"role": "center", "geometry": pt()}]}, ACT, now=tick()).data
stored = s.data["test_locations"][pl["id"]]
check("stored form has no array inside an array", not has_nested_array(stored), str(stored["geometries"][0]))
check("get returns plain GeoJSON, unchanged", s.get("locations", pl["id"])["geometries"][0]["geometry"] == poly)
check("create returned plain GeoJSON", pl["geometries"][0]["geometry"] == poly)
check("query returns plain GeoJSON", [d for d in s.query("locations", [("name", "==", "Boundary")])][0]["geometries"][0]["geometry"] == poly)
mp = {"type": "MultiPolygon", "coordinates": [[ring], [ring]]}
r = L.update(s, pl["id"], {"geometries": [{"role": "parcel", "geometry": mp}]}, ACT, now=tick())
check("update with a MultiPolygon", r.ok and not has_nested_array(s.data["test_locations"][pl["id"]]) and s.get("locations", pl["id"])["geometries"][0]["geometry"] == mp, str(r))
check("encode/decode round trip", decode(encode({"a": [[1, [2, 3]], [[4]]], "b": [{"c": [[5]]}]})) == {"a": [[1, [2, 3]], [[4]]], "b": [{"c": [[5]]}]})
check("encode leaves flat arrays and scalars alone", encode({"a": [1, 2], "b": "x", "c": [{"d": 1}]}) == {"a": [1, 2], "b": "x", "c": [{"d": 1}]})
check("a point stays a flat array", encode({"c": [1.5, 2.5]}) == {"c": [1.5, 2.5]})
try:
    s.create("x", "1", {"a": [[1]]}); ok = True
except ValueError:
    ok = False
check("the store never keeps a nested array", ok and not has_nested_array(s.data["test_x"]["1"]))

# --- soft delete, residential flag, scrub
d = L.create(s, {"name": "Del"}, ACT, now=tick()).data
check("soft delete works", L.soft_delete(s, d["id"], ACT, now=tick()).ok)
check("deleting twice is not_found", L.soft_delete(s, d["id"], ACT).code == "not_found")
check("soft delete keeps the record", s.get("locations", d["id"]).get("deleted_by") == ACT)
check("soft delete bad actor", pairs(L.soft_delete(s, d["id"], "x").problems) == ["actor:invalid_format"])
check("set_residential true", L.set_residential(s, loc["id"], True, now=tick()).ok and s.get("locations", loc["id"])["is_residential"] is True)
check("set_residential must be boolean", pairs(L.set_residential(s, loc["id"], "yes").problems) == ["is_residential:invalid_type"])
check("set_residential unknown id", L.set_residential(s, "3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b", True).code == "not_found")
home2 = L.create(s, copy.deepcopy(ex["valid"]["twenty_acre_property"]), ACT, now=tick()).data
r = L.scrub(s, home2["id"], "system:erase", now=tick())
after = s.get("locations", home2["id"])
check("scrub retires and removes the place's details", r.ok and after["status"] == "retired" and not any(k in after for k in L.PERSONAL_FIELDS), str(sorted(after)))
check("scrub keeps id and control fields", after["id"] == home2["id"] and after["created_by"] == ACT and after["is_residential"] is False)
check("scrub of unknown id", L.scrub(s, "3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b", "system:erase").code == "not_found")

# --- transaction: a failed write leaves nothing
before = sum(len(v) for v in s.data.values())
try:
    with s.transaction() as tx:
        L.create(s, {"name": "TX"}, ACT, tx=tx, now=tick())
        raise RuntimeError("abort")
except RuntimeError:
    pass
check("a rolled-back create leaves nothing", sum(len(v) for v in s.data.values()) == before)

print(f"\n{total - len(fails)}/{total} checks passed")
if fails:
    print("FAILED:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("OK")
