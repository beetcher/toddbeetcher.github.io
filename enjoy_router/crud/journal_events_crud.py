"""Handler for `journal_events`: the append-only log of who did what to a person's place in a class (see JOURNAL_EVENT_GUIDE.md).

Entries are written only by the server, inside the same transaction as the change they record (`record`). Through the endpoints only
`get` and `list` work; `create`, `update` and `soft_delete` are refused. The journal is provenance, never truth. Same function names as
a handler file, plus EXPANDABLE. list needs no index: one equality filter, sorted here.
"""
from __future__ import annotations

import builtins

from . import individuals_service as IS
from . import instructor_rosters_service as INS
from . import scheduled_classes_crud as CL
from .schema_kit import UUID_PATTERN, check_document, check_field, failure, load_collection, stamp_create, success

JOURNAL = load_collection("journal_event")
EXPANDABLE = True
DEFAULT_LIMIT = 100
MAX_LIMIT = 200
SCAN = 500
_LIST_FILTERS = ("request_id", "scheduled_class_id", "individual_id", "attendance_id")
_FIELDS = tuple(f for f in JOURNAL.properties if f not in JOURNAL.read_only)


def _bad(problems):
    return failure("validation_failed", problems)


# Same-second events: the cause comes before its consequence (request_unassigned last).
_RANK = {"placed": 0, "status_changed": 1, "removed": 1, "class_cancelled": 1, "class_removed": 1, "request_unassigned": 2}


def record(store, entry, actor, tx=None, now=None, source="dashboard"):
    """Write one entry. Called by the services, in their transaction. A problem here is our bug, so it says nothing about fields."""
    doc = {k: v for k, v in entry.items() if k in _FIELDS and v is not None}
    if check_document(JOURNAL, doc):
        return failure("server_error")
    doc = stamp_create(JOURNAL, doc, actor, source, now)
    store.create(JOURNAL.name, doc["id"], doc, tx=tx)
    return success(doc)


def expanded(store, rec):
    out = dict(rec)
    if rec.get("individual_id"):
        out["person"] = INS.R._person_view(store, rec["individual_id"])
    if rec.get("scheduled_class_id"):
        c = store.get(CL.CLASSES.name, rec["scheduled_class_id"])
        if c is not None and "deleted_at" not in c:
            out["class"] = {k: c[k] for k in ("id", "title", "starts_at", "time_zone", "status") if k in c}
        else:
            out["class"] = {"id": rec["scheduled_class_id"], "unavailable": True}
    return out


def get(store, id, include_deleted=False, expand=False):  # noqa: A002
    if not (isinstance(id, str) and UUID_PATTERN.match(id)):
        return _bad([{"field": "id", "issue": "invalid_format"}])
    doc = store.get(JOURNAL.name, id)
    if doc is None or ("deleted_at" in doc and not include_deleted):
        return failure("not_found")
    return success(expanded(store, doc) if expand else doc)


def list(store, filters=None, order="-created_at", limit=DEFAULT_LIMIT, expand=False):  # noqa: A001
    """Optional ONE filter: request_id, scheduled_class_id, individual_id or attendance_id. Order -created_at or created_at."""
    filters = dict(filters or {})
    problems = []
    for k, v in filters.items():
        problems += [{"field": k, "issue": "not_supported"}] if k not in _LIST_FILTERS else check_field(JOURNAL, k, v)
    if len(filters) > 1:
        problems += [{"field": k, "issue": "not_supported"} for k in filters]
    if order not in ("-created_at", "created_at"):
        problems.append({"field": "order", "issue": "not_supported"})
    if isinstance(limit, bool) or not isinstance(limit, int):
        problems.append({"field": "limit", "issue": "invalid_type"})
    if problems:
        return _bad(problems)
    docs = [d for d in store.query(JOURNAL.name, [(k, "==", v) for k, v in filters.items()], limit=SCAN) if "deleted_at" not in d]
    docs.sort(key=lambda d: (d.get("created_at", ""), _RANK.get(d.get("event_type"), 1), d.get("id", "")), reverse=order.startswith("-"))
    docs = docs[:max(1, min(limit, MAX_LIMIT))]
    if expand:
        docs = [expanded(store, d) for d in docs]
    return success({"records": docs, "count": len(docs)})


def _refused(*_a, **_k):
    return failure("validation_failed", [{"field": "op", "issue": "not_supported"}])


create = update = soft_delete = _refused
