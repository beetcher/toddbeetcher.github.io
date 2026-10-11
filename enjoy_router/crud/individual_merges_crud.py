"""Merge, unmerge and erase for individuals, and read access to merge events (schemas/merge_event.schema.json,
MERGE_EVENT_GUIDE.md, INDIVIDUAL_GUIDE.md section 6). Same rules as the other handler files: plain functions called by
services, never an endpoint; a Result with problems that name fields and never values.

    merge(store, survivor_id, duplicate_id, reason, actor, field_choices=None)
        Folds the duplicate into the survivor in ONE transaction: the survivor's merged record, the duplicate (status
        merged, merged_into_id), every record that pointed at the duplicate (re-pointed) and the merge_event.
    unmerge(store, merge_event_id, actor)
        Reverses it without undoing later legitimate changes (only values still equal to what the merge wrote move back).
    erase(store, id, actor)
        Irreversible. Leaves a tombstone, erases the person's restricted details, and scrubs the personal data in their
        history records and in merge-event snapshots. Nothing is hard-deleted (the store has no delete), so every link
        that points at the person still resolves, to the tombstone.
    get_event / list_events: read merge events.
"""
from __future__ import annotations

import builtins
import copy
from typing import Optional

from . import individual_restricted_details_crud as R
from . import individuals_crud as I
from .schema_kit import (
    UUID_PATTERN, check_actor, check_document, clean, failure, load_collection, new_id,
    stamp_create, success, utc_stamp,
)
from .store_errors import DocMissing, StaleUpdate

MERGES = load_collection("merge_event")
REQUESTS = load_collection("registration_request")
ASSIGNMENTS = load_collection("registration_assignment")
TRANSACTIONS = load_collection("transaction_record")
LOCATION_LINKS = load_collection("location_link")
VENUES = load_collection("venue")
INDIVIDUALS = I.INDIVIDUALS
DETAILS = R.DETAILS
HISTORY = I.HISTORY
DETAIL_HISTORY = R.HISTORY
MERGE_ACTOR = "system:identity_merge"
MAX_LINKS = 400
SCAN_LIMIT = 500

# (collection name, field path, kind). Every place that holds an individual id. A new schema that gains one adds a row here.
LINKS = (
    (DETAILS.name, "individual_id", "scalar"),
    (REQUESTS.name, "individual_id", "scalar"),
    (ASSIGNMENTS.name, "participant_individual_ids", "list"),
    (TRANSACTIONS.name, "participant_individual_ids", "list"),
    (TRANSACTIONS.name, "payer.party_id", "scalar"),
    (TRANSACTIONS.name, "payee.party_id", "scalar"),
    (LOCATION_LINKS.name, "subject_id", "scalar"),  # only links whose subject_type is individual (see _find_links)
    (VENUES.name, "contact_individual_id", "scalar"),
    (VENUES.name, "backup_contact_individual_id", "scalar"),
)

SKIP = frozenset({"id", "schema_version", "created_at", "created_by", "updated_at", "updated_by", "source", "status",
                  "merged_into_id", "erased_at", "display_name", "is_minor", "retention_class", "deleted_at", "deleted_by"})
BIRTH_GROUP = ("birth_date", "birth_date_certainty", "birth_date_verification")
DEATH_GROUP = ("life_status", "death_date", "death_date_certainty", "death_place_city", "death_place_region", "death_country", "death_evidence")
UNION_LISTS = ("external_refs", "same_as_urls")
GROUP_FIELDS = frozenset(BIRTH_GROUP + DEATH_GROUP + UNION_LISTS + ("record_privacy", "identity_verification"))
PRIVACY_RANK = {"normal": 0, "confidential": 1, "sealed": 2}
IDENT_RANK = {"none": 0, "self_reported": 1, "document_verified": 2}
BIRTH_RANK = {"none": 0, "self": 1, "document": 2}
DEAD = ("deceased", "presumed_deceased")
LIVE = ("active", "inactive")
# fields an erased person keeps (everything else is removed)
TOMBSTONE_KEEP = frozenset({"id", "schema_version", "created_at", "created_by", "updated_at", "updated_by", "source",
                            "status", "erased_at", "given_name", "display_name", "deleted_at", "deleted_by"})


def _bad(problems):
    seen, out = set(), []
    for p in problems:
        k = (p["field"], p["issue"])
        if k not in seen:
            seen.add(k)
            out.append(p)
    return failure("validation_failed", out)


def _uuid(v) -> bool:
    return isinstance(v, str) and bool(UUID_PATTERN.match(v))


def _live(doc) -> bool:
    return doc is not None and "deleted_at" not in doc


def _dig(doc: dict, path: str):
    cur = doc
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


_MISSING = object()


def _dig2(doc: dict, path: str):
    cur = doc
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return _MISSING
        cur = cur[part]
    return cur


# =============================================================================
# survivorship: two records become one
# =============================================================================

def combine(survivor: dict, duplicate: dict, choices: dict):
    """(merged record, changed_fields). Pure: reads two records, writes nothing."""
    merged = copy.deepcopy(survivor)

    def take_group(group):
        for f in group:
            merged.pop(f, None)
        for f in group:
            if f in duplicate:
                merged[f] = copy.deepcopy(duplicate[f])

    for f, v in duplicate.items():
        if f in SKIP or f in GROUP_FIELDS:
            continue
        if f not in merged or (choices.get(f) == "duplicate" and merged.get(f) != v):
            merged[f] = copy.deepcopy(v)

    # birth: the group moves whole; verification decides, never recency
    if "birth_date" in duplicate and choices.get("birth_date") != "survivor":
        s_rank = BIRTH_RANK.get(survivor.get("birth_date_verification", "none"), 0)
        d_rank = BIRTH_RANK.get(duplicate.get("birth_date_verification", "none"), 0)
        if "birth_date" not in survivor or d_rank > s_rank or choices.get("birth_date") == "duplicate":
            take_group(BIRTH_GROUP)

    # death: the duplicate's wins only on authoritative evidence and when the survivor is not already deceased
    d_dead = duplicate.get("life_status") in DEAD and duplicate.get("death_evidence") in ("document", "public_record")
    s_dead = survivor.get("life_status") in DEAD
    if choices.get("life_status") != "survivor" and "life_status" in duplicate:
        if (d_dead and not s_dead) or (choices.get("life_status") == "duplicate" and duplicate.get("life_status") != survivor.get("life_status")):
            take_group(DEATH_GROUP)

    for f, cap in (("external_refs", 20), ("same_as_urls", 10)):
        if f in duplicate:
            have = copy.deepcopy(merged.get(f, []))
            for item in duplicate[f]:
                if item not in have:
                    have.append(copy.deepcopy(item))
            if have:
                merged[f] = have[:cap]

    p = max((survivor.get("record_privacy", "normal"), duplicate.get("record_privacy", "normal")), key=lambda x: PRIVACY_RANK[x])
    if p != "normal" or "record_privacy" in survivor:
        merged["record_privacy"] = p
    iv = max((survivor.get("identity_verification", "none"), duplicate.get("identity_verification", "none")), key=lambda x: IDENT_RANK[x])
    if iv != "none" or "identity_verification" in survivor:
        merged["identity_verification"] = iv

    changed = []
    for f in sorted(set(merged) | set(survivor)):
        if f in SKIP:
            continue
        a, b = survivor.get(f, _MISSING), merged.get(f, _MISSING)
        if a != b:
            entry = {"field": f}
            if a is not _MISSING:
                entry["before"] = copy.deepcopy(a)
            if b is not _MISSING:
                entry["after"] = copy.deepcopy(b)
            changed.append(entry)
    return merged, changed


# =============================================================================
# finding and re-pointing links
# =============================================================================

def _find_links(store, individual_id: str) -> list:
    """[(collection, doc, field, kind)] for every record that points at this individual."""
    out = []
    for base, field, kind in LINKS:
        op = "array_contains" if kind == "list" else "=="
        for d in store.query(base, [(field, op, individual_id)], limit=SCAN_LIMIT):
            if base == LOCATION_LINKS.name and d.get("subject_type") != "individual":
                continue  # a venue or organization id can never equal an individual id, but say so anyway
            out.append((base, d, field, kind))
    return out


def _repoint(value, kind, old, new):
    if kind == "scalar":
        return new
    out = []
    for v in value:
        v = new if v == old else v
        if v not in out:
            out.append(v)
    return out


def _stamp(now, actor):
    t = utc_stamp(now)
    return {"updated_at": t, "updated_by": actor}


def _history(store, tx, individual_id, actor, before, after, now, merge_event_id=None):
    h = {"id": new_id(), "individual_id": individual_id, "changed_at": utc_stamp(now), "changed_by": actor,
         "before": before, "after": after}
    if merge_event_id:
        h["merge_event_id"] = merge_event_id
    store.create(HISTORY, h["id"], h, tx=tx)


# =============================================================================
# merge
# =============================================================================

def merge(store, survivor_id, duplicate_id, reason, actor, field_choices=None, tx=None, now=None):
    problems = check_actor(actor)
    body = {"survivor_id": survivor_id, "duplicate_id": duplicate_id, "reason": clean(reason)}
    if field_choices is not None:
        body["field_choices"] = field_choices
    body = {k: v for k, v in body.items() if v is not None}
    problems += [p for p in check_document(MERGES, body)]
    if problems:
        return _bad(problems)
    if survivor_id == duplicate_id:
        return _bad([{"field": "duplicate_id", "issue": "same_as_survivor"}])

    s = store.get(INDIVIDUALS.name, survivor_id)
    d = store.get(INDIVIDUALS.name, duplicate_id)
    problems = []
    if not _live(s) or s.get("status") not in LIVE:
        problems.append({"field": "survivor_id", "issue": "not_found"})
    if not _live(d) or d.get("status") not in LIVE:
        problems.append({"field": "duplicate_id", "issue": "not_found"})
    if problems:
        return _bad(problems)

    choices = field_choices or {}
    merged, changed = combine(s, d, choices)
    stamp = _stamp(now, actor)
    merged_full = {**merged, **stamp}
    merged_full.pop("display_name", None)
    prob = check_document(INDIVIDUALS, merged_full) + I._run_rules(merged_full, now)
    if prob:  # the combination is not a valid record: nothing is written
        return _bad([{"field": p["field"], "issue": p["issue"]} for p in prob])
    I._derive(merged_full, now)

    links = _find_links(store, duplicate_id)
    if len(links) > MAX_LINKS:
        return _bad([{"field": "duplicate_id", "issue": "too_many_links"}])
    if any(b == DETAILS.name for b, _, _, _ in links) and R._existing_for(store, survivor_id) is not None:
        return _bad([{"field": "duplicate_id", "issue": "conflict_restricted_detail"}])

    event_id = new_id()
    moved = []
    link_writes = []
    for base, doc, field, kind in links:
        before = _dig(doc, field)
        after = _repoint(before, kind, duplicate_id, survivor_id)
        moved.append({"collection": base, "id": doc["id"], "field": field, "before": copy.deepcopy(before), "after": copy.deepcopy(after)})
        link_writes.append((base, doc, field, after))

    event = stamp_create(MERGES, {"survivor_id": survivor_id, "duplicate_id": duplicate_id, "reason": body["reason"],
                                  **({"field_choices": field_choices} if field_choices else {})}, actor, "dashboard", now)
    event["id"] = event_id
    event.update({"status": "merged", "survivor_before": copy.deepcopy(s), "duplicate_before": copy.deepcopy(d),
                  "changed_fields": changed, "moved_links": moved})
    miss = [f for f in MERGES.server_required if f not in event]
    if miss or check_document(MERGES, event):
        return failure("server_error")

    def write(t):
        surv_set = {k: v for k, v in merged_full.items() if s.get(k, _MISSING) != v}
        surv_del = [k for k in s if k not in merged_full]
        store.update(INDIVIDUALS.name, survivor_id, surv_set, surv_del, expected_updated_at=s["updated_at"], tx=t)
        store.update(INDIVIDUALS.name, duplicate_id, {"status": "merged", "merged_into_id": duplicate_target(survivor_id), **stamp}, (),
                     expected_updated_at=d["updated_at"], tx=t)
        for base, doc, field, after in link_writes:
            store.update(base, doc["id"], {field: after, "updated_at": stamp["updated_at"], "updated_by": MERGE_ACTOR}, (), tx=t)
        store.create(MERGES.name, event_id, event, tx=t)
        _history(store, t, survivor_id, actor, {c["field"]: c["before"] for c in changed if "before" in c},
                 {c["field"]: c["after"] for c in changed if "after" in c}, now, event_id)
        _history(store, t, duplicate_id, actor, {"status": d.get("status")}, {"status": "merged", "merged_into_id": survivor_id}, now, event_id)

    try:
        if tx is not None:
            write(tx)
        else:
            with store.transaction() as own:
                write(own)
    except (DocMissing, StaleUpdate):
        return failure("conflict")
    return success({"id": event_id, "survivor_id": survivor_id, "duplicate_id": duplicate_id,
                    "changed_fields": [c["field"] for c in changed], "moved_links": len(moved)})


def duplicate_target(survivor_id):
    return survivor_id


# =============================================================================
# unmerge
# =============================================================================

def unmerge(store, merge_event_id, actor, tx=None, now=None):
    problems = check_actor(actor) + ([] if _uuid(merge_event_id) else [{"field": "id", "issue": "invalid_format"}])
    if problems:
        return _bad(problems)
    ev = store.get(MERGES.name, merge_event_id)
    if ev is None:
        return failure("not_found")
    if ev.get("status") != "merged":
        return failure("conflict", [{"field": "id", "issue": "not_merged"}])
    if ev.get("has_erased_snapshots") or not ev.get("duplicate_before"):
        return failure("conflict", [{"field": "id", "issue": "snapshots_erased"}])
    sid, did = ev["survivor_id"], ev["duplicate_id"]
    s, d = store.get(INDIVIDUALS.name, sid), store.get(INDIVIDUALS.name, did)
    if d is None or d.get("status") != "merged" or d.get("merged_into_id") != sid:
        return failure("conflict", [{"field": "duplicate_id", "issue": "changed"}])
    if s is None or s.get("status") not in LIVE or "deleted_at" in s:
        return failure("conflict", [{"field": "survivor_id", "issue": "changed"}])

    stamp = _stamp(now, actor)
    skipped = []
    # survivor: put back each field the merge changed, if it still holds the value the merge wrote
    s_set, s_del = {}, []
    for c in ev["changed_fields"]:
        f = c["field"]
        cur = s.get(f, _MISSING)
        want = c.get("after", _MISSING)
        if cur != want:
            skipped.append(f"survivor:{f}")
            continue
        if "before" in c:
            s_set[f] = c["before"]
        else:
            s_del.append(f)
    # duplicate: restore its snapshot, remove the redirect
    snap = ev["duplicate_before"]
    d_set = {k: v for k, v in snap.items() if k not in ("updated_at", "updated_by")}
    d_del = [k for k in d if k not in snap]
    # links
    link_writes = []
    for m in ev["moved_links"]:
        doc = store.get(m["collection"], m["id"])
        if doc is None or _dig2(doc, m["field"]) != m.get("after"):
            skipped.append(f"{m['collection']}:{m['id']}")
            continue
        link_writes.append((m, ))

    merged_after = {**{k: v for k, v in s.items() if k not in s_del}, **s_set}
    merged_after.pop("display_name", None)
    I._derive(merged_after, now)

    def write(t):
        store.update(INDIVIDUALS.name, sid, {**s_set, **{k: merged_after[k] for k in ("display_name", "is_minor") if k in merged_after}, **stamp},
                     s_del + [k for k in ("is_minor",) if k not in merged_after and k in s], expected_updated_at=s["updated_at"], tx=t)
        store.update(INDIVIDUALS.name, did, {**d_set, **stamp}, d_del, expected_updated_at=d["updated_at"], tx=t)
        for (m,) in link_writes:
            store.update(m["collection"], m["id"], {m["field"]: m["before"], "updated_at": stamp["updated_at"], "updated_by": MERGE_ACTOR}, (), tx=t)
        ev_set = {"status": "unmerged", "unmerged_at": stamp["updated_at"], "unmerged_by": actor, **stamp}
        if skipped:
            ev_set["unmerge_skipped"] = skipped[:500]
        store.update(MERGES.name, merge_event_id, ev_set, (), expected_updated_at=ev["updated_at"], tx=t)
        _history(store, t, sid, actor, {c["field"]: c.get("after") for c in ev["changed_fields"]}, {c["field"]: c.get("before") for c in ev["changed_fields"]}, now, merge_event_id)
        _history(store, t, did, actor, {"status": "merged", "merged_into_id": sid}, {"status": snap.get("status")}, now, merge_event_id)

    try:
        if tx is not None:
            write(tx)
        else:
            with store.transaction() as own:
                write(own)
    except (DocMissing, StaleUpdate):
        return failure("conflict")
    return success({"id": merge_event_id, "restored_links": len(link_writes), "skipped": skipped})


# =============================================================================
# erase
# =============================================================================

def erase(store, id, actor, tx=None, now=None):
    problems = check_actor(actor) + ([] if _uuid(id) else [{"field": "id", "issue": "invalid_format"}])
    if problems:
        return _bad(problems)
    cur = store.get(INDIVIDUALS.name, id)
    if cur is None:
        return failure("not_found")
    if cur.get("status") == "erased":
        return failure("conflict", [{"field": "status", "issue": "already_erased"}])
    t = utc_stamp(now)
    stamp = {"updated_at": t, "updated_by": actor}
    tomb = {"status": "erased", "erased_at": t, "given_name": "[erased]", "display_name": "[erased]", **stamp}
    dels = [k for k in cur if k not in TOMBSTONE_KEEP]
    detail = R._existing_for(store, id)
    sensitive = [k for k in (list(R.ALLOWED) + ["notes", "legal_basis"]) if detail and k in detail]
    hist = store.query(HISTORY, [("individual_id", "==", id)], limit=SCAN_LIMIT)
    dhist = store.query(DETAIL_HISTORY, [("individual_id", "==", id)], limit=SCAN_LIMIT)
    events = {e["id"]: e for field in ("survivor_id", "duplicate_id") for e in store.query(MERGES.name, [(field, "==", id)], limit=SCAN_LIMIT)}

    def write(tx_):
        store.update(INDIVIDUALS.name, id, tomb, dels, tx=tx_)
        if detail:
            store.update(DETAILS.name, detail["id"], {"deleted_at": t, "deleted_by": actor, **stamp}, sensitive, tx=tx_)
        for h in hist:
            store.update(HISTORY, h["id"], {"before": {}, "after": {}}, (), tx=tx_)
        for h in dhist:
            store.update(DETAIL_HISTORY, h["id"], {"before": {}, "after": {}}, (), tx=tx_)
        for e in events.values():
            store.update(MERGES.name, e["id"], {"survivor_before": {}, "duplicate_before": {}, "changed_fields": [],
                                                "has_erased_snapshots": True, "reason": "[erased]", **stamp}, (), tx=tx_)

    try:
        if tx is not None:
            write(tx)
        else:
            with store.transaction() as own:
                write(own)
    except DocMissing:
        return failure("not_found")
    return success({"id": id, "erased_at": t, "history_records_scrubbed": len(hist) + len(dhist), "merge_events_scrubbed": len(events)})


# =============================================================================
# read merge events
# =============================================================================

def get_event(store, id):
    if not _uuid(id):
        return _bad([{"field": "id", "issue": "invalid_format"}])
    doc = store.get(MERGES.name, id)
    return success(doc) if doc is not None else failure("not_found")


def list_events(store, filters=None, limit=100):
    filters = dict(filters or {})
    problems = []
    for k, v in filters.items():
        if k in ("survivor_id", "duplicate_id"):
            if not _uuid(v):
                problems.append({"field": k, "issue": "invalid_format"})
        elif k == "status":
            if v not in ("merged", "unmerged"):
                problems.append({"field": k, "issue": "invalid_value"})
        else:
            problems.append({"field": k, "issue": "not_supported"})
    if len(filters) > 1:
        problems += [{"field": k, "issue": "not_supported"} for k in filters]
    if isinstance(limit, bool) or not isinstance(limit, int):
        problems.append({"field": "limit", "issue": "invalid_type"})
    if problems:
        return _bad(problems)
    limit = max(1, min(limit, 200))
    docs = store.query(MERGES.name, [(k, "==", v) for k, v in filters.items()],
                       order_by=None if filters else "created_at", descending=True, limit=limit)
    return success({"records": docs, "count": len(docs)})
