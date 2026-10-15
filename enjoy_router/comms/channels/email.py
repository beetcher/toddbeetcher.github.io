"""The email channel. It hands a rendered message to a PROVIDER function the product supplies; it never imports an email library (R-1, R-18).

    sender(key, to, subject, text, html, attachments, headers) -> object with .ok (bool) and .code (str)

`headers` carries what the settings and the CMS decide: from_name, from_address, reply_to, message_id. The product's wiring
(step 3) adapts smtp_transport.send to this shape. Provider text never leaves this module: only a short sanitized code does.
"""
from __future__ import annotations

import re
from email.utils import make_msgid
from typing import Optional

from ..ports import ChannelResult

_CODE = re.compile(r"^[a-z0-9_]{1,60}$")


class EmailChannel:
    name = "email"
    supports_attachments = True

    def __init__(self, sender, key_getter, msgid_domain: Optional[str] = None):
        self._sender, self._key, self._domain = sender, key_getter, msgid_domain

    def can_carry(self, content: dict) -> bool:
        return bool(content.get("subject")) and bool(content.get("text"))

    def new_message_ref(self) -> Optional[str]:
        # None (the default) leaves the Message-ID to the mail provider, as the old senders did. Set a domain only when it matches the From domain.
        return make_msgid(domain=self._domain) if self._domain else None

    def send(self, to, content, settings, message_ref) -> ChannelResult:
        headers = {"from_name": settings.sender_name}
        if message_ref:
            headers["message_id"] = message_ref
        if settings.from_address:
            headers["from_address"] = settings.from_address
        if settings.reply_to:
            headers["reply_to"] = settings.reply_to
        try:
            res = self._sender(self._key(), to, content["subject"], content["text"], content.get("html"),
                               content.get("attachments") or None, headers)
        except TimeoutError:
            return ChannelResult("no_answer", "unknown")
        except Exception:
            return ChannelResult("no_answer", "unknown")
        code = str(getattr(res, "code", "") or "")
        if getattr(res, "ok", False) and code == "accepted":
            return ChannelResult("accepted")
        if code == "unknown":
            return ChannelResult("no_answer", "unknown")
        if getattr(res, "ok", False):
            return ChannelResult("rejected", "smtp_failed")
        return ChannelResult("rejected", code if _CODE.match(code) else "smtp_failed")
