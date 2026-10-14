"""Address -> GPS point, from the US Census geocoder (free, no key, US street addresses).

`lookup` is the hook the venue service calls. It is None by default, so tests and the in-memory emulator never touch the
network; main.py sets it to census_lookup for the deployed functions, and tests set it to a fake.
A lookup never raises: no match, a timeout or any error gives None, and the caller carries on without GPS.
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request

log = logging.getLogger("enjoy_router")
URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
TIMEOUT_SECONDS = 6

lookup = None   # callable(address: dict) -> (lat, lon) or None; set by main.py


def one_line(address: dict) -> str:
    """'1 Main St, Louisville, CO 80027' from a place address, or '' when it lacks a street, town or state."""
    street = " ".join(x for x in (address.get("street_number"), address.get("street")) if x) if address.get("street") else ""
    if not (street and address.get("locality") and address.get("region")):
        return ""
    tail = " ".join(x for x in (address.get("region"), address.get("postal_code")) if x)
    return ", ".join((street, address["locality"], tail))


def census_lookup(address: dict):
    text = one_line(address)
    if not text:
        return None
    url = URL + "?" + urllib.parse.urlencode({"address": text, "benchmark": "Public_AR_Current", "format": "json"})
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as r:
            data = json.loads(r.read())
        match = data["result"]["addressMatches"][0]["coordinates"]
        lat, lon = float(match["y"]), float(match["x"])
    except (IndexError, KeyError, TypeError, ValueError):
        return None   # no match
    except Exception as exc:   # network, timeout, bad JSON: say nothing about the cause
        log.info("geocode code=failed exception=%s", type(exc).__name__)
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon
