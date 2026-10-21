"""Service for `access_persons`: the handler (access_persons_crud.py) plus the invitation email (P-64).

Same function names as a handler file, so the dispatcher treats it like one. The handler owns every rule about the person; this file only
adds what happens AFTER a person is saved:

  * create     saves the invited person, then asks the CMS to send the invitation email (kind access_invite). The email is sent only for a
               person who is switched on and only when a signed-in human or the admin key made the invitation (actor user:...), never for
               a seed script or the test door. The answer carries `invite_email` {status, reason} so the Console can say plainly whether
               it went. A failed or skipped email NEVER undoes the invitation (CMS rules R-3 and R-4).
  * send_invite  Resend invite email: sends it again, by hand (a hand send ignores duplicate protection).

Who may call send_invite is decided at the door like any other write to access_persons. No key and no token are ever in the email.
"""
from __future__ import annotations

import logging

from . import access_persons_crud as H
from .discovery_kit import bad, id_problem
from .schema_kit import check_actor, failure, success

LOG = logging.getLogger("enjoy_router")
COLLECTION, get, list, update, soft_delete = H.COLLECTION, H.get, H.list, H.update, H.soft_delete
record_sign_in = H.record_sign_in


def _send(store, person, actor, manual):
    """-> {"status", "reason"} from the CMS, or a not_sent result with the reason. Never raises."""
    import comms
    from launch_comms import invite_context
    try:
        if not comms.is_configured():
            return {"status": "skipped", "reason": "cms_off"}
        call, reason = invite_context.call_for(store, person, actor, manual)
        if call is None:
            return {"status": "not_sent", "reason": reason}
        res = comms.notify(**call)
        return {"status": res.status, "reason": res.reason}
    except Exception as exc:                                    # a mail problem is never the caller's problem
        LOG.error("access_invite code=internal_error exception=%s", type(exc).__name__)
        return {"status": "not_sent", "reason": "internal_error"}


def create(store, data, actor, source="dashboard", tx=None, now=None):
    r = H.create(store, data, actor, source, tx=tx, now=now)
    if not r.ok or tx is not None:                              # inside a caller's transaction nothing is saved yet: no email
        return r
    if not (isinstance(actor, str) and actor.startswith("user:")) or not r.data.get("is_active"):
        return r
    return success({**r.data, "invite_email": _send(store, r.data, actor, False)})


def send_invite(store, id, actor, now=None):   # noqa: A002
    """Resend the invitation email now, by hand. Returns what the CMS decided: status, reason (and the log entry id)."""
    import comms
    problems = check_actor(actor) + id_problem(id)
    if problems:
        return bad(problems)
    if not comms.is_configured():
        return bad([{"field": "email", "issue": "not_enabled"}])
    cur = store.get(COLLECTION.name, id)
    if cur is None or "deleted_at" in cur:
        return failure("not_found")
    if not cur.get("is_active"):
        return bad([{"field": "is_active", "issue": "switched_off"}])
    return success({"id": id, **_send(store, cur, actor, True)})
