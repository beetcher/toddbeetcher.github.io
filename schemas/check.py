#!/usr/bin/env python3
"""Schema check. Run from the repo root:  python3 schemas/check.py
Verifies, for every type in schemas/registry.json:
  - the schema is valid JSON Schema (draft 2020-12)
  - every field name is snake_case, and the collection name is the plural of the type (s, or es after s, x, z, ch, sh)
  - x_server_required fields exist and are marked readOnly
  - every field is mentioned (in backticks) in the type's guide
  - every example marked valid passes, and every example marked invalid fails
  - capacity_minimum <= capacity_target <= capacity_max in examples and seed classes
  - the test records agree with the schema: schema-layer tests pass or fail as
    expected, endpoint-layer tests pass the schema (the endpoint decides the rest),
    names and references resolve, expected error codes are known, and no two
    different tests share an idempotency key; seed classes are valid scheduled_class
    records, and snapshot, class_closed and over_capacity expectations match them
Passing means the schema, guide, examples and test records agree. Needs: pip install jsonschema
"""
import json, re, sys, pathlib
try:
    from jsonschema import Draft202012Validator as V, FormatChecker
except ImportError:
    sys.exit("check.py needs jsonschema:  pip install jsonschema")

D = pathlib.Path(__file__).parent
SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")
HONEYPOT = "website"
CODES = {"validation_failed", "over_capacity", "class_not_found", "class_closed",
         "rate_limited", "not_found", "server_error"}
fails = []

def names(props):
    for k, v in props.items():
        yield k
        if isinstance(v, dict):
            if "properties" in v:
                yield from names(v["properties"])
            if isinstance(v.get("items"), dict) and "properties" in v["items"]:
                yield from names(v["items"]["properties"])

def prepare(doc):
    """What the endpoint does before validating: drop the honeypot, trim and lowercase the email."""
    doc = dict(doc)
    doc.pop(HONEYPOT, None)
    if isinstance(doc.get("email"), str):
        doc["email"] = doc["email"].strip().lower()
    return doc

def inbound_errors(schema, readonly, doc):
    doc = prepare(doc)
    errs = [f"readOnly field sent: {k}" for k in doc if k in readonly]
    errs += [e.message[:80] for e in V(schema, format_checker=FormatChecker()).iter_errors(doc)]
    return errs

REG = json.load(open(D / "registry.json"))["schemas"]
SCHEMAS = {e["name"]: json.load(open(D / e["schema"])) for e in REG}

def capacity_order(doc):
    return all(k in doc for k in ("capacity_minimum", "capacity_target", "capacity_max")) and not (doc["capacity_minimum"] <= doc["capacity_target"] <= doc["capacity_max"])

for e in REG:
    name = e["name"]
    schema = json.load(open(D / e["schema"]))
    V.check_schema(schema)
    plural = name + ("es" if name.endswith(("s", "x", "z", "ch", "sh")) else "s")
    if e["collection"] != plural:
        fails.append(f"{name}: collection should be {plural}")
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
        if capacity_order(doc):
            fails.append(f"{name}: valid example '{label}' breaks capacity_minimum <= capacity_target <= capacity_max")
    for label, doc in ex["invalid"].items():
        if not inbound_errors(schema, readonly, doc):
            fails.append(f"{name}: invalid example '{label}' passed but should fail")
    summary = f"{name}: {len(all_names)} fields, {len(ex['valid'])} valid and {len(ex['invalid'])} invalid examples"

    if e.get("test_records"):
        tr = json.load(open(D / e["test_records"]))
        cases = tr["tests"]
        by = {c["name"]: c for c in cases}
        if len(by) != len(cases):
            fails.append(f"{name}: duplicate test names")
        def body(c, depth=0):
            if depth > 10:
                raise RuntimeError("request_from loop")
            if "request_from" in c:
                if c["request_from"] not in by:
                    fails.append(f"{c['name']}: request_from unknown test {c['request_from']}")
                    return {}
                b = dict(body(by[c["request_from"]], depth + 1))
                b.update(c.get("override", {}))
                for k in c.get("remove", []):
                    b.pop(k, None)
                return b
            return dict(c["request"])
        seen = {}
        seeds = {c["id"]: c for c in tr["setup"]["scheduled_classes"]}
        class_ids = set(seeds)
        cs = SCHEMAS.get("scheduled_class")
        for sd in seeds.values():
            if cs is None:
                fails.append("test seed classes need the scheduled_class schema in the registry"); break
            serrs = [x.message[:70] for x in V(cs, format_checker=FormatChecker()).iter_errors(sd)]
            serrs += [f"missing server field {k}" for k in cs["x_server_required"] if k not in sd]
            if serrs:
                fails.append(f"seed class {sd.get('slug')}: {serrs[0]}")
            if capacity_order(sd):
                fails.append(f"seed class {sd.get('slug')}: breaks capacity order")
        for c in cases:
            doc = body(c)
            exp = c["expect"]
            errs = inbound_errors(schema, readonly, doc)
            if c["layer"] == "schema":
                if exp["ok"] and errs:
                    fails.append(f"{c['name']}: should pass the schema but fails: {errs[0]}")
                if not exp["ok"] and not errs:
                    fails.append(f"{c['name']}: should fail the schema but passes")
            elif c["layer"] == "endpoint":
                if errs:
                    fails.append(f"{c['name']}: endpoint-layer test must pass the schema, but fails: {errs[0]}")
            else:
                fails.append(f"{c['name']}: layer must be schema or endpoint")
            if not exp["ok"] and exp.get("error_code") not in CODES:
                fails.append(f"{c['name']}: unknown or missing error_code {exp.get('error_code')}")
            for ref in ("previous_id_of", "replay_of"):
                if ref in exp and exp[ref] not in by:
                    fails.append(f"{c['name']}: {ref} unknown test {exp[ref]}")
            key = doc.get("idempotency_key")
            replay = "replay_of" in exp
            if key in seen and not replay:
                fails.append(f"{c['name']}: idempotency key already used by {seen[key]}")
            seen.setdefault(key, c["name"])
            cid = doc.get("scheduled_class_id")
            sd = seeds.get(cid)
            if sd and exp.get("snapshot"):
                want = {"class_capacity_target_at_request": sd["capacity_target"], "class_capacity_max_at_request": sd["capacity_max"], "class_registered_at_request": sd["registered_count"], "seats_available_at_request": max(0, sd["capacity_max"] - sd["registered_count"])}
                if exp["snapshot"] != want:
                    fails.append(f"{c['name']}: snapshot does not match seed class (expected {want})")
            if sd and exp.get("error_code") == "class_closed" and sd["status"] == "enrolling":
                fails.append(f"{c['name']}: class_closed test uses an enrolling class")
            if sd and exp.get("error_code") == "over_capacity" and doc.get("attendee_count", 0) <= sd["capacity_max"]:
                fails.append(f"{c['name']}: over_capacity test is not over the class maximum")
            if cid and cid not in class_ids and exp.get("error_code") != "class_not_found" and exp["ok"]:
                fails.append(f"{c['name']}: picks a class that is not in setup.scheduled_classes")
        summary += f", {len(cases)} test records"
    print(summary + " checked")

if fails:
    print("\nFAILED:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("OK: schema, guide, examples and test records agree")
