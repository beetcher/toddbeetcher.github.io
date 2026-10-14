"""Service for organization links: the rules that look at other collections, on top of organization_links_crud.

    * the subject exists in the right collection and is live (individuals, organizations, venues); a merged individual
      is followed to the survivor and the link is made for the survivor; a sealed or erased individual is `not_found`
      unless `as_admin` (subject_id:not_found)
    * the organization exists and is not deleted (organization_id:not_found)
    * an organization is not linked to itself (organization_id:invalid_value)
Nothing else refuses a save (no overlap, loop, primary or word-fit rules). Update and delete need no cross-collection
check because the three ids never change. Same function names as a handler file.
"""
from __future__ import annotations

from . import individuals_crud as I
from . import organization_links_crud as H
from . import organizations_crud as O
from . import venues_crud as V
from .schema_kit import check_actor


def _subject_problems(store, doc, as_admin):
    """(problems, subject_id to use). Follows a merged individual to the survivor."""
    st, sid = doc["subject_type"], doc["subject_id"]
    if st == "individual":
        got = I.get(store, sid)
        if not got.ok or got.data.get("status") == "erased" or (got.data.get("record_privacy") == "sealed" and not as_admin):
            return [{"field": "subject_id", "issue": "not_found"}], sid
        return [], got.data["id"]
    got = O.get(store, sid) if st == "organization" else V.get(store, sid)
    return ([] if got.ok else [{"field": "subject_id", "issue": "not_found"}]), sid


def create(store, data, actor, source="dashboard", tx=None, now=None, as_admin=False):
    problems = check_actor(actor)
    if problems:
        return H._bad(problems)
    doc, problems = H.validate(data)
    if problems:
        return H._bad(problems)
    problems, sid = _subject_problems(store, doc, as_admin)
    if not O.get(store, doc["organization_id"]).ok:
        problems.append({"field": "organization_id", "issue": "not_found"})
    elif doc["subject_type"] == "organization" and doc["subject_id"] == doc["organization_id"]:
        problems.append({"field": "organization_id", "issue": "invalid_value"})
    if problems:
        return H._bad(problems)
    doc["subject_id"] = sid
    return H.create(store, doc, actor, source, tx=tx, now=now)


def get(store, id, include_deleted=False, as_admin=False):
    return H.get(store, id, include_deleted)


def list(store, filters=None, as_admin=False, **kw):  # noqa: A001
    return H.list(store, filters, **kw)


def update(store, id, changes, actor, expected_updated_at=None, tx=None, now=None, as_admin=False):
    return H.update(store, id, changes, actor, expected_updated_at=expected_updated_at, tx=tx, now=now)


def soft_delete(store, id, actor, tx=None, now=None, as_admin=False):
    return H.soft_delete(store, id, actor, tx=tx, now=now)
