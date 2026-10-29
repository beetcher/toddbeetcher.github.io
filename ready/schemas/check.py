#!/usr/bin/env python3
"""READY registry/schema/guide/fixture checker, using the repository method.

Runs offline and never opens Firebase. Root schemas/check.py is LAUNCH-specific;
this isolated checker enforces READY's own registry without changing LAUNCH data.
Also validates identical embedded definitions so shared metadata cannot drift.
"""
import json
from pathlib import Path
import re
import sys

from jsonschema import Draft202012Validator, FormatChecker

DIRECTORY = Path(__file__).resolve().parent


def field_names(node):
    """Inspect properties recursively, including definitions and array members."""
    if isinstance(node, dict):
        yield from node.get("properties", {})
        for value in node.values():
            yield from field_names(value)
    elif isinstance(node, list):
        for value in node:
            yield from field_names(value)


def run():
    errors = []
    registry = json.loads((DIRECTORY / "registry.json").read_text())["schemas"]
    assert len(registry) == 5, "Exactly five domain collections"
    shared = json.loads((DIRECTORY / "fragments.json").read_text())
    for entry in registry:
        schema = json.loads((DIRECTORY / entry["schema"]).read_text())
        Draft202012Validator.check_schema(schema)
        expected = entry["name"] + ("es" if entry["name"].endswith(("s", "x", "z", "ch", "sh")) else "s")
        if entry["collection"] != expected:
            errors.append(f"{entry['name']}: collection naming")
        if schema.get("x_history") != "linked_records" or "indefinite" not in schema.get("x_retention", ""):
            errors.append(f"{entry['name']}: history/retention policy")
        if schema["$defs"] != shared:
            errors.append(f"{entry['name']}: shared definitions drifted")
        guide = (DIRECTORY / entry["guide"]).read_text()
        for field in set(field_names(schema)):
            if not re.fullmatch(r"[a-z][a-z0-9_]*", field):
                errors.append(f"{entry['name']}: invalid field name {field}")
            if f"`{field}`" not in guide:
                errors.append(f"{entry['name']}: guide missing {field}")
        for field in schema["x_server_required"]:
            if not schema["properties"][field].get("readOnly"):
                errors.append(f"{entry['name']}: server-required field not protected: {field}")
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        for case in json.loads((DIRECTORY / entry["examples"]).read_text()):
            actual = not list(validator.iter_errors(case["data"]))
            if case["valid"] != actual:
                errors.append(f"{entry['name']}: example mismatch: {case['name']}")
            if case.get("stored"):
                missing = set(schema["x_server_required"]) - case["data"].keys()
                if missing:
                    errors.append(f"{entry['name']}: incomplete stored example")
    catalog = json.loads((DIRECTORY / "contracts.json").read_text())["contracts"]
    for name, filename in catalog.items():
        schema = json.loads((DIRECTORY / filename).read_text())
        Draft202012Validator.check_schema(schema)
        if any(schema.get("$defs", {}).get(key) != value for key, value in shared.items()):
            errors.append(f"{name}: shared definitions drifted")
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        for case in json.loads((DIRECTORY / f"{name}.examples.json").read_text()):
            if bool(case["valid"]) != (not list(validator.iter_errors(case["data"]))):
                errors.append(f"{name}: example mismatch: {case['name']}")
    outputs = json.loads((DIRECTORY / "outputs.json").read_text())["outputs"]
    for name, filename in outputs.items():
        schema = json.loads((DIRECTORY / filename).read_text())
        Draft202012Validator.check_schema(schema)
        if any(schema.get("$defs", {}).get(key) != value for key, value in shared.items()):
            errors.append(f"{name}: output fragments drifted")
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        for case in json.loads((DIRECTORY / f"{name}.output.examples.json").read_text()):
            if bool(case["valid"]) != (not list(validator.iter_errors(case["data"]))):
                errors.append(f"{name}: output fixture mismatch: {case['name']}")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"READY: {len(registry)} collections, {len(catalog)} request contracts and {len(outputs)} output contracts/fixtures valid.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
