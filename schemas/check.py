#!/usr/bin/env python3
"""Schema check. Run from the repo root:  python3 schemas/check.py
Verifies, for every type in schemas/registry.json:
  - the schema is valid JSON Schema (draft 2020-12)
  - every field name is snake_case, and the collection name is the plural of the type
  - x_server_required fields exist and are marked readOnly
  - every field is mentioned (in backticks) in the type's guide
  - every example marked valid passes, and every example marked invalid fails
Passing means the schema, guide and examples agree. Needs: pip install jsonschema
"""
import json, re, sys, pathlib
try:
    from jsonschema import Draft202012Validator as V, FormatChecker
except ImportError:
    sys.exit("check.py needs jsonschema:  pip install jsonschema")

D = pathlib.Path(__file__).parent
SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")
fails = []

def names(props):
    for k, v in props.items():
        yield k
        if isinstance(v, dict):
            if "properties" in v:
                yield from names(v["properties"])
            if isinstance(v.get("items"), dict) and "properties" in v["items"]:
                yield from names(v["items"]["properties"])

def inbound_errors(schema, readonly, doc):
    errs = [f"readOnly field sent: {k}" for k in doc if k in readonly]
    errs += [e.message[:80] for e in V(schema, format_checker=FormatChecker()).iter_errors(doc)]
    return errs

for e in json.load(open(D / "registry.json"))["schemas"]:
    name = e["name"]
    schema = json.load(open(D / e["schema"]))
    V.check_schema(schema)
    if e["collection"] != name + "s":
        fails.append(f"{name}: collection should be {name}s")
    all_names = list(dict.fromkeys(names(schema["properties"])))
    for n in all_names:
        if not SNAKE.match(n):
            fails.append(f"{name}: field not snake_case: {n}")
    readonly = {k for k, v in schema["properties"].items() if v.get("readOnly")}
    for k in schema.get("x_server_required", []):
        if k not in readonly:
            fails.append(f"{name}: x_server_required field not readOnly: {k}")
    guide = (D / e["guide"]).read_text()
    for n in all_names:
        if f"`{n}`" not in guide:
            fails.append(f"{name}: guide does not mention field: {n}")
    ex = json.load(open(D / e["examples"]))
    for label, doc in ex["valid"].items():
        errs = inbound_errors(schema, readonly, doc)
        if errs:
            fails.append(f"{name}: valid example '{label}' fails: {errs[0]}")
    for label, doc in ex["invalid"].items():
        if not inbound_errors(schema, readonly, doc):
            fails.append(f"{name}: invalid example '{label}' passed but should fail")
    print(f"{name}: {len(all_names)} fields, {len(ex['valid'])} valid and {len(ex['invalid'])} invalid examples checked")

if fails:
    print("\nFAILED:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("OK: schema, guide and examples agree")
