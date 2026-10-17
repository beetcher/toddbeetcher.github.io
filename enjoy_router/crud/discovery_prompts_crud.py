"""Handler for `discovery_prompts`: the instruction text sent to the AI, kept as data (see DISCOVERY_PROMPT_GUIDE.md).

Same linked-record pattern as message_templates_crud. `create` makes the FIRST draft for a finder; every later version starts with
`draft_from` (copy a published record into a draft whose previous_id is the standing record) and ends with `publish`. A draft is
edited in place with `update`; a published record is never edited. Only a draft can be deleted. Before a draft is saved or published
its text is checked: every {placeholder} must be one the core supplies, and curly braces are used for nothing else.
"""
from __future__ import annotations

from discovery import prompt as P
from launch_discovery import FINDER_KEYS, PROMPT_PLACEHOLDERS

from .discovery_kit import SCAN, STAMP, bad, id_problem, live
from .schema_kit import (check_actor, check_document, check_field, clean, drop_empty, failure, load_collection, stamp_create,
                         stamp_update, success, utc_stamp)
from .store_errors import DocExists, DocMissing, StaleUpdate

PROMPTS = load_collection("discovery_prompt")
COLLECTION = PROMPTS
SOURCES = ("dashboard", "import")
CONTENT = ("name", "text")
DEFAULT_LIMIT, MAX_LIMIT = 100, 200


def standing(store, rec):
    """The STANDING published record for rec's finder: published and not named as previous by another published record."""
    pub = [d for d in live(store, PROMPTS, finder_key=rec["finder_key"]) if d.get("status") == "published"]
    superseded = {d.get("previous_id") for d in pub}
    cur = [d for d in pub if d["id"] not in superseded]
    return max(cur, key=lambda d: d["version"]) if cur else None


def _draft(store, rec):
    found = [d for d in live(store, PROMPTS, finder_key=rec["finder_key"]) if d.get("status") == "draft"]
    return found[0] if found else None


def _wording(rec):
    return [{"field": "text", "issue": p["issue"]}
            for p in P.check_text(rec.get("text", ""), PROMPT_PLACEHOLDERS)]


def _finder(rec):
    return [] if rec.get("finder_key") in FINDER_KEYS else [{"field": "finder_key", "issue": "invalid_value"}]


def create(store, data, actor, source="dashboard", tx=None, now=None):
    problems = check_actor(actor)
    if source not in SOURCES:
        problems.append({"field": "source", "issue": "invalid_value"})
    if problems:
        return bad(problems)
    if not isinstance(data, dict):
        return bad([{"field": "body", "issue": "invalid_type"}])
    ro = [{"field": k, "issue": "not_allowed"} for k in data if k in PROMPTS.read_only]
    if ro:
        return bad(ro)
    doc = drop_empty({k: clean(v) for k, v in data.items()})
    problems = check_document(PROMPTS, {**doc, "status": "draft", "version": 1})
    problems = problems or _finder(doc) or _wording(doc)
    if problems:
        return bad(problems)
    if live(store, PROMPTS, finder_key=doc["finder_key"]):
        return bad([{"field": "finder_key", "issue": "duplicate"}])      # later versions start with draft_from
    doc = stamp_create(PROMPTS, {**doc, "status": "draft", "version": 1}, actor, source, now)
    try:
        store.create(PROMPTS.name, doc["id"], doc, tx=tx)
    except DocExists:
        return failure("server_error")
    return success(doc)


def draft_from(store, id, actor, tx=None, now=None):   # noqa: A002
    problems = check_actor(actor) + id_problem(id)
    if problems:
        return bad(problems)
    src = store.get(PROMPTS.name, id)
    if src is None or "deleted_at" in src:
        return failure("not_found")
    if src.get("status") != "published":
        return bad([{"field": "status", "issue": "not_allowed"}])
    if _draft(store, src):
        return failure("conflict")
    stand = standing(store, src)
    doc = {"finder_key": src["finder_key"], **{k: src[k] for k in CONTENT}, "status": "draft", "version": stand["version"] + 1,
           "previous_id": stand["id"]}
    doc = stamp_create(PROMPTS, doc, actor, "dashboard", now)
    if check_document(PROMPTS, doc):
        return failure("server_error")
    try:
        store.create(PROMPTS.name, doc["id"], doc, tx=tx)
    except DocExists:
        return failure("server_error")
    return success(doc)


def get(store, id, include_deleted=False):   # noqa: A002
    problems = id_problem(id)
    if problems:
        return bad(problems)
    doc = store.get(PROMPTS.name, id)
    if doc is None or ("deleted_at" in doc and not include_deleted):
        return failure("not_found")
    return success(doc)


def list(store, filters=None, order="finder_key", limit=DEFAULT_LIMIT):   # noqa: A001
    """Optional ONE filter: finder_key or status. Order finder_key or -created_at."""
    filters = dict(filters or {})
    problems = []
    for k, v in filters.items():
        problems += [{"field": k, "issue": "not_supported"}] if k not in ("finder_key", "status") else check_field(PROMPTS, k, v, allow_read_only=True)
    if len(filters) > 1:
        problems += [{"field": k, "issue": "not_supported"} for k in filters]
    if order not in ("finder_key", "-created_at"):
        problems.append({"field": "order", "issue": "not_supported"})
    if isinstance(limit, bool) or not isinstance(limit, int):
        problems.append({"field": "limit", "issue": "invalid_type"})
    if problems:
        return bad(problems)
    docs = [d for d in store.query(PROMPTS.name, [(k, "==", v) for k, v in filters.items()], limit=SCAN) if "deleted_at" not in d]
    if order == "finder_key":
        docs.sort(key=lambda d: (d.get("finder_key", ""), -d.get("version", 0), d.get("created_at", "")))
    else:
        docs.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    docs = docs[:max(1, min(limit, MAX_LIMIT))]
    return success({"records": docs, "count": len(docs)})


def update(store, id, changes, actor, expected_updated_at=None, tx=None, now=None):   # noqa: A002
    problems = check_actor(actor) + id_problem(id)
    if expected_updated_at is not None and not (isinstance(expected_updated_at, str) and STAMP.match(expected_updated_at)):
        problems.append({"field": "expected_updated_at", "issue": "invalid_format"})
    if not isinstance(changes, dict) or not changes:
        problems.append({"field": "changes", "issue": "required"})
    if problems:
        return bad(problems)
    cur = store.get(PROMPTS.name, id)
    if cur is None or "deleted_at" in cur:
        return failure("not_found")
    sets = {}
    for name, raw in changes.items():
        if name == "finder_key":
            problems.append({"field": name, "issue": "immutable"})
        elif name not in PROMPTS.properties or name in PROMPTS.read_only or name not in CONTENT or cur["status"] != "draft":
            problems.append({"field": name, "issue": "not_allowed"})
        else:
            value = clean(raw)
            if value is None:
                problems.append({"field": name, "issue": "required"})
            else:
                problems += check_field(PROMPTS, name, value)
                sets[name] = value
    if problems:
        return bad(problems)
    problems = _wording({**cur, **sets})
    if problems:
        return bad(problems)
    if expected_updated_at is not None and cur.get("updated_at") != expected_updated_at:
        return failure("conflict")
    stamp = stamp_update(actor, now)
    try:
        store.update(PROMPTS.name, id, {**sets, **stamp}, (), expected_updated_at=cur["updated_at"], tx=tx)
    except DocMissing:
        return failure("not_found")
    except StaleUpdate:
        return failure("conflict")
    return success({"id": id, "changed": sorted(sets), "removed": [], "updated_at": stamp["updated_at"], "updated_by": actor})


def publish(store, id, actor, expected_updated_at=None, tx=None, now=None):   # noqa: A002
    problems = check_actor(actor) + id_problem(id)
    if problems:
        return bad(problems)
    cur = store.get(PROMPTS.name, id)
    if cur is None or "deleted_at" in cur:
        return failure("not_found")
    if cur.get("status") != "draft":
        return bad([{"field": "status", "issue": "not_allowed"}])
    if expected_updated_at is not None and cur.get("updated_at") != expected_updated_at:
        return failure("conflict")
    stand = standing(store, cur)
    if (stand["id"] if stand else None) != cur.get("previous_id"):
        return failure("conflict")
    problems = _wording(cur)
    if problems:
        return bad(problems)
    stamp = utc_stamp(now)
    sets = {"status": "published", "version": stand["version"] + 1 if stand else 1,
            "published_at": stamp, "published_by": actor, "updated_at": stamp, "updated_by": actor}
    try:
        store.update(PROMPTS.name, id, sets, (), expected_updated_at=cur["updated_at"], tx=tx)
    except DocMissing:
        return failure("not_found")
    except StaleUpdate:
        return failure("conflict")
    return success({"id": id, "version": sets["version"], "published_at": stamp, "published_by": actor})


def soft_delete(store, id, actor, tx=None, now=None):   # noqa: A002
    """Only a draft can be deleted: every published version is kept so a run's prompt_version can be explained."""
    problems = check_actor(actor) + id_problem(id)
    if problems:
        return bad(problems)
    cur = store.get(PROMPTS.name, id)
    if cur is None or "deleted_at" in cur:
        return failure("not_found")
    if cur.get("status") != "draft":
        return bad([{"field": "status", "issue": "not_allowed"}])
    stamp = utc_stamp(now)
    try:
        store.update(PROMPTS.name, id, {"deleted_at": stamp, "deleted_by": actor, "updated_at": stamp, "updated_by": actor}, (),
                     expected_updated_at=cur["updated_at"], tx=tx)
    except DocMissing:
        return failure("not_found")
    except StaleUpdate:
        return failure("conflict")
    return success({"id": id, "deleted_at": stamp})
