"""The facts and the calls for the change notices: class_cancelled, placement_ended and participant_left (Stage 1 of the change notices), and the placement notices instructor_placed and students_added.

Rule (Todd, 2026-10-15): notification is cheap, an annoyed stakeholder is expensive. When a material change is made to a student, an
instructor or a class, everyone it touches is told. A guardian may be added later as one more recipient.

`class_view` works out the facts about the class; the three `*_items` functions return lists of arguments for comms.notify (CMS rule R-2).
Nothing here sends anything, reads the log or renders a word of the message: wording and sending are the CMS's job.
"""
from __future__ import annotations

from datetime import timedelta
from urllib.parse import quote_plus

from crud import individuals_service as IS
from crud import scheduled_classes_crud as CL
from crud import venues_service as VS

from .placement_context import ATT_NAME, OFF, _addr_line, _parse_utc, _stamp, _when_text

INSTRUCTOR_ROLES = ("primary_instructor", "instructor")
SEATED = ("assigned", "confirmed")            # holds a seat: its leaving matters to the instructors
HOW = {"declined": "declined their place", "withdrawn": "withdrew", "cancelled": "is no longer scheduled", "removed": "was removed"}


def audience_of(role):
    if role == "student":
        return "student"
    return "instructor" if role in INSTRUCTOR_ROLES else None


def _deleted(doc):
    return "deleted_at" in doc


def _person(store, individual_id):
    got = IS.get(store, individual_id)
    return got.data if got.ok and got.data.get("status") != "erased" else None


def _first_name(person):
    return (person or {}).get("given_name") or (person or {}).get("display_name") or "there"


def class_view(store, cls):
    """The class facts every change notice shares, or None when the class has no usable start time (nothing sensible to say).
    The class may be cancelled or deleted: that is the point."""
    start = _parse_utc((cls or {}).get("starts_at"))
    if start is None:
        return None
    venue = VS.get(store, cls["venue_id"], expand=True) if cls.get("venue_id") else None
    v = venue.data if venue is not None and venue.ok else {}
    place = v.get("place") or {}
    address = _addr_line(place.get("address"))
    end = start + timedelta(minutes=int(cls.get("duration_minutes") or 60))
    tzname = cls.get("time_zone") or place.get("time_zone") or "America/Denver"
    day, span, short = _when_text(start, end, tzname)
    venue_name, room = v.get("name") or "", cls.get("venue_room_label") or ""
    where = " · ".join(x for x in (venue_name, room) if x)
    maps = ("https://www.google.com/maps/search/?api=1&query=" + quote_plus(", ".join(x for x in (venue_name, address) if x))
            if (venue_name or address) else "")
    facts = {"title": cls.get("title") or "Your session", "start_utc": _stamp(start), "end_utc": _stamp(end), "time_zone": tzname,
             "when_day": day, "when_span": span, "when_short": short}
    optional = {"venue": venue_name, "room": room, "where": where, "address": address, "map_url": maps}
    facts.update({k: val for k, val in optional.items() if val})
    return facts


def _event(rec):
    """How many times this placement's status has changed so far: part of the duplicate key, so a person who is placed, leaves, is
    placed again and leaves again is told both times, while a repeated call for the same change is not sent twice."""
    return len(rec.get("status_history") or [])


def _item(kind, audience, individual_id, facts, att, actor, event):
    refs = {"attendance_id": att["id"], "scheduled_class_id": att["scheduled_class_id"]}
    if att.get("request_id"):
        refs["request_id"] = att["request_id"]      # lets the Messages station show the confirmation number
    return dict(kind=kind, recipient={"type": "individual", "individual_id": individual_id}, context=facts, by=actor, trigger="automatic",
                refs=refs, audience=audience,
                dedupe_key=f"{kind}:{individual_id}:{att['id']}:{event}"[:300])


def instructor_placed_items(store, rec, actor, via_request_id=None):
    """An instructor was just placed (assigned or confirmed): told they are assigned to teach, with a calendar file (P-41)."""
    cls = store.get(CL.CLASSES.name, rec.get("scheduled_class_id", ""))
    base = class_view(store, cls) if cls is not None else None
    if base is None or rec.get("role") not in INSTRUCTOR_ROLES or rec.get("status") not in SEATED:
        return []
    facts = {**base, "name": _first_name(_person(store, rec["individual_id"])), "uid": rec["id"],
             "role_word": "lead instructor" if rec.get("role") == "primary_instructor" else "instructor"}
    item = _item("instructor_placed", "instructor", rec["individual_id"], facts, rec, actor, _event(rec))
    if via_request_id:      # placed as part of putting a request in a class: the log entry carries that request's number (not stored on the instructor's record)
        item["refs"] = {**item["refs"], "request_id": via_request_id}
    return [item]


def _full_name(person):
    p = person or {}
    return p.get("display_name") or " ".join(x for x in (p.get("given_name"), p.get("family_name")) if x) or "A student"


def _and(names):
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def students_added_items(store, recs, actor):
    """`recs`: the student records placed together (one request, or one person) in ONE class. Every instructor placed in that class
    is told once, with everyone listed: one message per placement, not one per student."""
    import hashlib
    recs = [r for r in recs if r.get("role") == "student" and r.get("status") in SEATED + ("waitlisted",)]
    if not recs:
        return []
    cls = store.get(CL.CLASSES.name, recs[0].get("scheduled_class_id", ""))
    base = class_view(store, cls) if cls is not None else None
    if base is None:
        return []
    seated = [_full_name(_person(store, r["individual_id"])) for r in recs if r["status"] in SEATED]
    waiting = [_full_name(_person(store, r["individual_id"])) for r in recs if r["status"] == "waitlisted"]
    parts = []
    if seated:
        parts.append(f"{_and(seated)} {'was' if len(seated) == 1 else 'were'} added to your class.")
    if waiting:
        parts.append(f"{_and(waiting)} {'is' if len(waiting) == 1 else 'are'} on the waiting list.")
    facts = {k: v for k, v in base.items() if k in ("title", "when_day", "when_span", "when_short", "time_zone", "venue", "room", "where", "address")}
    facts["summary"] = " ".join(parts)
    cap = (cls or {}).get("capacity_max")
    if isinstance(cap, int) and cap > 0:
        taken = sum(1 for d in store.query(ATT_NAME, [("scheduled_class_id", "==", recs[0]["scheduled_class_id"])], limit=200)
                    if not _deleted(d) and d.get("role") == "student" and d.get("status") not in OFF and d.get("status") != "waitlisted")
        facts["seats"] = f"{taken} of {cap} seats taken"
    digest = hashlib.sha1(":".join(sorted(r["id"] for r in recs)).encode()).hexdigest()[:20]
    out = []
    for d in store.query(ATT_NAME, [("scheduled_class_id", "==", recs[0]["scheduled_class_id"])], limit=200):
        if _deleted(d) or d.get("status") in OFF or d.get("role") not in INSTRUCTOR_ROLES:
            continue
        item = _item("students_added", "instructor", d["individual_id"], {**facts, "name": _first_name(_person(store, d["individual_id"]))}, recs[0], actor, 0)
        item["dedupe_key"] = f"students_added:{d['individual_id']}:{digest}"
        item["refs"] = {k: v for k, v in item["refs"].items() if k != "attendance_id"}   # about several people: not filed under any one student's row
        out.append(item)
    return out


def class_cancelled_items(store, cls, recs, actor):
    """One class_cancelled call for every placement the cancel ended (`recs` are the records as they were BEFORE the cancel)."""
    base = class_view(store, cls)
    if base is None:
        return []
    out = []
    for r in recs:
        aud = audience_of(r.get("role"))
        if aud is None:
            continue
        facts = {**base, "name": _first_name(_person(store, r["individual_id"])), "uid": r["id"]}
        out.append(_item("class_cancelled", aud, r["individual_id"], facts, r, actor, _event(r)))
    return out


def placement_ended_items(store, before, how, actor):
    """`before` is the attendance record as it was before the placement ended; `how` is a key of HOW. Told: the person, and (for a
    student who held a seat) every instructor still placed in the class."""
    aud = audience_of(before.get("role"))
    cls = store.get(CL.CLASSES.name, before.get("scheduled_class_id", ""))
    base = class_view(store, cls) if cls is not None else None
    if aud is None or base is None or how not in HOW:
        return []
    person = _person(store, before["individual_id"])
    ev = _event(before)
    out = [_item("placement_ended", aud, before["individual_id"], {**base, "name": _first_name(person), "uid": before["id"]}, before, actor, ev)]
    if aud == "student" and before.get("status") in SEATED:
        student_name = (person or {}).get("display_name") or _first_name(person)
        for d in store.query(ATT_NAME, [("scheduled_class_id", "==", before["scheduled_class_id"])], limit=200):
            if _deleted(d) or d.get("status") in OFF or d.get("role") not in INSTRUCTOR_ROLES:
                continue
            facts = {k: v for k, v in base.items() if k in ("title", "when_day", "when_span", "when_short", "time_zone", "venue", "room", "where", "address")}
            facts.update({"name": _first_name(_person(store, d["individual_id"])), "student_name": student_name, "how": HOW[how]})
            out.append(_item("participant_left", "instructor", d["individual_id"], facts, before, actor, ev))
    return out
