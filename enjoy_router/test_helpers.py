"""Small helpers shared by the test scripts."""
from crud import locations_crud as _LOC, location_links_service as _LKS


def give_address(store, individual_id, region="CO", actor="user:admin"):
    """Give a person a live Lives-here address in `region`, the way the Console does (a place plus a resides_at link).
    An instructor roster entry needs this (slice B)."""
    loc = _LOC.create(store, {"name": "Test home", "addresses": [{"usage": "civic", "street_number": "1", "street": "Test St", "locality": "Town",
                                                                   "region": region, "postal_code": "80027", "country": "US"}]}, actor)
    assert loc.ok, loc.problems
    lk = _LKS.create(store, {"subject_type": "individual", "subject_id": individual_id, "location_id": loc.data["id"],
                             "relationship": "resides_at", "is_primary": True}, actor)
    assert lk.ok, lk.problems
    return lk.data


def give_venue_zone(store, venue_id, zone="America/Denver", actor="user:admin"):
    """Give a venue a place that carries its time zone (the Console no longer guesses Denver for a class at a venue with none)."""
    loc = _LOC.create(store, {"name": "Test place", "time_zone": zone, "addresses": [{"usage": "civic", "street_number": "1", "street": "Test St", "locality": "Town",
                                                                                      "region": "CO", "postal_code": "80027", "country": "US"}]}, actor)
    assert loc.ok, loc.problems
    lk = _LKS.create(store, {"subject_type": "venue", "subject_id": venue_id, "location_id": loc.data["id"], "relationship": "operates_at", "is_primary": True}, actor)
    assert lk.ok, lk.problems
    return lk.data
