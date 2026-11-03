# PLAN-R1 report: READY AI-readiness library, batch 1 (draft)

## What I did

I wrote a draft AI-readiness library in READY's own bulk-import format: a taxonomy, a small sample batch for you to review first (8 questions, 31 answers, 9 sets), and five main batches by difficulty level (68 questions, 259 answer atoms, 80 sets). Every record is `draft`, every file is `dry_run: true`, and nothing was imported anywhere. I built a test file that checks the files against the bulk-import schema and runs them through READY's own import and selection service in a throwaway in-memory store. I then did two self-review passes, fixed a number of defects (listed in `REVIEW-NOTES.md`), and wrote coverage and review notes. All work is in `ready/` and checkpointed on `finish-now`.

## Checks run

Commands from the repo root. READY's Python dependencies (`jsonschema`, `reportlab`) were not installed on this Mac, so I installed `ready/requirements.txt` into a throwaway virtual environment outside the repo (`pip` contacted PyPI; nothing else on the network was used). `$PY` below is that environment's Python.

| Check | Baseline (before my changes) | After |
|---|---|---|
| `python3 ready/schemas/check.py` (system Python) | failed: `ModuleNotFoundError: jsonschema` | not applicable |
| `$PY ready/schemas/check.py` | `READY: 5 collections, 11 request contracts and 15 output contracts/fixtures valid.` | same line, unchanged |
| `$PY -m unittest discover -s ready/tests` | 58 tests, OK | 75 tests, OK (the same 58 plus 17 new) |
| `$PY -m unittest ready.tests.test_seed_library` | not present | 17 tests, OK |
| `node --check ready/web/main.js` | not run at baseline | passes |

Note: `ready/schemas/check.py` checks READY's own schemas, fixtures and guides. It does not read anything in `ready/seed/`. So the schema check on every library file is done inside `test_seed_library.py`, which validates each file against `ready/schemas/bulk_import.schema.json` with the same `jsonschema` validator class the checker uses. I did not modify `check.py`.

What `test_seed_library.py` asserts for every file: schema-valid; `dry_run` is true and there is no idempotency key; exact counts; at most 200 records and 256 KiB; no UUIDs, timestamps, product names, years, dollar amounts or percentages; every reference resolves and every atom is used; no `client_ref` reused, even across files; every set has four distinct choices, at least one strong (exactly one for single-choice, at least two plus one incorrect for select-all); feedback of 40+ characters on every choice and an editor's note on every ambiguous choice; no duplicate question text anywhere and no duplicate answer text inside a file; every record `draft`, with the required tags, provenance exactly as specified, and only vocabulary from `TAXONOMY.md`. Then a dry-run import and a real import in a fresh in-memory store (new idempotency key), checking nothing was written by the dry run and that the real import creates the expected counts. It also checks that draft content is never selected, and, after publishing a copy in a throwaway store, that useful pools exist (intermediate + workplace; basic + adult beginner; introductory + student; advanced + educator; expert; every objective), and that an unmeetable request (50 expert sets for students) reports a shortfall with `start_over`, `add_more`, `cancel`.

## Files added

| File | Questions | Answers | Sets |
|---|---|---|---|
| `ready/seed/library/ai_sample_01.json` | 8 | 31 | 9 |
| `ready/seed/library/ai_lib_02_introductory.json` | 15 | 58 | 17 |
| `ready/seed/library/ai_lib_03_basic.json` | 16 | 62 | 18 |
| `ready/seed/library/ai_lib_04_intermediate.json` | 16 | 60 | 19 |
| `ready/seed/library/ai_lib_05_advanced.json` | 12 | 44 | 15 |
| `ready/seed/library/ai_lib_06_expert.json` | 9 | 35 | 11 |
| Main library (02 to 06) | 68 | 259 | 80 |

Other new files: `ready/docs/library/TAXONOMY.md`, `SAMPLE-READING-GUIDE.md`, `COVERAGE.md`, `REVIEW-NOTES.md`, `ready/tests/test_seed_library.py` and this report. The largest data file is about 92 KB (limit 256 KiB). The plan file `ready/docs/plans/PLAN-R1-ai-library.md` is included in the first checkpoint. The plan's targets (about 60 questions, 150+ answers, 60+ sets) are met. Reuse is the weak point: see Content decisions.

## Checkpoints

All pushed with `./checkpoint.sh` to `finish-now`; each named only the files it created. No `--all`, no direct `git push`.

| Commit | Message (short) |
|---|---|
| `c5058b8` | R1 step 2: taxonomy and plan file |
| `bcdd229` | R1 step 3: sample batch and reading guide |
| `9d63bd2` | R1 step 3 (fix): sample answer lengths balanced |
| `8baeedf` | R1 step 4: batch 02 introductory |
| `dd260a9` | R1 step 4: batch 03 basic |
| `6cdb47e` | R1 step 4: batch 04 intermediate |
| `8c82419` | R1 step 4: batch 05 advanced |
| `a6b0015` | R1 step 4: batch 06 expert |
| `3c1b115` | R1 step 4 (revised): role-changing reuse sets added; privacy scenario softened (final data commit) |
| `86bb202` | R1 step 6: `test_seed_library.py` (final code commit) |
| `9b811b3` | R1 step 7: coverage and review notes |

The report itself is committed after these. `git diff --name-only 66096df..HEAD` lists only files under `ready/seed/library/`, `ready/docs/library/`, `ready/tests/test_seed_library.py` and the R1 plan file, plus this report's own folder. `ready/seed/ai_readiness.json` and `ready/seed/PROMPT.md` are untouched. **No Firebase command, deploy or live import was run, no credential or admin key was used, and nothing was written to the live service or Firestore.** Pushing publishes only static files with the site.

Working-tree note: at the start only `ready/docs/plans/` was untracked. During my work other untracked files appeared that I did not create and did not touch or commit: `ready/docs/plans/PLAN-R2-smoking-meat.md`, `PLAN-R3-us-geography.md`, `PLAN-R4-us-citizenship.md`, `PLAN-R5-judgment-critical-thinking.md`, `READY-LIBRARY-COMMON.md` and `ready/scripts/run_library_plans.sh`. They are still untracked and unchanged.

## Vocabulary decisions

- **Used only what the schema allows.** `difficulty` (five levels), `status` (`draft`), roles, question types and authorship kinds are closed lists. `topics`, `audiences`, `learning_objectives` and `tags` are open text lists, so there was no list to run out of. The `attributes` object is closed and empty; I left it empty.
- **Audiences:** `adult_beginner` (same value the existing seed uses), `student`, `workplace`, `educator`.
- **Learning objectives (10):** recognize_when_ai_can_help, write_a_clear_request, check_and_verify_output, protect_private_information, understand_limits_and_bias, choose_when_not_to_use_ai, connect_ai_to_recurring_work, help_others_learn_ai, take_responsibility_for_results, improve_results_by_iterating. Each has a skill-family topic and a `skill_*` tag.
- **Tags:** `builder_created`, `needs_owner_review`, a batch label `ready_lib_ai_01` to `_06`, the skill tag, and `format_scenario` / `format_concept` / `format_select_all`.
- **Proposed, not made:** because the open lists accept typos silently, a closed vocabulary (or a check in the service) for audiences, objectives and tags would be safer. A bulk "publish this import's records" action would also help (see below). I changed no schema.

## Content decisions and risks

- **Risks I am least sure of** are listed in `ready/docs/library/REVIEW-NOTES.md`: borderline ambiguous roles, a few claims about AI behavior that could age (calculators, "looks things up", capital letters), people-decision scenarios (stereotype picture, grading, ranking volunteers), level calibration, and thin audience coverage.
- **Reuse is modest.** About 20% of answer atoms (51 of 259) appear in more than one set; six change role between sets; 12 of 68 questions are placed in two or three sets. Reuse only works inside one file, because import references cannot reach another file. The same sentence therefore appears as separate atoms in a few places (three pairs across files 05 and 06).
- **The strong answer was the longest choice** in most early sets (7 of 7 in the first sample). I rebalanced; it is now the longest in about 24% of single-choice sets and listed in positions 0 to 3 about evenly. This is a check for an accidental clue, not proof that none remain.
- **Objective balance:** verification has the most sets; clear request, when-not-to-use and iterating have 4 to 5 each. Empty objective-by-level cells are listed in `COVERAGE.md`.
- **Left out on purpose:** product names, versions, prices, dates, laws, statistics; medical, legal and financial scenarios; named people; tests, attempts and anyone's results; any claim of psychometric equivalence or certification.

## Not verified

- Content correctness, difficulty levels and reading level were not reviewed by a person or measured with a tool. Only I reviewed it.
- Nothing was imported to the live service, Firestore, the emulator or the browser workshop. Import was exercised only through the in-memory store in unit tests.
- Import by HTTP: size was checked as file size (largest 92 KB), not by posting a body.
- Publishing draft records, and how a published pool behaves in the live service, were not tried. The pool checks used a published copy in a throwaway store.
- The 17 new tests are my own; they check structure and rules, not whether the teaching is right.

## Questions or surprises

- `ready/schemas/check.py` never reads the seed folder, so "run the schema checker on every library file" had no direct meaning. I used the bulk-import schema inside the new test instead. You may want the checker to cover `ready/seed/`.
- Python dependencies are not installed on this Mac. The documented setup uses a `ready/.venv`; I used a venv outside the repo instead, so as not to create files in the repo.
- A bulk import is limited to 200 records and references cannot cross files, so a 70-question library has to be several files with duplicated atoms. If you want one answer atom shared across files, that needs a design decision.
- Draft content cannot be selected, which is what we want, but publishing needs every question, answer and set flipped. There is no bulk action. The plan did not cover how you want to approve content; I did not build one.
- Other plan files (R2 to R5) and a runner script appeared untracked in the working tree during this run. I left them alone.

## Start here, Todd

1. Open `ready/docs/library/SAMPLE-READING-GUIDE.md`, then `ready/seed/library/ai_sample_01.json`. It is 8 questions and 9 sets and takes about ten minutes.
2. Tell me about the voice (too formal? too chatty?), the levels, and any scenario you dislike. I would rather fix that now than across 80 sets.
3. Then read `ready/docs/library/REVIEW-NOTES.md` for the places I am least sure of.
4. Decide: (a) whether the reuse limit inside one file is acceptable, (b) how you want to approve and publish (all at once, or by file), and (c) whether the next batches should go deeper on the thin areas: clear requests, when not to use AI, and iterating.
