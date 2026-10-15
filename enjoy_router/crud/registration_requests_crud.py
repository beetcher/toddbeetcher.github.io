"""The registration_request collection definition, kept for tests and tools that read it.

The email-metadata setter that lived here (`set_acknowledgment_result`) is retired: since the CMS refactor the receipt's outcome is
written to the message log (communication_logs, by request_id), not onto the request. The `acknowledgment_email_*` fields stay in the
schema, deprecated and no longer written, until Todd's test-data cleanup is done.
"""
from .schema_kit import load_collection

REQUESTS = load_collection("registration_request")
