"""Handler for `activity_events`: the append-only activity log (see ACTIVITY_EVENT_GUIDE.md).

Entries are written only by the ActivityStore (activity_store.py), in the same transaction as the change they record. Through the endpoints
only `get` and `list` work; `create`, `update` and `soft_delete` are refused, and only a super admin may read (access/policy.py). Same
function names as a handler file. `list` takes ONE filter and is ordered by sequence_ms, which needs a composite index per filter
(firestore.indexes.json).
"""
from __future__ import annotations

import builtins

from .activity_log import ACTIVITY
from .schema_kit import UUID_PATTERN, check_document, check_field, failure, success

DEFAULT_LIMIT = 100
MAX_LIMIT = 200
_LIST_FILTERS = ("related_ids", "record_type", "collection", "action", "created_by")


def _bad(problems):
    return failure("validation_failed", problems)


def check_entry(entry):
    """Problems (field names only) with a whole entry, as the schema sees it. Empty when it is a valid entry."""
    return check_document(ACTIVITY, entry)


def get(store, id, include_deleted=False, expand=False):  # noqa: A002
    if not (isinstance(id, str) and UUID_PATTERN.match(id)):
        return _bad([{"field": "id", "issue": "invalid_format"}])
    doc = store.get(ACTIVITY.name, id)
    return failure("not_found") if doc is None else success(doc)


def _filter_problem(field, value):
    if field == "related_ids":
        ok = isinstance(value, str) and 0 < len(value) <= 100
        return [] if ok else [{"field": field, "issue": "invalid_format"}]
    return check_field(ACTIVITY, field, value, allow_read_only=True)


def list(store, filters=None, order="-created_at", limit=DEFAULT_LIMIT, expand=False):  # noqa: A001
    """Optional ONE filter: related_ids (one id: every entry that mentions it), record_type, collection, action or created_by.
    Newest first (order -created_at) or oldest first (created_at); at most 200."""
    filters = dict(filters or {})
    problems = []
    for k, v in filters.items():
        problems += [{"field": k, "issue": "not_supported"}] if k not in _LIST_FILTERS else _filter_problem(k, v)
    if len(filters) > 1:
        problems += [{"field": k, "issue": "not_supported"} for k in filters]
    if order not in ("-created_at", "created_at"):
        problems.append({"field": "order", "issue": "not_supported"})
    if isinstance(limit, builtins.bool) or not isinstance(limit, builtins.int):
        problems.append({"field": "limit", "issue": "invalid_type"})
    if problems:
        return _bad(problems)
    descending = order.startswith("-")
    n = max(1, min(limit, MAX_LIMIT))
    q = [(k, "array_contains" if k == "related_ids" else "==", v) for k, v in filters.items()]
    docs = store.query(ACTIVITY.name, q, order_by="sequence_ms", descending=descending, limit=n)
    return success({"records": docs, "count": len(docs)})


def _refused(*_a, **_k):
    return failure("validation_failed", [{"field": "op", "issue": "not_supported"}])


create = update = soft_delete = _refused
