"""questions shield; question.schema.json and question.guide.md; decision D001.

No correctness map or answer lookups: those belong to sets/services. Content
updates create linked revisions. Decommission retains all content and audit.
"""
from .schema_kit import load_collection
from . import record_kit as kit

COLLECTION = load_collection("question")


def rules(doc):
    """Question-specific same-record rules: structural rules are all in schema."""
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
    """Compatibility name: archive only, never hard delete."""
    return set_archived(store, id, actor, expected_record_version, reason, True)


def set_archived(store, id, actor, expected_record_version, reason, is_archived):
    return kit.archive_record(store, COLLECTION, id, actor, expected_record_version, reason, is_archived, rules)


def inventory(store, limit=1001):
    return kit.inventory(store, COLLECTION, limit)
