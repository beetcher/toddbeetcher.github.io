"""The fixed list of capabilities: read from the `access_role` schema, so the schema is the one place the list lives
(a role may only name capabilities in the schema's enum). The table that explains each one is in schemas/ACCESS_ROLE_GUIDE.md."""
from __future__ import annotations

import json

from crud.schema_kit import find_schema_dir


def _load():
    schema = json.loads((find_schema_dir() / "access_role.schema.json").read_text())
    return tuple(schema["properties"]["capabilities"]["items"]["enum"])


CAPABILITIES = _load()
