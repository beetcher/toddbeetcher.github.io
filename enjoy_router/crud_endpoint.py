"""The CRUD endpoints, with no Firebase in it: one dispatcher, two front doors.

    handle_crud_test   enjoy_crud_test: every op, test_-prefixed collections only (main.py gives it that store).
    handle_admin       enjoy_admin: the Console's door to the real collections; only the ops in ADMIN_OPS (everything but set_review_summary).

main.py turns a Firebase request into one of these; tests call them directly.

    POST  ...  Authorization: Bearer <ICDT_ADMIN_KEY>
    body: {"collection": "venues", "op": "create", "args": {...}}

ops and their args:
    create             data, source (optional)
    get                id, include_deleted (optional), expand (optional, venues and the rosters: read in what each record points at)
    list               filters, order, limit (all optional), expand (optional, venues and the rosters), near_zip (optional, venues with expand: nearest first, each with miles)
    update             id, changes, expected_updated_at (optional)
    soft_delete        id
    set_review_summary id, review_count, average_rating
    suggest            request_id             (registration_assignments only: what one touch would do)
    queue              limit (optional)       (registration_assignments only: the state of each recent request)
    get_for_individual individual_id          (individual_restricted_details only: the one record for a person)
    merge              survivor_id, duplicate_id, reason, field_choices (optional)   (individuals only)
    unmerge            id                     (individuals only: id is the merge event)
    erase              id                     (individuals only; the test door only, never the Console)
    end                valid_to, expected_updated_at (both optional)   (location_links only: ends the link, valid_to defaults to today)
    find_by_address    address, limit (optional)   (locations only: live locations that already hold this address)
    create_with_place  data, address or location_id (optional), source (optional)   (venues only: venue, place and link saved together)
    set_place          id, address or location_id   (venues only: moves the venue to another place, old link ends today)
    find_gps           id                           (venues only: looks up GPS from the place's street address; best effort, says what happened in `gps`)
    create_with_person data, person (optional), source (optional)   (the rosters only: data.individual_id for an existing person, or person for a new one; saved together)
    assign             data, person (optional), source (optional)   (attendances only: put a person in a class: person, roster entry and record together)
    send_confirmation  id                     (attendances only: send the placement confirmation email now)
    update_with_person id, changes and/or person, expected_updated_at (optional)   (the rosters only: roster fields and the person's name and contact, saved together)
    send_invite        id                     (access_persons only: send the invitation email again, by hand)

The test door is a TEST tool: main.py gives it a store whose collection names carry the prefix `test_`, so it can
never read or write a real collection. Its actor is always system:crud_test. The admin door works on the real
collections and stamps user:admin until Google sign-in replaces the key. Real services call the handlers in-process.

Fails closed like the Console: no admin key setting (or shorter than 32 characters) means nothing is allowed.
Logs only codes, never the key and never record content.
"""
from __future__ import annotations

import hmac
import json
import logging
from datetime import datetime

from access import delegate as _delegate, door as _door, guard as _guard, policy as _policy
from access.territory import Scope, Territory
from console import MIN_KEY_LENGTH, _bearer, make_failure_limiter  # noqa: F401  (make_failure_limiter re-exported)
from crud import (access_persons_service, access_roles_crud, activity_events_crud, console_settings_crud, assignments_service, attendances_service, classes_service, communication_logs_crud, comms_settings_crud, curriculums_crud,
                  individual_restricted_details_service, message_templates_crud,
                  individuals_service, journal_events_crud, instructor_rosters_service, location_links_service, locations_service,
                  merge_events_service, organization_links_service, organizations_crud, student_rosters_service, venues_service,
                  discovery_areas_crud, discovery_models_crud, discovery_prompts_crud, discovery_runs_crud, discovery_settings_crud,
                  discovery_types_crud)
from crud.schema_kit import failure, success
from handler import HttpResult, _error
from ratelimit import RateLimiter

log = logging.getLogger("enjoy_router")
TEST_ACTOR = "system:crud_test"
ADMIN_ACTOR = "user:admin"   # what the admin key stamps (access.authorize.KEY_ACTOR); a Google sign-in stamps user:<access_person id>
MAX_BODY_BYTES = 100_000

# collection -> module with the handler's function names (a handler file, or a service wrapping one). New collections are added here.
HANDLERS = {"venues": venues_service, "scheduled_classes": classes_service, "registration_assignments": assignments_service,
            "individuals": individuals_service, "individual_restricted_details": individual_restricted_details_service,
            "merge_events": merge_events_service, "locations": locations_service, "location_links": location_links_service,
            "instructor_rosters": instructor_rosters_service, "student_rosters": student_rosters_service,
            "curriculums": curriculums_crud, "attendances": attendances_service, "journal_events": journal_events_crud,
            "organizations": organizations_crud, "organization_links": organization_links_service,
            "message_templates": message_templates_crud, "communication_logs": communication_logs_crud,
            "comms_settings": comms_settings_crud, "discovery_models": discovery_models_crud, "discovery_areas": discovery_areas_crud,
            "discovery_types": discovery_types_crud, "discovery_prompts": discovery_prompts_crud, "discovery_settings": discovery_settings_crud,
            "discovery_runs": discovery_runs_crud, "access_roles": access_roles_crud, "access_persons": access_persons_service,
            "activity_events": activity_events_crud, "console_settings": console_settings_crud}
# Collections the Console door does not reach yet (sensitive: needs the Console panel and sign-in roles first). The test door reaches them.
ADMIN_BLOCKED_COLLECTIONS = frozenset({"individual_restricted_details", "discovery_runs"})   # runs: only the Discovery service writes them

# op -> (required args, optional args)
OPS = {
    "create": ({"data"}, {"source"}),
    "get": ({"id"}, {"include_deleted", "expand"}),
    "list": (set(), {"filters", "order", "limit", "expand", "near_zip"}),
    "update": ({"id", "changes"}, {"expected_updated_at"}),
    "soft_delete": ({"id"}, set()),
    "set_review_summary": ({"id", "review_count", "average_rating"}, set()),
    "suggest": ({"request_id"}, set()),   # only collections whose module has it (assignments)
    "queue": (set(), {"limit"}),          # same
    "get_for_individual": ({"individual_id"}, set()),  # only individual_restricted_details: the one record for a person
    "merge": ({"survivor_id", "duplicate_id", "reason"}, {"field_choices"}),  # only individuals
    "unmerge": ({"id"}, set()),                        # only individuals
    "erase": ({"id"}, set()),                          # only individuals; not in ADMIN_OPS
    "end": ({"id"}, {"valid_to", "expected_updated_at"}),   # only location_links
    "find_by_address": ({"address"}, {"limit"}),       # only locations
    "create_with_place": ({"data"}, {"address", "location_id", "source"}),   # only venues
    "create_with_person": ({"data"}, {"person", "source"}),                  # only the rosters
    "set_place": ({"id"}, {"address", "location_id"}),                       # only venues
    "find_gps": ({"id"}, set()),                                             # only venues: look up GPS from the place's address
    "assign": ({"data"}, {"person", "source", "via_request_id"}),                              # only attendances: person + roster entry + attendance together
    "send_confirmation": ({"id"}, set()),                                    # only attendances: send the placement confirmation email now
    "delete_request": ({"id"}, set()),                                       # only attendances: a registration request is marked deleted and hidden
    "assign_request": ({"data"}, {"requester", "source"}),                   # only attendances: everyone named on a request into one class
    "update_with_person": ({"id"}, {"changes", "person", "expected_updated_at"}),   # only the rosters
    "publish": ({"id"}, {"expected_updated_at"}),      # only message_templates: a draft becomes the standing version
    "draft_from": ({"id"}, set()),                     # only message_templates: copy a published version into a new draft
    "mark_handled": ({"id"}, {"note"}),                # only communication_logs: a person dealt with a not_sent message
    "add_note": ({"id", "text"}, set()),               # only communication_logs: a comment on an entry (add only)
    "send_invite": ({"id"}, set()),                    # only access_persons: send (or resend) the invitation email
}
# Ops the Console may use. set_review_summary is for the reviews service only, never the Console.
# erase is deliberately missing: it is irreversible and waits for sign-in roles.
ADMIN_OPS = frozenset({"list", "get", "create", "update", "soft_delete", "suggest", "queue", "get_for_individual",
                       "merge", "unmerge", "end", "find_by_address", "create_with_place", "set_place", "find_gps",
                       "create_with_person", "update_with_person", "assign", "assign_request", "delete_request", "send_confirmation", "publish", "draft_from", "mark_handled", "add_note", "send_invite"})
STATUS = {"validation_failed": 400, "not_found": 404, "conflict": 409, "server_error": 500}


def _run(module, store, op: str, a: dict, now: datetime, actor: str):
    if op in ("get", "list") and a.get("expand") and not getattr(module, "EXPANDABLE", False):
        return failure("validation_failed", [{"field": "expand", "issue": "not_supported"}])
    if op in ("suggest", "queue", "set_review_summary", "get_for_individual", "merge", "unmerge", "erase", "end", "find_by_address",
              "create_with_place", "set_place", "find_gps", "create_with_person", "update_with_person", "assign", "assign_request", "delete_request", "send_confirmation",
              "publish", "draft_from", "mark_handled", "add_note", "send_invite"):
        if not hasattr(module, op):
            return failure("validation_failed", [{"field": "op", "issue": "not_supported"}])
        if op == "create_with_place":
            return module.create_with_place(store, a["data"], actor, a.get("address"), a.get("location_id"), a.get("source", "dashboard"), now=now)
        if op == "send_confirmation":
            return module.send_confirmation(store, a["id"], actor, now=now)
        if op == "publish":
            return module.publish(store, a["id"], actor, a.get("expected_updated_at"), now=now)
        if op == "draft_from":
            return module.draft_from(store, a["id"], actor, now=now)
        if op == "mark_handled":
            return module.mark_handled(store, a["id"], actor, a.get("note"), now=now)
        if op == "add_note":
            return module.add_note(store, a["id"], actor, a.get("text"), now=now)
        if op == "send_invite":
            return module.send_invite(store, a["id"], actor, now=now)
        if op == "assign":
            return module.assign(store, a["data"], actor, a.get("person"), a.get("source", "dashboard"), now=now, via_request_id=a.get("via_request_id"))
        if op == "delete_request":
            return module.delete_request(store, a["id"], actor, now=now)
        if op == "assign_request":
            return module.assign_request(store, a["data"], actor, a.get("requester"), a.get("source", "dashboard"), now=now)
        if op == "create_with_person":
            return module.create_with_person(store, a["data"], actor, a.get("person"), a.get("source", "dashboard"), now=now)
        if op == "update_with_person":
            return module.update_with_person(store, a["id"], a.get("changes"), actor, a.get("person"), a.get("expected_updated_at"), now=now)
        if op == "find_gps":
            return module.find_gps(store, a["id"], actor, now=now)
        if op == "set_place":
            return module.set_place(store, a["id"], actor, a.get("address"), a.get("location_id"), now=now)
        if op == "end":
            return module.end(store, a["id"], actor, a.get("valid_to"), a.get("expected_updated_at"), now=now)
        if op == "find_by_address":
            return module.find_by_address(store, a["address"], **({"limit": a["limit"]} if "limit" in a else {}))
        if op == "get_for_individual":
            return module.get_for_individual(store, a["individual_id"])
        if op == "merge":
            return module.merge(store, a["survivor_id"], a["duplicate_id"], a["reason"], actor, a.get("field_choices"), now=now)
        if op == "unmerge":
            return module.unmerge(store, a["id"], actor, now=now)
        if op == "erase":
            return module.erase(store, a["id"], actor, now=now)
        if op == "suggest":
            return module.suggest(store, a["request_id"])
        if op == "queue":
            return module.queue(store, **({"limit": a["limit"]} if "limit" in a else {}))
        return module.set_review_summary(store, a["id"], a["review_count"], a["average_rating"], now=now)
    if op == "create":
        return module.create(store, a["data"], actor, a.get("source", "dashboard"), now=now)
    if op == "get":
        return module.get(store, a["id"], a.get("include_deleted", False), **({"expand": True} if a.get("expand") else {}))
    if op == "list":
        kw = {k: a[k] for k in ("order", "limit") if k in a}
        if a.get("expand"):
            kw["expand"] = True
        if "near_zip" in a:
            if not hasattr(module, "_position") or not isinstance(a["near_zip"], str):   # only venues rank by distance
                return failure("validation_failed", [{"field": "near_zip", "issue": "not_supported"}])
            kw["near_zip"] = a["near_zip"]
        return module.list(store, a.get("filters"), **kw)
    if op == "update":
        return module.update(store, a["id"], a["changes"], actor, a.get("expected_updated_at"), now=now)
    if op == "soft_delete":
        return module.soft_delete(store, a["id"], actor, now=now)
    return module.set_review_summary(store, a["id"], a["review_count"], a["average_rating"], now=now)


def handle_crud(method: str, authorization: str, raw_body: bytes, admin_key: str, visitor: str,
                store, limiter: RateLimiter, now: datetime, actor, allowed_ops, tag: str,
                blocked_collections=frozenset(), verifier=None, allow_me=False) -> HttpResult:
    """actor: a fixed actor string (the test door: key only, no per-person rules), or None = who signed in (the Console door:
    the key or a Google sign-in, with the capability rules in access/policy.py)."""
    if method.upper() != "POST":
        return _error(405, "validation_failed", "Use POST.", {"Allow": "POST"})

    access, refusal = _door.sign_in(authorization, admin_key=admin_key, verifier=verifier, store=store, limiter=limiter,
                                    visitor=visitor, now=now, tag=tag)
    if refusal:
        return refusal
    who = access.actor if actor is None else actor

    if len(raw_body) > MAX_BODY_BYTES:
        return _error(413, "validation_failed", "The request is too large.")
    try:
        body = json.loads(raw_body.decode("utf-8")) if raw_body else None
    except (UnicodeDecodeError, ValueError):
        return _error(400, "validation_failed", "The request body must be JSON.")
    if not isinstance(body, dict):
        return _error(400, "validation_failed", "Send a JSON object with collection, op and args.")
    if body.get("op") == "me":   # who is signed in and what they may do (the Console door only)
        if not allow_me:
            return _error(400, "validation_failed", "This op is not enabled here.")
        return HttpResult(200, {"ok": True, "data": _door.me(access)}, {"Cache-Control": "no-store"})

    collection, op, args = body.get("collection"), body.get("op"), body.get("args", {})
    if collection not in HANDLERS:
        return _error(400, "validation_failed", "Unknown collection. Known: " + ", ".join(sorted(HANDLERS)) + ".")
    if op not in OPS:
        return _error(400, "validation_failed", "Unknown op. Known: " + ", ".join(sorted(OPS)) + ".")
    if not isinstance(args, dict):
        return _error(400, "validation_failed", "args must be an object.")
    if op not in allowed_ops or collection in blocked_collections:
        return _error(400, "validation_failed", "This op is not enabled here.")
    if actor is None and not _policy.allowed(access, _policy.crud_need(collection, op, args)):
        # an instructor may LOOK at the roster of a class they teach; the guard then keeps only those classes' records
        if not ((collection == "attendances" and op in _policy.READ_OPS and access.ok and access.individual_id)
                or (collection in _delegate.COLLECTIONS and _delegate.has_door(access))):
            return _door.forbidden(tag)
    required, optional = OPS[op]
    missing, extra = sorted(required - set(args)), sorted(set(args) - required - optional)
    if missing or extra:
        return _error(400, "validation_failed",
                      f"For {op}: " + (f"missing {', '.join(missing)}. " if missing else "")
                      + (f"not allowed: {', '.join(extra)}." if extra else ""))

    scope = Scope(access, Territory(store)) if actor is None and not access.is_super_admin else None   # a person with limited territory
    try:
        if scope is not None and not _guard.before(scope, store, collection, op, args):
            return _door.forbidden(tag)
        run_args, want = _guard.widen(scope, collection, op, args) if scope is not None else (args, None)
        result = _run(HANDLERS[collection], store, op, run_args, now, who)
        if scope is not None and result.ok:
            shown = _guard.after(scope, store, collection, op, result.data)
            shown = _guard.trim(shown, want)
            if shown is None:
                return _door.forbidden(tag)
            result = success(shown)
    except Exception as exc:  # say nothing about the cause
        log.error("%s code=server_error op=%s exception=%s", tag, op, type(exc).__name__)
        return _error(500, "server_error", "Could not complete the request.")

    if result.ok:
        log.info("%s collection=%s op=%s code=ok", tag, collection, op)
        return HttpResult(200, {"ok": True, "data": result.data}, {"Cache-Control": "no-store"})
    log.info("%s collection=%s op=%s code=%s", tag, collection, op, result.code)
    res = _error(STATUS.get(result.code, 400), result.code, "The request was refused.")
    res.body["error"]["problems"] = result.problems
    return res


def handle_crud_test(method, authorization, raw_body, admin_key, visitor, store, limiter, now) -> HttpResult:
    return handle_crud(method, authorization, raw_body, admin_key, visitor, store, limiter, now,
                       TEST_ACTOR, frozenset(OPS), "crud_test")


def handle_admin(method, authorization, raw_body, admin_key, visitor, store, limiter, now, verifier=None) -> HttpResult:
    return handle_crud(method, authorization, raw_body, admin_key, visitor, store, limiter, now,
                       None, ADMIN_OPS, "admin", ADMIN_BLOCKED_COLLECTIONS, verifier=verifier, allow_me=True)
