"""CRUD handler for the `venues` collection. Model handler file: copy this shape for the next collection
(docs/schema-first-build-method.md, section 6 and Appendix A).

Rules of this file:
  * Plain functions called by services, in-process. Never an endpoint, never takes an HTTP request.
  * Validates with the standard checker through the kit. No business logic (who may do what, what happens next).
  * Returns a Result. Problems name fields, never values.
  * `store` is any document store with get/create/update/query (MemoryDocStore now, Firestore later).
    `tx` is optional: when a service passes one, writes join its transaction.
"""
from __future__ import annotations

import builtins
import re
from typing import Optional

from .schema_kit import (
    UUID_PATTERN, check_actor, check_document, check_field, clean, drop_empty, failure,
    load_collection, stamp_create, stamp_update, success, utc_stamp,
)
from .store_errors import DocExists, DocMissing, StaleUpdate

VENUES = load_collection("venue")

SOURCES = ("dashboard", "import")
DEFAULT_LIMIT = 100
MAX_LIMIT = 200
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


# =============================================================================
# RULES BLOCK: everything specific to venues that the schema cannot say
# =============================================================================

LOWERCASE_FIELDS = tuple(f for f in ("contact_email", "backup_contact_email") if f in VENUES.properties)


def _rooms_labels_unique(doc: dict) -> list:
    labels = [str(r.get("label", "")).strip().lower() for r in doc.get("rooms", []) if isinstance(r, dict)]
    return [] if len(labels) == len(set(labels)) else [{"field": "rooms", "issue": "duplicate"}]


def _rooms_preferred_within_max(doc: dict) -> list:
    for r in doc.get("rooms", []):
        if isinstance(r, dict) and "preferred_occupancy" in r and "max_occupancy" in r:
            if r["preferred_occupancy"] > r["max_occupancy"]:
                return [{"field": "rooms", "issue": "out_of_range"}]
    return []


def _hours_open_before_close(doc: dict) -> list:
    for h in doc.get("availability_hours", []):
        if isinstance(h, dict) and "opens_at" in h and "closes_at" in h and h["opens_at"] >= h["closes_at"]:
            return [{"field": "availability_hours", "issue": "out_of_range"}]
    return []


# (name, fields it reads, function). The fields column decides when an update must use the whole-record path.
CROSS_FIELD_RULES = (
    ("room_labels_unique", ("rooms",), _rooms_labels_unique),
    ("room_preferred_not_above_max", ("rooms",), _rooms_preferred_within_max),
    ("opens_before_closes", ("availability_hours",), _hours_open_before_close),
)
RULE_FIELDS = frozenset(f for _, fields, _ in CROSS_FIELD_RULES for f in fields)


def _prune(value):
    """Drop nulls left by blank strings inside nested objects (rooms, hours)."""
    if isinstance(value, dict):
        return {k: _prune(v) for k, v in value.items() if v is not None}
    if isinstance(value, builtins.list):
        return [_prune(v) for v in value if v is not None]
    return value


def _normalize_value(name: str, value):
    value = clean(value)
    if isinstance(value, str) and name in LOWERCASE_FIELDS:
        value = value.lower()
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

    read_only = [{"field": k, "issue": "not_allowed"} for k in data if k in VENUES.read_only]
    if read_only:
        return _bad(read_only)

    doc = drop_empty({k: _normalize_value(k, v) for k, v in data.items()})
    problems = check_document(VENUES, doc)
    if not problems:
        problems = _run_rules(doc)
    if problems:
        return _bad(problems)

    if store.query(VENUES.name, [("slug", "==", doc["slug"])], limit=1):  # includes soft-deleted venues
        return _bad([{"field": "slug", "issue": "duplicate"}])

    doc = stamp_create(VENUES, doc, actor, source, now)
    doc["review_count"] = 0
    missing = [{"field": f, "issue": "required"} for f in VENUES.server_required if f not in doc]
    self_check = check_document(VENUES, doc) + missing
    if self_check:  # our own bug, not the sender's: say nothing about fields
        return failure("server_error")
    try:
        store.create(VENUES.name, doc["id"], doc, tx=tx)
    except DocExists:
        return failure("server_error")
    return success(doc)


# =============================================================================
# get / list
# =============================================================================

def get(store, id, include_deleted=False):
    problems = _id_problem(id)
    if problems:
        return _bad(problems)
    doc = store.get(VENUES.name, id)
    if doc is None or (_is_deleted(doc) and not include_deleted):
        return failure("not_found")
    return success(doc)


_LIST_FILTERS = ("status", "is_public_venue")


def list(store, filters=None, order="name", limit=DEFAULT_LIMIT):  # noqa: A001  (the name is the contract)
    """Supported: no filter or ONE of status / is_public_venue, ordered by name; no filter ordered by -created_at.
    Anything else is `not_supported`, because each combination needs an index (section 8 of the method doc).
    Soft-deleted venues are left out after the query, so a page can hold fewer than `limit` records."""
    filters = dict(filters or {})
    problems = []
    for k, v in filters.items():
        if k not in _LIST_FILTERS:
            problems.append({"field": k, "issue": "not_supported"})
        else:
            problems += check_field(VENUES, k, v)
    if len(filters) > 1:
        problems += [{"field": k, "issue": "not_supported"} for k in filters]
    if order not in ("name", "-created_at"):
        problems.append({"field": "order", "issue": "not_supported"})
    elif order == "-created_at" and filters:
        problems.append({"field": "order", "issue": "not_supported"})
    if isinstance(limit, bool) or not isinstance(limit, int):
        problems.append({"field": "limit", "issue": "invalid_type"})
    if problems:
        return _bad(problems)
    limit = max(1, min(limit, MAX_LIMIT))
    docs = store.query(VENUES.name, [(k, "==", v) for k, v in filters.items()],
                       order_by=order.lstrip("-"), descending=order.startswith("-"), limit=limit)
    docs = [d for d in docs if not _is_deleted(d)]
    return success({"records": docs, "count": len(docs)})


# =============================================================================
# update
# =============================================================================

def update(store, id, changes, actor, expected_updated_at=None, tx=None, now=None):
    """Change some fields. A value of None (or "") removes an optional field.

    Simple path (no read): every changed field is checked against its own definition and nothing else
    is looked at. Whole-record path (one read): used only when a changed field takes part in a cross-field
    rule (schema set_involved/remove_involved, or a code rule), because then the other fields matter.
    expected_updated_at: if given, the write is refused with `conflict` when the record changed since.
    Updating a soft-deleted venue is allowed on the simple path (no read to notice); the whole-record path refuses it.
    """
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
        if name == "slug":
            problems.append({"field": name, "issue": "immutable"})
        elif name not in VENUES.properties or name in VENUES.read_only:
            problems.append({"field": name, "issue": "not_allowed"})
        else:
            value = _normalize_value(name, raw)
            if value is None:
                (problems.append({"field": name, "issue": "required"}) if name in VENUES.required
                 else removals.append(name))
            else:
                problems += check_field(VENUES, name, value)
                set_fields[name] = value
    if problems:
        return _bad(problems)

    needs_whole = (any(f in VENUES.set_involved or f in RULE_FIELDS for f in set_fields)
                   or any(f in VENUES.remove_involved or f in RULE_FIELDS for f in removals))
    stamp = stamp_update(actor, now)
    expected = expected_updated_at

    if needs_whole:
        cur = store.get(VENUES.name, id)
        if cur is None or _is_deleted(cur):
            return failure("not_found")
        if expected is not None and cur.get("updated_at") != expected:
            return failure("conflict")
        merged = {**cur, **set_fields}
        for f in removals:
            merged.pop(f, None)
        problems = check_document(VENUES, merged)
        if not problems:
            problems = _run_rules(merged)
        if problems:
            return _bad(problems)
        expected = cur["updated_at"]  # the record must not move between our read and our write

    try:
        store.update(VENUES.name, id, {**set_fields, **stamp}, removals, expected_updated_at=expected, tx=tx)
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
    """Mark deleted; the record stays. The service must first make sure no class points at this venue
    (the schema says: set it inactive instead). Deleting twice is `not_found`."""
    problems = check_actor(actor) + _id_problem(id)
    if problems:
        return _bad(problems)
    cur = store.get(VENUES.name, id)
    if cur is None or _is_deleted(cur):
        return failure("not_found")
    stamp = utc_stamp(now)
    fields = {"deleted_at": stamp, "deleted_by": actor, "updated_at": stamp, "updated_by": actor}
    try:
        store.update(VENUES.name, id, fields, (), expected_updated_at=cur["updated_at"], tx=tx)
    except DocMissing:
        return failure("not_found")
    except StaleUpdate:
        return failure("conflict")
    return success({"id": id, "deleted_at": stamp})


# =============================================================================
# server-kept summary fields (written only by the reviews service)
# =============================================================================

def set_review_summary(store, id, review_count, average_rating, actor="system:reviews", tx=None, now=None):
    problems = check_actor(actor) + _id_problem(id)
    problems += check_field(VENUES, "review_count", review_count, allow_read_only=True)
    if average_rating is not None:
        problems += check_field(VENUES, "average_rating", average_rating, allow_read_only=True)
    if problems:
        return _bad(problems)
    fields = {"review_count": review_count, **stamp_update(actor, now)}
    removals = []
    if average_rating is None:
        removals.append("average_rating")
    else:
        fields["average_rating"] = average_rating
    try:
        store.update(VENUES.name, id, fields, removals, tx=tx)
    except DocMissing:
        return failure("not_found")
    return success({"id": id, "review_count": review_count, "average_rating": average_rating})
