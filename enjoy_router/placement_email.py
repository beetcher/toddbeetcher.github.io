"""The placement confirmation email: "you are scheduled", with the details and a calendar file (.ics).

Sent when a student is placed (status assigned or confirmed) in a class that is scheduled (venue, date and start time) and the
person has an email address; also on demand (the Console's Send confirmation email button). Every try adds one line to the
attendance record's `correspondence` log (read only, server written, no message text). A failed email never undoes a placement.
Transport and key come from the caller; tests use a fake transport. No retries.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from html import escape
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import smtp_transport
from crud import individuals_service as IS
from crud import scheduled_classes_crud as CL
from crud import venues_service as VS
from crud.schema_kit import stamp_update, utc_stamp
from crud.store_errors import StaleUpdate

LOG = logging.getLogger("enjoy_router")
ATT_NAME = "attendances"
LOG_MAX = 100
SEND_STATUSES = ("assigned", "confirmed")
OFF = frozenset({"declined", "withdrawn", "cancelled"})
CONTACT_LINE = "Need to change something? Just reply to this email."


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


def check(store, att):
    """(details, None) when a confirmation can go, or (None, reason)."""
    if att is None or _deleted(att):
        return None, "not_found"
    if att.get("role") != "student":
        return None, "not_a_student"
    if att.get("status") not in SEND_STATUSES:
        return None, "not_placed"
    cls = store.get(CL.CLASSES.name, att.get("scheduled_class_id", ""))
    if cls is None or _deleted(cls):
        return None, "class_not_found"
    start = _parse_utc(cls.get("starts_at"))
    if start is None or cls.get("status") not in ("scheduled", "enrolling"):
        return None, "class_not_scheduled"
    if not cls.get("venue_id"):
        return None, "no_venue"
    got = IS.get(store, att["individual_id"])
    person = got.data if got.ok and got.data.get("status") != "erased" else None
    email = (person or {}).get("email")
    if not email:
        return None, "no_email"
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
    return {
        "to": email, "name": person.get("given_name") or person.get("display_name") or "there",
        "confirmation": att.get("confirmation_number"), "reference": att.get("reference_number"),
        "title": cls.get("title") or "Your session", "start": start, "end": end, "tz": tzname,
        "venue": v.get("name") or "", "address": address, "room": cls.get("venue_room_label") or "",
        "notes": cls.get("venue_notes") or "", "lead": lead, "others": others, "uid": att["id"],
    }, None


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


def make_ics(d, now=None):
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    where = ", ".join(x for x in (d["venue"], d["room"], d["address"]) if x)
    desc = [d["title"]]
    if d["lead"]:
        desc.append(f"Lead instructor: {d['lead']}")
    if d["confirmation"]:
        desc.append(f"Confirmation number: {d['confirmation']}")
    if d["notes"]:
        desc.append(d["notes"])
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//LAUNCH//I Can Do That//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             "BEGIN:VEVENT", f"UID:{d['uid']}@beetcher.com", f"DTSTAMP:{stamp}",
             f"DTSTART:{d['start'].strftime('%Y%m%dT%H%M%SZ')}", f"DTEND:{d['end'].strftime('%Y%m%dT%H%M%SZ')}",
             f"SUMMARY:{_ics_escape(d['title'])}"]
    if where:
        lines.append(f"LOCATION:{_ics_escape(where)}")
    lines += [f"DESCRIPTION:{_ics_escape(chr(10).join(desc))}", "STATUS:CONFIRMED", "END:VEVENT", "END:VCALENDAR"]
    return ("\r\n".join(_fold(x) for x in lines) + "\r\n").encode("utf-8")


def compose(d, now=None):
    day, span, short = _when_text(d["start"], d["end"], d["tz"])
    subject = f"Launch — you're scheduled: {short}"
    place = " · ".join(x for x in (d["venue"], d["room"]) if x)
    maps = "https://www.google.com/maps/search/?api=1&query=" + quote_plus(", ".join(x for x in (d["venue"], d["address"]) if x)) if (d["venue"] or d["address"]) else ""
    rows = [("What", d["title"]), ("When", f"{day}, {span}")]
    if place:
        rows.append(("Where", place))
    if d["address"]:
        rows.append(("Address", d["address"]))
    if d["lead"]:
        rows.append(("Lead instructor", d["lead"]))
    if d["others"]:
        rows.append(("Also teaching", ", ".join(d["others"])))
    if d["notes"]:
        rows.append(("Good to know", d["notes"]))
    if d["confirmation"]:
        rows.append(("Confirmation number", d["confirmation"]))
    text = f"Hello {d['name']},\n\nYou're scheduled. Here are the details:\n\n"
    text += "\n".join(f"{k}: {v}" for k, v in rows)
    if maps:
        text += f"\n\nMap: {maps}"
    text += ("\n\nA calendar file is attached: open it to add this to your calendar.\n\n" + CONTACT_LINE + "\n\nLaunch\n")
    html = f"<html><body><p>Hello {escape(d['name'])},</p><p>You're scheduled. Here are the details:</p><table cellpadding=\"4\" style=\"border-collapse:collapse\">"
    html += "".join(f"<tr><td style=\"color:#555;vertical-align:top\">{escape(k)}</td><td><strong>{escape(str(v))}</strong></td></tr>" for k, v in rows)
    html += "</table>"
    if maps:
        html += (f"<p><a href=\"{escape(maps)}\" style=\"display:inline-block;padding:12px 20px;background:#1a1a1a;color:#ffffff;"
                 "text-decoration:none;border-radius:6px;font-weight:bold\">Open the map</a></p>")
    html += (f"<p>A calendar file is attached: open it to add this to your calendar.</p><p>{escape(CONTACT_LINE)}</p><p>Launch</p></body></html>")
    return subject, text, html, make_ics(d, now)


def _append_log(store, att_id, entry, actor, now):
    for _ in range(3):
        cur = store.get(ATT_NAME, att_id)
        if cur is None or _deleted(cur):
            return None
        log = (cur.get("correspondence") or [])[-(LOG_MAX - 1):] + [entry]
        try:
            store.update(ATT_NAME, att_id, {"correspondence": log, **stamp_update(actor, now)}, (), expected_updated_at=cur["updated_at"])
            return log
        except StaleUpdate:
            continue
    return None


def send_for(store, attendance_id, actor, key, now=None, manual=False):
    """Send one confirmation and log it. Returns {"ok": False, "reason": ...} when nothing was sent because the placement is not
    eligible (no log line: nothing was tried), else {"ok": True, "result": sent|failed|unknown, "code": ..., "correspondence": [...]}."""
    details, reason = check(store, store.get(ATT_NAME, attendance_id))
    if details is None:
        return {"ok": False, "reason": reason}
    subject, text, html, ics = compose(details, now)
    res = smtp_transport.send(key, details["to"], subject, text, html, [("workshop.ics", "text/calendar", ics)])
    result = "sent" if res.ok else ("unknown" if res.code == "unknown" else "failed")
    entry = {"at": utc_stamp(now), "kind": "placement_confirmation", "channel": "email", "to": details["to"][:254], "subject": subject[:300],
             "result": result, "by": actor, "trigger": "manual" if manual else "automatic"}
    if result != "sent":
        entry["error_code"] = str(res.code)[:60]
    log = _append_log(store, attendance_id, entry, actor, now)
    LOG.info("placement email attendance=%s result=%s code=%s", attendance_id, result, res.code)
    return {"ok": True, "result": result, "code": res.code, "correspondence": log or [entry]}
