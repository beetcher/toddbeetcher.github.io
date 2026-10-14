"""Service for venues: the guards the venue schema asks for, on top of venues_crud (see classes_service.py).

    * a venue that live classes point at cannot be deleted   (conflict, id:in_use)
    * a room a live class uses cannot be removed or renamed
                                                                (validation_failed, rooms:in_use)
    * a venue becomes active only when it has a place: a live operates_at location_link to a location that is
      active and has an address or a GPS point                   (validation_failed, status:place_required)
      A link needs the venue to exist first, so a venue is created inactive, linked, then activated;
      creating one already active is refused for the same reason.
    * contact_individual_id and backup_contact_individual_id point at an individual that exists and is not erased
      (a merged person is followed to the survivor)               (validation_failed, <field>:not_found)
Reading and the one-window flows (Part 2, presentation):
    * get / list with expand=True return each venue with `place` (the place it operates at: name, address, GPS flag, time
      zone), `main_contact` and `backup_contact` (id and display_name) read from the linked records. Nothing is stored twice.
    * create_with_place saves a venue (inactive), its place and the operates_at link together, or nothing.
    * set_place moves a venue to another place: the old link ends today, the new one starts today, together.
Everything else passes straight through to the handler file. Same function names as a handler file.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import geocoder
from . import individuals_crud as I
from . import individuals_service as IS
from . import location_links_crud as LK
from . import locations_crud as LOC
from . import venues_crud as V
from .classes_service import _find_room, live_classes_at
from .schema_kit import UUID_PATTERN, failure, success

import geo_rank  # top-level module of enjoy_router: distances from a Colorado ZIP

CONTACT_FIELDS = ("contact_individual_id", "backup_contact_individual_id")
EXPANDABLE = True  # the endpoint passes expand=True only to modules that say so


def contact_problems(store, data) -> list:
    """Each contact pointer present must name an individual that exists and is not erased."""
    out = []
    for f in CONTACT_FIELDS:
        v = data.get(f)
        if isinstance(v, str) and UUID_PATTERN.match(v):
            got = I.get(store, v)
            if not got.ok or got.data.get("status") == "erased":
                out.append({"field": f, "issue": "not_found"})
    return out


def has_place(store, venue_id: str) -> bool:
    """True when a live operates_at link joins this venue to an active location that has an address or a GPS point."""
    for link in LK.live_for(store, "subject_id", venue_id):
        if link.get("subject_type") != "venue" or link.get("relationship") != "operates_at" or not LK.is_live(link):
            continue
        got = LOC.get(store, link["location_id"])
        if got.ok and place_ok(got.data):
            return True
    return False


def place_ok(loc: dict) -> bool:
    """An active location that has an address (not a former one) or a GPS point."""
    return loc.get("status") == "active" and bool(
        loc.get("geometries") or any(a.get("usage") != "former" for a in loc.get("addresses", [])))


def make_room_check(store, venue_id: str):
    def check(merged: dict) -> list:
        for c in live_classes_at(store, venue_id):
            if not c.get("venue_room_label"):
                continue
            room = _find_room(merged, c["venue_room_label"])
            if room is None:
                return [{"field": "rooms", "issue": "in_use"}]
        return []
    return check


def _create_problems(store, data) -> list:
    if not isinstance(data, dict):
        return []
    problems = contact_problems(store, data)
    if data.get("status") == "active":  # no link can exist before the venue does
        problems.append({"field": "status", "issue": "place_required"})
    return problems


def create(store, data, actor, source="dashboard", tx=None, now=None):
    problems = _create_problems(store, data)
    if problems:
        return failure("validation_failed", problems)
    return V.create(store, data, actor, source, tx=tx, now=now)


def _live_place_link(store, venue_id):
    links = [l for l in LK.live_for(store, "subject_id", venue_id)
             if l.get("subject_type") == "venue" and l.get("relationship") == "operates_at" and LK.is_live(l)]
    links.sort(key=lambda l: (not l.get("is_primary"), l.get("created_at", "")))
    return links


def _place_view(store, venue_id):
    for link in _live_place_link(store, venue_id):
        got = LOC.get(store, link["location_id"])
        if not got.ok:
            continue
        loc = got.data
        addrs = [a for a in loc.get("addresses", []) if a.get("usage") != "former"]
        addrs.sort(key=lambda a: not a.get("is_primary"))
        view = {"location_id": loc["id"], "link_id": link["id"], "name": loc.get("name"),
                "has_gps": bool(loc.get("geometries")), "status": loc.get("status")}
        if loc.get("geometries"):
            view["gps_source"] = "looked_up" if all(g.get("source") == "geocoder" for g in loc["geometries"]) else "entered"
        if addrs:
            view["address"] = addrs[0]
        if loc.get("time_zone"):
            view["time_zone"] = loc["time_zone"]
        return view
    return None


def _person_view(store, person_id):
    got = IS.get(store, person_id)
    if not got.ok or got.data.get("status") == "erased":
        return {"id": person_id, "unavailable": True}
    return {"id": got.data["id"], "display_name": got.data.get("display_name")}


def expanded(store, rec: dict) -> dict:
    """The venue with the records it points at read in: place, main_contact, backup_contact. Nothing here is stored."""
    out = dict(rec)
    place = _place_view(store, rec["id"])
    if place:
        out["place"] = place
    if rec.get("contact_individual_id"):
        out["main_contact"] = _person_view(store, rec["contact_individual_id"])
    if rec.get("backup_contact_individual_id"):
        out["backup_contact"] = _person_view(store, rec["backup_contact_individual_id"])
    return out


def get(store, id, include_deleted=False, expand=False):  # noqa: A002
    r = V.get(store, id, include_deleted)
    if r.ok and expand:
        return success(expanded(store, r.data))
    return r


def _position(store, venue_id):
    """[lat, lon] of the venue's place: its GPS, else the centre of its address ZIP, else None."""
    for link in _live_place_link(store, venue_id):
        got = LOC.get(store, link["location_id"])
        if got.ok:
            pos = geo_rank.position_of_place(got.data)
            if pos:
                return pos
    return None


def list(store, filters=None, expand=False, near_zip=None, **kw):  # noqa: A001, A002
    """With expand and a known Colorado near_zip: each record also carries miles (one decimal, straight line, when its
    position is known) and the list is nearest first, venues with no position last by name. An unknown or invalid
    near_zip is ignored: the list stays in the order asked for. near_zip without expand is not_supported."""
    if near_zip is not None and not expand:
        return failure("validation_failed", [{"field": "near_zip", "issue": "requires_expand"}])
    r = V.list(store, filters, **kw)
    if r.ok and expand:
        recs = [expanded(store, d) for d in r.data["records"]]
        origin = geo_rank.zip_origin(near_zip)
        if origin:
            for d in recs:
                pos = _position(store, d["id"])
                if pos:
                    d["miles"] = round(geo_rank.miles_between(origin, pos), 1)
            recs.sort(key=lambda d: (d.get("miles") is None, d.get("miles", 0), (d.get("name") or "").lower()))
        return success({"records": recs, "count": r.data["count"]})
    return r


def update(store, id, changes, actor, expected_updated_at=None, tx=None, now=None):
    if not isinstance(id, str):
        return V.update(store, id, changes, actor, expected_updated_at, tx=tx, now=now)
    rooms = make_room_check(store, id)
    activating = isinstance(changes, dict) and changes.get("status") == "active"

    def check(merged: dict) -> list:
        changed = {f: merged[f] for f in CONTACT_FIELDS if isinstance(changes, dict) and f in changes and f in merged}
        problems = rooms(merged) + contact_problems(store, changed)  # only pointers being changed, so an old one cannot block other edits
        if activating and not has_place(store, id):
            problems.append({"field": "status", "issue": "place_required"})
        return problems
    return V.update(store, id, changes, actor, expected_updated_at, tx=tx, now=now, check=check,
                    check_fields=("rooms", "status", *CONTACT_FIELDS))


def soft_delete(store, id, actor, tx=None, now=None):
    if isinstance(id, str) and live_classes_at(store, id, limit=1):
        return failure("conflict", [{"field": "id", "issue": "in_use"}])
    return V.soft_delete(store, id, actor, tx=tx, now=now)


def set_review_summary(store, id, review_count, average_rating, actor="system:reviews", tx=None, now=None):
    return V.set_review_summary(store, id, review_count, average_rating, actor, tx=tx, now=now)


# =============================================================================
# one-window flows: a venue and its place saved together
# =============================================================================

class _Abort(Exception):
    """Raised inside a transaction block so nothing in it is written; carries the failure to return."""
    def __init__(self, result):
        self.result = result


def _address_problems(problems: list) -> list:
    return [{"field": "address" if p["field"] == "addresses" else p["field"], "issue": p["issue"]} for p in problems]


def _place_args_problems(address, location_id) -> list:
    if address is not None and location_id is not None:
        return [{"field": "address", "issue": "choose_one"}]
    if address is not None and not isinstance(address, dict):
        return [{"field": "address", "issue": "invalid_type"}]
    if location_id is not None and not (isinstance(location_id, str) and UUID_PATTERN.match(location_id)):
        return [{"field": "location_id", "issue": "invalid_format"}]
    return []


def _saved_place_problems(store, location_id) -> list:
    loc = store.get(LOC.LOCATIONS.name, location_id)
    if loc is None or "deleted_at" in loc:
        return [{"field": "location_id", "issue": "not_found"}]
    if loc.get("status") != "active":
        return [{"field": "location_id", "issue": "retired"}]
    return []


def _new_place(store, tx, name, address, actor, source, now):
    """Create the place for a typed address inside the caller's transaction; returns its id."""
    addr = {"usage": "civic", "is_primary": True, **address}
    r = LOC.create(store, {"name": name, "kind": "site", "addresses": [addr]}, actor, source, tx=tx, now=now)
    if not r.ok:
        raise _Abort(failure("validation_failed", _address_problems(r.problems)))
    return r.data["id"]


def _link_to(store, tx, venue_id, location_id, actor, source, now, valid_from=None):
    data = {"subject_type": "venue", "subject_id": venue_id, "location_id": location_id,
            "relationship": "operates_at", "is_primary": True}
    if valid_from:
        data["valid_from"] = valid_from
    r = LK.create(store, data, actor, source, tx=tx, now=now)
    if not r.ok:
        raise _Abort(failure("validation_failed", r.problems))
    return r.data["id"]


def create_with_place(store, data, actor, address=None, location_id=None, source="dashboard", now=None):
    """Add a venue the way a person says it: a name and, if known, where. The venue is saved inactive; with an address a
    new place is saved too (named after the venue), with location_id an existing place is used; either way the
    operates_at link joins them. All saved together or none."""
    problems = _create_problems(store, data) + _place_args_problems(address, location_id)
    if not problems and location_id is not None:
        problems = _saved_place_problems(store, location_id)
    if problems:
        return failure("validation_failed", problems)
    out: dict = {}
    try:
        with store.transaction() as tx:
            r = V.create(store, data, actor, source, tx=tx, now=now)
            if not r.ok:
                raise _Abort(r)
            venue = r.data
            loc_id = location_id
            if address is not None:
                loc_id = _new_place(store, tx, venue["name"], address, actor, source, now)
            if loc_id is not None:
                out["link_id"] = _link_to(store, tx, venue["id"], loc_id, actor, source, now)
            out["venue"], out["location_id"] = venue, loc_id
    except _Abort as stop:
        return stop.result
    if address is not None:
        _try_gps(store, out["venue"]["id"], actor, now)
    return success({**expanded(store, V.get(store, out["venue"]["id"]).data), "created_place": address is not None})



def _civic_address(loc: dict):
    addrs = [a for a in loc.get("addresses", []) if a.get("usage") == "civic"]
    addrs.sort(key=lambda a: not a.get("is_primary"))
    return addrs[0] if addrs else None


def find_gps(store, id, actor, now=None):  # noqa: A002
    """Look up GPS for a venue's place from its street address and save it as a center point marked source geocoder.
    Best effort, never an error for the venue: the result says what happened in `gps`:
      found | no_match | skipped_not_public | skipped_entered (a point someone entered is kept) | skipped_no_address | skipped_off
    Only points this lookup made (source geocoder) are ever replaced."""
    got = V.get(store, id)
    if not got.ok:
        return got
    venue = got.data

    def done(status, **extra):
        return success({**expanded(store, V.get(store, id).data), "gps": status, **extra})

    if geocoder.lookup is None:
        return done("skipped_off")
    if venue.get("is_public_venue") is not True:
        return done("skipped_not_public")
    links = _live_place_link(store, id)
    loc = None
    for link in links:
        r = LOC.get(store, link["location_id"])
        if r.ok:
            loc = r.data
            break
    if loc is None:
        return done("skipped_no_address")
    manual = [g for g in loc.get("geometries", []) if g.get("source") != "geocoder"]
    if manual:
        return done("skipped_entered")
    addr = _civic_address(loc)
    if addr is None or not geocoder.one_line(addr):
        return done("skipped_no_address")
    point = geocoder.lookup(addr)
    if point is None:
        return done("no_match")
    today = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    geo = {"role": "center", "geometry": {"type": "Point", "coordinates": [round(point[1], 6), round(point[0], 6)]},
           "source": "geocoder", "as_of": today}
    up = LOC.update(store, loc["id"], {"geometries": [geo]}, actor, now=now)
    if not up.ok:
        return done("no_match")
    return done("found")


def _try_gps(store, venue_id, actor, now):
    """After a venue or its place is saved: look up GPS without ever failing the save."""
    try:
        find_gps(store, venue_id, actor, now=now)
    except Exception:   # the save already happened; GPS can be found later with Find GPS
        pass


def set_place(store, id, actor, address=None, location_id=None, source="dashboard", now=None):
    """Move a venue to another place. Its live operates_at links end today and the new one starts today, together.
    An active venue must keep a place, so the new place needs an address or a GPS point."""
    problems = _place_args_problems(address, location_id)
    if address is None and location_id is None and not problems:
        problems = [{"field": "address", "issue": "required"}]
    got = V.get(store, id) if not problems else None
    if got is not None and not got.ok:
        return got
    if not problems and location_id is not None:
        problems = _saved_place_problems(store, location_id)
        if not problems and got.data.get("status") == "active" and not place_ok(store.get(LOC.LOCATIONS.name, location_id)):
            problems = [{"field": "status", "issue": "place_required"}]
    if problems:
        return failure("validation_failed", problems)
    venue = got.data
    old = _live_place_link(store, id)
    if location_id is not None and any(l["location_id"] == location_id for l in old):
        return success({**expanded(store, venue), "changed": False})  # already there
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d") if now is None else now.strftime("%Y-%m-%d")
    try:
        with store.transaction() as tx:
            for link in old:
                r = LK.update(store, link["id"], {"valid_to": today}, actor, tx=tx, now=now)
                if not r.ok:
                    raise _Abort(failure("validation_failed", r.problems))
            loc_id = location_id if location_id is not None else _new_place(store, tx, venue["name"], address, actor, source, now)
            _link_to(store, tx, id, loc_id, actor, source, now, valid_from=today)
    except _Abort as stop:
        return stop.result
    _try_gps(store, id, actor, now)
    return success({**expanded(store, V.get(store, id).data), "changed": True})
