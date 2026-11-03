"""Checks for the draft U.S. citizenship and civics library in ready/seed/library_us_citizenship (plan R4).

Everything here is local: JSON files, the bulk-import schema, and the in-memory
store used by the other unit tests. Nothing is imported to a live service.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path
import re
import unittest
from uuid import uuid4

from jsonschema import Draft202012Validator, FormatChecker

from ready.crud.memory_store import MemoryStore
from ready.services import ReadyService

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "seed" / "library_us_citizenship"
SCHEMA = json.loads((ROOT / "schemas" / "bulk_import.schema.json").read_text())

# file -> (questions, answers, sets, batch tag)
EXPECTED = {
    "us_citizenship_sample_01.json": (8, 27, 10, "ready_lib_us_citizenship_01"),
}
SAMPLE = "us_citizenship_sample_01.json"
MAIN = [name for name in EXPECTED if name != SAMPLE]
DIFFICULTIES = ["introductory", "basic", "intermediate", "advanced", "expert"]
AUDIENCES = {"naturalization_applicant", "adult_english_learner", "civics_teacher_or_tutor", "general_adult_learner"}
OBJECTIVES = {
    "explain_democratic_principles": ("principles_democracy", "skill_principles_democracy"),
    "describe_branches_and_powers": ("system_government", "skill_system_government"),
    "explain_federalism_and_elections": ("federalism_elections", "skill_federalism_elections"),
    "identify_rights_and_freedoms": ("rights_freedoms", "skill_rights_freedoms"),
    "describe_civic_responsibilities": ("civic_responsibilities", "skill_civic_responsibilities"),
    "outline_colonial_and_founding_history": ("colonial_founding", "skill_colonial_founding"),
    "trace_nineteenth_century_changes": ("nineteenth_century", "skill_nineteenth_century"),
    "summarize_modern_american_history": ("modern_history", "skill_modern_history"),
    "recognize_symbols_and_holidays": ("symbols_holidays", "skill_symbols_holidays"),
    "use_civics_geography": ("civics_geography", "skill_civics_geography"),
    "read_civic_vocabulary_in_context": ("reading_vocabulary", "skill_reading_vocabulary"),
}
FORMAT_TAGS = {"format_fact", "format_reasoning", "format_scenario", "format_select_all"}
ORIGIN = {"author": "READY builder", "authorship_kind": "system",
          "source_reference": "Original draft material; not an official assessment; awaiting owner review",
          "notes": "Study practice only; not the official naturalization test, not affiliated with or endorsed by USCIS, and not legal or immigration advice."}
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")
# Time-sensitive wording that must not appear in evergreen content.
STALE = re.compile(r"\$\s?\d|\bpercent\b|%|population|\brecent|currently|nowadays|this year|today's|\bpresident (biden|trump|obama|bush|clinton|lincoln)\b|"
                   r"\b(biden|trump|obama|harris|pelosi|mcconnell)\b|\b20[0-3]\d\b", re.I)


def load(name):
    return json.loads((LIBRARY / name).read_text())


def all_metadata(doc):
    for kind in ("questions", "answers"):
        for row in doc[kind]:
            yield kind, row["client_ref"], row["data"]["metadata"], row["data"]["status"], row["data"]["origin"]
    for row in doc["sets"]:
        yield "sets", row["client_ref"], row["metadata"], row["status"], row["origin"]


def published_copy(doc):
    copy = deepcopy(doc)
    for row in copy["questions"] + copy["answers"]:
        row["data"]["status"] = "published"
    for row in copy["sets"]:
        row["status"] = "published"
    return copy


class LibraryFiles(unittest.TestCase):
    def test_exactly_the_expected_files_exist(self):
        self.assertEqual(sorted(p.name for p in LIBRARY.glob("*.json")), sorted(EXPECTED))

    def test_counts_and_limits(self):
        for name, (q, a, s, _) in EXPECTED.items():
            doc = load(name)
            self.assertEqual((len(doc["questions"]), len(doc["answers"]), len(doc["sets"])), (q, a, s), name)
            self.assertLessEqual(len(doc["questions"]), 100, name)
            self.assertLessEqual(len(doc["answers"]), 400, name)
            self.assertLessEqual(len(doc["questions"]) + len(doc["answers"]) + len(doc["sets"]), 200, name)
            self.assertLessEqual((LIBRARY / name).stat().st_size, 256 * 1024, name)

    @unittest.skipUnless(MAIN, 'main batches not written yet')
    def test_target_totals_of_the_main_library(self):
        docs = [load(n) for n in MAIN]
        self.assertGreaterEqual(sum(len(d["questions"]) for d in docs), 50)
        self.assertGreaterEqual(sum(len(d["answers"]) for d in docs), 120)
        self.assertGreaterEqual(sum(len(d["sets"]) for d in docs), 50)

    def test_schema_valid_and_dry_run_flag(self):
        validator = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
        for name in EXPECTED:
            doc = load(name)
            self.assertEqual(list(validator.iter_errors(doc)), [], name)
            self.assertIs(doc["dry_run"], True, name)
            self.assertNotIn("idempotency_key", doc, name)

    def test_no_ids_timestamps_people_tests_or_stale_facts(self):
        for name in EXPECTED:
            text = (LIBRARY / name).read_text()
            self.assertIsNone(UUID.search(text), f"{name}: uuid")
            self.assertIsNone(TIMESTAMP.search(text), f"{name}: timestamp")
            doc = json.loads(text)
            self.assertEqual(set(doc), {"dry_run", "questions", "answers", "sets"}, name)
            texts = [r["data"]["question_text"] for r in doc["questions"]] + [r["data"]["answer_text"] for r in doc["answers"]]
            for s in doc["sets"]:
                texts += [s["label"]] + [c["feedback"] for c in s["connections"]] + [c.get("notes", "") for c in s["connections"]]
            for value in texts:
                self.assertIsNone(STALE.search(value), f"{name}: stale-risk wording: {value[:70]}")

    def test_refs_unique_and_resolve(self):
        for name in EXPECTED:
            doc = load(name)
            refs = [r["client_ref"] for k in ("questions", "answers", "sets") for r in doc[k]]
            self.assertEqual(len(refs), len(set(refs)), name)
            questions = {r["client_ref"] for r in doc["questions"]}
            answers = {r["client_ref"] for r in doc["answers"]}
            used_q, used_a = set(), set()
            for s in doc["sets"]:
                self.assertIn(s["question_ref"], questions, name)
                used_q.add(s["question_ref"])
                offered = [c["answer_ref"] for c in s["connections"]]
                self.assertEqual(len(offered), len(set(offered)), f"{name}: repeated choice in {s['client_ref']}")
                for ref in offered:
                    self.assertIn(ref, answers, name)
                used_a.update(offered)
            self.assertEqual(used_q, questions, f"{name}: unused question")
            self.assertEqual(used_a, answers, f"{name}: unused answer")
        all_refs = [r["client_ref"] for n in EXPECTED for k in ("questions", "answers", "sets") for r in load(n)[k]]
        self.assertEqual(len(all_refs), len(set(all_refs)), "client_ref reused across files")

    def test_set_rules(self):
        for name in EXPECTED:
            doc = load(name)
            types = {r["client_ref"]: r["data"]["question_type"] for r in doc["questions"]}
            for s in doc["sets"]:
                roles = Counter(c["role"] for c in s["connections"])
                self.assertEqual(len(s["connections"]), 4, s["client_ref"])
                self.assertGreaterEqual(roles["strong"], 1, s["client_ref"])
                if types[s["question_ref"]] == "single_choice":
                    self.assertEqual(roles["strong"], 1, s["client_ref"])
                else:
                    self.assertGreaterEqual(roles["strong"], 2, s["client_ref"])
                    self.assertGreaterEqual(roles["incorrect"], 1, s["client_ref"])
                for c in s["connections"]:
                    self.assertGreaterEqual(len(c["feedback"]), 40, f"{s['client_ref']}: thin feedback")
                    if c["role"] == "ambiguous":
                        self.assertTrue(c.get("notes"), f"{s['client_ref']}: ambiguous choice needs an editor note")

    def test_strong_answer_is_not_a_giveaway_by_length(self):
        for name in EXPECTED:
            doc = load(name)
            types = {r["client_ref"]: r["data"]["question_type"] for r in doc["questions"]}
            text = {r["client_ref"]: r["data"]["answer_text"] for r in doc["answers"]}
            for s in doc["sets"]:
                if types[s["question_ref"]] != "single_choice":
                    continue
                lengths = sorted(((len(text[c["answer_ref"]]), c["role"]) for c in s["connections"]), reverse=True)
                if lengths[0][1] == "strong":
                    self.assertLessEqual(lengths[0][0], 1.25 * lengths[1][0], f"{s['client_ref']}: strong answer clearly longest")

    def test_no_duplicate_text(self):
        for name in EXPECTED:
            doc = load(name)
            for kind, field in (("questions", "question_text"), ("answers", "answer_text")):
                texts = [re.sub(r"\W+", " ", r["data"][field].lower()).strip() for r in doc[kind]]
                self.assertEqual(len(texts), len(set(texts)), f"{name}: duplicate {field}")
        stems = [re.sub(r"\W+", " ", r["data"]["question_text"].lower()).strip() for n in EXPECTED for r in load(n)["questions"]]
        self.assertEqual(len(stems), len(set(stems)), "same question text in two files")

    def test_every_record_carries_vocabulary_tags_and_draft_status(self):
        for name, (_, _, _, batch) in EXPECTED.items():
            for kind, ref, meta, status, origin in all_metadata(load(name)):
                self.assertEqual(status, "draft", ref)
                self.assertEqual(origin, ORIGIN, ref)
                self.assertTrue({"builder_created", "needs_owner_review", batch, "us_citizenship"} <= set(meta["tags"]), ref)
                self.assertIn("us_citizenship", meta["topics"], ref)
                self.assertIn(meta["difficulty"], DIFFICULTIES, ref)
                self.assertEqual(meta["attributes"], {}, ref)
                self.assertTrue(set(meta["audiences"]) <= AUDIENCES, ref)
                self.assertTrue(meta["learning_objectives"], ref)
                self.assertTrue(set(meta["learning_objectives"]) <= set(OBJECTIVES), ref)
                for objective in meta["learning_objectives"]:
                    topic, tag = OBJECTIVES[objective]
                    self.assertIn(topic, meta["topics"], ref)
                    self.assertIn(tag, meta["tags"], ref)
                allowed = {"builder_created", "needs_owner_review", batch, "us_citizenship"} | {t for _, t in OBJECTIVES.values()} | FORMAT_TAGS
                self.assertTrue(set(meta["tags"]) <= allowed, f"{ref}: unknown tag")
                allowed_topics = {"us_citizenship"} | {t for t, _ in OBJECTIVES.values()}
                self.assertTrue(set(meta["topics"]) <= allowed_topics, f"{ref}: unknown topic")
                if kind in ("questions", "sets"):
                    self.assertEqual(len(set(meta["tags"]) & FORMAT_TAGS), 1, ref)

    def test_one_objective_per_set_and_answer_context_is_the_union_of_its_sets(self):
        for name in EXPECTED:
            doc = load(name)
            for s in doc["sets"]:
                self.assertEqual(len(s["metadata"]["learning_objectives"]), 1, s["client_ref"])
                self.assertEqual(len(s["metadata"]["audiences"]), 1, s["client_ref"])
            audiences = defaultdict(set)
            for s in doc["sets"]:
                for c in s["connections"]:
                    audiences[c["answer_ref"]] |= set(s["metadata"]["audiences"])
            for row in doc["answers"]:
                self.assertEqual(set(row["data"]["metadata"]["audiences"]), audiences[row["client_ref"]], row["client_ref"])


class LibraryCoverage(unittest.TestCase):
    def test_sample_shows_the_ready_ideas(self):
        doc = load(SAMPLE)
        roles = defaultdict(set)
        sets_by_question = Counter(s["question_ref"] for s in doc["sets"])
        for s in doc["sets"]:
            for c in s["connections"]:
                roles[c["answer_ref"]].add(c["role"])
        self.assertTrue(any(len(r) >= 2 for r in roles.values()), "an answer used with two different roles")
        self.assertTrue(any(n >= 2 for n in sets_by_question.values()), "a question in two sets")
        diffs = {s["metadata"]["difficulty"] for s in doc["sets"]}
        auds = {a for s in doc["sets"] for a in s["metadata"]["audiences"]}
        types = {r["data"]["question_type"] for r in doc["questions"]}
        self.assertGreaterEqual(len(diffs), 2)
        self.assertGreaterEqual(len(auds), 2)
        self.assertEqual(types, {"single_choice", "multiple_choice"})
        for s in doc["sets"]:
            for c in s["connections"]:
                self.assertTrue(c["feedback"], s["client_ref"])

    @unittest.skipUnless(MAIN, 'main batches not written yet')
    def test_all_levels_and_audiences_and_objectives_in_the_main_library(self):
        by_level = Counter()
        levels_for_objective = defaultdict(set)
        audiences = set()
        reused_questions = 0
        for name in MAIN:
            doc = load(name)
            reused_questions += sum(n > 1 for n in Counter(s["question_ref"] for s in doc["sets"]).values())
            for s in doc["sets"]:
                meta = s["metadata"]
                by_level[meta["difficulty"]] += 1
                audiences.update(meta["audiences"])
                levels_for_objective[meta["learning_objectives"][0]].add(meta["difficulty"])
        minimum = {"introductory": 9, "basic": 30, "intermediate": 20, "advanced": 15, "expert": 5}
        for level in DIFFICULTIES:
            self.assertGreaterEqual(by_level[level], minimum[level], level)
        self.assertEqual(audiences, AUDIENCES)
        for objective in OBJECTIVES:
            self.assertGreaterEqual(len(levels_for_objective[objective]), 2, objective)
        self.assertGreaterEqual(reused_questions, 5)

    @unittest.skipUnless(MAIN, 'main batches not written yet')
    def test_answer_atoms_are_genuinely_reused(self):
        uses = Counter()
        for name in MAIN:
            for s in load(name)["sets"]:
                uses.update(c["answer_ref"] for c in s["connections"])
        self.assertGreaterEqual(len([r for r, n in uses.items() if n >= 2]), 50)

    @unittest.skipUnless(MAIN, 'main batches not written yet')
    def test_some_main_library_answers_change_role_between_sets(self):
        changed = 0
        for name in MAIN:
            roles = defaultdict(set)
            for s in load(name)["sets"]:
                for c in s["connections"]:
                    roles[c["answer_ref"]].add(c["role"])
            changed += sum(len(r) > 1 for r in roles.values())
        self.assertGreaterEqual(changed, 20)

    @unittest.skipUnless(MAIN, 'main batches not written yet')
    def test_both_question_types_and_ambiguous_choices_are_present(self):
        types, roles = Counter(), Counter()
        for name in MAIN:
            doc = load(name)
            kinds = {r["client_ref"]: r["data"]["question_type"] for r in doc["questions"]}
            for s in doc["sets"]:
                types[kinds[s["question_ref"]]] += 1
                roles.update(c["role"] for c in s["connections"])
        self.assertGreaterEqual(types["multiple_choice"], 8)
        self.assertGreaterEqual(roles["ambiguous"], 8)


class LibraryThroughTheService(unittest.TestCase):
    def test_dry_run_then_real_import_in_a_throwaway_store(self):
        for name, (q, a, s, _) in EXPECTED.items():
            doc = load(name)
            service = ReadyService(MemoryStore())
            preview = service.import_content(deepcopy(doc))
            self.assertTrue(preview["is_valid"], (name, preview))
            self.assertEqual(preview["would_create"], {"questions": q, "answers": a, "sets": s}, name)
            self.assertEqual(service.list("questions")["records"], [], f"{name}: dry run wrote data")
            real = deepcopy(doc)
            real.update(dry_run=False, idempotency_key=str(uuid4()))
            done = service.import_content(real)
            self.assertTrue(done["is_valid"])
            self.assertEqual(len(done["created"]), q + a + s, name)
            self.assertEqual(len(service.list("sets", limit=100)["records"]), s, name)
            self.assertEqual({r["status"] for r in service.list("sets", limit=100)["records"]}, {"draft"})

    def test_draft_content_is_never_selected(self):
        service = ReadyService(MemoryStore())
        for name in EXPECTED:
            real = load(name)
            real.update(dry_run=False, idempotency_key=str(uuid4()))
            service.import_content(real)
        found = service.select({"target": "sets", "mode": "ordered", "count": 5})
        self.assertEqual(found["found_count"], 0)

    @unittest.skipUnless(MAIN, 'main batches not written yet')
    def test_pools_exist_once_published_in_a_throwaway_store(self):
        service = ReadyService(MemoryStore())
        for name in EXPECTED:
            real = published_copy(load(name))
            real.update(dry_run=False, idempotency_key=str(uuid4()))
            service.import_content(real)

        def pool(**criteria):
            return service.select({"target": "sets", "mode": "ordered", "count": 50, "criteria": criteria})
        self.assertGreaterEqual(pool(difficulty=["introductory"], audiences=["grades_3_5"])["found_count"], 8)
        self.assertGreaterEqual(pool(difficulty=["basic"], audiences=["grades_3_5"])["found_count"], 12)
        self.assertGreaterEqual(pool(difficulty=["basic"], audiences=["grades_6_8"])["found_count"], 10)
        self.assertGreaterEqual(pool(difficulty=["intermediate"], audiences=["grades_6_8"])["found_count"], 8)
        self.assertGreaterEqual(pool(difficulty=["intermediate"], audiences=["grades_9_12"])["found_count"], 8)
        self.assertGreaterEqual(pool(difficulty=["advanced"], audiences=["grades_9_12"])["found_count"], 5)
        self.assertGreaterEqual(pool(difficulty=["introductory"], audiences=["adult_general"])["found_count"], 3)
        self.assertGreaterEqual(pool(difficulty=["basic"], audiences=["adult_general"])["found_count"], 10)
        self.assertGreaterEqual(pool(difficulty=["advanced"], audiences=["adult_enthusiast"])["found_count"], 10)
        self.assertGreaterEqual(pool(difficulty=["expert"], audiences=["adult_enthusiast"])["found_count"], 6)
        for audience in AUDIENCES:
            self.assertGreaterEqual(pool(audiences=[audience])["found_count"], 15, audience)
        for objective in OBJECTIVES:
            self.assertGreaterEqual(pool(learning_objectives=[objective])["found_count"], 6, objective)
        # A pool shortage is reported explicitly, never padded silently.
        short = service.select({"target": "sets", "mode": "ordered", "count": 50,
                                "criteria": {"difficulty": ["expert"], "audiences": ["grades_3_5"]}})
        self.assertGreater(short["shortfall_count"], 0)
        self.assertEqual(short["requested_count"], 50)
        self.assertEqual(short["available_actions"], ["start_over", "add_more", "cancel"])
        self.assertEqual(short["found_count"] + short["shortfall_count"], 50)


if __name__ == "__main__":
    unittest.main()
