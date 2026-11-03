# PLAN-R3 report: U.S. geography draft library

## What I did
Built a draft U.S. geography library for READY in the bulk-import format: a taxonomy, a sample batch with a one-page reading guide, five main batches (one per age band), a test file, coverage figures and review notes. The main batches hold 102 question atoms, 315 answer atoms and 109 sets across five age bands (grades 3 to 5, 6 to 8, 9 to 12, general adult, adult enthusiast) and all five difficulty levels. Everything is `draft`. Nothing was imported to the live service, and nothing was deployed. The plan asked for about 50 questions; I ended up with about twice that (see "Content decisions and risks").

## Checks run
All from the repo root with `ready/.venv/bin/python` (the venv already existed).

| Check | Baseline (before my files) | After |
|---|---|---|
| `ready/schemas/check.py` | OK: 5 collections, 11 request contracts and 15 output contracts/fixtures valid | same |
| `python -m unittest ready.tests.test_foundation ready.tests.test_services ready.tests.test_http ready.tests.test_firestore_adapter` | 58 tests, OK (22 + 19 + 15 + 2) | 58 tests, OK (unchanged) |
| `python -m unittest ready.tests.test_seed_library_us_geography` | n/a | 19 tests, OK |
| Schema validation of each import file (Draft 2020-12 validator, format checker, an ad hoc script outside the repo) | n/a | all six files: no errors |

The new test file follows `test_services.py`: in-memory store, `import_content` with `dry_run: True`, then in a fresh throwaway store with `dry_run: False` and a fresh idempotency key. For every file it asserts schema validity, counts, resolved references, no unused atoms, at least one strong answer per set (exactly one for single choice), no duplicate question or answer text, required tags, draft status, provenance, allowed topics/audiences/objectives/tags, no UUID-like strings or timestamps, no stale-risk wording, a thin-feedback check and a "strong answer is not clearly the longest" check. It also checks read-only selection pools on the throwaway store, with the sets published only in that copy: audience by level pools exist for each band, each objective has at least 6 sets, and an explicit shortage is reported for expert sets in grades 3 to 5. No tests, attempts or people were created.

## Files added
Seed files in `ready/seed/library_us_geography/` (questions / answers / sets):

| File | Q | A | S |
|---|---|---|---|
| `us_geography_sample_01.json` | 8 | 33 | 10 |
| `us_geography_lib_02_grades_3_5.json` | 24 | 60 | 24 |
| `us_geography_lib_03_grades_6_8.json` | 23 | 80 | 26 |
| `us_geography_lib_04_grades_9_12.json` | 17 | 62 | 19 |
| `us_geography_lib_05_adult_general.json` | 21 | 64 | 23 |
| `us_geography_lib_06_adult_enthusiast.json` | 17 | 49 | 17 |
| Main total (02 to 06) | 102 | 315 | 109 |

Docs in `ready/docs/library_us_geography/`: `TAXONOMY.md`, `SAMPLE-READING-GUIDE.md`, `COVERAGE.md`, `REVIEW-NOTES.md`. Test: `ready/tests/test_seed_library_us_geography.py`. This report.

Reuse figures (main files): 71 of 315 answer atoms are offered in two or more sets (33 in three or more); 38 atoms change role between sets; 7 questions are placed in two sets (different bands or levels). Reuse happens inside each file only, since an import resolves references within its own file.

## Checkpoints
All pushed with `./checkpoint.sh` naming only my files. Final content commit is the last one that touched a seed file, `9c31866`.

- `ad65b09` R3: US geography taxonomy
- `2e83a6a` R3: US geography sample batch, reading guide, test scaffold
- `99d756f` R3: US geography main batch 02 (grades 3-5)
- `48665c4` R3: US geography main batch 03 (grades 6-8)
- `a3ca63a` R3: US geography main batch 04 (grades 9-12)
- `49ba6ed` R3: US geography main batch 05 (adult general). This commit had a few thin-feedback lines that I fixed in the next checkpoint.
- `9c31866` R3: US geography cluster additions, batch 06 (adult enthusiast), tests. Final content commit.
- `bf7ccca` R3: US geography coverage and review notes
- The commit for this report follows.

No Firebase command was run, no deploy, no credential or admin key used, and no import into the live service or Firestore.

## Vocabulary decisions
- Audiences: the five from the plan, unchanged. The audience carries the age band; `difficulty` is relative to the band.
- Subtopics: the plan's list became ten topic families (states and capitals; regions and borders merged; physical features; map skills; time zones; climate and biomes; territories and D.C.; parks and landmarks; human geography; everyday geography). Each maps one-to-one to a learning objective.
- Tags: `builder_created`, `needs_owner_review`, `ready_lib_us_geography_NN`, `us_geography`, `skill_*`, and a `format_*` tag on questions and sets.
- Regions use the Census Bureau's four regions, named in every region question. Other labels (Southwest, Mid-Atlantic) are marked `ambiguous` or `incorrect` according to what the stem asks.
- Proposals not acted on: a separate `age_band` tag (the `audiences` field already carries it); a `region_convention` tag to separate Census questions from cultural ones.

## Content decisions and risks
- Size: 102 questions and 109 sets, about double the plan, because I added sets that share answer choices to get real reuse and role changes. This raises your review load. The easiest cut is described in REVIEW-NOTES section 7.
- Evergreen: no populations, city rankings, prices, dates, years or officeholders. Stable superlatives only (largest state by land area, largest and wholly-US Great Lakes, lowest point, highest point in the 48 states).
- I left out, on purpose, the current official names of the highest peak in North America and of the gulf south of the Gulf Coast states, because those names have been changed by order more than once. I also left out the longest river because sources disagree.
- Least certain: time-zone boundaries (Texas, Florida Panhandle, Idaho Panhandle, Arizona daylight saving), place-name origins (Boise, Colorado), the Mississippi meaning (popular versus scholarly), territory legal terms ("commonwealth", "unincorporated"), and the Census region assignments. All listed in REVIEW-NOTES.
- Only 8 `ambiguous` choices, because I used it only where a respected usage exists.
- Grades 6 to 8 and 9 to 12 have no introductory sets; expert sets are enthusiast only; general adult has only 2 advanced sets.

## Not verified
- Facts were not checked against an outside source; they come from my own knowledge and were limited to well-established ones.
- Reading level was matched by hand, not measured.
- Correct-answer position balance across the library was not measured. Position is shuffled per set by a fixed rule.
- I did not run the browser check script or any live import preview; both are outside the allowed scope.
- The Firestore adapter was not exercised with these files (no emulator, by design).

## Questions or surprises
- `service.list` returns 25 records by default. My first run of the throwaway-store test failed for a file with 26 sets until I passed `limit=100`. This is a test detail, not a data problem.
- The per-file budget of 200 records (questions plus answers plus sets) was well within limits in every file (the largest is 129).
- Some of my generated source lived outside the repo (a small Python script that emits the JSON). It is not part of the deliverable; the JSON files are the source of truth from here on.

## Start here, Todd
Open `ready/seed/library_us_geography/us_geography_sample_01.json` with `ready/docs/library_us_geography/SAMPLE-READING-GUIDE.md` beside it. Then read `REVIEW-NOTES.md`. Decide: (1) is the voice right for each age band, and is the difficulty relative to the band what you want; (2) do you want the main library trimmed from 102 questions to about 50, or kept; (3) are you comfortable leaving out the contested names (Section 1 of the notes); (4) should grades 6 to 8 and grades 9 to 12 get introductory sets, and should general adult get more advanced ones.
