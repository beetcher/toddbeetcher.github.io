"""Registration request core: the rules, with no Firebase in it.

The wrapper (main.py, later) turns an HTTP call into handle_registration_request()
and connects a Store to Firestore. The test runner (run_tests.py) connects an
in-memory Store. Both run exactly this code.

The rules follow schemas/REGISTRATION_REQUEST_GUIDE.md section 6. Steps, in order:
  1 honeypot, 2 readOnly fields, 3 normalize email, 4 validate, 5 idempotency,
  6 past dates, 7 names versus count, 8 class pick, 9 repeat flag,
  10 server fields, 11 self-check, 12 store and reply.
Rate limiting (step 13) belongs to the wrapper.

Privacy: nothing here logs or echoes a submitted value. Errors name fields only.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional, Protocol
from zoneinfo import ZoneInfo

from jsonschema import Draft202012Validator, FormatChecker

HONEYPOT = "website"
ACTOR = "web:enjoy"
SOURCE = "web_enjoy"
TIME_ZONE = ZoneInfo("America/Denver")
# No vowels (so no accidental words) and no 0, 1, so nothing looks like O, I or L.
CONFIRMATION_ALPHABET = "23456789BCDFGHJKMNPQRSTVWXYZ"
CONFIRMATION_PREFIX = "ICDT-"
CONFIRMATION_LENGTH = 6
HTTP_STATUS = {
    "validation_failed": 400,
    "class_not_found": 404,
    "not_found": 404,
    "class_closed": 409,
    "over_capacity": 409,
    "rate_limited": 429,
    "server_error": 500,
}


# ----------------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------------

def find_schema_dir() -> pathlib.Path:
    """ICDT_SCHEMA_DIR if set; else ./schemas beside this file (a deploy copy); else ../schemas (the repo)."""
    env = os.environ.get("ICDT_SCHEMA_DIR")
    if env:
        return pathlib.Path(env)
    here = pathlib.Path(__file__).resolve().parent
    for d in (here / "schemas", here.parent / "schemas"):
        if (d / "registry.json").exists():
            return d
    raise RuntimeError("schemas folder not found; set ICDT_SCHEMA_DIR")


@dataclass
class Schemas:
    """The registration_request schema and what the registry says about it."""
    schema: dict
    validator: Draft202012Validator
    read_only: frozenset
    server_required: tuple
    snapshot_fields: tuple
    collection: str  # the Firestore collection name, from registry.json
    class_collection: str

    @staticmethod
    def load(directory: Optional[pathlib.Path] = None) -> "Schemas":
        d = directory or find_schema_dir()
        registry = json.loads((d / "registry.json").read_text())["schemas"]
        by_name = {e["name"]: e for e in registry}
        entry = by_name["registration_request"]
        schema = json.loads((d / entry["schema"]).read_text())
        Draft202012Validator.check_schema(schema)
        props = schema["properties"]
        return Schemas(
            schema=schema,
            validator=Draft202012Validator(schema, format_checker=FormatChecker()),
            read_only=frozenset(k for k, v in props.items() if v.get("readOnly")),
            server_required=tuple(schema.get("x_server_required", [])),
            snapshot_fields=tuple(schema.get("x_class_snapshot_fields", [])),
            collection=entry["collection"],
            class_collection=by_name["scheduled_class"]["collection"],
        )


# ----------------------------------------------------------------------------
# Store: what the core needs from storage. Firestore in the wrapper, a dict in tests.
# ----------------------------------------------------------------------------

class Store(Protocol):
    def get_class(self, class_id: str) -> Optional[dict]: ...
    def find_by_idempotency_key(self, key: str) -> Optional[dict]: ...
    def find_latest_by_email_and_type(self, email: str, registration_type: str) -> Optional[dict]: ...
    def confirmation_number_exists(self, number: str) -> bool: ...
    def put_request(self, doc: dict) -> None: ...


# ----------------------------------------------------------------------------
# Result
# ----------------------------------------------------------------------------

@dataclass
class Result:
    status: int                      # HTTP status for the wrapper
    envelope: dict                   # the JSON body for the browser
    outcome: str                     # created | replay | discarded_spam | rejected
    error_code: Optional[str] = None
    doc: Optional[dict] = None       # the stored document, when outcome is created
    field_errors: list = field(default_factory=list)


def _ok(status: int, doc: dict, outcome: str) -> Result:
    return Result(
        status=status,
        envelope={"ok": True, "data": {
            "confirmation_number": doc["confirmation_number"],
            "registration_type": doc["registration_type"],
        }},
        outcome=outcome,
        doc=doc if outcome == "created" else None,
    )


def _err(code: str, message: str, fields: Optional[list] = None) -> Result:
    fields = fields or []
    error = {"code": code, "message": message}
    if fields:
        error["field_errors"] = fields
    return Result(status=HTTP_STATUS[code], envelope={"ok": False, "error": error},
                  outcome="rejected", error_code=code,
                  field_errors=[f["field"] for f in fields])


# ----------------------------------------------------------------------------
# Turning validator errors into field names (never values)
# ----------------------------------------------------------------------------

_REQUIRED = re.compile(r"^'([^']+)' is a required property")
_ISSUE = {
    "required": "required",
    "additionalProperties": "not_allowed",
    "propertyNames": "not_allowed",
    "format": "invalid_format",
    "pattern": "invalid_format",
    "enum": "invalid_value",
    "const": "invalid_value",
    "type": "invalid_type",
    "oneOf": "choose_one",
    "anyOf": "choose_one",
}


def _names_for(err, instance: dict, schema: dict) -> list:
    """Top-level field names an error is about."""
    path = list(err.absolute_path)
    if path and isinstance(path[0], str):
        return [path[0]]
    if "propertyNames" in list(err.absolute_schema_path) and isinstance(err.instance, str):
        return [err.instance]
    if err.validator is None:
        # A property the schema forbids (`"name": false`): the error does not carry the name,
        # so read it from the `properties` block the error came from.
        node: Any = schema
        try:
            for p in err.absolute_schema_path:
                node = node[p]
        except (KeyError, IndexError, TypeError):
            return []
        if isinstance(node, dict):
            return sorted(k for k, v in node.items() if v is False and k in instance)
        return []
    if err.validator == "required":
        m = _REQUIRED.match(err.message)
        return [m.group(1)] if m else []
    if err.validator == "additionalProperties":
        return sorted(k for k in instance if k not in schema["properties"])
    if err.validator in ("oneOf", "anyOf"):
        names = []
        for branch in err.validator_value:
            for k in branch.get("required", []):
                if k not in names:
                    names.append(k)
        return names
    return []


def _issue(err) -> str:
    path = list(err.absolute_path)
    if err.validator is None and path:
        return "not_allowed"  # a property the schema forbids here (false schema)
    return _ISSUE.get(err.validator, "out_of_range" if err.validator in (
        "minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems") else "invalid")


def _field_errors(errors, instance: dict, schema: dict) -> list:
    seen: dict = {}
    for e in errors:
        issue = _issue(e)
        for name in _names_for(e, instance, schema):
            seen.setdefault(name, issue)
    return [{"field": k, "issue": v} for k, v in sorted(seen.items())]


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def utc_stamp(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_confirmation_number() -> str:
    return CONFIRMATION_PREFIX + "".join(secrets.choice(CONFIRMATION_ALPHABET) for _ in range(CONFIRMATION_LENGTH))


def _date_before(value: Any, today) -> bool:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date() < today
    except (TypeError, ValueError):
        return False  # the schema has already judged the format


# ----------------------------------------------------------------------------
# The handler
# ----------------------------------------------------------------------------

def handle_registration_request(
    body: Any,
    store: Store,
    schemas: Schemas,
    now: Optional[datetime] = None,
    new_id: Callable[[], str] = lambda: str(uuid.uuid4()),
    new_confirmation: Callable[[], str] = new_confirmation_number,
) -> Result:
    now = now or datetime.now(timezone.utc)
    if not isinstance(body, dict):
        return _err("validation_failed", "The request body must be a JSON object.")

    # 1. Honeypot. A bot filled the hidden field: look successful, store nothing.
    body = dict(body)
    trap = body.pop(HONEYPOT, None)
    if trap:
        fake = {"confirmation_number": new_confirmation(),
                "registration_type": body.get("registration_type") if isinstance(body.get("registration_type"), str) else "private"}
        r = _ok(201, fake, "discarded_spam")
        return r

    # 2. readOnly fields belong to the server.
    sent_read_only = sorted(k for k in body if k in schemas.read_only)
    if sent_read_only:
        return _err("validation_failed", "The request contains fields only the server may set.",
                    [{"field": k, "issue": "not_allowed"} for k in sent_read_only])

    # 3. Normalize the email before validating or matching.
    if isinstance(body.get("email"), str):
        body["email"] = body["email"].strip().lower()

    # 4. Validate.
    errors = list(schemas.validator.iter_errors(body))
    if errors:
        fe = _field_errors(errors, body, schemas.schema)
        return _err("validation_failed", "The request did not pass validation.", fe)

    # 5. Idempotency: the same key again returns the original and creates nothing.
    earlier = store.find_by_idempotency_key(body["idempotency_key"])
    if earlier is not None:
        return _ok(200, earlier, "replay")

    # 6. Requested dates may not be in the past (Mountain time).
    today = now.astimezone(TIME_ZONE).date()
    past = [k for k in ("requested_date", "alternate_requested_date") if k in body and _date_before(body[k], today)]
    if past:
        return _err("validation_failed", "A requested date is in the past.",
                    [{"field": k, "issue": "out_of_range"} for k in past])

    # 7. Names listed may not exceed the headcount.
    named = len(body.get("participants", [])) + (1 if body.get("is_requester_attending") else 0)
    if named > body["attendee_count"]:
        return _err("validation_failed", "More people are named than the attendee count.",
                    [{"field": "participants", "issue": "out_of_range"}])

    # 8. A class pick: load the class, check it takes requests and has room under its maximum.
    snapshot: dict = {}
    class_id = body.get("scheduled_class_id")
    if class_id:
        cls = store.get_class(class_id)
        if cls is None or cls.get("deleted_at"):
            return _err("class_not_found", "That class was not found.")
        if cls.get("status") != "enrolling":
            return _err("class_closed", "That class is not taking requests.")
        if body["attendee_count"] > cls["capacity_max"]:
            return _err("over_capacity", "That is more people than the class can hold.")
        snapshot = {
            "class_capacity_target_at_request": cls["capacity_target"],
            "class_capacity_max_at_request": cls["capacity_max"],
            "class_registered_at_request": cls["registered_count"],
            "seats_available_at_request": max(0, cls["capacity_max"] - cls["registered_count"]),
        }

    # 9. Repeats are flagged, never blocked.
    previous = store.find_latest_by_email_and_type(body["email"], body["registration_type"])

    # 10. Server fields.
    stamp = utc_stamp(now)
    number = new_confirmation()
    for _ in range(5):
        if not store.confirmation_number_exists(number):
            break
        number = new_confirmation()
    else:
        return _err("server_error", "Could not complete the request.")
    doc = dict(body)
    doc.update(snapshot)
    doc.update({
        "id": new_id(),
        "schema_version": 1,
        "created_at": stamp,
        "created_by": ACTOR,
        "updated_at": stamp,
        "updated_by": ACTOR,
        "source": SOURCE,
        "confirmation_number": number,
        "processing_status": "not_processed",
        "is_paid": False,
    })
    if previous is not None:
        doc["previous_id"] = previous["id"]

    # 11. Self-check: the stored record must itself satisfy the schema and carry every server field.
    problems = list(schemas.validator.iter_errors(doc))
    missing = [k for k in schemas.server_required if k not in doc]
    if problems or missing:
        return _err("server_error", "Could not complete the request.")

    # 12. Store one document; reply with the confirmation number and type only.
    store.put_request(doc)
    return _ok(201, doc, "created")
