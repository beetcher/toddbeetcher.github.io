"""Handler for `comms_settings`: the ONE record of CMS settings (see COMMS_SETTING_GUIDE.md).

`create` makes the record with the Launch defaults when none exists and refuses a second. `update` changes it in place. `soft_delete` is
refused. `is_text_on` cannot be turned on until a text channel exists. `from_address` and `reply_to` are trimmed and lowercased.
"""
from __future__ import annotations

import re

from .schema_kit import (
    UUID_PATTERN, check_actor, check_document, check_field, clean, drop_empty, failure,
    load_collection, stamp_create, stamp_update, success,
)
from .store_errors import DocExists, DocMissing, StaleUpdate

SETTINGS = load_collection("comms_setting")
SOURCES = ("dashboard", "import")
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
DEFAULTS = {"settings_key": "default", "sender_name": "Launch", "is_email_on": True, "is_text_on": False}
LOWER = ("from_address", "reply_to", "test_redirect_address")


def _bad(problems):
    seen, out = set(), []
    for p in problems:
        k = (p["field"], p["issue"])
        if k not in seen:
            seen.add(k)
            out.append(p)
    return failure("validation_failed", out)


def _tidy(name, value):
    return value.strip().lower() if name in LOWER and isinstance(value, str) else value


def _all(store):
    return [d for d in store.query(SETTINGS.name, [], limit=10) if "deleted_at" not in d]


def create(store, data, actor, source="dashboard", tx=None, now=None):
    problems = check_actor(actor)
    if source not in SOURCES:
        problems.append({"field": "source", "issue": "invalid_value"})
    if not isinstance(data, dict):
        problems.append({"field": "body", "issue": "invalid_type"})
    if problems:
        return _bad(problems)
    problems = [{"field": k, "issue": "not_allowed"} for k in data if k in SETTINGS.read_only]
    if problems:
        return _bad(problems)
    doc = {**DEFAULTS, **drop_empty({k: _tidy(k, clean(v)) for k, v in data.items()})}
    if doc.get("is_text_on") is True:
        problems.append({"field": "is_text_on", "issue": "invalid_value"})
    problems += check_document(SETTINGS, doc)
    if problems:
        return _bad(problems)
    if store.query(SETTINGS.name, [], limit=1):     # includes any record at all: exactly one exists
        return _bad([{"field": "settings_key", "issue": "duplicate"}])
    doc = stamp_create(SETTINGS, doc, actor, source, now)
    if check_document(SETTINGS, doc) or [f for f in SETTINGS.server_required if f not in doc]:
        return failure("server_error")
    try:
        store.create(SETTINGS.name, doc["id"], doc, tx=tx)
    except DocExists:
        return failure("server_error")
    return success(doc)


def get(store, id, include_deleted=False):   # noqa: A002
    if not (isinstance(id, str) and UUID_PATTERN.match(id)):
        return _bad([{"field": "id", "issue": "invalid_format"}])
    doc = store.get(SETTINGS.name, id)
    if doc is None or ("deleted_at" in doc and not include_deleted):
        return failure("not_found")
    return success(doc)


def list(store, filters=None, order=None, limit=10):   # noqa: A001
    """No filters. Returns the one record, or none when it has not been created yet (the Console then calls create)."""
    if filters:
        return _bad([{"field": k, "issue": "not_supported"} for k in filters])
    docs = _all(store)
    return success({"records": docs, "count": len(docs)})


def update(store, id, changes, actor, expected_updated_at=None, tx=None, now=None):   # noqa: A002
    problems = check_actor(actor)
    if not (isinstance(id, str) and UUID_PATTERN.match(id)):
        problems.append({"field": "id", "issue": "invalid_format"})
    if expected_updated_at is not None and not (isinstance(expected_updated_at, str) and STAMP.match(expected_updated_at)):
        problems.append({"field": "expected_updated_at", "issue": "invalid_format"})
    if not isinstance(changes, dict) or not changes:
        problems.append({"field": "changes", "issue": "required"})
    if problems:
        return _bad(problems)
    sets, removals = {}, []
    for name, raw in changes.items():
        if name == "settings_key":
            problems.append({"field": name, "issue": "immutable"})
        elif name not in SETTINGS.properties or name in SETTINGS.read_only:
            problems.append({"field": name, "issue": "not_allowed"})
        else:
            value = _tidy(name, clean(raw))
            if value is None:
                (problems.append({"field": name, "issue": "required"}) if name in SETTINGS.required else removals.append(name))
            else:
                problems += check_field(SETTINGS, name, value)
                sets[name] = value
    if sets.get("is_text_on") is True:
        problems.append({"field": "is_text_on", "issue": "invalid_value"})
    if problems:
        return _bad(problems)
    cur = store.get(SETTINGS.name, id)
    if cur is None or "deleted_at" in cur:
        return failure("not_found")
    if expected_updated_at is not None and cur.get("updated_at") != expected_updated_at:
        return failure("conflict")
    stamp = stamp_update(actor, now)
    try:
        store.update(SETTINGS.name, id, {**sets, **stamp}, removals, expected_updated_at=cur["updated_at"], tx=tx)
    except DocMissing:
        return failure("not_found")
    except StaleUpdate:
        return failure("conflict")
    return success({"id": id, "changed": sorted(sets), "removed": sorted(removals), "updated_at": stamp["updated_at"], "updated_by": actor})


def _refused(*_a, **_k):
    return failure("validation_failed", [{"field": "op", "issue": "not_supported"}])


soft_delete = _refused
