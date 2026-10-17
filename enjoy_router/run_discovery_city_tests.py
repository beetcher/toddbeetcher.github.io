#!/usr/bin/env python3
"""Tests for the city list data (launch_discovery/city_table.py and the build step in build_zip_table.py): which GeoNames rows become
entries, how ZIPs are matched to a city, ranking and the ten-per-state limit, and what happens with missing or odd data. No network.
Run from enjoy_router/:  python3 run_discovery_city_tests.py   (-v lists every check)."""
import io, json, pathlib, sys, tempfile, zipfile
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_zip_table as B  # noqa: E402
from launch_discovery import city_table as CT  # noqa: E402

fails, total = [], 0
def check(label, ok, detail=""):
    global total
    total += 1
    if not ok: fails.append(label)
    if not ok or "-v" in sys.argv: print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")

def row(name, state, pop, lat=40.0, lon=-100.0, fclass="P", country="US", ascii_=None):
    c = [""] * 19
    c[0], c[1], c[2], c[4], c[5], c[6], c[7], c[8], c[10], c[14] = "1", name, ascii_ or name, str(lat), str(lon), fclass, "PPL", country, state, str(pop)
    return "\t".join(c)
def z(zipc, state, place): return [state, 40.0, -100.0, place]

# ---------------------------------------------------------------- spelling
check("normalize: case, accents, punctuation", CT.normalize("Cañon City") == "canon city" and CT.normalize("  BOULDER ") == "boulder" and CT.normalize("Coeur d'Alene") == "coeur dalene")
check("normalize: St, St., Saint are one", CT.normalize("St. Paul") == CT.normalize("Saint Paul") == CT.normalize("St Paul") == "saint paul")
check("normalize: Ft and Mt", CT.normalize("Ft. Collins") == "fort collins" and CT.normalize("Mt. Pleasant") == "mount pleasant")
check("normalize: New York City = New York, but Kansas City keeps its word", CT.normalize("New York City") == CT.normalize("New York") and CT.normalize("Kansas City") == "kansas city")

# ---------------------------------------------------------------- build
zips = {"55401": z("", "MN", "Minneapolis"), "55402": z("", "MN", "Minneapolis"), "55101": z("", "MN", "Saint Paul"), "55901": z("", "MN", "Rochester"),
        "55033": z("", "MN", "Hastings"), "80301": z("", "CO", "Boulder"), "80302": z("", "CO", "Boulder"), "14604": z("", "NY", "Rochester"), "10001": z("", "NY", "New York")}
text = "\n".join([row("Minneapolis", "MN", 429954), row("St. Paul", "MN", 311527), row("Rochester", "MN", 121395), row("Duluth", "MN", 86697),
                 row("Boulder", "CO", 108250), row("Rochester", "NY", 211328), row("New York City", "NY", 8804190), row("Hastings", "MN", 22000, fclass="S")])
out = CT.build(text, zips)
check("each state gets its cities, biggest first", [c["name"] for c in out["MN"]] == ["Minneapolis", "St. Paul", "Rochester"], [c["name"] for c in out.get("MN", [])])
check("a city takes the ZIPs that carry its name, sorted", out["MN"][0]["zips"] == ["55401", "55402"] and out["CO"][0]["zips"] == ["80301", "80302"])
check("St. Paul matches 'Saint Paul' ZIPs", out["MN"][1]["zips"] == ["55101"])
check("the same city name in two states does not mix their ZIPs", out["NY"][1]["zips"] == ["14604"] and out["MN"][2]["zips"] == ["55901"])
check("New York City matches the ZIP place 'New York' and ranks first", out["NY"][0]["name"] == "New York City" and out["NY"][0]["zips"] == ["10001"])
check("a city with no matching ZIP (Duluth) is left out, so every entry can be selected", all(c["name"] != "Duluth" for c in out["MN"]))
check("rows that are not populated places or not in the US are ignored", all(c["name"] != "Hastings" for c in out["MN"])
      and CT.build(row("Boulder", "CO", 99, country="CA"), zips) == {})
check("population, position and name are kept", out["CO"][0]["population"] == 108250 and out["CO"][0]["lat"] == 40.0 and out["CO"][0]["lon"] == -100.0)
many = "\n".join(row(f"Town{i:02d}", "CO", 100000 - i) for i in range(25)); zmany = {f"8{i:04d}": z("", "CO", f"Town{i:02d}") for i in range(25)}
big = CT.build(many, zmany)
check("at most ten cities per state, the ten biggest", len(big["CO"]) == 10 and [c["name"] for c in big["CO"]] == [f"Town{i:02d}" for i in range(10)])
check("a state's limit can be changed by the caller", len(CT.build(many, zmany, per_state=3)["CO"]) == 3)
dup = CT.build(row("Boulder", "CO", 100) + "\n" + row("Boulder", "CO", 900), zips)
check("the same city twice keeps the bigger entry once", len(dup["CO"]) == 1 and dup["CO"][0]["population"] == 900)
check("odd data does not crash the build", CT.build("junk\n\t\t\n" + row("Boulder", "CO", "many"), zips) == {} and CT.build("", zips) == {} and CT.build(text, {}) == {} and CT.build(text, None) == {})
check("the build is the same every time", json.dumps(CT.build(text, zips), sort_keys=True) == json.dumps(CT.build(text, zips), sort_keys=True))

# ---------------------------------------------------------------- the table reader
CT.set_table({"CO": out["CO"]})
check("cities_in_state gives the list; a state with none gives an empty list", CT.cities_in_state("CO")[0]["name"] == "Boulder" and CT.cities_in_state("TX") == [] and CT.is_loaded())
check("the caller cannot change the stored list by editing the answer", (lambda a: (a.append(1), len(CT.cities_in_state("CO")))[1])(CT.cities_in_state("CO")) == 1)
CT.set_table({}); check("with no data nothing is loaded and nothing breaks", not CT.is_loaded() and CT.cities_in_state("CO") == [])

# ---------------------------------------------------------------- the builder script, end to end with local files
with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    us = "\n".join("\t".join(["US", zc, r[3], "", r[0], "", "", "", "", str(r[1]), str(r[2]), "1"]) for zc, r in zips.items())
    for name, data, fname in (("US.zip", us, "US.txt"), ("cities15000.zip", text, "cities15000.txt")):
        with zipfile.ZipFile(d / name, "w") as zf: zf.writestr(fname, data)
    B.OUT, B.CITY_OUT = d / "zips.json", d / "cities.json"
    buf = io.StringIO(); old = sys.stdout; sys.stdout = buf
    try: B.main(["x", str(d / "US.zip"), str(d / "cities15000.zip")])
    finally: sys.stdout = old
    check("the builder writes the ZIP table and the city list from local copies", (d / "zips.json").exists() and json.loads((d / "cities.json").read_text())["MN"][0]["name"] == "Minneapolis" and "cities in" in buf.getvalue(), buf.getvalue())
    buf = io.StringIO(); sys.stdout = buf; (d / "cities.json").unlink()
    try: B.main(["x", str(d / "US.zip"), str(d / "missing.zip")])
    finally: sys.stdout = old
    check("a missing city file skips the list but still saves the ZIP table, and says so", (d / "zips.json").exists() and not (d / "cities.json").exists() and "SKIPPED" in buf.getvalue(), buf.getvalue())

print(f"{total - len(fails)}/{total} checks passed" + (f"; FAILED: {fails}" if fails else ""))
sys.exit(1 if fails else 0)
