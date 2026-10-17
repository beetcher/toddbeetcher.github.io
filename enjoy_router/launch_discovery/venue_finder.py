"""The venue finder: what the AI is asked for when it looks for meeting places, and the rule for telling two results apart.

Field types and limits come from `venue.schema.json` wherever the venue record has the same field, so there is one definition of a
valid website, phone or description. See schemas/DISCOVERY_GUIDE.md section 4 for the field list.
"""
from __future__ import annotations

import re

from crud.schema_kit import load_collection
from discovery.contract import FieldSpec, Finder

KEY = "venue"
_V = load_collection("venue").properties
_TEXT = {"type": "string", "minLength": 1, "maxLength": 200}
_PUNCT = re.compile(r"[^a-z0-9]+")


def norm(text) -> str:
    """Lowercase, punctuation to single spaces, a leading 'the' dropped: 'The Beanery, Inc.' and 'beanery inc' compare equal."""
    s = _PUNCT.sub(" ", str(text).lower()).strip()
    return s[4:] if s.startswith("the ") else s


def dedupe_key(v: dict):
    """Same name + same operator + same place (street, else city). Used inside one run; the sink applies the full rule against saved records."""
    place = norm(f"{v.get('street', '')}") or norm(v["city"])
    return f"{norm(v['name'])}|{norm(v['operator'])}|{place}|{norm(v['state'])}"


def _field(key, description, tier, schema=None):
    return FieldSpec(key, description, tier, schema or _V[key])


FINDER = Finder(
    key=KEY, name="Meeting places", result_key="venues",
    ask_fields=(
        _field("name", "the place's name as people know it", "needed"),
        _field("operator", "who runs the place: the business, library district, city or organization that operates it", "needed", _TEXT),
        _field("city", "the city or town", "needed", {"type": "string", "minLength": 1, "maxLength": 100}),
        _field("state", "the two-letter state code in capitals, such as CO", "needed", {"type": "string", "pattern": "^[A-Z]{2}$"}),
        _field("is_public_venue", "true only if it is a public place open to the public; false for a home, apartment or private office", "needed"),
        _field("street", "the street address, number and street, such as 100 Main St", "optional", {"type": "string", "minLength": 1, "maxLength": 200}),
        _field("postal_code", "the five-digit ZIP code", "optional", {"type": "string", "pattern": "^[0-9]{5}$"}),
        _field("description", "two or three sentences on what makes it a good place to meet", "optional"),
        _field("website_url", "the place's own web page", "optional"),
        _field("phone", "the place's public phone number", "optional"),
        _field("email", "the place's public business email address", "optional"),
        _field("has_wifi", "true if wifi is available to customers", "optional"),
        _field("is_accessible", "true if the place is wheelchair accessible", "optional"),
        _field("allows_minors", "true if people under 18 may be there", "optional"),
        _field("public_hours", "the place's public opening hours on one line, such as Mon-Fri 7am-5pm, Sat-Sun 8am-3pm", "optional", {"type": "string", "minLength": 1, "maxLength": 300}),
        _field("notes", "anything else worth knowing, such as quiet hours or a back room", "optional"),
    ),
    dedupe_key=dedupe_key,
    must_be_true={"is_public_venue": "private_home"},
    attention_if_missing={"street": "no_street_address"},
)
