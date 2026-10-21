"""The logic of the activity log (P-46), with no store and no clock in it: what makes an entry, and what it says.

An entry (schemas/activity_event.schema.json, ACTIVITY_EVENT_GUIDE.md) says that a record was created, edited, deleted or restored, by whom,
when, and which fields went from what to what. The ActivityStore (activity_store.py) calls this to build the entry for each document write and
writes it in the same transaction. Personal data is never copied: a field marked x_pii in its own schema, and every field of the
sensitive-details collection, is named but its values are withheld.

Nothing here knows a collection by name except the few rules below, which are the guide's section 3.
"""
from __future__ import annotations

import copy
import json
import pathlib
from datetime import datetime, timezone
from typing import Any, Optional

from .schema_kit import ACTOR_PATTERN, find_schema_dir, load_collection, new_id

ACTIVITY = load_collection("activity_event")
COLLECTION = ACTIVITY.name      # activity_events

# Logs themselves, and what the server writes constantly. Everything else in the registry is covered automatically.
EXCLUDED_COLLECTIONS = frozenset({"activity_events", "communication_logs", "journal_events", "discovery_runs"})
# Collections whose every field is sensitive: the entry names the fields and never holds a value.
WITHHOLD_COLLECTIONS = frozenset({"individual_restricted_details"})
# Fields that are not marked x_pii but must never be copied into a log.
# (A person's display_name is computed from their name, and a request's free text and organisation come from the requester; their schemas
# do not mark them x_pii, so they are named here. Marking them in their own schemas would make this list shorter.)
WITHHOLD_FIELDS = {"access_persons": frozenset({"google_uid"}),
                   "individuals": frozenset({"display_name", "birth_country"}),
                   "registration_requests": frozenset({"notes", "organization_name"})}
# Fields whose change alone is not worth an entry (a change next to a real one is simply left out of the list).
QUIET_FIELDS = {
    "access_persons": frozenset({"last_sign_in_at"}),
    "registration_requests": frozenset({"acknowledgment_email_status", "acknowledgment_email_attempted_at", "acknowledgment_email_error_code"}),
}
STAMPS = frozenset({"id", "schema_version", "created_at", "created_by", "updated_at", "updated_by"})
# Where a record names other records. A new schema that points at another record adds its field here.
RELATED_FIELDS = ("individual_id", "scheduled_class_id", "request_id", "venue_id", "location_id", "attendance_id", "organization_id", "curriculum_id",
                  "contact_individual_id", "backup_contact_individual_id", "subject_id", "participant_individual_ids")
RELATED_PATHS = (("payer", "party_id"), ("payee", "party_id"))
LABEL_FIELDS = ("name", "title", "slug", "label")
MAX_VALUE_CHARS = 1000
MAX_CHANGES = 150
MAX_RELATED = 12
MAX_LABEL = 200
FALLBACK_ACTOR = "system:unattributed"
_MISSING = object()


# ----------------------------------------------------------------------------
# Which collections are covered, and which of their fields are personal (read from the registry, so a new schema is covered by being registered)
# ----------------------------------------------------------------------------

def _has_pii(node: Any, defs: dict, seen: tuple = ()) -> bool:
    if isinstance(node, dict):
        if node.get("x_pii"):
            return True
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/") and ref not in seen:
            return _has_pii(defs.get(ref.split("/")[-1], {}), defs, seen + (ref,))
        return any(_has_pii(v, defs, seen) for v in node.values())
    if isinstance(node, list):
        return any(_has_pii(v, defs, seen) for v in node)
    return False


_INDEX: dict = {}


def _index() -> dict:
    """collection name -> (type name, frozenset of personal top-level fields)."""
    if not _INDEX:
        d = find_schema_dir()
        for entry in json.loads((d / "registry.json").read_text())["schemas"]:
            schema = json.loads((pathlib.Path(d) / entry["schema"]).read_text())
            defs = schema.get("$defs", {})
            personal = frozenset(k for k, v in schema.get("properties", {}).items() if _has_pii(v, defs))
            _INDEX[entry["collection"]] = (entry["name"], personal)
    return _INDEX


def collection_info(collection: str):
    """(type name, personal fields) when this collection is logged, else None (excluded, or not in the registry)."""
    if collection in EXCLUDED_COLLECTIONS:
        return None
    hit = _index().get(collection)
    return None if hit is None else (collection, hit[0], hit[1])


def is_withheld(collection: str, personal: frozenset, field: str) -> bool:
    return collection in WITHHOLD_COLLECTIONS or field in personal or field in WITHHOLD_FIELDS.get(collection, ())


# ----------------------------------------------------------------------------
# Small pure helpers
# ----------------------------------------------------------------------------

def canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def value_text(value: Any):
    """(JSON text, truncated). Cut at MAX_VALUE_CHARS."""
    s = canon(value)
    return (s[:MAX_VALUE_CHARS], True) if len(s) > MAX_VALUE_CHARS else (s, False)


def _stamp_ok(v: Any) -> bool:
    if not isinstance(v, str):
        return False
    try:
        datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ")
        return True
    except ValueError:
        return False


def actor_of(*candidates: Any) -> str:
    for c in candidates:
        if isinstance(c, str) and ACTOR_PATTERN.match(c):
            return c
    return FALLBACK_ACTOR


def related_ids(record_id: str, *docs: dict) -> list:
    out = [record_id]
    def add(v):
        if isinstance(v, str) and 0 < len(v) <= 100 and v not in out:
            out.append(v)
    for doc in docs:
        for f in RELATED_FIELDS:
            v = (doc or {}).get(f)
            for x in (v if isinstance(v, list) else [v]):
                add(x)
        for a, b in RELATED_PATHS:
            sub = (doc or {}).get(a)
            if isinstance(sub, dict):
                add(sub.get(b))
    return out[:MAX_RELATED]


def label_of(collection: str, personal: frozenset, doc: dict) -> Optional[str]:
    for f in LABEL_FIELDS:
        v = (doc or {}).get(f)
        if isinstance(v, str) and v.strip() and not is_withheld(collection, personal, f):
            return v.strip()[:MAX_LABEL]
    return None


def _change(collection: str, personal: frozenset, field: str, before: Any, after: Any) -> dict:
    c: dict = {"field": field}
    if is_withheld(collection, personal, field):
        c["values_withheld"] = True
        return c
    cut = False
    if before is not _MISSING:
        c["old_value"], t = value_text(before)
        cut = cut or t
    if after is not _MISSING:
        c["new_value"], t = value_text(after)
        cut = cut or t
    if cut:
        c["truncated"] = True
    return c


def apply_changes(before: dict, set_fields: dict, delete_fields) -> dict:
    after = copy.deepcopy(before)
    for path, value in set_fields.items():
        parts = path.split(".")
        cur = after
        for p in parts[:-1]:
            if not isinstance(cur.get(p), dict):
                cur[p] = {}
            cur = cur[p]
        cur[parts[-1]] = copy.deepcopy(value)
    for f in delete_fields:
        after.pop(f, None)
    return after


def _entry(collection: str, type_name: str, action: str, record_id: str, actor: str, created_at: str, changes: list, omitted: int,
           related: list, label: Optional[str], sequence_ms: int) -> dict:
    e = {"id": new_id(), "schema_version": ACTIVITY.schema_version, "action": action, "record_type": type_name, "collection": collection,
         "record_id": record_id, "related_ids": related, "created_at": created_at, "created_by": actor, "updated_at": created_at,
         "updated_by": actor, "source": "system", "sequence_ms": sequence_ms}
    if changes:
        e["changes"] = changes
    if omitted:
        e["fields_omitted"] = omitted
    if label:
        e["record_label"] = label
    return e


def _cap(changes: list):
    return changes[:MAX_CHANGES], max(0, len(changes) - MAX_CHANGES)


# ----------------------------------------------------------------------------
# Building an entry
# ----------------------------------------------------------------------------

def entry_for_create(info, record_id: str, doc: dict, sequence_ms: int, now: datetime) -> dict:
    collection, type_name, personal = info
    fields = sorted(k for k in doc if k not in STAMPS)
    changes, omitted = _cap([_change(collection, personal, k, _MISSING, doc[k]) for k in fields])
    created_at = doc.get("created_at") if _stamp_ok(doc.get("created_at")) else now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return _entry(collection, type_name, "created", record_id, actor_of(doc.get("created_by"), doc.get("updated_by")), created_at,
                  changes, omitted, related_ids(record_id, doc), label_of(collection, personal, doc), sequence_ms)


def entry_for_update(info, record_id: str, before: dict, set_fields: dict, delete_fields, sequence_ms: int, now: datetime) -> Optional[dict]:
    """The entry for one update, or None when nothing worth recording changed (only stamps, or only quiet fields)."""
    collection, type_name, personal = info
    after = apply_changes(before, set_fields, delete_fields)
    touched = {p.split(".")[0] for p in set_fields} | {f.split(".")[0] for f in delete_fields}
    quiet = QUIET_FIELDS.get(collection, frozenset())
    changed = []
    for k in sorted(touched - STAMPS - quiet):
        b, a = before.get(k, _MISSING), after.get(k, _MISSING)
        if (b is _MISSING) != (a is _MISSING) or (b is not _MISSING and canon(b) != canon(a)):
            changed.append(k)
    if not changed:
        return None
    if "deleted_at" in changed and "deleted_at" in after and "deleted_at" not in before:
        action = "deleted"
    elif "deleted_at" in changed and "deleted_at" in before and "deleted_at" not in after:
        action = "restored"
    else:
        action = "edited"
    changes, omitted = _cap([_change(collection, personal, k, before.get(k, _MISSING), after.get(k, _MISSING)) for k in changed])
    stamp = set_fields.get("updated_at")
    created_at = stamp if _stamp_ok(stamp) else now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    actor = actor_of(set_fields.get("deleted_by") if action == "deleted" else None, set_fields.get("updated_by"))
    return _entry(collection, type_name, action, record_id, actor, created_at, changes, omitted,
                  related_ids(record_id, before, after), label_of(collection, personal, after), sequence_ms)
