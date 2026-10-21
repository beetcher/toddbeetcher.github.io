"""Territory: which ZIPs a person's grants cover (P-60 / P-65, decided by Todd 2026-10-20).

    t = Territory(store)                      # store: the one that holds `discovery_areas` (states and regions)
    t.covers(grant, "80301")                  # does one grant cover a ZIP?
    scope = Scope(access, t)
    scope.has("edit_venues", "80301")         # may this person do that here?  (super admin: always)
    scope.sees("80301")                       # does any grant cover the ZIP? (looking only)

Rules (see schemas/ACCESS_PERSON_GUIDE.md section 2a):
  * A ZIP is never owned on its own. A ZIP belongs to the regions whose `zip_codes` list it; a region has one state. Regions may share ZIPs.
  * kind `all` covers everything, including a record with no ZIP.
  * kind `state` covers every ZIP in the state, including ZIPs no region has claimed (the state of a ZIP comes from the ZIP table, else from
    a region that lists it).
  * kind `regions` covers a ZIP listed by any of its regions.
  * A record with no ZIP, or a ZIP nobody can place, is covered only by `all`.
  * Territorial capabilities are held per grant. Global capabilities (access.capabilities.GLOBAL) come from the role. Holding any grant that
    covers a place lets a person LOOK at it; doing something needs the capability in a covering grant.
"""
from __future__ import annotations

import re

from launch_discovery import zip_table

from .capabilities import GLOBAL, TERRITORIAL

_ZIP = re.compile(r"\s*(\d{5})(?:\D|$)")


def norm_zip(value):
    """The five-digit ZIP at the start of `value` (a ZIP+4 is trimmed), or None."""
    if not isinstance(value, str):
        return None
    m = _ZIP.match(value)
    return m.group(1) if m else None


class Territory:
    """The states and regions, read once for one request."""

    def __init__(self, store):
        self._store = store
        self._loaded = False
        self.states, self.regions, self._by_zip = {}, {}, {}

    def _load(self):
        if self._loaded:
            return
        self._loaded = True
        for a in self._store.query("discovery_areas", [], limit=1000):
            if "deleted_at" in a:
                continue
            if a.get("kind") == "state":
                self.states[a.get("state_code")] = a
            elif a.get("kind") == "region":
                self.regions[a["id"]] = a
                for z in a.get("zip_codes", []):
                    self._by_zip.setdefault(z, set()).add(a["id"])

    def regions_of_zip(self, zip_code):
        self._load()
        return frozenset(self._by_zip.get(zip_code, ()))

    def state_of_zip(self, zip_code):
        """The state a ZIP is in: the ZIP table first, else the state of a region that lists it, else None."""
        self._load()
        st = zip_table.state_of(zip_code) if zip_table.is_loaded() else None
        if st:
            return st
        for rid in self._by_zip.get(zip_code, ()):
            return self.regions[rid].get("state_code")
        return None

    def state_of_region(self, region_id):
        self._load()
        r = self.regions.get(region_id)
        return r.get("state_code") if r else None

    def covers_region(self, grant, region_id):
        """Does one grant cover a whole region (a record that belongs to a region by id, not by ZIP)? `all` covers any; a state grant covers
        every region of its state; a regions grant covers the regions it lists."""
        kind = grant.get("kind")
        if kind == "all":
            return True
        if kind == "state":
            return self.state_of_region(region_id) == grant.get("state_code")
        if kind == "regions":
            return region_id in grant.get("region_ids", ())
        return False

    def covers(self, grant, zip_code):
        kind = grant.get("kind")
        if kind == "all":
            return True
        z = norm_zip(zip_code)
        if z is None:
            return False
        if kind == "state":
            return self.state_of_zip(z) == grant.get("state_code")
        if kind == "regions":
            return bool(self.regions_of_zip(z) & set(grant.get("region_ids", ())))
        return False


class Scope:
    """One person's reach for one request: their grants, read against the territory."""

    def __init__(self, access, territory):
        self.access, self.territory = access, territory

    @property
    def unlimited(self):
        return bool(self.access.ok and (self.access.is_super_admin or any(g.get("kind") == "all" for g in self.access.grants)))

    def sees(self, zip_code):
        if not self.access.ok:
            return False
        if self.access.is_super_admin:
            return True
        return any(self.territory.covers(g, zip_code) for g in self.access.grants)

    def has(self, capability, zip_code):
        """May this person use `capability` on a record in this ZIP (None = the record has no place)?"""
        a = self.access
        if not a.ok:
            return False
        if a.is_super_admin:
            return True
        if capability in GLOBAL:
            return a.can(capability)
        if capability not in TERRITORIAL:
            return False
        return any(capability in g.get("capabilities", ()) and self.territory.covers(g, zip_code) for g in a.grants)

    def has_in_region(self, capability, region_id):
        """May this person use `capability` on a record that belongs to this region (by id)?"""
        a = self.access
        if not a.ok:
            return False
        if a.is_super_admin:
            return True
        if capability in GLOBAL:
            return a.can(capability)
        if capability not in TERRITORIAL:
            return False
        return any(capability in g.get("capabilities", ()) and self.territory.covers_region(g, region_id) for g in a.grants)

    def satisfies_region(self, need, region_id):
        return all(any(self.has_in_region(c, region_id) for c in group) for group in need)

    def sees_region(self, region_id):
        if not self.access.ok:
            return False
        return self.access.is_super_admin or any(self.territory.covers_region(g, region_id) for g in self.access.grants)

    def teaches(self, store, class_id):
        """Is this person attached to this class as an instructor (an attendance record, role instructor, for the person their sign-in is
        linked to)? Looking only; it never lets them change anything."""
        pid = self.access.individual_id if self.access.ok else ""
        if not pid or not class_id:
            return False
        if not hasattr(self, "_taught"):
            self._taught = {a.get("scheduled_class_id") for a in store.query("attendances", [("individual_id", "==", pid)], limit=1000)
                            if a.get("role") == "instructor" and "deleted_at" not in a}
        return class_id in self._taught

    def can_read(self, need, zip_code):
        """Reading a record in this ZIP: the collection's read need is met here AND a grant covers the place."""
        return self.satisfies(need, zip_code) and self.sees(zip_code)

    def satisfies(self, need, zip_code):
        """`need` in the policy.py shape (all groups, any capability in a group), evaluated at one ZIP."""
        return all(any(self.has(c, zip_code) for c in group) for group in need)

    # ---- areas (the states and regions themselves) -------------------------------------------------------------------------------
    def area_has(self, capability, area):
        """May this person use `capability` on this state or region record? A state grant reaches every region of its state; a regions
        grant reaches the regions it lists. A state record itself is reached only through a state grant (or all)."""
        a = self.access
        if not a.ok:
            return False
        if self.unlimited:
            return True
        if capability in GLOBAL:
            return a.can(capability)
        if capability not in TERRITORIAL or not isinstance(area, dict):
            return False
        for g in a.grants:
            if capability not in g.get("capabilities", ()):
                continue
            if g.get("kind") == "state" and g.get("state_code") == area.get("state_code"):
                return True
            if g.get("kind") == "regions" and area.get("kind") == "region" and area.get("id") in g.get("region_ids", ()):
                return True
        return False

    def area_sees(self, area):
        """Looking at a state or region record: any grant in the state, or a grant for that very region."""
        if self.unlimited:
            return True
        if not self.access.ok or not isinstance(area, dict):
            return False
        for g in self.access.grants:
            if g.get("kind") == "state" and g.get("state_code") == area.get("state_code"):
                return True
            if g.get("kind") == "regions":
                if area.get("kind") == "state" and g.get("state_code") == area.get("state_code"):
                    return True
                if area.get("kind") == "region" and area.get("id") in g.get("region_ids", ()):
                    return True
        return False
