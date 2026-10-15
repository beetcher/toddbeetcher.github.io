"""The facts and the call for the placement_confirmation kind. Port of placement_email.check / compose inputs.

`build` works out the kind's facts (including the derived when_*, where, address, map_url, also_teaching) from the attendance, its
class, the venue and the people. Wording, the calendar file and the sending are the CMS's job; nothing here renders anything.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

from crud import individuals_service as IS
from crud import scheduled_classes_crud as CL
from crud import venues_service as VS

ATT_NAME = "attendances"
SEND_STATUSES = ("assigned", "confirmed")
OFF = frozenset({"declined", "withdrawn", "cancelled"})


def _deleted(doc):
    return "deleted_at" in doc


def _addr_line(addr):
    if not addr:
        return ""
    street = " ".join(x for x in (addr.get("street_number"), addr.get("street")) if x)
    if addr.get("unit"):
        street = f"{street}, {addr['unit']}" if street else addr["unit"]
    region = " ".join(x for x in (addr.get("region"), addr.get("postal_code")) if x)
    return ", ".join(x for x in (street, addr.get("locality"), region) if x)


def _parse_utc(stamp):
    try:
        return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _local(dt, tzname):
    try:
        return dt.astimezone(ZoneInfo(tzname)), tzname
    except Exception:
        return dt, "UTC"


def _when_text(start, end, tzname):
    s, name = _local(start, tzname)
    e, _ = _local(end, tzname)

    def clock(d):
        h = d.hour % 12 or 12
        return f"{h}:{d.minute:02d} {'AM' if d.hour < 12 else 'PM'}"
    day = f"{s.strftime('%A, %B')} {s.day}, {s.year}"
    abbr = s.strftime("%Z") or name
    return day, f"{clock(s)} to {clock(e)} {abbr}", f"{s.strftime('%a %b')} {s.day}, {clock(s)}"


def _stamp(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def build(store, att):
    """(facts, individual_id, None) when a confirmation can go, or (None, None, reason). Reasons: not_found, not_a_student, not_placed,
    class_not_found, class_not_scheduled, no_venue, person_not_found. A missing email is NOT a reason here: the CMS decides (no_contact)."""
    if att is None or _deleted(att):
        return None, None, "not_found"
    if att.get("role") != "student":
        return None, None, "not_a_student"
    if att.get("status") not in SEND_STATUSES:
        return None, None, "not_placed"
    cls = store.get(CL.CLASSES.name, att.get("scheduled_class_id", ""))
    if cls is None or _deleted(cls):
        return None, None, "class_not_found"
    start = _parse_utc(cls.get("starts_at"))
    if start is None or cls.get("status") not in ("scheduled", "enrolling"):
        return None, None, "class_not_scheduled"
    if not cls.get("venue_id"):
        return None, None, "no_venue"
    got = IS.get(store, att["individual_id"])
    person = got.data if got.ok and got.data.get("status") != "erased" else None
    if person is None:
        return None, None, "person_not_found"
    venue = VS.get(store, cls["venue_id"], expand=True)
    v = venue.data if venue.ok else {}
    place = v.get("place") or {}
    address = _addr_line(place.get("address"))
    lead, others = None, []
    for d in store.query(ATT_NAME, [("scheduled_class_id", "==", cls["id"])], limit=200):
        if _deleted(d) or d.get("status") in OFF or d.get("role") == "student":
            continue
        who = IS.get(store, d["individual_id"])
        name = who.data.get("display_name") if who.ok else None
        if not name:
            continue
        if d["role"] == "primary_instructor" and lead is None:
            lead = name
        else:
            others.append(name)
    end = start + timedelta(minutes=int(cls.get("duration_minutes") or 60))
    tzname = cls.get("time_zone") or place.get("time_zone") or "America/Denver"
    day, span, short = _when_text(start, end, tzname)
    venue_name, room = v.get("name") or "", cls.get("venue_room_label") or ""
    where = " · ".join(x for x in (venue_name, room) if x)
    maps = ("https://www.google.com/maps/search/?api=1&query=" + quote_plus(", ".join(x for x in (venue_name, address) if x))
            if (venue_name or address) else "")
    facts = {
        "name": person.get("given_name") or person.get("display_name") or "there",
        "title": cls.get("title") or "Your session",
        "start_utc": _stamp(start), "end_utc": _stamp(end), "time_zone": tzname,
        "when_day": day, "when_span": span, "when_short": short, "uid": att["id"],
    }
    optional = {"where": where, "address": address, "venue": venue_name, "room": room, "notes": cls.get("venue_notes") or "",
                "lead": lead or "", "also_teaching": ", ".join(others), "confirmation_number": att.get("confirmation_number") or "",
                "map_url": maps}
    facts.update({k: val for k, val in optional.items() if val})
    return facts, person["id"], None


def call_for(store, attendance_id: str, actor: str, manual: bool = False):
    """(call, None) with the arguments for comms.notify (R-2), or (None, reason) when the placement is not eligible (nothing is tried)."""
    att = store.get(ATT_NAME, attendance_id)
    facts, individual_id, reason = build(store, att)
    if facts is None:
        return None, reason
    return dict(kind="placement_confirmation", recipient={"type": "individual", "individual_id": individual_id}, context=facts, by=actor,
                trigger="manual" if manual else "automatic", refs={"attendance_id": attendance_id, "scheduled_class_id": att["scheduled_class_id"]},
                audience="student"), None
