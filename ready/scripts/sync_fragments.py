#!/usr/bin/env python3
"""Copy canonical shared definitions into self-contained schemas; checker enforces parity.

Edit schemas/fragments.json first, run this script, then run schemas/check.py.
Self-contained schemas let kit field validators and browser imports resolve refs
without network/schema resolver configuration. This is the existing repo's
defined-once-and-byte-equivalent-fragments pattern, not separate field rules.
"""
import json
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parents[1] / "schemas"


def main():
    fragments = json.loads((DIRECTORY / "fragments.json").read_text())
    for path in DIRECTORY.glob("*.schema.json"):
        schema = json.loads(path.read_text())
        schema.setdefault("$defs", {}).update(fragments)
        path.write_text(json.dumps(schema, indent=2) + "\n")


if __name__ == "__main__":
    main()
