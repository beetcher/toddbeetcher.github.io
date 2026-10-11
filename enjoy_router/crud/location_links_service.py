"""Service for location links: the rules that look at other collections, on top of location_links_crud.

    * the subject exists in the right collection and is live (individuals, venues); a merged individual is followed to
      the survivor and the link is made for the survivor; a sealed individual is `not_found` unless `as_admin`
    * subject_type organization is reserved (subject_type:not_supported) until organizations have a schema
    * resides_at needs an individual, operates_at needs a venue (relationship:invalid_value)
    * the location exists, is not deleted and is active (location_id:not_found, location_id:retired)
    * no two live links with the same subject, location and relationship overlap in time (location_id:duplicate)
    * one primary per subject and relationship among active links: making one primary demotes the other in the same
      write (the reply carries `demoted_link_ids`)
    * the location's is_residential follows its active resides_at links, written in the same transaction
    * residence links of confidential or sealed people are left out of lists and `get` unless `as_admin`
Same function names as a handler file, plus `end` and `scrub_for_individual` (used by erase).
"""
from __future__ import annotations

import builtins
from datetime import datetime, timezone

from . import individuals_crud as I
from . import location_links_crud as H
from . import locations_crud as LOC
from . import venues_crud as V
from .schema_kit import UUID_PATTERN, check_actor, failure, stamp_update, success

RESIDENCE = "resides_at"
FIT = {"resides_at": "individual", "operates_at": "venue"}


def _uuid(v) -> bool:
    return isinstance(v, str) and bool(UUID_PATTERN.match(v))


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _private_individual(store, subject_id, cache) -> bool:
    if subject_id not in cache:
        d = store.get(I.INDIVIDUALS.name, subject_id)
        cache[subject_id] = bool(d) and d.get("record_privacy") in ("sealed", "confidential")
    return cache[subject_id]


def _sealed_individual(store, subject_id) -> bool:
    d = store.get(I.INDIVIDUALS.name, subject_id)
    return bool(d) and d.get("record_privacy") == "sealed"


def _subject_problems(store, doc, as_admin):
    """(problems, subject_id to use). Follows a merged individual to the survivor."""
    st, sid = doc["subject_type"], doc["subject_id"]
    if st == "organization":
        return [{"field": "subject_type", "issue": "not_supported"}], sid
    if st == "individual":
        got = I.get(store, sid)
        if not got.ok or got.data.get("status") == "erased" or (got.data.get("record_privacy") == "sealed" and not as_admin):
            return [{"field": "subject_id", "issue": "not_found"}], sid
        return [], got.data["id"]
    got = V.get(store, sid)
    return ([] if got.ok else [{"field": "subject_id", "issue": "not_found"}]), sid


def _fit_problems(doc):
    need = FIT.get(doc["relationship"])
    return [{"field": "relationship", "issue": "invalid_value"}] if need and need != doc["subject_type"] else []


def _location_problems(store, location_id):
    loc = store.get(LOC.LOCATIONS.name, location_id)
    if loc is None or "deleted_at" in loc:
        return [{"field": "location_id", "issue": "not_found"}], None
    if loc.get("status") != "active":
        return [{"field": "location_id", "issue": "retired"}], loc
    return [], loc


def _overlap_problems(store, doc, exclude_id=None):
    for l in H.live_for(store, "subject_id", doc["subject_id"]):
        if (l["id"] != exclude_id and l["location_id"] == doc["location_id"] and l["relationship"] == doc["relationship"]
                and H.overlaps(l, doc)):
            return [{"field": "location_id", "issue": "duplicate"}]
    return []


def _primaries_to_demote(store, doc, exclude_id=None) -> builtins.list:
    if not (doc.get("is_primary") and doc.get("status", H._status_for(doc)) == "active"):
        return []
    return [l["id"] for l in H.live_for(store, "subject_id", doc["subject_id"])
            if l["id"] != exclude_id and l["relationship"] == doc["relationship"] and l.get("is_primary") and H.is_live(l)]


def _residential_after(store, location_id, changed_doc, changed_id, deleted=False) -> bool:
    """Would the location have an active residence link once `changed_doc` (id `changed_id`) is written?"""
    for l in H.live_for(store, "location_id", location_id):
        if l["id"] == changed_id:
            continue
        if l["relationship"] == RESIDENCE and H.is_live(l):
            return True
    return bool(changed_doc and not deleted and changed_doc["relationship"] == RESIDENCE and changed_doc.get("status") == "active")


def _sync_residential(store, loc, now_flag, actor, tx, now):
    if loc is not None and bool(loc.get("is_residential")) != now_flag:
        LOC.set_residential(store, loc["id"], now_flag, actor="system:location_links", tx=tx, now=now)


def _in_tx(store, tx, fn):
    if tx is not None:
        return fn(tx)
    with store.transaction() as own:
        return fn(own)


# =============================================================================
# create / get / list
# =============================================================================

def create(store, data, actor, source="dashboard", tx=None, now=None, as_admin=False):
    problems = check_actor(actor)
    if problems:
        return H._bad(problems)
    doc, problems = H.validate(data)
    if problems:
        return H._bad(problems)
    sp, sid = _subject_problems(store, doc, as_admin)
    problems = sp + _fit_problems(doc)
    lp, loc = _location_problems(store, doc["location_id"])
    problems += lp
    if problems:
        return H._bad(problems)
    doc["subject_id"] = sid
    doc["status"] = H._status_for(doc)
    problems = H.validate({k: v for k, v in doc.items() if k != "status"})[1] or _overlap_problems(store, doc)
    if problems:
        return H._bad(problems)
    demote = _primaries_to_demote(store, doc)
    residential = _residential_after(store, doc["location_id"], doc, None)

    out: dict = {}

    def write(t):
        r = H.create(store, {k: v for k, v in doc.items() if k != "status"}, actor, source, tx=t, now=now)
        if not r.ok:
            return r
        for other in demote:
            H.set_primary(store, other, False, "system:location_links", tx=t, now=now)
        _sync_residential(store, loc, residential, actor, t, now)
        out["doc"] = r.data
        return r

    r = _in_tx(store, tx, write)
    if not r.ok:
        return r
    return success({**out["doc"], **({"demoted_link_ids": demote} if demote else {})})


def get(store, id, include_deleted=False, as_admin=False):
    r = H.get(store, id, include_deleted)
    if r.ok and not as_admin and r.data["subject_type"] == "individual" and r.data["relationship"] == RESIDENCE \
            and _private_individual(store, r.data["subject_id"], {}):
        return failure("not_found")
    return r


def list(store, filters=None, as_admin=False, **kw):  # noqa: A001
    r = H.list(store, filters, **kw)
    if not r.ok or as_admin:
        return r
    cache: dict = {}
    docs = [d for d in r.data["records"]
            if not (d["subject_type"] == "individual" and d["relationship"] == RESIDENCE and _private_individual(store, d["subject_id"], cache))]
    return success({"records": docs, "count": len(docs)})


# =============================================================================
# update / end / soft delete
# =============================================================================

def update(store, id, changes, actor, expected_updated_at=None, tx=None, now=None, as_admin=False):
    if not (isinstance(id, str) and _uuid(id)):
        return H.update(store, id, changes, actor, expected_updated_at, tx=tx, now=now)
    cur = store.get(H.LINKS.name, id)
    if cur is None or "deleted_at" in cur:
        return failure("not_found")
    if not as_admin and cur["subject_type"] == "individual" and _sealed_individual(store, cur["subject_id"]):
        return failure("not_found")
    box: dict = {}

    def check(merged):
        merged = {**merged, "status": H._status_for(merged)}
        problems = _overlap_problems(store, merged, exclude_id=id)
        if not problems:
            box["demote"] = _primaries_to_demote(store, merged, exclude_id=id)
            box["merged"] = merged
        return problems

    def write(t):
        r = H.update(store, id, changes, actor, expected_updated_at, tx=t, now=now, check=check)
        if not r.ok:
            return r
        merged = box["merged"]
        for other in box["demote"]:
            H.set_primary(store, other, False, "system:location_links", tx=t, now=now)
        loc = store.get(LOC.LOCATIONS.name, cur["location_id"])
        if loc is not None and "deleted_at" not in loc:
            _sync_residential(store, loc, _residential_after(store, cur["location_id"], merged, id), actor, t, now)
        return r

    r = _in_tx(store, tx, write)
    if r.ok and box.get("demote"):
        r = success({**r.data, "demoted_link_ids": box["demote"]})
    return r


def end(store, id, actor, valid_to=None, expected_updated_at=None, tx=None, now=None, as_admin=False):
    """Set valid_to (default today) so the link stops applying. Ending an already ended link is `conflict`."""
    if _uuid(id):
        cur = store.get(H.LINKS.name, id)
        if cur is not None and "deleted_at" not in cur and cur.get("status") == "ended":
            return failure("conflict", [{"field": "valid_to", "issue": "already_ended"}])
    return update(store, id, {"valid_to": valid_to or _today()}, actor, expected_updated_at, tx=tx, now=now, as_admin=as_admin)


def soft_delete(store, id, actor, tx=None, now=None, as_admin=False):
    problems = check_actor(actor)
    if problems or not _uuid(id):
        return H.soft_delete(store, id, actor, tx=tx, now=now)
    cur = store.get(H.LINKS.name, id)
    if cur is None or "deleted_at" in cur:
        return failure("not_found")
    if not as_admin and cur["subject_type"] == "individual" and _sealed_individual(store, cur["subject_id"]):
        return failure("not_found")
    loc = store.get(LOC.LOCATIONS.name, cur["location_id"])
    flag = _residential_after(store, cur["location_id"], None, id) if loc is not None and "deleted_at" not in loc else None

    def write(t):
        r = H.soft_delete(store, id, actor, tx=t, now=now)
        if r.ok and flag is not None:
            _sync_residential(store, loc, flag, actor, t, now)
        return r

    return _in_tx(store, tx, write)


# =============================================================================
# erase support (called from the individual erase)
# =============================================================================

def scrub_for_individual(store, individual_id, actor, tx, now=None):
    """For an erased person: scrub every link of theirs, then retire and scrub any location left with no live link of any
    kind, past or present. Returns {"links_scrubbed": n, "locations_scrubbed": m}. Writes join `tx`."""
    links = H.live_for(store, "subject_id", individual_id)
    mine = {l["id"] for l in links}
    locations = sorted({l["location_id"] for l in links})
    for l in links:
        H.scrub(store, l["id"], actor, tx=tx, now=now)
    scrubbed = 0
    for lid in locations:
        loc = store.get(LOC.LOCATIONS.name, lid)
        if loc is None or "deleted_at" in loc or loc.get("status") != "active":
            continue
        others = [l for l in H.live_for(store, "location_id", lid) if l["id"] not in mine]
        if not others:  # nobody else, past or present, is linked: nothing is left to describe
            LOC.scrub(store, lid, actor, tx=tx, now=now)
            scrubbed += 1
        elif loc.get("is_residential") and not any(o["relationship"] == RESIDENCE and H.is_live(o) for o in others):
            LOC.set_residential(store, lid, False, "system:location_links", tx=tx, now=now)
    return {"links_scrubbed": len(links), "locations_scrubbed": scrubbed}
