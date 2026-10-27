#!/usr/bin/env python3
"""Build data/us_zip_zones.json: the time zone of every ZIP in data/us_zips.json (P-94, Todd 2026-10-27).

Run on a computer with the `timezonefinder` package (pip install timezonefinder); nothing at run time needs it. For each ZIP's coordinates it finds the
official IANA zone, then folds it into one of the eight zones the Console offers by comparing real UTC offsets in January and July 2026
(Indiana, Detroit, Louisville fold into America/New_York; Boise into America/Denver; Navajo Nation observes daylight time so it is America/Denver;
Phoenix stays America/Phoenix; Juneau and Sitka fold into America/Anchorage). The file stores ZIP ranges, not 41,000 rows.
Usage:  python3 build_zip_zones.py
"""
import json, pathlib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from timezonefinder import TimezoneFinder

HERE = pathlib.Path(__file__).resolve().parent
ZONES = ["America/New_York", "America/Chicago", "America/Denver", "America/Phoenix", "America/Los_Angeles", "America/Anchorage", "America/Adak", "Pacific/Honolulu"]
PROBES = [datetime(2026, 1, 15, 12, tzinfo=timezone.utc), datetime(2026, 7, 15, 12, tzinfo=timezone.utc)]

def fingerprint(name):
    z = ZoneInfo(name)
    return tuple(p.astimezone(z).utcoffset() for p in PROBES)

CANON = {fingerprint(n): n for n in ZONES}

def fold(name):
    return CANON.get(fingerprint(name))

def main():
    table = json.loads((HERE / "data" / "us_zips.json").read_text())
    tf = TimezoneFinder()
    zips = sorted(table)
    ranges, last, unknown = [], None, []
    for z in zips:
        _, lat, lon, _ = table[z]
        raw = tf.timezone_at(lat=lat, lng=lon) or tf.closest_timezone_at(lat=lat, lng=lon)
        zone = fold(raw) if raw else None
        if zone is None:
            unknown.append((z, raw)); zone = last   # never happens for the 50 states; keep the neighbour's zone and list it
        if zone != last:
            ranges.append([int(z), ZONES.index(zone)]); last = zone
    out = {"zones": ZONES, "ranges": ranges}
    (HERE / "data" / "us_zip_zones.json").write_text(json.dumps(out, separators=(",", ":")))
    print("zips", len(zips), "ranges", len(ranges), "unknown", unknown[:10])

if __name__ == "__main__":
    main()
