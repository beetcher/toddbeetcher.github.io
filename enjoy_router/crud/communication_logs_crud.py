"""Handler for `communication_logs`: the append-only record of every message the CMS tried to send (see COMMUNICATION_LOG_GUIDE.md).

Entries are written only by the server (`record`, called by launch_comms.stores.LogStore). Through the endpoints only `get`, `list` and
`mark_handled` and `add_note` work; `create`, `update` and `soft_delete` are refused. list needs no index: one equality filter, sorted here.
"""
from __future__ import annotations

import re

from .schema_kit import (
    UUID_PATTERN, check_actor, check_document, check_field, clean, failure, load_collection, stamp_create, success, utc_stamp,
)
from .store_errors import DocMissing, StaleUpdate

LOG = load_collection("communication_log")
EXPANDABLE = False
DEFAULT_LIMIT = 100
MAX_LIMIT = 200
SCAN = 500
_LIST_FILTERS = ("individual_id", "request_id", "scheduled_class_id", "attendance_id", "status", "kind", "reason", "dedupe_key")
_FIELDS = tuple(f for f in LOG.properties if f not in LOG.read_only)
NOTE_MAX = 500
COMMENT_MAX = 1000
MAX_NOTES = 50


def _bad(problems):
    return failure("validation_failed", problems)


def record(store, entry, actor, tx=None, now=None, source="dashboard"):
    """Write one entry. Called by the CMS's log store. A problem here is our bug, so it says nothing about fields."""
    doc = {k: v for k, v in entry.items() if k in _FIELDS and v is not None}
    if check_document(LOG, doc):
        return failure("server_error")
    doc = stamp_create(LOG, doc, actor, source, now)
    store.create(LOG.name, doc["id"], doc, tx=tx)
    return success(doc)


def get(store, id, include_deleted=False):   # noqa: A002
    if not (isinstance(id, str) and UUID_PATTERN.match(id)):
        return _bad([{"field": "id", "issue": "invalid_format"}])
    doc = store.get(LOG.name, id)
    if doc is None or ("deleted_at" in doc and not include_deleted):
        return failure("not_found")
    return success(doc)


def list(store, filters=None, order="-created_at", limit=DEFAULT_LIMIT):   # noqa: A001
    """Optional ONE filter (individual_id, request_id, scheduled_class_id, attendance_id, status, kind, reason, dedupe_key). Order -created_at or created_at."""
    filters = dict(filters or {})
    problems = []
    for k, v in filters.items():
        problems += [{"field": k, "issue": "not_supported"}] if k not in _LIST_FILTERS else check_field(LOG, k, v)
    if len(filters) > 1:
        problems += [{"field": k, "issue": "not_supported"} for k in filters]
    if order not in ("-created_at", "created_at"):
        problems.append({"field": "order", "issue": "not_supported"})
    if isinstance(limit, bool) or not isinstance(limit, int):
        problems.append({"field": "limit", "issue": "invalid_type"})
    if problems:
        return _bad(problems)
    docs = [d for d in store.query(LOG.name, [(k, "==", v) for k, v in filters.items()], limit=SCAN) if "deleted_at" not in d]
    docs.sort(key=lambda d: (d.get("created_at", ""), d.get("id", "")), reverse=order.startswith("-"))
    docs = docs[:max(1, min(limit, MAX_LIMIT))]
    return success({"records": docs, "count": len(docs)})


def mark_handled(store, id, actor, note=None, tx=None, now=None):   # noqa: A002
    """An operator says a not_sent entry has been dealt with (for example, they phoned the person). Set once; nothing else changes."""
    problems = check_actor(actor)
    if not (isinstance(id, str) and UUID_PATTERN.match(id)):
        problems.append({"field": "id", "issue": "invalid_format"})
    note = clean(note) if note is not None else None
    if note is not None:
        problems += check_field(LOG, "handled_note", note, allow_read_only=True)
    if problems:
        return _bad(problems)
    cur = store.get(LOG.name, id)
    if cur is None or "deleted_at" in cur:
        return failure("not_found")
    if cur.get("status") != "not_sent":
        return _bad([{"field": "status", "issue": "not_allowed"}])
    if "handled_at" in cur:
        return failure("conflict")
    stamp = utc_stamp(now)
    sets = {"handled_at": stamp, "handled_by": actor, "updated_at": stamp, "updated_by": actor}
    if note:
        sets["handled_note"] = note
        notes = [*(cur.get("notes") or [])]
        if len(notes) < MAX_NOTES:   # the comment also reads as a note, so there is one place to look
            sets["notes"] = notes + [{"at": stamp, "by": actor, "text": "Handled: " + note}]
    try:
        store.update(LOG.name, id, sets, (), expected_updated_at=cur["updated_at"], tx=tx)
    except DocMissing:
        return failure("not_found")
    except StaleUpdate:
        return failure("conflict")
    return success({"id": id, "handled_at": stamp, "handled_by": actor})


def add_note(store, id, actor, text, tx=None, now=None):   # noqa: A002
    """An operator comments on an entry (any status) so the next person need not repeat the investigation. Add only: a note is never
    edited or removed. The facts of the entry do not change."""
    problems = check_actor(actor)
    if not (isinstance(id, str) and UUID_PATTERN.match(id)):
        problems.append({"field": "id", "issue": "invalid_format"})
    text = clean(text) if isinstance(text, str) else text
    if not isinstance(text, str) or not text:
        problems.append({"field": "text", "issue": "required"})
    elif len(text) > COMMENT_MAX:
        problems.append({"field": "text", "issue": "too_long"})
    if problems:
        return _bad(problems)
    cur = store.get(LOG.name, id)
    if cur is None or "deleted_at" in cur:
        return failure("not_found")
    notes = [*(cur.get("notes") or [])]
    if len(notes) >= MAX_NOTES:
        return _bad([{"field": "notes", "issue": "too_many"}])
    stamp = utc_stamp(now)
    notes.append({"at": stamp, "by": actor, "text": text})
    if check_field(LOG, "notes", notes, allow_read_only=True):
        return failure("server_error")
    try:
        store.update(LOG.name, id, {"notes": notes, "updated_at": stamp, "updated_by": actor}, (), expected_updated_at=cur["updated_at"], tx=tx)
    except DocMissing:
        return failure("not_found")
    except StaleUpdate:
        return failure("conflict")
    return success({"id": id, "notes": notes})


def _refused(*_a, **_k):
    return failure("validation_failed", [{"field": "op", "issue": "not_supported"}])


create = update = soft_delete = _refused
