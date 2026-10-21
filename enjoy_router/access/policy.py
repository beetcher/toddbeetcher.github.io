"""Which capability each operation needs (P-62 step 3). One table; every door asks it, so a new collection cannot be forgotten.

A need is a tuple of groups: ALL groups must be satisfied, and each group is satisfied by ANY one of its capabilities.
    (("edit_venues",),)                      needs edit_venues
    (("edit_venues",), ("activate_venues",)) needs both
    (("run_discovery", "view_spend"),)       needs either
The name SUPER_ONLY is a capability no role may list, so only a super admin (who can do anything) passes it. Anything not named
here falls to SUPER_ONLY: unknown collection, unknown operation. That is on purpose (fail closed).

The key (the back door) is a super admin, so it passes everything; these rules only ever limit invited people.
"""
from __future__ import annotations

SUPER_ONLY = "__super_admin_only__"
_SUPER = ((SUPER_ONLY,),)

READ_OPS = frozenset({"get", "list", "find_by_address", "get_for_individual", "suggest", "queue"})

# collection -> capabilities that allow READING it (any one)
READ = {
    "venues": ("view_console",),
    "scheduled_classes": ("view_console",),
    "registration_assignments": ("manage_requests", "manage_classes"),
    "attendances": ("manage_classes", "manage_requests"),
    "journal_events": ("view_console",),
    "curriculums": ("view_console",),
    "instructor_rosters": ("manage_instructors", "manage_classes"),
    "student_rosters": ("manage_classes", "manage_requests"),
    "individuals": ("edit_people",),
    "individual_restricted_details": ("edit_people",),
    "merge_events": ("edit_people",),
    "locations": ("edit_places", "edit_venues"),          # street addresses of people stay behind edit_places / venue editing
    "location_links": ("edit_places", "edit_venues"),
    "organizations": ("edit_people",),
    "organization_links": ("edit_people",),
    "message_templates": ("view_messages",),
    "comms_settings": ("view_messages",),
    "communication_logs": ("view_messages",),
    "discovery_areas": ("view_console",),                 # the Venues State/Region filters read regions
    "discovery_types": ("run_discovery", "edit_discovery_settings"),
    "discovery_models": ("run_discovery", "edit_discovery_settings"),
    "discovery_prompts": ("run_discovery", "edit_discovery_settings"),
    "discovery_settings": ("run_discovery", "edit_discovery_settings"),
    "discovery_runs": ("run_discovery", "view_spend"),
    "access_roles": ("manage_access",),
    "access_persons": ("manage_access",),
    "activity_events": (SUPER_ONLY,),                     # the activity log: only a super admin reads it
}

# collection -> capabilities that allow WRITING it (any one)
WRITE = {
    "venues": ("edit_venues",),
    "scheduled_classes": ("manage_classes",),
    "registration_assignments": ("manage_requests",),
    "attendances": ("manage_classes",),
    "journal_events": (SUPER_ONLY,),                       # written by the server only
    "curriculums": ("manage_curriculums",),
    "instructor_rosters": ("manage_instructors",),
    "student_rosters": ("manage_classes",),
    "individuals": ("edit_people",),
    "individual_restricted_details": ("edit_people",),
    "merge_events": ("edit_people",),
    "locations": ("edit_places", "edit_venues", "manage_instructors"),   # the write-only address forms (venue place, instructor address)
    "location_links": ("edit_places", "edit_venues", "manage_instructors"),
    "organizations": ("edit_people",),
    "organization_links": ("edit_people",),
    "message_templates": ("manage_messages",),
    "comms_settings": ("manage_messages",),
    "communication_logs": ("manage_messages",),
    "discovery_areas": ("edit_discovery_settings", "edit_regions"),   # edit_regions only inside the person's own territory (access/guard.py)
    "discovery_types": ("edit_discovery_settings",),
    "discovery_models": ("edit_discovery_settings",),
    "discovery_prompts": ("edit_discovery_settings",),
    "discovery_settings": ("edit_discovery_settings",),
    "discovery_runs": (SUPER_ONLY,),                       # only the Discovery service writes runs
    "access_roles": ("manage_access",),
    "access_persons": ("manage_access",),
    "activity_events": (SUPER_ONLY,),                     # written by the ActivityStore only, never through a door
}


def crud_need(collection, op, args):
    """The need for one CRUD door call. `args` is the call's args object (already shape-checked by the door)."""
    args = args if isinstance(args, dict) else {}
    if op in READ_OPS:
        caps = READ.get(collection)
        return (tuple(caps),) if caps else _SUPER
    caps = WRITE.get(collection)
    if not caps:
        return _SUPER
    if collection == "attendances" and op == "delete_request":
        return (("manage_requests",),)
    if collection == "venues":
        if op == "soft_delete":
            return _SUPER                                   # deleting a venue stays the super admin's
        groups = [("edit_venues",)]
        data = args.get("changes") if op in ("update", "update_with_person") else args.get("data")
        if isinstance(data, dict) and "status" in data:     # switching a venue on or off is its own capability
            groups.append(("activate_venues",))
        return tuple(groups)
    return (tuple(caps),)


# Discovery door: op -> capabilities (any one)
DISCOVERY = {
    "status": ("run_discovery", "edit_discovery_settings", "view_spend"),
    "quote": ("run_discovery",), "plan": ("run_discovery",), "step": ("run_discovery",), "stop": ("run_discovery",),
    "withdraw": ("run_discovery",),
    "get_run": ("run_discovery", "view_spend"), "list_runs": ("run_discovery", "view_spend"),
    "zips": ("run_discovery", "edit_discovery_settings"),
}


def discovery_need(op):
    caps = DISCOVERY.get(op)
    return (tuple(caps),) if caps else _SUPER


# Console records door (registration requests, read only)
RECORDS = (("manage_requests", "manage_classes"),)


def allowed(access, need) -> bool:
    return bool(access and access.ok and all(any(access.can(c) for c in group) for group in need))
