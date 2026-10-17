"""The shared ZIP table: which state a ZIP code is in (and where it is), for all 50 states plus DC.

The table is DATA built once from the GeoNames US postal code file by `build_zip_table.py` (run on a computer with internet) and
saved as `data/us_zips.json`: {"80301": ["CO", 40.0, -105.2, "Boulder"], ...}. Nothing here reads the network. Tests and the server set
the table with `set_table`; with no table loaded every lookup says "unknown" and callers refuse rather than guess.
"""
from __future__ import annotations

import json
import pathlib

_TABLE: dict | None = None
DEFAULT_PATH = pathlib.Path(__file__).resolve().parent / "data" / "us_zips.json"


def set_table(table: dict | None) -> None:
    global _TABLE
    _TABLE = table


def table() -> dict | None:
    global _TABLE
    if _TABLE is None and DEFAULT_PATH.exists():
        _TABLE = json.loads(DEFAULT_PATH.read_text())
    return _TABLE


def is_loaded() -> bool:
    return bool(table())


def state_of(zip_code: str):
    t = table()
    row = t.get(zip_code) if t else None
    return row[0] if row else None


def zips_in_state(state_code: str) -> list:
    t = table() or {}
    return sorted(z for z, row in t.items() if row[0] == state_code)


def states_loaded() -> list:
    t = table() or {}
    return sorted({row[0] for row in t.values()})
