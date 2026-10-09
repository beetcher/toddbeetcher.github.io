#!/usr/bin/env python3
"""In-memory tests for the CRUD handler files (crud/). Run from enjoy_router/:  python3 run_crud_tests.py

Needs the `jsonschema` library. Reads schemas/examples/venue.examples.json and venue.handler_tests.json.
Nothing here touches Firebase."""
import copy
import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crud import venues_crud as V  # noqa: E402
from crud.memory_doc_store import MemoryDocStore  # noqa: E402
from crud.schema_kit import involved_fields, load_collection  # noqa: E402

EXAMPLES = json.loads((HERE.parent / "schemas" / "examples" / "venue.examples.json").read_text())
TESTS = json.loads((HERE.parent / "schemas" / "examples" / "venue.handler_tests.json").read_text())
START = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
fails: list = []
total = 0


def check(label, ok, detail=""):
    global total
    total += 1
    if not ok:
        fails.append(label)
    if not ok or "-v" in sys.argv:
        print(f"{'ok  ' if ok else 'FAIL'} {label} {detail if not ok else ''}")


def fresh():
    return MemoryDocStore("test_")


def example(spec):
    if isinstance(spec, dict) and "$example" in spec:
        body = copy.deepcopy(EXAMPLES["valid"][spec["$example"]])
        body.update(copy.deepcopy(spec.get("set", {})))
        for k in spec.get("unset", []):
            body.pop(k, None)
        return body
    return spec


def pairs(problems):
    return sorted(f"{p['field']}:{p['issue']}" for p in problems)


# ---------------------------------------------------------------------------
# 1. Every example in venue.examples.json, through create()
# ---------------------------------------------------------------------------
for name, body in EXAMPLES["valid"].items():
    r = V.create(fresh(), copy.deepcopy(body), "user:todd", now=START)
    check(f"valid example creates: {name}", r.ok, str(r.problems))
for name, body in EXAMPLES["invalid"].items():
    s = fresh()
    r = V.create(s, copy.deepcopy(body), "user:todd", now=START)
    check(f"invalid example refused: {name}", (not r.ok) and r.code == "validation_failed" and r.problems, str(r))
    check(f"invalid example stored nothing: {name}", not s.data.get("test_venues"))
    check(f"problems carry no values: {name}", all(set(p) == {"field", "issue"} for p in r.problems))


# ---------------------------------------------------------------------------
# 2. Scenarios from venue.handler_tests.json
# ---------------------------------------------------------------------------
def resolve(value, refs, store):
    if isinstance(value, str) and value.startswith("$") and value != "$absent":
        name, _, fld = value[1:].partition(".")
        vid = refs[name]
        return vid if not fld else store.data["test_venues"][vid].get(fld)
    if isinstance(value, dict):
        return {k: resolve(v, refs, store) for k, v in value.items()}
    return value


def dig(data, path):
    for part in path.split("."):
        data = data[int(part)] if isinstance(data, list) else data[part]
    return data


def run_step(step, store, refs, clock):
    op = step["op"]
    actor = step.get("actor", "user:todd")
    now = clock
    ident = resolve(step.get("id"), refs, store) if "id" in step else None
    before = len(store.reads)
    if op == "create":
        r = V.create(store, example(copy.deepcopy(step["data"])), actor, step.get("source", "dashboard"), now=now)
        if r.ok and "as" in step:
            refs[step["as"]] = r.data["id"]
    elif op == "get":
        r = V.get(store, ident, step.get("include_deleted", False))
    elif op == "list":
        kw = {k: step[k] for k in ("order", "limit") if k in step}
        r = V.list(store, step.get("filters"), **kw)
    elif op == "update":
        r = V.update(store, ident, copy.deepcopy(step["changes"]), actor,
                     expected_updated_at=resolve(step.get("expected_updated_at"), refs, store), now=now)
    elif op == "soft_delete":
        r = V.soft_delete(store, ident, actor, now=now)
    elif op == "set_review_summary":
        r = V.set_review_summary(store, ident, step["review_count"], step["average_rating"], now=now)
    else:
        raise SystemExit(f"unknown op {op}")
    return r, len(store.reads) - before, ident


for sc in TESTS["scenarios"]:
    store, refs = fresh(), {}
    for i, step in enumerate(sc["steps"], 1):
        label = f"{sc['name']} / step {i} ({step['op']})"
        r, reads, ident = run_step(step, store, refs, START + timedelta(seconds=i))
        ex = step["expect"]
        if "ok" in ex:
            check(label + ": ok", r.ok is ex["ok"], str(r))
        if "code" in ex:
            check(label + ": code", r.code == ex["code"], str(r))
        if "problems" in ex:
            check(label + ": problems", pairs(r.problems) == sorted(ex["problems"]), str(r.problems))
        if "problems_include" in ex:
            got = set(pairs(r.problems))
            check(label + ": problems include", set(ex["problems_include"]) <= got, str(sorted(got)))
        if "reads" in ex:
            check(label + ": reads", reads == ex["reads"], f"read {reads}")
        if "data" in ex:
            for path, want in ex["data"].items():
                try:
                    got = dig(r.data, path)
                except (KeyError, IndexError, TypeError):
                    got = "<missing>"
                check(label + f": data {path}", got == resolve(want, refs, store), f"{got!r}")
        if "stored" in ex:
            target = ident or (r.data or {}).get("id") or refs.get(step.get("as"))
            doc = store.data["test_venues"][target]
            for fld, want in ex["stored"].items():
                if isinstance(want, dict) and want.get("$absent"):
                    check(label + f": stored {fld} absent", fld not in doc, f"{doc.get(fld)!r}")
                else:
                    check(label + f": stored {fld}", doc.get(fld) == want, f"{doc.get(fld)!r}")


# ---------------------------------------------------------------------------
# 3. Transactions: writes join the service's transaction, all or nothing
# ---------------------------------------------------------------------------
store = fresh()
with store.transaction() as tx:
    a = V.create(store, example({"$example": "idea_only"}), "user:todd", tx=tx, now=START)
    b = V.create(store, example({"$example": "free_venue"}), "user:todd", tx=tx, now=START)
check("tx: both creates accepted", a.ok and b.ok)
check("tx: both stored after commit", len(store.data["test_venues"]) == 2)
try:
    with store.transaction() as tx:
        V.update(store, a.data["id"], {"name": "Changed"}, "user:todd", tx=tx, now=START)
        V.soft_delete(store, b.data["id"], "user:todd", tx=tx, now=START)
        raise RuntimeError("service failed after calling handlers")
except RuntimeError:
    pass
check("tx: error before commit writes nothing", store.data["test_venues"][a.data["id"]]["name"] == "Possible cafe venue"
      and "deleted_at" not in store.data["test_venues"][b.data["id"]])

# ---------------------------------------------------------------------------
# 4. Test prefix: handlers only ever see names from the registry; the store adds the prefix
# ---------------------------------------------------------------------------
check("collection name comes from the registry", V.VENUES.name == "venues")
check("prefix keeps real collection untouched", "venues" not in store.data and "test_venues" in store.data)

# ---------------------------------------------------------------------------
# 5. Schema-derived facts the update logic depends on
# ---------------------------------------------------------------------------
setf, remf = involved_fields(V.VENUES.schema)
check("set_involved holds the GPS and cost triggers", {"latitude", "cost_cents", "status", "rooms"} <= setf)
check("remove_involved holds contact fields and required ones",
      {"contact_email", "contact_phone", "street_address", "name"} <= remf)
check("a plain field is in neither set", "notes" not in setf and "notes" not in remf)
check("code rules read only rooms and availability_hours", V.RULE_FIELDS == {"rooms", "availability_hours"})

# ---------------------------------------------------------------------------
# 6. Deliberate-break check: prove these tests would notice a handler that stopped validating
# ---------------------------------------------------------------------------
real = V.check_document
V.check_document = lambda coll, doc: []
slipped = 0
for name, body in EXAMPLES["invalid"].items():
    if V.create(fresh(), copy.deepcopy(body), "user:todd", now=START).ok:
        slipped += 1
V.check_document = real
check("break test: with the checker switched off most invalid examples would get through", slipped >= 15, f"{slipped}")
check("break test: checker restored", V.check_document is real)

print(f"\n{total - len(fails)}/{total} checks passed")
if fails:
    print("FAILED:\n  " + "\n  ".join(fails))
    sys.exit(1)
