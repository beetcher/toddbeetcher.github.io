"""Handler and service for `attendances`: one person in one class, in one role, and where they stand (see ATTENDANCE_GUIDE.md).

The ONLY refusals: the person exists and is not erased (a merged person is followed), the class exists and is not deleted,
one live record per person per class, individual_id and scheduled_class_id never change, the schema's own limits.
Capacity never refuses. `assign` is the one-window flow: person (if new) + roster entry (if missing) + attendance, all or nothing.
Same function names as a handler file, plus assign and EXPANDABLE. list needs no index: one equality filter, sorted here.
"""
from __future__ import annotations

import builtins
import logging
import re
import secrets
from contextlib import contextmanager

from . import individuals_service as IS
from . import instructor_rosters_service as INS
from . import journal_events_crud as JR
from . import scheduled_classes_crud as CL
from . import student_rosters_service as STU
from .roster_kit import PERSON_NEW, _Abort
from .schema_kit import (
    UUID_PATTERN, check_actor, check_document, check_field, clean, drop_empty, failure,
    load_collection, stamp_create, stamp_update, success, utc_stamp,
)
from .store_errors import DocExists, DocMissing, StaleUpdate

ATT = load_collection("attendance")
REQUESTS = load_collection("registration_request")
EXPANDABLE = True
SOURCES = ("dashboard", "import")
DEFAULT_LIMIT = 100
MAX_LIMIT = 200
SCAN = 500
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_LIST_FILTERS = ("scheduled_class_id", "individual_id", "request_id")
_INDEX_FILTERS = _LIST_FILTERS
STUDENT = "student"
IMMUTABLE = ("individual_id", "scheduled_class_id")
HISTORY_MAX = 100
STATUS_OFF = frozenset({"declined", "withdrawn", "cancelled"})      # no longer a placement
NO_SEAT = STATUS_OFF | {"waitlisted"}                                 # does not hold a seat
OPEN = frozenset({"assigned", "waitlisted", "confirmed"})             # what a cancelled or deleted class cancels
SEND_STATUSES = ("assigned", "confirmed")
LOG = logging.getLogger("enjoy_router")


def _notify(store, attendance_id, actor, manual):
    """Ask the CMS to send the placement confirmation. Returns (comms Result, None), or (None, reason) when the placement is not eligible
    (nothing is tried, so nothing is logged). The CMS is told AFTER the placement is saved (R-4) and never raises (R-3)."""
    import comms
    from launch_comms import placement_context
    call, reason = placement_context.call_for(store, attendance_id, actor, manual=manual)
    if call is None:
        return None, reason
    return comms.notify(**call), None


def _auto_notify(store, rec, actor, now):
    """A student was just placed: the CMS sends the confirmation (never raises, never undoes the placement)."""
    import comms
    if not comms.is_configured() or rec.get("role") != STUDENT or rec.get("status") not in SEND_STATUSES:
        return
    try:
        _notify(store, rec["id"], actor, False)
    except Exception:   # a mail problem must never fail a placement; no details are logged
        LOG.warning("placement email failed attendance=%s", rec.get("id"))


def _bad(problems):
    seen, out = set(), []
    for p in problems:
        k = (p["field"], p["issue"])
        if k not in seen:
            seen.add(k)
            out.append(p)
    return failure("validation_failed", out)


def _id_problem(id):
    return [] if isinstance(id, str) and UUID_PATTERN.match(id) else [{"field": "id", "issue": "invalid_format"}]


def _deleted(doc):
    return "deleted_at" in doc


def _live_for(store, field, value):
    return [d for d in store.query(ATT.name, [(field, "==", value)], limit=SCAN) if not _deleted(d)]


def _class(store, class_id):
    doc = store.get(CL.CLASSES.name, class_id)
    return None if doc is None or _deleted(doc) else doc


_REF_ALPHABET = "BCDFGHJKLMNPQRSTVWXYZ23456789"   # no vowels, no 0 or 1: reads cleanly and is hard to guess


def _new_reference(store):
    for _ in range(20):
        ref = "ICDT-A-" + "".join(secrets.choice(_REF_ALPHABET) for _ in range(6))
        if not store.query(ATT.name, [("reference_number", "==", ref)], limit=1):
            return ref
    return "ICDT-A-" + "".join(secrets.choice(_REF_ALPHABET) for _ in range(8))


def _confirmation_of(store, request_id):
    """The confirmation number of a registration request, or None when the request is not found."""
    req = store.get(REQUESTS.name, request_id) if request_id else None
    return req.get("confirmation_number") if isinstance(req, dict) else None


def _history_entry(status, actor, now):
    return {"status": status, "at": utc_stamp(now), "by": actor}


@contextmanager
def _tx(store, tx):
    """Join the caller's transaction, or open one, so a change and its journal lines are written together."""
    if tx is not None:
        yield tx
    else:
        with store.transaction() as t:
            yield t


def _journal(store, event_type, actor, tx, now, **fields):
    return JR.record(store, {"event_type": event_type, **fields}, actor, tx=tx, now=now)


def _still_placed(store, request_id, excluding):
    """Does the request keep an active placement apart from the records in `excluding`? (A request is assigned when it does.)"""
    return any(d["id"] not in excluding and d.get("status") not in STATUS_OFF for d in _live_for(store, "request_id", request_id))


def _unassigned_if_left(store, request_id, class_id, excluding, actor, tx, now):
    if request_id and not _still_placed(store, request_id, excluding):
        _journal(store, "request_unassigned", actor, tx, now, request_id=request_id, scheduled_class_id=class_id)


# ---- create -----------------------------------------------------------------

def _create(store, data, actor, source, tx, now, person_known=False):
    problems = check_actor(actor)
    if source not in SOURCES:
        problems.append({"field": "source", "issue": "invalid_value"})
    if problems:
        return _bad(problems)
    if not isinstance(data, dict):
        return _bad([{"field": "body", "issue": "invalid_type"}])
    ro = [{"field": k, "issue": "not_allowed"} for k in data if k in ATT.read_only]
    if ro:
        return _bad(ro)
    doc = drop_empty({k: clean(v) for k, v in data.items()})
    doc.setdefault("status", "assigned")
    problems = check_document(ATT, doc)
    if problems:
        return _bad(problems)
    if not person_known:
        got = IS.get(store, doc["individual_id"])
        if not got.ok or got.data.get("status") == "erased":
            return _bad([{"field": "individual_id", "issue": "not_found"}])
        doc["individual_id"] = got.data["id"]
    if _class(store, doc["scheduled_class_id"]) is None:
        return _bad([{"field": "scheduled_class_id", "issue": "not_found"}])
    if not person_known:
        live = [d for d in _live_for(store, "individual_id", doc["individual_id"]) if d["scheduled_class_id"] == doc["scheduled_class_id"]]
        if live:
            return _bad([{"field": "individual_id", "issue": "duplicate", "existing_id": live[0]["id"]}])
    doc = stamp_create(ATT, doc, actor, source, now)
    number = _confirmation_of(store, doc.get("request_id"))
    if number:
        doc["confirmation_number"] = number
    doc["reference_number"] = _new_reference(store)
    doc["status_history"] = [_history_entry(doc["status"], actor, now)]
    missing = [f for f in ATT.server_required if f not in doc]
    if check_document(ATT, doc) or missing:
        return failure("server_error")
    try:
        with _tx(store, tx) as t:
            store.create(ATT.name, doc["id"], doc, tx=t)
            _journal(store, "placed", actor, t, now, request_id=doc.get("request_id"), scheduled_class_id=doc["scheduled_class_id"],
                     individual_id=doc["individual_id"], attendance_id=doc["id"], role=doc["role"], to_status=doc["status"])
    except DocExists:
        return failure("server_error")
    return success(doc)


def create(store, data, actor, source="dashboard", tx=None, now=None):
    r = _create(store, data, actor, source, tx, now)
    if r.ok and tx is None:
        _auto_notify(store, r.data, actor, now)
        fresh = store.get(ATT.name, r.data["id"])
        if fresh:
            return success(fresh)
    return r


_SEND_REASONS = {"not_found": "not_found", "not_a_student": "not_a_student", "not_placed": "not_placed", "class_not_found": "class_not_found",
                 "class_not_scheduled": "class_not_scheduled", "no_venue": "no_venue", "person_not_found": "not_found"}


def send_confirmation(store, id, actor, now=None):  # noqa: A002
    """Send the placement confirmation for one student record now, by hand (the CMS logs it; a hand send ignores duplicate protection).
    Returns what the CMS decided: status (sent, failed, unknown, not_sent, skipped), reason and channel."""
    import comms
    problems = check_actor(actor) + _id_problem(id)
    if problems:
        return _bad(problems)
    if not comms.is_configured():
        return _bad([{"field": "email", "issue": "not_enabled"}])
    cur = store.get(ATT.name, id)
    if cur is None or _deleted(cur):
        return failure("not_found")
    res, reason = _notify(store, id, actor, True)
    if res is None:
        return _bad([{"field": "id", "issue": _SEND_REASONS.get(reason, "not_allowed")}])
    return success({"id": id, "status": res.status, "reason": res.reason, "channel": res.channel, "log_id": res.log_id})


# ---- reading ----------------------------------------------------------------

def expanded(store, rec):
    out = dict(rec)
    if rec.get("individual_id"):
        out["person"] = INS.R._person_view(store, rec["individual_id"])
    c = store.get(CL.CLASSES.name, rec.get("scheduled_class_id", ""))
    if c is not None and not _deleted(c):
        out["class"] = {k: c[k] for k in ("id", "title", "starts_at", "time_zone", "status", "class_type", "venue_id", "capacity_max") if k in c}
    else:
        out["class"] = {"id": rec.get("scheduled_class_id"), "unavailable": True}
    return out


def get(store, id, include_deleted=False, expand=False):  # noqa: A002
    problems = _id_problem(id)
    if problems:
        return _bad(problems)
    doc = store.get(ATT.name, id)
    if doc is None or (_deleted(doc) and not include_deleted):
        return failure("not_found")
    return success(expanded(store, doc) if expand else doc)


def list(store, filters=None, order="-created_at", limit=DEFAULT_LIMIT, expand=False):  # noqa: A001
    """Optional ONE of scheduled_class_id, individual_id or request_id, and optionally `status` as well (status alone works too).
    Order -created_at or created_at. Removed records are left out."""
    filters = dict(filters or {})
    problems = []
    for k, v in filters.items():
        problems += [{"field": k, "issue": "not_supported"}] if k not in _LIST_FILTERS + ("status",) else check_field(ATT, k, v)
    index = [k for k in filters if k in _INDEX_FILTERS]
    if len(index) > 1:
        problems += [{"field": k, "issue": "not_supported"} for k in index]
    if order not in ("-created_at", "created_at"):
        problems.append({"field": "order", "issue": "not_supported"})
    if isinstance(limit, bool) or not isinstance(limit, int):
        problems.append({"field": "limit", "issue": "invalid_type"})
    if problems:
        return _bad(problems)
    key = index[0] if index else ("status" if "status" in filters else None)
    where = [(key, "==", filters[key])] if key else []
    docs = [d for d in store.query(ATT.name, where, limit=SCAN) if not _deleted(d)]
    if "status" in filters:
        docs = [d for d in docs if d.get("status") == filters["status"]]
    docs.sort(key=lambda d: d.get("created_at", ""), reverse=order.startswith("-"))
    docs = docs[:max(1, min(limit, MAX_LIMIT))]
    if expand:
        docs = [expanded(store, d) for d in docs]
    return success({"records": docs, "count": len(docs)})


# ---- update / delete --------------------------------------------------------

def update(store, id, changes, actor, expected_updated_at=None, tx=None, now=None):
    """Change role, order, status, request_id or notes. None (or "") removes an optional field. A status change is added to status_history."""
    problems = check_actor(actor) + _id_problem(id)
    if expected_updated_at is not None and not (isinstance(expected_updated_at, str) and STAMP.match(expected_updated_at)):
        problems.append({"field": "expected_updated_at", "issue": "invalid_format"})
    if not isinstance(changes, dict) or not changes:
        problems.append({"field": "changes", "issue": "required"})
    if problems:
        return _bad(problems)
    sets, removals = {}, []
    for name, raw in changes.items():
        if name in IMMUTABLE:
            problems.append({"field": name, "issue": "immutable"})
        elif name not in ATT.properties or name in ATT.read_only:
            problems.append({"field": name, "issue": "not_allowed"})
        else:
            value = clean(raw)
            if value is None:
                (problems.append({"field": name, "issue": "required"}) if name in ATT.required or name == "status" else removals.append(name))
            else:
                problems += check_field(ATT, name, value)
                sets[name] = value
    if problems:
        return _bad(problems)
    cur = store.get(ATT.name, id)
    if cur is None or _deleted(cur):
        return failure("not_found")
    if expected_updated_at is not None and cur.get("updated_at") != expected_updated_at:
        return failure("conflict")
    fields = dict(sets)
    if "request_id" in sets:
        number = _confirmation_of(store, sets["request_id"])
        (fields.__setitem__("confirmation_number", number) if number else removals.append("confirmation_number"))
    elif "request_id" in removals:
        removals.append("confirmation_number")
    if "status" in sets and sets["status"] != cur.get("status"):
        fields["status_history"] = (cur.get("status_history") or [])[-(HISTORY_MAX - 1):] + [_history_entry(sets["status"], actor, now)]
    stamp = stamp_update(actor, now)
    try:
        with _tx(store, tx) as t:
            store.update(ATT.name, id, {**fields, **stamp}, removals, expected_updated_at=cur["updated_at"], tx=t)
            if "status" in sets and sets["status"] != cur.get("status"):
                _journal(store, "status_changed", actor, t, now, request_id=cur.get("request_id"), scheduled_class_id=cur["scheduled_class_id"],
                         individual_id=cur["individual_id"], attendance_id=id, role=cur.get("role"), from_status=cur.get("status"), to_status=sets["status"])
                if sets["status"] in STATUS_OFF and cur.get("status") not in STATUS_OFF:
                    _unassigned_if_left(store, cur.get("request_id"), cur["scheduled_class_id"], {id}, actor, t, now)
    except DocMissing:
        return failure("not_found")
    except StaleUpdate:
        return failure("conflict")
    return success({"id": id, "changed": sorted(sets), "removed": sorted(removals),
                    "updated_at": stamp["updated_at"], "updated_by": actor})


def soft_delete(store, id, actor, tx=None, now=None):
    """For a mistake. A person who leaves is `withdrawn`, not deleted."""
    problems = check_actor(actor) + _id_problem(id)
    if problems:
        return _bad(problems)
    cur = store.get(ATT.name, id)
    if cur is None or _deleted(cur):
        return failure("not_found")
    stamp = utc_stamp(now)
    try:
        with _tx(store, tx) as t:
            store.update(ATT.name, id, {"deleted_at": stamp, "deleted_by": actor, "updated_at": stamp, "updated_by": actor}, (),
                         expected_updated_at=cur["updated_at"], tx=t)
            _journal(store, "removed", actor, t, now, request_id=cur.get("request_id"), scheduled_class_id=cur["scheduled_class_id"],
                     individual_id=cur["individual_id"], attendance_id=id, role=cur.get("role"), from_status=cur.get("status"))
            if cur.get("status") not in STATUS_OFF:
                _unassigned_if_left(store, cur.get("request_id"), cur["scheduled_class_id"], {id}, actor, t, now)
    except DocMissing:
        return failure("not_found")
    except StaleUpdate:
        return failure("conflict")
    return success({"id": id, "deleted_at": stamp})


# ---- assign: the one-window flow ---------------------------------------------

def _starting_status(store, cls, role):
    """assigned, or waitlisted for a student when the class already has as many seat-holding students as capacity_max."""
    if role != STUDENT:
        return "assigned"
    full = sum(1 for d in _live_for(store, "scheduled_class_id", cls["id"]) if d.get("role") == STUDENT and d.get("status") not in NO_SEAT)
    return "waitlisted" if full >= cls.get("capacity_max", 10 ** 9) else "assigned"


def end_class(store, class_id, actor, event_type, tx, now=None):
    """A class was cancelled or deleted: every open attendance (assigned, waitlisted, confirmed) becomes `cancelled`, each with a journal
    line, and a request left with no active placement gets a `request_unassigned` line. Writes join `tx`, the same transaction as the
    class change. People who already have an outcome or have left are untouched. Returns how many records were cancelled."""
    recs = [d for d in _live_for(store, "scheduled_class_id", class_id) if d.get("status") in OPEN]
    ids = {d["id"] for d in recs}
    for d in recs:
        hist = (d.get("status_history") or [])[-(HISTORY_MAX - 1):] + [_history_entry("cancelled", actor, now)]
        store.update(ATT.name, d["id"], {"status": "cancelled", "status_history": hist, **stamp_update(actor, now)}, (),
                     expected_updated_at=d["updated_at"], tx=tx)
        _journal(store, event_type, actor, tx, now, request_id=d.get("request_id"), scheduled_class_id=class_id, individual_id=d["individual_id"],
                 attendance_id=d["id"], role=d.get("role"), from_status=d["status"], to_status="cancelled")
    for rid in sorted({d["request_id"] for d in recs if d.get("request_id")}):
        _unassigned_if_left(store, rid, class_id, ids, actor, tx, now)
    return len(recs)


def assign(store, data, actor, person=None, source="dashboard", now=None):
    """Put a person in a class. data: scheduled_class_id, role, and individual_id (an existing person) OR `person` (a new one:
    given_name, family_name, email, phone); optional status, order, request_id, notes. Creates the person if new, adds them to the
    student or instructor roster if missing, and creates the record, together or not at all. Never matches a typed name to a person."""
    data = dict(data) if isinstance(data, dict) else {}
    problems = []
    if person is not None and data.get("individual_id") is not None:
        problems.append({"field": "person", "issue": "choose_one"})
    if person is not None and not isinstance(person, dict):
        problems.append({"field": "person", "issue": "invalid_type"})
    elif isinstance(person, dict):
        problems += [{"field": "person." + k, "issue": "not_allowed"} for k in person if k not in PERSON_NEW]
    if person is None and data.get("individual_id") is None:
        problems.append({"field": "individual_id", "issue": "required"})
    cid = data.get("scheduled_class_id")
    cls = _class(store, cid) if isinstance(cid, str) and UUID_PATTERN.match(cid) else None
    if cls is None and not any(p["field"] == "scheduled_class_id" for p in problems):
        problems.append({"field": "scheduled_class_id", "issue": "not_found" if cid else "required"})
    if data.get("role") not in ATT.properties["role"]["enum"]:
        problems.append({"field": "role", "issue": "required" if data.get("role") is None else "invalid_value"})
    if problems:
        return _bad(problems)
    roster = STU.R if data["role"] == STUDENT else INS.R
    out = {"created_roster_entry": False}
    try:
        with store.transaction() as tx:
            if person is not None:
                p = IS.create(store, person, actor, source, tx=tx, now=now)
                if not p.ok:
                    raise _Abort(failure("validation_failed", [{"field": "person." + x["field"], "issue": x["issue"]} for x in p.problems]
                                         if p.code == "validation_failed" else p.problems))
                pid, known = p.data["id"], True
            else:
                pid, known = data["individual_id"], False
                got = IS.get(store, pid)
                if not got.ok or got.data.get("status") == "erased":
                    raise _Abort(_bad([{"field": "individual_id", "issue": "not_found"}]))
                pid = got.data["id"]
            if known or not roster._live_entries(store, pid):
                r = roster._create(store, {"individual_id": pid}, actor, source, tx, now, person_known=True)
                if not r.ok:
                    raise _Abort(r)
                out["created_roster_entry"] = True
            body = {**data, "individual_id": pid}
            if not body.get("status"):
                body["status"] = _starting_status(store, cls, data["role"])
            r = _create(store, body, actor, source, tx, now, person_known=known)
            if not r.ok:
                raise _Abort(r)
            out["rec"] = r.data
    except _Abort as stop:
        return stop.result
    _auto_notify(store, out["rec"], actor, now)
    out["rec"] = store.get(ATT.name, out["rec"]["id"]) or out["rec"]
    return success({**expanded(store, out["rec"]), "created_person": person is not None, "created_roster_entry": out["created_roster_entry"]})
