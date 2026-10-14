"""Registration-request email metadata setter; no public CRUD door.

Follows venues_crud.set_review_summary and schema_kit conventions. The legacy
creation path in core.py remains responsible for creation and its atomic save.
"""
from .schema_kit import (
    UUID_PATTERN, check_actor, check_field, failure, load_collection,
    stamp_update, success,
)
from .store_errors import DocMissing

REQUESTS = load_collection("registration_request")


def set_acknowledgment_result(store, id, status, attempted_at, error_code=None, now=None):
    actor = "system:cms"
    fields = {
        "acknowledgment_email_status": status,
        "acknowledgment_email_attempted_at": attempted_at,
    }
    if error_code is not None:
        fields["acknowledgment_email_error_code"] = error_code
    problems = check_actor(actor)
    if not isinstance(id, str) or not UUID_PATTERN.fullmatch(id):
        problems.append({"field": "id", "issue": "invalid_format"})
    for name, value in fields.items():
        problems += check_field(REQUESTS, name, value, allow_read_only=True)
    if (status == "accepted" and error_code is not None) or (status != "accepted" and error_code is None):
        problems.append({"field": "acknowledgment_email_error_code", "issue": "invalid_value"})
    if problems:
        return failure("validation_failed", problems)
    fields.update(stamp_update(actor, now))
    removals = () if error_code is not None else ("acknowledgment_email_error_code",)
    try:
        store.update(REQUESTS.name, id, fields, removals, timeout=2)
    except DocMissing:
        return failure("not_found")
    return success({"id": id, "acknowledgment_email_status": status})
