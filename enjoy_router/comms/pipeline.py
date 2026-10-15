"""The pipeline: notify and notify_many (CMS_GUIDE.md sections 2 and 3). Product-blind (R-1).

The thirteen steps run in a fixed order (R-6). Every call writes exactly one log entry per recipient, whatever happens (R-7).
Nothing here raises into the caller (R-3): a bug inside is caught, logged as internal_error, and the caller carries on.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from . import dedupe
from .calendar_event import event_from_facts, make_ics
from .contract import CONTRACT_VERSION, REF_FIELDS, STATUS_OF, TRIGGERS, Result, normalize_recipient
from .render import Incomplete, render
from .settings import MODES

LOG = logging.getLogger("enjoy_router")


class Comms:
    def __init__(self, *, kinds, directory, templates, log, settings, channels, mode="off", clock=None, monotonic=None):
        self.kinds, self.directory, self.templates, self.log, self.settings = kinds, directory, templates, log, settings
        self.channels = {c.name: c for c in channels}
        self.mode = mode if mode in MODES else "off"          # an unknown mode fails closed
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.monotonic = monotonic or time.monotonic

    # ------------------------------------------------------------------ public

    def notify(self, kind, recipient, context, by, trigger, refs=None, audience=None, suppress=None, dedupe_key=None) -> Result:
        try:
            return self._notify(kind, recipient, context, by, trigger, refs, audience, suppress, dedupe_key)
        except Exception as exc:                                # R-3: never into the caller
            LOG.error("comms code=internal_error exception=%s", type(exc).__name__)
            return self._safe_internal_error(kind, recipient, by, trigger, refs, audience)

    def notify_many(self, items, time_budget_s) -> list:
        """One Result per item, in order. Items not reached before the budget ends are logged not_sent / time_budget (R-22)."""
        start, out = self.monotonic(), []
        for item in items:
            if self.monotonic() - start >= time_budget_s:
                out.append(self._unreached(item))
            else:
                out.append(self.notify(**item))
        return out

    # ------------------------------------------------------------------ the pipeline

    def _notify(self, kind, recipient, context, by, trigger, refs, audience, suppress, dedupe_key) -> Result:
        now = self.clock()
        refs = dict(refs) if isinstance(refs, dict) else {}
        audience = audience or "default"
        e = self._base(kind, audience, trigger, refs)
        done = lambda reason, code=None, ref=None: self._finish(e, reason, by, now, code, ref)   # noqa: E731

        # 1. validate the call (R-5)
        try:
            rec = normalize_recipient(recipient)
        except ValueError:
            return done("invalid_context")
        if rec["type"] == "individual":
            e["individual_id"] = rec["individual_id"]
        kd = self.kinds.get(kind)
        if kd is None:
            return done("unknown_kind")
        if trigger not in TRIGGERS or audience not in kd.audiences or by is None or self.kinds.validate(kind, context):
            return done("invalid_context")
        key = dedupe_key or dedupe.default_key(kind, rec, refs)
        e["dedupe_key"] = key[:300]

        # 2. mode (R-13)
        if self.mode == "off":
            return done("cms_off")

        # 3. duplicate protection; an operator's manual send bypasses it (R-9)
        if trigger != "manual" and any(x.get("status") in ("sent", "unknown") for x in self.log.find_by_dedupe_key(e["dedupe_key"])):
            return done("duplicate")

        # 4. resolve the recipient
        contact = self.directory.lookup(rec)
        if contact is None or contact.preferred_channel is None:
            return done("no_contact")

        # 5. suppression and mute (R-10)
        if self._suppressed(contact, rec, suppress):
            return done("excluded")
        if contact.muted:
            return done("muted")

        # 6. choose the channel: the person's preferred one, and only that one (R-8)
        st = self.settings.read()
        name = contact.preferred_channel
        channel = self.channels.get(name)
        if channel is None or not st.channel_is_on(name):
            return done("channel_unavailable")
        e["channel"] = name
        address = contact.email if name == "email" else (contact.phone or contact.backup_phone)
        if not address:
            return done("no_contact")

        # 7. find the published, active template (R-11)
        t = self.templates.find_published(kind, name, audience)
        if t is None or not t.get("is_active"):
            return done("no_template")
        e["template_version"] = t["version"]

        # 8. render (R-12)
        try:
            subject, text, html = render(t, context, footer=st.footer)
        except Incomplete:
            return done("incomplete")
        content = {"subject": subject, "text": text, "html": html, "attachments": []}
        if channel.supports_attachments:
            for att in kd.attachments:
                if att["kind"] == "calendar_event":
                    ev = event_from_facts(context, att["event_fields"])
                    content["attachments"].append((att["filename"], att["mime_type"],
                                                   make_ics(ev, now, att.get("uid_domain", "beetcher.com"), att.get("method", "PUBLISH"))))
        if not channel.can_carry(content):
            return done("channel_unavailable")

        # 9. test redirect
        to = address
        if st.test_redirect_address:
            to, e["is_redirected"] = st.test_redirect_address, True
        e["to"], e["subject"] = to, subject[:300]

        # 10. log_only stops here (R-13)
        if self.mode == "log_only":
            return done("log_only")

        # 11. send
        ref = channel.new_message_ref()
        res = channel.send(to, content, st, ref)
        if ref:
            e["message_ref"] = ref[:200]
        if res.outcome == "accepted":
            return done("ok")
        if res.outcome == "rejected":
            return done("adapter_error", res.error_code)
        return done("timeout", res.error_code or "unknown")

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _base(kind, audience, trigger, refs) -> dict:
        e = {"kind": str(kind)[:60], "channel": "none", "trigger": trigger if trigger in TRIGGERS else "automatic",
             "contract_version": CONTRACT_VERSION}
        if audience:
            e["audience"] = str(audience)[:40]
        for k in REF_FIELDS:
            if refs.get(k):
                e[k] = refs[k]
        return e

    def _finish(self, e, reason, by, now, error_code=None, message_ref=None) -> Result:
        e["reason"], e["status"] = reason, STATUS_OF[reason]
        if error_code:
            e["error_code"] = str(error_code)[:60]
        if message_ref:
            e["message_ref"] = message_ref
        log_id = self._write(e, by, now)
        return Result(e["status"], e["channel"], reason, log_id)

    def _write(self, entry, by, now) -> Optional[str]:
        """R-7: the log write may fail; that never raises and never undoes anything."""
        try:
            return self.log.append({k: v for k, v in entry.items() if v is not None}, by or "system:comms", now)
        except Exception as exc:
            LOG.error("comms code=log_write_failed exception=%s", type(exc).__name__)
            return None

    def _safe_internal_error(self, kind, recipient, by, trigger, refs, audience) -> Result:
        try:
            e = self._base(kind, audience or "default", trigger, dict(refs) if isinstance(refs, dict) else {})
            if isinstance(recipient, dict) and recipient.get("type") == "individual" and recipient.get("individual_id"):
                e["individual_id"] = recipient["individual_id"]
            return self._finish(e, "internal_error", by, self.clock())
        except Exception:
            return Result("not_sent", "none", "internal_error", None)

    def _unreached(self, item) -> Result:
        try:
            refs = dict(item.get("refs") or {})
            e = self._base(item.get("kind"), item.get("audience") or "default", item.get("trigger"), refs)
            rec = item.get("recipient")
            if isinstance(rec, dict) and rec.get("type") == "individual" and rec.get("individual_id"):
                e["individual_id"] = rec["individual_id"]
            return self._finish(e, "time_budget", item.get("by"), self.clock())
        except Exception:
            return Result("not_sent", "none", "time_budget", None)

    @staticmethod
    def _suppressed(contact, rec, suppress) -> bool:
        if not suppress:
            return False
        wanted = {str(s).strip().lower() for s in suppress}
        mine = {x.lower() for x in (rec.get("individual_id"), contact.individual_id, contact.email, contact.phone, contact.backup_phone) if x}
        return bool(wanted & mine)
