"""Post-save acknowledgment around the unchanged registration creation rules.

Both hooks are None by default. main.py enables them for the opted-in deployed
function; tests supply fakes. Email work never changes the core's return value.
"""
import logging

from core import handle_registration_request
from crud.schema_kit import load_collection, utc_stamp
from smtp_transport import SendResult

log = logging.getLogger("enjoy_router")
acknowledge = None  # callable(saved_doc) -> SendResult
record_result = None  # callable(id, status, attempted_at, error_code) -> CRUD Result


def register(body, store, schemas, now):
    result = handle_registration_request(body, store, schemas, now=now)
    if result.outcome != "created" or acknowledge is None:
        return result
    try:
        attempted_at = utc_stamp()
        try:
            email_result = acknowledge(dict(result.doc))
        except TimeoutError:
            email_result = SendResult(False, "unknown")
        except Exception:
            email_result = SendResult(False, "configuration_failed")
        allowed = load_collection("registration_request").properties["acknowledgment_email_error_code"]["enum"]
        if email_result.ok and email_result.code == "accepted":
            status, code = "accepted", None
        elif email_result.code == "unknown":
            status, code = "unknown", "unknown"
        else:
            status = "failed"
            code = email_result.code if email_result.code in allowed else "smtp_failed"
        if record_result is None:
            log.error("cms id=%s code=result_recorder_disabled", result.doc["id"])
        else:
            recorded = record_result(result.doc["id"], status, attempted_at, code)
            if not recorded.ok:
                log.error("cms id=%s code=result_record_failed", result.doc["id"])
        log.info("cms id=%s status=%s code=%s", result.doc["id"], status, code or "accepted")
    except Exception:
        log.error("cms id=%s code=result_record_failed", result.doc["id"])
    return result
