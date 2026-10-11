"""Service for restricted individual details: the audit trail on top of individual_restricted_details_crud.

Every operation on a sensitive record leaves one log line with the operation, the record id and the code, never a
value and never a field name. (Reads are logged too: the schema says reads of restricted details are logged by id.)
The checks (purpose, consent or lawful basis, the individual exists, minors refused, one record per individual)
are in the handler file. Who may call this at all is decided by the endpoint: the Console door does not enable
this collection until the Console panel and sign-in roles exist; only the test door reaches it today.
Same function names as a handler file, so the dispatcher treats both alike.
"""
from __future__ import annotations

import logging

from . import individual_restricted_details_crud as R

log = logging.getLogger("enjoy_router")


def _audit(op: str, id, result):
    rid = id if isinstance(id, str) and len(id) <= 40 else "-"
    log.info("restricted_detail op=%s id=%s code=%s", op, rid, "ok" if result.ok else result.code)
    return result


def create(store, data, actor, source="dashboard", tx=None, now=None):
    r = R.create(store, data, actor, source, tx=tx, now=now)
    return _audit("create", r.data["id"] if r.ok else "-", r)


def get(store, id, include_deleted=False):
    return _audit("get", id, R.get(store, id, include_deleted))


def get_for_individual(store, individual_id):
    return _audit("get_for_individual", individual_id, R.get_for_individual(store, individual_id))


def list(store, filters=None, **kw):  # noqa: A001
    return _audit("list", "-", R.list(store, filters, **kw))


def update(store, id, changes, actor, expected_updated_at=None, tx=None, now=None):
    return _audit("update", id, R.update(store, id, changes, actor, expected_updated_at, tx=tx, now=now))


def soft_delete(store, id, actor, tx=None, now=None):
    return _audit("soft_delete", id, R.soft_delete(store, id, actor, tx=tx, now=now))
