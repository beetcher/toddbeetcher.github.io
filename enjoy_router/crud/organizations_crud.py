"""CRUD handler for the `organizations` collection (who an organization is: name, kinds, contact, identifiers).
Same shape as curriculums_crud.py. No cross-field rules and no other collection is read (links come in a later slice).

Tidying done here: strings trimmed, blank aliases and blank identifier descriptions dropped, email lowercased, phone spaces collapsed.
Refused: any server-set field, and a sender setting status to `merged` (only a future merge step may). Deleting is always allowed.
list needs no index: one optional status filter, sorted by name here.
"""
from __future__ import annotations

import re

from .schema_kit import (
    UUID_PATTERN, check_actor, check_document, check_field, clean, drop_empty, failure,
    load_collection, stamp_create, stamp_update, success, utc_stamp,
)
from .store_errors import DocExists, DocMissing, StaleUpdate

ORGANIZATIONS = load_collection("organization")
SOURCES = ("dashboard", "import")
DEFAULT_LIMIT = 100
MAX_LIMIT = 200
SCAN = 500
_LIST = type([])  # `list` is this module's own function
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


def _tidy(name, value):
    """Trim and normalize one sender value. None means: leave the field out."""
    value = clean(value)
    if name == "aliases" and isinstance(value, _LIST):
        value = [a for a in value if a is not None] or None
    elif name == "identifiers" and isinstance(value, _LIST):
        value = [drop_empty(i) if isinstance(i, dict) else i for i in value] or None
    elif name == "kinds" and isinstance(value, _LIST):
        value = value or None
    elif name == "email" and isinstance(value, str):
        value = value.lower()
    elif name == "phone" and isinstance(value, str):
        value = re.sub(r"\s+", " ", value)
    return value


def _merged(name, value):
    return name == "status" and value == "merged"


def create(store, data, actor, source="dashboard", tx=None, now=None):
    problems = check_actor(actor)
    if source not in SOURCES:
        problems.append({"field": "source", "issue": "invalid_value"})
    if problems:
        return _bad(problems)
    if not isinstance(data, dict):
        return _bad([{"field": "body", "issue": "invalid_type"}])
    ro = [{"field": k, "issue": "not_allowed"} for k in data if k in ORGANIZATIONS.read_only]
    ro += [{"field": "status", "issue": "not_allowed"} for k, v in data.items() if _merged(k, v)]
    if ro:
        return _bad(ro)
    doc = drop_empty({k: _tidy(k, v) for k, v in data.items()})
    doc.setdefault("status", "active")
    problems = check_document(ORGANIZATIONS, doc)
    if problems:
        return _bad(problems)
    doc = stamp_create(ORGANIZATIONS, doc, actor, source, now)
    missing = [f for f in ORGANIZATIONS.server_required if f not in doc]
    if check_document(ORGANIZATIONS, doc) or missing:
        return failure("server_error")
    try:
        store.create(ORGANIZATIONS.name, doc["id"], doc, tx=tx)
    except DocExists:
        return failure("server_error")
    return success(doc)


def get(store, id, include_deleted=False):
    problems = _id_problem(id)
    if problems:
        return _bad(problems)
    doc = store.get(ORGANIZATIONS.name, id)
    if doc is None or (_deleted(doc) and not include_deleted):
        return failure("not_found")
    return success(doc)


def list(store, filters=None, order="name", limit=DEFAULT_LIMIT):  # noqa: A001
    """Optional ONE filter: status. Order name or -created_at. Removed organizations are left out."""
    filters = dict(filters or {})
    problems = []
    for k, v in filters.items():
        problems += [{"field": k, "issue": "not_supported"}] if k != "status" else check_field(ORGANIZATIONS, k, v)
    if order not in ("name", "-created_at"):
        problems.append({"field": "order", "issue": "not_supported"})
    if isinstance(limit, bool) or not isinstance(limit, int):
        problems.append({"field": "limit", "issue": "invalid_type"})
    if problems:
        return _bad(problems)
    docs = [d for d in store.query(ORGANIZATIONS.name, [(k, "==", v) for k, v in filters.items()], limit=SCAN) if not _deleted(d)]
    if order == "name":
        docs.sort(key=lambda d: (d.get("name", "").lower(), d.get("created_at", "")))
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
        if name not in ORGANIZATIONS.properties or name in ORGANIZATIONS.read_only or _merged(name, raw):
            problems.append({"field": name, "issue": "not_allowed"})
        else:
            value = _tidy(name, raw)
            if value is None:
                (problems.append({"field": name, "issue": "required"}) if name in ORGANIZATIONS.required or name == "status"
                 else removals.append(name))
            else:
                problems += check_field(ORGANIZATIONS, name, value)
                sets[name] = value
    if problems:
        return _bad(problems)
    cur = store.get(ORGANIZATIONS.name, id)
    if cur is None or _deleted(cur):
        return failure("not_found")
    if expected_updated_at is not None and cur.get("updated_at") != expected_updated_at:
        return failure("conflict")
    stamp = stamp_update(actor, now)
    try:
        store.update(ORGANIZATIONS.name, id, {**sets, **stamp}, removals, expected_updated_at=cur["updated_at"], tx=tx)
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
    cur = store.get(ORGANIZATIONS.name, id)
    if cur is None or _deleted(cur):
        return failure("not_found")
    stamp = utc_stamp(now)
    try:
        store.update(ORGANIZATIONS.name, id, {"deleted_at": stamp, "deleted_by": actor, "updated_at": stamp, "updated_by": actor}, (),
                     expected_updated_at=cur["updated_at"], tx=tx)
    except DocMissing:
        return failure("not_found")
    except StaleUpdate:
        return failure("conflict")
    return success({"id": id, "deleted_at": stamp})
