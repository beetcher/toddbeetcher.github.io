"""CMS settings and the send mode (CMS_GUIDE.md section 7; rules R-13, R-19). Product-blind."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

MODES = ("off", "log_only", "live")


@dataclass(frozen=True)
class Settings:
    """Mirrors the comms_setting record. Defaults are what a missing record means."""
    sender_name: str = "Launch"
    from_address: Optional[str] = None
    reply_to: Optional[str] = None
    footer: Optional[str] = None
    test_redirect_address: Optional[str] = None
    is_email_on: bool = True
    is_text_on: bool = False

    def channel_is_on(self, channel: str) -> bool:
        return {"email": self.is_email_on, "text": self.is_text_on}.get(channel, False)


def resolve_mode(environ) -> str:
    """The send mode comes from the environment, never from the Console. ICDT_COMMS_MODE (off, log_only, live) wins; otherwise
    the old switch ICDT_CMS_ENABLED=true means live and anything else means off. An unknown value means off (fail closed)."""
    raw = (environ.get("ICDT_COMMS_MODE") or "").strip().lower()
    if raw:
        return raw if raw in MODES else "off"
    return "live" if (environ.get("ICDT_CMS_ENABLED") or "").strip().lower() == "true" else "off"
