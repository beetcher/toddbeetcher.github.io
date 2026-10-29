"""Immutable test shield; test.schema.json/guide; D001.

Named create_frozen is called only by a service after cross-record selection and
snapshot construction. There is no test-content update/delete path. Archival
only appends availability audit and preserves original frozen content.
"""
from collections import Counter

from .schema_kit import failure, load_collection
from . import record_kit as kit

COLLECTION = load_collection("test")


# RULES BLOCK: occurrence uniqueness, exact duplicate pairs and frozen choices.
def rules(doc):
    problems = []
    items = doc["items"]
    item_ids = [row["item_id"] for row in items]
    if len(item_ids) != len(set(item_ids)):
        problems.append({"field": "items", "issue": "duplicate_item_id"})
    counts = Counter(row["question_id"] for row in items)
    pairs = sum(count == 2 for count in counts.values())
    if any(count > 2 for count in counts.values()):
        problems.append({"field": "items", "issue": "triplets_not_allowed"})
    if not doc["allow_duplicates"] and pairs:
        problems.append({"field": "items", "issue": "duplicates_not_allowed"})
    if pairs != doc["duplicate_pair_count"] or (not doc["allow_duplicates"] and doc["duplicate_pair_count"]):
        problems.append({"field": "duplicate_pair_count", "issue": "pair_count_mismatch"})
    if doc["selection_summary"]["selected_count"] != len(items):
        problems.append({"field": "selection_summary", "issue": "count_mismatch"})
    for item in items:
        answer_ids = [row["answer_id"] for row in item["answers"]]
        strong = sum(row["role"] == "strong" for row in item["answers"])
        if len(answer_ids) != len(set(answer_ids)):
            problems.append({"field": "items", "issue": "duplicate_answer_id"})
        if not strong or (item["question_type"] == "single_choice" and strong != 1):
            problems.append({"field": "items", "issue": "invalid_strong_answers"})
    return problems


def create(store, data, actor, source="ready_admin"):
    return failure("validation_failed", [{"field": "body", "issue": "use_test_service"}])


def create_frozen(store, snapshot, actor, receipt=None):
    """Service-only snapshot constructor; no participant identity accepted by schema."""
    return kit.create_record(store, COLLECTION, snapshot, actor, "ready_system", rules, service_fields=receipt)


def get(store, id, include_archived=False):
    return kit.get_record(store, COLLECTION, id, include_archived)


def list(store, **options):
    return kit.list_records(store, COLLECTION, **options)


def update(store, id, changes, actor, expected_record_version):
    return failure("conflict", [{"field": "items", "issue": "immutable_test"}])


def soft_delete(store, id, actor, expected_record_version, reason):
    return set_archived(store, id, actor, expected_record_version, reason, True)


def set_archived(store, id, actor, expected_record_version, reason, is_archived):
    return kit.archive_record(store, COLLECTION, id, actor, expected_record_version, reason, is_archived, rules)


def inventory(store, limit=1001):
    return kit.inventory(store, COLLECTION, limit)
