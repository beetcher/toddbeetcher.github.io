"""The ports: what the product supplies to the CMS (CMS_GUIDE.md section 4). The core knows only these shapes (R-1).

The product (LAUNCH) implements them in launch_comms/. Memory versions for tests live in comms/memory_stores.py, and
comms/contract_kit.py holds the tests every implementation must pass (R-18).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol

from .contract import Contact


class RecipientDirectory(Protocol):
    def lookup(self, recipient: dict) -> Optional[Contact]:
        """recipient is the normalized form (individual or adhoc). Returns None when the person cannot be found or reached.
        The directory applies the product's channel-preference rule (R-24) and sets Contact.preferred_channel."""


class TemplateStore(Protocol):
    def find_published(self, kind: str, channel: str, audience: str) -> Optional[dict]:
        """The STANDING published template record for (kind, channel, audience), or None. Drafts are never returned (R-11, R-21).
        The record has the message_template fields (subject, blocks, is_active, version, ...)."""


class LogStore(Protocol):
    def append(self, entry: dict, by: str, now) -> Optional[str]:
        """Write one communication_log entry (only fields that have values) and return its id. May raise; the CMS catches it (R-7)."""

    def find_by_dedupe_key(self, key: str) -> list:
        """Log entries (dicts with at least `status`) that carry this dedupe_key."""


class SettingsStore(Protocol):
    def read(self) -> Any:
        """The current comms.settings.Settings (defaults when no record exists)."""


@dataclass(frozen=True)
class ChannelResult:
    """outcome: accepted (the provider took it), rejected (the provider refused it) or no_answer (we cannot say)."""
    outcome: str
    error_code: Optional[str] = None


class Channel(Protocol):
    name: str
    supports_attachments: bool

    def can_carry(self, content: dict) -> bool: ...

    def new_message_ref(self) -> Optional[str]:
        """A reference to put on the message so the provider's later reports can be matched (the Message-ID for email), or None."""

    def send(self, to: str, content: dict, settings: Any, message_ref: Optional[str]) -> ChannelResult:
        """content: {"subject", "text", "html", "attachments": [(filename, mime_type, bytes)]}. Never raises; never exposes provider text."""
