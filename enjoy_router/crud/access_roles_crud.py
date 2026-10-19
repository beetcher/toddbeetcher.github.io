"""Handler for `access_roles`: named bundles of capabilities (see ACCESS_GUIDE.md and ACCESS_ROLE_GUIDE.md).

Rules: key is unique among live roles and never changes; a super admin role holds every capability and lists none; any other role
needs at least one; a role that people still hold cannot be deleted; the last active super admin role cannot be switched off,
turned into an ordinary role or deleted (so the owner cannot lock themselves out). A new role starts switched on.

Who may call this (only a super admin: capability `manage_access`) is decided at the door, not here.
"""
from __future__ import annotations

from .discovery_kit import make

ROLES = "access_roles"
PERSONS = "access_persons"
SCAN = 500


def _live(store, name, **match):
    """Live (not soft-deleted) records of one collection whose fields equal `match`. One equality query, the rest filtered here."""
    first = tuple(match.items())[:1]      # (not list(): this module's `list` is the handler)
    docs = store.query(name, [(k, "==", v) for k, v in first], limit=SCAN)
    return [d for d in docs if "deleted_at" not in d and all(d.get(k) == v for k, v in match.items())]


def other_super_roles(store, role_id):
    """Active super admin roles other than `role_id`."""
    return [d for d in _live(store, ROLES, is_super_admin=True) if d.get("is_active") and d["id"] != role_id]


def _tidy(name, v):
    return v.strip() if isinstance(v, str) else v


def _rules(store, doc, cur):
    problems = []
    if doc.get("is_super_admin") and doc.get("capabilities"):
        problems.append({"field": "capabilities", "issue": "not_allowed"})        # a super admin holds all of them already
    if not doc.get("is_super_admin") and not doc.get("capabilities"):
        problems.append({"field": "capabilities", "issue": "required"})
    if not doc.get("is_super_admin") and "manage_access" in (doc.get("capabilities") or []):
        problems.append({"field": "capabilities", "issue": "not_allowed"})        # delegating access management comes later
    cur_id = (cur or {}).get("id")
    if any(d["id"] != cur_id for d in _live(store, ROLES, key=doc["key"])):
        problems.append({"field": "key", "issue": "duplicate"})
    if cur and cur.get("is_super_admin") and cur.get("is_active") and not (doc.get("is_super_admin") and doc.get("is_active")):
        if not other_super_roles(store, cur_id):
            problems.append({"field": "is_active" if not doc.get("is_active") else "is_super_admin", "issue": "last_super_admin"})
    return problems


def _delete_rules(store, cur):
    problems = []
    if _live(store, PERSONS, role_id=cur["id"]):
        problems.append({"field": "id", "issue": "in_use"})
    if cur.get("is_super_admin") and cur.get("is_active") and not other_super_roles(store, cur["id"]):
        problems.append({"field": "id", "issue": "last_super_admin"})
    return problems


H = make("access_role", defaults={"is_active": True}, immutable=("key",), tidy=_tidy, rules=_rules, delete_rules=_delete_rules,
         order="key", filters=("is_active", "is_super_admin", "key"))
COLLECTION, create, get, list, update, soft_delete = H.COLLECTION, H.create, H.get, H.list, H.update, H.soft_delete
