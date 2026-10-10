"""CRUD handler for the `registration_assignments` collection. Same shape as scheduled_classes_crud.py.

An assignment is the decision that puts a registration request into a class (accepted, overflow, waitlisted,
declined or cancelled). Rules of this file (docs/schema-first-build-method.md, section 6):
  * Plain functions called by services, in-process. Never an endpoint.
  * Validates with the standard checker through the kit. No business logic (seat counts, class status).
  * Knows ONLY its own collection. Rules that need the request or the class live in assignments_service.py,
    which passes them to `create` as `check`.
  * A decision is never overwritten. Changing a decision is a NEW record whose `previous_id` names the one it
    replaces (x_history: linked_records). The only in-place edits are the note and the transaction ids.
  * Returns a Result. Problems name fields, never values.

The helpers at the bottom (`current_only`, `for_class`, `for_request`) answer "which decisions stand now": a
record stands when it is not soft-deleted and no other record names it as `previous_id`. A replacement always
keeps the same request and class (a move to another class is a cancel plus a new assignment), so the two
equality queries below find every record in a chain.
"""
from __future__ import annotations

import re

from .schema_kit import (
    UUID_PATTERN, check_actor, check_document, check_field, clean, drop_empty, failure,
    load_collection, stamp_create, stamp_update, success, utc_stamp,
)
from .store_errors import DocExists, DocMissing, StaleUpdate

ASSIGNMENTS = load_collection("registration_assignment")

SOURCES = ("dashboard", "import", "system")
DEFAULT_LIMIT = 100
MAX_LIMIT = 200
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
SEAT_STATUSES = ("accepted", "overflow")          # these count toward the class's registered_count
HOLDING_STATUSES = ("accepted", "overflow", "waitlisted")  # a decision that still holds a place
# Server-supplied fields a SERVICE may pass to create (a browser may never send these).
SERVER_FIELDS_ALLOWED = ("program_slug", "previous_id")


# =============================================================================
# RULES BLOCK: everything specific to assignments that the schema cannot say
# =============================================================================

# A decision is never edited into a different decision: change it by writing a new linked record.
IMMUTABLE_FIELDS = ("request_id", "scheduled_class_id", "status", "attendee_count")


def _bad(problems: list):
    seen, out = set(), []
    for p in problems:
        k = (p["field"], p["issue"])
        if k not in seen:
            seen.add(k)
            out.append(p)
    return failure("validation_failed", out)


def _id_problem(id) -> list:
    return [] if isinstance(id, str) and UUID_PATTERN.match(id) else [{"field": "id", "issue": "invalid_format"}]


def _is_deleted(doc: dict) -> bool:
    return "deleted_at" in doc


# =============================================================================
# create
# =============================================================================

def create(store, data, actor, source="dashboard", tx=None, now=None, check=None, server_fields=None):
    """server_fields: values only a service may set (program_slug, previous_id). decided_at and decided_by
    are set here from `now` and `actor`."""
    problems = check_actor(actor)
    if source not in SOURCES:
        problems.append({"field": "source", "issue": "invalid_value"})
    if problems:
        return _bad(problems)
    if not isinstance(data, dict):
        return _bad([{"field": "body", "issue": "invalid_type"}])

    read_only = [{"field": k, "issue": "not_allowed"} for k in data if k in ASSIGNMENTS.read_only]
    if read_only:
        return _bad(read_only)

    extra = dict(server_fields or {})
    if any(k not in SERVER_FIELDS_ALLOWED for k in extra):
        return failure("server_error")

    doc = drop_empty({k: clean(v) for k, v in data.items()})
    doc.update(extra)
    stamp = utc_stamp(now)
    problems = check_document(ASSIGNMENTS, doc)
    if not problems and check is not None:
        problems = check(doc)
    if problems:
        return _bad(problems)

    doc = stamp_create(ASSIGNMENTS, doc, actor, source, now)
    doc["decided_at"], doc["decided_by"] = stamp, actor
    missing = [{"field": f, "issue": "required"} for f in ASSIGNMENTS.server_required if f not in doc]
    if check_document(ASSIGNMENTS, doc) or missing:  # our own bug, not the sender's: say nothing about fields
        return failure("server_error")
    try:
        store.create(ASSIGNMENTS.name, doc["id"], doc, tx=tx)
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
    doc = store.get(ASSIGNMENTS.name, id)
    if doc is None or (_is_deleted(doc) and not include_deleted):
        return failure("not_found")
    return success(doc)


_LIST_FILTERS = ("status", "scheduled_class_id", "request_id")


def list(store, filters=None, order="-created_at", limit=DEFAULT_LIMIT):  # noqa: A001  (the name is the contract)
    """Supported: no filter or ONE of status / scheduled_class_id / request_id, newest first (-created_at).
    Anything else is `not_supported` (each combination needs an index, section 8). Soft-deleted records are left
    out after the query, so a page can hold fewer than `limit` records. Superseded decisions ARE returned
    (they are history); a reader marks a record superseded when another record names it as previous_id."""
    filters = dict(filters or {})
    problems = []
    for k, v in filters.items():
        if k not in _LIST_FILTERS:
            problems.append({"field": k, "issue": "not_supported"})
        else:
            problems += check_field(ASSIGNMENTS, k, v)
    if len(filters) > 1:
        problems += [{"field": k, "issue": "not_supported"} for k in filters]
    if order != "-created_at":
        problems.append({"field": "order", "issue": "not_supported"})
    if isinstance(limit, bool) or not isinstance(limit, int):
        problems.append({"field": "limit", "issue": "invalid_type"})
    if problems:
        return _bad(problems)
    limit = max(1, min(limit, MAX_LIMIT))
    docs = store.query(ASSIGNMENTS.name, [(k, "==", v) for k, v in filters.items()],
                       order_by="created_at", descending=True, limit=limit)
    docs = [d for d in docs if not _is_deleted(d)]
    return success({"records": docs, "count": len(docs)})


# =============================================================================
# update (only the note and the transaction ids; a decision is changed by a new record)
# =============================================================================

def update(store, id, changes, actor, expected_updated_at=None, tx=None, now=None):
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
        if name in IMMUTABLE_FIELDS:
            problems.append({"field": name, "issue": "immutable"})
        elif name not in ASSIGNMENTS.properties or name in ASSIGNMENTS.read_only:
            problems.append({"field": name, "issue": "not_allowed"})
        else:
            value = clean(raw)
            if value is None:
                (problems.append({"field": name, "issue": "required"}) if name in ASSIGNMENTS.required
                 else removals.append(name))
            else:
                problems += check_field(ASSIGNMENTS, name, value)
                set_fields[name] = value
    if problems:
        return _bad(problems)

    expected = expected_updated_at
    if any(f in ASSIGNMENTS.set_involved for f in set_fields) or any(f in ASSIGNMENTS.remove_involved for f in removals):
        cur = store.get(ASSIGNMENTS.name, id)
        if cur is None or _is_deleted(cur):
            return failure("not_found")
        if expected is not None and cur.get("updated_at") != expected:
            return failure("conflict")
        merged = {**cur, **set_fields}
        for f in removals:
            merged.pop(f, None)
        problems = check_document(ASSIGNMENTS, merged)
        if problems:
            return _bad(problems)
        expected = cur["updated_at"]

    stamp = stamp_update(actor, now)
    try:
        store.update(ASSIGNMENTS.name, id, {**set_fields, **stamp}, removals, expected_updated_at=expected, tx=tx)
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
    """Mark deleted; the record stays. Deleting twice is `not_found`. The service decides whether deleting a
    decision is allowed at all (it is not, today: cancel the assignment instead)."""
    problems = check_actor(actor) + _id_problem(id)
    if problems:
        return _bad(problems)
    cur = store.get(ASSIGNMENTS.name, id)
    if cur is None or _is_deleted(cur):
        return failure("not_found")
    stamp = utc_stamp(now)
    fields = {"deleted_at": stamp, "deleted_by": actor, "updated_at": stamp, "updated_by": actor}
    try:
        store.update(ASSIGNMENTS.name, id, fields, (), expected_updated_at=cur["updated_at"], tx=tx)
    except DocMissing:
        return failure("not_found")
    except StaleUpdate:
        return failure("conflict")
    return success({"id": id, "deleted_at": stamp})


# =============================================================================
# which decisions stand now (read helpers for services)
# =============================================================================

def current_only(docs: list) -> list:
    """Not soft-deleted, and not named as previous_id by another record in `docs`."""
    superseded = {d["previous_id"] for d in docs if d.get("previous_id")}
    return [d for d in docs if not _is_deleted(d) and d["id"] not in superseded]


def for_class(store, class_id: str, limit: int = 500) -> list:
    """Every record for a class (history included, soft-deleted included). One equality query, no index."""
    return store.query(ASSIGNMENTS.name, [("scheduled_class_id", "==", class_id)], limit=limit)


def for_request(store, request_id: str, limit: int = 100) -> list:
    return store.query(ASSIGNMENTS.name, [("request_id", "==", request_id)], limit=limit)
