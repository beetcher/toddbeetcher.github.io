"""Shared persistence mechanics for model-shaped collection handlers (D001).

No collection names, field-specific rules, joins or grading here. Callers supply
their loaded schema and local rule callback. Every creation is checked twice:
input, then complete server-stamped record including x_server_required fields.
Linked revisions preserve prior documents. No hard-delete operation exists.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json

from .schema_kit import (
    UUID_PATTERN, check_actor, check_document, clean, drop_empty,
    failure, new_id, stamp_create, success,
)


def _bad(field, issue):
    return failure("validation_failed", [{"field": field, "issue": issue}])


def _stamp():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _validate_stored(coll, doc, rules):
    try:
        encoded = json.dumps(doc, allow_nan=False, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError):
        return [{"field": "body", "issue": "non_json_value"}]
    if len(encoded) > 768 * 1024:
        return [{"field": "body", "issue": "document_size_exceeded"}]
    problems = check_document(coll, doc)
    problems += [{"field": key, "issue": "required"} for key in coll.server_required if key not in doc]
    return problems if problems else rules(doc)


def create_record(store, coll, data, actor, source, rules, *, service_fields=None):
    """Create a validated record; trusted generated fields are a separate argument.

    No external request may call service_fields directly. Endpoint contracts must
    validate caller payloads before a service constructs those protected values.
    Returns Result; no partial write when validation fails.
    """
    if not isinstance(data, dict):
        return _bad("body", "invalid_type")
    issues = check_actor(actor)
    issues += [{"field": key, "issue": "not_allowed"} for key in data if key in coll.read_only]
    if issues:
        return failure("validation_failed", issues)
    doc = drop_empty({key: clean(value) for key, value in deepcopy(data).items()})
    problems = check_document(coll, doc)
    if problems:
        return failure("validation_failed", problems)
    doc = stamp_create(coll, doc, actor, source)
    doc.update(series_id=doc["id"], revision_number=1, record_version=1,
               is_archived=False, lifecycle_events=[], created_at=_stamp())
    doc["updated_at"] = doc["created_at"]
    if service_fields:
        # Schema validation below also rejects unknown trusted fields.
        doc.update(deepcopy(service_fields))
    problems = _validate_stored(coll, doc, rules)
    if problems:
        return failure("validation_failed", problems)
    store.create(coll.name, doc["id"], doc)
    return success(doc)


def get_record(store, coll, record_id, include_archived=False):
    if not isinstance(record_id, str) or not UUID_PATTERN.fullmatch(record_id):
        return _bad("id", "invalid_format")
    doc = store.get(coll.name, record_id)
    if doc is None or (doc["is_archived"] and not include_archived):
        return failure("not_found")
    return success(doc)


def list_records(store, coll, *, limit=25, include_archived=False):
    """Bounded raw revision inventory; current-revision selection is a service rule."""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        return _bad("limit", "out_of_range")
    filters = () if include_archived else (("is_archived", False),)
    return success({"records": store.query(coll.name, filters, limit=limit)})


def revise_record(store, coll, record_id, changes, actor, expected_record_version, rules):
    """Append linked revision, never replace prior content; one chain tip wins.

    The collection's service must check references before invoking this inside
    its transaction. This function enforces only same-collection invariants.
    """
    if not isinstance(changes, dict) or not changes:
        return _bad("changes", "required")
    if isinstance(expected_record_version, bool) or not isinstance(expected_record_version, int):
        return _bad("expected_record_version", "invalid_type")
    issues = check_actor(actor)
    issues += [{"field": key, "issue": "not_allowed"} for key in changes if key in coll.read_only]
    if issues:
        return failure("validation_failed", issues)

    def work(tx):
        got = get_record(tx, coll, record_id)
        if not got.ok:
            return got
        old = got.data
        if old["record_version"] != expected_record_version:
            return failure("conflict")
        if old.get("successor_id"):
            return failure("conflict", [{"field": "id", "issue": "not_chain_tip"}])
        if tx.query(coll.name, (("previous_id", record_id),), limit=1):
            return failure("conflict", [{"field": "id", "issue": "not_chain_tip"}])
        merged = deepcopy(old)
        for key, value in changes.items():
            value = clean(value)
            if value is None:
                merged.pop(key, None)
            else:
                merged[key] = value
        merged.update(id=new_id(), previous_id=old["id"],
                      revision_number=old["revision_number"] + 1,
                      record_version=1, created_at=_stamp(), created_by=actor,
                      updated_by=actor, lifecycle_events=[], is_archived=False, source="ready_admin")
        for key in ("successor_id", "operation_key", "request_digest", "import_receipt"):
            merged.pop(key, None)
        merged["updated_at"] = merged["created_at"]
        problems = _validate_stored(coll, merged, rules)
        if problems:
            return failure("validation_failed", problems)
        tx.create(coll.name, merged["id"], merged)
        advance_chain(tx, coll, old, merged["id"], actor)
        return success(merged)
    return store.transact(work)


def inventory(store, coll, limit=1001):
    """Internal bounded revision scan; service applies current/status/criteria rules."""
    return store.query(coll.name, limit=limit)


def advance_chain(store, coll, previous, successor_id, actor):
    """Named metadata change locks the chain tip in the actual Firestore transaction.

    Content/result evidence never changes. Audit preserves prior update stamp;
    two concurrent successors must contend on this predecessor document.
    """
    old = deepcopy(previous)
    if old.get("successor_id"):
        return failure("conflict")
    old["successor_id"] = successor_id
    old["record_version"] += 1
    old["lifecycle_events"].append({"at": _stamp(), "by": actor,
        "is_archived": old["is_archived"], "reason": "Preserved revision linked to successor"})
    old.update(updated_at=_stamp(), updated_by=actor)
    store.replace_metadata(coll.name, old["id"], old)
    return success(old)


def archive_record(store, coll, record_id, actor, expected_record_version, reason, is_archived, rules):
    """Change availability with append-only audit; no content deletion or rewrite."""
    if not isinstance(is_archived, bool):
        return _bad("is_archived", "invalid_type")
    if isinstance(expected_record_version, bool) or not isinstance(expected_record_version, int):
        return _bad("expected_record_version", "invalid_type")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        return _bad("reason", "invalid_value")
    issues = check_actor(actor)
    if issues:
        return failure("validation_failed", issues)

    def work(tx):
        got = get_record(tx, coll, record_id, include_archived=True)
        if not got.ok:
            return got
        doc = got.data
        if doc["record_version"] != expected_record_version:
            return failure("conflict")
        now = _stamp()
        doc["lifecycle_events"].append({"at": now, "by": actor,
                                        "is_archived": is_archived, "reason": reason.strip()})
        doc.update(is_archived=is_archived, record_version=doc["record_version"] + 1,
                   updated_at=now, updated_by=actor)
        problems = _validate_stored(coll, doc, rules)
        if problems:
            return failure("validation_failed", problems)
        tx.replace_metadata(coll.name, record_id, doc)
        return success(doc)
    return store.transact(work)
