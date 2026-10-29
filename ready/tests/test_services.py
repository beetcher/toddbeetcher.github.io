"""Integration of real schemas/handlers/services, with atomic memory persistence."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import unittest
from uuid import uuid4

from ready.crud.memory_store import MemoryStore
from ready.services import ReadyService, ServiceError

ROOT = Path(__file__).resolve().parents[1]


class ServicesTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.service = ReadyService(self.store)
        self.seed = json.loads((ROOT / "seed/ai_readiness.json").read_text())
        self.seed.update(dry_run=False, idempotency_key=str(uuid4()))
        self.imported = self.service.import_content(self.seed)
        self.set_ids = [row["id"] for row in self.imported["created"] if row["type"] == "question_answer_set"]

    def assembly_request(self, ids=None, pairs=0):
        return {"label": "Service integration test", "metadata": {"topics": ["ai_readiness"]},
                "origin": {"author": "Builder", "authorship_kind": "system", "source_reference": "validation"},
                "set_ids": ids or self.set_ids[:2], "allow_duplicates": bool(pairs), "duplicate_pair_count": pairs}

    def make_test(self, ids=None, pairs=0):
        return self.service.create_test(self.assembly_request(ids, pairs), str(uuid4()))[0]

    def report(self, test, person=False):
        request = {"test_id": test["id"], "responses": [{"item_id": item["item_id"], "answer_ids": [row["answer_id"] for row in item["answers"] if row["role"] == "strong"]} for item in test["items"]],
                   "returned_score": {"points_earned": 0, "points_possible": len(test["items"])}, "idempotency_key": str(uuid4())}
        if person:
            request.update(person_id="external-user-1", test_taken_at="2026-10-28T12:00:00Z")
        return request

    def test_import_preview_leaves_no_data(self):
        service = ReadyService(MemoryStore())
        preview = deepcopy(self.seed)
        preview["dry_run"] = True
        self.assertTrue(service.import_content(preview)["is_valid"])
        self.assertEqual(service.list("questions")["records"], [])

    def test_import_replay_stable_mapping_and_mismatch(self):
        again = self.service.import_content(self.seed)
        self.assertEqual(again["created"], self.imported["created"])
        changed = deepcopy(self.seed)
        changed["answers"][0]["data"]["answer_text"] = "A different answer"
        with self.assertRaises(ServiceError) as raised:
            self.service.import_content(changed)
        self.assertEqual(raised.exception.code, "conflict")

    def test_bad_import_rolls_back_all_atoms(self):
        service = ReadyService(MemoryStore())
        bad = deepcopy(self.seed)
        bad["sets"][0]["connections"][0]["answer_ref"] = "missing_ref"
        with self.assertRaises(ServiceError):
            service.import_content(bad)
        self.assertEqual(service.list("answers")["records"], [])

    def test_shortage_returns_and_preserves_found_items(self):
        result = self.service.select({"target": "sets", "mode": "random", "count": 15})
        self.assertEqual(result["found_count"], 10)
        self.assertEqual(result["shortfall_count"], 5)
        self.assertEqual(result["available_actions"], ["start_over", "add_more", "cancel"])
        self.assertEqual(len(self.service.list("tests")["records"]), 0)
        extra = self.service.select({"target": "sets", "mode": "random", "count": 10, "exclude_ids": [row["id"] for row in result["items"]]})
        self.assertEqual(extra["found_count"], 0)

    def test_combined_criteria_work_on_atoms_and_sets(self):
        for kind in ("questions", "answers", "sets"):
            found = self.service.select({"target": kind, "mode": "ordered", "count": 1,
                "criteria": {"topics": ["ai_readiness"], "audiences": ["adult_beginner"], "difficulty": ["basic"], "tags": ["system_validation"]}})
            self.assertEqual(found["found_count"], 1)
            none = self.service.select({"target": kind, "mode": "ordered", "count": 1, "criteria": {"topics": ["no_such_topic"]}})
            self.assertEqual(none["found_count"], 0)

    def test_published_set_checks_missing_and_draft_references(self):
        value = deepcopy(self.seed["questions"][0]["data"])
        value["status"] = "draft"
        question, _ = self.service.create("questions", value, str(uuid4()))
        existing = self.service.get("sets", self.set_ids[0])
        request = {k: deepcopy(existing[k]) for k in ("label", "origin", "metadata", "status", "connections")}
        request["question_id"] = question["id"]
        with self.assertRaises(ServiceError):
            self.service.create("sets", request, str(uuid4()))

    def test_creations_are_idempotent_even_under_concurrency(self):
        key = str(uuid4())
        value = self.seed["questions"][0]["data"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            rows = list(pool.map(lambda _: self.service.create("questions", value, key), range(2)))
        self.assertEqual(rows[0][0]["id"], rows[1][0]["id"])
        self.assertEqual(sum(replayed for _, replayed in rows), 1)

    def test_frozen_test_unchanged_after_library_revision_and_archive(self):
        test = self.make_test()
        old = self.service.get("sets", self.set_ids[0])
        self.service.revise("sets", old["id"], {"label": "A new variant"}, 1)
        self.service.archive("tests", test["id"], {"is_archived": True, "reason": "Done distributing", "expected_record_version": 1})
        self.assertEqual(self.service.get("tests", test["id"])["items"], test["items"])
        result, _ = self.service.submit_result(self.report(test))
        self.assertEqual(result["calculated_score"]["percentage"], 100)

    def test_duplicate_occurrences_grade_independently(self):
        test = self.make_test([self.set_ids[0], self.set_ids[0]], 1)
        report = self.report(test)
        report["responses"].pop()
        result, _ = self.service.submit_result(report)
        self.assertEqual(result["calculated_score"]["points_earned"], 1)
        self.assertEqual(result["calculated_score"]["points_possible"], 2)
        self.assertNotEqual(test["items"][0]["item_id"], test["items"][1]["item_id"])

    def test_result_both_scores_discrepancy_and_breakdowns(self):
        test = self.make_test()
        result, _ = self.service.submit_result(self.report(test))
        self.assertEqual(result["returned_score"]["points_earned"], 0)
        self.assertEqual(result["calculated_score"]["points_earned"], 2)
        self.assertTrue(result["score_difference"]["is_different"])
        self.assertTrue(result["breakdowns"])

    def test_identified_correction_links_preserved_results(self):
        test = self.make_test()
        report = self.report(test, True)
        first, _ = self.service.submit_result(report)
        retry, replayed = self.service.submit_result(report)
        self.assertTrue(replayed)
        self.assertEqual(retry["id"], first["id"])
        report["idempotency_key"] = str(uuid4())
        report["returned_score"]["points_earned"] = 2
        second, _ = self.service.submit_result(report)
        self.assertEqual(second["previous_id"], first["id"])
        self.assertEqual(second["series_id"], first["id"])
        self.assertEqual(self.service.result(first["id"])["returned_score"]["points_earned"], 0)
        self.assertEqual(len(self.service.list("attempts", include_history=True)["records"]), 2)
        self.assertEqual(len(self.service.list("attempts")["records"]), 1)

    def test_anonymous_reports_do_not_infer_same_person(self):
        test = self.make_test()
        report = self.report(test)
        first, _ = self.service.submit_result(report)
        report["idempotency_key"] = str(uuid4())
        second, _ = self.service.submit_result(report)
        self.assertNotEqual(first["id"], second["id"])
        self.assertNotIn("previous_id", second)

    def test_repeated_person_different_test_time_is_distinct(self):
        test = self.make_test()
        report = self.report(test, True)
        self.service.submit_result(report)
        report.update(idempotency_key=str(uuid4()), test_taken_at="2026-10-28T13:00:00Z")
        second, _ = self.service.submit_result(report)
        self.assertNotIn("previous_id", second)

    def test_concurrent_identified_reports_form_one_chain(self):
        test = self.make_test()
        first, second = self.report(test, True), self.report(test, True)
        with ThreadPoolExecutor(max_workers=2) as pool:
            records = list(pool.map(self.service.submit_result, (first, second)))
        self.assertEqual(sum("previous_id" not in record for record, _ in records), 1)
        self.assertEqual(len(self.service.list("attempts")["records"]), 1)
        self.assertEqual(len(self.service.list("attempts", include_history=True)["records"]), 2)

    def test_original_report_preserved_before_time_normalization(self):
        test = self.make_test()
        request = self.report(test, True)
        result, _ = self.service.submit_result(request)
        self.assertEqual(json.loads(result["submitted_payload"]), request)

    def test_relationships_keep_question_relative_roles(self):
        answer = next(row["id"] for row in self.imported["created"] if row["client_ref"] == "test_a021")
        found = self.service.relationships("answers", answer)
        self.assertEqual(found["count"], 3)
        strong = self.service.relationships("answers", answer, role="strong")
        self.assertEqual(strong["count"], 2)

    def test_inspection_bundle_stable_but_test_occurrences_unique(self):
        self.assertEqual(self.service.bundle(self.set_ids[0]), self.service.bundle(self.set_ids[0]))
        test = self.make_test([self.set_ids[0], self.set_ids[0]], 1)
        self.assertNotEqual(test["items"][0]["item_id"], test["items"][1]["item_id"])

    def test_soft_only_half_strong_full_regardless_soft(self):
        test = self.make_test()
        item = test["items"][0]
        item["question_type"] = "multiple_choice"
        strong = next(row["answer_id"] for row in item["answers"] if row["role"] == "strong")
        soft = next(row for row in item["answers"] if row["role"] == "incorrect")
        soft["role"] = "ambiguous"
        test["items"] = [item]
        for selected, expected in (([soft["answer_id"]], .5), ([strong], 1), ([strong, soft["answer_id"]], 1), ([], 0)):
            report = self.report(test)
            report["responses"][0]["answer_ids"] = selected
            grade = self.service.grade(test, report)
            self.assertEqual(grade["calculated_score"]["points_earned"], expected)

    def test_unoffered_answer_not_silently_graded_wrong(self):
        test = self.make_test()
        report = self.report(test)
        report["responses"][0]["answer_ids"] = [str(uuid4())]
        with self.assertRaises(ServiceError) as raised:
            self.service.submit_result(report)
        self.assertEqual(raised.exception.issue, "not_offered")
        self.assertEqual(self.service.list("attempts")["records"], [])


if __name__ == "__main__":
    unittest.main()
