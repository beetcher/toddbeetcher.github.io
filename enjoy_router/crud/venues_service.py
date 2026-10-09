"""Service for venues: the guards the venue schema asks for, on top of venues_crud (see classes_service.py).

    * a venue that live classes point at cannot be deleted   (conflict, id:in_use)
    * a room a live class uses cannot be removed, renamed, or shrunk below that class's capacity_max
                                                                (validation_failed, rooms:in_use)
Everything else passes straight through to the handler file. Same function names as a handler file.
"""
from __future__ import annotations

from . import venues_crud as V
from .classes_service import _find_room, live_classes_at
from .schema_kit import failure


def make_room_check(store, venue_id: str):
    def check(merged: dict) -> list:
        for c in live_classes_at(store, venue_id):
            if not c.get("venue_room_label"):
                continue
            room = _find_room(merged, c["venue_room_label"])
            if room is None or (isinstance(c.get("capacity_max"), int) and c["capacity_max"] > room.get("max_occupancy", 10 ** 9)):
                return [{"field": "rooms", "issue": "in_use"}]
        return []
    return check


def create(store, data, actor, source="dashboard", tx=None, now=None):
    return V.create(store, data, actor, source, tx=tx, now=now)


def get(store, id, include_deleted=False):
    return V.get(store, id, include_deleted)


def list(store, filters=None, **kw):  # noqa: A001
    return V.list(store, filters, **kw)


def update(store, id, changes, actor, expected_updated_at=None, tx=None, now=None):
    check = make_room_check(store, id) if isinstance(id, str) else None
    return V.update(store, id, changes, actor, expected_updated_at, tx=tx, now=now, check=check, check_fields=("rooms",))


def soft_delete(store, id, actor, tx=None, now=None):
    if isinstance(id, str) and live_classes_at(store, id, limit=1):
        return failure("conflict", [{"field": "id", "issue": "in_use"}])
    return V.soft_delete(store, id, actor, tx=tx, now=now)


def set_review_summary(store, id, review_count, average_rating, actor="system:reviews", tx=None, now=None):
    return V.set_review_summary(store, id, review_count, average_rating, actor, tx=tx, now=now)
