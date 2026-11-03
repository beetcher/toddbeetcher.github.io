# PLAN-R5 report: judgment and critical thinking library (draft)

## What I did
Wrote a draft library of situational judgment items in READY's bulk-import format: a design note and taxonomy first, then an 8-question sample, then seven main batches (68 questions, 280 answers, 81 sets) covering twelve skill families at five difficulty levels and five audiences. Everything is `draft`, `dry_run: true`, nothing was imported anywhere. Roles carry the nuance: `strong` is the most defensible response, `ambiguous` a reasonable one with a named cost (every one has an editor note), `incorrect` clearly worse. This is practice and discussion material, not a validated instrument.

## Checks run
Run from the repo root with `ready/.venv/bin/python` (venv already existed).
- Baseline before my files: `ready/schemas/check.py` OK ("5 collections, 11 request contracts and 15 output contracts/fixtures valid"); `-m unittest ready.tests.test_foundation` 22 OK; `test_services` 19 OK; `test_http` 15 OK; `test_firestore_adapter` 2 OK.
- After: same schema check OK; the same four files pass with the same counts (22, 19, 15, 2); `ready.tests.test_seed_library_judgment` 21 tests OK; all five together: 79 tests OK.
- Each of the 8 seed files validated against `bulk_import.schema.json` with 0 errors; largest file about 79 KB.
- The new test imports every file with `dry_run: True` then `False` into throwaway in-memory stores, checks counts, references, strong-answer rules, no duplicate text, tags, draft status, no UUIDs or timestamps, no stale or off-limits words, strong answer never more than 1.25 times the next longest, and that draft content is never selected. After publishing a copy in a throwaway store it checks the selection pools by audience, level, skill tag and `move_ask_or_delay` tag, and that a shortage (for example expert for teens) is reported explicitly with a shortfall count.

## Files added
Seed (`ready/seed/library_judgment/`), questions / answers / sets:
- `judgment_sample_01.json` 8 / 34 / 10
- `judgment_lib_02_evidence_claims.json` 10 / 41 / 13
- `judgment_lib_03_cause_probability.json` 10 / 42 / 13
- `judgment_lib_04_errors_biases.json` 10 / 40 / 11
- `judgment_lib_05_uncertainty_tradeoffs.json` 9 / 38 / 11
- `judgment_lib_06_ethics_questions.json` 10 / 41 / 11
- `judgment_lib_07_updating_ai.json` 10 / 40 / 11
- `judgment_lib_08_choose_two_and_more.json` 9 / 38 / 11
Docs (`ready/docs/library_judgment/`): `JUDGMENT-DESIGN.md`, `TAXONOMY.md`, `SAMPLE-READING-GUIDE.md`, `COVERAGE.md`, `REVIEW-NOTES.md`. Test: `ready/tests/test_seed_library_judgment.py`. This report.

## Checkpoints
All via `./checkpoint.sh` with named files only. No Firebase deploy, no live import, no credential used.
- `bd65596` design note and taxonomy
- `ca82289` sample, reading guide, first test file
- `3e7a947` batch 02
- `09ecbb3` batches 03 and 04
- `a6bdbd2` batches 05 to 08 and the complete test file
- `9652603` coverage, review notes, one feedback fix (final content commit)
- A last commit adds the review-notes wording fix and this report.

## Vocabulary decisions
Topics: `judgment` plus 12 subtopics (one per objective). Audiences: the five suggested. Tags: skill (`skill_*`), format (`format_scenario`, `format_choose_two`), `move_ask_or_delay`, and the required builder and batch tags. Planned `scenario_*` tags were not needed (no shared scenario got a tag); shared scenarios are simply the same question in several sets. No proposals left unacted except labelling the classic reasoning-error names (see REVIEW-NOTES).

## Content decisions and risks
- Least sure items are listed in REVIEW-NOTES.md (confidences, rounding figures, forecast pair, expansion lease).
- Difficulty is my judgment of ambiguity; expert items may be mislabelled by a level.
- Invented numbers only; no dates, people, prices or events. Two workplace-honesty items assume widely held but not universal norms.
- Left out on purpose: political, religious, health and family scenarios; anything needing images or links.
- Answer reuse is modest: 41 of 280 answer atoms appear in more than one set and 10 change role between sets. 13 questions are placed in several sets. Judgment answers are tied to scenarios, and a bulk file can only reuse atoms within itself.
- Pools are thin for college at intermediate and advanced, teen above introductory, manager at basic, adult at introductory and expert, and early career at expert (COVERAGE.md).

## Not verified
- No human subject-matter or reading-level review beyond my own read-through; reading level was judged by eye, not by a formula.
- No browser or live-service import; the Firestore adapter path was not exercised with these files.
- Whether real learners find the strong choices uncontroversial is untested.
- The sandbox did not check that the unrelated, untracked work of other plans is unaffected beyond `git status` showing only my files.

## Questions or surprises
- The common file says "about 50 questions, 120+ answers, 50+ sets"; I exceeded all three, but answer reuse is lower than a fact library would give.
- The sample uses 34 answers for 8 questions (more than a fully 4-per-set design) because shared questions carry different distractors.

## Start here, Todd
Open `ready/docs/library_judgment/SAMPLE-READING-GUIDE.md`, then `ready/seed/library_judgment/judgment_sample_01.json`. Decide: (1) is the voice and the `ambiguous` treatment what you want; (2) should the thin pools (managers at basic, college above basic, teens above introductory) be filled next; (3) then read REVIEW-NOTES.md and flip any `strong` you would argue with.
