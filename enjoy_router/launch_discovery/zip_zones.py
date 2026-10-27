"""The time zone of a US ZIP (P-94, Todd 2026-10-27: the system assigns it, nobody looks it up).

DATA built once by `build_zip_zones.py` into `data/us_zip_zones.json`: {"zones": [eight IANA names], "ranges": [[first ZIP as a number, zone index], ...]}.
A ZIP gets the zone of the last range that starts at or before it, but only when the ZIP is in the shared ZIP table (`zip_table`), so a made-up ZIP
answers None. Nothing reads the network. The eight zones: New_York, Chicago, Denver, Phoenix, Los_Angeles, Anchorage, Adak, Honolulu.
"""
from __future__ import annotations

import bisect
import json
import pathlib
import re

from . import zip_table

DEFAULT_PATH = pathlib.Path(__file__).resolve().parent / "data" / "us_zip_zones.json"
ZIP5 = re.compile(r"^[0-9]{5}")
_DATA: dict | None = None
_STARTS: list = []


def _load():
    global _DATA, _STARTS
    if _DATA is None and DEFAULT_PATH.exists():
        _DATA = json.loads(DEFAULT_PATH.read_text())
        _STARTS = [r[0] for r in _DATA["ranges"]]
    return _DATA


def zones() -> list:
    """The eight zones the Console offers, in display order."""
    d = _load()
    return list(d["zones"]) if d else []


def zone_of(zip_code) -> str | None:
    """The IANA zone for a five-digit ZIP (extra digits after the fifth are ignored), or None when the ZIP is not in the table."""
    m = ZIP5.match(str(zip_code or "").strip())
    d = _load()
    if not m or not d or not zip_table.table() or m.group(0) not in zip_table.table():
        return None
    i = bisect.bisect_right(_STARTS, int(m.group(0))) - 1
    return d["zones"][d["ranges"][i][1]] if i >= 0 else None


def zone_of_addresses(addresses) -> str | None:
    """The zone from the first address that has a ZIP the table knows."""
    for a in addresses or []:
        if isinstance(a, dict):
            z = zone_of(a.get("postal_code"))
            if z:
                return z
    return None
