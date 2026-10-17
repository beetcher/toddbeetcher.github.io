"""Saves Discovery's venue candidates as INACTIVE venues, with their place and operator, through the existing venue, location and
organization services. Nobody is contacted, and nothing is activated (D-6).

Duplicate rule (D-7): a venue is a duplicate of a saved one when it has the same place, the same normalized name and the same operating
organization. "Same place": the same street address (location address match); with no street address, the same city. A duplicate is
skipped and the saved record is never changed. Same name and place but a different operator is a different venue and shares the place.

The operator organization is found by normalized name (name, short name, legal name or alias); when it does not exist it is created
and the venue is flagged `operator_unconfirmed`. A candidate with no street address is kept with a city-only place and flagged
`no_street_address`. GPS is NOT looked up here (the existing "find GPS" action does that after a person activates the venue).

Everything the sink creates is made by the actor `system:discovery`. A record counts as untouched, and Withdraw may take it back, only
while its updated_by is still that actor (a person who activates or edits it changes the actor) and nothing else depends on it (D-13).
"""
from __future__ import annotations

import re

from crud import location_links_crud as LK
from crud import locations_crud as LOC
from crud import organization_links_crud as OLC
from crud import organization_links_service as OLS
from crud import organizations_crud as ORG
from crud import venues_crud as VC
from crud import venues_service as VS
from discovery.contract import SinkResult, WithdrawResult

from .venue_finder import norm

ACTOR = "system:discovery"
SCAN = 2000
HOURS_PREFIX = "Public hours per the web (check before relying on them): "
VENUE_FIELDS = ("name", "description", "website_url", "phone", "email", "has_wifi", "is_accessible", "allows_minors", "notes")
_NUMBER = re.compile(r"^(\d+[A-Za-z]?)\s+(.+)$")
_SLUG = re.compile(r"[^a-z0-9]+")


def _live(doc) -> bool:
    return doc is not None and "deleted_at" not in doc


def _slug_base(name, city) -> str:
    s = _SLUG.sub("_", f"{name} {city}".lower()).strip("_")
    return (s[:70].strip("_") or "venue")


class VenueSink:
    def __init__(self, store):
        self.store = store
        self._orgs = None            # normalized name -> org id
        self._venues = None          # normalized venue name -> [venue ids]

    # ------------------------------------------------------------------ lookups
    def _org_index(self):
        if self._orgs is None:
            self._orgs = {}
            for o in self.store.query(ORG.ORGANIZATIONS.name, [], limit=SCAN):
                if not _live(o) or o.get("status") == "merged":
                    continue
                for n in [o.get("name"), o.get("short_name"), o.get("legal_name"), *(o.get("aliases") or [])]:
                    if n:
                        self._orgs.setdefault(norm(n), o["id"])
        return self._orgs

    def _venue_index(self):
        if self._venues is None:
            self._venues = {}
            for v in self.store.query(VC.VENUES.name, [], limit=SCAN):
                if _live(v):
                    self._venues.setdefault(norm(v["name"]), []).append(v["id"])
        return self._venues

    def _links(self, coll, field, value):
        return [d for d in self.store.query(coll, [(field, "==", value)], limit=200) if _live(d)]

    def _venue_places(self, venue_id):
        out = []
        for l in self._links(LK.LINKS.name, "subject_id", venue_id):
            if l.get("subject_type") == "venue" and l.get("relationship") == "operates_at" and LK.is_live(l):
                loc = self.store.get(LOC.LOCATIONS.name, l["location_id"])
                if _live(loc):
                    out.append(loc)
        return out

    def _operated_by(self, venue_id, org_id) -> bool:
        return any(l.get("subject_type") == "venue" and l.get("relationship") == "operated_by" and l.get("organization_id") == org_id
                   for l in self._links(OLC.LINKS.name, "subject_id", venue_id))

    def _duplicate_of(self, v, org_id, address, matches):
        """The id of a saved venue this candidate duplicates, or None."""
        if org_id is None:
            return None
        match_ids = {m["id"] for m in matches}
        for vid in self._venue_index().get(norm(v["name"]), []):
            if not self._operated_by(vid, org_id):
                continue
            places = self._venue_places(vid)
            if address and address.get("street"):
                if any(p["id"] in match_ids for p in places):
                    return vid
            elif not places or any(norm(a.get("locality", "")) == norm(v["city"]) for p in places for a in p.get("addresses", [])):
                return vid
        return None

    # ------------------------------------------------------------------ save
    def _address(self, v):
        addr = {"usage": "civic", "is_primary": True, "locality": v["city"], "region": v["state"], "country": "US"}
        if v.get("postal_code"):
            addr["postal_code"] = v["postal_code"]
        if v.get("street"):
            m = _NUMBER.match(v["street"])
            addr.update({"street_number": m.group(1), "street": m.group(2)} if m else {"street": v["street"]})
        else:
            addr["lines"] = [f"{v['city']}, {v['state']}"]      # the place schema wants lines, a street or a PO box
            addr["verification"] = "none"
        return addr

    def save(self, candidate, ctx) -> SinkResult:
        ids: dict = {}
        try:
            return self._save(candidate, ctx, ids)
        except Exception:
            return SinkResult("rejected", reason="internal_error", ids=ids)

    def _save(self, candidate, ctx, ids) -> SinkResult:
        v, st, now = candidate.values(), self.store, ctx.now
        address = self._address(v)
        has_street = bool(v.get("street"))
        org_id = self._org_index().get(norm(v["operator"]))
        matches = LOC.find_by_address(st, address).data["records"] if has_street else []
        dup = self._duplicate_of(v, org_id, address, matches)
        if dup:
            return SinkResult("duplicate", reason="same_venue")
        reasons = []
        if org_id is None:
            o = ORG.create(st, {"name": v["operator"], "notes": f"Created by Discovery run {ctx.run_id}. Check the name and what kind of organization it is."},
                           ACTOR, "import", now=now)
            if not o.ok:
                return SinkResult("rejected", reason="operator_refused", ids=ids)
            org_id = o.data["id"]
            self._org_index()[norm(v["operator"])] = org_id
            ids.setdefault("organization", []).append(org_id)
            reasons.append("operator_unconfirmed")
        data = {k: v[k] for k in VENUE_FIELDS if k in v}
        if v.get("public_hours"):                      # opening hours are NOT class availability: kept as text for a person to read
            data["availability_notes"] = (HOURS_PREFIX + v["public_hours"])[:1000]
        data.update({"status": "inactive", "is_public_venue": True})
        base, n, res = _slug_base(v["name"], v["city"]), 1, None
        while n <= 6:
            data["slug"] = base if n == 1 else f"{base}_{n}"
            if matches:
                res = VS.create_with_place(st, data, ACTOR, location_id=matches[0]["id"], source="import", now=now)
            else:
                res = VS.create_with_place(st, data, ACTOR, address=address, source="import", now=now)
            if res.ok or not any(p["field"] == "slug" and p["issue"] == "duplicate" for p in (res.problems or [])):
                break
            n += 1
        if not res.ok:
            return SinkResult("rejected", reason="venue_refused", ids=ids)
        d = res.data
        vid = d["id"]
        ids.setdefault("venue", []).append(vid)
        self._venue_index().setdefault(norm(v["name"]), []).append(vid)
        place = d.get("place") or {}
        if d.get("created_place") and place.get("location_id"):
            ids.setdefault("location", []).append(place["location_id"])
        if place.get("link_id"):
            ids.setdefault("location_link", []).append(place["link_id"])
        link = OLS.create(st, {"subject_type": "venue", "subject_id": vid, "organization_id": org_id, "relationship": "operated_by"},
                          ACTOR, "import", now=now, as_admin=True)
        if link.ok:
            ids.setdefault("organization_link", []).append(link.data["id"])
        elif "operator_unconfirmed" not in reasons:
            reasons.append("operator_unconfirmed")
        block = dict(candidate.block)
        merged = list(dict.fromkeys([*block.get("attention_reasons", []), *reasons]))
        if merged:
            block["needs_attention"], block["attention_reasons"] = True, merged
        VC.set_discovery(st, vid, block, ACTOR, now=now)
        return SinkResult("saved", record_status="inactive", ids=ids, attention_reasons=tuple(reasons))

    # ------------------------------------------------------------------ withdraw
    def _untouched(self, doc, active_status=None) -> bool:
        return _live(doc) and doc.get("updated_by") == ACTOR and (active_status is None or doc.get("status") == active_status)

    def withdraw(self, run, by, now) -> WithdrawResult:
        st, removed, kept = self.store, {}, []

        def drop(kind, fn, rid):
            r = fn(st, rid, ACTOR, now=now)
            if r.ok:
                removed[kind] = removed.get(kind, 0) + 1
            else:
                kept.append(rid)
        venues = [st.get(VC.VENUES.name, i) for i in run.get("created_venue_ids", [])]
        keep_v = {d["id"] for d in venues if _live(d) and not (self._untouched(d, "inactive") and not self._used(d["id"]))}
        for lid in run.get("created_location_link_ids", []):
            d = st.get(LK.LINKS.name, lid)
            if _live(d):
                kept.append(lid) if d.get("subject_id") in keep_v else drop("location_link", _link_delete(LK), lid)
        for lid in run.get("created_organization_link_ids", []):
            d = st.get(OLC.LINKS.name, lid)
            if _live(d):
                kept.append(lid) if d.get("subject_id") in keep_v else drop("organization_link", _link_delete(OLC), lid)
        for d in venues:
            if _live(d):
                kept.append(d["id"]) if d["id"] in keep_v else drop("venue", VS.soft_delete, d["id"])
        for pid in run.get("created_location_ids", []):
            d = st.get(LOC.LOCATIONS.name, pid)
            if not _live(d):
                continue
            if not self._untouched(d) or self._links(LK.LINKS.name, "location_id", pid):
                kept.append(pid)
            else:
                drop("location", LOC.soft_delete, pid)
        for oid in run.get("created_organization_ids", []):
            d = st.get(ORG.ORGANIZATIONS.name, oid)
            if not _live(d):
                continue
            if not self._untouched(d) or self._links(OLC.LINKS.name, "organization_id", oid):
                kept.append(oid)
            else:
                drop("organization", ORG.soft_delete, oid)
        return WithdrawResult(removed, kept)

    def _used(self, venue_id) -> bool:
        from crud.classes_service import live_classes_at
        return bool(live_classes_at(self.store, venue_id, limit=1))


def _link_delete(mod):
    return lambda st, rid, actor, now=None: mod.soft_delete(st, rid, actor, now=now)
