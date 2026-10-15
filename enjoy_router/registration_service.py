"""Post-save receipt around the unchanged registration creation rules.

After a NEW request is saved, the CMS is asked to notify the requester (`request_received`). The CMS decides the wording, the channel,
whether it is sent at all (mode, duplicates) and logs it (R-2, R-4). A message problem never changes the core's return value (R-3).
"""
import logging

import comms
from core import handle_registration_request
from launch_comms import request_context

log = logging.getLogger("enjoy_router")


def register(body, store, schemas, now):
    result = handle_registration_request(body, store, schemas, now=now)
    if result.outcome != "created" or not comms.is_configured():
        return result
    try:
        comms.notify(**request_context.call_for(result.doc))
    except Exception:
        log.error("receipt id=%s code=notify_failed", result.doc.get("id"))
    return result
