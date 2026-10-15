"""In-memory versions of the ports, for tests and for the contract kit (R-18). Not for production."""
from __future__ import annotations

import uuid
from typing import Optional

from .contract import Contact
from .settings import Settings


class MemoryDirectory:
    """contacts: {individual_id: Contact}. Adhoc recipients are turned into a Contact directly."""

    def __init__(self, contacts=None):
        self.contacts = dict(contacts or {})

    def lookup(self, recipient: dict) -> Optional[Contact]:
        if recipient["type"] == "adhoc":
            ch = "email" if recipient.get("email") else "text" if recipient.get("phone") else None
            return Contact(name=recipient.get("name", ""), email=recipient.get("email"), phone=recipient.get("phone"), preferred_channel=ch)
        return self.contacts.get(recipient["individual_id"])


class MemoryTemplateStore:
    def __init__(self, templates=None):
        self.templates = list(templates or [])

    def add(self, t: dict) -> dict:
        t = dict(t)
        t.setdefault("id", str(uuid.uuid4()))
        t.setdefault("status", "published")
        t.setdefault("version", 1)
        self.templates.append(t)
        return t

    def find_published(self, kind, channel, audience):
        pub = [t for t in self.templates if t["status"] == "published" and "deleted_at" not in t
               and (t["kind"], t["channel"], t["audience"]) == (kind, channel, audience)]
        superseded = {t.get("previous_id") for t in pub}
        standing = [t for t in pub if t["id"] not in superseded]
        return dict(standing[0]) if standing else None


class MemoryLogStore:
    def __init__(self, fail=False):
        self.entries: list = []
        self.fail = fail

    def append(self, entry: dict, by: str, now) -> Optional[str]:
        if self.fail:
            raise RuntimeError("log store down")
        e = dict(entry)
        e["id"] = str(uuid.uuid4())
        e["created_by"], e["created_at"] = by, now
        self.entries.append(e)
        return e["id"]

    def find_by_dedupe_key(self, key: str) -> list:
        return [dict(e) for e in self.entries if e.get("dedupe_key") == key]


class MemorySettings:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()

    def read(self) -> Settings:
        return self.settings
