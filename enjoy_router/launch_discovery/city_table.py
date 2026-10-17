"""The largest cities of each state, with the ZIP codes that carry their name, for the Console map's city list.

DATA, built once by `build_zip_table.py` from the GeoNames city file (cities with 15,000 people or more) and the ZIP table, saved as
`data/us_cities.json`: {"MN": [{"name": "Minneapolis", "population": 429954, "lat": 44.98, "lon": -93.26, "zips": ["55401", ...]}, ...]}.
At most TOP_PER_STATE cities per state, biggest first. A ZIP belongs to a city when its postal place name is the city's name (spelled
the same way after the small clean-up in `normalize`). That is the post office's name for the ZIP, NOT the city limits: a suburb with
its own postal name is its own entry (or none), and a ZIP that straddles two towns goes to its postal name. A city with no matching
ZIP is left out, so every entry in the list can be selected. Nothing here reads the network; with no file every lookup is empty.
"""
from __future__ import annotations

import json
import pathlib
import re
import unicodedata

TOP_PER_STATE = 10
DEFAULT_PATH = pathlib.Path(__file__).resolve().parent / "data" / "us_cities.json"
_TABLE: dict | None = None

_ABBREV = ((r"\bst\b", "saint"), (r"\bste\b", "sainte"), (r"\bft\b", "fort"), (r"\bmt\b", "mount"), (r"\bpt\b", "port"))


def normalize(name: str) -> str:
    """A spelling both sources agree on: no accents, lower case, no punctuation, 'St.' = 'Saint', 'Ft' = 'Fort', 'Mt' = 'Mount', and a
    trailing ' city' dropped ('New York City' = 'New York'; 'Oklahoma City' keeps its word, see the guard below)."""
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s.replace("'", ""))
    s = re.sub(r"\s+", " ", s).strip()
    for pat, rep in _ABBREV:
        s = re.sub(pat, rep, s)
    if s.endswith(" city") and s.count(" ") >= 2:        # 'new york city' -> 'new york'; 'oklahoma city', 'kansas city' have only one space and keep 'city'
        s = s[:-5]
    return s


def build(cities_text: str, zip_table: dict, per_state: int = TOP_PER_STATE) -> dict:
    """cities_text is the GeoNames 'cities15000.txt': tab separated, columns id, name, asciiname, alternatenames, latitude, longitude,
    feature class, feature code, country, cc2, admin1 (the state letters for the US), admin2, admin3, admin4, population, ..."""
    by_place: dict = {}
    for z, row in (zip_table or {}).items():
        by_place.setdefault((row[0], normalize(row[3])), []).append(z)
    found: dict = {}
    for line in cities_text.splitlines():
        c = line.split("\t")
        if len(c) < 15 or c[8] != "US" or c[6] != "P":
            continue
        state = c[10]
        try:
            pop, lat, lon = int(c[14]), round(float(c[4]), 4), round(float(c[5]), 4)
        except ValueError:
            continue
        zips = by_place.get((state, normalize(c[1]))) or by_place.get((state, normalize(c[2])))
        if not zips:
            continue
        found.setdefault(state, {})
        key = normalize(c[1])
        if key not in found[state] or pop > found[state][key]["population"]:
            found[state][key] = {"name": c[1][:60], "population": pop, "lat": lat, "lon": lon, "zips": sorted(zips)}
    return {st: sorted(v.values(), key=lambda e: (-e["population"], e["name"]))[:per_state] for st, v in sorted(found.items())}


def set_table(table: dict | None) -> None:
    global _TABLE
    _TABLE = table


def table() -> dict:
    global _TABLE
    if _TABLE is None:
        _TABLE = json.loads(DEFAULT_PATH.read_text()) if DEFAULT_PATH.exists() else {}
    return _TABLE


def is_loaded() -> bool:
    return bool(table())


def cities_in_state(state_code: str) -> list:
    return list(table().get(state_code, []))
