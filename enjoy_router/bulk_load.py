"""Bulk loader: puts a PLAN of organizations, places, venues and links into the system through the admin door, and takes
them out again. First built for the organization test suite; the shape is meant to be reused by a future "load venues
for a new community" button.

A plan is a dict:
    {"marker": "LAUNCH test data",
     "orgs":   [{"key": "bvsd", "data": {organization fields}}],
     "places": [{"key": "bvsd_hq", "data": {location fields}, "part_of": "other_place_key" (optional)}],
     "venues": [{"key": "ozo_arapahoe", "data": {venue fields},
                 "place": "place_key" | "address": {address fields} | neither, "activate": True|False}],
     "links":  [("o:school", "part_of", "o:bvsd", {extras}),            # organization_link: target starts with o:
                ("o:bvsd", "operates_at", "p:bvsd_hq", {extras}),       # location_link:     target starts with p:
                ("v:ozo_arapahoe", "operated_by", "o:ozo", {})]}        # subject prefix o: organization, v: venue

`call(collection, op, **args)` returns (http_status, body) and is either the real HTTPS door or the in-process one, so the
same code is tested in memory and run live. Nothing here reads a key; the caller owns that.

load() keeps going when one record is refused and reports every refusal at the end. Nothing is ever merged or overwritten:
every record is a new create. cleanup() soft-deletes only what the manifest (or, failing that, the marker) names.
"""
from __future__ import annotations

LOC_LINK_RELATIONSHIPS = {"operates_at", "works_at", "owns", "manages", "resides_at", "mailing_address_for", "billing_address_for",
                          "delivers_to"}


def _data(res):
    return ((res[1] or {}).get("data")) or {}


def _problem_text(res):
    err = (res[1] or {}).get("error") or {}
    probs = err.get("problems") or []
    if probs:
        return ", ".join(f"{p.get('field')}:{p.get('issue')}" for p in probs)
    return str(err.get("code") or res[0])


def new_manifest():
    return {"orgs": {}, "places": {}, "venues": {}, "org_links": [], "loc_links": []}


def load(plan, call, say=print, ids=None):
    """Create everything in the plan. `ids` (optional) is filled in as records are made, so a caller can save it even if the
    run is interrupted. Returns {"ids": manifest, "errors": [...], "counts": {...}}."""
    ids = ids if ids is not None else new_manifest()
    errors, notes = [], []
    marker = plan.get("marker", "")

    def refused(label, res):
        errors.append(f"{label}: {_problem_text(res)}")
        say(f"  REFUSED {label}: {_problem_text(res)}")

    say(f"Organizations ({len(plan['orgs'])})")
    for o in plan["orgs"]:
        r = call("organizations", "create", data=o["data"], source="import")
        if r[0] == 200:
            ids["orgs"][o["key"]] = _data(r)["id"]
        else:
            refused("organization " + o["data"].get("name", o["key"]), r)

    say(f"Places ({len(plan['places'])})")
    for p in plan["places"]:
        data = dict(p["data"])
        if p.get("part_of"):
            parent = ids["places"].get(p["part_of"])
            if parent is None:
                errors.append(f"place {p['key']}: parent {p['part_of']} was not created")
                continue
            data["part_of_location_id"] = parent
        r = call("locations", "create", data=data, source="import")
        if r[0] == 200:
            ids["places"][p["key"]] = _data(r)["id"]
        else:
            refused("place " + data.get("name", p["key"]), r)

    say(f"Venues ({len(plan['venues'])})")
    for v in plan["venues"]:
        args = {"data": dict(v["data"], status="inactive"), "source": "import"}
        if v.get("place"):
            pid = ids["places"].get(v["place"])
            if pid is None:
                errors.append(f"venue {v['key']}: place {v['place']} was not created")
                continue
            args["location_id"] = pid
        elif v.get("address"):
            args["address"] = v["address"]
        r = call("venues", "create_with_place", **args)
        base_slug, n_try = args["data"]["slug"], 1
        while r[0] == 400 and "slug:duplicate" in _problem_text(r) and n_try < 6:
            # a removed venue still holds its slug ("never changes once set"), so a reload gets _2, _3, ...
            n_try += 1
            args["data"] = dict(args["data"], slug=f"{base_slug}_{n_try}")
            r = call("venues", "create_with_place", **args)
        if r[0] != 200:
            refused("venue " + v["data"].get("name", v["key"]), r)
            continue
        d = _data(r)
        ids["venues"][v["key"]] = d["id"]
        place = d.get("place") or {}
        if place.get("link_id"):
            ids["loc_links"].append(place["link_id"])      # the venue's own operates_at link
        if d.get("created_place") and place.get("location_id"):
            ids["places"]["venue_place:" + v["key"]] = place["location_id"]
        if v.get("activate", True) and (v.get("place") or v.get("address")):
            u = call("venues", "update", id=d["id"], changes={"status": "active"})
            if u[0] != 200:
                notes.append(f"venue {v['data']['name']} left inactive: {_problem_text(u)}")

    say(f"Links ({len(plan['links'])})")
    for subject, rel, target, extra in plan["links"]:
        extra = dict(extra or {})
        s_kind, s_key = subject.split(":", 1)
        t_kind, t_key = target.split(":", 1)
        s_id = (ids["orgs"] if s_kind == "o" else ids["venues"]).get(s_key)
        t_id = (ids["orgs"] if t_kind == "o" else ids["places"]).get(t_key)
        label = f"link {subject} {rel} {target}"
        if s_id is None or t_id is None:
            errors.append(f"{label}: an end was not created")
            continue
        stype = "organization" if s_kind == "o" else "venue"
        if t_kind == "o":
            r = call("organization_links", "create", data={"subject_type": stype, "subject_id": s_id, "organization_id": t_id,
                                                           "relationship": rel, **extra}, source="import")
            (ids["org_links"].append(_data(r)["id"]) if r[0] == 200 else refused(label, r))
        else:
            r = call("location_links", "create", data={"subject_type": stype, "subject_id": s_id, "location_id": t_id,
                                                       "relationship": rel, **extra}, source="import")
            (ids["loc_links"].append(_data(r)["id"]) if r[0] == 200 else refused(label, r))

    counts = {"organizations": len(ids["orgs"]), "places": len(ids["places"]), "venues": len(ids["venues"]),
              "organization_links": len(ids["org_links"]), "location_links": len(ids["loc_links"])}
    return {"ids": ids, "errors": errors, "notes": notes, "counts": counts, "marker": marker}


def _list_all(call, coll, **args):
    r = call(coll, "list", limit=200, **args)
    return (_data(r).get("records") or []) if r[0] == 200 else []


def find_existing(call, marker):
    """Organizations or venues already carrying the marker (a load that was never cleaned up)."""
    out = []
    for coll in ("organizations", "venues"):
        out += [x["id"] for x in _list_all(call, coll) if marker in (x.get("notes") or "")]
    return out


def cleanup(call, manifest, say=print):
    """Soft-delete links, then venues, then places, then organizations named in the manifest. Returns {"deleted": n, "errors": [...]}."""
    errors, n = [], 0

    def drop(coll, rid):
        nonlocal n
        r = call(coll, "soft_delete", id=rid)
        if r[0] == 200:
            n += 1
        elif r[0] != 404:
            errors.append(f"{coll} {rid}: {_problem_text(r)}")

    say("Removing links")
    for rid in manifest.get("org_links", []):
        drop("organization_links", rid)
    for rid in manifest.get("loc_links", []):
        drop("location_links", rid)
    say("Removing venues")
    for rid in manifest.get("venues", {}).values():
        drop("venues", rid)
    say("Removing places")
    for rid in manifest.get("places", {}).values():
        drop("locations", rid)
    say("Removing organizations")
    for rid in manifest.get("orgs", {}).values():
        drop("organizations", rid)
    return {"deleted": n, "errors": errors}


def scan_manifest(call, marker, say=print):
    """Rebuild a manifest by looking for the marker (used when the saved manifest is gone): organizations and venues whose notes
    carry it, places whose description carries it or that a marked venue operates at, and every link touching any of them."""
    m = new_manifest()
    for o in _list_all(call, "organizations"):
        if marker in (o.get("notes") or ""):
            m["orgs"][o["id"]] = o["id"]
    for v in _list_all(call, "venues"):
        if marker in (v.get("notes") or ""):
            m["venues"][v["id"]] = v["id"]
    for loc in _list_all(call, "locations"):
        if marker in (loc.get("description") or ""):
            m["places"][loc["id"]] = loc["id"]
    ends = set(m["orgs"].values()) | set(m["venues"].values())
    for vid in list(m["venues"].values()):
        for l in _list_all(call, "location_links", filters={"subject_id": vid}):
            m["loc_links"].append(l["id"])
            m["places"].setdefault(l["location_id"], l["location_id"])   # the place a test venue operates at
    seen_org, seen_loc = set(), set(m["loc_links"])
    for eid in ends | set(m["places"].values()):
        for flt in ({"subject_id": eid}, {"organization_id": eid}):
            for l in _list_all(call, "organization_links", filters=flt):
                if l["id"] not in seen_org:
                    seen_org.add(l["id"]); m["org_links"].append(l["id"])
        for flt in ({"subject_id": eid}, {"location_id": eid}):
            for l in _list_all(call, "location_links", filters=flt):
                if l["id"] not in seen_loc:
                    seen_loc.add(l["id"]); m["loc_links"].append(l["id"])
    return m
