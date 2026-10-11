"""CRUD handler for the `individual_restricted_details` collection (schemas/individual_restricted_detail.schema.json,
INDIVIDUAL_RESTRICTED_DETAIL_GUIDE.md). Same shape as venues_crud.py and individuals_crud.py.

Rules of this file:
  * Plain functions called by services, in-process. Never an endpoint. Who may read or write (admin only, logged
    reads) is the service's and the endpoint's job, not this file's.
  * Every write needs a purpose and a consent_ref or legal_basis (the schema), and each sensitive field may be held
    only for a purpose it allows (x_allowed_purposes in the schema).
  * One record per individual. The individual must exist, must not be erased, and must not be a minor (the
    guardianship schema does not exist yet, so a minor's restricted details are refused).
  * Every update writes one record to `individual_restricted_detail_history` in the same transaction.
  * Erasing the individual erases this record too; that is the erase handler's job (later), not this file's.
"""
from __future__ import annotations

import builtins
import re
from typing import Optional

from .individuals_crud import INDIVIDUALS, is_minor_from
from .schema_kit import (
    UUID_PATTERN, check_actor, check_document, clean, drop_empty, failure, load_collection,
    new_id, stamp_create, stamp_update, success, utc_stamp,
)
from .store_errors import DocExists, DocMissing, StaleUpdate

DETAILS = load_collection("individual_restricted_detail")
HISTORY = DETAILS.type_name + "_history"

SOURCES = ("dashboard", "import")
DEFAULT_LIMIT = 100
MAX_LIMIT = 200
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
BASIS_FIELDS = frozenset({"individual_id", "purpose", "consent_ref", "legal_basis"})
ALLOWED = {k: tuple(v["x_allowed_purposes"]) for k, v in DETAILS.properties.items() if "x_allowed_purposes" in v}


# =============================================================================
# RULES BLOCK
# =============================================================================

def _purpose_rules(doc: dict) -> list:
    """Each sensitive field present must allow the record's purpose."""
    purpose = doc.get("purpose")
    return [{"field": f, "issue": "purpose_not_allowed"} for f, ok in ALLOWED.items()
            if f in doc and purpose not in ok]


def _individual_rules(store, individual_id: str, now=None) -> list:
    ind = store.get(INDIVIDUALS.name, individual_id)
    if ind is None or "deleted_at" in ind or ind.get("status") in ("merged", "erased"):
        return [{"field": "individual_id", "issue": "not_found"}]
    if is_minor_from(ind.get("birth_date"), now):
        return [{"field": "individual_id", "issue": "minor_needs_guardian"}]
    return []


def _bad(problems: list):
    seen, out = set(), []
    for p in problems:
        k = (p["field"], p["issue"])
        if k not in seen:
            seen.add(k)
            out.append(p)
    return failure("validation_failed", out)


def _id_problem(id, field="id") -> list:
    return [] if isinstance(id, str) and UUID_PATTERN.match(id) else [{"field": field, "issue": "invalid_format"}]


def _is_deleted(doc: dict) -> bool:
    return "deleted_at" in doc


def _prune(value):
    if isinstance(value, dict):
        return {k: _prune(v) for k, v in value.items() if v is not None}
    if isinstance(value, builtins.list):
        return [_prune(v) for v in value if v is not None]
    return value


def _existing_for(store, individual_id: str) -> Optional[dict]:
    for d in store.query(DETAILS.name, [("individual_id", "==", individual_id)], limit=5):
        if not _is_deleted(d):
            return d
    return None


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

    read_only = [{"field": k, "issue": "not_allowed"} for k in data if k in DETAILS.read_only]
    if read_only:
        return _bad(read_only)

    doc = drop_empty({k: _prune(clean(v)) for k, v in data.items()})
    problems = check_document(DETAILS, doc)
    if not problems:
        problems = _purpose_rules(doc)
    if problems:
        return _bad(problems)

    problems = _individual_rules(store, doc["individual_id"], now)
    if problems:
        return _bad(problems)
    if _existing_for(store, doc["individual_id"]) is not None:
        return _bad([{"field": "individual_id", "issue": "duplicate"}])

    doc = stamp_create(DETAILS, doc, actor, source, now)
    missing = [{"field": f, "issue": "required"} for f in DETAILS.server_required if f not in doc]
    if check_document(DETAILS, doc) + missing:
        return failure("server_error")
    try:
        store.create(DETAILS.name, doc["id"], doc, tx=tx)
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
    doc = store.get(DETAILS.name, id)
    if doc is None or (_is_deleted(doc) and not include_deleted):
        return failure("not_found")
    return success(doc)


def get_for_individual(store, individual_id):
    """The one restricted-detail record for an individual, or not_found."""
    problems = _id_problem(individual_id, "individual_id")
    if problems:
        return _bad(problems)
    doc = _existing_for(store, individual_id)
    return success(doc) if doc is not None else failure("not_found")


def list(store, filters=None, order="-created_at", limit=DEFAULT_LIMIT):  # noqa: A001
    """Supported: no filter, or ONE of individual_id / purpose; ordered -created_at only when unfiltered. A filtered
    list has no order guarantee. Soft-deleted records are left out after the query."""
    filters = dict(filters or {})
    problems = []
    for k, v in filters.items():
        if k == "individual_id":
            problems += _id_problem(v, k)
        elif k == "purpose":
            if v not in DETAILS.properties["purpose"]["enum"]:
                problems.append({"field": k, "issue": "invalid_value"})
        else:
            problems.append({"field": k, "issue": "not_supported"})
    if len(filters) > 1:
        problems += [{"field": k, "issue": "not_supported"} for k in filters]
    if order != "-created_at":
        problems.append({"field": "order", "issue": "not_supported"})
    if isinstance(limit, bool) or not isinstance(limit, int):
        problems.append({"field": "limit", "issue": "invalid_type"})
    if problems:
        return _bad(problems)
    limit = max(1, min(limit, MAX_LIMIT))
    docs = store.query(DETAILS.name, [(k, "==", v) for k, v in filters.items()],
                       order_by=None if filters else "created_at", descending=True, limit=limit)
    docs = [d for d in docs if not _is_deleted(d)]
    return success({"records": docs, "count": len(docs)})


# =============================================================================
# update
# =============================================================================

def update(store, id, changes, actor, expected_updated_at=None, tx=None, now=None):
    """Change some fields; None (or "") removes an optional field. Whole-record path always: the purpose rules look
    at every field together. individual_id never changes. A history record (values before and after) is written in
    the same transaction. The basis (purpose plus consent_ref or legal_basis) must still hold after the change."""
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
        if name == "individual_id":
            problems.append({"field": name, "issue": "immutable"})
        elif name not in DETAILS.properties or name in DETAILS.read_only:
            problems.append({"field": name, "issue": "not_allowed"})
        else:
            value = _prune(clean(raw))
            if value is None:
                (problems.append({"field": name, "issue": "required"}) if name in DETAILS.required
                 else removals.append(name))
            else:
                set_fields[name] = value
    if problems:
        return _bad(problems)

    cur = store.get(DETAILS.name, id)
    if cur is None or _is_deleted(cur):
        return failure("not_found")
    if expected_updated_at is not None and cur.get("updated_at") != expected_updated_at:
        return failure("conflict")

    merged = {**cur, **set_fields}
    for f in removals:
        merged.pop(f, None)
    problems = check_document(DETAILS, merged)
    if not problems:
        problems = _purpose_rules(merged)
    if problems:
        return _bad(problems)

    stamp = stamp_update(actor, now)
    changed = sorted(set(set_fields) | set(removals))
    history = {"id": new_id(), "individual_id": cur["individual_id"], "restricted_detail_id": id,
               "changed_at": stamp["updated_at"], "changed_by": actor,
               "before": {k: cur[k] for k in changed if k in cur},
               "after": {k: merged[k] for k in changed if k in merged}}
    try:
        if tx is not None:
            _write_update(store, id, {**set_fields, **stamp}, removals, cur["updated_at"], history, tx)
        else:
            with store.transaction() as own:
                _write_update(store, id, {**set_fields, **stamp}, removals, cur["updated_at"], history, own)
    except DocMissing:
        return failure("not_found")
    except StaleUpdate:
        return failure("conflict")
    return success({"id": id, "changed": sorted(set_fields), "removed": sorted(removals),
                    "updated_at": stamp["updated_at"], "updated_by": actor})


def _write_update(store, id, fields, deletes, expected, history, tx):
    store.update(DETAILS.name, id, fields, deletes, expected_updated_at=expected, tx=tx)
    store.create(HISTORY, history["id"], history, tx=tx)


# =============================================================================
# soft delete
# =============================================================================

def soft_delete(store, id, actor, tx=None, now=None):
    """Mark deleted; the record stays (use when consent is withdrawn and the facts are to stop being used; the erase
    handler, later, removes the personal data itself). A new record may then be created for the individual."""
    problems = check_actor(actor) + _id_problem(id)
    if problems:
        return _bad(problems)
    cur = store.get(DETAILS.name, id)
    if cur is None or _is_deleted(cur):
        return failure("not_found")
    stamp = utc_stamp(now)
    fields = {"deleted_at": stamp, "deleted_by": actor, "updated_at": stamp, "updated_by": actor}
    try:
        store.update(DETAILS.name, id, fields, (), expected_updated_at=cur["updated_at"], tx=tx)
    except DocMissing:
        return failure("not_found")
    except StaleUpdate:
        return failure("conflict")
    return success({"id": id, "deleted_at": stamp})
