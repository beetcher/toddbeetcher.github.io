"""CRUD handler for the `locations` collection (docs/schema-first-build-method.md, section 6; shape copied from venues_crud.py).

A location is a place on Earth and nothing more. It knows nothing about who lives, owns or operates there:
that is the location_link collection. This file never reads links; the service (locations_service.py) does.

Rules of this file: plain functions, never an endpoint; validates with the kit; returns a Result;
problems name fields and never values.
"""
from __future__ import annotations

import builtins
import re
from typing import Optional
from zoneinfo import ZoneInfo

from .schema_kit import (
    UUID_PATTERN, check_actor, check_document, check_field, clean, drop_empty, failure,
    load_collection, stamp_create, stamp_update, success, utc_stamp,
)
from .store_errors import DocExists, DocMissing, StaleUpdate
from launch_discovery import zip_zones   # P-94: a place with a ZIP and no time zone gets its zone from the ZIP

LOCATIONS = load_collection("location")

SOURCES = ("dashboard", "import")
DEFAULT_LIMIT = 100
MAX_LIMIT = 200
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
MAX_PARENT_DEPTH = 30
MAX_KEYS = 40
# fields that describe a place and are personal data when the place is a home; removed when a residential location is scrubbed
PERSONAL_FIELDS = ("name", "aliases", "description", "addresses", "geometries", "identifiers", "characteristics", "address_keys")


# =============================================================================
# RULES BLOCK: everything specific to locations that the schema cannot say
# =============================================================================

def _is_num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _position_ok(p) -> bool:
    if not isinstance(p, builtins.list) or len(p) not in (2, 3) or not all(_is_num(v) for v in p):
        return False
    return -180 <= p[0] <= 180 and -90 <= p[1] <= 90


def _positions_ok(ps, minimum) -> bool:
    return isinstance(ps, builtins.list) and len(ps) >= minimum and all(_position_ok(p) for p in ps)


def _ring_ok(r) -> bool:
    return _positions_ok(r, 4) and r[0][:2] == r[-1][:2]


def _polygon_ok(poly) -> bool:
    return isinstance(poly, builtins.list) and len(poly) >= 1 and all(_ring_ok(r) for r in poly)


def geojson_ok(geometry) -> bool:
    """GeoJSON (RFC 7946) shape and range for the six types we accept."""
    if not isinstance(geometry, dict):
        return False
    t, c = geometry.get("type"), geometry.get("coordinates")
    if t == "Point":
        return _position_ok(c)
    if t == "MultiPoint":
        return _positions_ok(c, 1)
    if t == "LineString":
        return _positions_ok(c, 2)
    if t == "MultiLineString":
        return isinstance(c, builtins.list) and len(c) >= 1 and all(_positions_ok(x, 2) for x in c)
    if t == "Polygon":
        return _polygon_ok(c)
    if t == "MultiPolygon":
        return isinstance(c, builtins.list) and len(c) >= 1 and all(_polygon_ok(x) for x in c)
    return False


def _geometries_valid(doc: dict) -> list:
    for g in doc.get("geometries", []):
        if isinstance(g, dict) and not geojson_ok(g.get("geometry")):
            return [{"field": "geometries", "issue": "invalid_value"}]
    return []


def _addresses_one_primary(doc: dict) -> list:
    n = sum(1 for a in doc.get("addresses", []) if isinstance(a, dict) and a.get("is_primary") is True)
    return [] if n <= 1 else [{"field": "addresses", "issue": "duplicate"}]


def _civic_needs_country(doc: dict) -> list:
    for a in doc.get("addresses", []):
        if isinstance(a, dict) and a.get("usage") == "civic" and "country" not in a:
            return [{"field": "addresses", "issue": "required"}]
    return []


def _period_key(s: str) -> tuple:
    p = s.split("-")
    return (int(p[0]), int(p[1]) if len(p) > 1 else 1, int(p[2]) if len(p) > 2 else 1)


def _address_dates_in_order(doc: dict) -> list:
    for a in doc.get("addresses", []):
        if isinstance(a, dict) and "valid_from" in a and "valid_to" in a and _period_key(a["valid_from"]) > _period_key(a["valid_to"]):
            return [{"field": "addresses", "issue": "out_of_range"}]
    return []


def _time_zone_real(doc: dict) -> list:
    tz = doc.get("time_zone")
    if tz is None:
        return []
    try:
        if not re.match(r"^[A-Za-z0-9_+\-/]+$", tz) or ".." in tz:
            raise ValueError
        ZoneInfo(tz)
    except Exception:
        return [{"field": "time_zone", "issue": "invalid_value"}]
    return []


CROSS_FIELD_RULES = (
    ("geometries_valid", ("geometries",), _geometries_valid),
    ("one_primary_address", ("addresses",), _addresses_one_primary),
    ("civic_needs_country", ("addresses",), _civic_needs_country),
    ("address_dates_in_order", ("addresses",), _address_dates_in_order),
    ("time_zone_real", ("time_zone",), _time_zone_real),
)
RULE_FIELDS = frozenset(f for _, fields, _ in CROSS_FIELD_RULES for f in fields)

_ABBREV = {"street": "st", "avenue": "ave", "road": "rd", "drive": "dr", "lane": "ln", "court": "ct", "boulevard": "blvd",
           "place": "pl", "circle": "cir", "highway": "hwy", "parkway": "pkwy", "north": "n", "south": "s", "east": "e",
           "west": "w", "northeast": "ne", "northwest": "nw", "southeast": "se", "southwest": "sw", "county": "co",
           "apartment": "apt", "suite": "ste", "unit": "unit", "floor": "fl"}


def _norm(text) -> str:
    words = re.sub(r"[^a-z0-9 ]", " ", str(text).lower()).split()
    return " ".join(_ABBREV.get(w, w) for w in words)


def address_key(a: dict) -> Optional[str]:
    """One normalized string for an address, or None when the address is former or too thin to compare."""
    if a.get("usage") == "former":
        return None
    country = a.get("country", "")
    postal = str(a.get("postal_code", ""))[:5].lower()
    if a.get("po_box"):
        return f"pobox|{country}|{postal}|{_norm(a['po_box'])}"
    if a.get("street"):
        # the postal code pins the town; without one, the town name is all there is
        town = "" if postal else _norm(a.get("locality", ""))
        return "|".join(("street", country, postal, _norm(a.get("street_number", "")), _norm(a["street"]),
                         _norm(a.get("unit", "")), town))
    if a.get("lines"):
        return "lines|" + country + "|" + _norm(" ".join(a["lines"]))
    return None


def address_keys_for(doc: dict) -> list:
    keys: list = []
    for a in doc.get("addresses", []):
        if isinstance(a, dict):
            k = address_key(a)
            if k and k not in keys:
                keys.append(k)
    return keys[:MAX_KEYS]


def _prune(value):
    if isinstance(value, dict):
        return {k: _prune(v) for k, v in value.items() if v is not None}
    if isinstance(value, builtins.list):
        return [_prune(v) for v in value if v is not None]
    return value


def _normalize_value(name: str, value):
    value = clean(value)
    if isinstance(value, str) and name == "time_zone":
        value = value.replace(" ", "")
    return _prune(value)


def _run_rules(doc: dict) -> list:
    problems: list = []
    for _, _, fn in CROSS_FIELD_RULES:
        problems += fn(doc)
    return problems


def _dedupe(problems: list) -> list:
    seen, out = set(), []
    for p in problems:
        k = (p["field"], p["issue"])
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out


def _bad(problems: list):
    return failure("validation_failed", _dedupe(problems))


def _id_problem(id) -> list:
    return [] if isinstance(id, str) and UUID_PATTERN.match(id) else [{"field": "id", "issue": "invalid_format"}]


def _is_deleted(doc: dict) -> bool:
    return "deleted_at" in doc


def _parent_problems(store, id, doc: dict) -> list:
    """part_of_location_id must exist (not deleted), not be the record itself, and make no loop."""
    pid = doc.get("part_of_location_id")
    if pid is None:
        return []
    if pid == id:
        return [{"field": "part_of_location_id", "issue": "invalid_value"}]
    seen, cur = {id} if id else set(), pid
    for depth in range(MAX_PARENT_DEPTH):
        if cur in seen:
            return [{"field": "part_of_location_id", "issue": "invalid_value"}]
        seen.add(cur)
        p = store.get(LOCATIONS.name, cur)
        if p is None or _is_deleted(p):
            return [{"field": "part_of_location_id", "issue": "not_found"}] if depth == 0 else []
        cur = p.get("part_of_location_id")
        if cur is None:
            return []
    return [{"field": "part_of_location_id", "issue": "out_of_range"}]


# =============================================================================
# create
# =============================================================================

def create(store, data, actor, source="dashboard", tx=None, now=None):
    problems = check_actor(actor)
    if source not in SOURCES:
        problems.append({"field": "source", "issue": "invalid_value"})
    if problems:
        return _bad(problems)
    if not isinstance(data, dict):
        return _bad([{"field": "body", "issue": "invalid_type"}])
    read_only = [{"field": k, "issue": "not_allowed"} for k in data if k in LOCATIONS.read_only]
    if read_only:
        return _bad(read_only)

    doc = drop_empty({k: _normalize_value(k, v) for k, v in data.items()})
    if not doc.get("time_zone"):   # P-94: the system assigns the zone from the ZIP; a person only edits it when it is wrong
        auto = zip_zones.zone_of_addresses(doc.get("addresses"))
        if auto:
            doc["time_zone"] = auto
    problems = check_document(LOCATIONS, doc)
    if not problems:
        problems = _run_rules(doc)
    if not problems:
        problems = _parent_problems(store, None, doc)
    if problems:
        return _bad(problems)

    doc.setdefault("status", "active")
    doc.setdefault("kind", "site")
    doc = stamp_create(LOCATIONS, doc, actor, source, now)
    doc["is_residential"] = False
    keys = address_keys_for(doc)
    if keys:
        doc["address_keys"] = keys
    missing = [{"field": f, "issue": "required"} for f in LOCATIONS.server_required if f not in doc]
    if check_document(LOCATIONS, doc) + missing:
        return failure("server_error")
    try:
        store.create(LOCATIONS.name, doc["id"], doc, tx=tx)
    except DocExists:
        return failure("server_error")
    return success(doc)


# =============================================================================
# get / list / find
# =============================================================================

def get(store, id, include_deleted=False):
    problems = _id_problem(id)
    if problems:
        return _bad(problems)
    doc = store.get(LOCATIONS.name, id)
    if doc is None or (_is_deleted(doc) and not include_deleted):
        return failure("not_found")
    return success(doc)


_LIST_FILTERS = ("status", "kind", "is_residential")


def list(store, filters=None, order="-created_at", limit=DEFAULT_LIMIT):  # noqa: A001
    """No filter or ONE of status / kind / is_residential, newest first. Anything else is `not_supported`
    (each combination needs an index). Soft-deleted records are left out after the query."""
    filters = dict(filters or {})
    problems = []
    for k, v in filters.items():
        if k not in _LIST_FILTERS:
            problems.append({"field": k, "issue": "not_supported"})
        else:
            problems += check_field(LOCATIONS, k, v, allow_read_only=True)
    if len(filters) > 1:
        problems += [{"field": k, "issue": "not_supported"} for k in filters]
    if order != "-created_at":
        problems.append({"field": "order", "issue": "not_supported"})
    if isinstance(limit, bool) or not isinstance(limit, int):
        problems.append({"field": "limit", "issue": "invalid_type"})
    if problems:
        return _bad(problems)
    limit = max(1, min(limit, MAX_LIMIT))
    docs = store.query(LOCATIONS.name, [(k, "==", v) for k, v in filters.items()],
                       order_by="created_at", descending=True, limit=limit)
    docs = [d for d in docs if not _is_deleted(d)]
    return success({"records": docs, "count": len(docs)})


def find_by_address(store, address, limit=10):
    """Live locations that already hold this address (an `address` object as in the schema). Never merges."""
    if not isinstance(address, dict):
        return _bad([{"field": "address", "issue": "invalid_type"}])
    key = address_key(drop_empty(_prune(clean(address))))
    if key is None:
        return success({"records": [], "count": 0})
    docs = [d for d in store.query(LOCATIONS.name, [("address_keys", "array_contains", key)], limit=max(1, min(limit, MAX_LIMIT)))
            if not _is_deleted(d)]
    return success({"records": docs, "count": len(docs)})


def matches_for(store, doc: dict, exclude_id: Optional[str] = None) -> builtins.list:
    """Ids of other live locations that share any normalized address with `doc` (for the service to report)."""
    out: list = []
    for key in address_keys_for(doc):
        for d in store.query(LOCATIONS.name, [("address_keys", "array_contains", key)], limit=10):
            if not _is_deleted(d) and d["id"] != exclude_id and d["id"] not in out:
                out.append(d["id"])
    return out


# =============================================================================
# update
# =============================================================================

def update(store, id, changes, actor, expected_updated_at=None, tx=None, now=None, check=None, check_fields=()):
    """Change some fields. A value of None (or "") removes an optional field.

    Simple path (no read) when no changed field takes part in a cross-field rule; whole-record path (one read) otherwise.
    `addresses`, `geometries`, `time_zone` and `part_of_location_id` always use the whole-record path.
    check: optional function(merged record) -> problems from a service (it runs on the whole-record path;
    pass check_fields to force it). expected_updated_at: refused with `conflict` when the record changed since.
    """
    problems = check_actor(actor) + _id_problem(id)
    if expected_updated_at is not None and not (isinstance(expected_updated_at, str) and STAMP.match(expected_updated_at)):
        problems.append({"field": "expected_updated_at", "issue": "invalid_format"})
    if not isinstance(changes, dict) or not changes:
        problems.append({"field": "changes", "issue": "required"})
    if problems:
        return _bad(problems)

    if isinstance(changes.get("addresses"), builtins.list) and "time_zone" not in changes:   # P-94: a place with no zone that gets an address gets its zone from the ZIP
        cur0 = store.get(LOCATIONS.name, id)
        if isinstance(cur0, dict) and not cur0.get("time_zone") and not cur0.get("deleted_at"):
            auto = zip_zones.zone_of_addresses(changes["addresses"])
            if auto:
                changes = {**changes, "time_zone": auto}

    set_fields: dict = {}
    removals: list = []
    for name, raw in changes.items():
        if name not in LOCATIONS.properties or name in LOCATIONS.read_only:
            problems.append({"field": name, "issue": "not_allowed"})
        else:
            value = _normalize_value(name, raw)
            if value is None:
                removals.append(name)
            else:
                problems += check_field(LOCATIONS, name, value)
                set_fields[name] = value
    if problems:
        return _bad(problems)
    if "addresses" in set_fields:
        keys = address_keys_for(set_fields)
        (set_fields.__setitem__("address_keys", keys) if keys else removals.append("address_keys"))
    elif "addresses" in removals:
        removals.append("address_keys")

    always_whole = RULE_FIELDS | {"part_of_location_id", "status"}
    extra = frozenset(check_fields) if check is not None else frozenset()
    touched = set(set_fields) | set(removals)
    needs_whole = bool(touched & always_whole) or any(f in LOCATIONS.set_involved or f in LOCATIONS.remove_involved for f in touched) \
        or bool(touched & extra)
    stamp = stamp_update(actor, now)
    expected = expected_updated_at

    if needs_whole:
        cur = store.get(LOCATIONS.name, id)
        if cur is None or _is_deleted(cur):
            return failure("not_found")
        if expected is not None and cur.get("updated_at") != expected:
            return failure("conflict")
        merged = {**cur, **set_fields}
        for f in removals:
            merged.pop(f, None)
        problems = check_document(LOCATIONS, merged)
        if not problems:
            problems = _run_rules(merged)
        if not problems and ("part_of_location_id" in touched):
            problems = _parent_problems(store, id, merged)
        if not problems and check is not None:
            problems = check(merged)
        if problems:
            return _bad(problems)
        expected = cur["updated_at"]

    try:
        store.update(LOCATIONS.name, id, {**set_fields, **stamp}, removals, expected_updated_at=expected, tx=tx)
    except DocMissing:
        return failure("not_found")
    except StaleUpdate:
        return failure("conflict")
    return success({"id": id, "changed": sorted(set_fields), "removed": sorted(removals),
                    "updated_at": stamp["updated_at"], "updated_by": actor})


# =============================================================================
# soft delete
# =============================================================================

def soft_delete(store, id, actor, tx=None, now=None):
    """Mark deleted; the record stays. The service must first make sure no live link points here. Deleting twice is `not_found`."""
    problems = check_actor(actor) + _id_problem(id)
    if problems:
        return _bad(problems)
    cur = store.get(LOCATIONS.name, id)
    if cur is None or _is_deleted(cur):
        return failure("not_found")
    stamp = utc_stamp(now)
    fields = {"deleted_at": stamp, "deleted_by": actor, "updated_at": stamp, "updated_by": actor}
    try:
        store.update(LOCATIONS.name, id, fields, (), expected_updated_at=cur["updated_at"], tx=tx)
    except DocMissing:
        return failure("not_found")
    except StaleUpdate:
        return failure("conflict")
    return success({"id": id, "deleted_at": stamp})


# =============================================================================
# server-kept fields (written only by the link service)
# =============================================================================

def set_residential(store, id, value, actor="system:location_links", tx=None, now=None):
    problems = check_actor(actor) + _id_problem(id) + check_field(LOCATIONS, "is_residential", value, allow_read_only=True)
    if problems:
        return _bad(problems)
    try:
        store.update(LOCATIONS.name, id, {"is_residential": value, **stamp_update(actor, now)}, (), tx=tx)
    except DocMissing:
        return failure("not_found")
    return success({"id": id, "is_residential": value})


def scrub(store, id, actor, tx=None, now=None):
    """Retire a location and remove everything that describes the place (used when the last resident is erased).
    Keeps the id, control fields and tombstone facts so links in history still resolve."""
    problems = check_actor(actor) + _id_problem(id)
    if problems:
        return _bad(problems)
    cur = store.get(LOCATIONS.name, id)
    if cur is None:
        return failure("not_found")
    removals = [f for f in (*PERSONAL_FIELDS, "part_of_location_id", "time_zone", "kind") if f in cur]
    try:
        store.update(LOCATIONS.name, id, {"status": "retired", "is_residential": False, **stamp_update(actor, now)}, removals, tx=tx)
    except DocMissing:
        return failure("not_found")
    return success({"id": id, "removed": sorted(removals)})
