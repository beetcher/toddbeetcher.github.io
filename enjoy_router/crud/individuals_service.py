"""Service for individuals: the rules that look at privacy and at other collections, on top of individuals_crud
(see venues_service.py and classes_service.py for the pattern).

    * a `sealed` record is invisible to everyone but an administrator: get, list, update and soft_delete answer
      `not_found`, so its existence is not revealed.
    * a `confidential` record is left out of lists for everyone but an administrator (get still returns it).
    * merge, unmerge and erase refuse (not_found) when a sealed record is involved and the caller is not an admin.
    * an individual that a live restricted-detail record points at cannot be soft-deleted (conflict, id:in_use).
      Other collections will add their own guards here when they gain an `individual_id`.

`as_admin` is False by default. The Console door has one shared key and no roles yet, so until Google sign-in
supplies roles, sealed records are unreachable through the endpoint on purpose (fail closed).
Same function names as a handler file, so the dispatcher treats both alike. All field checking stays in the handler file.
"""
from __future__ import annotations

from . import individual_merges_crud as M
from . import individuals_crud as I
from . import location_links_service as LINKS
from . import roster_links as ROSTER_LINKS
from .schema_kit import UUID_PATTERN, failure, load_collection, success

RESTRICTED = load_collection("individual_restricted_detail")


def _sealed(doc) -> bool:
    return bool(doc) and doc.get("record_privacy") == "sealed"


def create(store, data, actor, source="dashboard", tx=None, now=None):
    return I.create(store, data, actor, source, tx=tx, now=now)


def get(store, id, include_deleted=False, follow_merged=True, as_admin=False):
    r = I.get(store, id, include_deleted, follow_merged)
    if r.ok and _sealed(r.data) and not as_admin:
        return failure("not_found")
    return r


def list(store, filters=None, as_admin=False, **kw):  # noqa: A001
    r = I.list(store, filters, **kw)
    if not r.ok or as_admin:
        return r
    docs = [d for d in r.data["records"] if d.get("record_privacy") not in ("sealed", "confidential")]
    return success({"records": docs, "count": len(docs)})


def _hidden_from(store, id, as_admin) -> bool:
    if as_admin or not (isinstance(id, str) and UUID_PATTERN.match(id)):
        return False
    return _sealed(store.get(I.INDIVIDUALS.name, id))


def update(store, id, changes, actor, expected_updated_at=None, tx=None, now=None, as_admin=False):
    if _hidden_from(store, id, as_admin):
        return failure("not_found")
    return I.update(store, id, changes, actor, expected_updated_at, tx=tx, now=now)


def soft_delete(store, id, actor, tx=None, now=None, as_admin=False):
    if _hidden_from(store, id, as_admin):
        return failure("not_found")
    if isinstance(id, str) and UUID_PATTERN.match(id):
        live = [d for d in store.query(RESTRICTED.name, [("individual_id", "==", id)], limit=5) if "deleted_at" not in d]
        if live:
            return failure("conflict", [{"field": "id", "issue": "in_use"}])
    return I.soft_delete(store, id, actor, tx=tx, now=now)


def merge(store, survivor_id, duplicate_id, reason, actor, field_choices=None, tx=None, now=None, as_admin=False):
    if _hidden_from(store, survivor_id, as_admin) or _hidden_from(store, duplicate_id, as_admin):
        return failure("not_found")
    return M.merge(store, survivor_id, duplicate_id, reason, actor, field_choices, tx=tx, now=now)


def unmerge(store, id, actor, tx=None, now=None, as_admin=False):
    ev = store.get(M.MERGES.name, id) if isinstance(id, str) and UUID_PATTERN.match(id) else None
    if ev and (_hidden_from(store, ev["survivor_id"], as_admin) or _hidden_from(store, ev["duplicate_id"], as_admin)):
        return failure("not_found")
    return M.unmerge(store, id, actor, tx=tx, now=now)


def erase(store, id, actor, tx=None, now=None, as_admin=False):
    if _hidden_from(store, id, as_admin):
        return failure("not_found")

    def run(t):
        r = M.erase(store, id, actor, tx=t, now=now)
        if r.ok:  # the person's links go in the same write, and any location left with nobody linked is scrubbed
            r.data.update(LINKS.scrub_for_individual(store, id, actor, t, now=now))
            r.data.update(ROSTER_LINKS.scrub_for_individual(store, id, actor, t, now=now))
        return r

    if tx is not None:
        return run(tx)
    with store.transaction() as own:
        return run(own)
