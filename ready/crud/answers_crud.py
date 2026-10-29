"""answers shield; answer.schema.json and guide; decision D001.

Atoms have no correctness. Set references and publication guards are service
rules. This handler validates only its record, never another collection.
"""
from .schema_kit import load_collection
from . import record_kit as kit

COLLECTION = load_collection("answer")


def rules(doc):
    return []


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
