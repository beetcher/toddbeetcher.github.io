#!/usr/bin/env python3
"""Schema check. Run from the repo root:  python3 schemas/check.py
Verifies, for every type in schemas/registry.json:
  - the schema is valid JSON Schema (draft 2020-12)
  - every field name is snake_case, and the collection name is the plural of the type (s, or es after s, x, z, ch, sh)
  - x_server_required fields exist and are marked readOnly
  - every field is mentioned (in backticks) in the type's guide
  - every example marked valid passes, and every example marked invalid fails
  - capacity_minimum <= capacity_target <= capacity_max in examples and seed classes
  - venue rules the schema cannot express, in examples and seed venues: room labels are
    unique, opens_at before closes_at (no rule on room occupancy: Todd)
  - the test records agree with the schema: schema-layer tests pass or fail as
    expected, endpoint-layer tests pass the schema (the endpoint decides the rest),
    names and references resolve, expected error codes are known, and no two
    different tests share an idempotency key; seed classes are valid scheduled_class
    records, and snapshot, class_closed and over_capacity expectations match them;
    setup.now parses (the clock the endpoint runner uses);
    a class request may only pick a seed class of type workshop;
    seed venues are valid venue records, every seed class points at a seed venue, names a room that
    exists there
Shared fragments (registry.json "fragments", for example the Discovery module's discovery_mark block): the fragment is valid, its field names
    are snake_case and mentioned in its guide, its valid and invalid examples behave as labelled, and every schema that embeds it carries a
    byte-for-byte copy (so "defined once" cannot drift)
Passing means the schema, guide, examples and test records agree. Needs: pip install jsonschema
"""
import json, re, sys, pathlib
from datetime import datetime
try:
    from jsonschema import Draft202012Validator as V, FormatChecker
except ImportError:
    sys.exit("check.py needs jsonschema:  pip install jsonschema")

D = pathlib.Path(__file__).parent
SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")
HONEYPOT = "website"
CODES = {"validation_failed", "over_capacity", "class_not_found", "venue_not_found", "curriculum_not_found", "class_closed",
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

def venue_problems(doc):
    out = []
    rooms = doc.get("rooms", [])
    labels = [r.get("label") for r in rooms]
    if len(labels) != len(set(labels)):
        out.append("room labels are not unique")
    for h in doc.get("availability_hours", []):
        if "opens_at" in h and "closes_at" in h and h["opens_at"] >= h["closes_at"]:
            out.append(f"{h.get('day_of_week')}: opens_at not before closes_at")
    return out

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
        if name == "venue":
            for p in venue_problems(doc):
                fails.append(f"{name}: valid example '{label}': {p}")
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
        try:
            datetime.fromisoformat(tr["setup"]["now"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            fails.append(f"{name}: test records need setup.now (UTC, for example 2026-10-06T17:00:00Z); the runner uses it as the clock")
        seen = {}
        seeds = {c["id"]: c for c in tr["setup"]["scheduled_classes"]}
        class_ids = set(seeds)
        cs = SCHEMAS.get("scheduled_class")
        vs = SCHEMAS.get("venue")
        venues = {v["id"]: v for v in tr["setup"].get("venues", [])}
        if seeds and vs is None:
            fails.append("test seed classes need the venue schema in the registry")
        for vd in venues.values():
            if vs is None:
                break
            verrs = [x.message[:70] for x in V(vs, format_checker=FormatChecker()).iter_errors(vd)]
            verrs += [f"missing server field {k}" for k in vs["x_server_required"] if k not in vd]
            if verrs:
                fails.append(f"seed venue {vd.get('slug')}: {verrs[0]}")
            for p in venue_problems(vd):
                fails.append(f"seed venue {vd.get('slug')}: {p}")
        for sd in seeds.values():
            vd = venues.get(sd.get("venue_id"))
            if vd is None:
                fails.append(f"seed class {sd.get('slug')}: venue_id is not in setup.venues")
            elif "venue_room_label" in sd:
                room = next((r for r in vd.get("rooms", []) if r["label"] == sd["venue_room_label"]), None)
                if room is None:
                    fails.append(f"seed class {sd.get('slug')}: venue_room_label not a room at its venue")
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
            if sd and exp["ok"] and sd.get("class_type") != "workshop":
                fails.append(f"{c['name']}: a class request may only pick a workshop, but the seed class is {sd.get('class_type')}")
            if sd and exp.get("error_code") == "class_not_found" and sd.get("class_type") == "workshop" and sd["status"] == "enrolling" and sd.get("is_public"):
                fails.append(f"{c['name']}: class_not_found test uses a public enrolling workshop")
            if sd and exp.get("error_code") == "class_closed" and sd["status"] == "enrolling":
                fails.append(f"{c['name']}: class_closed test uses an enrolling class")
            if sd and exp.get("error_code") == "over_capacity" and doc.get("attendee_count", 0) <= sd["capacity_max"]:
                fails.append(f"{c['name']}: over_capacity test is not over the class maximum")
            if cid and cid not in class_ids and exp.get("error_code") != "class_not_found" and exp["ok"]:
                fails.append(f"{c['name']}: picks a class that is not in setup.scheduled_classes")
        summary += f", {len(cases)} test records"
    print(summary + " checked")

def check_message_kinds():
    """CMS (spec: claude/cms-architecture-spec.md). For every message kind in registry.json: the fact schema is sound; the seed
    templates use only facts of their kind (optional facts only inside their own show_if guard, no stray braces, bold balanced);
    and the golden masters (what the pre-refactor code produced) are reproduced byte for byte by the reference renderer."""
    import importlib.util
    mk = json.load(open(D / "registry.json")).get("message_kinds")
    if not mk:
        return
    guide = (D / mk["guide"]).read_text()
    spec = importlib.util.spec_from_file_location("reference_render", D / mk["reference_renderer"])
    RR = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(RR)
    kinds = {}
    for k in mk["kinds"]:
        kn = k["kind"]
        fs = json.load(open(D / k["facts"]))
        V.check_schema(fs)
        if not SNAKE.match(kn) or fs.get("title") != kn:
            fails.append(f"kind {kn}: key must be snake_case and equal the fact schema title")
        if f"`{kn}`" not in guide:
            fails.append(f"kind {kn}: {mk['guide']} does not mention it")
        if fs.get("additionalProperties") is not False:
            fails.append(f"kind {kn}: fact schema must set additionalProperties false")
        x = fs.get("x_kind") or {}
        for key in ("name", "audiences", "triggers", "recipient", "dedupe", "refs"):
            if not x.get(key):
                fails.append(f"kind {kn}: x_kind.{key} is missing")
        props = fs.get("properties", {})
        for n, p in props.items():
            if not SNAKE.match(n):
                fails.append(f"kind {kn}: fact not snake_case: {n}")
            if not p.get("description") or "type" not in p:
                fails.append(f"kind {kn}: fact {n} needs a description and a type")
        for r in fs.get("required", []):
            if r not in props:
                fails.append(f"kind {kn}: required fact {r} is not a property")
        for att in x.get("attachments", []):
            if att.get("attach_if") and att["attach_if"] not in props:
                fails.append(f"kind {kn}: attachment attach_if names unknown fact {att['attach_if']}")
            for field, fact in att.get("event_fields", {}).items():
                if fact not in props:
                    fails.append(f"kind {kn}: attachment field {field} names unknown fact {fact}")
        kinds[kn] = fs
    mt_schema = SCHEMAS["message_template"]
    mt_readonly = {k for k, v in mt_schema["properties"].items() if v.get("readOnly")}
    ph = re.compile(r"\{([^{}]*)\}")
    seeds = json.load(open(D / mk["seed_templates"]))["templates"]
    by = {}

    def check_text(label, s, known, required, guard):
        if "{" in ph.sub("", s) or "}" in ph.sub("", s):
            fails.append(f"{label}: stray curly brace in '{s[:40]}'")
        if s.count("**") % 2:
            fails.append(f"{label}: unbalanced ** in '{s[:40]}'")
        for n in ph.findall(s):
            if n not in known:
                fails.append(f"{label}: placeholder {{{n}}} is not a fact of this kind")
            elif n not in required and n != guard:
                fails.append(f"{label}: optional fact {{{n}}} is used without its own show_if")

    for t in seeds:
        label = f"seed template {t.get('kind')}/{t.get('audience')}"
        for e in inbound_errors(mt_schema, mt_readonly, t):
            fails.append(f"{label}: fails the schema: {e}")
        fs = kinds.get(t.get("kind"))
        if fs is None:
            fails.append(f"{label}: kind is not registered")
            continue
        if t["audience"] not in fs["x_kind"]["audiences"]:
            fails.append(f"{label}: audience is not one of the kind's audiences")
        key = (t["kind"], t["channel"], t["audience"])
        if key in by:
            fails.append(f"{label}: duplicate kind/channel/audience")
        by[key] = t
        known, required = set(fs["properties"]), set(fs.get("required", []))
        check_text(label + " subject", t["subject"], known, required, None)
        for i, b in enumerate(t["blocks"]):
            bl = f"{label} block {i + 1}"
            guard = b.get("show_if")
            if guard and guard not in known:
                fails.append(f"{bl}: show_if names unknown fact {guard}")
            if b["type"] == "paragraph":
                check_text(bl, b["text"], known, required, guard)
                if "plain" in b:
                    check_text(bl + " plain", b["plain"], known, required, guard)
            elif b["type"] == "button":
                check_text(bl + " link", b["link"], known, required, guard)
                if ph.search(b["label"]):
                    fails.append(f"{bl}: a button label has no placeholders")
            elif b["type"] == "facts_table":
                for j, r in enumerate(b["rows"]):
                    g2 = r.get("show_if")
                    if g2 and g2 not in known:
                        fails.append(f"{bl} row {j + 1}: show_if names unknown fact {g2}")
                    if ph.search(r["label"]):
                        fails.append(f"{bl} row {j + 1}: a row label has no placeholders")
                    check_text(f"{bl} row {j + 1}", r["value"], known, required, g2)
    gm = json.load(open(D / mk["golden_masters"]))
    done = 0
    for name, c in gm["cases"].items():
        fs = kinds.get(c["kind"])
        t = by.get((c["kind"], "email", c["audience"]))
        if fs is None or t is None:
            fails.append(f"golden {name}: no kind or seed template for {c['kind']}/{c['audience']}")
            continue
        for e in V(fs, format_checker=FormatChecker()).iter_errors(c["facts"]):
            fails.append(f"golden {name}: facts fail the fact schema: {e.message[:80]}")
        try:
            subject, text, html = RR.render(t, c["facts"])
        except RR.Incomplete as e:
            fails.append(f"golden {name}: seed template needs fact {e}")
            continue
        for part, got in (("subject", subject), ("text", text), ("html", html)):
            if got != c["expect"][part]:
                fails.append(f"golden {name}: {part} differs from the pre-refactor output")
        done += 1
    print(f"message_kinds: {len(kinds)} kinds, {len(seeds)} seed templates, {done} golden cases checked (subject, text and HTML byte for byte)")


def check_fragments():
    """Shared schema fragments (spec: claude/discovery-module-plan.md). A fragment is one field definition that several schemas embed
    unchanged. It is defined once in its own file; this proves every embedded copy still equals it."""
    fr = json.load(open(D / "registry.json")).get("fragments", [])
    for f in fr:
        frag = json.load(open(D / f["file"]))
        V.check_schema(frag)
        guide = (D / f["guide"]).read_text()
        all_names = list(dict.fromkeys(names(frag.get("properties", {}))))
        for n in all_names:
            if not SNAKE.match(n):
                fails.append(f"fragment {f['name']}: field not snake_case: {n}")
            if f"`{n}`" not in guide:
                fails.append(f"fragment {f['name']}: guide {f['guide']} does not mention field: {n}")
        ex = json.load(open(D / f["examples"]))
        checker = V(frag, format_checker=FormatChecker())
        for label, doc in ex["valid"].items():
            errs = [e.message[:80] for e in checker.iter_errors(doc)]
            if errs:
                fails.append(f"fragment {f['name']}: valid example '{label}' fails: {errs[0]}")
        for label, doc in ex["invalid"].items():
            if not list(checker.iter_errors(doc)):
                fails.append(f"fragment {f['name']}: invalid example '{label}' passed but should fail")
        for emb in f.get("embedded_in", []):
            sch = SCHEMAS.get(emb["schema"])
            prop = (sch or {}).get("properties", {}).get(emb["property"])
            want = dict(frag, readOnly=True) if emb.get("read_only") else dict(frag)
            if prop is None:
                fails.append(f"fragment {f['name']}: {emb['schema']} has no property {emb['property']}")
            elif prop != want:
                fails.append(f"fragment {f['name']}: {emb['schema']}.{emb['property']} differs from {f['file']}")
        print(f"fragment {f['name']}: {len(all_names)} fields, {len(ex['valid'])} valid and {len(ex['invalid'])} invalid examples, "
              f"{len(f.get('embedded_in', []))} embedded copies checked")


check_message_kinds()
check_fragments()

if fails:
    print("\nFAILED:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("OK: schema, guide, examples and test records agree")
