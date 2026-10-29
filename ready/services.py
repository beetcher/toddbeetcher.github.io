"""READY domain services: content → selections → immutable tests → returned results.

D002: caller administers tests. No live answer/session API. All collection access
passes through handlers. Transactions coordinate references, receipts and chains.
Inventory is deliberately bounded (1000 revisions per collection); never pretend
that a first page is a random sample of a larger unexamined population.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import random
from uuid import UUID, uuid4

from . import contracts
from .crud import questions_crud as Q, answers_crud as A
from .crud import question_answer_sets_crud as S, tests_crud as T, attempts_crud as R

HANDLERS = {"questions": Q, "answers": A, "sets": S, "tests": T, "attempts": R}
CONTRACTS = {"questions": "question", "answers": "answer", "sets": "question_answer_set"}
MAX_POOL = 1000
POLICY = "strong_soft_fraction_v1"


class ServiceError(Exception):
    """Value-free service error mapped by the HTTP boundary, never a raw exception."""
    def __init__(self, code="validation_failed", field="body", issue="invalid", details=None):
        self.code, self.field, self.issue, self.details = code, field, issue, details or {}
        super().__init__(code)


def _result(value):
    if not value.ok:
        first = value.problems[0] if value.problems else {}
        raise ServiceError(value.code, first.get("field", "body"), first.get("issue", value.code))
    return value.data


def _validate(name, value):
    problems = contracts.problems(name, value)
    if problems:
        raise ServiceError(field=problems[0]["field"], issue=problems[0]["issue"])


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _uid(key, operation, actor):
    # Server allocation of stable UUID-form IDs enables replay without a sixth
    # collection. The API key protects access; these IDs are not credentials.
    raw = hashlib.sha256(f"{actor}:{operation}:{key}".encode()).digest()[:16]
    return str(UUID(bytes=raw, version=4))


def _key(value):
    try:
        if not isinstance(value, str) or UUID(value).version != 4:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ServiceError(field="idempotency_key", issue="uuid_v4_required")
    return value


def _time(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    except (ValueError, AttributeError, TypeError):
        raise ServiceError(field="test_taken_at", issue="invalid_time")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _number(value):
    return float(Decimal(str(value)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _percentage(earned, possible):
    return float((Decimal(str(earned)) * 100 / Decimal(str(possible))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


class ReadyService:
    def __init__(self, store, actor="user:super_admin"):
        self.store, self.actor = store, actor

    def _inventory(self, store, kind):
        rows = HANDLERS[kind].inventory(store, MAX_POOL + 1)
        if len(rows) > MAX_POOL:
            raise ServiceError(field="criteria", issue="candidate_pool_too_large", details={"max_candidate_scan": MAX_POOL})
        return rows

    def _get(self, store, kind, record_id, include_archived=True):
        if kind not in HANDLERS:
            raise ServiceError("not_found")
        return _result(HANDLERS[kind].get(store, record_id, include_archived))

    def get(self, kind, record_id, include_archived=True):
        """Super-admin inspection may retrieve preserved archived revisions."""
        return self._get(self.store, kind, record_id, include_archived)

    def _published(self, store, kind, record_id):
        doc = self._get(store, kind, record_id)
        if doc["is_archived"] or doc.get("successor_id") or doc.get("status") != "published":
            raise ServiceError(field=kind, issue="not_published_current")
        return doc

    def _check_set(self, store, doc):
        question = self._get(store, "questions", doc["question_id"])
        for row in doc["connections"]:
            self._get(store, "answers", row["answer_id"])
        if doc["status"] == "published":
            self._published(store, "questions", doc["question_id"])
            for row in doc["connections"]:
                self._published(store, "answers", row["answer_id"])
            strong = sum(row["role"] == "strong" for row in doc["connections"])
            if question["question_type"] == "single_choice" and strong != 1:
                raise ServiceError(field="connections", issue="single_choice_requires_one_strong")

    def _receipt(self, store, kind, record_id, digest):
        got = HANDLERS[kind].get(store, record_id, True)
        if not got.ok:
            if got.code == "not_found":
                return None
            _result(got)
        if got.data.get("request_digest") != digest:
            raise ServiceError("conflict", issue="idempotency_mismatch")
        return got.data

    def _create(self, store, kind, data, key, actor=None, operation=None, extra=None):
        actor = actor or self.actor
        _validate(CONTRACTS[kind] + "_create", data)
        digest = _digest(data)
        record_id = _uid(key, operation or f"create:{kind}", actor)
        old = self._receipt(store, kind, record_id, digest)
        if old:
            return old, True
        if kind == "sets":
            self._check_set(store, data)
        receipt = {"id": record_id, "series_id": record_id, "operation_key": key, "request_digest": digest, **(extra or {})}
        return _result(HANDLERS[kind].create(store, data, actor, "ready_import" if operation else "ready_admin", receipt)), False

    def create(self, kind, data, key):
        """Idempotent atom/set create; replay is same record, never another atom."""
        if kind not in CONTRACTS:
            raise ServiceError(field="type", issue="use_named_constructor")
        _key(key)
        return self.store.transact(lambda tx: self._create(tx, kind, data, key))

    def revise(self, kind, record_id, changes, expected):
        if kind not in CONTRACTS:
            raise ServiceError("conflict", issue="immutable_record")
        _validate(CONTRACTS[kind] + "_patch", changes)
        def work(tx):
            old = self._get(tx, kind, record_id)
            merged = deepcopy(old)
            for field, value in changes.items():
                if value is None:
                    merged.pop(field, None)
                else:
                    merged[field] = value
            if kind == "sets":
                # Validate merged structure before reading connection fields.
                writable = {k: v for k, v in merged.items() if k not in S.COLLECTION.read_only}
                _validate("question_answer_set_create", writable)
                self._check_set(tx, merged)
            return _result(HANDLERS[kind].update(tx, record_id, changes, self.actor, expected))
        return self.store.transact(work)

    def archive(self, kind, record_id, request):
        _validate("archive_request", request)
        if kind not in HANDLERS:
            raise ServiceError("not_found")
        return self.store.transact(lambda tx: _result(HANDLERS[kind].set_archived(tx, record_id, self.actor,
            request["expected_record_version"], request["reason"], request["is_archived"])))

    def list(self, kind, *, include_archived=False, include_history=False, person_id=None, test_id=None, criteria=None, cursor=0, limit=25):
        if kind not in HANDLERS or not isinstance(limit, int) or not 1 <= limit <= 100 or not isinstance(cursor, int) or cursor < 0:
            raise ServiceError(field="pagination", issue="invalid")
        _validate("selection_request", {"target": "questions", "mode": "ordered", "count": 1, "criteria": criteria or {}})
        rows = self._inventory(self.store, kind)
        rows = [row for row in rows if (include_archived or not row["is_archived"])
                and (include_history or not row.get("successor_id"))
                and (person_id is None or row.get("person_id") == person_id)
                and (test_id is None or row.get("test_id") == test_id)
                and self._matches(row, criteria or {})]
        rows.sort(key=lambda row: (row["created_at"], row["id"]), reverse=True)
        page = {"records": rows[cursor:cursor+limit], "count": len(rows[cursor:cursor+limit])}
        if cursor + limit < len(rows):
            page["next_cursor"] = cursor + limit
        return page

    @staticmethod
    def _matches(row, criteria):
        metadata = row.get("metadata", {})
        for field, values in criteria.items():
            if field == "attributes":
                for name, expected in values.items():
                    actual = metadata.get("attributes", {}).get(name)
                    if isinstance(expected, list):
                        items = actual if isinstance(actual, list) else [actual]
                        if not set(expected).intersection(items):
                            return False
                    elif actual != expected:
                        return False
                continue
            actual = metadata.get(field, [])
            actual = [actual] if isinstance(actual, str) else actual
            if field == "tags":
                if not set(values).issubset(actual):
                    return False
            elif values and not set(values).intersection(actual):
                return False
        return True

    def select(self, request):
        _validate("selection_request", request)
        kind, mode = request["target"], request["mode"]
        records = self._inventory(self.store, kind)
        eligible = []
        for row in records:
            if row["is_archived"] or row.get("successor_id") or row.get("status") != "published":
                continue
            if kind == "sets":
                try:
                    self._check_set(self.store, row)
                except ServiceError as exc:
                    if exc.code == "not_found" or exc.issue == "not_published_current":
                        continue
                    raise
            if self._matches(row, request.get("criteria", {})) and row["id"] not in request.get("exclude_ids", []):
                eligible.append(row)
        if mode == "explicit":
            by_id = {row["id"]: row for row in eligible}
            selected = [by_id[id] for id in request["ids"] if id in by_id]
            requested = len(request["ids"])
        else:
            requested = request["count"]
            selected = random.SystemRandom().sample(eligible, min(requested, len(eligible))) if mode == "random" else eligible[:requested]
        return {"target": kind, "requested_count": requested, "found_count": len(selected),
                "shortfall_count": max(0, requested-len(selected)), "items": selected,
                "available_actions": ["start_over", "add_more", "cancel"] if len(selected) < requested else []}

    def bundle(self, set_id, store=None, require_available=False):
        store = store or self.store
        doc = self._published(store, "sets", set_id) if require_available else self._get(store, "sets", set_id)
        if require_available:
            self._check_set(store, doc)
        question = self._get(store, "questions", doc["question_id"])
        public_origin = lambda origin: {key: value for key, value in origin.items() if key != "notes"}
        choices = []
        for connection in doc["connections"]:
            answer = self._get(store, "answers", connection["answer_id"])
            choices.append({"answer_id": answer["id"], "answer_revision": answer["revision_number"],
                "answer_text": answer["answer_text"], "role": connection["role"],
                **({"feedback": connection["feedback"]} if connection.get("feedback") else {}),
                "metadata": deepcopy(connection.get("metadata", answer.get("metadata", {}))),
                "answer_metadata": deepcopy(answer.get("metadata", {})), "answer_origin": public_origin(answer["origin"])})
        return {"item_id": _uid(doc["id"], "inspection_occurrence", self.actor), "set_id": doc["id"], "set_revision": doc["revision_number"],
                "question_id": question["id"], "question_revision": question["revision_number"],
                "question_text": question["question_text"], "question_type": question["question_type"],
                "metadata": {**deepcopy(question.get("metadata", {})), **deepcopy(doc.get("metadata", {}))},
                "question_metadata": deepcopy(question.get("metadata", {})), "set_metadata": deepcopy(doc.get("metadata", {})),
                "question_origin": public_origin(question["origin"]), "set_origin": public_origin(doc["origin"]), "answers": choices}

    def relationships(self, kind, record_id, *, set_id=None, question_id=None, role=None, limit=25, cursor=0):
        """Contextual associations, paginated; never flatten different sets' truth."""
        self._get(self.store, kind, record_id)
        if role is not None and role not in ("strong", "ambiguous", "incorrect"):
            raise ServiceError(field="role", issue="invalid_value")
        if not isinstance(limit, int) or not 1 <= limit <= 100 or not isinstance(cursor, int) or cursor < 0:
            raise ServiceError(field="pagination", issue="invalid")
        found = []
        for record in self._inventory(self.store, "sets"):
            if set_id and record["id"] != set_id:
                continue
            if question_id and record["question_id"] != question_id:
                continue
            connections = [entry for entry in record["connections"] if (not role or entry["role"] == role)]
            if kind == "questions":
                if record["question_id"] != record_id or (role and not connections):
                    continue
            else:
                if not any(entry["answer_id"] == record_id for entry in connections):
                    continue
            found.append({**record, "bundle": self.bundle(record["id"])})
        output = {"records": found[cursor:cursor+limit], "count": len(found[cursor:cursor+limit])}
        if cursor+limit < len(found):
            output["next_cursor"] = cursor+limit
        return output

    def create_test(self, request, key, parent_test_id=None):
        _validate("test_create", request)
        _key(key)
        digest = _digest({"request": request, "parent_test_id": parent_test_id})
        record_id = _uid(key, "create:test", self.actor)
        def work(tx):
            old = self._receipt(tx, "tests", record_id, digest)
            if old:
                return old, True
            parent = self._get(tx, "tests", parent_test_id) if parent_test_id else None
            items = [self.bundle(id, tx, True) for id in request["set_ids"]]
            for item in items:
                item["item_id"] = str(uuid4())
            snapshot = {key: deepcopy(value) for key, value in request.items() if key != "set_ids"}
            snapshot.update(items=items, scoring_policy_version=POLICY,
                selection_summary={"mode": "explicit", "requested_count": len(items), "selected_count": len(items)})
            receipt = {"id": record_id, "series_id": record_id, "operation_key": key, "request_digest": digest}
            if parent:
                # A variant is distinct, not a successor: the original stays available.
                receipt["previous_id"] = parent["id"]
            return _result(T.create_frozen(tx, snapshot, self.actor, receipt)), False
        return self.store.transact(work)

    def import_content(self, request):
        _validate("bulk_import", request)
        rows = [("answers", row) for row in request["answers"]] + [("questions", row) for row in request["questions"]] + [("sets", row) for row in request["sets"]]
        if not rows or len(rows) > 200:
            raise ServiceError(field="records", issue="require_1_to_200_records")
        refs = [row["client_ref"] for _, row in rows]
        if len(set(refs)) != len(refs):
            raise ServiceError(field="client_ref", issue="duplicate_ref")
        key = request.get("idempotency_key") or str(uuid4())
        _key(key)
        digest = _digest({k: v for k, v in request.items() if k not in ("dry_run", "idempotency_key")})
        anchor = _uid(key, "import:anchor", self.actor)
        mapping = {row["client_ref"]: {"client_ref": row["client_ref"], "type": CONTRACTS[kind],
            "id": anchor if index == 0 else _uid(key, f"import:{row['client_ref']}", self.actor)} for index, (kind, row) in enumerate(rows)}
        class PreviewRollback(Exception):
            pass
        def work(tx):
            for kind in CONTRACTS:
                got = HANDLERS[kind].get(tx, anchor, True)
                if got.ok:
                    if got.data.get("request_digest") != digest:
                        raise ServiceError("conflict", issue="idempotency_mismatch")
                    return {"dry_run": request["dry_run"], "is_valid": True, "created": got.data["import_receipt"]["mapping"], "replayed": True}
            for index, (kind, row) in enumerate(rows):
                if kind == "sets":
                    def resolve(ref, expected):
                        found = mapping.get(ref)
                        if not found or found["type"] != expected:
                            raise ServiceError(field="references", issue="unknown_or_wrong_type_ref")
                        return found["id"]
                    data = {k: deepcopy(v) for k, v in row.items() if k not in ("client_ref", "question_ref", "connections")}
                    data["question_id"] = resolve(row["question_ref"], "question")
                    data["connections"] = [{**{k: deepcopy(v) for k, v in c.items() if k != "answer_ref"},
                        "answer_id": resolve(c["answer_ref"], "answer")} for c in row["connections"]]
                    self._check_set(tx, data)
                else:
                    data = row["data"]
                receipt = {"id": mapping[row["client_ref"]]["id"], "series_id": mapping[row["client_ref"]]["id"], "operation_key": key}
                if index == 0:
                    receipt.update(request_digest=digest, import_receipt={"mapping": list(mapping.values())})
                _result(HANDLERS[kind].create(tx, data, self.actor, "ready_import", receipt))
            result = {"dry_run": request["dry_run"], "is_valid": True, "created": list(mapping.values()), "replayed": False}
            if request["dry_run"]:
                raise PreviewRollback(result)
            return result
        try:
            return self.store.transact(work)
        except PreviewRollback as preview:
            result = preview.args[0]
            result["would_create"] = {"questions": len(request["questions"]), "answers": len(request["answers"]), "sets": len(request["sets"])}
            result.pop("created", None)
            return result
        except ServiceError as exc:
            if request["dry_run"]:
                return {"dry_run": True, "is_valid": False, "problems": [{"field": exc.field, "code": exc.issue}]}
            raise

    def submit_result(self, request):
        _validate("result_submit", request)
        key = _key(request["idempotency_key"])
        request = deepcopy(request)
        original_payload = json.dumps(request, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if "person_id" in request and (not request["person_id"].strip() or request["person_id"] != request["person_id"].strip()):
            raise ServiceError(field="person_id", issue="nonblank_trimmed_id_required")
        if "test_taken_at" in request:
            request["test_taken_at"] = _time(request["test_taken_at"])
        digest = _digest(request)
        record_id = _uid(key, "record:attempt", self.actor)
        def work(tx):
            old = self._receipt(tx, "attempts", record_id, digest)
            if old:
                return self.result_output(old, self._get(tx, "tests", old["test_id"])), True
            test = self._get(tx, "tests", request["test_id"])
            generated = self.grade(test, request)
            generated.update(id=record_id, series_id=record_id, received_at=_now(), request_digest=digest, submitted_payload=original_payload)
            if request.get("person_id"):
                root_id = _uid(_digest([request["test_id"], request["person_id"], request["test_taken_at"]]), "identified_run_root", self.actor)
                root = R.get(tx, root_id, True)
                if root.ok:
                    if root.data["idempotency_key"] == key:
                        if root.data["request_digest"] != digest:
                            raise ServiceError("conflict", issue="idempotency_mismatch")
                        return self.result_output(root.data, test), True
                    prior = self._get(tx, "attempts", root.data["chain_head_id"])
                    generated.update(previous_id=prior["id"], series_id=prior["series_id"], revision_number=prior["revision_number"]+1)
                    _result(R.link_successor(tx, prior, record_id, self.actor))
                    _result(R.set_chain_head(tx, root_id, record_id, self.actor))
                else:
                    _result(root) if root.code != "not_found" else None
                    generated.update(id=root_id, series_id=root_id, chain_head_id=root_id)
            attempt = _result(R.record_result(tx, request, generated, self.actor))
            return self.result_output(attempt, test), False
        return self.store.transact(work)

    @staticmethod
    def grade(test, submitted):
        """D002 deterministic policy: strong fraction; ambiguous-only half; wrong zero.

        Owner-approved strong/ambiguous cases preserved. Multi-strong fraction
        and wrong-option zero are explicit engineering defaults, versioned in
        each frozen test. No AI or proficiency classification is used.
        """
        if test["scoring_policy_version"] != POLICY:
            raise ServiceError("conflict", issue="unsupported_scoring_policy")
        reported = submitted["returned_score"]
        if reported["points_earned"] > reported["points_possible"]:
            raise ServiceError(field="returned_score", issue="earned_exceeds_possible")
        entries = submitted["responses"]
        if len({row["item_id"] for row in entries}) != len(entries):
            raise ServiceError(field="responses", issue="duplicate_item")
        item_ids = {row["item_id"] for row in test["items"]}
        if any(row["item_id"] not in item_ids for row in entries):
            raise ServiceError(field="responses", issue="unknown_item")
        by_id = {row["item_id"]: row for row in entries}
        results = []
        for item in test["items"]:
            selected = set(by_id.get(item["item_id"], {}).get("answer_ids", []))
            offered = {row["answer_id"]: row for row in item["answers"]}
            if not selected.issubset(offered):
                raise ServiceError(field="answer_ids", issue="not_offered")
            if item["question_type"] == "single_choice" and len(selected) > 1:
                raise ServiceError(field="answer_ids", issue="single_choice")
            strong = {key for key, value in offered.items() if value["role"] == "strong"}
            ambiguous = {key for key, value in offered.items() if value["role"] == "ambiguous"}
            wrong = {key for key, value in offered.items() if value["role"] == "incorrect"}
            credit = Decimal(0)
            if not selected.intersection(wrong):
                if selected.intersection(strong):
                    credit = Decimal(len(selected.intersection(strong))) / Decimal(len(strong))
                elif selected.intersection(ambiguous):
                    credit = Decimal("0.5")
            results.append({"item_id": item["item_id"], "credit": _number(credit),
                "selected_answer_ids": sorted(selected), "ambiguous_answer_ids": sorted(selected.intersection(ambiguous)),
                "feedback": [value["feedback"] for key, value in offered.items() if value.get("feedback") and (key in selected or key in strong)]})
        earned = _number(sum(Decimal(str(row["credit"])) for row in results))
        possible = len(results)
        percentage = _percentage(earned, possible)
        reported_percentage = _percentage(reported["points_earned"], reported["points_possible"])
        same = reported["points_possible"] == possible
        difference = {"is_different": Decimal(str(reported["points_earned"])) * possible != Decimal(str(earned)) * Decimal(str(reported["points_possible"])),
            "same_denominator": same, "percentage_point_difference": float((Decimal(str(reported["points_earned"])) * 100 / Decimal(str(reported["points_possible"])) - Decimal(str(earned)) * 100 / Decimal(possible)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))}
        if same:
            difference["points_difference"] = _number(Decimal(str(reported["points_earned"]))-Decimal(str(earned)))
        return {"calculated_score": {"points_earned": earned, "points_possible": possible, "percentage": percentage, "policy_version": POLICY},
                "score_difference": difference, "item_results": results}

    @staticmethod
    def result_output(attempt, test):
        output = deepcopy(attempt)
        output["attempt_id"] = output["id"]
        groups = defaultdict(lambda: {"points_earned": 0, "points_possible": 0})
        by_id = {row["item_id"]: row for row in test["items"]}
        for row in output["item_results"]:
            item = by_id[row["item_id"]]
            row.update(question_text=item["question_text"], set_id=item["set_id"])
            for dimension in ("topics", "learning_objectives"):
                for label in item.get("metadata", {}).get(dimension, []):
                    group = groups[(dimension, label)]
                    group["points_earned"] = _number(Decimal(str(group["points_earned"]))+Decimal(str(row["credit"])))
                    group["points_possible"] += 1
        output["breakdowns"] = [{"dimension": dimension, "label": label, **values,
            "percentage": _percentage(values["points_earned"], values["points_possible"])} for (dimension, label), values in sorted(groups.items())]
        # Receipt diagnostics are internal; scores/submitted evidence remain visible.
        output.pop("request_digest", None)
        return output

    def result(self, attempt_id):
        record = self._get(self.store, "attempts", attempt_id)
        return self.result_output(record, self._get(self.store, "tests", record["test_id"]))
