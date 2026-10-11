"""Read-only service for merge events. A merge event is written only by the merge handler (individual_merges_crud) and
changed only by unmerge and erase, so create, update and soft_delete are refused here. Same function names as a handler
file, so the dispatcher treats it like one."""
from __future__ import annotations

from . import individual_merges_crud as M
from .schema_kit import failure


def get(store, id, include_deleted=False):
    return M.get_event(store, id)


def list(store, filters=None, **kw):  # noqa: A001
    return M.list_events(store, filters, **({"limit": kw["limit"]} if "limit" in kw else {}))


def _refuse(field):
    return failure("validation_failed", [{"field": field, "issue": "not_allowed"}])


def create(store, data, actor, source="dashboard", tx=None, now=None):
    return _refuse("body")


def update(store, id, changes, actor, expected_updated_at=None, tx=None, now=None):
    return _refuse("id")


def soft_delete(store, id, actor, tx=None, now=None):
    return _refuse("id")
