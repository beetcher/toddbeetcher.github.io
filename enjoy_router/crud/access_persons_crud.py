"""Handler for `access_persons`: one invited Google account and what it may do (see ACCESS_GUIDE.md and ACCESS_PERSON_GUIDE.md).

Rules: the email is trimmed, lowercased and unique among live records; the role must exist and be active (checked when the person is
created or given a different role, so a person whose role was later switched off can still be switched off); individual_id and
scope_region_id, when given, must name a real person / a region; once someone has signed in their email cannot change; the last
active super admin cannot be switched off, moved to an ordinary role or deleted; a person cannot change their own role, region,
email or on/off switch, or delete themselves.

Who may call this (only a super admin: capability `manage_access`) is decided at the door, not here.
`record_sign_in` is the one way `google_uid` and `last_sign_in_at` are written; the shared sign-in check calls it.
"""
from __future__ import annotations

from .access_roles_crud import PERSONS, ROLES, _live
from .discovery_kit import bad, make
from .schema_kit import utc_stamp

SELF_LOCKED = ("role_id", "is_active", "scope_region_id", "email")   # a person may not change these on their own record


def _tidy(name, v):
    v = v.strip() if isinstance(v, str) else v
    return v.lower() if name == "email" and isinstance(v, str) else v


def role_of(store, person):
    """The person's live role record, or None."""
    r = store.get(ROLES, person["role_id"]) if person.get("role_id") else None
    return None if r is None or "deleted_at" in r else r


def is_super(store, person):
    """True when the person is switched on and holds an active super admin role."""
    if not person.get("is_active"):
        return False
    r = role_of(store, person)
    return bool(r and r.get("is_active") and r.get("is_super_admin"))


def other_super_persons(store, person_id):
    return [p for p in store.query(PERSONS, [], limit=500) if "deleted_at" not in p and p["id"] != person_id and is_super(store, p)]


def find_live_by_email(store, email):
    """The live person with this email (any state), or None. Emails are unique among live records."""
    found = _live(store, PERSONS, email=(email or "").strip().lower())
    return found[0] if found else None


def _rules(store, doc, cur):
    problems = []
    cur_id = (cur or {}).get("id")
    if any(d["id"] != cur_id for d in _live(store, PERSONS, email=doc["email"])):
        problems.append({"field": "email", "issue": "duplicate"})
    if cur and cur.get("google_uid") and cur.get("email") != doc["email"]:
        problems.append({"field": "email", "issue": "immutable"})
    if cur is None or cur.get("role_id") != doc["role_id"]:
        r = store.get(ROLES, doc["role_id"])
        if r is None or "deleted_at" in r or not r.get("is_active"):
            problems.append({"field": "role_id", "issue": "not_found"})
    if doc.get("individual_id") and (cur is None or cur.get("individual_id") != doc["individual_id"]):
        p = store.get("individuals", doc["individual_id"])
        if p is None or "deleted_at" in p or p.get("status") == "erased":
            problems.append({"field": "individual_id", "issue": "not_found"})
    if doc.get("scope_region_id") and (cur is None or cur.get("scope_region_id") != doc["scope_region_id"]):
        a = store.get("discovery_areas", doc["scope_region_id"])
        if a is None or "deleted_at" in a or a.get("kind") != "region":
            problems.append({"field": "scope_region_id", "issue": "not_found"})
    if cur and is_super(store, cur) and not is_super(store, doc) and not other_super_persons(store, cur_id):
        problems.append({"field": "is_active" if not doc.get("is_active") else "role_id", "issue": "last_super_admin"})
    return problems


def _delete_rules(store, cur):
    if is_super(store, cur) and not other_super_persons(store, cur["id"]):
        return [{"field": "id", "issue": "last_super_admin"}]
    return []


H = make("access_person", defaults={"is_active": True}, tidy=_tidy, rules=_rules, delete_rules=_delete_rules,
         order="email", filters=("is_active", "role_id", "email"))
COLLECTION, create, get, list = H.COLLECTION, H.create, H.get, H.list


def update(store, id, changes, actor, expected_updated_at=None, tx=None, now=None):   # noqa: A002
    if isinstance(changes, dict) and actor == f"user:{id}":
        own = [{"field": f, "issue": "not_allowed"} for f in SELF_LOCKED if f in changes]
        if own:
            return bad(own)
    return H.update(store, id, changes, actor, expected_updated_at, tx=tx, now=now)


def soft_delete(store, id, actor, tx=None, now=None):   # noqa: A002
    if actor == f"user:{id}":
        return bad([{"field": "id", "issue": "not_allowed"}])
    return H.soft_delete(store, id, actor, tx=tx, now=now)


def record_sign_in(store, person, uid, now=None):
    """Save the Google account id at the first sign-in and the time of each sign-in. Does not touch updated_at/updated_by, so it
    never makes a super admin's open edit stale. Only the shared sign-in check calls this."""
    fields = {"last_sign_in_at": utc_stamp(now)}
    if not person.get("google_uid"):
        fields["google_uid"] = uid
    store.update(PERSONS, person["id"], fields, ())
