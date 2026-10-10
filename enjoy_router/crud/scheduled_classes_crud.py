"""CRUD handler for the `scheduled_classes` collection. Same shape as venues_crud.py (the model handler file).

Rules of this file (docs/schema-first-build-method.md, section 6):
  * Plain functions called by services, in-process. Never an endpoint, never takes an HTTP request.
  * Validates with the standard checker through the kit. No business logic (who may do what, what happens next).
  * Knows ONLY its own collection. It never reads venues or any other collection. Rules that need another
    collection live in classes_service.py, which hands them to create/update as `check`.
  * Returns a Result. Problems name fields, never values.

`check` (create and update): an optional function(doc) -> problems, run on the final record after the schema
and this file's own rules pass. `check_fields` (update): the fields that make an update use the whole-record
path so `check` can see the merged record.
"""
from __future__ import annotations

import re

from .schema_kit import (
    UUID_PATTERN, check_actor, check_document, check_field, clean, drop_empty, failure,
    load_collection, stamp_create, stamp_update, success, utc_stamp,
)
from .store_errors import DocExists, DocMissing, StaleUpdate

CLASSES = load_collection("scheduled_class")

SOURCES = ("dashboard", "import")
DEFAULT_LIMIT = 100
MAX_LIMIT = 200
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
COUNT_FIELDS = ("registered_count", "waitlist_count", "attended_count", "review_count")  # start at 0, server-kept


# =============================================================================
# RULES BLOCK: everything specific to scheduled classes that the schema cannot say
# =============================================================================

LOWERCASE_FIELDS = tuple(f for f in ("organizer_email",) if f in CLASSES.properties)


def _capacity_order(doc: dict) -> list:
    """capacity_minimum <= capacity_target <= capacity_max (schema description, an endpoint rule)."""
    lo, mid, hi = doc.get("capacity_minimum"), doc.get("capacity_target"), doc.get("capacity_max")
    out = []
    if isinstance(lo, int) and isinstance(mid, int) and lo > mid:
        out.append({"field": "capacity_minimum", "issue": "out_of_range"})
    if isinstance(mid, int) and isinstance(hi, int) and mid > hi:
        out.append({"field": "capacity_max", "issue": "out_of_range"})
    if isinstance(lo, int) and isinstance(hi, int) and lo > hi and not out:
        out.append({"field": "capacity_max", "issue": "out_of_range"})
    return out


def _cancelled_reason_only_when_cancelled(doc: dict) -> list:
    if "cancelled_reason" in doc and doc.get("status") != "cancelled":
        return [{"field": "cancelled_reason", "issue": "not_allowed"}]
    return []


def _source_request_only_private_or_group(doc: dict) -> list:
    if "source_request_id" in doc and doc.get("class_type") == "workshop":
        return [{"field": "source_request_id", "issue": "not_allowed"}]
    return []


def _capacity_not_below_registered(doc: dict) -> list:
    """The biggest size cannot drop below the seats already registered (registered_count is server-kept)."""
    hi, reg = doc.get("capacity_max"), doc.get("registered_count")
    if isinstance(hi, int) and isinstance(reg, int) and hi < reg:
        return [{"field": "capacity_max", "issue": "out_of_range"}]
    return []


# (name, fields it reads, function). The fields column decides when an update must use the whole-record path.
CROSS_FIELD_RULES = (
    ("capacity_order", ("capacity_minimum", "capacity_target", "capacity_max"), _capacity_order),
    ("capacity_not_below_registered", ("capacity_max", "registered_count"), _capacity_not_below_registered),
    ("cancelled_reason_only_when_cancelled", ("cancelled_reason", "status"), _cancelled_reason_only_when_cancelled),
    ("source_request_only_private_or_group", ("source_request_id", "class_type"), _source_request_only_private_or_group),
)
RULE_FIELDS = frozenset(f for _, fields, _ in CROSS_FIELD_RULES for f in fields)


def _normalize_value(name: str, value):
    value = clean(value)
    if isinstance(value, str) and name in LOWERCASE_FIELDS:
        value = value.lower()
    return value


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

def create(store, data, actor, source="dashboard", tx=None, now=None, check=None):
    problems = check_actor(actor)
    if source not in SOURCES:
        problems.append({"field": "source", "issue": "invalid_value"})
    if problems:
        return _bad(problems)
    if not isinstance(data, dict):
        return _bad([{"field": "body", "issue": "invalid_type"}])

    read_only = [{"field": k, "issue": "not_allowed"} for k in data if k in CLASSES.read_only]
    if read_only:
        return _bad(read_only)

    doc = drop_empty({k: _normalize_value(k, v) for k, v in data.items()})
    problems = check_document(CLASSES, doc)
    if not problems:
        problems = _run_rules(doc)
    if not problems and check is not None:
        problems = check(doc)
    if problems:
        return _bad(problems)

    if store.query(CLASSES.name, [("slug", "==", doc["slug"])], limit=1):  # includes soft-deleted classes
        return _bad([{"field": "slug", "issue": "duplicate"}])

    doc = stamp_create(CLASSES, doc, actor, source, now)
    for f in COUNT_FIELDS:
        doc[f] = 0
    missing = [{"field": f, "issue": "required"} for f in CLASSES.server_required if f not in doc]
    self_check = check_document(CLASSES, doc) + missing
    if self_check:  # our own bug, not the sender's: say nothing about fields
        return failure("server_error")
    try:
        store.create(CLASSES.name, doc["id"], doc, tx=tx)
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
    doc = store.get(CLASSES.name, id)
    if doc is None or (_is_deleted(doc) and not include_deleted):
        return failure("not_found")
    return success(doc)


_LIST_FILTERS = ("status", "class_type", "venue_id", "is_public")


def list(store, filters=None, order="title", limit=DEFAULT_LIMIT):  # noqa: A001  (the name is the contract)
    """Supported: no filter or ONE of status / class_type / venue_id / is_public, ordered by title; no filter
    may also be ordered by -created_at. Anything else is `not_supported`, because each combination needs an index
    (section 8 of the method doc). Not ordered by starts_at: an idea has no start, and a store leaves out
    records that lack the ordered field. Soft-deleted classes are left out after the query, so a page can hold
    fewer than `limit` records."""
    filters = dict(filters or {})
    problems = []
    for k, v in filters.items():
        if k not in _LIST_FILTERS:
            problems.append({"field": k, "issue": "not_supported"})
        else:
            problems += check_field(CLASSES, k, v)
    if len(filters) > 1:
        problems += [{"field": k, "issue": "not_supported"} for k in filters]
    if order not in ("title", "-created_at"):
        problems.append({"field": "order", "issue": "not_supported"})
    elif order == "-created_at" and filters:
        problems.append({"field": "order", "issue": "not_supported"})
    if isinstance(limit, bool) or not isinstance(limit, int):
        problems.append({"field": "limit", "issue": "invalid_type"})
    if problems:
        return _bad(problems)
    limit = max(1, min(limit, MAX_LIMIT))
    docs = store.query(CLASSES.name, [(k, "==", v) for k, v in filters.items()],
                       order_by=order.lstrip("-"), descending=order.startswith("-"), limit=limit)
    docs = [d for d in docs if not _is_deleted(d)]
    return success({"records": docs, "count": len(docs)})


# =============================================================================
# update
# =============================================================================

def update(store, id, changes, actor, expected_updated_at=None, tx=None, now=None, check=None, check_fields=()):
    """Change some fields. A value of None (or "") removes an optional field.

    Simple path (no read): every changed field is checked against its own definition and nothing else
    is looked at. Whole-record path (one read): used only when a changed field takes part in a cross-field
    rule (schema set_involved/remove_involved, a code rule, or check_fields), because then the other fields matter.
    expected_updated_at: if given, the write is refused with `conflict` when the record changed since.
    Updating a soft-deleted class is allowed on the simple path (no read to notice); the whole-record path refuses it.
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
        elif name not in CLASSES.properties or name in CLASSES.read_only:
            problems.append({"field": name, "issue": "not_allowed"})
        else:
            value = _normalize_value(name, raw)
            if value is None:
                (problems.append({"field": name, "issue": "required"}) if name in CLASSES.required
                 else removals.append(name))
            else:
                problems += check_field(CLASSES, name, value)
                set_fields[name] = value
    if problems:
        return _bad(problems)

    extra = frozenset(check_fields) if check is not None else frozenset()
    needs_whole = (any(f in CLASSES.set_involved or f in RULE_FIELDS or f in extra for f in set_fields)
                   or any(f in CLASSES.remove_involved or f in RULE_FIELDS or f in extra for f in removals))
    stamp = stamp_update(actor, now)
    expected = expected_updated_at

    if needs_whole:
        cur = store.get(CLASSES.name, id)
        if cur is None or _is_deleted(cur):
            return failure("not_found")
        if expected is not None and cur.get("updated_at") != expected:
            return failure("conflict")
        merged = {**cur, **set_fields}
        for f in removals:
            merged.pop(f, None)
        problems = check_document(CLASSES, merged)
        if not problems:
            problems = _run_rules(merged)
        if not problems and check is not None:
            problems = check(merged)
        if problems:
            return _bad(problems)
        expected = cur["updated_at"]  # the record must not move between our read and our write

    try:
        store.update(CLASSES.name, id, {**set_fields, **stamp}, removals, expected_updated_at=expected, tx=tx)
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
    """Mark deleted; the record stays. Deleting twice is `not_found`. The service decides whether a class that
    already has registrations may go (nothing is enforced here)."""
    problems = check_actor(actor) + _id_problem(id)
    if problems:
        return _bad(problems)
    cur = store.get(CLASSES.name, id)
    if cur is None or _is_deleted(cur):
        return failure("not_found")
    stamp = utc_stamp(now)
    fields = {"deleted_at": stamp, "deleted_by": actor, "updated_at": stamp, "updated_by": actor}
    try:
        store.update(CLASSES.name, id, fields, (), expected_updated_at=cur["updated_at"], tx=tx)
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
    problems += check_field(CLASSES, "review_count", review_count, allow_read_only=True)
    if average_rating is not None:
        problems += check_field(CLASSES, "average_rating", average_rating, allow_read_only=True)
    if problems:
        return _bad(problems)
    fields = {"review_count": review_count, **stamp_update(actor, now)}
    removals = []
    if average_rating is None:
        removals.append("average_rating")
    else:
        fields["average_rating"] = average_rating
    try:
        store.update(CLASSES.name, id, fields, removals, tx=tx)
    except DocMissing:
        return failure("not_found")
    return success({"id": id, "review_count": review_count, "average_rating": average_rating})


# =============================================================================
# server-kept seat counts (written only by the assignments service)
# =============================================================================

def set_registration_counts(store, id, registered_count, waitlist_count, actor="system:assignments", tx=None, now=None):
    """Write registered_count (accepted + overflow seats) and waitlist_count. No read, no other rule."""
    problems = check_actor(actor) + _id_problem(id)
    problems += check_field(CLASSES, "registered_count", registered_count, allow_read_only=True)
    problems += check_field(CLASSES, "waitlist_count", waitlist_count, allow_read_only=True)
    if problems:
        return _bad(problems)
    fields = {"registered_count": registered_count, "waitlist_count": waitlist_count, **stamp_update(actor, now)}
    try:
        store.update(CLASSES.name, id, fields, (), tx=tx)
    except DocMissing:
        return failure("not_found")
    return success({"id": id, "registered_count": registered_count, "waitlist_count": waitlist_count})
