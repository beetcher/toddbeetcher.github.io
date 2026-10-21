"""The Global Inspector (P-78, decided by Todd 2026-10-21): a person who may LOOK at everything and CHANGE nothing, as a demo and sales tool.

A role that holds the global capability `inspect_everything` makes its person VIEW ONLY at all three doors (Access.inspector). This file holds
the rules that are not about who may call what:

    refuses_op(collection, op)                    True when the Console CRUD door must refuse the call (any write, any blocked collection)
    refuses_filters(collection, filters)          True when a list is filtered on a field that is hidden or masked (so a value cannot be guessed)
    shape(store, collection, op, data)            the result with private data hidden or masked; None when a single record may not be seen
    shape_records(records)                        the same for the registration requests the records door returns
    discovery_refusal(store, access, op, args)    None when the Discovery call may run, else (code, message)

What the Inspector never sees (decided 2026-10-21):
    HIDDEN (the field is removed)   notes of every kind (not a venue's or a curriculum's), street addresses, birth and death details,
                                    restricted person details, home addresses (places and links that belong to a person), Google account ids.
    MASKED (the field shows "(hidden)")  email, phone, backup email and phone, ZIP, a referrer's email, an organizer's email and phone, the
                                    address a message was sent to. Names show.
    SHOWN IN FULL                   the emails of access people (staff), venues and their public contacts, organizations' own contact
                                    details, the place a venue operates at.
A fixed 25-cent cap per Discovery run applies to an Inspector (CAP_CENTS); the Discovery limits (10 cents today) apply as well, the lower wins.
This file has no Firebase in it.
"""
from __future__ import annotations

from . import policy

CAP_CENTS = 25
MASK = "(hidden)"
INSPECTOR_DISCOVERY_OPS = frozenset({"status", "quote", "plan", "step", "stop", "get_run", "list_runs", "zips"})   # no `withdraw`: it changes records
OWN_RUN_OPS = frozenset({"step", "stop"})        # only on a run the Inspector started

BLOCKED_COLLECTIONS = frozenset({"individual_restricted_details"})      # never, not even to look at

HIDE_FIELDS = frozenset({"street_address", "handled_note", "note", "birth_date", "birth_date_certainty", "birth_date_verification",
                         "birth_place_city", "birth_place_region", "birth_country", "multiple_birth_count", "multiple_birth_order",
                         "death_date", "death_date_certainty", "death_place_city", "death_place_region", "death_country", "death_evidence",
                         "google_uid", "preferred_location", "address_keys"})
HIDE_NOTES = "notes"
NOTES_KEPT = frozenset({"venues", "curriculums"})                      # a venue's own note and a curriculum's note are not about a person
MASK_FIELDS = frozenset({"email", "phone", "backup_email", "backup_phone", "postal_code", "referrer_email", "organizer_email", "organizer_phone"})
ADDRESS_LISTS = frozenset({"addresses"})                                # a place's address list (hidden except on a venue's or business place)

# Fields that stay visible at the top of a record of this collection (the thing's OWN public contact), and subtrees that stay as they are.
KEEP_TOP = {"venues": frozenset({"email", "phone"}), "organizations": frozenset({"email", "phone"}),
            "access_persons": frozenset({"email"}), "access_roles": frozenset(), "comms_settings": frozenset({"from_address", "reply_to", "test_redirect_address", "email"})}
KEEP_SUBTREE = {"venues": frozenset({"place"}),                         # the place a venue operates at (name, address, GPS flag)
                "locations": frozenset({"addresses"})}                  # places that belong to people are dropped before this (see shape)
# Collections whose records are not about people at all: nothing is hidden or masked in them.
PLAIN = frozenset({"curriculums", "message_templates", "discovery_areas", "discovery_types", "discovery_models", "discovery_prompts",
                   "discovery_settings", "discovery_runs", "console_settings", "access_roles", "comms_settings"})
PERSON_SUBJECT = "individual"


def refuses_op(collection, op) -> bool:
    """The Console CRUD door, for an Inspector: only reads, and never a blocked collection."""
    return op not in policy.READ_OPS or collection in BLOCKED_COLLECTIONS


def _hidden_or_masked(collection):
    names = set(HIDE_FIELDS) | set(MASK_FIELDS)
    if collection not in NOTES_KEPT:
        names.add(HIDE_NOTES)
    return names - set(KEEP_TOP.get(collection, ()))


def refuses_filters(collection, filters) -> bool:
    """A list filtered on something the Inspector may not see would let them find a value by guessing."""
    if not isinstance(filters, dict) or not filters:
        return False
    bad = _hidden_or_masked(collection)
    return any(k in bad for k in filters)


# ---- hiding and masking -------------------------------------------------------------------------------------------------------------

def _scrub(node, collection, top=True):
    """A copy of `node` with the hidden fields removed and the masked ones replaced. Works on records, lists and anything nested."""
    if isinstance(node, list):
        return [_scrub(n, collection, top=False) for n in node]
    if not isinstance(node, dict):
        return node
    keep = KEEP_TOP.get(collection, frozenset()) if top else frozenset()
    subtree = KEEP_SUBTREE.get(collection, frozenset()) if top else frozenset()
    mask_to = "channel" in node and "to" in node             # a message line (a message log entry or an old placement line)
    out = {}
    for k, v in node.items():
        if k in HIDE_FIELDS or (k == HIDE_NOTES and collection not in NOTES_KEPT):
            continue
        if k in ADDRESS_LISTS and collection not in ("venues", "locations"):
            continue
        if k in subtree:
            out[k] = v
        elif (k in MASK_FIELDS and k not in keep) or (k == "to" and mask_to):
            out[k] = MASK if v not in (None, "", [], {}) else v
        else:
            out[k] = _scrub(v, collection, top=False)
    return out


def _person_location_ids(store):
    """The ids of places that belong to a person (somebody's home or mailing address)."""
    ids = set()
    for ln in store.query("location_links", [("subject_type", "==", PERSON_SUBJECT)], limit=5000):
        if ln.get("location_id"):
            ids.add(ln["location_id"])
    return ids


def shape(store, collection, op, data):
    """What the Inspector gets back from a read. None = this single record may not be seen (the door answers forbidden)."""
    if collection in BLOCKED_COLLECTIONS:
        return None
    if collection == "location_links":
        data = _drop(data, lambda r: r.get("subject_type") == PERSON_SUBJECT)
        if data is None:
            return None
    elif collection == "locations":
        mine = _person_location_ids(store)
        data = _drop(data, lambda r: r.get("id") in mine)
        if data is None:
            return None
    if collection in PLAIN:
        return data
    if isinstance(data, dict) and isinstance(data.get("records"), list):      # a list: each record is a record (its own contact may be kept)
        return {**data, "records": [_scrub(r, collection) for r in data["records"]]}
    return _scrub(data, collection)


def _drop(data, is_private):
    """A list without the private records, or a single record, or None when that single record is private."""
    if isinstance(data, dict) and isinstance(data.get("records"), list):
        recs = [r for r in data["records"] if not is_private(r)]
        return {**data, "records": recs, "count": len(recs)}
    if isinstance(data, dict) and "id" in data:
        return None if is_private(data) else data
    return data


def shape_records(records):
    """The registration requests, as the records door returns them, for an Inspector."""
    return [_scrub(r, "registration_requests") for r in records]


# ---- Discovery ----------------------------------------------------------------------------------------------------------------------

def discovery_refusal(store, access, op, args):
    """None when an Inspector's Discovery call may run, else (error code, plain message)."""
    if op not in INSPECTOR_DISCOVERY_OPS:
        return "forbidden", "This account is view only."
    if op in ("quote", "plan"):
        cap = args.get("spend_cap_cents")
        if not isinstance(cap, int) or isinstance(cap, bool) or cap > CAP_CENTS:
            return "inspector_cap", f"A view-only account may spend at most {CAP_CENTS} cents on one run."
    if op in OWN_RUN_OPS:
        run = store.get("discovery_runs", args.get("run_id")) if isinstance(args.get("run_id"), str) else None
        if run is None or run.get("created_by") != access.actor:
            return "forbidden", "A view-only account may only work with a run it started."
    return None
