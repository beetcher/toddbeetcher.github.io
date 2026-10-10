"""Service for scheduled classes: the rules that need another collection (venues), plus the venue guards.

    classes_service   create/get/list/update/soft_delete/set_review_summary for `scheduled_classes`, with:
                        * the venue exists and is not deleted                (venue_id:not_found)
                        * a room label needs a venue                         (venue_id:required)
                        * the room exists in that venue's rooms list         (venue_room_label:not_found)
                        * capacity_max is not above that room's max          (capacity_max:out_of_range)
                        * a scheduled or enrolling class needs an active venue (venue_id:inactive)
    * a class that holds registrations cannot be deleted         (conflict, id:in_use)
    (venues_service.py holds the matching guards on the venue side.)

Both modules expose the same function names as a handler file, so the dispatcher treats them alike. All the
checking of fields stays in the handler files; this file only reads the other collection and decides.
Problems name fields and never values (so the Console asks which classes are in the way with a normal list).
"""
from __future__ import annotations

from . import registration_assignments_crud as A
from . import scheduled_classes_crud as C
from . import venues_crud as V
from .schema_kit import failure

# What changes the answer of a class rule. An update touching none of these never reads the venue.
CLASS_CHECK_FIELDS = ("venue_id", "venue_room_label", "capacity_max", "status")
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
            elif isinstance(doc.get("capacity_max"), int) and doc["capacity_max"] > room.get("max_occupancy", 10 ** 9):
                problems.append({"field": "capacity_max", "issue": "out_of_range"})
        return problems
    return check


# ---- classes ---------------------------------------------------------------

def create(store, data, actor, source="dashboard", tx=None, now=None):
    return C.create(store, data, actor, source, tx=tx, now=now, check=make_class_check(store))


def get(store, id, include_deleted=False):
    return C.get(store, id, include_deleted)


def list(store, filters=None, **kw):  # noqa: A001
    return C.list(store, filters, **kw)


def update(store, id, changes, actor, expected_updated_at=None, tx=None, now=None):
    return C.update(store, id, changes, actor, expected_updated_at, tx=tx, now=now,
                    check=make_class_check(store), check_fields=CLASS_CHECK_FIELDS)


def soft_delete(store, id, actor, tx=None, now=None):
    if isinstance(id, str) and holding_assignments(store, id):
        return failure("conflict", [{"field": "id", "issue": "in_use"}])
    return C.soft_delete(store, id, actor, tx=tx, now=now)


def set_review_summary(store, id, review_count, average_rating, actor="system:reviews", tx=None, now=None):
    return C.set_review_summary(store, id, review_count, average_rating, actor, tx=tx, now=now)


def holding_assignments(store, class_id: str) -> list:
    """Decisions that still hold a place in this class (accepted, overflow, waitlisted and not replaced)."""
    return [d for d in A.current_only(A.for_class(store, class_id)) if d["status"] in A.HOLDING_STATUSES]


def live_classes_at(store, venue_id: str, limit: int = 200) -> list:
    """Classes that point at this venue and are not soft-deleted. A plain equality query (no composite index)."""
    docs = store.query(C.CLASSES.name, [("venue_id", "==", venue_id)], limit=limit)
    return [d for d in docs if "deleted_at" not in d]
