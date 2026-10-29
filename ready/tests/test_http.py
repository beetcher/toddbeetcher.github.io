"""Authenticated HTTP-boundary checks against actual services/handlers/contracts."""
import json
from pathlib import Path
import unittest
from uuid import uuid4

from ready.application import Application
from ready.crud.memory_store import MemoryStore
from ready.services import ReadyService

KEY = "local-test-key-not-a-production-secret-123456789"
ROOT = Path(__file__).resolve().parents[1]


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.service = ReadyService(MemoryStore())
        self.app = Application(self.service, KEY)

    def call(self, method, target, data=None, auth=True, **extra):
        headers = {"Content-Type": "application/json", **extra}
        if auth:
            headers["Authorization"] = "Bearer " + KEY
        status, headers, body = self.app.handle(method, target, headers, json.dumps(data).encode() if data is not None else b"")
        return status, headers, json.loads(body)

    def test_management_static_contains_no_key_and_has_csp(self):
        status, headers, body = self.app.handle("GET", "/ready/")
        self.assertEqual(status, 200)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertNotIn(KEY.encode(), body)

    def test_health_public_but_data_requires_key(self):
        self.assertEqual(self.call("GET", "/v1/health", auth=False)[0], 200)
        self.assertEqual(self.call("GET", "/v1/questions", auth=False)[0], 401)

    def test_missing_server_key_fails_closed(self):
        app = Application(self.service, "")
        self.assertEqual(app.handle("GET", "/v1/questions")[0], 503)

    def test_schemas_and_seed_available(self):
        self.assertEqual(self.call("GET", "/v1/schemas")[0], 200)
        self.assertEqual(self.call("GET", "/v1/schemas/question")[0], 200)
        self.assertEqual(self.app.handle("GET", "/ready/seed.json")[0], 200)

    def test_json_array_and_nonfinite_input_rejected(self):
        headers = {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}
        for body in (b"[]", b'{"value":NaN}', b"invalid"):
            self.assertEqual(self.app.handle("POST", "/v1/selections", headers, body)[0], 400)

    def test_unknown_query_and_duplicate_parameter_rejected(self):
        for target in ("/v1/questions?evil=true", "/v1/questions?limit=2&limit=3"):
            self.assertEqual(self.call("GET", target)[0], 400)

    def test_unsupported_criteria_return_validation_not_server_error(self):
        self.assertEqual(self.call("GET", '/v1/questions?criteria=%7B%22evil%22%3A1%7D')[0], 422)

    def test_full_api_import_test_delivery_result_roundtrip(self):
        seed = json.loads((ROOT / "seed/ai_readiness.json").read_text())
        seed.update(dry_run=False, idempotency_key=str(uuid4()))
        status, _, result = self.call("POST", "/v1/content/imports", seed)
        self.assertEqual(status, 201)
        set_ids = [row["id"] for row in result["data"]["created"] if row["type"] == "question_answer_set"][:2]
        create = {"set_ids": set_ids, "allow_duplicates": False, "duplicate_pair_count": 0,
            "label": "HTTP test", "metadata": {}, "origin": {"author": "Builder", "authorship_kind": "system", "source_reference": "validation"}}
        status, _, result = self.call("POST", "/v1/tests", create, **{"Idempotency-Key": str(uuid4())})
        self.assertEqual(status, 201)
        test = result["data"]
        self.assertEqual(self.call("GET", "/v1/tests/" + test["id"])[0], 200)
        report = {"test_id": test["id"], "responses": [{"item_id": row["item_id"], "answer_ids": [answer["answer_id"] for answer in row["answers"] if answer["role"] == "strong"]} for row in test["items"]], "returned_score": {"points_earned": 0, "points_possible": 2}, "idempotency_key": str(uuid4())}
        status, _, output = self.call("POST", "/v1/attempts", report)
        self.assertEqual(status, 201)
        self.assertTrue(output["data"]["score_difference"]["is_different"])
        self.assertEqual(output["data"]["calculated_score"]["points_earned"], 2)
        retry_status, retry_headers, replay = self.call("POST", "/v1/attempts", report)
        self.assertEqual(retry_status, 200)
        self.assertEqual(retry_headers["Idempotency-Replayed"], "true")
        self.assertEqual(replay["data"]["id"], output["data"]["id"])
        self.assertEqual(self.call("GET", "/v1/tests/" + test["id"] + "/attempts")[2]["data"]["count"], 1)

    def test_nonadministration_routes(self):
        random_id = str(uuid4())
        self.assertEqual(self.call("POST", "/v1/attempts/" + random_id + "/responses", {})[0], 405)
        self.assertEqual(self.call("POST", "/v1/attempts/" + random_id + "/complete", {})[0], 405)
        self.assertEqual(self.call("DELETE", "/v1/tests/" + random_id, {})[0], 405)

    def test_no_path_traversal(self):
        self.assertNotEqual(self.app.handle("GET", "/ready/../../.env")[0], 200)

    def test_cors_does_not_grant_arbitrary_origin(self):
        status, headers, _ = self.app.handle("OPTIONS", "/v1/tests", {"Origin": "https://untrusted.example"})
        self.assertEqual(status, 403)
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_body_limit_enforced(self):
        self.assertEqual(self.app.handle("POST", "/v1/questions", {"Authorization": "Bearer " + KEY}, b"x" * 262145)[0], 413)

    def test_all_documented_operation_families_and_archive_aliases(self):
        """Exercise concrete HTTP contracts end-to-end, including preserved revisions."""
        origin = {"author": "Builder", "authorship_kind": "system", "source_reference": "validation"}
        def call(method, path, data=None, **headers):
            status, _, result = self.call(method, path, data, **headers)
            self.assertIn(status, (200, 201), (method, path, result))
            return result["data"]
        def create(kind, data):
            return call("POST", "/v1/" + kind, data, **{"Idempotency-Key": str(uuid4())})
        def archive(kind, row, method="PUT"):
            path = "/v1/" + kind + "/" + row["id"] + ("/archive" if method == "PUT" else "")
            return call(method, path, {"is_archived": True, "reason": "Validation complete", "expected_record_version": row["record_version"]})
        call("GET", "/v1/health")
        call("GET", "/v1/capabilities")
        call("GET", "/v1/schemas")
        call("GET", "/v1/schemas/question")
        call("POST", "/v1/person-ids", {})
        base = {"origin": origin, "metadata": {}, "status": "published"}
        q = create("questions", {**base, "question_text": "First?", "question_type": "single_choice"})
        call("GET", "/v1/questions/" + q["id"])
        call("GET", "/v1/questions")
        q2 = call("PATCH", "/v1/questions/" + q["id"], {"question_text": "Revised?"}, **{"If-Match": '"1"'})
        archive("questions", self.service.get("questions", q["id"]), "DELETE")
        a = create("answers", {**base, "answer_text": "Strong"})
        wrong = create("answers", {**base, "answer_text": "Wrong"})
        call("GET", "/v1/answers/" + a["id"])
        call("GET", "/v1/answers")
        wrong2 = call("PATCH", "/v1/answers/" + wrong["id"], {"answer_text": "Revised wrong"}, **{"If-Match": '"1"'})
        archive("answers", self.service.get("answers", wrong["id"]), "DELETE")
        pair = create("sets", {**base, "label": "Set", "question_id": q2["id"], "connections": [{"answer_id": a["id"], "role": "strong"}, {"answer_id": wrong2["id"], "role": "incorrect"}]})
        call("GET", "/v1/sets/" + pair["id"])
        call("GET", "/v1/sets")
        pair2 = call("PATCH", "/v1/sets/" + pair["id"], {"label": "Revised set"}, **{"If-Match": '"1"'})
        archive("sets", self.service.get("sets", pair["id"]), "DELETE")
        call("GET", "/v1/questions/" + q2["id"] + "/answers")
        call("GET", "/v1/answers/" + a["id"] + "/relationships")
        call("POST", "/v1/selections", {"target": "sets", "mode": "random", "count": 5})
        seed = json.loads((ROOT / "seed/ai_readiness.json").read_text())
        call("POST", "/v1/content/imports", seed)
        test_request = {"label": "Test", "origin": origin, "metadata": {}, "set_ids": [pair2["id"]], "allow_duplicates": False, "duplicate_pair_count": 0}
        test = create("tests", test_request)
        call("GET", "/v1/tests/" + test["id"])
        call("GET", "/v1/tests")
        call("POST", "/v1/tests/" + test["id"] + "/variants", {**test_request, "label": "Variant"}, **{"Idempotency-Key": str(uuid4())})
        archive("tests", test)
        report = {"test_id": test["id"], "responses": [{"item_id": test["items"][0]["item_id"], "answer_ids": [a["id"]]}], "returned_score": {"points_earned": 0, "points_possible": 1}, "idempotency_key": str(uuid4())}
        attempt = call("POST", "/v1/attempts", report)
        call("GET", "/v1/attempts/" + attempt["id"])
        call("GET", "/v1/attempts")
        call("GET", "/v1/tests/" + test["id"] + "/attempts")
        for kind, row in (("questions", q2), ("answers", a), ("sets", pair2), ("attempts", attempt)):
            archive(kind, row)


if __name__ == "__main__":
    unittest.main()
