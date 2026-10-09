"""The shared kit for CRUD handler files (docs/schema-first-build-method.md, section 6.5).

Holds the mechanical parts every handler file needs, so the copies cannot drift:
loading a collection through the registry, checking one field or a whole document with the
standard checker (the `jsonschema` library), finding which fields are involved in cross-field
rules, stamping the standard fields, and the Result type.

It holds NO field logic and NO collection names. A collection's own rules live in its handler
file's rules block. Problems name fields and never include values (SCHEMA_RULES sections 8, 9).
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from jsonschema import Draft202012Validator, FormatChecker

ACTOR_PATTERN = re.compile(r"^(web|system|user):[A-Za-z0-9_.-]{1,90}$")
UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


# ----------------------------------------------------------------------------
# Result: what every handler function returns
# ----------------------------------------------------------------------------

@dataclass
class Result:
    ok: bool
    data: Any = None
    code: Optional[str] = None          # a code from SCHEMA_RULES section 8, plus `conflict`
    problems: list = field(default_factory=list)  # [{"field": ..., "issue": ...}], never values


def success(data: Any) -> Result:
    return Result(ok=True, data=data)


def failure(code: str, problems: Optional[list] = None) -> Result:
    return Result(ok=False, code=code, problems=problems or [])


# ----------------------------------------------------------------------------
# Loading a collection through the registry
# ----------------------------------------------------------------------------

def find_schema_dir() -> pathlib.Path:
    """ICDT_SCHEMA_DIR if set; else ../schemas (the repo); else ./schemas (the copy sync_schemas.py puts in a deploy)."""
    env = os.environ.get("ICDT_SCHEMA_DIR")
    if env:
        return pathlib.Path(env)
    here = pathlib.Path(__file__).resolve().parent.parent  # enjoy_router/
    for d in (here.parent / "schemas", here / "schemas"):
        if (d / "registry.json").exists():
            return d
    raise RuntimeError("schemas folder not found; set ICDT_SCHEMA_DIR")


@dataclass
class Collection:
    type_name: str                 # "venue"
    name: str                      # "venues" (from the registry; never typed by hand)
    schema: dict
    validator: Draft202012Validator
    properties: dict
    read_only: frozenset
    required: tuple
    server_required: tuple
    schema_version: int
    history: str                   # x_history: in_place | linked_records | history_collection
    retention: str                 # x_retention (a written policy)
    set_involved: frozenset        # setting one of these fields needs the whole-record check
    remove_involved: frozenset     # removing one of these fields needs the whole-record check
    _field_validators: dict = field(default_factory=dict, repr=False)


def _names_in_required(node: dict) -> set:
    names = set(node.get("required", []))
    for kw in ("anyOf", "oneOf"):
        for branch in node.get(kw, []):
            names |= _names_in_required(branch)
    return names


def involved_fields(schema: dict) -> tuple:
    """(set_involved, remove_involved), found by scanning the schema's own cross-field keywords.

    Setting a field can break a rule only when the field is a trigger (dependentRequired key),
    is part of an `if` condition, or carries a conditional constraint (a property named in a
    then/else block). Removing a field can break a rule only when the field is required by one
    of those rules or by the schema itself.
    """
    setf: set = set()
    remf: set = set(schema.get("required", []))
    for trigger, needed in schema.get("dependentRequired", {}).items():
        setf.add(trigger)
        remf.update(needed)
    for block in schema.get("allOf", []):
        cond = block.get("if", {})
        setf |= set(cond.get("properties", {})) | set(cond.get("required", []))
        remf |= set(cond.get("required", []))
        for branch in (block.get("then", {}), block.get("else", {})):
            setf |= set(branch.get("properties", {}))
            remf |= _names_in_required(branch)
    for kw in ("anyOf", "oneOf"):
        for branch in schema.get(kw, []):
            remf |= _names_in_required(branch)
    return frozenset(setf), frozenset(remf)


_CACHE: dict = {}


def load_collection(type_name: str, directory: Optional[pathlib.Path] = None) -> Collection:
    d = directory or find_schema_dir()
    key = (str(d), type_name)
    if key in _CACHE:
        return _CACHE[key]
    registry = json.loads((d / "registry.json").read_text())["schemas"]
    entry = next(e for e in registry if e["name"] == type_name)
    schema = json.loads((d / entry["schema"]).read_text())
    Draft202012Validator.check_schema(schema)
    props = schema["properties"]
    setf, remf = involved_fields(schema)
    coll = Collection(
        type_name=type_name,
        name=entry["collection"],
        schema=schema,
        validator=Draft202012Validator(schema, format_checker=FormatChecker()),
        properties=props,
        read_only=frozenset(k for k, v in props.items() if v.get("readOnly")),
        required=tuple(schema.get("required", [])),
        server_required=tuple(schema.get("x_server_required", [])),
        schema_version=props["schema_version"]["const"],
        history=schema.get("x_history", ""),
        retention=schema.get("x_retention", ""),
        set_involved=setf,
        remove_involved=remf,
    )
    _CACHE[key] = coll
    return coll


# ----------------------------------------------------------------------------
# Turning checker errors into field problems (never values). Same words as core.py.
# ----------------------------------------------------------------------------

_REQUIRED = re.compile(r"^'([^']+)' is a required property")
_DEPENDENCY = re.compile(r"^'([^']+)' is a dependency of")
_ISSUE = {
    "required": "required", "dependentRequired": "required",
    "additionalProperties": "not_allowed", "propertyNames": "not_allowed",
    "format": "invalid_format", "pattern": "invalid_format",
    "enum": "invalid_value", "const": "invalid_value", "type": "invalid_type",
    "oneOf": "choose_one", "anyOf": "choose_one",
}
_RANGE = ("minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems")


def _issue(err) -> str:
    if err.validator is None and list(err.absolute_path):
        return "not_allowed"
    return _ISSUE.get(err.validator, "out_of_range" if err.validator in _RANGE else "invalid")


def _names_for(err, instance: dict, schema: dict) -> list:
    path = list(err.absolute_path)
    if path and isinstance(path[0], str):
        return [path[0]]
    if "propertyNames" in list(err.absolute_schema_path) and isinstance(err.instance, str):
        return [err.instance]
    if err.validator == "required":
        m = _REQUIRED.match(err.message)
        return [m.group(1)] if m else []
    if err.validator == "dependentRequired":
        m = _DEPENDENCY.match(err.message)
        return [m.group(1)] if m else []
    if err.validator == "additionalProperties":
        return sorted(k for k in instance if k not in schema["properties"])
    if err.validator in ("oneOf", "anyOf"):
        names: list = []
        for branch in err.validator_value:
            for k in branch.get("required", []):
                if k not in names:
                    names.append(k)
        return names
    return []


def check_document(coll: Collection, doc: Any) -> list:
    """Check a whole document with the standard checker. Returns problems (empty when valid)."""
    if not isinstance(doc, dict):
        return [{"field": "body", "issue": "invalid_type"}]
    seen: dict = {}
    for e in coll.validator.iter_errors(doc):
        issue = _issue(e)
        for name in _names_for(e, doc, coll.schema):
            seen.setdefault(name, issue)
    return [{"field": k, "issue": v} for k, v in sorted(seen.items())]


def check_field(coll: Collection, name: str, value: Any, allow_read_only: bool = False) -> list:
    """Check ONE value against that field's own definition. No other field is looked at."""
    if name not in coll.properties:
        return [{"field": name, "issue": "not_allowed"}]
    if name in coll.read_only and not allow_read_only:
        return [{"field": name, "issue": "not_allowed"}]
    v = coll._field_validators.get(name)
    if v is None:
        wrapper = {"$schema": coll.schema["$schema"], "$defs": coll.schema.get("$defs", {}),
                   "properties": coll.properties, "$ref": "#/properties/" + name}
        v = coll._field_validators[name] = Draft202012Validator(wrapper, format_checker=FormatChecker())
    errors = list(v.iter_errors(value))
    return [{"field": name, "issue": _issue(errors[0])}] if errors else []


# ----------------------------------------------------------------------------
# Small shared helpers
# ----------------------------------------------------------------------------

def utc_stamp(now: Optional[datetime] = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id() -> str:
    return str(uuid.uuid4())


def check_actor(actor: Any) -> list:
    ok = isinstance(actor, str) and ACTOR_PATTERN.match(actor)
    return [] if ok else [{"field": "actor", "issue": "invalid_format"}]


def clean(value: Any) -> Any:
    """Trim every string, recursively. An empty string becomes None (meaning: leave the field out)."""
    if isinstance(value, str):
        v = value.strip()
        return v if v else None
    if isinstance(value, list):
        return [clean(x) for x in value]
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    return value


def drop_empty(doc: dict) -> dict:
    """Optional fields are omitted when empty; never store null (SCHEMA_RULES section 3)."""
    return {k: v for k, v in doc.items() if v is not None}


def stamp_create(coll: Collection, data: dict, actor: str, source: str, now: Optional[datetime] = None) -> dict:
    stamp = utc_stamp(now)
    doc = dict(data)
    doc.update({"id": new_id(), "schema_version": coll.schema_version,
                "created_at": stamp, "created_by": actor,
                "updated_at": stamp, "updated_by": actor, "source": source})
    return doc


def stamp_update(actor: str, now: Optional[datetime] = None) -> dict:
    return {"updated_at": utc_stamp(now), "updated_by": actor}
