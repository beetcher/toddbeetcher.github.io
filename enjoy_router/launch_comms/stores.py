"""TemplateStore, LogStore and SettingsStore over the CRUD handlers (the CMS's ports, comms/ports.py).

The handlers own the rules (versions, append-only log, one settings record); these classes only translate. The CMS catches any
exception from here (R-3, R-7), so a store problem never reaches a caller.
"""
from __future__ import annotations

from typing import Optional

from comms.settings import Settings
from crud import communication_logs_crud as LOGS
from crud import comms_settings_crud as SET
from crud import message_templates_crud as TPL


class TemplateStore:
    def __init__(self, store):
        self._store = store

    def find_published(self, kind: str, channel: str, audience: str) -> Optional[dict]:
        probe = {"kind": kind, "channel": channel, "audience": audience}
        stand = TPL.standing(self._store, probe)
        return dict(stand) if stand else None


class LogStore:
    def __init__(self, store):
        self._store = store

    def append(self, entry: dict, by: str, now) -> Optional[str]:
        res = LOGS.record(self._store, entry, by, now=now)
        if not res.ok:
            raise RuntimeError("log entry refused")
        return res.data["id"]

    def find_by_dedupe_key(self, key: str) -> list:
        res = LOGS.list(self._store, {"dedupe_key": key[:300]})
        return list(res.data["records"]) if res.ok else []


class SettingsStore:
    def __init__(self, store):
        self._store = store

    def read(self) -> Settings:
        res = SET.list(self._store)
        if not res.ok or not res.data["records"]:
            return Settings()
        r = res.data["records"][0]
        return Settings(sender_name=r["sender_name"], from_address=r.get("from_address"), reply_to=r.get("reply_to"),
                        footer=r.get("footer"), test_redirect_address=r.get("test_redirect_address"),
                        is_email_on=r["is_email_on"], is_text_on=r["is_text_on"])
