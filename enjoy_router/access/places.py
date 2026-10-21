"""Where a record is: the ZIP that decides whose territory it is in (P-60 / P-65).

Every function takes the store (one that holds the records) and returns a five-digit ZIP, or None when the record has no place we can
read (None is covered only by an `all` grant). Nothing here writes. The rules, from Todd's design of 2026-10-20:

    venue                 the ZIP of the place it operates at (live operates_at link, primary first)
    scheduled class       its venue's ZIP
    registration request  its own postal_code; else its class's venue; else a class built from it; else the venue it asked for
    registration_assignment / attendance / communication_log   through the request or class they point at
    person (individual)   the ZIP of where they live (live resides_at / mailing_address_for link, primary first)
    instructor / student roster entry   the person's ZIP
    location              its own address ZIP;  location link: its location's ZIP
"""
from __future__ import annotations

from .territory import norm_zip

HOME_LINKS = ("resides_at", "mailing_address_for")


def zip_of_location(loc):
    """The ZIP of a location record: the primary current address first, else any current address."""
    if not isinstance(loc, dict):
        return None
    addrs = [a for a in loc.get("addresses", []) if a.get("usage") != "former"]
    addrs.sort(key=lambda a: not a.get("is_primary"))
    for a in addrs:
        z = norm_zip(a.get("postal_code"))
        if z:
            return z
    return None


def _live(doc):
    return doc is not None and "deleted_at" not in doc


def _zip_via_links(store, subject_type, subject_id, relationships):
    if not subject_id:
        return None
    links = [l for l in store.query("location_links", [("subject_id", "==", subject_id)], limit=100)
             if _live(l) and l.get("status") == "active" and l.get("subject_type") == subject_type and l.get("relationship") in relationships]
    links.sort(key=lambda l: (not l.get("is_primary"), l.get("created_at", "")))
    for l in links:
        z = zip_of_location(store.get("locations", l.get("location_id")))
        if z:
            return z
    return None


def zip_of_venue(store, venue_id):
    return _zip_via_links(store, "venue", venue_id, ("operates_at",))


def zip_of_region_id(store, region_id):
    """The first ZIP (sorted) on the region's list, so a request that picked a region and gave no ZIP is placed inside it. None if none."""
    if not region_id:
        return None
    r = store.get("discovery_areas", region_id)
    if not isinstance(r, dict) or r.get("deleted_at") or r.get("kind") != "region":
        return None
    zips = sorted(z for z in (norm_zip(x) for x in r.get("zip_codes", [])) if z)
    return zips[0] if zips else None


def zip_of_person(store, individual_id):
    return _zip_via_links(store, "individual", individual_id, HOME_LINKS)


def zip_of_class(store, class_doc):
    return zip_of_venue(store, class_doc.get("venue_id")) if isinstance(class_doc, dict) else None


def zip_of_class_id(store, class_id):
    doc = store.get("scheduled_classes", class_id) if class_id else None
    return zip_of_class(store, doc) if _live(doc) else None


def zip_of_request(store, request_doc):
    if not isinstance(request_doc, dict):
        return None
    z = norm_zip(request_doc.get("postal_code"))
    if z:
        return z
    z = zip_of_class_id(store, request_doc.get("scheduled_class_id"))
    if z:
        return z
    for c in store.query("scheduled_classes", [("source_request_id", "==", request_doc.get("id"))], limit=5):   # a class built from a party request
        z = zip_of_class(store, c) if _live(c) else None
        if z:
            return z
    z = zip_of_venue(store, request_doc.get("preferred_venue_id"))
    if z:
        return z
    return zip_of_region_id(store, request_doc.get("region_id"))


def zip_of_request_id(store, request_id):
    doc = store.get("registration_requests", request_id) if request_id else None
    return zip_of_request(store, doc) if _live(doc) else None


def zip_of_link(store, link_doc):
    return zip_of_location(store.get("locations", link_doc.get("location_id"))) if isinstance(link_doc, dict) else None


def zip_of(store, collection, doc):
    """The ZIP of one record of any territorial collection, or None. Collections with no place of their own return None."""
    if not isinstance(doc, dict):
        return None
    if collection == "venues":
        return zip_of_venue(store, doc.get("id"))
    if collection == "scheduled_classes":
        return zip_of_class(store, doc)
    if collection == "registration_requests":
        return zip_of_request(store, doc)
    if collection == "registration_assignments":
        return zip_of_request_id(store, doc.get("request_id")) or zip_of_class_id(store, doc.get("scheduled_class_id"))
    if collection == "attendances":
        return zip_of_class_id(store, doc.get("scheduled_class_id")) or zip_of_request_id(store, doc.get("request_id"))
    if collection == "communication_logs":
        return (zip_of_class_id(store, doc.get("scheduled_class_id")) or zip_of_request_id(store, doc.get("request_id"))
                or zip_of_person(store, doc.get("individual_id")))
    if collection in ("instructor_rosters", "student_rosters"):
        return zip_of_person(store, doc.get("individual_id"))
    if collection == "individuals":
        return zip_of_person(store, doc.get("id"))
    if collection == "locations":
        return zip_of_location(doc)
    if collection == "location_links":
        return zip_of_link(store, doc)
    return None
