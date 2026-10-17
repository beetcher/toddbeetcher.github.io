"""Reading the AI's reply text. Product-blind. Never raises: anything unreadable is None."""
from __future__ import annotations

import json
import re

FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def parse_items(text: str, result_key: str):
    """The list under result_key in the first JSON object found in the text, or None when there is none."""
    if not isinstance(text, str):
        return None
    candidates = [m.group(1) for m in FENCE.finditer(text)] + [text]
    for chunk in candidates:
        chunk = chunk.strip()
        start, end = chunk.find("{"), chunk.rfind("}")
        if start < 0 or end <= start:
            continue
        try:
            data = json.loads(chunk[start:end + 1])
        except ValueError:
            continue
        items = data.get(result_key) if isinstance(data, dict) else None
        if isinstance(items, list):
            return items
    return None
