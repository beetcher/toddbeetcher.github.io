"""Shared pieces for the Discovery collection handlers (discovery_model, _area, _type, _setting; the prompt and run handlers use
the helpers). Each collection keeps its own handler module with its own rules; this file only holds what they would repeat.

`make(type_name, ...)` builds the standard five operations from per-collection rules:
    defaults      values set on create when the sender gave none
    immutable     fields that cannot change after create (reported as `immutable`)
    tidy(name, v) trims one sender value (None = leave the field out)
    rules(store, doc, current)   cross-record rules on the whole record about to be saved; returns problems
    delete_rules(store, cur)     problems that block deleting
    order         default list order field
    filters       fields the list may filter on
Never raises for bad input; returns Result objects like every handler.
"""
from __future__ import annotations

import re
from types import SimpleNamespace

from .schema_kit import (UUID_PATTERN, check_actor, check_document, check_field, clean, drop_empty, failure, load_collection,
                         stamp_create, stamp_update, success, utc_stamp)
from .store_errors import DocExists, DocMissing, StaleUpdate

SOURCES = ("dashboard", "import")
DEFAULT_LIMIT = 100
MAX_LIMIT = 200
SCAN = 500
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def bad(problems):
    seen, out = set(), []
    for p in problems:
        k = (p["field"], p["issue"])
        if k not in seen:
            seen.add(k)
            out.append(p)
    return failure("validation_failed", out)


def id_problem(id):   # noqa: A002
    return [] if isinstance(id, str) and UUID_PATTERN.match(id) else [{"field": "id", "issue": "invalid_format"}]


def live(store, coll, **match):
    wanted = [(k, "==", v) for k, v in match.items()]
    return [d for d in store.query(coll.name, wanted, limit=SCAN) if "deleted_at" not in d]


def make(type_name, *, defaults=None, immutable=(), tidy=None, rules=None, delete_rules=None, order="created_at", filters=()):
    C = load_collection(type_name)
    defaults = dict(defaults or {})
    tidy = tidy or (lambda name, value: value)
    default_order, allowed = order, tuple(filters)

    def create(store, data, actor, source="dashboard", tx=None, now=None):
        problems = check_actor(actor)
        if source not in SOURCES:
            problems.append({"field": "source", "issue": "invalid_value"})
        if problems:
            return bad(problems)
        if not isinstance(data, dict):
            return bad([{"field": "body", "issue": "invalid_type"}])
        ro = [{"field": k, "issue": "not_allowed"} for k in data if k in C.read_only]
        if ro:
            return bad(ro)
        doc = {**defaults, **drop_empty({k: tidy(k, clean(v)) for k, v in data.items()})}
        problems = check_document(C, doc)
        if not problems and rules:
            problems = rules(store, doc, None)
        if problems:
            return bad(problems)
        doc = stamp_create(C, doc, actor, source, now)
        if check_document(C, doc) or [f for f in C.server_required if f not in doc]:
            return failure("server_error")
        try:
            store.create(C.name, doc["id"], doc, tx=tx)
        except DocExists:
            return failure("server_error")
        return success(doc)

    def get(store, id, include_deleted=False):   # noqa: A002
        problems = id_problem(id)
        if problems:
            return bad(problems)
        doc = store.get(C.name, id)
        if doc is None or ("deleted_at" in doc and not include_deleted):
            return failure("not_found")
        return success(doc)

    def list_(store, filters=None, order=None, limit=DEFAULT_LIMIT):
        flt, problems = dict(filters or {}), []
        for k, v in flt.items():
            problems += [{"field": k, "issue": "not_supported"}] if k not in allowed else check_field(C, k, v, allow_read_only=True)
        o = order or default_order
        if o.lstrip("-") not in C.properties:
            problems.append({"field": "order", "issue": "not_supported"})
        if isinstance(limit, bool) or not isinstance(limit, int):
            problems.append({"field": "limit", "issue": "invalid_type"})
        if problems:
            return bad(problems)
        docs = [d for d in store.query(C.name, [(k, "==", v) for k, v in flt.items()], limit=SCAN) if "deleted_at" not in d]
        docs.sort(key=lambda d: (str(d.get(o.lstrip("-"), "")).lower(), d.get("created_at", "")), reverse=o.startswith("-"))
        docs = docs[:max(1, min(limit, MAX_LIMIT))]
        return success({"records": docs, "count": len(docs)})

    def update(store, id, changes, actor, expected_updated_at=None, tx=None, now=None):   # noqa: A002
        problems = check_actor(actor) + id_problem(id)
        if expected_updated_at is not None and not (isinstance(expected_updated_at, str) and STAMP.match(expected_updated_at)):
            problems.append({"field": "expected_updated_at", "issue": "invalid_format"})
        if not isinstance(changes, dict) or not changes:
            problems.append({"field": "changes", "issue": "required"})
        if problems:
            return bad(problems)
        sets, removals = {}, []
        for name, raw in changes.items():
            if name in immutable:
                problems.append({"field": name, "issue": "immutable"})
            elif name not in C.properties or name in C.read_only:
                problems.append({"field": name, "issue": "not_allowed"})
            else:
                value = tidy(name, clean(raw))
                if value is None:
                    (problems.append({"field": name, "issue": "required"}) if name in C.required else removals.append(name))
                else:
                    problems += check_field(C, name, value)
                    sets[name] = value
        if problems:
            return bad(problems)
        cur = store.get(C.name, id)
        if cur is None or "deleted_at" in cur:
            return failure("not_found")
        merged = {**cur, **sets}
        for r in removals:
            merged.pop(r, None)
        problems = check_document(C, merged)
        if not problems and rules:
            problems = rules(store, merged, cur)
        if problems:
            return bad(problems)
        if expected_updated_at is not None and cur.get("updated_at") != expected_updated_at:
            return failure("conflict")
        stamp = stamp_update(actor, now)
        try:
            store.update(C.name, id, {**sets, **stamp}, removals, expected_updated_at=cur["updated_at"], tx=tx)
        except DocMissing:
            return failure("not_found")
        except StaleUpdate:
            return failure("conflict")
        return success({"id": id, "changed": sorted(sets), "removed": sorted(removals), "updated_at": stamp["updated_at"],
                        "updated_by": actor})

    def soft_delete(store, id, actor, tx=None, now=None):   # noqa: A002
        problems = check_actor(actor) + id_problem(id)
        if problems:
            return bad(problems)
        cur = store.get(C.name, id)
        if cur is None or "deleted_at" in cur:
            return failure("not_found")
        problems = delete_rules(store, cur) if delete_rules else []
        if problems:
            return bad(problems)
        stamp = utc_stamp(now)
        try:
            store.update(C.name, id, {"deleted_at": stamp, "deleted_by": actor, "updated_at": stamp, "updated_by": actor}, (),
                         expected_updated_at=cur["updated_at"], tx=tx)
        except DocMissing:
            return failure("not_found")
        except StaleUpdate:
            return failure("conflict")
        return success({"id": id, "deleted_at": stamp})

    return SimpleNamespace(COLLECTION=C, create=create, get=get, list=list_, update=update, soft_delete=soft_delete)
