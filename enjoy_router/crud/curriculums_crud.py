"""CRUD handler for the `curriculums` collection (what is taught). Same shape as venues_crud.py, with no cross-field rules.

The only refusals: slug unique (soft-deleted records count), slug never changes, the schema's own types and limits.
Deleting is always allowed (Todd: no extra rules). list needs no index: one optional status filter, sorted here.
"""
from __future__ import annotations

import re

from .schema_kit import (
    UUID_PATTERN, check_actor, check_document, check_field, clean, drop_empty, failure,
    load_collection, stamp_create, stamp_update, success, utc_stamp,
)
from .store_errors import DocExists, DocMissing, StaleUpdate

CURRICULUMS = load_collection("curriculum")
SOURCES = ("dashboard", "import")
DEFAULT_LIMIT = 100
MAX_LIMIT = 200
SCAN = 500
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


def create(store, data, actor, source="dashboard", tx=None, now=None):
    problems = check_actor(actor)
    if source not in SOURCES:
        problems.append({"field": "source", "issue": "invalid_value"})
    if problems:
        return _bad(problems)
    if not isinstance(data, dict):
        return _bad([{"field": "body", "issue": "invalid_type"}])
    ro = [{"field": k, "issue": "not_allowed"} for k in data if k in CURRICULUMS.read_only]
    if ro:
        return _bad(ro)
    doc = drop_empty({k: clean(v) for k, v in data.items()})
    doc.setdefault("status", "active")
    problems = check_document(CURRICULUMS, doc)
    if problems:
        return _bad(problems)
    if store.query(CURRICULUMS.name, [("slug", "==", doc["slug"])], limit=1):  # includes soft-deleted
        return _bad([{"field": "slug", "issue": "duplicate"}])
    doc = stamp_create(CURRICULUMS, doc, actor, source, now)
    missing = [f for f in CURRICULUMS.server_required if f not in doc]
    if check_document(CURRICULUMS, doc) or missing:
        return failure("server_error")
    try:
        store.create(CURRICULUMS.name, doc["id"], doc, tx=tx)
    except DocExists:
        return failure("server_error")
    return success(doc)


def get(store, id, include_deleted=False):
    problems = _id_problem(id)
    if problems:
        return _bad(problems)
    doc = store.get(CURRICULUMS.name, id)
    if doc is None or (_deleted(doc) and not include_deleted):
        return failure("not_found")
    return success(doc)


def list(store, filters=None, order="title", limit=DEFAULT_LIMIT):  # noqa: A001
    """Optional ONE filter: status. Order title or -created_at. Removed curricula are left out."""
    filters = dict(filters or {})
    problems = []
    for k, v in filters.items():
        problems += [{"field": k, "issue": "not_supported"}] if k != "status" else check_field(CURRICULUMS, k, v)
    if order not in ("title", "-created_at"):
        problems.append({"field": "order", "issue": "not_supported"})
    if isinstance(limit, bool) or not isinstance(limit, int):
        problems.append({"field": "limit", "issue": "invalid_type"})
    if problems:
        return _bad(problems)
    docs = [d for d in store.query(CURRICULUMS.name, [(k, "==", v) for k, v in filters.items()], limit=SCAN) if not _deleted(d)]
    if order == "title":
        docs.sort(key=lambda d: (d.get("title", "").lower(), d.get("created_at", "")))
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
        if name == "slug":
            problems.append({"field": name, "issue": "immutable"})
        elif name not in CURRICULUMS.properties or name in CURRICULUMS.read_only:
            problems.append({"field": name, "issue": "not_allowed"})
        else:
            value = clean(raw)
            if value is None:
                (problems.append({"field": name, "issue": "required"}) if name in CURRICULUMS.required or name == "status"
                 else removals.append(name))
            else:
                problems += check_field(CURRICULUMS, name, value)
                sets[name] = value
    if problems:
        return _bad(problems)
    cur = store.get(CURRICULUMS.name, id)
    if cur is None or _deleted(cur):
        return failure("not_found")
    if expected_updated_at is not None and cur.get("updated_at") != expected_updated_at:
        return failure("conflict")
    stamp = stamp_update(actor, now)
    try:
        store.update(CURRICULUMS.name, id, {**sets, **stamp}, removals, expected_updated_at=cur["updated_at"], tx=tx)
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
    cur = store.get(CURRICULUMS.name, id)
    if cur is None or _deleted(cur):
        return failure("not_found")
    stamp = utc_stamp(now)
    try:
        store.update(CURRICULUMS.name, id, {"deleted_at": stamp, "deleted_by": actor, "updated_at": stamp, "updated_by": actor}, (),
                     expected_updated_at=cur["updated_at"], tx=tx)
    except DocMissing:
        return failure("not_found")
    except StaleUpdate:
        return failure("conflict")
    return success({"id": id, "deleted_at": stamp})
