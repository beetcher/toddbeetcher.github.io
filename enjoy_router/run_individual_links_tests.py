#!/usr/bin/env python3
"""In-memory tests for the individual links on LAUNCH records: assignment participants (service rules).
Run from enjoy_router/:  python3 run_individual_links_tests.py   (add -v to list every check). Nothing touches Firebase."""
import copy
import pathlib
import sys
import uuid
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import assignments_service as S  # noqa: E402
from crud import classes_service as CS  # noqa: E402
from crud import individuals_crud as I  # noqa: E402
from crud import venues_crud as V  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402

START = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
fails: list = []
total = 0
clock = [0]


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


def pairs(problems):
    return sorted(f"{p['field']}:{p['issue']}" for p in problems)


VENUE = {"name": "Library", "slug": "library", "status": "active", "is_public_venue": True,
         "email": "pat@example.com", "contact_individual_id": "5b1f0c2e-7a4d-4c3b-9e6f-1a2b3c4d5e6f",
         "is_accessible": True, "allows_minors": True, "allows_animals": False,
         "rooms": [{"label": "Main room", "max_occupancy": 40}]}

s = MemoryDocStore("test_")
venue = V.create(s, copy.deepcopy(VENUE), "user:t", now=tick()).data
cls = CS.create(s, {"title": "Class", "slug": "class_1", "class_type": "workshop", "program_slug": "launch", "status": "enrolling",
                    "is_public": True, "capacity_minimum": 2, "capacity_target": 6, "capacity_max": 8,
                    "starts_at": "2026-11-21T01:00:00Z", "time_zone": "America/Denver", "duration_minutes": 120,
                    "venue_id": venue["id"], "is_venue_confirmed": True, "price_cents": 5000, "price_basis": "per_person",
                    "is_waitlist_enabled": False}, "user:t", now=tick()).data


def request(seats=2):
    rid = str(uuid.uuid4())
    s.data.setdefault("test_registration_requests", {})[rid] = {
        "id": rid, "registration_type": "class", "attendee_count": seats, "confirmation_number": "ICDT-000001",
        "first_name": "Ann", "last_name": "Tester", "email": "a@example.com", "created_at": "2026-10-10T12:00:00Z",
        "processing_status": "not_processed"}
    return s.data["test_registration_requests"][rid]


person = lambda name, **kw: I.create(s, {"given_name": name, **kw}, "user:todd", now=tick()).data
assign = lambda req, **extra: S.create(s, {"request_id": req["id"], "scheduled_class_id": cls["id"], **extra}, "user:todd", now=tick())

a, b, c = person("Ann"), person("Bob"), person("Cy")

# create with participants
r = assign(request(2), participant_individual_ids=[a["id"], b["id"]])
check("create with two participants ok", r.ok, str(r.problems))
check("participants stored", r.data["participant_individual_ids"] == [a["id"], b["id"]])
check("no participants: unchanged behaviour", assign(request(2)).ok)
r = assign(request(2), participant_individual_ids=[str(uuid.uuid4())])
check("unknown participant refused", pairs(r.problems) == ["participant_individual_ids:not_found"], str(r))
req3 = request(2)
r = assign(req3, participant_individual_ids=[a["id"], b["id"], c["id"]])
check("more participants than seats refused", pairs(r.problems) == ["participant_individual_ids:out_of_range"], str(r))
check("refusals wrote no assignment for that request", not [d for d in s.data["test_registration_assignments"].values() if d["request_id"] == req3["id"]])
r = assign(request(2), participant_individual_ids=["nope"])
check("non-uuid id reported by the handler", (not r.ok) and "participant_individual_ids" in pairs(r.problems)[0], str(r))
r = assign(request(2), participant_individual_ids=[a["id"], a["id"]])
check("duplicate ids refused by the schema", not r.ok)

# deleted, erased, merged
gone = person("Gone")
I.soft_delete(s, gone["id"], "user:todd", now=tick())
check("deleted individual refused", pairs(assign(request(2), participant_individual_ids=[gone["id"]]).problems) == ["participant_individual_ids:not_found"])
erased = person("Erased")
s.update("individuals", erased["id"], {"status": "erased", "erased_at": "2026-10-10T12:00:00Z"})
check("erased individual refused", pairs(assign(request(2), participant_individual_ids=[erased["id"]]).problems) == ["participant_individual_ids:not_found"])
dup, keep = person("Dup"), person("Keep")
s.update("individuals", dup["id"], {"status": "merged", "merged_into_id": keep["id"]})
check("merged person is followed and accepted", assign(request(2), participant_individual_ids=[dup["id"]]).ok)
dangling = person("Dangling")
s.update("individuals", dangling["id"], {"status": "merged", "merged_into_id": str(uuid.uuid4())})
check("merged into nothing refused", not assign(request(2), participant_individual_ids=[dangling["id"]]).ok)

# update
req4 = request(2)
first = assign(req4).data
r = S.update(s, first["id"], {"participant_individual_ids": [c["id"]]}, "user:todd", now=tick())
check("update adds participants", r.ok and s.data["test_registration_assignments"][first["id"]]["participant_individual_ids"] == [c["id"]], str(r))
r = S.update(s, first["id"], {"participant_individual_ids": [str(uuid.uuid4())]}, "user:todd", now=tick())
check("update with unknown participant refused", pairs(r.problems) == ["participant_individual_ids:not_found"], str(r))
r = S.update(s, first["id"], {"participant_individual_ids": [a["id"], b["id"], c["id"]]}, "user:todd", now=tick())
check("update beyond seats refused", pairs(r.problems) == ["participant_individual_ids:out_of_range"], str(r))
r = S.update(s, first["id"], {"participant_individual_ids": None}, "user:todd", now=tick())
check("update removes participants", r.ok and "participant_individual_ids" not in s.data["test_registration_assignments"][first["id"]], str(r))
check("update of the decision still immutable", pairs(S.update(s, first["id"], {"status": "declined"}, "user:todd").problems) == ["status:immutable"])
check("update of other fields unaffected", S.update(s, first["id"], {"decision_note": "ok"}, "user:todd", now=tick()).ok)

print(f"\n{total - len(fails)}/{total} checks passed")
if fails:
    print("FAILED:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("OK")
