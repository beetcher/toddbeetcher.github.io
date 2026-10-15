"""Service for scheduled classes: the rules that need another collection (venues), plus the venue guards.

    classes_service   create/get/list/update/soft_delete/set_review_summary for `scheduled_classes`, with:
                        * the venue exists and is not deleted                (venue_id:not_found)
                        * a room label needs a venue                         (venue_id:required)
                        * the room exists in that venue's rooms list         (venue_room_label:not_found)
                        * a scheduled or enrolling class needs an active venue (venue_id:inactive)
    * a class that holds registrations cannot be deleted         (conflict, id:in_use)
    (venues_service.py holds the matching guards on the venue side.)

Both modules expose the same function names as a handler file, so the dispatcher treats them alike. All the
checking of fields stays in the handler files; this file only reads the other collection and decides.
Problems name fields and never values (so the Console asks which classes are in the way with a normal list).
"""
from __future__ import annotations

from . import attendances_service as AT
from . import curriculums_crud as CU
from . import registration_assignments_crud as A
from . import scheduled_classes_crud as C
from . import venues_crud as V
from .roster_kit import _Abort
from .schema_kit import failure

# What changes the answer of a class rule. An update touching none of these never reads the venue.
CLASS_CHECK_FIELDS = ("venue_id", "venue_room_label", "status", "curriculum_id", "series_id", "session_number")
LIVE_STATUSES_NEEDING_ACTIVE_VENUE = ("scheduled", "enrolling")


def _find_room(venue: dict, label: str):
    want = str(label).strip().lower()
    for r in venue.get("rooms", []):
        if isinstance(r, dict) and str(r.get("label", "")).strip().lower() == want:
            return r
    return None


def make_class_check(store):
    """The rules that look at the venue, as one function(doc) -> problems."""
    def check(doc: dict) -> list:
        return _curriculum_series_problems(store, doc) + _venue_problems(store, doc)

    def _venue_problems(store, doc: dict) -> list:
        vid, label = doc.get("venue_id"), doc.get("venue_room_label")
        if label and not vid:
            return [{"field": "venue_id", "issue": "required"}]
        if not vid:
            return []
        got = V.get(store, vid)
        if not got.ok:
            return [{"field": "venue_id", "issue": "not_found"}]
        venue = got.data
        problems = []
        if doc.get("status") in LIVE_STATUSES_NEEDING_ACTIVE_VENUE and venue.get("status") != "active":
            problems.append({"field": "venue_id", "issue": "inactive"})
        if label:
            room = _find_room(venue, label)
            if room is None:
                problems.append({"field": "venue_room_label", "issue": "not_found"})
        return problems
    return check


def _curriculum_series_problems(store, doc: dict) -> list:
    """The curriculum exists (a removed one still counts, so the class stays editable); no two live classes in one series share a session number."""
    out = []
    cid = doc.get("curriculum_id")
    if cid and not CU.get(store, cid, include_deleted=True).ok:
        out.append({"field": "curriculum_id", "issue": "not_found"})
    sid, num = doc.get("series_id"), doc.get("session_number")
    if sid and num is not None:
        for other in store.query(C.CLASSES.name, [("series_id", "==", sid)], limit=200):
            if "deleted_at" not in other and other.get("id") != doc.get("id") and other.get("session_number") == num:
                out.append({"field": "session_number", "issue": "duplicate"})
                break
    return out


# ---- classes ---------------------------------------------------------------

def create(store, data, actor, source="dashboard", tx=None, now=None):
    return C.create(store, data, actor, source, tx=tx, now=now, check=make_class_check(store))


def get(store, id, include_deleted=False):
    return C.get(store, id, include_deleted)


def list(store, filters=None, **kw):  # noqa: A001
    return C.list(store, filters, **kw)


def update(store, id, changes, actor, expected_updated_at=None, tx=None, now=None):
    if tx is None and isinstance(changes, dict) and changes.get("status") == "cancelled" and isinstance(id, str):
        cur = store.get(C.CLASSES.name, id)
        if cur is not None and "deleted_at" not in cur and cur.get("status") != "cancelled":
            return _with_cascade(store, "class_cancelled", actor, now, lambda t: C.update(
                store, id, changes, actor, expected_updated_at, tx=t, now=now, check=make_class_check(store), check_fields=CLASS_CHECK_FIELDS), id)
    return C.update(store, id, changes, actor, expected_updated_at, tx=tx, now=now,
                    check=make_class_check(store), check_fields=CLASS_CHECK_FIELDS)


def soft_delete(store, id, actor, tx=None, now=None):
    if isinstance(id, str) and holding_assignments(store, id):
        return failure("conflict", [{"field": "id", "issue": "in_use"}])
    if tx is None and isinstance(id, str):
        cur = store.get(C.CLASSES.name, id)
        if cur is not None and "deleted_at" not in cur:
            return _with_cascade(store, "class_removed", actor, now, lambda t: C.soft_delete(store, id, actor, tx=t, now=now), id)
    return C.soft_delete(store, id, actor, tx=tx, now=now)


def _with_cascade(store, event_type, actor, now, change, class_id):
    """The class change and the cancelling of everyone's open attendance (with its journal) happen together or not at all."""
    cls, recs = store.get(C.CLASSES.name, class_id), AT.open_placements(store, class_id)      # as they are BEFORE the change
    try:
        with store.transaction() as t:
            r = change(t)
            if not r.ok:
                raise _Abort(r)
            n = AT.end_class(store, class_id, actor, event_type, t, now)
    except _Abort as stop:
        return stop.result
    if recs and cls is not None:
        AT.notify_class_ended(store, cls, recs, actor)       # only after the cancel is saved; a mail problem never undoes it
    return r


def set_review_summary(store, id, review_count, average_rating, actor="system:reviews", tx=None, now=None):
    return C.set_review_summary(store, id, review_count, average_rating, actor, tx=tx, now=now)


def holding_assignments(store, class_id: str) -> list:
    """Decisions that still hold a place in this class (accepted, overflow, waitlisted and not replaced)."""
    return [d for d in A.current_only(A.for_class(store, class_id)) if d["status"] in A.HOLDING_STATUSES]


def live_classes_at(store, venue_id: str, limit: int = 200) -> list:
    """Classes that point at this venue and are not soft-deleted. A plain equality query (no composite index)."""
    docs = store.query(C.CLASSES.name, [("venue_id", "==", venue_id)], limit=limit)
    return [d for d in docs if "deleted_at" not in d]
