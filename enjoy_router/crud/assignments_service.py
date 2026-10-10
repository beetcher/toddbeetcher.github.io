"""Service for registration assignments: the rules that need the request and the class, the automatic
decision, and the "Needs attention" queue. Same function names as a handler file, plus `suggest` and `queue`.

    create    puts a registration request into a scheduled class. If `status` is left out the SERVER decides:
                accepted   the party fits under the class target
                overflow   it fits between the target and the maximum (a party is never split)
                waitlisted over the maximum, waiting list on and not full
              If it cannot decide, nothing is written and the refusal names why (a conflict):
                class_closed (not enrolling), class_full, waitlist_full. The Console shows these on Home under
                "Needs attention" for a person to settle.
              If `status` is given (a person's decision) the server only checks that it fits: over_target,
                class_full, waitlist_off, waitlist_full, class_closed. declined and cancelled always go through.
              Other rules: the request and the class must exist (request_id:not_found, scheduled_class_id:not_found);
              seats cannot exceed the request's attendee_count (attendee_count:out_of_range); a private or group
              request may only go into the class made from it (scheduled_class_id:wrong_class); a second decision for the
              same request and class is a NEW record that replaces the first (previous_id), and an identical one
              is refused (status:unchanged).
    update    note and transaction ids only (the handler refuses changes to the decision: `immutable`).
    soft_delete  not allowed (cancel the assignment instead): id:not_allowed.
    suggest   what one touch would do for one request, without writing anything.
    queue     the state of each recent request (assigned, ready, needs_attention, no_class, closed).

After each create the class's registered_count (accepted + overflow seats) and waitlist_count are rewritten
from the decisions that stand, in the same transaction as the new record. The request's own processing_status
is not touched (a later step).

Limitation: two decisions for one class written at the same instant could both pass the seat check. There is one
operator today; a counter transaction is the fix when there are more.
"""
from __future__ import annotations

from . import registration_assignments_crud as A
from . import scheduled_classes_crud as C
from .schema_kit import UUID_PATTERN, failure, load_collection, success

REQUESTS = load_collection("registration_request")
PARTY_TYPES = ("private", "group")
QUEUE_REQUESTS = 100
QUEUE_ASSIGNMENTS = 500


def _uuid(v) -> bool:
    return isinstance(v, str) and bool(UUID_PATTERN.match(v))


def _live(doc):
    return doc if doc is not None and "deleted_at" not in doc else None


def get_request(store, request_id):
    return _live(store.get(REQUESTS.name, request_id)) if _uuid(request_id) else None


def get_class(store, class_id):
    got = C.get(store, class_id) if _uuid(class_id) else None
    return got.data if got is not None and got.ok else None


# ---- seat arithmetic ---------------------------------------------------------

def seats_taken(current: list, exclude_id=None) -> tuple:
    """(registered, waiting) in people, from the decisions that stand."""
    reg = sum(d["attendee_count"] for d in current if d["id"] != exclude_id and d["status"] in A.SEAT_STATUSES)
    wait = sum(d["attendee_count"] for d in current if d["id"] != exclude_id and d["status"] == "waitlisted")
    return reg, wait


def judge(cls: dict, seats: int, registered: int, waiting: int):
    """The server's own decision: (status, None) or (None, why_not)."""
    if cls.get("status") != "enrolling":
        return None, "class_closed"
    if registered + seats <= cls["capacity_target"]:
        return "accepted", None
    if registered + seats <= cls["capacity_max"]:
        return "overflow", None
    if cls.get("is_waitlist_enabled"):
        cap = cls.get("waitlist_max")
        if cap is not None and waiting + seats > cap:
            return None, "waitlist_full"
        return "waitlisted", None
    return None, "class_full"


def verify(cls: dict, status: str, seats: int, registered: int, waiting: int):
    """A person's chosen status: None if it fits, else why not."""
    if status in ("declined", "cancelled"):
        return None
    if cls.get("status") != "enrolling":
        return "class_closed"
    if status == "accepted":
        return None if registered + seats <= cls["capacity_target"] else "over_target"
    if status == "overflow":
        return None if registered + seats <= cls["capacity_max"] else "class_full"
    if not cls.get("is_waitlist_enabled"):
        return "waitlist_off"
    cap = cls.get("waitlist_max")
    return "waitlist_full" if cap is not None and waiting + seats > cap else None


# ---- create ------------------------------------------------------------------

class _Abort(Exception):
    """Raised inside the transaction to throw the whole write away."""


def _refuse(code, field, issue):
    return failure(code, [{"field": field, "issue": issue}])


def create(store, data, actor, source="dashboard", tx=None, now=None):
    if not isinstance(data, dict) or not _uuid(data.get("request_id")) or not _uuid(data.get("scheduled_class_id")):
        return A.create(store, data, actor, source, tx=tx, now=now, server_fields={"program_slug": "launch"})
    rid, cid = data["request_id"], data["scheduled_class_id"]
    request = get_request(store, rid)
    if request is None:
        return _refuse("validation_failed", "request_id", "not_found")
    cls = get_class(store, cid)
    if cls is None:
        return _refuse("validation_failed", "scheduled_class_id", "not_found")
    if request.get("registration_type") in PARTY_TYPES and cls.get("source_request_id") != rid:
        return _refuse("validation_failed", "scheduled_class_id", "wrong_class")

    seats = data.get("attendee_count", request["attendee_count"])
    if isinstance(seats, bool) or not isinstance(seats, int):
        return A.create(store, data, actor, source, tx=tx, now=now, server_fields={"program_slug": cls["program_slug"]})
    if seats > request["attendee_count"]:
        return _refuse("validation_failed", "attendee_count", "out_of_range")

    current = A.current_only(A.for_class(store, cid))
    prior = next((d for d in current if d["request_id"] == rid), None)
    registered, waiting = seats_taken(current, prior["id"] if prior else None)

    status = data.get("status")
    if status is None:
        status, why = judge(cls, seats, registered, waiting)
        if why:
            return _refuse("conflict", "status", why)
    elif status in ("accepted", "overflow", "waitlisted", "declined", "cancelled"):
        why = verify(cls, status, seats, registered, waiting)
        if why:
            return _refuse("conflict", "status", why)
    # an invalid status word falls through; the handler reports it

    if prior and prior["status"] == status and prior["attendee_count"] == seats:
        return _refuse("validation_failed", "status", "unchanged")

    new_data = {**data, "status": status, "attendee_count": seats}
    extra = {"program_slug": cls["program_slug"]}
    if prior:
        extra["previous_id"] = prior["id"]

    def write(t):
        res = A.create(store, new_data, actor, source, tx=t, now=now, server_fields=extra)
        if not res.ok:
            return res
        others = [d for d in current if not prior or d["id"] != prior["id"]]
        reg, wait = seats_taken(others + [res.data])
        counted = C.set_registration_counts(store, cid, reg, wait, "system:assignments", tx=t, now=now)
        if not counted.ok:
            raise _Abort()  # the new record and the counts go in together or not at all
        return res

    try:
        if tx is not None:
            return write(tx)
        with store.transaction() as t:
            return write(t)
    except _Abort:
        return failure("server_error")


def get(store, id, include_deleted=False):
    return A.get(store, id, include_deleted)


def list(store, filters=None, **kw):  # noqa: A001
    return A.list(store, filters, **kw)


def update(store, id, changes, actor, expected_updated_at=None, tx=None, now=None):
    return A.update(store, id, changes, actor, expected_updated_at, tx=tx, now=now)


def soft_delete(store, id, actor, tx=None, now=None):
    return _refuse("validation_failed", "id", "not_allowed")


# ---- suggest and queue -------------------------------------------------------

def _item(request: dict) -> dict:
    return {"request_id": request["id"], "confirmation_number": request.get("confirmation_number"),
            "first_name": request.get("first_name"), "last_name": request.get("last_name"),
            "registration_type": request.get("registration_type"), "attendee_count": request.get("attendee_count"),
            "created_at": request.get("created_at")}


def _plan(store, request: dict, mine_current: list, current_by_class, class_cache: dict) -> dict:
    """The state of one request. `mine_current`: the decisions that stand for it. `current_by_class(class_id)`:
    the decisions that stand for a class. `class_cache`: class_id -> class or None, filled as we go."""
    item = _item(request)

    def klass(cid):
        if cid not in class_cache:
            class_cache[cid] = get_class(store, cid)
        return class_cache[cid]

    holding = [d for d in mine_current if d["status"] in A.HOLDING_STATUSES]
    if holding:
        d = holding[0]
        cls = klass(d["scheduled_class_id"])
        return {**item, "state": "assigned", "status": d["status"], "assignment_id": d["id"], "seats": d["attendee_count"],
                "scheduled_class_id": d["scheduled_class_id"], "class_title": (cls or {}).get("title")}
    if mine_current:  # declined or cancelled stands: a person has settled it
        return {**item, "state": "closed", "status": mine_current[0]["status"], "assignment_id": mine_current[0]["id"]}

    rid = request["id"]
    if request.get("registration_type") in PARTY_TYPES:
        made = [c for c in store.query(C.CLASSES.name, [("source_request_id", "==", rid)], limit=5) if "deleted_at" not in c]
        if not made:
            return {**item, "state": "no_class", "reason": "no_class_yet"}
        cid = made[0]["id"]
    else:
        cid = request.get("scheduled_class_id")
        if not cid:
            return {**item, "state": "no_class", "reason": "no_class_fits"}
    cls = klass(cid)
    if cls is None:
        return {**item, "state": "needs_attention", "reason": "class_not_found", "scheduled_class_id": cid}
    registered, waiting = seats_taken(current_by_class(cid))
    status, why = judge(cls, request["attendee_count"], registered, waiting)
    base = {**item, "scheduled_class_id": cid, "class_title": cls.get("title")}
    if why:
        return {**base, "state": "needs_attention", "reason": why}
    return {**base, "state": "ready", "status": status, "seats": request["attendee_count"]}


def suggest(store, request_id):
    """What one touch would do for this request. Writes nothing."""
    request = get_request(store, request_id)
    if request is None:
        return failure("not_found")
    mine = A.current_only(A.for_request(store, request_id))
    return success(_plan(store, request, mine, lambda cid: A.current_only(A.for_class(store, cid)), {}))


def queue(store, limit=QUEUE_REQUESTS):
    """The state of the newest requests (default 100), newest first, and counts of each state."""
    if isinstance(limit, bool) or not isinstance(limit, int):
        return failure("validation_failed", [{"field": "limit", "issue": "invalid_type"}])
    limit = max(1, min(limit, 200))
    requests = [r for r in store.query(REQUESTS.name, [], order_by="created_at", descending=True, limit=limit)
                if "deleted_at" not in r]
    current = A.current_only(store.query(A.ASSIGNMENTS.name, [], order_by="created_at", descending=True,
                                         limit=QUEUE_ASSIGNMENTS))
    by_request: dict = {}
    by_class: dict = {}
    for d in current:
        by_request.setdefault(d["request_id"], []).append(d)
        by_class.setdefault(d["scheduled_class_id"], []).append(d)
    cache: dict = {}
    items = [_plan(store, r, by_request.get(r["id"], []), lambda cid: by_class.get(cid, []), cache) for r in requests]
    counts = {"assigned": 0, "ready": 0, "needs_attention": 0, "no_class": 0, "closed": 0}
    for it in items:
        counts[it["state"]] += 1
    return success({"items": items, "counts": counts})
