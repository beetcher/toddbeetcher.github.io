"""Contract tests every port implementation must pass (rule R-18). Each function returns a list of failure messages ([] = passes).

    channel_contract(make_channel)
    log_store_contract(make_store)
    template_store_contract(make_store, add)        add(store, record) puts a template record in the store
    directory_contract(make_directory, individual_id)   a directory that knows `individual_id` as a reachable person
Product-blind: the product runs these against its own implementations (launch_comms) the same way the core runs them on the memory ones.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .contract import Contact
from .ports import ChannelResult
from .settings import Settings

NOW = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
CONTENT = {"subject": "Hello", "text": "Hello\n", "html": "<html><body><p>Hello</p></body></html>", "attachments": []}


def channel_contract(make) -> list:
    out = []
    ch = make()
    if not isinstance(getattr(ch, "name", None), str) or not ch.name:
        out.append("a channel needs a name")
    if not isinstance(getattr(ch, "supports_attachments", None), bool):
        out.append("supports_attachments must be a bool")
    if not isinstance(ch.can_carry(dict(CONTENT)), bool):
        out.append("can_carry must return a bool")
    ref = ch.new_message_ref()
    if ref is not None and not isinstance(ref, str):
        out.append("new_message_ref must be a string or None")
    try:
        res = ch.send("someone@example.com", dict(CONTENT), Settings(), ref)
    except Exception as exc:
        return out + [f"send must never raise (raised {type(exc).__name__})"]
    if not isinstance(res, ChannelResult) or res.outcome not in ("accepted", "rejected", "no_answer"):
        out.append("send must return a ChannelResult with outcome accepted, rejected or no_answer")
    elif res.error_code is not None and not (isinstance(res.error_code, str) and len(res.error_code) <= 60):
        out.append("error_code must be a short string")
    return out


def log_store_contract(make) -> list:
    out = []
    s = make()
    e = {"kind": "k", "channel": "email", "status": "sent", "reason": "ok", "trigger": "automatic", "contract_version": 1,
         "dedupe_key": "k:abc"}
    lid = s.append(dict(e), "user:admin", NOW)
    if not isinstance(lid, str) or not lid:
        out.append("append must return the new entry's id")
    if [x["status"] for x in s.find_by_dedupe_key("k:abc")] != ["sent"]:
        out.append("find_by_dedupe_key must return the entry just appended")
    if s.find_by_dedupe_key("nope"):
        out.append("find_by_dedupe_key must return [] for an unknown key")
    return out


def template_store_contract(make, add) -> list:
    out = []
    s = make()
    if s.find_published("k", "email", "default") is not None:
        out.append("an empty store must return None")
    base = {"kind": "k", "channel": "email", "audience": "default", "name": "n", "subject": "s", "blocks": [], "is_active": True}
    old = add(s, {**base, "status": "published", "version": 1})
    got = s.find_published("k", "email", "default")
    if not got or got["version"] != 1:
        out.append("a published template must be found")
    add(s, {**base, "status": "draft", "version": 2, "previous_id": old["id"]})
    if s.find_published("k", "email", "default")["version"] != 1:
        out.append("a draft must never be returned")
    add(s, {**base, "status": "published", "version": 2, "previous_id": old["id"]})
    if s.find_published("k", "email", "default")["version"] != 2:
        out.append("the standing version is the published one nobody supersedes")
    if s.find_published("k", "email", "other") is not None:
        out.append("audience must match")
    return out


def directory_contract(make, individual_id) -> list:
    out = []
    d = make()
    c = d.lookup({"type": "individual", "individual_id": individual_id})
    if not isinstance(c, Contact) or c.preferred_channel not in ("email", "text"):
        out.append("a reachable person must resolve to a Contact with a preferred channel")
    if d.lookup({"type": "individual", "individual_id": "00000000-0000-4000-8000-00000000dead"}) is not None:
        out.append("an unknown person must resolve to None")
    a = d.lookup({"type": "adhoc", "name": "Pat", "email": "pat@example.com"})
    if not isinstance(a, Contact) or a.preferred_channel != "email" or a.email != "pat@example.com":
        out.append("an adhoc recipient with an email must resolve to an email Contact")
    return out
