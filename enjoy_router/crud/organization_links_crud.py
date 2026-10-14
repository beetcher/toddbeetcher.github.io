"""CRUD handler for the `organization_links` collection: one relationship between a subject (individual, organization,
venue) and an organization, with dates. Shape copied from organizations_crud.py.

This file checks one link at a time: its own fields and the three ids that never change. Whether the subject and the
organization exist is the service's job (organization_links_service.py). No date-order, overlap, loop or primary rules.
list needs no index: equality filters only, sorted here.
"""
from __future__ import annotations

import re

from .schema_kit import (
    UUID_PATTERN, check_actor, check_document, check_field, clean, drop_empty, failure,
    load_collection, stamp_create, stamp_update, success, utc_stamp,
)
from .store_errors import DocExists, DocMissing, StaleUpdate

LINKS = load_collection("organization_link")
SOURCES = ("dashboard", "import")
DEFAULT_LIMIT = 100
MAX_LIMIT = 200
SCAN = 500
IMMUTABLE = ("subject_type", "subject_id", "organization_id")
LIST_FILTERS = ("subject_id", "organization_id", "subject_type", "relationship")
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _bad(problems):
    seen, out = set(), []
    for p in problems:
        k = (p["field"], p["issue"])
        if k not in seen:
            seen.add(k)
            out.append(p)
    return failure("validation_failed", out)


def _id_problem(id):
    return [] if isinstance(id, str) and UUID_PATTERN.match(id) else [{"field": "id", "issue": "invalid_format"}]


def _deleted(doc):
    return "deleted_at" in doc


def validate(data):
    """(tidy doc, problems) for the sender's fields only."""
    if not isinstance(data, dict):
        return {}, [{"field": "body", "issue": "invalid_type"}]
    ro = [{"field": k, "issue": "not_allowed"} for k in data if k in LINKS.read_only]
    if ro:
        return {}, ro
    doc = drop_empty({k: clean(v) for k, v in data.items()})
    return doc, check_document(LINKS, doc)


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
    missing = [f for f in LINKS.server_required if f not in doc]
    if check_document(LINKS, doc) or missing:
        return failure("server_error")
    try:
        store.create(LINKS.name, doc["id"], doc, tx=tx)
    except DocExists:
        return failure("server_error")
    return success(doc)


def get(store, id, include_deleted=False):
    problems = _id_problem(id)
    if problems:
        return _bad(problems)
    doc = store.get(LINKS.name, id)
    if doc is None or (_deleted(doc) and not include_deleted):
        return failure("not_found")
    return success(doc)


def list(store, filters=None, order="-created_at", limit=DEFAULT_LIMIT):  # noqa: A001
    """Any of the equality filters subject_id, organization_id, subject_type, relationship. Order -created_at or valid_from.
    Soft-deleted links are left out."""
    filters = dict(filters or {})
    problems = []
    for k, v in filters.items():
        problems += [{"field": k, "issue": "not_supported"}] if k not in LIST_FILTERS else check_field(LINKS, k, v)
    if order not in ("-created_at", "valid_from"):
        problems.append({"field": "order", "issue": "not_supported"})
    if isinstance(limit, bool) or not isinstance(limit, int):
        problems.append({"field": "limit", "issue": "invalid_type"})
    if problems:
        return _bad(problems)
    docs = [d for d in store.query(LINKS.name, [(k, "==", v) for k, v in filters.items()], limit=SCAN) if not _deleted(d)]
    if order == "valid_from":
        docs.sort(key=lambda d: (d.get("valid_from", ""), d.get("created_at", "")))
    else:
        docs.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    docs = docs[:max(1, min(limit, MAX_LIMIT))]
    return success({"records": docs, "count": len(docs)})


def update(store, id, changes, actor, expected_updated_at=None, tx=None, now=None):
    problems = check_actor(actor) + _id_problem(id)
    if expected_updated_at is not None and not (isinstance(expected_updated_at, str) and STAMP.match(expected_updated_at)):
        problems.append({"field": "expected_updated_at", "issue": "invalid_format"})
    if not isinstance(changes, dict) or not changes:
        problems.append({"field": "changes", "issue": "required"})
    if problems:
        return _bad(problems)
    sets, removals = {}, []
    for name, raw in changes.items():
        if name in IMMUTABLE:
            problems.append({"field": name, "issue": "immutable"})
        elif name not in LINKS.properties or name in LINKS.read_only:
            problems.append({"field": name, "issue": "not_allowed"})
        else:
            value = clean(raw)
            if value is None:
                (problems.append({"field": name, "issue": "required"}) if name in LINKS.required else removals.append(name))
            else:
                problems += check_field(LINKS, name, value)
                sets[name] = value
    if problems:
        return _bad(problems)
    cur = store.get(LINKS.name, id)
    if cur is None or _deleted(cur):
        return failure("not_found")
    if expected_updated_at is not None and cur.get("updated_at") != expected_updated_at:
        return failure("conflict")
    stamp = stamp_update(actor, now)
    try:
        store.update(LINKS.name, id, {**sets, **stamp}, removals, expected_updated_at=cur["updated_at"], tx=tx)
    except DocMissing:
        return failure("not_found")
    except StaleUpdate:
        return failure("conflict")
    return success({"id": id, "changed": sorted(sets), "removed": sorted(removals),
                    "updated_at": stamp["updated_at"], "updated_by": actor})


def soft_delete(store, id, actor, tx=None, now=None):
    problems = check_actor(actor) + _id_problem(id)
    if problems:
        return _bad(problems)
    cur = store.get(LINKS.name, id)
    if cur is None or _deleted(cur):
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
