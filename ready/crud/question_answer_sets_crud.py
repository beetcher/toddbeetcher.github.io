"""Contextual-set shield; question_answer_set schema/guide; D001.

Connection roles and diagnostics belong here, never globally on answer atoms.
Question-type/availability lookups are service rules; no joins in this handler.
"""
from .schema_kit import load_collection
from . import record_kit as kit

COLLECTION = load_collection("question_answer_set")


# RULES BLOCK: JSON Schema cannot enforce uniqueness by one object property.
def rules(doc):
    ids = [row["answer_id"] for row in doc["connections"]]
    problems = []
    if len(ids) != len(set(ids)):
        problems.append({"field": "connections", "issue": "duplicate_answer"})
    if doc["status"] == "published" and not any(row["role"] == "strong" for row in doc["connections"]):
        problems.append({"field": "connections", "issue": "strong_answer_required"})
    return problems


def create(store, data, actor, source="ready_admin", receipt=None):
    return kit.create_record(store, COLLECTION, data, actor, source, rules, service_fields=receipt)


def get(store, id, include_archived=False):
    return kit.get_record(store, COLLECTION, id, include_archived)


def list(store, **options):
    return kit.list_records(store, COLLECTION, **options)


def update(store, id, changes, actor, expected_record_version):
    return kit.revise_record(store, COLLECTION, id, changes, actor, expected_record_version, rules)


def soft_delete(store, id, actor, expected_record_version, reason):
    return set_archived(store, id, actor, expected_record_version, reason, True)


def set_archived(store, id, actor, expected_record_version, reason, is_archived):
    return kit.archive_record(store, COLLECTION, id, actor, expected_record_version, reason, is_archived, rules)


def inventory(store, limit=1001):
    return kit.inventory(store, COLLECTION, limit)
