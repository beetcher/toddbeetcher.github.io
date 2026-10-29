#!/usr/bin/env python3
"""Real Firestore emulator-only integration check. Never runs against live data.

Requires FIRESTORE_EMULATOR_HOST and a demo- project. Uses only tagged synthetic
records, preserves them in the emulator, and tests concurrent identified reports.
Missing SDK/emulator is failure/blocked, not a passing test.
"""
import json
import os
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))


def main():
    project = os.environ.get("READY_EMULATOR_PROJECT", "demo-ready-local")
    if not os.environ.get("FIRESTORE_EMULATOR_HOST") or not project.startswith("demo-"):
        print("Refused: set FIRESTORE_EMULATOR_HOST and use a demo- project.")
        return 2
    from ready.crud.firestore_store import FirestoreStore
    from ready.services import ReadyService
    service = ReadyService(FirestoreStore(project))
    seed = json.loads((ROOT / "seed/ai_readiness.json").read_text())
    seed.update(dry_run=False, idempotency_key=str(uuid4()))
    preview = service.import_content({**seed, "dry_run": True})
    assert preview["is_valid"]
    imported = service.import_content(seed)
    assert service.import_content(seed)["created"] == imported["created"]
    ids = [row["id"] for row in imported["created"] if row["type"] == "question_answer_set"][:2]
    test, _ = service.create_test({"label": "Emulator validation", "metadata": {"tags": ["system_validation"]},
        "origin": {"author": "READY builder", "authorship_kind": "system", "source_reference": "emulator check"},
        "set_ids": ids, "allow_duplicates": False, "duplicate_pair_count": 0}, str(uuid4()))
    report = {"test_id": test["id"], "person_id": "emulator-"+str(uuid4()), "test_taken_at": "2026-10-28T14:00:00+02:00",
        "responses": [{"item_id": row["item_id"], "answer_ids": [answer["answer_id"] for answer in row["answers"] if answer["role"] == "strong"]} for row in test["items"]],
        "returned_score": {"points_earned": 0, "points_possible": 2}, "idempotency_key": str(uuid4())}
    first, replay = service.submit_result(report)
    assert not replay and first["calculated_score"]["points_earned"] == 2
    assert service.result(first["id"])["submitted_payload"] == report
    assert service.submit_result(report)[1]
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(service.submit_result, ({**report, "idempotency_key": str(uuid4())} for _ in range(2))))
    assert all(not replay for _, replay in rows)
    history = service.list("attempts", test_id=test["id"], person_id=report["person_id"], include_history=True)
    assert history["count"] == 3
    assert service.list("attempts", test_id=test["id"], person_id=report["person_id"])["count"] == 1
    assert service.result(first["id"])["returned_score"]["points_earned"] == 0
    print("Firestore emulator passed: import/replay, frozen test, dual scoring, concurrent linked results and preserved history.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
