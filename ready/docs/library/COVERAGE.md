# READY AI library: coverage (generated from the import files)

Counts below are read directly from `ready/seed/library/*.json`. 'Main library' means files 02 to 06; the sample batch is counted separately.

## Totals

| | Questions | Answer atoms | Sets | Choices offered |
|---|---|---|---|---|
| Sample (file 01) | 8 | 31 | 9 | 36 |
| Main library (files 02-06) | 68 | 259 | 80 | 320 |
| Everything | 76 | 290 | 89 | 356 |

## Per file

| File | Questions | Answers | Sets | Select-all questions |
|---|---|---|---|---|
| `ai_sample_01.json` | 8 | 31 | 9 | 2 |
| `ai_lib_02_introductory.json` | 15 | 58 | 17 | 1 |
| `ai_lib_03_basic.json` | 16 | 62 | 18 | 2 |
| `ai_lib_04_intermediate.json` | 16 | 60 | 19 | 0 |
| `ai_lib_05_advanced.json` | 12 | 44 | 15 | 1 |
| `ai_lib_06_expert.json` | 9 | 35 | 11 | 0 |

## Main library by difficulty

| Difficulty | Sets |
|---|---|
| introductory | 17 |
| basic | 18 |
| intermediate | 19 |
| advanced | 15 |
| expert | 11 |

## Main library by audience

Each set has exactly one audience.

| Audience | Sets |
|---|---|
| adult_beginner | 15 |
| student | 11 |
| workplace | 42 |
| educator | 12 |

## Main library by learning objective

| Objective | Sets |
|---|---|
| recognize_when_ai_can_help | 6 |
| write_a_clear_request | 4 |
| check_and_verify_output | 19 |
| protect_private_information | 11 |
| understand_limits_and_bias | 9 |
| choose_when_not_to_use_ai | 4 |
| connect_ai_to_recurring_work | 7 |
| help_others_learn_ai | 7 |
| take_responsibility_for_results | 9 |
| improve_results_by_iterating | 4 |

## Objective by difficulty (sets, main library)

| Objective | introductory | basic | intermediate | advanced | expert |
|---|---|---|---|---|---|
| recognize_when_ai_can_help | 3 | 1 | 1 | 0 | 1 |
| write_a_clear_request | 1 | 2 | 1 | 0 | 0 |
| check_and_verify_output | 4 | 6 | 6 | 2 | 1 |
| protect_private_information | 3 | 3 | 2 | 2 | 1 |
| understand_limits_and_bias | 1 | 1 | 3 | 3 | 1 |
| choose_when_not_to_use_ai | 1 | 1 | 0 | 1 | 1 |
| connect_ai_to_recurring_work | 1 | 1 | 1 | 2 | 2 |
| help_others_learn_ai | 1 | 1 | 2 | 2 | 1 |
| take_responsibility_for_results | 1 | 1 | 2 | 2 | 3 |
| improve_results_by_iterating | 1 | 1 | 1 | 1 | 0 |

Every objective appears at two or more difficulty levels (checked by the tests). Empty cells in this round: recognize_when_ai_can_help / advanced; write_a_clear_request / advanced; write_a_clear_request / expert; choose_when_not_to_use_ai / intermediate; improve_results_by_iterating / expert.

## Question types (main library)

| Type | Questions |
|---|---|
| single_choice | 64 |
| multiple_choice | 4 |

## Choice roles (main library, over all offered choices)

| Role | Choices |
|---|---|
| strong | 86 |
| ambiguous | 40 |
| incorrect | 194 |

## Reuse (main library; counted within each file, because import references cannot cross files)

- Answer atoms: 259. Offered choices: 320.
- Atoms used in two or more sets: 51 (20% of atoms). Those atoms account for 112 of the 320 offered choices.
- Atoms that take a different role in different sets: 6.
- Most-used atom: used in 5 sets.
- Questions placed in more than one set (different audience or choices): 12 of 68.
- Use is lower than the plan hoped for. About 81% of atoms appear in one set only, because most distractors were written to fit one scenario. See the review notes.

## Clue checks (single-choice sets, main library)

- Strong answer is also the longest choice in 18 of 74 sets (24%). With four choices, chance alone would give about 25%.
- Position of the strong answer among the four listed choices (0 = first): 0: 18, 1: 19, 2: 21, 3: 16.
