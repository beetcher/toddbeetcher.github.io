"""Handler for `message_templates`: the wording of each message, kept as data (see MESSAGE_TEMPLATE_GUIDE.md).

Versions are linked records. `create` makes the FIRST draft for a (kind, channel, audience). Every later version starts with
`draft_from` (copy a published record into a draft whose previous_id is the standing record) and ends with `publish`. A draft is edited in
place with `update`; a published record changes only its `is_active` switch. Only drafts can be deleted. Placeholders are checked against
the kind's fact schema before a draft is saved or published (R-12, R-21).
"""
from __future__ import annotations

import re

from launch_comms import kinds as K

from .schema_kit import (
    UUID_PATTERN, check_actor, check_document, check_field, clean, drop_empty, failure, load_collection, stamp_create,
    stamp_update, success, utc_stamp,
)
from .store_errors import DocExists, DocMissing, StaleUpdate

TEMPLATES = load_collection("message_template")
SOURCES = ("dashboard", "import")
DEFAULT_LIMIT = 100
MAX_LIMIT = 200
SCAN = 500
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
CONTENT = ("name", "subject", "blocks", "is_active")
KEY = ("kind", "channel", "audience")
_LIST_FILTERS = ("kind", "status", "audience")


def _bad(problems):
    seen, out = set(), []
    for p in problems:
        k = (p["field"], p["issue"])
        if k not in seen:
            seen.add(k)
            out.append(p)
    return failure("validation_failed", out)


def _id_problem(id):   # noqa: A002
    return [] if isinstance(id, str) and UUID_PATTERN.match(id) else [{"field": "id", "issue": "invalid_format"}]


def _live(store, **match):
    wanted = [(k, "==", v) for k, v in match.items()]
    return [d for d in store.query(TEMPLATES.name, wanted, limit=SCAN) if "deleted_at" not in d]


def _same_key(store, rec):
    return [d for d in _live(store, kind=rec["kind"]) if d["channel"] == rec["channel"] and d["audience"] == rec["audience"]]


def standing(store, rec):
    """The STANDING published record for rec's (kind, channel, audience): published, and no other published record names it as previous."""
    pub = [d for d in _same_key(store, rec) if d.get("status") == "published"]
    superseded = {d.get("previous_id") for d in pub}
    cur = [d for d in pub if d["id"] not in superseded]
    return max(cur, key=lambda d: d["version"]) if cur else None


def _draft(store, rec):
    found = [d for d in _same_key(store, rec) if d.get("status") == "draft"]
    return found[0] if found else None


def _wording(rec):
    return K.registry().check_template(rec)


def create(store, data, actor, source="dashboard", tx=None, now=None):
    problems = check_actor(actor)
    if source not in SOURCES:
        problems.append({"field": "source", "issue": "invalid_value"})
    if problems:
        return _bad(problems)
    if not isinstance(data, dict):
        return _bad([{"field": "body", "issue": "invalid_type"}])
    ro = [{"field": k, "issue": "not_allowed"} for k in data if k in TEMPLATES.read_only]
    if ro:
        return _bad(ro)
    doc = drop_empty({k: clean(v) for k, v in data.items()})
    doc.setdefault("is_active", True)
    problems = check_document(TEMPLATES, {**doc, "status": "draft", "version": 1})
    if problems:
        return _bad(problems)
    problems = _wording(doc)
    if problems:
        return _bad(problems)
    if _same_key(store, doc):
        return _bad([{"field": "kind", "issue": "duplicate"}])      # later versions start with draft_from
    doc = stamp_create(TEMPLATES, {**doc, "status": "draft", "version": 1}, actor, source, now)
    try:
        store.create(TEMPLATES.name, doc["id"], doc, tx=tx)
    except DocExists:
        return failure("server_error")
    return success(doc)


def draft_from(store, id, actor, tx=None, now=None):   # noqa: A002
    """Copy a PUBLISHED record into a new draft; its previous_id is the standing record. Reverting is draft_from on an older record."""
    problems = check_actor(actor) + _id_problem(id)
    if problems:
        return _bad(problems)
    src = store.get(TEMPLATES.name, id)
    if src is None or "deleted_at" in src:
        return failure("not_found")
    if src.get("status") != "published":
        return _bad([{"field": "status", "issue": "not_allowed"}])
    if _draft(store, src):
        return failure("conflict")
    stand = standing(store, src)
    doc = {k: src[k] for k in KEY + CONTENT}
    doc["status"], doc["version"] = "draft", stand["version"] + 1
    doc["previous_id"] = stand["id"]
    doc = stamp_create(TEMPLATES, doc, actor, "dashboard", now)
    if check_document(TEMPLATES, doc):
        return failure("server_error")
    try:
        store.create(TEMPLATES.name, doc["id"], doc, tx=tx)
    except DocExists:
        return failure("server_error")
    return success(doc)


def get(store, id, include_deleted=False):   # noqa: A002
    problems = _id_problem(id)
    if problems:
        return _bad(problems)
    doc = store.get(TEMPLATES.name, id)
    if doc is None or ("deleted_at" in doc and not include_deleted):
        return failure("not_found")
    return success(doc)


def list(store, filters=None, order="kind", limit=DEFAULT_LIMIT):   # noqa: A001
    """Optional ONE filter: kind, status or audience. Order kind or -created_at."""
    filters = dict(filters or {})
    problems = []
    for k, v in filters.items():
        problems += [{"field": k, "issue": "not_supported"}] if k not in _LIST_FILTERS else check_field(TEMPLATES, k, v, allow_read_only=True)
    if len(filters) > 1:
        problems += [{"field": k, "issue": "not_supported"} for k in filters]
    if order not in ("kind", "-created_at"):
        problems.append({"field": "order", "issue": "not_supported"})
    if isinstance(limit, bool) or not isinstance(limit, int):
        problems.append({"field": "limit", "issue": "invalid_type"})
    if problems:
        return _bad(problems)
    docs = [d for d in store.query(TEMPLATES.name, [(k, "==", v) for k, v in filters.items()], limit=SCAN) if "deleted_at" not in d]
    if order == "kind":
        docs.sort(key=lambda d: (d.get("kind", ""), d.get("channel", ""), d.get("audience", ""), -d.get("version", 0), d.get("created_at", "")))
    else:
        docs.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    docs = docs[:max(1, min(limit, MAX_LIMIT))]
    return success({"records": docs, "count": len(docs)})


def update(store, id, changes, actor, expected_updated_at=None, tx=None, now=None):   # noqa: A002
    problems = check_actor(actor) + _id_problem(id)
    if expected_updated_at is not None and not (isinstance(expected_updated_at, str) and STAMP.match(expected_updated_at)):
        problems.append({"field": "expected_updated_at", "issue": "invalid_format"})
    if not isinstance(changes, dict) or not changes:
        problems.append({"field": "changes", "issue": "required"})
    if problems:
        return _bad(problems)
    cur = store.get(TEMPLATES.name, id)
    if cur is None or "deleted_at" in cur:
        return failure("not_found")
    editable = CONTENT if cur["status"] == "draft" else ("is_active",)
    sets = {}
    for name, raw in changes.items():
        if name in KEY:
            problems.append({"field": name, "issue": "immutable"})
        elif name not in TEMPLATES.properties or name in TEMPLATES.read_only or name not in editable:
            problems.append({"field": name, "issue": "not_allowed"})
        else:
            value = clean(raw)
            if value is None:
                problems.append({"field": name, "issue": "required"})
            else:
                problems += check_field(TEMPLATES, name, value)
                sets[name] = value
    if problems:
        return _bad(problems)
    problems = _wording({**cur, **sets}) if cur["status"] == "draft" else []
    if problems:
        return _bad(problems)
    if expected_updated_at is not None and cur.get("updated_at") != expected_updated_at:
        return failure("conflict")
    stamp = stamp_update(actor, now)
    try:
        store.update(TEMPLATES.name, id, {**sets, **stamp}, (), expected_updated_at=cur["updated_at"], tx=tx)
    except DocMissing:
        return failure("not_found")
    except StaleUpdate:
        return failure("conflict")
    return success({"id": id, "changed": sorted(sets), "removed": [], "updated_at": stamp["updated_at"], "updated_by": actor})


def publish(store, id, actor, expected_updated_at=None, tx=None, now=None):   # noqa: A002
    """Turn a draft into the new standing record. Refused when the standing record changed since the draft was made."""
    problems = check_actor(actor) + _id_problem(id)
    if problems:
        return _bad(problems)
    cur = store.get(TEMPLATES.name, id)
    if cur is None or "deleted_at" in cur:
        return failure("not_found")
    if cur.get("status") != "draft":
        return _bad([{"field": "status", "issue": "not_allowed"}])
    if expected_updated_at is not None and cur.get("updated_at") != expected_updated_at:
        return failure("conflict")
    stand = standing(store, cur)
    if (stand["id"] if stand else None) != cur.get("previous_id"):
        return failure("conflict")
    problems = _wording(cur)
    if problems:
        return _bad(problems)
    stamp = utc_stamp(now)
    sets = {"status": "published", "version": stand["version"] + 1 if stand else 1,
            "published_at": stamp, "published_by": actor, "updated_at": stamp, "updated_by": actor}
    try:
        store.update(TEMPLATES.name, id, sets, (), expected_updated_at=cur["updated_at"], tx=tx)
    except DocMissing:
        return failure("not_found")
    except StaleUpdate:
        return failure("conflict")
    return success({"id": id, "version": sets["version"], "published_at": stamp, "published_by": actor})


def soft_delete(store, id, actor, tx=None, now=None):   # noqa: A002
    """Only a draft can be deleted: every published version is kept so a log entry's version can be explained."""
    problems = check_actor(actor) + _id_problem(id)
    if problems:
        return _bad(problems)
    cur = store.get(TEMPLATES.name, id)
    if cur is None or "deleted_at" in cur:
        return failure("not_found")
    if cur.get("status") != "draft":
        return _bad([{"field": "status", "issue": "not_allowed"}])
    stamp = utc_stamp(now)
    try:
        store.update(TEMPLATES.name, id, {"deleted_at": stamp, "deleted_by": actor, "updated_at": stamp, "updated_by": actor}, (),
                     expected_updated_at=cur["updated_at"], tx=tx)
    except DocMissing:
        return failure("not_found")
    except StaleUpdate:
        return failure("conflict")
    return success({"id": id, "deleted_at": stamp})
