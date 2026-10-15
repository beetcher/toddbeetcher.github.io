"""Message kinds: the registry of what can be sent (CMS_GUIDE.md sections 2 and 5; rules R-5, R-12).

A kind is declared by its FACT SCHEMA (schemas/message_kinds/<kind>.facts.schema.json) and listed in registry.json under
`message_kinds`. The schema says which facts a template may use, the audiences, and any attachment. Product-blind: jsonschema only.
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field

from jsonschema import Draft202012Validator, FormatChecker

from .render import placeholders_in


@dataclass
class Kind:
    key: str
    name: str
    audiences: tuple
    schema: dict
    validator: Draft202012Validator = field(repr=False)
    attachments: tuple = ()

    @property
    def required(self) -> tuple:
        return tuple(self.schema.get("required", []))

    @property
    def facts(self) -> frozenset:
        return frozenset(self.schema["properties"])


class KindRegistry:
    def __init__(self):
        self._kinds: dict = {}

    def register(self, schema: dict) -> Kind:
        Draft202012Validator.check_schema(schema)
        x = schema["x_kind"]
        k = Kind(key=schema["title"], name=x["name"], audiences=tuple(x["audiences"]), schema=schema,
                 validator=Draft202012Validator(schema, format_checker=FormatChecker()), attachments=tuple(x.get("attachments", ())))
        self._kinds[k.key] = k
        return k

    def load(self, schema_dir) -> "KindRegistry":
        """Register every kind listed under `message_kinds` in registry.json."""
        d = pathlib.Path(schema_dir)
        for entry in json.loads((d / "registry.json").read_text()).get("message_kinds", {}).get("kinds", []):
            self.register(json.loads((d / entry["facts"]).read_text()))
        return self

    def get(self, key):
        return self._kinds.get(key)

    def keys(self) -> list:
        return sorted(self._kinds)

    def validate(self, key: str, context) -> list:
        """Problems naming facts (never values) when the context does not match the kind's fact schema; [] when valid (R-5)."""
        k = self._kinds[key]
        try:
            json.dumps(context)      # plain JSON only, so the call could be queued later
        except (TypeError, ValueError):
            return [{"field": "context", "issue": "not_plain_json"}]
        if not isinstance(context, dict):
            return [{"field": "context", "issue": "invalid_type"}]
        out = {}
        for e in k.validator.iter_errors(context):
            name = e.absolute_path[0] if e.absolute_path else (e.message.split("'")[1] if e.validator == "required" and "'" in e.message else "context")
            out.setdefault(str(name), e.validator)
        return [{"field": n, "issue": v} for n, v in sorted(out.items())]

    def check_template(self, template: dict) -> list:
        """Problems when a template names a fact its kind does not supply, or uses an optional fact outside its own show_if guard (R-12).
        The template handler calls this before it saves a template."""
        k = self._kinds.get(template.get("kind"))
        if k is None:
            return [{"field": "kind", "issue": "unknown_kind"}]
        problems = []
        if template.get("audience") not in k.audiences:
            problems.append({"field": "audience", "issue": "invalid_value"})
        unknown = placeholders_in(template) - k.facts
        problems += [{"field": "blocks", "issue": "unknown_fact"}] if unknown else []
        if not unknown:
            problems += _unguarded(template, set(k.required))
        return problems


def _unguarded(template, required) -> list:
    import re
    ph = re.compile(r"\{([a-z][a-z0-9_]*)\}")
    bad = []

    def chk(text, guard):
        if "{" in ph.sub("", text) or "}" in ph.sub("", text) or text.count("**") % 2:
            bad.append({"field": "blocks", "issue": "invalid_format"})
        for n in ph.findall(text):
            if n not in required and n != guard:
                bad.append({"field": "blocks", "issue": "optional_fact_unguarded"})

    chk(template.get("subject", ""), None)
    for b in template.get("blocks", []):
        g = b.get("show_if")
        for key in ("text", "plain", "link"):
            if key in b:
                chk(b[key], g)
        for r in b.get("rows", []):
            chk(r.get("value", ""), r.get("show_if"))
    seen, out = set(), []
    for p in bad:
        if (p["field"], p["issue"]) not in seen:
            seen.add((p["field"], p["issue"]))
            out.append(p)
    return out
