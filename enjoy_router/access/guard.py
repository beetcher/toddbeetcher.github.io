"""Territory at the doors (P-60 / P-65, step 3): the second check after access/policy.py.

policy.py answers "does this person hold the capability anywhere?" (a courtesy gate). This file answers "for THIS record, in THIS ZIP?".
A person who is unlimited (a super admin, or any `all` grant) is never held back. Everyone else is checked against their grants:

    before(scope, store, collection, op, args)  -> True when the call may run (every record it touches is in reach with the capability)
    after(scope, store, collection, op, data)   -> the result with records out of reach removed, or None when a single record is out of reach

Collections fall in three groups:
    PLACED      a record has a place (ZIP) from access/places.py: venues, classes, requests' assignments, attendances, rosters, people,
                locations and links, message logs. Reads and writes are checked per record.
    AREAS       the states and regions themselves: a state grant reaches its regions, a regions grant reaches those regions.
    UNPLACED    organizations, organization links, merges: no place of their own, so only an unlimited person may use them.
    everything else (curriculums, message wording, Discovery settings, the activity log, access) is global: the role decides.

Failing closed: a call whose target cannot be placed is refused for a limited person (a new venue with no address, a person with no
address, ...). Ops not listed here are refused for a limited person on a PLACED collection.
"""
from __future__ import annotations

from . import delegate, places, policy
from .territory import norm_zip

PLACED = frozenset({"venues", "scheduled_classes", "registration_assignments", "attendances", "instructor_rosters", "student_rosters",
                    "individuals", "locations", "location_links", "communication_logs"})
UNPLACED = frozenset({"organizations", "organization_links", "merge_events", "individual_restricted_details"})
AREAS = "discovery_areas"
NO_PLACE = object()     # the call touches something that cannot be placed


def _doc(store, collection, doc_id):
    d = store.get(collection, doc_id) if isinstance(doc_id, str) else None
    return d if d is not None else None


def _venue_zip(store, venue_id):
    return places.zip_of_venue(store, venue_id) if isinstance(venue_id, str) else None


def _address_zip(address):
    return norm_zip(address.get("postal_code")) if isinstance(address, dict) else None


def _location_zip(store, location_id):
    loc = _doc(store, "locations", location_id)
    return places.zip_of_location(loc) if loc else None


def call_zips(store, collection, op, args):
    """The ZIPs a WRITE call touches: a list (each may be None = cannot be placed). An empty list means the target record does not exist
    (the handler will say not_found; nothing is revealed). NO_PLACE means refuse."""
    a = args if isinstance(args, dict) else {}
    data = a.get("data") if isinstance(a.get("data"), dict) else {}
    changes = a.get("changes") if isinstance(a.get("changes"), dict) else {}
    cur = _doc(store, collection, a.get("id")) if "id" in a else None
    here = [places.zip_of(store, collection, cur)] if cur is not None else []

    if collection == "venues":
        if op == "create":
            return [None]                                              # a venue with no place: use create_with_place
        if op == "create_with_place":
            if a.get("address") is not None:
                return [_address_zip(a.get("address"))]
            return [_location_zip(store, a.get("location_id"))]
        if op == "set_place":
            new = _address_zip(a["address"]) if a.get("address") is not None else _location_zip(store, a.get("location_id"))
            return here + [new] if cur is not None else []
        return here                                                    # update, soft_delete, find_gps
    if collection == "scheduled_classes":
        if op == "create":
            return [_venue_zip(store, data.get("venue_id"))]
        extra = [_venue_zip(store, changes["venue_id"])] if "venue_id" in changes else []
        return here + extra if cur is not None else []
    if collection == "registration_assignments":
        if op == "create":
            return [places.zip_of_request_id(store, data.get("request_id"))]
        if op == "suggest":
            return [places.zip_of_request_id(store, a.get("request_id"))]
        return here
    if collection == "attendances":
        if op in ("create", "assign"):
            return [places.zip_of_class_id(store, data.get("scheduled_class_id"))]
        if op == "assign_request":
            return [places.zip_of_class_id(store, data.get("scheduled_class_id")), places.zip_of_request_id(store, data.get("request_id"))]
        if op == "delete_request":
            req = _doc(store, "registration_requests", a.get("id"))
            return [places.zip_of_request(store, req)] if req is not None else []
        return here                                                    # update, soft_delete, send_confirmation
    if collection in ("instructor_rosters", "student_rosters"):
        if op in ("create", "create_with_person"):
            return [places.zip_of_person(store, data.get("individual_id"))] if data.get("individual_id") else [None]
        return here                                                    # update, update_with_person, soft_delete
    if collection == "individuals":
        if op in ("create", "merge", "unmerge", "erase"):
            return NO_PLACE
        return here
    if collection == "locations":
        if op == "create":
            for ad in data.get("addresses", []) if isinstance(data.get("addresses"), list) else []:
                z = _address_zip(ad)
                if z:
                    return [z]
            return [None]
        return here
    if collection == "location_links":
        if op == "create":
            return [_location_zip(store, data.get("location_id"))]
        return here                                                    # update, end, soft_delete
    if collection == "communication_logs":
        return NO_PLACE if op == "create" else here                    # mark_handled, add_note, update
    return NO_PLACE


def _area_write_ok(scope, store, op, args):
    """discovery_areas writes by a limited person: only REGION records, only through edit_regions, only where a grant reaches. A person
    who holds edit_discovery_settings (a global capability) is not held back here."""
    if scope.access.can("edit_discovery_settings"):
        return True
    a = args if isinstance(args, dict) else {}
    if op == "create":
        data = a.get("data") if isinstance(a.get("data"), dict) else {}
        return data.get("kind") == "region" and scope.area_has("edit_regions", {"kind": "region", "state_code": data.get("state_code"), "id": None})
    cur = _doc(store, AREAS, a.get("id"))
    if cur is None:
        return True
    return cur.get("kind") == "region" and scope.area_has("edit_regions", cur)


def _instructor_roster_ok(scope, store, op, args):
    """Instructor entries belong to a place two ways: the ZIP where the person lives (as for any person) and the regions listed in
    `region_ids`. A write is allowed when the entry (as it is now, or as a new one will be) is in reach by EITHER way, and every region a
    person puts an instructor into is one they may manage instructors in. A new entry for someone new (no address yet) needs a region."""
    a = args if isinstance(args, dict) else {}
    data = a.get("data") if isinstance(a.get("data"), dict) else (a.get("changes") if isinstance(a.get("changes"), dict) else {})
    need = policy.crud_need("instructor_rosters", op, args)
    new = [r for r in data.get("region_ids") or [] if isinstance(r, str)]
    if not all(scope.satisfies_region(need, r) and scope.sees_region(r) for r in new):
        return False
    cur = _doc(store, "instructor_rosters", a.get("id")) if "id" in a else None
    if "id" in a:
        if cur is None:
            return True                                        # the handler says not_found; nothing is revealed
        z = places.zip_of(store, "instructor_rosters", cur)
        by_zip = scope.satisfies(need, z) and scope.sees(z)
        by_region = any(scope.satisfies_region(need, r) and scope.sees_region(r) for r in cur.get("region_ids") or [])
        return by_zip or by_region
    pid = data.get("individual_id")                            # creating
    z = places.zip_of_person(store, pid) if pid else None
    by_zip = z is not None and scope.satisfies(need, z) and scope.sees(z)
    return by_zip or bool(new)


def before(scope, store, collection, op, args):
    if scope.unlimited:
        return True
    if collection == AREAS:
        if op in policy.READ_OPS:
            return True                                                # filtered or checked after the read
        return _area_write_ok(scope, store, op, args)
    if collection in delegate.COLLECTIONS:                              # people and roles: only a delegate (invite_people) gets here
        return delegate.has_door(scope.access) and delegate.allowed(scope, store, collection, op, args, policy.READ_OPS)
    if collection in UNPLACED:
        return False
    if collection not in PLACED:
        return True                                                    # global: the role decides
    if op == "suggest":                                                 # reads one request's plan: the request must be in reach
        return scope.can_read(policy.crud_need(collection, op, args), places.zip_of_request_id(store, (args or {}).get("request_id")))
    if op in policy.READ_OPS:
        return True                                                    # checked per record after the read
    if collection == "instructor_rosters":
        return _instructor_roster_ok(scope, store, op, args)
    if collection == "individuals" and op == "create":                # a new person has no home yet: whoever may edit people somewhere may add one
        return any("edit_people" in g.get("capabilities", ()) for g in scope.access.grants)
    zips = call_zips(store, collection, op, args)
    if zips is NO_PLACE:
        return False
    need = policy.crud_need(collection, op, args)
    return all(scope.satisfies(need, z) and scope.sees(z) for z in zips)


def _readable(scope, store, collection, doc):
    caps = policy.READ.get(collection)
    if not caps:
        return False
    if scope.can_read((tuple(caps),), places.zip_of(store, collection, doc)):
        return True
    if collection == "scheduled_classes" and scope.teaches(store, doc.get("id")):
        return True                                                    # a class they teach (looking only)
    if collection == "attendances" and scope.teaches(store, doc.get("scheduled_class_id")):
        return True
    return collection == "instructor_rosters" and any(scope.satisfies_region((tuple(caps),), r) and scope.sees_region(r)
                                                        for r in doc.get("region_ids") or [])         # an instructor placed in a region by id


def after(scope, store, collection, op, data):
    """The result for a limited person. For a list: the records in reach. For one record: itself, or None when it is out of reach."""
    if scope.unlimited or not isinstance(data, (dict, list)) or op not in policy.READ_OPS:
        return data                                                     # a write's answer is just what it changed
    if collection == AREAS:
        if scope.access.can("edit_discovery_settings"):
            return data
        if isinstance(data, dict) and "records" in data:
            recs = [r for r in data["records"] if scope.area_sees(r)]
            return {**data, "records": recs, "count": len(recs)}
        return data if isinstance(data, dict) and scope.area_sees(data) else None
    if collection in delegate.COLLECTIONS:
        return delegate.show(scope, store, collection, data)
    if collection not in PLACED:
        return data
    if op == "queue":                                                   # registration_assignments: the state of each recent request
        need = policy.crud_need(collection, "queue", {})
        items = [i for i in data.get("items", []) if scope.can_read(need, places.zip_of_request_id(store, i.get("request_id")))]
        counts = {k: 0 for k in data.get("counts", {})}
        for i in items:
            counts[i["state"]] = counts.get(i["state"], 0) + 1
        return {**data, "items": items, "counts": counts}
    if isinstance(data, dict) and "records" in data:
        recs = [r for r in data["records"] if _readable(scope, store, collection, r)]
        return {**data, "records": recs, "count": len(recs)}
    if isinstance(data, dict) and "id" in data and op in ("get", "get_for_individual"):
        return data if _readable(scope, store, collection, data) else None
    return data


WIDE = 200      # the most any handler returns in one call


def widen(scope, collection, op, args):
    """Limits come BEFORE the territory filter inside the handlers, so a limited person asking for the newest 100 would get fewer than
    their own newest 100 whenever others' records are mixed in. For a list or queue on a PLACED collection, ask the handler for the most
    it will give, and trim to what the person asked for AFTER filtering. Returns (args to run, the limit to trim to or None)."""
    if scope.unlimited or collection not in PLACED or op not in ("list", "queue") or not isinstance(args, dict):
        return args, None
    want = args.get("limit")
    return {**args, "limit": WIDE}, (want if isinstance(want, int) and not isinstance(want, bool) and want > 0 else 100)


def trim(data, want):
    """Cut a filtered list or queue to the limit the person asked for."""
    if want is None or not isinstance(data, dict):
        return data
    if isinstance(data.get("records"), list):
        recs = data["records"][:want]
        return {**data, "records": recs, "count": len(recs)}
    if isinstance(data.get("items"), list):
        items = data["items"][:want]
        counts = {k: 0 for k in data.get("counts", {})}
        for i in items:
            counts[i["state"]] = counts.get(i["state"], 0) + 1
        return {**data, "items": items, "counts": counts}
    return data
