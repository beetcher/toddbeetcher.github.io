"""Turning one raw AI item into a checked Candidate (plan 8.1 step 5; rules D-3, D-8). Product-blind.

The AI's answer is never trusted: unknown keys are dropped, every value is checked against the schema the finder gave for it,
and a fact marked sure without a source is stored as verify (D-3).
"""
from __future__ import annotations

import re

import jsonschema

from .contract import Candidate, MARKS, MAX_SOURCE_URLS

URL = re.compile(r"^https?://[^\s]{1,490}$")


def _valid(value, schema) -> bool:
    try:
        jsonschema.validate(value, schema)
        return True
    except jsonschema.ValidationError:
        return False


def _source(entry) -> str | None:
    url = entry.get("source_url") if isinstance(entry, dict) else None
    return url if isinstance(url, str) and URL.match(url) else None


def _rejection(reason, fields, name):
    out = {"reason": reason, "fields": list(fields)}
    if name and name.strip():
        out["name"] = name.strip()[:200]               # a name is left out when empty: the run record never stores blanks
    return out


def check_item(raw, finder):
    """Returns (Candidate, None) or (None, rejection) where rejection = {"reason", "fields": [names only], "name"}."""
    if not isinstance(raw, dict):
        return None, {"reason": "not_an_object", "fields": []}
    fields, urls, missing, dropped = {}, [], [], []
    for spec in finder.ask_fields:
        entry = raw.get(spec.key)
        value = entry.get("value") if isinstance(entry, dict) else None
        if value is None or not _valid(value, spec.schema) or (isinstance(value, str) and not value.strip()):
            (missing if spec.tier == "needed" else dropped).append(spec.key)
            continue
        mark = entry.get("mark") if entry.get("mark") in MARKS else "verify"
        src = _source(entry)
        if mark == "sure" and not src:
            mark = "verify"                                    # D-3
        fields[spec.key] = {"value": value, "mark": mark, **({"source_url": src} if src else {})}
        if src and src not in urls and len(urls) < MAX_SOURCE_URLS:
            urls.append(src)
    label_value = raw.get(finder.ask_fields[0].key)
    name = label_value.get("value") if isinstance(label_value, dict) and isinstance(label_value.get("value"), str) else ""
    if missing:
        return None, _rejection("missing_needed", missing, name)
    for key, reason in finder.must_be_true.items():
        if fields.get(key, {}).get("value") is not True:
            return None, _rejection(reason, [key], name)
    attention = [code for key, code in finder.attention_if_missing.items() if key not in fields]
    first = finder.ask_fields[0].key
    return Candidate(key="", label=str(fields[first]["value"]), fields=fields, source_urls=urls,
                     attention_reasons=attention), None


def build_block(candidate, run_id: str, model_name: str, prompt_version: int, found_at: str, extra_attention=()) -> dict:
    """The record's AI block (schemas/discovery_mark.fragment.json)."""
    reasons = list(dict.fromkeys(list(candidate.attention_reasons) + list(extra_attention)))
    block = {"run_id": run_id, "model_name": model_name, "prompt_version": prompt_version, "found_at": found_at,
             "marks": {k: v["mark"] for k, v in candidate.fields.items()}}
    if candidate.source_urls:
        block["source_urls"] = list(candidate.source_urls)
    if reasons:
        block["needs_attention"] = True
        block["attention_reasons"] = reasons
    return block
