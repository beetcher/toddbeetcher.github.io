"""One email check for every schema in the server.

jsonschema's own "email" format only looks for an @, so `name@gmail.com+tag` passed. Importing this module replaces that
check with the `email-validator` library (syntax only: no DNS lookup, so it is fast and works offline). A plus before the @
is fine (`name+tag@gmail.com`); a plus after it is not. Import it before any validator is built (core.py and
crud/schema_kit.py do). Swapping in a stricter check later means changing only `is_valid_email` here.
"""
from __future__ import annotations

from email_validator import EmailNotValidError, validate_email
from jsonschema import FormatChecker


def is_valid_email(value) -> bool:
    if not isinstance(value, str):
        return True   # jsonschema convention: a format only judges strings (the type rule judges the rest)
    if value != value.strip() or " " in value:
        return False
    try:
        validate_email(value, check_deliverability=False, allow_smtputf8=False)
    except EmailNotValidError:
        return False
    return True


FormatChecker.cls_checks("email")(is_valid_email)
