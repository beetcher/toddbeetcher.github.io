"""CRUD handler for the `individuals` collection (schemas/individual.schema.json, INDIVIDUAL_GUIDE.md).
Same shape as venues_crud.py (the model handler file).

Rules of this file:
  * Plain functions called by services, in-process. Never an endpoint, never takes an HTTP request.
  * Validates with the standard checker through the kit. Who may do what (roles, sealed records) is a service's job.
  * Returns a Result. Problems name fields, never values.
  * `store` is any document store with get/create/update/query (MemoryDocStore now, Firestore later).
    `tx` is optional: when a service passes one, writes join its transaction.
  * Every update writes one record to `individual_history` (x_history: history_collection), in the same
    transaction as the change. The history holds the values before and after, so it is personal data and is
    erased with the individual.
  * Merge and erase are NOT here. They are their own handlers; a sender can never set status merged or erased.
"""
from __future__ import annotations

import builtins
import re
from datetime import date, datetime, timezone
from typing import Optional

from .schema_kit import (
    UUID_PATTERN, check_actor, check_document, clean, drop_empty, failure, load_collection,
    new_id, stamp_create, stamp_update, success, utc_stamp,
)
from .store_errors import DocExists, DocMissing, StaleUpdate

INDIVIDUALS = load_collection("individual")
HISTORY = INDIVIDUALS.type_name + "_history"  # "individual_history"; built with this handler

SOURCES = ("web_enjoy", "dashboard", "import")
SENDER_STATUSES = ("active", "inactive")
DEFAULT_LIMIT = 100
MAX_LIMIT = 200
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
UPPERCASE_FIELDS = tuple(f for f in ("birth_country", "death_country") if f in INDIVIDUALS.properties)
LOWERCASE_FIELDS = tuple(f for f in ("email", "backup_email") if f in INDIVIDUALS.properties)


# =============================================================================
# RULES BLOCK: everything specific to individuals that the schema cannot say
# =============================================================================

def parse_partial_date(text: str):
    """YYYY, YYYY-MM or YYYY-MM-DD -> (year, month|None, day|None) if it is a real calendar date, else None."""
    parts = text.split("-")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return None
    y = nums[0]
    m = nums[1] if len(nums) > 1 else None
    d = nums[2] if len(nums) > 2 else None
    if d is not None:
        try:
            date(y, m, d)
        except ValueError:
            return None
    return (y, m, d)


def _today(now: Optional[datetime]) -> date:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).date()


def _after_today(parsed, today: date) -> bool:
    """True when the partial date is certainly in the future (compared only at its own precision)."""
    y, m, d = parsed
    key = (y, m or 0, d or 0)
    return key > (today.year, today.month if m else 0, today.day if d else 0)


def _before(a: str, b: str) -> bool:
    """True when partial date `a` is certainly before `b`, compared at the precision both share."""
    n = min(len(a), len(b))
    return a[:n] < b[:n]


def is_minor_from(birth_date: Optional[str], now: Optional[datetime] = None) -> Optional[bool]:
    """Whether the person is under 18, from a partial birth date. None when there is no birth date.
    Cautious on purpose: when the precision cannot rule out being under 18, the answer is True."""
    if not birth_date:
        return None
    parsed = parse_partial_date(birth_date)
    if parsed is None:
        return None
    today = _today(now)
    y, m, d = parsed
    if d is not None:
        eighteenth = date(y + 18, m, d) if not (m == 2 and d == 29) else date(y + 18, 3, 1)
        return today < eighteenth
    if m is not None:
        # latest the birthday could be is the end of that month: under 18 until the 18th anniversary of the month's last day
        return (today.year, today.month) <= (y + 18, m)
    return today.year <= y + 18


def _dates_valid(doc: dict, now=None) -> list:
    today = _today(now)
    problems = []
    for f in ("birth_date", "death_date"):
        if f in doc:
            parsed = parse_partial_date(doc[f])
            if parsed is None:
                problems.append({"field": f, "issue": "invalid_format"})
            elif _after_today(parsed, today):
                problems.append({"field": f, "issue": "out_of_range"})
    if not problems and "birth_date" in doc and "death_date" in doc and _before(doc["death_date"], doc["birth_date"]):
        problems.append({"field": "death_date", "issue": "out_of_range"})
    return problems


def _display_name(doc: dict) -> str:
    if doc.get("name_to_use"):
        return doc["name_to_use"]
    return " ".join(p for p in (doc.get("given_name"), doc.get("family_name")) if p)


def _prune(value):
    if isinstance(value, dict):
        return {k: _prune(v) for k, v in value.items() if v is not None}
    if isinstance(value, builtins.list):
        return [_prune(v) for v in value if v is not None]
    return value


def _normalize_value(name: str, value):
    value = clean(value)
    if isinstance(value, str) and name in UPPERCASE_FIELDS:
        value = value.upper()
    if isinstance(value, str) and name in LOWERCASE_FIELDS:
        value = value.lower()
    return _prune(value)


def contact_order(doc: dict) -> list:
    """How to reach this person, in the order to try: a list of {"kind": "email"|"text", "to": value}. Derived, never refused.
    The preference is `prefers_email` (true email, false text); when absent, a person with only one contact prefers it, and
    a person with both prefers email. A preference pointing at a contact that is not there is ignored. A missing primary
    falls back to its backup. LAUNCH sends text messages only and never calls."""
    emails = [v for v in (doc.get("email"), doc.get("backup_email")) if v]
    phones = [v for v in (doc.get("phone"), doc.get("backup_phone")) if v]
    prefer_email = doc.get("prefers_email")
    if prefer_email is None or (prefer_email and not emails) or (prefer_email is False and not phones):
        prefer_email = bool(emails)
    first, second = (("email", emails), ("text", phones)) if prefer_email else (("text", phones), ("email", emails))
    return [{"kind": k, "to": v} for k, vals in (first, second) for v in vals]


def _default_retention(doc: dict, now=None) -> str:
    if doc.get("life_status") in ("deceased", "presumed_deceased"):
        return "deceased_review"
    if is_minor_from(doc.get("birth_date"), now):
        return "minor_review_at_18"
    return "active_participant"


def _run_rules(doc: dict, now=None) -> list:
    return _dates_valid(doc, now)


def _derive(doc: dict, now=None) -> None:
    """Fill the fields the server computes. Mutates doc."""
    doc["display_name"] = _display_name(doc)
    minor = is_minor_from(doc.get("birth_date"), now)
    if minor is None:
        doc.pop("is_minor", None)
    else:
        doc["is_minor"] = minor


def _bad(problems: list):
    seen, out = set(), []
    for p in problems:
        k = (p["field"], p["issue"])
        if k not in seen:
            seen.add(k)
            out.append(p)
    return failure("validation_failed", out)


def _id_problem(id) -> list:
    return [] if isinstance(id, str) and UUID_PATTERN.match(id) else [{"field": "id", "issue": "invalid_format"}]


def _is_deleted(doc: dict) -> bool:
    return "deleted_at" in doc


# =============================================================================
# create
# =============================================================================

def create(store, data, actor, source="dashboard", tx=None, now=None):
    problems = check_actor(actor)
    if source not in SOURCES:
        problems.append({"field": "source", "issue": "invalid_value"})
    if problems:
        return _bad(problems)
    if not isinstance(data, dict):
        return _bad([{"field": "body", "issue": "invalid_type"}])

    read_only = [{"field": k, "issue": "not_allowed"} for k in data if k in INDIVIDUALS.read_only]
    if read_only:
        return _bad(read_only)

    doc = drop_empty({k: _normalize_value(k, v) for k, v in data.items()})
    if "status" in doc and doc["status"] not in SENDER_STATUSES:
        return _bad([{"field": "status", "issue": "invalid_value"}])
    doc.setdefault("status", "active")
    doc.setdefault("life_status", "alive")
    problems = check_document(INDIVIDUALS, doc)
    if not problems:
        problems = _run_rules(doc, now)
    if problems:
        return _bad(problems)

    doc = stamp_create(INDIVIDUALS, doc, actor, source, now)
    _derive(doc, now)
    doc.setdefault("retention_class", _default_retention(doc, now))
    missing = [{"field": f, "issue": "required"} for f in INDIVIDUALS.server_required if f not in doc]
    if check_document(INDIVIDUALS, doc) + missing:  # our own bug, not the sender's: say nothing about fields
        return failure("server_error")
    try:
        store.create(INDIVIDUALS.name, doc["id"], doc, tx=tx)
    except DocExists:
        return failure("server_error")
    return success(doc)


# =============================================================================
# get / list
# =============================================================================

def get(store, id, include_deleted=False, follow_merged=True):
    """One individual. A merged record redirects to the individual it was folded into (up to 5 hops) unless
    follow_merged is False. An erased record comes back as its tombstone."""
    problems = _id_problem(id)
    if problems:
        return _bad(problems)
    doc = store.get(INDIVIDUALS.name, id)
    for _ in range(5):
        if doc is None or (_is_deleted(doc) and not include_deleted):
            return failure("not_found")
        if follow_merged and doc.get("status") == "merged" and doc.get("merged_into_id"):
            doc = store.get(INDIVIDUALS.name, doc["merged_into_id"])
            continue
        break
    else:
        return failure("server_error")
    return success(doc)


_LIST_FILTERS = ("status", "life_status", "is_minor")
_LIST_VALUES = {"status": INDIVIDUALS.properties["status"].get("enum"),
                "life_status": INDIVIDUALS.properties["life_status"].get("enum")}


def list(store, filters=None, order="display_name", limit=DEFAULT_LIMIT):  # noqa: A001  (the name is the contract)
    """Supported: no filter or ONE of status / life_status / is_minor, ordered by display_name; no filter ordered by
    -created_at. Anything else is `not_supported` (each combination needs an index). Soft-deleted records are left
    out after the query, and without a status filter so are merged and erased records, so a page can hold fewer
    than `limit` records."""
    filters = dict(filters or {})
    problems = []
    for k, v in filters.items():
        if k not in _LIST_FILTERS:
            problems.append({"field": k, "issue": "not_supported"})
        elif k == "is_minor":
            if not isinstance(v, bool):
                problems.append({"field": k, "issue": "invalid_type"})
        elif v not in _LIST_VALUES[k]:
            problems.append({"field": k, "issue": "invalid_value"})
    if len(filters) > 1:
        problems += [{"field": k, "issue": "not_supported"} for k in filters]
    if order not in ("display_name", "-created_at"):
        problems.append({"field": "order", "issue": "not_supported"})
    elif order == "-created_at" and filters:
        problems.append({"field": "order", "issue": "not_supported"})
    if isinstance(limit, bool) or not isinstance(limit, int):
        problems.append({"field": "limit", "issue": "invalid_type"})
    if problems:
        return _bad(problems)
    limit = max(1, min(limit, MAX_LIMIT))
    docs = store.query(INDIVIDUALS.name, [(k, "==", v) for k, v in filters.items()],
                       order_by=order.lstrip("-"), descending=order.startswith("-"), limit=limit)
    docs = [d for d in docs if not _is_deleted(d)]
    if "status" not in filters:
        docs = [d for d in docs if d.get("status") not in ("merged", "erased")]
    return success({"records": docs, "count": len(docs)})


# =============================================================================
# update
# =============================================================================

def update(store, id, changes, actor, expected_updated_at=None, tx=None, now=None):
    """Change some fields. A value of None (or "") removes an optional field.

    Always the whole-record path: the record is read once, the change is applied, the whole record is checked and the
    server fields (display_name, is_minor) are recomputed. A history record with the values before and after is
    written in the same transaction. A merged or erased record is locked (`conflict`).
    expected_updated_at: if given, the write is refused with `conflict` when the record changed since.
    """
    problems = check_actor(actor) + _id_problem(id)
    if expected_updated_at is not None and not (isinstance(expected_updated_at, str) and STAMP.match(expected_updated_at)):
        problems.append({"field": "expected_updated_at", "issue": "invalid_format"})
    if not isinstance(changes, dict) or not changes:
        problems.append({"field": "changes", "issue": "required"})
    if problems:
        return _bad(problems)

    set_fields: dict = {}
    removals: list = []
    for name, raw in changes.items():
        if name not in INDIVIDUALS.properties or name in INDIVIDUALS.read_only:
            problems.append({"field": name, "issue": "not_allowed"})
            continue
        value = _normalize_value(name, raw)
        if value is None:
            (problems.append({"field": name, "issue": "required"}) if name in INDIVIDUALS.required
             else removals.append(name))
        else:
            if name == "status" and value not in SENDER_STATUSES:
                problems.append({"field": name, "issue": "invalid_value"})
            set_fields[name] = value
    if problems:
        return _bad(problems)

    cur = store.get(INDIVIDUALS.name, id)
    if cur is None or _is_deleted(cur):
        return failure("not_found")
    if expected_updated_at is not None and cur.get("updated_at") != expected_updated_at:
        return failure("conflict")
    if cur.get("status") in ("merged", "erased"):
        return failure("conflict", [{"field": "status", "issue": "locked"}])

    merged = {**cur, **set_fields}
    for f in removals:
        merged.pop(f, None)
    merged.pop("display_name", None)
    problems = check_document_for_update(merged)
    if not problems:
        problems = _run_rules(merged, now)
    if problems:
        return _bad(problems)
    _derive(merged, now)

    stamp = stamp_update(actor, now)
    changed = sorted(set(set_fields) | set(removals))
    derived = {k: merged[k] for k in ("display_name", "is_minor") if k in merged}
    removed_derived = [k for k in ("is_minor",) if k not in merged and k in cur]
    before = {k: cur[k] for k in changed if k in cur}
    after = {k: merged[k] for k in changed if k in merged}
    history = {"id": new_id(), "individual_id": id, "changed_at": stamp["updated_at"], "changed_by": actor,
               "before": before, "after": after}
    try:
        if tx is not None:
            _write_update(store, id, {**set_fields, **derived, **stamp}, removals + removed_derived, cur["updated_at"], history, tx)
        else:
            with store.transaction() as own:
                _write_update(store, id, {**set_fields, **derived, **stamp}, removals + removed_derived, cur["updated_at"], history, own)
    except DocMissing:
        return failure("not_found")
    except StaleUpdate:
        return failure("conflict")
    return success({"id": id, "changed": sorted(set_fields), "removed": sorted(removals),
                    "updated_at": stamp["updated_at"], "updated_by": actor})


def check_document_for_update(merged: dict) -> list:
    """The stored record minus display_name (recomputed after the check) against the schema, with server fields present."""
    return check_document(INDIVIDUALS, merged)


def _write_update(store, id, fields, deletes, expected, history, tx):
    store.update(INDIVIDUALS.name, id, fields, deletes, expected_updated_at=expected, tx=tx)
    store.create(HISTORY, history["id"], history, tx=tx)


# =============================================================================
# soft delete
# =============================================================================

def soft_delete(store, id, actor, tx=None, now=None):
    """Mark deleted; the record stays. A service must first make sure nothing live points at this individual
    (set it inactive instead). Deleting twice is `not_found`. To remove personal data use the erase handler (later)."""
    problems = check_actor(actor) + _id_problem(id)
    if problems:
        return _bad(problems)
    cur = store.get(INDIVIDUALS.name, id)
    if cur is None or _is_deleted(cur):
        return failure("not_found")
    stamp = utc_stamp(now)
    fields = {"deleted_at": stamp, "deleted_by": actor, "updated_at": stamp, "updated_by": actor}
    try:
        store.update(INDIVIDUALS.name, id, fields, (), expected_updated_at=cur["updated_at"], tx=tx)
    except DocMissing:
        return failure("not_found")
    except StaleUpdate:
        return failure("conflict")
    return success({"id": id, "deleted_at": stamp})
