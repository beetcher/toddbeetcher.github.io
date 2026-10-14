"""One factory for the two rosters (instructor_roster, student_roster): handler and service together, because the
two rosters are the same shape (a pointer to an individual plus a few LAUNCH fields). A roster service file is two lines:

    R = Roster("instructor_roster"); create = R.create; ...

The ONLY refusals (Todd): the person exists and is not erased, one live entry per person per roster, status a known
value, the schema's type and length limits, hours that open before they close, individual_id never changes.
Nothing else blocks a save. Removing is a soft delete; the person can be added again.
Same function names as a handler file, plus create_with_person, update_with_person, EXPANDABLE.
"""
from __future__ import annotations

import builtins
import re

from . import individuals_service as IS
from . import location_links_crud as LK
from . import locations_crud as LOC
from .schema_kit import (
    UUID_PATTERN, check_actor, check_document, check_field, clean, drop_empty, failure,
    load_collection, stamp_create, stamp_update, success, utc_stamp,
)
from .store_errors import DocExists, DocMissing, StaleUpdate

SOURCES = ("dashboard", "import")
DEFAULT_LIMIT = 100
MAX_LIMIT = 200
SCAN = 500
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
PERSON_NEW = ("given_name", "family_name", "email", "phone")
PERSON_EDIT = ("given_name", "family_name", "email", "phone", "backup_email", "backup_phone", "prefers_email")
_LIST_FILTERS = ("status", "individual_id")


class _Abort(Exception):
    def __init__(self, result):
        self.result = result


def _dedupe(problems: list) -> list:
    seen, out = set(), []
    for p in problems:
        k = (p["field"], p["issue"])
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out


def _bad(problems: list):
    return failure("validation_failed", _dedupe(problems))


def _id_problem(id) -> list:
    return [] if isinstance(id, str) and UUID_PATTERN.match(id) else [{"field": "id", "issue": "invalid_format"}]


def _deleted(doc: dict) -> bool:
    return "deleted_at" in doc


def _prune(value):
    if isinstance(value, dict):
        return {k: _prune(v) for k, v in value.items() if v is not None}
    if isinstance(value, builtins.list):
        return [_prune(v) for v in value if v is not None]
    return value


def residence_state(store, individual_id):
    """The two-letter state of where the person lives, read from their live resides_at links (the primary one first), then
    the place's current addresses (the primary one first). None when there is no such address or it has no region.
    Derived on every read; nothing is stored."""
    got = LK.list(store, {"subject_id": individual_id}, limit=50)
    if not got.ok:
        return None
    links = [d for d in got.data["records"] if LK.is_live(d) and d.get("subject_type") == "individual" and d.get("relationship") == "resides_at"]
    links.sort(key=lambda d: not d.get("is_primary"))
    for link in links:
        loc = LOC.get(store, link["location_id"])
        if not loc.ok or loc.data.get("status") != "active":
            continue
        addrs = [a for a in loc.data.get("addresses", []) if a.get("usage") != "former"]
        addrs.sort(key=lambda a: not a.get("is_primary"))
        for a in addrs:
            region = str(a.get("region") or "").strip().upper()
            if re.fullmatch(r"[A-Z]{2}", region):
                return region
    return None


class Roster:
    EXPANDABLE = True

    def __init__(self, type_name: str):
        self.C = load_collection(type_name)
        self.type_name = type_name
        self.rule_fields = frozenset(f for f in ("availability",) if f in self.C.properties)

    # ---- helpers -----------------------------------------------------------
    def _normalize(self, name, value):
        value = clean(value)
        if name == "capabilities" and isinstance(value, builtins.list):
            seen, out = set(), []
            for v in value:
                if isinstance(v, str) and v.lower() not in seen:
                    seen.add(v.lower())
                    out.append(v)
                elif not isinstance(v, str):
                    out.append(v)
            value = out or None
        return _prune(value)

    def _rules(self, doc: dict) -> list:
        for h in doc.get("availability", []):
            if isinstance(h, dict) and "opens_at" in h and "closes_at" in h and h["opens_at"] >= h["closes_at"]:
                return [{"field": "availability", "issue": "out_of_range"}]
        return []

    def _live_entries(self, store, individual_id) -> builtins.list:
        return [d for d in store.query(self.C.name, [("individual_id", "==", individual_id)], limit=50) if not _deleted(d)]

    def _person_problems(self, store, individual_id):
        """(problems, resolved id). A merged person is followed to the survivor. A person who is gone or erased is not_found."""
        got = IS.get(store, individual_id)
        if not got.ok or got.data.get("status") == "erased":
            return [{"field": "individual_id", "issue": "not_found"}], individual_id
        return [], got.data["id"]

    def _person_view(self, store, pid):
        got = IS.get(store, pid)
        if not got.ok or got.data.get("status") == "erased":
            return {"id": pid, "unavailable": True}
        p = got.data
        view = {"id": p["id"], "display_name": p.get("display_name"), "status": p.get("status")}
        for k in ("given_name", "family_name", "email", "phone", "backup_email", "backup_phone", "prefers_email"):
            if k in p:
                view[k] = p[k]
        return view

    def expanded(self, store, rec: dict) -> dict:
        out = dict(rec)
        if rec.get("individual_id"):
            out["person"] = self._person_view(store, rec["individual_id"])
            if self.type_name == "instructor_roster":
                state = residence_state(store, rec["individual_id"])
                if state:
                    out["residence_state"] = state   # derived, never stored: only the state leaves, not the address
        return out

    # ---- create ------------------------------------------------------------
    def _create(self, store, data, actor, source, tx, now, person_known=False):
        problems = check_actor(actor)
        if source not in SOURCES:
            problems.append({"field": "source", "issue": "invalid_value"})
        if problems:
            return _bad(problems)
        if not isinstance(data, dict):
            return _bad([{"field": "body", "issue": "invalid_type"}])
        ro = [{"field": k, "issue": "not_allowed"} for k in data if k in self.C.read_only]
        if ro:
            return _bad(ro)
        doc = drop_empty({k: self._normalize(k, v) for k, v in data.items()})
        doc.setdefault("status", "active")
        problems = check_document(self.C, doc) or self._rules(doc)
        if problems:
            return _bad(problems)
        if not person_known:
            problems, resolved = self._person_problems(store, doc["individual_id"])
            if problems:
                return _bad(problems)
            doc["individual_id"] = resolved
            live = self._live_entries(store, resolved)
            if live:
                return _bad([{"field": "individual_id", "issue": "duplicate", "existing_id": live[0]["id"]}])
        doc = stamp_create(self.C, doc, actor, source, now)
        missing = [{"field": f, "issue": "required"} for f in self.C.server_required if f not in doc]
        if check_document(self.C, doc) + missing:
            return failure("server_error")
        try:
            store.create(self.C.name, doc["id"], doc, tx=tx)
        except DocExists:
            return failure("server_error")
        return success(doc)

    def create(self, store, data, actor, source="dashboard", tx=None, now=None):
        return self._create(store, data, actor, source, tx, now)

    def create_with_person(self, store, data, actor, person=None, source="dashboard", now=None):
        """Add a roster entry the way a person says it. Give data.individual_id for someone already in People, or `person`
        (given_name, family_name, email, phone) for someone new; the new person and the entry are saved together or not at all.
        Never matches a typed name to an existing person: the operator picks."""
        data = data if isinstance(data, dict) else {}
        if person is None:
            r = self._create(store, data, actor, source, None, now)
            return success({**self.expanded(store, r.data), "created_person": False}) if r.ok else r
        problems = []
        if data.get("individual_id") is not None:
            problems.append({"field": "person", "issue": "choose_one"})
        if not isinstance(person, dict):
            problems.append({"field": "person", "issue": "invalid_type"})
        else:
            problems += [{"field": "person." + k, "issue": "not_allowed"} for k in person if k not in PERSON_NEW]
        if problems:
            return _bad(problems)
        out = {}
        try:
            with store.transaction() as tx:
                p = IS.create(store, person, actor, source, tx=tx, now=now)
                if not p.ok:
                    raise _Abort(failure("validation_failed", [{"field": "person." + x["field"], "issue": x["issue"]} for x in p.problems]
                                         if p.code == "validation_failed" else p.problems))
                r = self._create(store, {**data, "individual_id": p.data["id"]}, actor, source, tx, now, person_known=True)
                if not r.ok:
                    raise _Abort(r)
                out["rec"] = r.data
        except _Abort as stop:
            return stop.result
        return success({**self.expanded(store, out["rec"]), "created_person": True})

    # ---- get / list --------------------------------------------------------
    def get(self, store, id, include_deleted=False, expand=False):  # noqa: A002
        problems = _id_problem(id)
        if problems:
            return _bad(problems)
        doc = store.get(self.C.name, id)
        if doc is None or (_deleted(doc) and not include_deleted):
            return failure("not_found")
        return success(self.expanded(store, doc) if expand else doc)

    def list(self, store, filters=None, order="-created_at", limit=DEFAULT_LIMIT, expand=False):  # noqa: A003
        """Optional filter: ONE of status or individual_id. Ordered by name when expanded, else newest first.
        Removed entries are left out. Needs no index: equality filters only, sorted here."""
        filters = dict(filters or {})
        problems = []
        for k, v in filters.items():
            if k not in _LIST_FILTERS:
                problems.append({"field": k, "issue": "not_supported"})
            else:
                problems += check_field(self.C, k, v)
        if len(filters) > 1:
            problems += [{"field": k, "issue": "not_supported"} for k in filters]
        if order not in ("-created_at", "created_at", "name"):
            problems.append({"field": "order", "issue": "not_supported"})
        if isinstance(limit, bool) or not isinstance(limit, int):
            problems.append({"field": "limit", "issue": "invalid_type"})
        if problems:
            return _bad(problems)
        limit = max(1, min(limit, MAX_LIMIT))
        docs = [d for d in store.query(self.C.name, [(k, "==", v) for k, v in filters.items()], limit=SCAN) if not _deleted(d)]
        if order == "name":
            docs = [self.expanded(store, d) for d in docs]
            docs.sort(key=lambda d: ((d.get("person", {}).get("display_name") or "~").lower(), d.get("created_at", "")))
        else:
            docs.sort(key=lambda d: d.get("created_at", ""), reverse=order.startswith("-"))
            if expand:
                docs = [self.expanded(store, d) for d in docs]
        docs = docs[:limit]
        if expand and order == "name":
            pass
        return success({"records": docs, "count": len(docs)})

    # ---- update ------------------------------------------------------------
    def update(self, store, id, changes, actor, expected_updated_at=None, tx=None, now=None):
        """Change some fields. None (or "") removes an optional field. Always one read, so a removed entry is not_found."""
        problems = check_actor(actor) + _id_problem(id)
        if expected_updated_at is not None and not (isinstance(expected_updated_at, str) and STAMP.match(expected_updated_at)):
            problems.append({"field": "expected_updated_at", "issue": "invalid_format"})
        if not isinstance(changes, dict) or not changes:
            problems.append({"field": "changes", "issue": "required"})
        if problems:
            return _bad(problems)
        sets, removals = {}, []
        for name, raw in changes.items():
            if name == "individual_id":
                problems.append({"field": name, "issue": "immutable"})
            elif name not in self.C.properties or name in self.C.read_only:
                problems.append({"field": name, "issue": "not_allowed"})
            else:
                value = self._normalize(name, raw)
                if value is None:
                    (problems.append({"field": name, "issue": "required"}) if name in self.C.required or name == "status"
                     else removals.append(name))
                else:
                    problems += check_field(self.C, name, value)
                    sets[name] = value
        if problems:
            return _bad(problems)
        cur = store.get(self.C.name, id)
        if cur is None or _deleted(cur):
            return failure("not_found")
        if expected_updated_at is not None and cur.get("updated_at") != expected_updated_at:
            return failure("conflict")
        merged = {**cur, **sets}
        for f in removals:
            merged.pop(f, None)
        problems = check_document(self.C, merged) or self._rules(merged)
        if problems:
            return _bad(problems)
        stamp = stamp_update(actor, now)
        try:
            store.update(self.C.name, id, {**sets, **stamp}, removals, expected_updated_at=cur["updated_at"], tx=tx)
        except DocMissing:
            return failure("not_found")
        except StaleUpdate:
            return failure("conflict")
        return success({"id": id, "changed": sorted(sets), "removed": sorted(removals),
                        "updated_at": stamp["updated_at"], "updated_by": actor})

    def update_with_person(self, store, id, changes, actor, person=None, expected_updated_at=None, now=None):
        """Save roster fields and the person's name and contact together or not at all. `changes` or `person` may be empty, not both."""
        problems = _id_problem(id)
        if not changes and not person:
            problems.append({"field": "changes", "issue": "required"})
        if person is not None and not isinstance(person, dict):
            problems.append({"field": "person", "issue": "invalid_type"})
        elif person:
            problems += [{"field": "person." + k, "issue": "not_allowed"} for k in person if k not in PERSON_EDIT]
        if problems:
            return _bad(problems)
        cur = store.get(self.C.name, id)
        if cur is None or _deleted(cur):
            return failure("not_found")
        try:
            with store.transaction() as tx:
                if changes:
                    r = self.update(store, id, changes, actor, expected_updated_at, tx=tx, now=now)
                    if not r.ok:
                        raise _Abort(r)
                if person:
                    p = IS.update(store, cur["individual_id"], person, actor, tx=tx, now=now)
                    if not p.ok:
                        raise _Abort(failure(p.code, [{"field": "person." + x["field"], "issue": x["issue"]} for x in p.problems]))
        except _Abort as stop:
            return stop.result
        return success(self.expanded(store, store.get(self.C.name, id)))

    # ---- soft delete -------------------------------------------------------
    def soft_delete(self, store, id, actor, tx=None, now=None):
        """Take the person off the roster. The record stays for history; they can be added again."""
        problems = check_actor(actor) + _id_problem(id)
        if problems:
            return _bad(problems)
        cur = store.get(self.C.name, id)
        if cur is None or _deleted(cur):
            return failure("not_found")
        stamp = utc_stamp(now)
        try:
            store.update(self.C.name, id, {"deleted_at": stamp, "deleted_by": actor, "updated_at": stamp, "updated_by": actor}, (),
                         expected_updated_at=cur["updated_at"], tx=tx)
        except DocMissing:
            return failure("not_found")
        except StaleUpdate:
            return failure("conflict")
        return success({"id": id, "deleted_at": stamp})
