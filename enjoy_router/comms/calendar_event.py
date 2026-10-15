"""The shared calendar-event helper (rule R-25): neutral event data to a calendar file (.ics). Moved unchanged from
placement_email.make_ics; the golden masters hold its exact output. Product-blind: standard library only."""
from __future__ import annotations

from datetime import datetime, timezone


def _ics_escape(text):
    return str(text).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\n").replace("\n", "\\n")


def _fold(line):
    """RFC 5545: lines are at most 75 octets; continuation lines start with a space."""
    raw, out = line.encode("utf-8"), []
    while len(raw) > 75:
        cut = 75
        while cut > 0 and (raw[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append(raw[:cut].decode("utf-8"))
        raw = b" " + raw[cut:]
    out.append(raw.decode("utf-8"))
    return "\r\n".join(out)


def parse_utc(stamp):
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def event_from_facts(facts: dict, mapping: dict) -> dict:
    """mapping (from the kind's attachment declaration) says which fact feeds which event field."""
    ev = {field: facts.get(fact) for field, fact in mapping.items()}
    ev["start"], ev["end"] = parse_utc(ev["start"]), parse_utc(ev["end"])
    return ev


def make_ics(ev: dict, now=None, uid_domain: str = "beetcher.com", method: str = "PUBLISH") -> bytes:
    """ev: uid, title, start, end (datetimes, UTC), and optional venue, room, address, lead, confirmation, notes."""
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    where = ", ".join(x for x in (ev.get("venue"), ev.get("room"), ev.get("address")) if x)
    desc = [ev["title"]]
    if ev.get("lead"):
        desc.append(f"Lead instructor: {ev['lead']}")
    if ev.get("confirmation"):
        desc.append(f"Confirmation number: {ev['confirmation']}")
    if ev.get("notes"):
        desc.append(ev["notes"])
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//LAUNCH//I Can Do That//EN", "CALSCALE:GREGORIAN", f"METHOD:{method}",
             "BEGIN:VEVENT", f"UID:{ev['uid']}@{uid_domain}", f"DTSTAMP:{stamp}",
             f"DTSTART:{ev['start'].strftime('%Y%m%dT%H%M%SZ')}", f"DTEND:{ev['end'].strftime('%Y%m%dT%H%M%SZ')}",
             f"SUMMARY:{_ics_escape(ev['title'])}"]
    if where:
        lines.append(f"LOCATION:{_ics_escape(where)}")
    cancel = method == "CANCEL"
    lines += [f"DESCRIPTION:{_ics_escape(chr(10).join(desc))}"]
    # A PUBLISH with no sequence is the original event (output unchanged). An update or a cancel carries a SEQUENCE higher than any earlier one
    # (seconds since 1970 of `now`), which is what makes a calendar replace or remove the event it already holds.
    seq = ev.get("sequence") if ev.get("sequence") is not None else (int((now or datetime.now(timezone.utc)).timestamp()) if cancel else None)
    if seq is not None:
        lines.append(f"SEQUENCE:{int(seq)}")
    lines += ["STATUS:CANCELLED" if cancel else "STATUS:CONFIRMED", "END:VEVENT", "END:VCALENDAR"]
    return ("\r\n".join(_fold(x) for x in lines) + "\r\n").encode("utf-8")
