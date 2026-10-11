"""CRUD handler for the `location_links` collection: one relationship between a subject (individual, venue,
organization) and a location, with dates. Shape copied from venues_crud.py.

This file checks one link at a time: its own fields, date order, immutable fields, and keeping `status` in step with
`valid_to`. Whether the subject and the location exist, overlaps with other links, the single primary and the
location's residential flag are the service's job (location_links_service.py).
"""
from __future__ import annotations

import builtins
import re

from .schema_kit import (
    UUID_PATTERN, check_actor, check_document, check_field, clean, drop_empty, failure,
    load_collection, stamp_create, stamp_update, success, utc_stamp,
)
from .store_errors import DocExists, DocMissing, StaleUpdate

LINKS = load_collection("location_link")

SOURCES = ("dashboard", "import")
DEFAULT_LIMIT = 100
MAX_LIMIT = 200
SCAN_LIMIT = 500
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
IMMUTABLE = ("subject_type", "subject_id", "location_id", "relationship")
# cleared when an erased person's link is scrubbed
SCRUB_FIELDS = ("description", "notes", "verification", "valid_from", "valid_to", "is_primary")


# =============================================================================
# RULES BLOCK
# =============================================================================

def period_start(s):
    if s is None:
        return (0, 1, 1)
    p = s.split("-")
    return (int(p[0]), int(p[1]) if len(p) > 1 else 1, int(p[2]) if len(p) > 2 else 1)


def period_end(s):
    if s is None:
        return (9999, 12, 31)
    p = s.split("-")
    return (int(p[0]), int(p[1]) if len(p) > 1 else 12, int(p[2]) if len(p) > 2 else 31)


def overlaps(a: dict, b: dict) -> bool:
    """True when the two links' periods share a day. A year or month counts as the whole of it."""
    return period_start(a.get("valid_from")) <= period_end(b.get("valid_to")) and period_start(b.get("valid_from")) <= period_end(a.get("valid_to"))


def _dates_in_order(doc: dict) -> list:
    if "valid_from" in doc and "valid_to" in doc and period_start(doc["valid_from"]) > period_start(doc["valid_to"]):
        return [{"field": "valid_to", "issue": "out_of_range"}]
    return []


CROSS_FIELD_RULES = (("dates_in_order", ("valid_from", "valid_to"), _dates_in_order),)
RULE_FIELDS = frozenset(f for _, fields, _ in CROSS_FIELD_RULES for f in fields)


def _status_for(doc: dict) -> str:
    return "ended" if "valid_to" in doc else "active"


def _prune(v):
    if isinstance(v, dict):
        return {k: _prune(x) for k, x in v.items() if x is not None}
    if isinstance(v, builtins.list):
        return [_prune(x) for x in v if x is not None]
    return v


def _normalize_value(name, value):
    return _prune(clean(value))


def _run_rules(doc):
    out: list = []
    for _, _, fn in CROSS_FIELD_RULES:
        out += fn(doc)
    return out


def _dedupe(problems):
    seen, out = set(), []
    for p in problems:
        k = (p["field"], p["issue"])
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out


def _bad(problems):
    return failure("validation_failed", _dedupe(problems))


def _id_problem(id):
    return [] if isinstance(id, str) and UUID_PATTERN.match(id) else [{"field": "id", "issue": "invalid_format"}]


def _is_deleted(doc):
    return "deleted_at" in doc


def is_live(doc) -> bool:
    return doc is not None and not _is_deleted(doc) and doc.get("status") == "active"


# =============================================================================
# create
# =============================================================================

def validate(data):
    """Check a link a sender supplies, with no store: (cleaned document, problems). Used by create and by the service."""
    if not isinstance(data, dict):
        return None, [{"field": "body", "issue": "invalid_type"}]
    ro = [{"field": k, "issue": "not_allowed"} for k in data if k in LINKS.read_only]
    if ro:
        return None, ro
    doc = drop_empty({k: _normalize_value(k, v) for k, v in data.items()})
    return doc, check_document(LINKS, doc) or _run_rules(doc)


def create(store, data, actor, source="dashboard", tx=None, now=None):
    problems = check_actor(actor)
    if source not in SOURCES:
        problems.append({"field": "source", "issue": "invalid_value"})
    if problems:
        return _bad(problems)
    doc, problems = validate(data)
    if problems:
        return _bad(problems)
    doc = stamp_create(LINKS, doc, actor, source, now)
    doc["status"] = _status_for(doc)
    missing = [{"field": f, "issue": "required"} for f in LINKS.server_required if f not in doc]
    if check_document(LINKS, doc) + missing:
        return failure("server_error")
    try:
        store.create(LINKS.name, doc["id"], doc, tx=tx)
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
    doc = store.get(LINKS.name, id)
    if doc is None or (_is_deleted(doc) and not include_deleted):
        return failure("not_found")
    return success(doc)


_LIST_FILTERS = ("subject_id", "location_id", "subject_type", "relationship", "status")


def list(store, filters=None, order="-created_at", limit=DEFAULT_LIMIT):  # noqa: A001
    """No filter or ONE of subject_id / location_id / subject_type / relationship / status, newest first.
    Anything else is `not_supported` (each combination needs an index). Soft-deleted links are left out after the query."""
    filters = dict(filters or {})
    problems = []
    for k, v in filters.items():
        if k not in _LIST_FILTERS:
            problems.append({"field": k, "issue": "not_supported"})
        else:
            problems += check_field(LINKS, k, v, allow_read_only=True)
    if len(filters) > 1:
        problems += [{"field": k, "issue": "not_supported"} for k in filters]
    if order != "-created_at":
        problems.append({"field": "order", "issue": "not_supported"})
    if isinstance(limit, bool) or not isinstance(limit, int):
        problems.append({"field": "limit", "issue": "invalid_type"})
    if problems:
        return _bad(problems)
    limit = max(1, min(limit, MAX_LIMIT))
    docs = store.query(LINKS.name, [(k, "==", v) for k, v in filters.items()], order_by="created_at", descending=True, limit=limit)
    docs = [d for d in docs if not _is_deleted(d)]
    return success({"records": docs, "count": len(docs)})


def live_for(store, field, value, limit=SCAN_LIMIT) -> builtins.list:
    """Every non-deleted link whose `field` (subject_id or location_id) equals `value`, ended or not."""
    return [d for d in store.query(LINKS.name, [(field, "==", value)], limit=limit) if not _is_deleted(d)]


# =============================================================================
# update
# =============================================================================

def update(store, id, changes, actor, expected_updated_at=None, tx=None, now=None, check=None):
    """Change dates, is_primary, description, verification, notes. A value of None (or "") removes an optional field.
    The four identity fields are `immutable`. `status` follows `valid_to` (set it: ended; remove it: active).
    Dates always take the whole-record path (one read). check: optional function(merged record) -> problems from the service."""
    problems = check_actor(actor) + _id_problem(id)
    if expected_updated_at is not None and not (isinstance(expected_updated_at, str) and STAMP.match(expected_updated_at)):
        problems.append({"field": "expected_updated_at", "issue": "invalid_format"})
    if not isinstance(changes, dict) or not changes:
        problems.append({"field": "changes", "issue": "required"})
    if problems:
        return _bad(problems)
    set_fields: dict = {}
    removals: list = []
    for name, raw in changes.items():
        if name in IMMUTABLE:
            problems.append({"field": name, "issue": "immutable"})
        elif name not in LINKS.properties or name in LINKS.read_only:
            problems.append({"field": name, "issue": "not_allowed"})
        else:
            value = _normalize_value(name, raw)
            if value is None:
                removals.append(name)
            else:
                problems += check_field(LINKS, name, value)
                set_fields[name] = value
    if problems:
        return _bad(problems)

    touched = set(set_fields) | set(removals)
    needs_whole = bool(touched & RULE_FIELDS) or check is not None
    stamp = stamp_update(actor, now)
    expected = expected_updated_at
    if needs_whole:
        cur = store.get(LINKS.name, id)
        if cur is None or _is_deleted(cur):
            return failure("not_found")
        if expected is not None and cur.get("updated_at") != expected:
            return failure("conflict")
        merged = {**cur, **set_fields}
        for f in removals:
            merged.pop(f, None)
        problems = check_document(LINKS, {k: v for k, v in merged.items() if k != "status"}) or _run_rules(merged)
        if not problems and check is not None:
            problems = check(merged)
        if problems:
            return _bad(problems)
        new_status = _status_for(merged)
        if new_status != cur.get("status"):
            set_fields["status"] = new_status
        expected = cur["updated_at"]
    try:
        store.update(LINKS.name, id, {**set_fields, **stamp}, removals, expected_updated_at=expected, tx=tx)
    except DocMissing:
        return failure("not_found")
    except StaleUpdate:
        return failure("conflict")
    return success({"id": id, "changed": sorted(set_fields), "removed": sorted(removals),
                    "updated_at": stamp["updated_at"], "updated_by": actor})


# =============================================================================
# soft delete, set_primary, scrub
# =============================================================================

def soft_delete(store, id, actor, tx=None, now=None):
    problems = check_actor(actor) + _id_problem(id)
    if problems:
        return _bad(problems)
    cur = store.get(LINKS.name, id)
    if cur is None or _is_deleted(cur):
        return failure("not_found")
    stamp = utc_stamp(now)
    try:
        store.update(LINKS.name, id, {"deleted_at": stamp, "deleted_by": actor, "updated_at": stamp, "updated_by": actor}, (),
                     expected_updated_at=cur["updated_at"], tx=tx)
    except DocMissing:
        return failure("not_found")
    except StaleUpdate:
        return failure("conflict")
    return success({"id": id, "deleted_at": stamp})


def set_primary(store, id, value, actor, tx=None, now=None):
    """Used by the service to promote (True) or demote (False) a link. Demoting removes the flag; false is never stored."""
    problems = check_actor(actor) + _id_problem(id)
    if not isinstance(value, bool):
        problems.append({"field": "is_primary", "issue": "invalid_type"})
    if problems:
        return _bad(problems)
    try:
        store.update(LINKS.name, id, {**({"is_primary": True} if value else {}), **stamp_update(actor, now)},
                     () if value else ("is_primary",), tx=tx)
    except DocMissing:
        return failure("not_found")
    return success({"id": id, "is_primary": value})


def scrub(store, id, actor, tx=None, now=None):
    """Soft delete a link of an erased person and remove everything that describes the relationship, leaving an anonymous tombstone."""
    problems = check_actor(actor) + _id_problem(id)
    if problems:
        return _bad(problems)
    cur = store.get(LINKS.name, id)
    if cur is None:
        return failure("not_found")
    stamp = utc_stamp(now)
    removals = [f for f in SCRUB_FIELDS if f in cur]
    try:
        store.update(LINKS.name, id, {"status": "ended", "deleted_at": cur.get("deleted_at", stamp), "deleted_by": cur.get("deleted_by", actor),
                                      "updated_at": stamp, "updated_by": actor}, removals, tx=tx)
    except DocMissing:
        return failure("not_found")
    return success({"id": id, "removed": sorted(removals)})
