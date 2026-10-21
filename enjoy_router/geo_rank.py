"""Distance helpers shared by the public venue list and the operator venue list (no store, no records).

A ZIP is any five digits. The centre of a ZIP comes from the US table the Discovery module uses (launch_discovery/zip_table.py, every state),
when it is loaded; otherwise from the Colorado table in co_zips.json, which stays as the fallback (and is what the cloud tests rely on).
"""
from __future__ import annotations

import json
import math
import pathlib
import re

ZIP_RE = re.compile(r"^[0-9]{5}$")
_zips = None


def zip_table() -> dict:
    """Colorado ZIP -> [lat, lon], read once from co_zips.json."""
    global _zips
    if _zips is None:
        _zips = json.loads((pathlib.Path(__file__).resolve().parent / "co_zips.json").read_text())
    return _zips


def centre_of_zip(z):
    """[lat, lon] of a five-digit ZIP's centre: the US table first (any state), else the Colorado table, else None."""
    from launch_discovery import zip_table as us
    row = (us.table() or {}).get(z)
    if row and len(row) >= 3:
        return [row[1], row[2]]
    return zip_table().get(z)


def zip_origin(zip_code):
    """[lat, lon] for a known ZIP (any state), else None."""
    return centre_of_zip(str(zip_code)) if zip_code and ZIP_RE.match(str(zip_code)) else None


def miles_between(a, b) -> float:
    """Straight-line miles between two [lat, lon] points."""
    (la1, lo1), (la2, lo2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    d = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(d))


def gps_of(loc: dict):
    """[lat, lon] of the place's best GPS point (centre, then entrance, then any point), or None."""
    for role in ("center", "entrance"):
        for g in loc.get("geometries", []):
            geo = g.get("geometry") or {}
            if g.get("role") == role and geo.get("type") == "Point" and len(geo.get("coordinates", [])) >= 2:
                return [geo["coordinates"][1], geo["coordinates"][0]]
    for g in loc.get("geometries", []):
        geo = g.get("geometry") or {}
        if geo.get("type") == "Point" and len(geo.get("coordinates", [])) >= 2:
            return [geo["coordinates"][1], geo["coordinates"][0]]
    return None


def position_of_place(loc: dict):
    """Where a place is: its GPS, else the centre of its (current) address ZIP, else None."""
    gps = gps_of(loc)
    if gps:
        return gps
    for a in loc.get("addresses", []):
        z = str(a.get("postal_code") or "")[:5]
        if a.get("usage") != "former":
            c = centre_of_zip(z)
            if c:
                return c
    return None
