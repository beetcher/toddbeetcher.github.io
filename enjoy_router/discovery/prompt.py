"""Building the prompt (plan section 8.1 step 3; rule D-18). Product-blind.

The prompt TEXT is data the operator edits in the Console. The core fills its {placeholders} from the operator's choices:
    {territory}   the area, in words
    {types}       the type this step searches, with its hint
    {fields}      the facts to give, which are needed and which are optional, and the shape of the answer
    {max_results} how many results this step may return
A placeholder that is not in the finder's closed list, and any stray curly brace, is refused (check_text).
"""
from __future__ import annotations

import re

PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
MAX_LISTED_ZIPS = 40


def check_text(text: str, allowed) -> list:
    """Problems with a prompt text: [{"issue": "unknown_placeholder", "name": ...}] and stray braces. [] means it can be used."""
    problems = []
    for name in PLACEHOLDER.findall(text):
        if name not in allowed:
            problems.append({"issue": "unknown_placeholder", "name": name})
    if "{" in PLACEHOLDER.sub("", text) or "}" in PLACEHOLDER.sub("", text):
        problems.append({"issue": "stray_brace"})
    return problems


def render(text: str, values: dict) -> str:
    """Fill the placeholders in one pass (inserted text is never scanned again). Raises ValueError on any problem."""
    bad = check_text(text, values.keys())
    if bad:
        raise ValueError(bad[0]["issue"])
    return PLACEHOLDER.sub(lambda m: str(values[m.group(1)]), text)


def territory_text(area) -> str:
    n = len(area.zip_codes)
    if 0 < n <= MAX_LISTED_ZIPS:
        return f"{area.label} (ZIP codes: {', '.join(area.zip_codes)})"
    if n:
        return f"{area.label} (about {n} ZIP codes)"
    return area.label


def types_text(type_entry) -> str:
    line = f"- {type_entry.label}"
    if type_entry.search_hint:
        line += f": {type_entry.search_hint}"
    if type_entry.is_chain:
        line += " (this is one named chain: list every location of it in the area)"
    return line


def fields_text(finder) -> str:
    lines = [f'Return a JSON object {{"{finder.result_key}": [ ... ]}}. Each item has these keys:']
    for spec in finder.ask_fields:
        lines.append(f"- {spec.key} ({spec.tier}): {spec.description}")
    lines.append('Give every fact as {"value": ..., "mark": "sure" or "verify", "source_url": "https://..."}. '
                 'A fact marked "sure" must have a source_url. Leave a key out completely when you do not know it.')
    return "\n".join(lines)


def build(prompt_text: str, finder, area, type_entry, max_results: int) -> str:
    return render(prompt_text, {"territory": territory_text(area), "types": types_text(type_entry),
                                "fields": fields_text(finder), "max_results": max_results})
