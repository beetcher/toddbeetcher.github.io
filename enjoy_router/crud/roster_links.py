"""The two rosters' names, shared by the merge and erase code without importing the roster service
(which imports the individuals service, which would loop). The roster is a pointer to an individual:
merging repoints it, erasing scrubs it."""
from __future__ import annotations

from .schema_kit import load_collection, stamp_update

ROSTER_TYPES = ("instructor_roster", "student_roster", "attendance")  # attendance rides along: same pointer, same scrub
ROSTERS = tuple(load_collection(t) for t in ROSTER_TYPES)
KEEP = frozenset({"id", "schema_version", "created_at", "created_by", "updated_at", "updated_by", "source", "status",
                  "deleted_at", "deleted_by"})


def scrub_for_individual(store, individual_id, actor, tx, now=None):
    """Erase of a person: every roster entry of theirs (live or removed) is soft deleted and everything that
    describes it is removed, leaving an anonymous tombstone. Writes join `tx`. Returns {"roster_entries_scrubbed": n}."""
    n = 0
    for coll in ROSTERS:
        for d in store.query(coll.name, [("individual_id", "==", individual_id)], limit=50):
            stamp = stamp_update(actor, now)
            fields = dict(stamp)
            fields.setdefault("deleted_at", d.get("deleted_at") or stamp["updated_at"])
            fields["deleted_at"] = d.get("deleted_at") or stamp["updated_at"]
            fields["deleted_by"] = d.get("deleted_by") or actor
            removals = sorted(k for k in d if k not in KEEP)
            store.update(coll.name, d["id"], fields, removals, tx=tx)
            n += 1
    return {"roster_entries_scrubbed": n}
