# PLAN-R2 report: READY smoking-meat library (draft)

## What I did
Built a draft skill-ladder library for smoking meat at home, from a first cook to an experienced pitmaster, in READY's bulk-import format: a taxonomy, a 9-question sample batch with a reading guide, five main batches by difficulty (introductory to expert), a test file, coverage, and review notes. In total there are 74 questions, 289 answers and 88 sets (sample and main together), all `draft`, all `dry_run: true`. Nothing was imported to READY or Firestore. I wrote the content as compact Python source in `/tmp` and compiled it to JSON; that generator is not in the repo (it is only a means to produce the files). After the first full build, a self-review found that the strong answer was clearly the longest option in 41 single-choice sets, and that the library had too few select-all sets and too little reuse. I fixed all three and added a test for the length problem.

## Checks run
All from the repo root with `ready/.venv/bin/python` (I created `ready/.venv` as OPERATIONS.md describes; the install is approved and the folder is git-ignored).

| Check | Baseline (before my files) | After |
|---|---|---|
| `-m unittest ready.tests.test_foundation` | 22 OK | 22 OK |
| `-m unittest ready.tests.test_services` | 19 OK | 19 OK |
| `-m unittest ready.tests.test_http` | 15 OK | 15 OK |
| `-m unittest ready.tests.test_firestore_adapter` | 2 OK | 2 OK |
| `ready/schemas/check.py` | "5 collections, 11 request contracts and 15 output contracts/fixtures valid" | same |
| `-m unittest ready.tests.test_seed_library_smoking_meat` | n/a | 19 OK |

Note: `ready/schemas/check.py` validates the schema registry and its fixtures; it does not read the seed folders. The seed files are checked against `bulk_import.schema.json` by the new test file (Draft 2020-12 validator with format checking) and by READY's own `import_content` dry run, which I also ran on each file during the build.

The new test file checks, for every file: schema-valid and `dry_run` true; expected counts; all references resolve and no unused atoms; every set has 4 offered answers, at least one strong, exactly one for single-choice, at least two strong and one incorrect for select-all, feedback of 40 or more characters on every choice, a note on every ambiguous choice; no duplicate question or answer text; required tags, draft status and provenance on every record; no UUID-like strings, timestamps, brand names, prices or percentages; and that the strong answer is not more than 1.25 times as long as the next-longest option. It also runs `import_content` as a dry run and then for real in a fresh in-memory store with a fresh idempotency key, checks that draft content is never selected, and (with a published copy in the throwaway store) that useful pools exist for the audiences and levels and that a shortage is reported explicitly. No tests, attempts or people were created.

## Files added
Questions / answers / sets per file.

| File | Q | A | S |
|---|---|---|---|
| `ready/seed/library_smoking_meat/smoking_meat_sample_01.json` | 9 | 36 | 10 |
| `ready/seed/library_smoking_meat/smoking_meat_lib_02_introductory.json` | 15 | 57 | 17 |
| `ready/seed/library_smoking_meat/smoking_meat_lib_03_basic.json` | 15 | 56 | 18 |
| `ready/seed/library_smoking_meat/smoking_meat_lib_04_intermediate.json` | 16 | 60 | 17 |
| `ready/seed/library_smoking_meat/smoking_meat_lib_05_advanced.json` | 11 | 46 | 14 |
| `ready/seed/library_smoking_meat/smoking_meat_lib_06_expert.json` | 8 | 34 | 12 |
| Total main (02 to 06) | 65 | 253 | 78 |

Docs and tests: `ready/docs/library_smoking_meat/{TAXONOMY,SAMPLE-READING-GUIDE,COVERAGE,REVIEW-NOTES}.md`, `ready/tests/test_seed_library_smoking_meat.py`, and this report.

Main-library headline numbers (details in COVERAGE.md): 17/18/17/14/12 sets at introductory/basic/intermediate/advanced/expert; 22 beginner, 27 enthusiast, 14 host, 15 competitor-or-caterer sets; 67 single-choice and 11 select-all sets; 89 strong, 30 ambiguous, 193 incorrect offered choices; 13 questions placed in more than one set; 58 of 253 answer atoms reused, 6 carrying different roles in different sets.

## Checkpoints
All pushed to `finish-now` with `./checkpoint.sh`, naming only my files. Final content commit: **df26d12**.
- 6d2f130 R2: smoking meat taxonomy
- 287acd0 R2: smoking meat sample batch and reading guide
- a06224a R2: smoking meat main batches 02 (introductory) and 03 (basic)
- e8fd857 R2: smoking meat main batch 04 (intermediate)
- 04fbf49 R2: smoking meat main batch 05 (advanced)
- eb2d3a9 R2: smoking meat main batch 06 (expert)
- 6cbad4c R2: smoking meat self-review pass (option lengths, select-all sets, reuse) and test file
- df26d12 R2: smoking meat coverage and review notes, wording fixes
- The report was checkpointed after this one (see `git log`).

No Firebase command or deploy, no credential or admin key, and no live import or Firestore write was used. This work is not recorded in Helm. I did not use any other category's folders, `ready/seed/library/**`, or any existing file.

## Vocabulary decisions
- Used the four suggested audiences unchanged (`hobbyist_beginner`, `home_enthusiast`, `backyard_host_for_a_crowd`, `aspiring_competitor_or_caterer`).
- Merged the plan's twelve subtopics into ten topic values (one per learning objective) and gave each a skill tag, following the AI-readiness precedent. TAXONOMY.md lists the mapping.
- Ten learning objectives; each set has exactly one objective and one audience.
- Proposals not acted on: a schema field for "equipment type" (for example offset or pellet) would let a pool filter by cooker; it would need a schema change, so I only used tags and topics.

## Content decisions and risks
See REVIEW-NOTES.md for the full list. In short:
- Food-safety numbers (danger zone and two-hour rule, 165/160/145°F minimums, 165°F reheat, 140°F hot-holding, ice-water test) are from memory of widely published US guidance and were not looked up. They need one check against the current official source before publishing. I framed one question (unknown time in the danger zone) conservatively: discard.
- 35 ambiguous choices, each with an editor note, mark real disagreement (wrap material, hot-and-fast, spritzing, trimming, baffles, wood blends, chilling-and-reheating versus hot holding, and similar). A few technique answers I committed to as strong or incorrect are listed there.
- Still weak: in 44 of 76 single-choice sets the strong answer is the longest option, though never clearly so (the test limit is 1.25 times). Expect a length-balancing pass if this goes forward.
- Left out on purpose: curing quantities, canning, brands, prices, images, cooking-time tables.

## Not verified
- None of the food-safety facts were checked against a source during this run (see above).
- No human subject-matter expert, and no reading-level tool, reviewed the text. The reading-level and subject-matter review was my own pass.
- Nothing was shown in READY's management interface; I did not run the browser checks.
- Content was only tested in a throwaway in-memory store. Firestore behavior of these files was not exercised.
- Whether the select-all questions grade as intended under READY's grading policy was not checked beyond import and selection.

## Questions or surprises
- The plan and common standard ask to "run the schema checker on every file", but `ready/schemas/check.py` does not read seed folders. I used the bulk-import schema and the import dry run instead, as described above.
- Because an import file must resolve its own references, answer reuse can only happen inside a file. I split the main library by difficulty (as PLAN-R1 did), so reuse is strongest between sets at the same level.
- `ready/seed/library/**` (R1) was present in the checkout and complete when I started; I only read its test file and one sample file as a pattern and changed nothing there.

## Start here, Todd
Open `ready/docs/library_smoking_meat/SAMPLE-READING-GUIDE.md`, then `ready/seed/library_smoking_meat/smoking_meat_sample_01.json` (9 questions, 10 sets). Decide first: does the voice and difficulty feel right, and are the stall and wrapping questions marked "ambiguous" in the way you want? Then read REVIEW-NOTES.md section 1 (food-safety numbers to check) and section 2 (technique calls). If the sample works, the five main files follow the same pattern and can be reviewed by level.
