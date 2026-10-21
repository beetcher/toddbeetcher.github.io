"""Handler for `console_settings`: the ONE record of Console settings (see CONSOLE_SETTING_GUIDE.md).

Today it holds one setting, `session_timeout_minutes`: minutes of inactivity before the Console signs a person out (1 to 480, no off setting).
`create` makes the record with the starting value (10 minutes) when none exists and refuses a second. `update` changes it in place and needs
the `updated_at` the editor read. Deleting is refused. Who may read or change it is decided in access/policy.py (read: view_console, change:
super admin only), not here.
"""
from __future__ import annotations

from .discovery_kit import live, make
from .schema_kit import failure

DEFAULTS = {"settings_key": "default", "session_timeout_minutes": 10}


def _rules(store, doc, cur):
    problems = []
    if cur is None and live(store, H.COLLECTION):
        problems.append({"field": "settings_key", "issue": "duplicate"})
    return problems


H = make("console_setting", defaults=DEFAULTS, immutable=("settings_key",), rules=_rules, order="settings_key")
COLLECTION, create, get, list, update = H.COLLECTION, H.create, H.get, H.list, H.update


def soft_delete(*_a, **_k):
    return failure("validation_failed", [{"field": "op", "issue": "not_supported"}])
