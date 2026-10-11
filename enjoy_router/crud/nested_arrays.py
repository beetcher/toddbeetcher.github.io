"""Firestore refuses an array that directly holds another array ("nested arrays are not allowed"). GeoJSON coordinates
are arrays of arrays (a MultiPoint, a line, a polygon ring). The stores therefore wrap every array that sits directly
inside another array as a one-key map, {"_a": [...]}, on the way in, and unwrap it on the way out. The handlers, services,
schemas and the wire format never see the wrapper: they keep plain GeoJSON.

Safe because no schema allows a field named `_a` (field names must start with a lowercase letter).
"""
from __future__ import annotations

WRAP = "_a"


def encode(value):
    """A copy of `value` with no array directly inside an array."""
    if isinstance(value, dict):
        return {k: encode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [{WRAP: encode(v)} if isinstance(v, list) else encode(v) for v in value]
    return value


def decode(value):
    """The inverse of encode."""
    if isinstance(value, dict):
        if len(value) == 1 and isinstance(value.get(WRAP), list):
            return decode(value[WRAP])
        return {k: decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decode(v) for v in value]
    return value


def has_nested_array(value) -> bool:
    """True when some array directly holds an array (what Firestore refuses)."""
    if isinstance(value, dict):
        return any(has_nested_array(v) for v in value.values())
    if isinstance(value, list):
        return any(isinstance(v, list) or has_nested_array(v) for v in value)
    return False
