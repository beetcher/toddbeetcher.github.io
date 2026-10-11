#!/usr/bin/env python3
"""In-memory tests for the individual services and their endpoint wiring.
Run from enjoy_router/:  python3 run_individual_endpoint_tests.py   (add -v to list every check)
Covers: sealed and confidential privacy, the soft-delete guard, the audit log, the test door and the Console door
(the Console door must not reach restricted details yet), and the get_for_individual op. Nothing touches Firebase."""
import json
import logging
import pathlib
import sys
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import individual_restricted_details_service as RS  # noqa: E402
from crud import individuals_service as S  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud_endpoint import handle_admin, handle_crud_test, make_failure_limiter  # noqa: E402

KEY = "k" * 16 + "Z" * 16 + "-test-key-not-real"
NOW = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
fails: list = []
total = 0


def check(label, ok, detail=""):
    global total
    total += 1
    if not ok:
        fails.append(label)
    if not ok or "-v" in sys.argv:
        print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")


def pairs(problems):
    return sorted(f"{p['field']}:{p['issue']}" for p in problems)


# ---------------------------------------------------------------------------
# 1. Service rules (in process)
# ---------------------------------------------------------------------------
s = MemoryDocStore("test_")
mk = lambda body: S.create(s, body, "user:todd", now=NOW).data
open_p = mk({"given_name": "Open"})
conf = mk({"given_name": "Conf", "record_privacy": "confidential"})
seal = mk({"given_name": "Seal", "record_privacy": "sealed"})

check("normal get ok", S.get(s, open_p["id"]).ok)
check("confidential get ok", S.get(s, conf["id"]).ok)
check("sealed get hidden as not_found", S.get(s, seal["id"]).code == "not_found")
check("sealed get visible to admin", S.get(s, seal["id"], as_admin=True).ok)
names = lambda r: sorted(x["given_name"] for x in r.data["records"])
check("list hides sealed and confidential", names(S.list(s)) == ["Open"])
check("list count matches", S.list(s).data["count"] == 1)
check("admin list shows all", names(S.list(s, as_admin=True)) == ["Conf", "Open", "Seal"])
check("list problems still reported", not S.list(s, {"status": "gone"}).ok)
check("sealed update hidden", S.update(s, seal["id"], {"notes": "x"}, "user:a", now=NOW).code == "not_found")
check("sealed update ok for admin", S.update(s, seal["id"], {"notes": "x"}, "user:a", now=NOW, as_admin=True).ok)
check("sealed soft_delete hidden", S.soft_delete(s, seal["id"], "user:a", now=NOW).code == "not_found")
check("update of normal record ok", S.update(s, open_p["id"], {"notes": "y"}, "user:a", now=NOW).ok)
check("bad id passes through to handler problems", pairs(S.update(s, "nope", {"notes": "y"}, "user:a").problems) == ["id:invalid_format"])

# soft-delete guard
adult = mk({"given_name": "Adult", "birth_date": "1961-04-17"})
rd = RS.create(s, {"individual_id": adult["id"], "purpose": "safety", "consent_ref": "c1", "blood_type_abo": "O"}, "user:todd", now=NOW)
check("restricted create via service ok", rd.ok, str(rd))
r = S.soft_delete(s, adult["id"], "user:a", now=NOW)
check("cannot soft-delete while restricted record is live", (not r.ok) and r.code == "conflict" and pairs(r.problems) == ["id:in_use"], str(r))
RS.soft_delete(s, rd.data["id"], "user:todd", now=NOW)
check("soft-delete allowed once the restricted record is gone", S.soft_delete(s, adult["id"], "user:a", now=NOW).ok)
check("soft-delete of a plain person ok", S.soft_delete(s, open_p["id"], "user:a", now=NOW).ok)

# audit log: ids and codes only, never values or field names
class Grab(logging.Handler):
    def __init__(self):
        super().__init__(); self.lines = []
    def emit(self, record):
        self.lines.append(record.getMessage())

grab = Grab()
lg = logging.getLogger("enjoy_router"); lg.addHandler(grab); lg.setLevel(logging.INFO)
s3 = MemoryDocStore("test_")
p3 = S.create(s3, {"given_name": "Zelda", "birth_date": "1961-04-17"}, "user:todd", now=NOW).data
r = RS.create(s3, {"individual_id": p3["id"], "purpose": "safety", "consent_ref": "SECRET-CONSENT", "blood_type_abo": "AB"}, "user:todd", now=NOW)
RS.get(s3, r.data["id"]); RS.get_for_individual(s3, p3["id"]); RS.list(s3); RS.update(s3, r.data["id"], {"blood_type_abo": "A"}, "user:a", now=NOW)
RS.get(s3, "3f2b8c1e-7a4d-4e5f-9b6a-1c2d3e4f5a6b")
text = "\n".join(grab.lines)
check("audit: every op logged", all(f"op={o} " in text for o in ("create", "get", "get_for_individual", "list", "update")), text)
check("audit: ids present", r.data["id"] in text)
check("audit: failed read logs its code", "code=not_found" in text)
check("audit: no values leaked", all(v not in text for v in ("SECRET-CONSENT", "AB", "Zelda", "blood_type", "1961")), text)
lg.removeHandler(grab)

# ---------------------------------------------------------------------------
# 2. Endpoint wiring
# ---------------------------------------------------------------------------
store = MemoryDocStore("test_")
limiter = make_failure_limiter()


def door(fn, body):
    return fn("POST", f"Bearer {KEY}", json.dumps(body).encode(), KEY, "v", store, limiter, NOW)


test_door = lambda coll, op, **a: door(handle_crud_test, {"collection": coll, "op": op, "args": a})
admin_door = lambda coll, op, **a: door(handle_admin, {"collection": coll, "op": op, "args": a})

r = test_door("individuals", "create", data={"given_name": "Maria", "family_name": "Garcia", "birth_date": "1961-04-17"})
check("test door: create individual", r.status == 200 and r.body["data"]["display_name"] == "Maria Garcia" and r.body["data"]["created_by"] == "system:crud_test", str(r.body))
pid = r.body["data"]["id"]
check("test door: stored under test_ prefix only", sorted(store.data) == ["test_individuals"], str(list(store.data)))
check("test door: get", test_door("individuals", "get", id=pid).body["data"]["id"] == pid)
r = test_door("individuals", "update", id=pid, changes={"family_name": "Lopez"})
check("test door: update", r.status == 200 and r.body["data"]["changed"] == ["family_name"])
check("test door: update wrote history under test_ prefix", len(store.data.get("test_individual_history", {})) == 1)
r = test_door("individuals", "list", filters={"status": "active"})
check("test door: list", r.status == 200 and r.body["data"]["count"] == 1)
r = test_door("individuals", "create", data={"given_name": "X", "status": "merged"})
check("test door: refused create is 400 with problems", r.status == 400 and r.body["error"]["problems"] == [{"field": "status", "issue": "invalid_value"}])

r = test_door("individual_restricted_details", "create", data={"individual_id": pid, "purpose": "safety", "consent_ref": "c1", "blood_type_abo": "O"})
check("test door: restricted create", r.status == 200 and r.body["data"]["individual_id"] == pid, str(r.body))
check("test door: restricted under test_ prefix only", sorted(store.data) == ["test_individual_history", "test_individual_restricted_details", "test_individuals"], str(sorted(store.data)))
r = test_door("individual_restricted_details", "get_for_individual", individual_id=pid)
check("test door: get_for_individual", r.status == 200 and r.body["data"]["blood_type_abo"] == "O")
r = test_door("individual_restricted_details", "create", data={"individual_id": pid, "purpose": "billing", "consent_ref": "c1", "notes": "n"})
check("test door: second record refused", r.status == 400 and r.body["error"]["problems"] == [{"field": "individual_id", "issue": "duplicate"}])
r = test_door("individuals", "soft_delete", id=pid)
check("test door: in_use delete is 409", r.status == 409 and r.body["error"]["problems"] == [{"field": "id", "issue": "in_use"}], str(r.body))
check("get_for_individual not supported on other collections", test_door("individuals", "get_for_individual", individual_id=pid).status == 400)
check("get_for_individual needs its arg", test_door("individual_restricted_details", "get_for_individual").status == 400)

# the Console door
before = json.dumps(store.data, sort_keys=True)
for op, args in (("get", {"id": pid}), ("list", {}), ("get_for_individual", {"individual_id": pid}),
                 ("create", {"data": {"individual_id": pid, "purpose": "safety", "consent_ref": "c", "blood_type_abo": "A"}}),
                 ("update", {"id": pid, "changes": {"notes": "x"}}), ("soft_delete", {"id": pid})):
    r = admin_door("individual_restricted_details", op, **args)
    check(f"Console door cannot reach restricted details: {op}", r.status == 400 and "not enabled" in r.body["error"]["message"], str(r.body))
check("Console door left the store untouched", json.dumps(store.data, sort_keys=True) == before)
r = admin_door("individuals", "get", id=pid)
check("Console door reaches individuals", r.status == 200 and r.body["data"]["id"] == pid and r.body["data"]["created_by"] == "system:crud_test")
r = admin_door("individuals", "create", data={"given_name": "Via Console"})
check("Console door: create stamps user:admin", r.status == 200 and r.body["data"]["created_by"] == "user:admin")
sealed = test_door("individuals", "create", data={"given_name": "Sealed", "record_privacy": "sealed"}).body["data"]["id"]
check("endpoint hides sealed records (no roles yet)", admin_door("individuals", "get", id=sealed).status == 404)
check("endpoint list hides sealed", "Sealed" not in [x["given_name"] for x in admin_door("individuals", "list").body["data"]["records"]])
check("unknown collection still refused", admin_door("people", "get", id=pid).status == 400)

print(f"\n{total - len(fails)}/{total} checks passed")
if fails:
    print("FAILED:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("OK")
