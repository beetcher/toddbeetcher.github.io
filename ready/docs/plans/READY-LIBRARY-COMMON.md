# READY library plans: shared standard (applies in full to PLAN-R2, R3, R4, R5)

Each category plan says WHAT to build. This file says HOW, and what is forbidden. Read this file first, then the category plan. PLAN-R1 (AI readiness) is a separate plan that may be running at the same time; do not touch its files.

## What this builds
Draft question atoms, answer atoms and contextual question-answer sets in READY's bulk-import format, for one category. **No tests, no attempts, no people.** Nothing is imported into the live READY service. Everything is DRAFT for Todd's review.

## Where to work
- Repo: `/Users/nddev/nd/bd/toddbeetcher.github.io`, branch `finish-now`, working directly in the main checkout. No worktree, no new branch.
- Allowed changes (all new files, inside `ready/` only; `<cat>` is the category slug given in your plan):
  - `ready/seed/library_<cat>/**` (import JSON files)
  - `ready/docs/library_<cat>/**` (taxonomy, coverage, review notes, design notes)
  - `ready/tests/test_seed_library_<cat>.py`
  - `ready/docs/reports/PLAN-<id>-report.md`
  - your own plan file in `ready/docs/plans/`
- Do NOT modify: any existing file, `ready/seed/ai_readiness.json`, `ready/seed/library/**` (belongs to PLAN-R1), any other category's folders, schemas, services, web code, existing tests.
- Do not run `firebase` or any deploy, do not use any credential or admin key, do not import to or write to the live READY service or Firestore. This work is not recorded in Helm.
- Other workers may be running in the same checkout right now on other categories. Rules: only create/edit files in your own folders; run `git status` before starting and leave anything not yours alone; if a git or checkpoint command fails on a lock file or a rejected push, wait 30 seconds and retry up to 5 times; never delete lock files; never run `git pull`, `git rebase`, `git reset`, `git stash`, or `git checkout` on shared files.
- If anything is unclear or impossible, stop and write the question in the report instead of guessing.

## Setup and checks
- READY's Python environment: use `ready/.venv` if it exists. If not, create it exactly as `ready/docs/OPERATIONS.md` says (`python3 -m venv ready/.venv` then `ready/.venv/bin/python -m pip install -r ready/requirements.txt`); that install is approved. If another worker is creating it, wait 60 seconds and check again before creating it yourself. `ready/.venv/` is git-ignored.
- Baseline: run only the pre-existing tests (`test_foundation`, `test_services`, `test_http`, `test_firestore_adapter`) plus the schema checker (`ready/schemas/check.py`) with `ready/.venv/bin/python`, from the repo root, the way OPERATIONS.md shows. Record results. Other workers' new test files may be incomplete while you run; ignore them.
- Read before writing content: `ready/README.md`, `ready/docs/ARCHITECTURE.md`, `ready/docs/decisions/0001-foundation.md`, `0002-runtime-and-grading.md`, `ready/schemas/{question,answer,question_answer_set,bulk_import}.guide.md` and schemas, `ready/schemas/fragments.json`, and the precedent `ready/seed/ai_readiness.json` with `ready/seed/PROMPT.md`.

## Facts about the schema (verified; do not extend them)
- `difficulty` is one of: introductory, basic, intermediate, advanced, expert.
- `topics`, `audiences`, `learning_objectives`, `tags` are free text (lowercase with underscores recommended, as in the precedent). Limits: up to 30 topics/audiences/objectives and 50 tags per record. `metadata.attributes` must stay `{}`.
- Set `status` is draft / published / retired. **Use `draft` for everything**, so published-only selection never picks this material up before Todd approves it.
- Connection roles are `strong`, `ambiguous`, `incorrect`, and they live on the set's connections, never on answer atoms. A set has 2 to 20 connections. Each single-choice set has exactly one strong answer; every set has at least one strong answer.
- Question types: `single_choice`, `multiple_choice`.
- Import limits per file: at most 100 questions and 400 answers, plus the set and byte budgets you will find in the schema and ARCHITECTURE. Split into several files when needed.
- Identifiers in files are `client_ref` values: unique, lowercase, underscores, starting with a letter. No UUIDs, timestamps, people, tests or attempts in the files. Every file has `dry_run: true`.
- Provenance on every record: `authorship_kind` "system", author "READY builder", `source_reference` "Original draft material; not an official assessment; awaiting owner review". Do not invent a human author.
- Tags on every record: `builder_created`, `needs_owner_review`, and a batch label `ready_lib_<cat>_NN` per file.

## Build order
1. TAXONOMY first (`ready/docs/library_<cat>/TAXONOMY.md`): subtopics, audiences, what each difficulty level means in this category, learning objectives (8 to 12), tag scheme.
2. SAMPLE batch next (`ready/seed/library_<cat>/<cat>_sample_01.json`): about 8 questions with 4 offered answers per set. It must deliberately show READY's ideas: (a) one answer atom reused in two sets with different contextual roles, (b) one question placed in two sets for different audiences or levels, (c) both question types, (d) at least two difficulty levels, (e) teaching feedback on every choice. Then write `SAMPLE-READING-GUIDE.md` (one page: what to look at, what each role means, what to change if voice or level is wrong). Run the checks on the sample and checkpoint it BEFORE writing the rest.
3. MAIN batches (`<cat>_lib_02_*.json` onward): about 50 question atoms, 120 or more answer atoms with genuine reuse, and 50 or more sets, spread across all five difficulty levels and the category's audiences, every learning objective covered at more than one level. Include some questions placed in several sets with different contexts.
4. Verification, self-review, coverage, review notes, report (below).

## Content quality rules (every record)
- Original wording only. Do not copy from any exam bank, certification, textbook, website or published instrument. Not an official assessment; no psychometric-equivalence claim. Same length does not mean same difficulty.
- Evergreen. No current officeholders, prices, rankings, statistics, dates or recent events that go stale. Do not state anything you are not confident is stable and correct. Where experts or traditions legitimately differ, use role `ambiguous` and say why in the feedback.
- Plausible distractors that reflect real misconceptions. No trick wording, no humor at the learner's expense, no accidental clues (the longest option correct, grammar giveaways, always-correct "all of the above").
- Feedback on every choice teaches: why it works, why it fails, what to try instead. Plain language matched to the audience's reading level.
- Respectful, unbiased, no sensitive personal scenarios.
- Text only: no questions that need an image, map, audio or link.

## Verification (build and run; record exact commands and results)
- Run READY's schema checker on every file in your folder.
- Write `ready/tests/test_seed_library_<cat>.py` following `ready/tests/test_services.py` (in-memory store; `import_content` with `dry_run: True`, then in a fresh throwaway store with `dry_run: False` and a fresh idempotency key). For every file assert: valid, expected counts, all references resolve, every set has at least one strong answer, single-choice sets have exactly one, no duplicate question text, required tags and draft status on every record, no UUID-like strings or timestamps in the files.
- With the existing selection service on the throwaway store, check read-only that useful pools exist for your category's audiences and levels, and that a shortage is reported explicitly. Do not create tests or attempts.
- Run the new test file plus the pre-existing tests again and confirm nothing previously passing changed.

## Self-review (as a strict subject-matter editor and a reading-level editor)
Correctness, ambiguity, accidental clues, duplicate concepts, uneven difficulty, stale facts, anything outside your confidence. Fix what you find. Write `ready/docs/library_<cat>/REVIEW-NOTES.md` listing the items you are least sure about so Todd can focus there, and `COVERAGE.md` (counts by difficulty, audience, learning objective, subtopic, question type, and answer-atom reuse statistics).

## Checkpointing (the way this repo always does it)
Use `./checkpoint.sh "message" path/one path/two ...` from the repo root, naming exactly the files you created (it stages only those, commits and pushes `finish-now`). Never use `--all`, never name files you did not create, never run `git push` or `git commit` directly. Checkpoint after each logical piece (taxonomy; sample + reading guide; each main batch; tests; docs; report). After the last checkpoint confirm with `git show --stat` that your commits touch only allowed paths. Pushing only publishes the static files with the site; there is no Firebase deploy and no live import.

## Report
Write `ready/docs/reports/PLAN-<id>-report.md`, ending with a short "Start here, Todd" section that names the first file to open (the sample) and what to decide next.
- **What I did**: one short paragraph.
- **Checks run**: exact commands and results (baseline vs. after, test counts).
- **Files added**: list with counts of questions, answers and sets per file.
- **Checkpoints**: commit hashes (final content commit, not the report commit) and each checkpoint message; confirm no Firebase deploy or live import.
- **Vocabulary decisions**: what you used, and any proposals you did not act on.
- **Content decisions and risks**: items least certain, stale-fact risks, anything left out on purpose.
- **Not verified**: anything you did not or could not check. Write "nothing" only if true.
- **Questions or surprises**.

Do not claim the content is validated, effective, or certification-grade.
