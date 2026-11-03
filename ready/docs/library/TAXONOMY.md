# READY AI-readiness library: taxonomy (draft for owner review)

This is the vocabulary the AI library (plan R1) uses. Everything here is taken from what the READY schema allows today. Nothing in the schema was changed.

## What the schema fixes and what it leaves open

| Field | Schema rule | Used here |
|---|---|---|
| `difficulty` | Closed list: introductory, basic, intermediate, advanced, expert. One value per record. | All five |
| `status` | Closed list: draft, published, retired | `draft` only |
| connection `role` | Closed list: strong, ambiguous, incorrect | All three |
| `question_type` | Closed list: single_choice, multiple_choice | Both |
| `origin.authorship_kind` | Closed list: human, system, mixed | `system` |
| `topics`, `audiences`, `learning_objectives`, `tags` | Open lists of lowercase-style strings (up to 30, 30, 30 and 50 items) | Defined below |
| `attributes` | Closed and empty: no extra typed dimensions | Not used |

Because the four open lists accept any text, a typo creates a new value silently. The tests in `ready/tests/test_seed_library.py` check every value in the library against the lists on this page.

## Difficulty levels for AI readiness

Difficulty describes the thinking asked of the learner, not the length of the text. Same length does not mean same difficulty.

| Level | A person at this level can... |
|---|---|
| introductory | Say what AI tools are for in everyday life. Notice that an output needs a look before use. Make a one-step, common-sense choice. Plain words, no jargon. |
| basic | Write a specific request with a goal and some context. Keep obviously private details out of a request. Check one fact against a better source. Follow a simple rule in an ordinary task. |
| intermediate | Weigh two reasonable options in a realistic workplace, study or teaching scene. Pick a fitting way to verify. Improve a weak first result by changing the request. Recognise common limits and unfairness patterns. Decide whether AI fits a task at all. |
| advanced | Design a repeatable routine, combine several checks, and handle competing constraints (time, privacy, quality). Anticipate how a process could fail. Set simple team habits and explain the reasons to others. |
| expert | Judge a whole process or practice: where oversight belongs, which risks matter most, how small errors compound, how to detect over-reliance, and how to lead others toward careful use. |

## Audiences

| Value | Meaning |
|---|---|
| `adult_beginner` | An adult new to AI tools, with everyday tasks (home, community, errands). Plainest wording. (Same value the existing seed uses.) |
| `student` | A learner using AI for study or school-style tasks. |
| `workplace` | A person at work: office, field or service tasks, working with coworkers and managers. |
| `educator` | A teacher, trainer or team lead who guides other people in using AI. |

## Topics

Every record carries `ai_readiness`. Each also carries one skill-family topic, the one matching its learning objective.

## Learning objectives (10)

Each objective is a stable `snake_case` value. Skill-family topic and tag are given in the same row.

| # | Objective value | In plain words | Topic | Tag |
|---|---|---|---|---|
| 1 | `recognize_when_ai_can_help` | Spot tasks where AI is a good helper | `ai_opportunities` | `skill_opportunity` |
| 2 | `write_a_clear_request` | Say what you want, with goal, context and shape | `ai_prompting` | `skill_prompting` |
| 3 | `check_and_verify_output` | Check AI output before relying on it | `ai_verification` | `skill_verification` |
| 4 | `protect_private_information` | Keep private and sensitive details safe | `ai_privacy` | `skill_privacy` |
| 5 | `understand_limits_and_bias` | Know what AI gets wrong and who it can treat unfairly | `ai_limits_and_bias` | `skill_limits` |
| 6 | `choose_when_not_to_use_ai` | Decide when a person, not AI, should do the work | `ai_judgment` | `skill_judgment` |
| 7 | `connect_ai_to_recurring_work` | Build safe, repeatable routines for regular tasks | `ai_workflow` | `skill_workflow` |
| 8 | `help_others_learn_ai` | Explain, model and coach careful use | `ai_teaching` | `skill_teaching` |
| 9 | `take_responsibility_for_results` | Own what you share, send or decide | `ai_accountability` | `skill_accountability` |
| 10 | `improve_results_by_iterating` | Refine a request or result step by step | `ai_iteration` | `skill_iteration` |

The older seed uses a single objective, `recognize_and_check_ai_use`. This library does not reuse it, because objectives 1 and 3 above separate its two halves.

## Tag scheme

Every question, answer and set in the library carries these tags.

| Tag | Meaning |
|---|---|
| `builder_created` | Written by the READY builder (same tag as the existing seed) |
| `needs_owner_review` | Draft: not yet read by Todd. Remove when approved. |
| `ready_lib_ai_NN` | Batch label, one per import file (see below) |
| `skill_*` | Skill family, from the table above |
| `format_scenario` / `format_concept` | A realistic situation, or a direct question about an idea |
| `format_select_all` | Multiple-choice (select all that apply) question or set |

Batch labels:

| Label | File |
|---|---|
| `ready_lib_ai_01` | `ai_sample_01.json` (sample batch) |
| `ready_lib_ai_02` | `ai_lib_02_introductory.json` |
| `ready_lib_ai_03` | `ai_lib_03_basic.json` |
| `ready_lib_ai_04` | `ai_lib_04_intermediate.json` |
| `ready_lib_ai_05` | `ai_lib_05_advanced.json` |
| `ready_lib_ai_06` | `ai_lib_06_expert.json` |

An answer atom is tagged with every skill family of the sets that use it.

## Import-file rules

- Every file has `dry_run: true`, and every question, answer and set has `status: draft`. The selection service only picks published, current records, so none of this can reach a test before it is published on purpose.
- Every file stays within the import limits: at most 200 records (questions + answers + sets), at most 256 KiB, and the bulk-import maximums of 100 questions, 400 answers and 100 sets. Cross-file references do not exist: every `answer_ref` and `question_ref` resolves inside its own file. That is why an answer used in two files appears as two atoms.
- Provenance on every record: author "READY builder", kind `system`, source reference "Original draft material; not an official assessment; awaiting owner review".
