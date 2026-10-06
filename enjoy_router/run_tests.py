#!/usr/bin/env python3
"""Run schemas/examples/registration_request.test_records.json against the core, in memory.

    python3 enjoy_router/run_tests.py

Each test runs in file order against one in-memory store seeded from setup.scheduled_classes,
with the clock fixed at setup.now. A test passes when every expectation it states is met:
ok, error_code, field_errors (exact set), stored, snapshot, stored_fields, no_previous_id,
previous_id_of, replay_of, discarded_as_spam. Every stored document must also pass the schema.
Needs: pip install jsonschema
"""
import json
import pathlib
import sys
from datetime import datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from core import Schemas, handle_registration_request  # noqa: E402
from memory_store import MemoryStore  # noqa: E402


def build_body(case, by_name, depth=0):
    if depth > 10:
        raise RuntimeError("request_from loop")
    if "request_from" in case:
        body = dict(build_body(by_name[case["request_from"]], by_name, depth + 1))
        body.update(case.get("override", {}))
        for k in case.get("remove", []):
            body.pop(k, None)
        return body
    return dict(case["request"])


def run(records_path: pathlib.Path, schemas: Schemas, verbose: bool = True) -> list:
    data = json.loads(records_path.read_text())
    cases = data["tests"]
    by_name = {c["name"]: c for c in cases}
    now = datetime.fromisoformat(data["setup"]["now"].replace("Z", "+00:00"))
    store = MemoryStore(data["setup"]["scheduled_classes"])
    stored_by_test: dict = {}   # test name -> stored doc
    answered: dict = {}         # test name -> confirmation number replied
    fails = []

    for c in cases:
        exp = c["expect"]
        before = len(store.requests)
        r = handle_registration_request(build_body(c, by_name), store, schemas, now=now)
        problems = []

        if r.envelope["ok"] != exp["ok"]:
            problems.append(f"ok is {r.envelope['ok']}, expected {exp['ok']}")
        if not exp["ok"]:
            code = r.envelope.get("error", {}).get("code")
            if code != exp.get("error_code"):
                problems.append(f"error code {code}, expected {exp.get('error_code')}")
        if "field_errors" in exp and sorted(r.field_errors) != sorted(exp["field_errors"]):
            problems.append(f"field_errors {sorted(r.field_errors)}, expected {sorted(exp['field_errors'])}")
        created = len(store.requests) - before
        if created not in (0, 1):
            problems.append(f"{created} documents stored for one request")
        if "stored" in exp and (created == 1) != exp["stored"]:
            problems.append(f"stored {created == 1}, expected {exp['stored']}")
        if exp.get("discarded_as_spam") and r.outcome != "discarded_spam":
            problems.append(f"outcome {r.outcome}, expected discarded_spam")
        if "replay_of" in exp:
            if r.outcome != "replay":
                problems.append(f"outcome {r.outcome}, expected replay")
            elif r.envelope["data"]["confirmation_number"] != answered.get(exp["replay_of"]):
                problems.append("replay did not return the original confirmation number")

        doc = store.requests[-1] if created == 1 else None
        if doc is not None:
            stored_by_test[c["name"]] = doc
            bad = [e.message[:60] for e in schemas.validator.iter_errors(doc)]
            if bad:
                problems.append(f"stored document fails the schema: {bad[0]}")
            for k in schemas.server_required:
                if k not in doc:
                    problems.append(f"stored document lacks server field {k}")
            if "snapshot" in exp:
                got = {k: doc.get(k) for k in schemas.snapshot_fields}
                if got != exp["snapshot"]:
                    problems.append(f"snapshot {got}, expected {exp['snapshot']}")
            elif any(k in doc for k in schemas.snapshot_fields) and not c.get("request_from") and "scheduled_class_id" not in doc:
                problems.append("snapshot present without a class pick")
            for k, v in exp.get("stored_fields", {}).items():
                if doc.get(k) != v:
                    problems.append(f"stored {k} is {doc.get(k)!r}, expected {v!r}")
            if exp.get("no_previous_id") and "previous_id" in doc:
                problems.append("previous_id present, expected none")
            if "previous_id_of" in exp:
                want = stored_by_test.get(exp["previous_id_of"], {}).get("id")
                if doc.get("previous_id") != want:
                    problems.append("previous_id does not point at the earlier request")
        elif "snapshot" in exp or "stored_fields" in exp:
            problems.append("expected a stored document")

        if r.envelope["ok"] and r.outcome in ("created", "replay", "discarded_spam"):
            answered[c["name"]] = r.envelope["data"]["confirmation_number"]
        # the reply never carries anything but the number and the type
        if r.envelope["ok"] and set(r.envelope["data"]) != {"confirmation_number", "registration_type"}:
            problems.append("reply carries more than confirmation_number and registration_type")

        mark = "ok  " if not problems else "FAIL"
        if verbose:
            print(f"{mark} {c['name']}")
            for p in problems:
                print(f"       - {p}")
        fails += [f"{c['name']}: {p}" for p in problems]

    expected_stored = sum(1 for c in cases if c["expect"].get("stored"))
    if len(store.requests) != expected_stored:
        fails.append(f"end state: {len(store.requests)} documents stored, expected {expected_stored}")
    numbers = [d["confirmation_number"] for d in store.requests]
    if len(numbers) != len(set(numbers)):
        fails.append("end state: duplicate confirmation numbers")
    return fails


def main() -> int:
    schemas = Schemas.load()
    records = pathlib.Path(__file__).resolve().parent.parent / "schemas" / "examples" / "registration_request.test_records.json"
    if len(sys.argv) > 1:
        records = pathlib.Path(sys.argv[1])
    fails = run(records, schemas)
    total = len(json.loads(records.read_text())["tests"])
    if fails:
        print(f"\nFAILED: {len(fails)} problem(s)")
        return 1
    print(f"\nOK: all {total} test records pass against the core")
    return 0


if __name__ == "__main__":
    sys.exit(main())
