# PLAN-R4 report: U.S. citizenship and civics study library (draft)

## What I did
Built an original, draft-only question library for U.S. citizenship and civics study practice: a taxonomy, a sample batch with a reading guide, eight main batches, a test file, coverage and review notes. Everything is `draft`, every file has `dry_run: true`, and nothing was imported anywhere. The material is not the official naturalization test, not affiliated with or endorsed by USCIS, and not legal or immigration advice; this is stated in the taxonomy, the reading guide, the review notes and every record's `origin.notes`. I could not look anything up in this run, so facts come from my own knowledge, kept to stable and widely agreed points.

## Checks run
Run from the repo root with `ready/.venv/bin/python` (the venv already existed).
- Baseline, before any content: `ready/schemas/check.py` OK (5 collections, 11 request contracts, 15 output contracts); `unittest ready.tests.test_foundation` 22 OK; `test_services` 19 OK; `test_http` 15 OK; `test_firestore_adapter` 2 OK.
- After: the same five commands give the same results (22, 19, 15, 2 tests OK, checker OK). Nothing previously passing changed.
- New: `ready/.venv/bin/python -m unittest ready.tests.test_seed_library_us_citizenship` runs 19 tests, all OK. It covers: exact file list, counts and import limits (at most 100 questions, 400 answers, 200 records and 256 KB per file), JSON-schema validity of every file, dry run in a throwaway in-memory store then a real import in a fresh store with a new idempotency key, reference resolution, no unused records, one strong answer per single-choice set and at least two (plus one incorrect) per select-all set, no duplicate question or answer text, strong answer not clearly the longest, draft status, provenance, required tags and vocabulary, no UUIDs, timestamps or stale-fact wording, a sample check for the READY ideas, minimum totals/levels/audiences/objectives, answer reuse and role changes, selection pools in a throwaway store with the files published there, and an explicit shortfall report (expert items for English learners).
- Draft content is never selected: a test imports everything as draft and confirms selection finds 0.
- No Firebase deploy, credentials or live import were used.

## Files added
Under `ready/seed/library_us_citizenship/` (questions / answers / sets):
- `us_citizenship_sample_01.json`: 8 / 27 / 10
- `us_citizenship_lib_02_principles_government.json`: 23 / 75 / 30
- `us_citizenship_lib_03_rights_responsibilities_elections.json`: 21 / 71 / 26
- `us_citizenship_lib_04_colonial_founding.json`: 10 / 38 / 15
- `us_citizenship_lib_05_nineteenth_century.json`: 12 / 50 / 15
- `us_citizenship_lib_06_modern_history.json`: 14 / 47 / 17
- `us_citizenship_lib_07_symbols_geography.json`: 20 / 61 / 25
- `us_citizenship_lib_08_reading_vocabulary.json`: 13 / 52 / 14
- `us_citizenship_lib_09_applied_and_expert.json`: 10 / 41 / 12

Main library totals (batches 02 to 09): 123 questions, 435 answers, 154 sets (plan target: about 50 / 120+ / 50+). Every set has exactly four choices.

Under `ready/docs/library_us_citizenship/`: `TAXONOMY.md`, `SAMPLE-READING-GUIDE.md`, `COVERAGE.md`, `REVIEW-NOTES.md`. Also `ready/tests/test_seed_library_us_citizenship.py` and this report.

Coverage in brief (details in COVERAGE.md): 24 introductory, 67 basic, 39 intermediate, 17 advanced, 7 expert sets; all four audiences; all 11 learning objectives at two or more levels; 15 select-all sets; 11 ambiguous choices with editor notes; 124 answer atoms used in more than one set; 28 answer atoms that change role between sets; 30 question atoms placed in several sets.

## Checkpoints
All through `./checkpoint.sh`, each naming only files I created.
- `bc0ecd0` "R4: US citizenship taxonomy"
- `d359742` "R4: US citizenship sample batch, reading guide, test scaffold"
- `8584c94` "R4: US citizenship main batch 02 (principles and government)"
- `2ab7d91` "R4: US citizenship main batch 03 (rights, responsibilities, elections)"
- `1bdc85f` "R4: US citizenship batches 02-03 fixes, batch 04 (colonial and founding)"
- `1c5c2aa` "R4: US citizenship batches 05 (1800s) and 06 (modern history)"
- `497e7db` "R4: US citizenship batches 07 (symbols, geography), 08 (reading), 09 (applied and expert), tests, taxonomy"
- `0cb2c74` "R4: US citizenship coverage and review notes" (final content commit)
- The report is committed after this one.

Two earlier checkpoints (`8584c94`, `2ab7d91`) were pushed while the new test file still had failures (aggregate targets not yet reached and some thin feedback); these were fixed in the later commits. No Firebase deploy and no live import happened.

## Vocabulary decisions
- Audiences: `naturalization_applicant`, `adult_english_learner`, `civics_teacher_or_tutor`, `general_adult_learner`, as suggested.
- Eleven learning objectives and matching topics and `skill_*` tags (listed in TAXONOMY.md). I split "system of government" into branches/powers and federalism/elections so each objective is asked at several levels. "Reading and writing practice" became one objective, `read_civic_vocabulary_in_context`, text only (no audio).
- Format tags (`format_fact`, `format_reasoning`, `format_scenario`, `format_select_all`) as in the geography library.
- Proposals not acted on: none.

## Content decisions and risks
See REVIEW-NOTES.md for the ranked list. In short: legal framing of rights, slavery and the founding, the cause of the Civil War, removal of Native nations, causes of the Great Depression, judicial review and the republic-or-democracy wording are the items I am least sure about. Left out on purpose: anything that depends on a current officeholder, party control, recent laws or rulings, state-specific facts, and contested names. Stable numbers (fifty states, term lengths, the two-election limit) are used and flagged as law or custom that could change. **Check the current official USCIS civics test materials before using this for real applicants.**

## Not verified
- Facts were not checked against any outside source (no browsing). Every historical and constitutional statement needs a subject-matter read.
- English-learner reading level was judged by me only, not by a reading-level tool or an ESL teacher.
- Nothing was shown in the READY management interface; I only ran the service-level import in a throwaway in-memory store.
- Firestore behavior (emulator or live) was not exercised.
- I did not confirm what the current official test covers.

## Questions or surprises
- The bulk-import budget (about 200 records per file in the earlier library's tests) shaped the split into eight files; answer reuse can only happen inside one file.
- Writing short answers (names, one-word choices) made the "strong answer is not clearly the longest" rule awkward; I handled it by choosing distractors of similar length or adding a longer-named distractor.

## Start here, Todd
Open `ready/seed/library_us_citizenship/us_citizenship_sample_01.json`, with `ready/docs/library_us_citizenship/SAMPLE-READING-GUIDE.md` beside it. Decide: (1) is the voice right for English learners and for tutors; (2) the ambiguous choices and role choices flagged in `REVIEW-NOTES.md`; (3) whether to have the main files read by a civics or history subject-matter reviewer before anything is published; (4) whether to ask for more advanced and expert items, which are the thinnest part.
