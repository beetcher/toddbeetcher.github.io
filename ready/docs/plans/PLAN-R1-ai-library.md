# PLAN-R1: READY question library, batch 1 (AI readiness) — draft content for owner review

## Outcome
A catalog of original AI-readiness question atoms, answer atoms, and contextual question-answer sets, written in READY's own bulk-import format, validated by READY's own checker and service code, and delivered as DRAFT content for Todd to review. Three layers only: questions, answers, sets. **No tests, no attempts, no people** (the service builds tests later). The first deliverable is one small sample batch Todd can validate by eye before the larger batches.

## Where to work (hard rules)
- Repo: `/Users/nddev/nd/bd/toddbeetcher.github.io`, branch `finish-now`, working directly in the main checkout (as usual). No worktree, no new branch.
- Before starting, run `git status` and note any pre-existing uncommitted changes. Do not touch or commit those; name only the files this plan creates.
- This plan file itself (`ready/docs/plans/PLAN-R1-ai-library.md`) may be included in your first checkpoint.
- Allowed changes (all additive, inside the `ready/` folder only):
  - new: `ready/seed/library/**` (import JSON files)
  - new: `ready/docs/library/**` (taxonomy, coverage, review notes)
  - new: `ready/tests/test_seed_library.py`
  - new: `ready/docs/reports/PLAN-R1-report.md` (create the folder)
- Do NOT modify: existing `ready/seed/ai_readiness.json`, `ready/seed/PROMPT.md`, any schema, any service/crud/web code, any existing test, or anything outside `ready/`. If you believe a schema or vocabulary change is needed, do not make it; write it up in the report.
- Do not run `firebase` or any deploy, do not call any network service, do not use any credential or admin key, and do not import to or write to the live READY service or Firestore. Everything is local files plus the existing in-memory store used by the unit tests. This work is not recorded in Helm. The only push allowed is the repo's own `./checkpoint.sh` (see step 8).
- Every record is DRAFT: `dry_run: true` in every import file, and the safest non-published `status` value the schema allows (if a `draft` status exists, use it, so published-only selection never picks this material up before Todd approves it; if not, say so in the report and use the closest value).
- If anything is unclear or impossible, stop and write the question in the report instead of guessing.

## Read first (understand the structure before writing content)
`ready/README.md`, `ready/docs/ARCHITECTURE.md`, `ready/docs/decisions/0001-foundation.md` and `0002-runtime-and-grading.md`, `ready/docs/OPERATIONS.md` (how tests are run), `ready/schemas/{question,answer,question_answer_set,bulk_import}.guide.md` and schemas, `ready/schemas/fragments.json` (the metadata vocabulary and limits), and the existing `ready/seed/ai_readiness.json` plus `ready/seed/PROMPT.md` as the style and structure precedent. Also read the import size/byte budget limits so each file stays within them.

## Steps
1. Run `git status` and record it. Run the existing READY test suite and schema checker the documented way and record the baseline result.
2. Write `ready/docs/library/TAXONOMY.md`: the vocabulary this library will use, taken ONLY from what the schema allows today (difficulty levels, audiences, topics, learning objectives, tags). List what each difficulty level means in practice for AI readiness (what a person at that level can recognize, check, decide, or build). Define 8 to 12 learning objectives (for example recognize when AI could help, write a clear request, check and verify output, protect private information, understand limits and bias, choose when not to use AI, connect AI to real recurring work, help someone else learn). If the schema's vocabulary is a closed list that is too small, use what exists and list proposed additions in the report; do not extend the schema. Define a tag scheme: `builder_created`, `needs_owner_review`, a batch label per file (`ready_lib_ai_01`, `ready_lib_ai_02`, ...), plus tags for skill families and format.
3. Write the SAMPLE batch first: `ready/seed/library/ai_sample_01.json`. About 8 questions with 4 offered answers per set, covering at least two difficulty levels and two audiences, mixing `single_choice` and `multiple_choice`, and deliberately showing the READY ideas: (a) one answer atom reused in two different sets with different contextual roles (strong, ambiguous, incorrect), (b) the same question placed in two sets for different audiences or difficulties, (c) teaching feedback on every choice. Single-choice sets have exactly one strong answer; every set has at least one strong answer. Validate it (step 6 checks) before continuing. Write `ready/docs/library/SAMPLE-READING-GUIDE.md`: a one-page guide for Todd to review the sample quickly (what to look at, what each role means, what to change if the voice or level is wrong).
4. Write the main AI library in batches, each a separate import file, each within the byte budget: `ai_lib_02_*.json` onward, grouped sensibly (for example by difficulty or by skill family). Target about 60 question atoms, 150 or more answer atoms with genuine reuse, and 60 or more sets, spread across all difficulty levels and the audiences the schema allows, with every learning objective covered at more than one level. Include some questions that appear in several sets with different contexts so the catalog can later serve different tests. Include some scenario-style questions grounded in everyday and workplace tasks, not only definitions.
5. Content quality rules (apply to every record):
   - Original wording only; do not copy from any certification, exam bank, textbook, or website. Not an official assessment, and no psychometric-equivalence claim. Same-length does not mean same-difficulty.
   - Evergreen. Do not name specific AI products, model versions, prices, dates, laws, or statistics that go stale. Do not state anything about AI you are not confident is stable and correct.
   - Plausible distractors that reflect real misconceptions, never trick wording, never humor at the learner's expense. Exactly the right number of strong answers; use `ambiguous` only where a reasonable expert could argue either way, and explain why in the feedback.
   - Feedback on every choice that teaches (why it works, why it fails, what to try instead). Plain language, matched to the audience's reading level. No bias, no sensitive personal scenarios, no medical, legal, or financial advice scenarios that require expertise to judge.
   - Provenance: `authorship_kind` system, author "READY builder", `source_reference` "Original draft material; not an official assessment; awaiting owner review". Do not invent a human author.
   - Unique lowercase underscore `client_ref` values; no UUIDs, timestamps, people, tests, or attempts in the files.
6. Verification (build and run, record exact commands and results):
   - Run READY's schema checker on every library file.
   - Write `ready/tests/test_seed_library.py` following the pattern in `ready/tests/test_services.py` (in-memory store, `import_content` with `dry_run: True` then a second pass with `dry_run: False` and a fresh idempotency key in a throwaway store). For every library file assert: valid, expected counts, every reference resolves, every set has at least one strong answer, single-choice sets have exactly one, no duplicate question text, no duplicate answer text with conflicting meaning, every record carries the required tags and draft status.
   - Using the existing selection service on the throwaway store, check read-only that useful pools exist (for example intermediate plus workplace audience; basic plus beginner audience) and that a pool shortage is reported explicitly. Do not create tests or attempts.
   - Run the full existing READY suite again and confirm no previously passing test changed.
7. Self-review pass over all content as if you were a strict subject-matter editor and a reading-level editor: correctness, ambiguity, accidental clues (longest answer is correct, grammar clues), duplicate concepts, uneven difficulty, any item that depends on stale facts. Fix what you find. Write `ready/docs/library/REVIEW-NOTES.md` listing items you are least sure about so Todd can focus there, and `ready/docs/library/COVERAGE.md` (counts by difficulty, audience, learning objective, question type, and reuse statistics for answer atoms).
8. Checkpoint the way this repo always does: `./checkpoint.sh "message" path/one path/two ...` from the repo root, naming exactly the new files (it stages only those, commits, and pushes `finish-now`). Never use `--all`, never name files you did not create, never run `git push` directly. Checkpoint after each logical piece (taxonomy; sample batch + reading guide; each library batch; tests; docs; report) so every piece is a rollback point. After the last checkpoint confirm `git show --stat` for your commits touches only allowed paths and that anything uncommitted before you started is still uncommitted and unchanged. No Firebase deploy and no live import: pushing only publishes the static files with the site.
9. Write the report.

## Verification level: full for the new test file and the checker; the existing suite must not regress. Do not claim the content is validated, effective, or certification-grade.

## Done when
Sample batch and main batches exist and pass the checker and the new tests; the existing suite passes as before; all work is checkpointed on `finish-now` with `./checkpoint.sh`; taxonomy, sample reading guide, coverage, review notes and the report exist.

## Report format
Write `ready/docs/reports/PLAN-R1-report.md`, ending with a short "Start here, Todd" section that tells him which file to open first (the sample) and what to decide next.
- **What I did**: one short paragraph.
- **Checks run**: exact commands and results (baseline vs. after, test counts).
- **Files added**: list with counts of questions, answers, sets per file.
- **Checkpoints**: the commit hashes on `finish-now` (final code commit, not the report commit), each checkpoint message, and confirmation that no Firebase deploy or live import was done.
- **Vocabulary decisions**: what you used, and any additions you propose but did not make.
- **Content decisions and risks**: items least certain, any stale-fact risks, anything you left out on purpose.
- **Not verified**: anything you did not or could not check (including that nothing was imported to the live service). Write "nothing" only if true.
- **Questions or surprises**: anything unclear in this plan or in READY itself.
