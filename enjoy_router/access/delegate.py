"""Delegated invitations (P-68, decided 2026-10-20): a person holding `invite_people` in a grant may invite and manage people INSIDE that
territory, and nothing else. Every rule is one small function here; the guard (access/guard.py) calls them for the two access collections.

  * What they may give: regions grants only, every region inside a grant of theirs that holds `invite_people`, with capabilities that grant
    also holds, never `invite_people` itself (no chains). No state grants, no `all`, no retired `scope_region_id`.
  * Which roles: active, not a super admin, no `manage_access`, and every global capability of the role is one the inviter holds.
  * Whom they see and change: people whose whole territory is inside theirs by the same test, or who have no territory yet and were
    invited by this person. Never themselves, never a super admin.
  * Roles: they can read the roles they may hand out, nothing else; they cannot write roles.
"""
from __future__ import annotations

from . import places
from .capabilities import GLOBAL

INVITE = "invite_people"
COLLECTIONS = ("access_persons", "access_roles")


def _inviting(scope):
    return [g for g in scope.access.grants if INVITE in g.get("capabilities", ())]


def has_door(access):
    """May this sign-in use the people-and-roles door at all (as a delegate)?"""
    return bool(access and access.ok and not access.is_super_admin and any(INVITE in g.get("capabilities", ()) for g in access.grants))


def grant_ok(scope, g):
    if not isinstance(g, dict) or g.get("kind") != "regions":
        return False
    caps = set(g.get("capabilities") or ())
    rids = g.get("region_ids") or []
    if INVITE in caps or not rids:
        return False
    inviting = _inviting(scope)
    for rid in rids:
        covering = [x for x in inviting if scope.territory.covers_region(x, rid)]
        if not covering or not any(caps <= set(x.get("capabilities", ())) for x in covering):
            return False
    return True


def role_ok(scope, store, role_id):
    r = store.get("access_roles", role_id) if isinstance(role_id, str) else None
    if r is None or "deleted_at" in r or not r.get("is_active") or r.get("is_super_admin"):
        return False
    caps = set(r.get("capabilities") or ())
    return "manage_access" not in caps and all(scope.access.can(c) for c in caps if c in GLOBAL)


def _self_id(scope):
    a = scope.access.actor or ""
    return a.split(":", 1)[1] if a.startswith("user:") else None


def person_ok(scope, store, p):
    """Is this access person one the delegate may see and change?"""
    if not isinstance(p, dict) or p.get("id") == _self_id(scope):
        return False
    r = store.get("access_roles", p.get("role_id")) if p.get("role_id") else None
    if r is None or r.get("is_super_admin"):
        return False
    grants = p.get("grants") or []
    if p.get("scope_region_id") and not grants:
        return False
    if grants:
        return all(grant_ok(scope, g) for g in grants)
    return p.get("created_by") == scope.access.actor


def _individual_ok(scope, store, individual_id):
    return individual_id is None or (isinstance(individual_id, str) and scope.sees(places.zip_of_person(store, individual_id)))


def allowed(scope, store, collection, op, args, read_ops):
    """The `before` check for the two access collections (a delegate only)."""
    if collection == "access_roles":
        return op in read_ops
    if op in read_ops:
        return True                                            # filtered after the read
    a = args if isinstance(args, dict) else {}
    if op == "create":
        d = a.get("data") if isinstance(a.get("data"), dict) else {}
        return (role_ok(scope, store, d.get("role_id")) and all(grant_ok(scope, g) for g in d.get("grants") or [])
                and not d.get("scope_region_id") and _individual_ok(scope, store, d.get("individual_id")))
    cur = store.get("access_persons", a.get("id")) if isinstance(a.get("id"), str) else None
    if cur is None:
        return True                                            # the handler says not_found; nothing is revealed
    if not person_ok(scope, store, cur):
        return False
    if op == "soft_delete":
        return True
    c = a.get("changes") if isinstance(a.get("changes"), dict) else {}
    return ((c.get("role_id") is None or role_ok(scope, store, c["role_id"]))
            and all(grant_ok(scope, g) for g in c.get("grants") or [])
            and not c.get("scope_region_id") and _individual_ok(scope, store, c.get("individual_id")))


def show(scope, store, collection, data):
    """The result of a read, cut down to what the delegate may see."""
    keep = (lambda r: role_ok(scope, store, r.get("id"))) if collection == "access_roles" else (lambda r: person_ok(scope, store, r))
    if isinstance(data, dict) and "records" in data:
        recs = [r for r in data["records"] if keep(r)]
        return {**data, "records": recs, "count": len(recs)}
    return data if isinstance(data, dict) and keep(data) else None
