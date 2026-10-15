"""A fake channel for tests (R-18): records what it was given and answers as told. Never sends anything."""
from __future__ import annotations

from typing import Optional

from ..ports import ChannelResult


class FakeChannel:
    def __init__(self, name="email", outcome="accepted", error_code=None, supports_attachments=True, can_carry=True):
        self.name, self.supports_attachments = name, supports_attachments
        self.outcome, self.error_code, self._can_carry = outcome, error_code, can_carry
        self.sent: list = []
        self._n = 0

    def can_carry(self, content: dict) -> bool:
        return self._can_carry

    def new_message_ref(self) -> Optional[str]:
        self._n += 1
        return f"<fake-{self._n}@example.test>"

    def send(self, to, content, settings, message_ref) -> ChannelResult:
        self.sent.append({"to": to, "content": content, "settings": settings, "message_ref": message_ref})
        return ChannelResult(self.outcome, self.error_code)
