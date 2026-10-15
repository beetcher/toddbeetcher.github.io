"""Watches a change that may alter what people in a class are told (Stage 2 of the change notices, Todd 2026-10-15: notify abundantly).

Usage, in a service that changes a class, a class's instructors, a venue or a place:

    done = change_watch.class_watch(store, class_id)        # BEFORE the change: remembers how the class reads now
    ... make the change, commit ...
    done(actor, stamp)                                       # AFTER the commit: tells everyone the difference touches

Everything here is best effort: it never raises and never undoes the change (CMS rules R-3, R-4). When the CMS is not configured the
watch costs nothing (no queries). One message per person per save: the notices are built from the class as it stood before and as it
stands after, so a save that changes the date and the room is one message.
"""
from __future__ import annotations

import logging

from . import location_links_crud as LK
from . import scheduled_classes_crud as CL

LOG = logging.getLogger("enjoy_router")
INSTRUCTOR_ROLES = ("primary_instructor", "instructor")


def _on() -> bool:
    import comms
    return comms.is_configured()


def _noop(actor, stamp, skip=()):
    return None


def _states(store, class_ids):
    from launch_comms import change_context as CC
    out = {}
    for cid in class_ids:
        s = CC.class_state(store, cid)
        if s is not None:
            out[cid] = s
    return out


def _tell(store, before_states, class_ids, actor, stamp, skip):
    from crud import attendances_service as AT
    from launch_comms import change_context as CC
    for cid in class_ids:
        after = CC.class_state(store, cid)
        before = before_states.get(cid)
        if before is None and after is not None:
            AT._send_notices("class_scheduled_items", store, cid, actor)           # first time the class has a start time
        elif before is not None and after is not None:
            AT._send_notices("class_changed_items", store, before, after, actor, stamp, tuple(skip))


def class_watch(store, class_id):
    """Watch one class. Returns done(actor, stamp, skip=()) to call after the change is committed."""
    try:
        if not _on():
            return _noop
        ids = [class_id]
        before = _states(store, ids)
    except Exception:
        LOG.warning("change watch (class) could not start")
        return _noop

    def done(actor, stamp, skip=()):
        try:
            _tell(store, before, ids, actor, stamp, skip)
        except Exception:
            LOG.warning("change watch (class) failed")
    return done


def venue_class_ids(store, venue_ids):
    """Live classes that point at any of these venues (scheduled or enrolling; class_state drops the rest)."""
    ids = []
    for vid in venue_ids:
        for d in store.query(CL.CLASSES.name, [("venue_id", "==", vid)], limit=200):
            if "deleted_at" not in d and d["id"] not in ids:
                ids.append(d["id"])
    return ids


def venue_watch(store, venue_ids):
    """Watch every live class at these venues (a venue's name or place is about to change)."""
    try:
        if not _on():
            return _noop
        ids = venue_class_ids(store, list(venue_ids))
        before = _states(store, ids)
    except Exception:
        LOG.warning("change watch (venue) could not start")
        return _noop

    def done(actor, stamp, skip=()):
        try:
            _tell(store, before, ids, actor, stamp, skip)
        except Exception:
            LOG.warning("change watch (venue) failed")
    return done


def location_watch(store, location_id):
    """Watch every class at every venue linked to this place (its address or name is about to change)."""
    try:
        if not _on():
            return _noop
        links = [l for l in store.query(LK.LINKS.name, [("location_id", "==", location_id)], limit=200)
                 if LK.is_live(l) and l.get("subject_type") == "venue"]
        return venue_watch(store, [l["subject_id"] for l in links])
    except Exception:
        LOG.warning("change watch (location) could not start")
        return _noop
