"""Service for locations: the guards that need the links, on top of locations_crud (see venues_service.py).

    * a location with a live link (active, not deleted) cannot be retired or soft-deleted (conflict, id:in_use)
    * create reports other live locations that already hold the same address as `address_matches`
      (ids only, not stored; the server never merges)
    * a residential location where a confidential or sealed person lives is invisible to everyone but an administrator
      until sign-in roles exist: get answers not_found and lists leave it out (fail closed, like those people). The
      check runs only for locations with is_residential true, one link query each.
Same function names as a handler file. All field checking stays in the handler file.
"""
from __future__ import annotations

from . import change_watch
from . import location_links_crud as LK
from . import location_links_service as LINKS
from . import locations_crud as L
from .schema_kit import UUID_PATTERN, failure, success


def _uuid(v) -> bool:
    return isinstance(v, str) and bool(UUID_PATTERN.match(v))


def live_links_at(store, location_id, limit=5):
    return [l for l in store.query(LK.LINKS.name, [("location_id", "==", location_id)], limit=100)
            if LK.is_live(l)][:limit]


def _hidden(store, doc, as_admin, cache=None) -> bool:
    if not doc or as_admin or not doc.get("is_residential"):
        return False
    cache = cache if cache is not None else {}
    for l in LK.live_for(store, "location_id", doc["id"]):
        if l["subject_type"] == "individual" and l["relationship"] == "resides_at" and LK.is_live(l) \
                and LINKS._private_individual(store, l["subject_id"], cache):
            return True
    return False


def create(store, data, actor, source="dashboard", tx=None, now=None, as_admin=False):
    r = L.create(store, data, actor, source, tx=tx, now=now)
    if not r.ok:
        return r
    matches = L.matches_for(store, r.data, exclude_id=r.data["id"])
    return success({**r.data, **({"address_matches": matches} if matches else {})})


def get(store, id, include_deleted=False, as_admin=False):
    r = L.get(store, id, include_deleted)
    return failure("not_found") if r.ok and _hidden(store, r.data, as_admin) else r


def list(store, filters=None, as_admin=False, **kw):  # noqa: A001
    r = L.list(store, filters, **kw)
    if not r.ok or as_admin:
        return r
    cache: dict = {}
    docs = [d for d in r.data["records"] if not _hidden(store, d, as_admin, cache)]
    return success({"records": docs, "count": len(docs)})


def update(store, id, changes, actor, expected_updated_at=None, tx=None, now=None, as_admin=False):
    cur = store.get(L.LOCATIONS.name, id) if _uuid(id) else None
    if _hidden(store, cur, as_admin):
        return failure("not_found")
    if cur is not None and isinstance(changes, dict) and changes.get("status") == "retired" and live_links_at(store, id, 1):
        return failure("conflict", [{"field": "id", "issue": "in_use"}])

    def check(merged):
        if merged.get("status") == "retired" and live_links_at(store, id, 1):
            return [{"field": "id", "issue": "in_use"}]
        return []

    watch = change_watch.location_watch(store, id) if tx is None and cur is not None else None     # an address or name edit reaches people in upcoming classes here
    r = L.update(store, id, changes, actor, expected_updated_at, tx=tx, now=now, check=check, check_fields=("status",))
    if watch is not None and r.ok:
        watch(actor, (r.data or {}).get("updated_at") or "")
    return r


def soft_delete(store, id, actor, tx=None, now=None, as_admin=False):
    if _uuid(id):
        cur = store.get(L.LOCATIONS.name, id)
        if _hidden(store, cur, as_admin):
            return failure("not_found")
        if live_links_at(store, id, 1):
            return failure("conflict", [{"field": "id", "issue": "in_use"}])
    return L.soft_delete(store, id, actor, tx=tx, now=now)


def find_by_address(store, address, as_admin=False, **kw):
    r = L.find_by_address(store, address, **kw)
    if not r.ok or as_admin:
        return r
    cache: dict = {}
    docs = [d for d in r.data["records"] if not _hidden(store, d, as_admin, cache)]
    return success({"records": docs, "count": len(docs)})
