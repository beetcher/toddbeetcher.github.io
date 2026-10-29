"""Returned-result shield; attempt.schema.json/guide; D001.

No live administration. The service grades a returned report and supplies trusted
calculated fields. New or corrected runs are appended by a service with explicit
chain linkage; raw update never overwrites scores, answers or prior evidence.
"""
from .schema_kit import failure, load_collection
from . import record_kit as kit

COLLECTION = load_collection("attempt")


# RULES BLOCK: local result identities and score arithmetic, never grading joins.
def rules(doc):
    problems = []
    ids = [row["item_id"] for row in doc["responses"]]
    if len(ids) != len(set(ids)):
        problems.append({"field": "responses", "issue": "duplicate_item_response"})
    for key in ("returned_score", "calculated_score"):
        score = doc[key]
        if score["points_earned"] > score["points_possible"]:
            problems.append({"field": key, "issue": "earned_exceeds_possible"})
    if "person_id" in doc and "test_taken_at" not in doc:
        problems.append({"field": "test_taken_at", "issue": "required"})
    return problems


def create(store, data, actor, source="ready_results"):
    return failure("validation_failed", [{"field": "body", "issue": "use_result_service"}])


def record_result(store, submitted, calculated_fields, actor):
    """Service-only initial result constructor; update-chain mechanics follow later."""
    return kit.create_record(store, COLLECTION, submitted, actor, "ready_results", rules,
                             service_fields=calculated_fields)


def get(store, id, include_archived=False):
    return kit.get_record(store, COLLECTION, id, include_archived)


def list(store, **options):
    return kit.list_records(store, COLLECTION, **options)


def update(store, id, changes, actor, expected_record_version):
    return failure("conflict", [{"field": "body", "issue": "append_linked_result"}])


def soft_delete(store, id, actor, expected_record_version, reason):
    return set_archived(store, id, actor, expected_record_version, reason, True)


def set_archived(store, id, actor, expected_record_version, reason, is_archived):
    return kit.archive_record(store, COLLECTION, id, actor, expected_record_version, reason, is_archived, rules)


def inventory(store, limit=1001):
    return kit.inventory(store, COLLECTION, limit)


def link_successor(store, previous, successor_id, actor):
    return kit.advance_chain(store, COLLECTION, previous, successor_id, actor)


def set_chain_head(store, root_id, head_id, actor):
    """Service-only transactional root guard; no result evidence is changed."""
    from copy import deepcopy
    root = kit.get_record(store, COLLECTION, root_id, True)
    if not root.ok:
        return root
    value = deepcopy(root.data)
    value["chain_head_id"] = head_id
    value["record_version"] += 1
    value["lifecycle_events"].append({"at": kit._stamp(), "by": actor,
        "is_archived": value["is_archived"], "reason": "Updated-result chain head advanced"})
    value.update(updated_at=kit._stamp(), updated_by=actor)
    issues = kit._validate_stored(COLLECTION, value, rules)
    if issues:
        return failure("validation_failed", issues)
    store.replace_metadata(COLLECTION.name, root_id, value)
    return root.__class__(ok=True, data=value)
