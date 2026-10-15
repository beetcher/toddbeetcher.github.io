#!/usr/bin/env python3
"""One-time capture of the GOLDEN MASTERS for the CMS refactor (spec claude/cms-architecture-spec.md, plan claude/cms-refactor-build-plan.md).

HISTORICAL: cms_service.py and placement_email.py were removed in CMS step 3, so this only runs on a checkout of commit 21bce01.
Runs the PRE-REFACTOR code (cms_service.acknowledge and placement_email.compose/make_ics, as at commit 21bce01) on fixed inputs and
writes what it produces to ../schemas/message_kinds/golden_masters.json. The refactored code must reproduce every byte of these
outputs from the seed templates. Do not regenerate after the refactor: the old code is gone by then, and that is the point.

    cd enjoy_router && python3 capture_comms_golden.py
"""
import json
import pathlib
from datetime import datetime, timezone
from urllib.parse import quote_plus

import cms_service
import placement_email as PE
import smtp_transport

OUT = pathlib.Path(__file__).resolve().parent.parent / "schemas" / "message_kinds" / "golden_masters.json"
NOW = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
STAMP = "2026-10-15T12:00:00Z"

sent = []


def fake(key, recipient, subject, body, html_body=None, attachments=None):
    sent.append({"to": recipient, "subject": subject, "text": body, "html": html_body})
    return smtp_transport.SendResult(True, "accepted")


smtp_transport.transport = fake

RECEIPTS = {
    "receipt_with_link": {"name": "Maria O'Brien & Sons", "email": "maria@example.com", "confirmation_number": "ICDT-ABC123",
                          "link": "https://beetcher.com/enjoy/register/private/?r=tok123&x=1"},
    "receipt_without_link": {"name": "Gladys Hart", "email": "gladys@example.com", "confirmation_number": "ICDT-Y9D2FT", "link": None},
}
PLACEMENTS = {
    "placement_full": {
        "to": "gladys@example.com", "name": "Gladys", "confirmation": "ICDT-ABC123", "reference": "R-1",
        "title": "Gladys's AI Happy Hour", "start": "2026-10-17T23:00:00Z", "end": "2026-10-18T00:30:00Z", "tz": "America/Denver",
        "venue": "Ozo's Coffee, East Pearl", "address": "1500 Pearl St, Boulder, CO 80302", "room": "Back room",
        "notes": "Park behind the building; ring the bell & wait <b>please</b>. Bring a phone, a tablet or a laptop; chargers are provided, "
                 "and so is coffee, café au lait, tea — whatever you like; line two\nline three; done.",
        "lead": "Todd Beetcher", "others": ["Susan Adams", "Bobby Hodgkins"], "uid": "7d6f2a5c-1e8b-4c93-9fae-5a6b7c8d9e0f",
    },
    "placement_minimal": {
        "to": "sam@example.com", "name": "there", "confirmation": None, "reference": None,
        "title": "Your session", "start": "2026-11-05T17:00:00Z", "end": "2026-11-05T18:00:00Z", "tz": "America/Denver",
        "venue": "", "address": "", "room": "", "notes": "", "lead": None, "others": [], "uid": "1a2b3c4d-0000-4000-8000-000000000001",
    },
    "placement_standard_time": {
        "to": "lee@example.com", "name": "Lee", "confirmation": "ICDT-QQ77ZZ", "reference": None,
        "title": "Intro to AI", "start": "2026-11-14T16:00:00Z", "end": "2026-11-14T18:00:00Z", "tz": "America/Denver",
        "venue": "Boulder Public Library", "address": "1001 Arapahoe Ave, Boulder, CO 80302", "room": "", "notes": "",
        "lead": "Todd Beetcher", "others": [], "uid": "1a2b3c4d-0000-4000-8000-000000000002",
    },
    "placement_unknown_zone": {
        "to": "kim@example.com", "name": "Kim", "confirmation": None, "reference": None,
        "title": "Evening workshop", "start": "2026-12-01T01:30:00Z", "end": "2026-12-01T03:00:00Z", "tz": "Europe/Nowhere",
        "venue": "Community Hall", "address": "", "room": "Room 2", "notes": "", "lead": None, "others": ["Pat"],
        "uid": "1a2b3c4d-0000-4000-8000-000000000003",
    },
}


def parse(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


cases = {}
for key, r in RECEIPTS.items():
    sent.clear()
    cms_service.acknowledge(r["name"], r["email"], r["confirmation_number"], "k", r["link"])
    out = sent[0]
    facts = {"name": r["name"], "confirmation_number": r["confirmation_number"]}
    if r["link"]:
        facts["completion_link"] = r["link"]
    cases[key] = {"kind": "request_received", "audience": "requester", "inputs": r, "facts": facts,
                  "expect": {"subject": out["subject"], "text": out["text"], "html": out["html"]}}

for key, p in PLACEMENTS.items():
    d = dict(p, start=parse(p["start"]), end=parse(p["end"]))
    subject, text, html, ics = PE.compose(d, NOW)
    day, span, short = PE._when_text(d["start"], d["end"], d["tz"])
    where = " · ".join(x for x in (d["venue"], d["room"]) if x)
    maps = ("https://www.google.com/maps/search/?api=1&query=" + quote_plus(", ".join(x for x in (d["venue"], d["address"]) if x))
            if (d["venue"] or d["address"]) else "")
    facts = {"name": d["name"], "title": d["title"], "start_utc": p["start"], "end_utc": p["end"], "time_zone": d["tz"],
             "when_day": day, "when_span": span, "when_short": short, "uid": d["uid"]}
    for k, v in (("where", where), ("address", d["address"]), ("venue", d["venue"]), ("room", d["room"]), ("notes", d["notes"]),
                 ("lead", d["lead"]), ("also_teaching", ", ".join(d["others"])), ("confirmation_number", d["confirmation"]),
                 ("map_url", maps)):
        if v:
            facts[k] = v
    cases[key] = {"kind": "placement_confirmation", "audience": "student", "inputs": p, "facts": facts,
                  "expect": {"subject": subject, "text": text, "html": html, "ics": ics.decode("utf-8")}}

doc = {"captured_from": "commit 21bce01 (pre-refactor cms_service.acknowledge and placement_email.compose / make_ics)",
       "clock_for_calendar_stamp": STAMP, "cases": cases}
OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"wrote {OUT} with {len(cases)} cases")
