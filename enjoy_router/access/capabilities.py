"""The fixed list of capabilities: read from the `access_role` schema, so the schema is the one place the list lives
(a role may only name capabilities in the schema's enum). The table that explains each one is in schemas/ACCESS_ROLE_GUIDE.md."""
from __future__ import annotations

import json

from crud.schema_kit import find_schema_dir


def _load():
    schema = json.loads((find_schema_dir() / "access_role.schema.json").read_text())
    return tuple(schema["properties"]["capabilities"]["items"]["enum"])


CAPABILITIES = _load()

# Decided 2026-10-20: a territorial capability applies only inside a person's territory (their grants); a global one comes from the role.
# view_console is global (it lets a person open the Console); looking at records in a territory is implied by holding any grant there.
TERRITORIAL = ("manage_requests", "manage_classes", "manage_instructors", "edit_venues", "activate_venues", "edit_people", "edit_places",
               "edit_regions", "view_messages", "manage_messages", "run_discovery", "invite_people")
GLOBAL = tuple(c for c in CAPABILITIES if c not in TERRITORIAL)
