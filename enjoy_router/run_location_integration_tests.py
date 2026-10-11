#!/usr/bin/env python3
"""In-memory tests for locations meeting individuals: merge re-points residence links, unmerge puts them back,
erase scrubs a person's links and any location nobody else is linked to.
Run from enjoy_router/:  python3 run_location_integration_tests.py   (add -v to list every check)."""
import pathlib
import sys
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import individual_merges_crud as M  # noqa: E402
from crud import individuals_crud as I  # noqa: E402
from crud import individuals_service as IS  # noqa: E402
from crud import location_links_crud as H  # noqa: E402
from crud import location_links_service as S  # noqa: E402
from crud import locations_crud as L  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402

START = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)
fails: list = []
total = 0
clock = [0]
ACT = "user:todd"


def tick():
    clock[0] += 5
    return START + timedelta(seconds=clock[0])


def check(label, ok, detail=""):
    global total
    total += 1
    if not ok:
        fails.append(label)
    if not ok or "-v" in sys.argv:
        print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")


s = MemoryDocStore("test_")


def person(n):
    return I.create(s, {"given_name": n}, ACT, now=tick()).data


def place(n, **kw):
    return L.create(s, {"name": n, **kw}, ACT, now=tick()).data


def link(p, loc, rel="resides_at", **kw):
    r = S.create(s, {"subject_type": "individual", "subject_id": p["id"], "location_id": loc["id"], "relationship": rel, **kw}, ACT, now=tick())
    assert r.ok, r
    return r.data


def raw(b, i):
    return s.get(b, i)


# ---- merge
keep, dup = person("Keep"), person("Dup")
h1, h2 = place("H1"), place("H2")
a = link(keep, h1, valid_from="2020")
b = link(dup, h2, valid_from="2018", valid_to="2019-12-31")
c = link(dup, h1, "mailing_address_for")
r = IS.merge(s, keep["id"], dup["id"], "same person", ACT, now=tick())
check("merge succeeds", r.ok, str(r))
mid = r.data["id"] if r.ok else None
check("merge re-points the duplicate's links to the survivor", raw("location_links", b["id"])["subject_id"] == keep["id"] and raw("location_links", c["id"])["subject_id"] == keep["id"])
check("merge leaves the survivor's own link alone", raw("location_links", a["id"])["subject_id"] == keep["id"])
check("the event lists the moved links", sum(1 for m in raw("merge_events", mid)["moved_links"] if m["collection"] == "location_links") == 2)
check("the survivor now has three links", len(H.live_for(s, "subject_id", keep["id"])) == 3 and not H.live_for(s, "subject_id", dup["id"]))
check("residential flags unchanged by the merge", raw("locations", h1["id"])["is_residential"] is True and raw("locations", h2["id"])["is_residential"] is False)
r = IS.unmerge(s, mid, ACT, now=tick())
check("unmerge succeeds", r.ok, str(r))
check("unmerge puts the links back", raw("location_links", b["id"])["subject_id"] == dup["id"] and raw("location_links", c["id"])["subject_id"] == dup["id"] and raw("location_links", a["id"])["subject_id"] == keep["id"])

# unmerge skips a link whose subject changed since (only equals-what-the-merge-wrote is restored)
k2, d2 = person("K2"), person("D2")
x = link(d2, h2, "owns")
m2 = IS.merge(s, k2["id"], d2["id"], "same", ACT, now=tick()).data["id"]
third = person("Third")
s.update("location_links", x["id"], {"subject_id": third["id"]}, ())
r = IS.unmerge(s, m2, ACT, now=tick())
check("unmerge leaves a link that was changed since", r.ok and raw("location_links", x["id"])["subject_id"] == third["id"], str(r))

# a venue link is never touched by a merge, whatever the ids
k3, d3 = person("K3"), person("D3")
vlink = H.create(s, {"subject_type": "venue", "subject_id": d3["id"], "location_id": h1["id"], "relationship": "operates_at"}, ACT, now=tick()).data
IS.merge(s, k3["id"], d3["id"], "same", ACT, now=tick())
check("a non-individual link with a matching id is not re-pointed", raw("location_links", vlink["id"])["subject_id"] == d3["id"])

# ---- erase through the individual service
e = person("Erase")
home = place("Erase home", addresses=[{"usage": "civic", "street": "5 Pine St", "country": "US"}])
other = person("Other")
shared = place("Shared")
link(e, home)
link(e, shared)
link(other, shared)
r = IS.erase(s, e["id"], ACT, now=tick())
check("erase succeeds and reports what it scrubbed", r.ok and r.data["links_scrubbed"] == 2 and r.data["locations_scrubbed"] == 1, str(r))
check("the person is a tombstone", raw("individuals", e["id"])["status"] == "erased")
check("the sole home is retired and scrubbed", raw("locations", home["id"])["status"] == "retired" and "addresses" not in raw("locations", home["id"]) and "name" not in raw("locations", home["id"]))
check("the shared home keeps its details and its other resident", raw("locations", shared["id"]).get("name") == "Shared" and raw("locations", shared["id"])["is_residential"] is True)
check("no live link of the erased person remains", not [x for x in H.live_for(s, "subject_id", e["id"])])
check("the other resident's link is intact", len(H.live_for(s, "subject_id", other["id"])) == 1)
check("erasing twice is still a conflict", IS.erase(s, e["id"], ACT).code == "conflict")
check("a refused erase scrubs nothing", IS.erase(s, "3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b", ACT).code == "not_found")
sealed = I.create(s, {"given_name": "Sealed", "record_privacy": "sealed"}, ACT, now=tick()).data
sl = place("Sealed home")
S.create(s, {"subject_type": "individual", "subject_id": sealed["id"], "location_id": sl["id"], "relationship": "resides_at"}, ACT, now=tick(), as_admin=True)
check("a non-admin cannot erase a sealed person, and nothing is scrubbed", IS.erase(s, sealed["id"], ACT, now=tick()).code == "not_found" and raw("locations", sl["id"]).get("name") == "Sealed home")

print(f"\n{total - len(fails)}/{total} checks passed")
if fails:
    print("FAILED:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("OK")
