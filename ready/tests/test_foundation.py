"""Behavioral foundation checks: preservation, scope, repeats and protected input.

No network/Firebase. Firestore integration and API tests remain later milestones.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import unittest
from uuid import uuid4

from ready import contracts
from ready.crud import (
    answers_crud as answers, attempts_crud as attempts,
    question_answer_sets_crud as sets, questions_crud as questions, tests_crud as tests,
)
from ready.crud.memory_store import MemoryStore
from ready.crud.schema_kit import failure

ROOT = Path(__file__).resolve().parents[1]
ACTOR = "system:ready_test"


def fixture(name, stored=False):
    cases = json.loads((ROOT / "schemas" / f"{name}.examples.json").read_text())
    return deepcopy(next(row["data"] for row in cases if row["valid"] and bool(row.get("stored")) == stored))


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()

    def test_questions_and_answers_have_no_global_correctness_mapping(self):
        for module, name in ((questions, "question"), (answers, "answer")):
            value = fixture(name)
            value["is_correct"] = True
            self.assertFalse(module.create(self.store, value, ACTOR).ok)

    def test_reusable_answer_can_have_different_roles_in_different_sets(self):
        first = fixture("question_answer_set")
        second = deepcopy(first)
        second["question_id"] = str(uuid4())
        second["connections"][0]["role"] = "incorrect"
        second["connections"][1]["role"] = "strong"
        self.assertTrue(sets.create(self.store, first, ACTOR).ok)
        self.assertTrue(sets.create(self.store, second, ACTOR).ok)
        # These local handlers intentionally do not verify referenced documents.

    def test_content_revision_preserves_original(self):
        old = questions.create(self.store, fixture("question"), ACTOR).data
        revised = questions.update(self.store, old["id"], {"question_text": "Revised wording"}, ACTOR, 1)
        self.assertTrue(revised.ok)
        self.assertNotEqual(revised.data["id"], old["id"])
        self.assertEqual(revised.data["previous_id"], old["id"])
        self.assertEqual(revised.data["series_id"], old["id"])
        self.assertEqual(revised.data["revision_number"], 2)
        preserved = questions.get(self.store, old["id"]).data
        self.assertEqual(preserved["question_text"], old["question_text"])
        self.assertEqual(preserved["created_at"], old["created_at"])
        self.assertEqual(preserved["origin"], old["origin"])
        self.assertEqual(preserved["successor_id"], revised.data["id"])
        self.assertEqual(preserved["record_version"], 2)

    def test_parallel_content_revisions_cannot_fork_same_tip(self):
        old = questions.create(self.store, fixture("question"), ACTOR).data
        def revise(text):
            return questions.update(self.store, old["id"], {"question_text": text}, ACTOR, 1)
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(revise, ("One revision", "Another revision")))
        self.assertEqual(sum(row.ok for row in result), 1)
        self.assertEqual(next(row.code for row in result if not row.ok), "conflict")

    def test_archive_is_not_destruction_and_has_audit(self):
        old = answers.create(self.store, fixture("answer"), ACTOR).data
        archived = answers.soft_delete(self.store, old["id"], ACTOR, 1, "Validation complete")
        self.assertTrue(archived.ok)
        self.assertFalse(answers.get(self.store, old["id"]).ok)
        history = answers.get(self.store, old["id"], include_archived=True).data
        self.assertEqual(history["answer_text"], old["answer_text"])
        self.assertEqual(history["record_version"], 2)
        self.assertEqual(history["lifecycle_events"][0]["reason"], "Validation complete")
        restored = answers.set_archived(self.store, old["id"], ACTOR, 2, "Use again", False)
        self.assertTrue(restored.ok)
        self.assertEqual(len(restored.data["lifecycle_events"]), 2)

    def test_stale_archive_does_not_erase_history(self):
        old = answers.create(self.store, fixture("answer"), ACTOR).data
        answers.soft_delete(self.store, old["id"], ACTOR, 1, "Archive")
        stale = answers.set_archived(self.store, old["id"], ACTOR, 1, "Stale write", False)
        self.assertEqual(stale.code, "conflict")
        self.assertEqual(len(answers.get(self.store, old["id"], True).data["lifecycle_events"]), 1)

    def test_remove_required_field_returns_error_without_revision(self):
        old = questions.create(self.store, fixture("question"), ACTOR).data
        result = questions.update(self.store, old["id"], {"question_text": None}, ACTOR, 1)
        self.assertFalse(result.ok)
        self.assertEqual(len(questions.list(self.store).data["records"]), 1)

    def test_protected_record_fields_are_rejected(self):
        value = fixture("question")
        value["created_by"] = "system:pretend"
        self.assertFalse(questions.create(self.store, value, ACTOR).ok)
        value.pop("created_by")
        made = questions.create(self.store, value, ACTOR).data
        self.assertFalse(questions.update(self.store, made["id"], {"series_id": str(uuid4())}, ACTOR, 1).ok)

    def test_unknown_metadata_attributes_are_not_arbitrary_queries(self):
        value = fixture("question")
        value["metadata"]["attributes"] = {"invented_operator": "scan_everything"}
        self.assertFalse(questions.create(self.store, value, ACTOR).ok)

    def test_sets_reject_duplicate_answers_and_no_strong_answer(self):
        value = fixture("question_answer_set")
        value["connections"][1]["answer_id"] = value["connections"][0]["answer_id"]
        self.assertFalse(sets.create(self.store, value, ACTOR).ok)
        value = fixture("question_answer_set")
        for row in value["connections"]:
            row["role"] = "ambiguous"
        self.assertFalse(sets.create(self.store, value, ACTOR).ok)

    def test_two_duplicate_pairs_are_four_occurrences_not_triplets(self):
        value = fixture("test")
        original = deepcopy(value["items"][0])
        other = deepcopy(original)
        other["question_id"] = str(uuid4())
        other["set_id"] = str(uuid4())
        value["items"] = [deepcopy(row) for row in (original, other, original, other)]
        for row in value["items"]:
            row["item_id"] = str(uuid4())
        value.update(allow_duplicates=True, duplicate_pair_count=2)
        value["selection_summary"].update(selected_count=4, requested_count=4)
        result = tests.create_frozen(self.store, value, ACTOR)
        self.assertTrue(result.ok, result.problems)
        self.assertEqual(len(result.data["items"]), 4)
        value["items"][3]["question_id"] = original["question_id"]
        self.assertFalse(tests.create_frozen(self.store, value, ACTOR).ok)

    def test_same_question_in_different_sets_can_be_an_intentional_pair(self):
        value = fixture("test")
        second = deepcopy(value["items"][0])
        second.update(item_id=str(uuid4()), set_id=str(uuid4()))
        value["items"].append(second)
        value.update(allow_duplicates=True, duplicate_pair_count=1)
        value["selection_summary"].update(selected_count=2, requested_count=2)
        self.assertTrue(tests.create_frozen(self.store, value, ACTOR).ok)

    def test_duplicate_occurrence_ids_are_invalid(self):
        value = fixture("test")
        value["items"] *= 2
        value.update(allow_duplicates=True, duplicate_pair_count=1)
        value["selection_summary"].update(selected_count=2, requested_count=2)
        self.assertFalse(tests.create_frozen(self.store, value, ACTOR).ok)

    def test_test_content_cannot_be_updated_in_place(self):
        made = tests.create_frozen(self.store, fixture("test"), ACTOR).data
        result = tests.update(self.store, made["id"], {"label": "New"}, ACTOR, 1)
        self.assertEqual(result.code, "conflict")
        self.assertEqual(tests.get(self.store, made["id"]).data, made)

    def test_person_id_rejected_on_test_and_selection_requests(self):
        for name in ("test_create", "selection_request"):
            values = json.loads((ROOT / "schemas" / f"{name}.examples.json").read_text())
            value = deepcopy(values[0]["data"])
            value["person_id"] = "caller-person"
            self.assertTrue(contracts.problems(name, value))

    def test_closed_response_schema_rejects_nested_server_fields(self):
        value = fixture("attempt")
        value["responses"][0]["service_result"] = {"credit": 1}
        self.assertTrue(contracts.problems("result_submit", value))

    def test_identified_result_requires_occurrence_time_not_receipt_time(self):
        value = fixture("attempt")
        value["person_id"] = "person_17"
        self.assertTrue(contracts.problems("result_submit", value))
        value["test_taken_at"] = "2026-10-28T12:00:00Z"
        self.assertFalse(contracts.problems("result_submit", value))

    def test_nonfinite_caller_scores_are_rejected(self):
        for number in (float("nan"), float("inf"), -float("inf")):
            value = fixture("attempt")
            value["returned_score"]["points_earned"] = number
            self.assertTrue(contracts.problems("result_submit", value))

    def test_raw_result_create_update_cannot_bypass_grading_service(self):
        self.assertFalse(attempts.create(self.store, fixture("attempt"), ACTOR).ok)
        self.assertEqual(attempts.update(self.store, str(uuid4()), {}, ACTOR, 1).code, "conflict")

    def test_result_preserves_both_scores_without_overwrite(self):
        stored = fixture("attempt", stored=True)
        generated = {key: stored[key] for key in ("calculated_score", "score_difference", "item_results", "received_at", "request_digest")}
        submitted = fixture("attempt")
        submitted["returned_score"]["points_earned"] = 0
        generated["score_difference"].update(is_different=True, points_difference=-1, percentage_point_difference=-100)
        result = attempts.record_result(self.store, submitted, generated, ACTOR)
        self.assertTrue(result.ok, result.problems)
        self.assertEqual(result.data["returned_score"]["points_earned"], 0)
        self.assertEqual(result.data["calculated_score"]["points_earned"], 1)

    def test_failed_transaction_rolls_back_earlier_writes(self):
        def work(tx):
            questions.create(tx, fixture("question"), ACTOR)
            return failure("conflict")
        self.assertFalse(self.store.transact(work).ok)
        self.assertEqual(questions.list(self.store).data["records"], [])

    def test_native_builder_seed_has_ten_questions_four_choices_and_reuse(self):
        seed = json.loads((ROOT / "seed" / "ai_readiness.json").read_text())
        self.assertFalse(contracts.problems("bulk_import", seed))
        self.assertEqual(len(seed["questions"]), 10)
        self.assertEqual(len(seed["sets"]), 10)
        for row in seed["questions"] + seed["answers"]:
            self.assertIn("builder_created", row["data"]["metadata"]["tags"])
        uses = []
        for row in seed["sets"]:
            self.assertEqual(len(row["connections"]), 4)
            self.assertEqual(sum(c["role"] == "strong" for c in row["connections"]), 1)
            uses.extend(c["answer_ref"] for c in row["connections"])
        self.assertGreater(len(uses), len(set(uses)))


if __name__ == "__main__":
    unittest.main()
