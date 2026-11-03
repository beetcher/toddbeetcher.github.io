# Coverage: judgment and critical thinking (draft)

Counts are for the main batches (files 02 to 08). The sample (`judgment_sample_01.json`: 8 questions, 34 answers, 10 sets) is separate and overlaps in topic.

**Totals:** 68 questions, 280 answers, 81 sets (all `draft`).

## Per file
| file | questions | answers | sets |
|---|---|---|---|
| judgment_lib_02_evidence_claims.json | 10 | 41 | 13 |
| judgment_lib_03_cause_probability.json | 10 | 42 | 13 |
| judgment_lib_04_errors_biases.json | 10 | 40 | 11 |
| judgment_lib_05_uncertainty_tradeoffs.json | 9 | 38 | 11 |
| judgment_lib_06_ethics_questions.json | 10 | 41 | 11 |
| judgment_lib_07_updating_ai.json | 10 | 40 | 11 |
| judgment_lib_08_choose_two_and_more.json | 9 | 38 | 11 |

## Sets by difficulty
| level | sets |
|---|---|
| introductory | 13 |
| basic | 19 |
| intermediate | 18 |
| advanced | 17 |
| expert | 14 |

## Sets by audience and difficulty (a set with two audiences counts under each)
| audience | introductory | basic | intermediate | advanced | expert | total |
|---|---|---|---|---|---|---|
| teen_9_12 | 12 | 2 | 0 | 0 | 0 | 14 |
| college_student | 0 | 7 | 2 | 1 | 0 | 10 |
| early_career_professional | 0 | 3 | 8 | 3 | 1 | 15 |
| team_lead_or_manager | 0 | 0 | 1 | 10 | 12 | 23 |
| general_adult | 1 | 7 | 7 | 3 | 1 | 19 |

## Sets by learning objective and level
| objective | introductory | basic | intermediate | advanced | expert | total |
|---|---|---|---|---|---|---|
| evaluate_sources_and_evidence | 1 | 3 | 2 | 2 | 1 | 9 |
| separate_claim_evidence_assumption | 1 | 2 | 1 | 1 | 1 | 6 |
| reason_about_cause_and_correlation | 2 | 1 | 3 | 2 | 1 | 9 |
| reason_about_probability_and_base_rates | 1 | 3 | 1 | 2 | 1 | 8 |
| recognize_reasoning_errors | 1 | 1 | 1 | 1 | 1 | 5 |
| notice_cognitive_biases | 1 | 2 | 3 | 1 | 1 | 8 |
| decide_under_uncertainty | 1 | 1 | 1 | 1 | 1 | 5 |
| weigh_tradeoffs_and_second_order_effects | 1 | 1 | 2 | 2 | 1 | 7 |
| apply_ethical_judgment_at_work | 1 | 1 | 1 | 1 | 2 | 6 |
| ask_questions_and_notice_missing_information | 1 | 1 | 1 | 2 | 1 | 6 |
| update_views_and_know_when_to_escalate | 1 | 1 | 1 | 1 | 1 | 5 |
| evaluate_ai_and_persuasive_content | 1 | 2 | 1 | 1 | 2 | 7 |

## Sets by subtopic
| subtopic | sets |
|---|---|
| evidence_sources | 9 |
| claim_evidence_assumption | 6 |
| cause_correlation | 9 |
| probability_base_rates | 8 |
| reasoning_errors | 5 |
| cognitive_biases | 8 |
| uncertainty_decisions | 5 |
| tradeoffs_second_order | 7 |
| workplace_ethics | 6 |
| questions_missing_info | 6 |
| updating_escalating | 5 |
| ai_persuasive_content | 7 |

## Question type (by set)
| type | sets |
|---|---|
| single_choice | 71 |
| multiple_choice | 10 |

## Roles on connections
| role | connections |
|---|---|
| strong | 91 |
| incorrect | 140 |
| ambiguous | 93 |

## Sets tagged `move_ask_or_delay` (strong move is to ask or wait)
| level | sets |
|---|---|
| introductory | 6 |
| basic | 5 |
| intermediate | 8 |
| advanced | 13 |
| expert | 9 |

## Reuse statistics

- Answer atoms used in more than one set: 41 of 280 (14 out of 100).
- Answer atoms whose role differs between sets: 10.
- Most-used answer atom appears in 4 sets.
- Questions placed in more than one set: 13 of 68.
- Reuse is mostly inside one file, because a bulk-import file can only refer to atoms in itself.
- Answer-atom reuse is lower than in a fact library (a judgment answer names a specific course of action in a specific scenario). The reuse that exists comes from shared scenarios with different decision points and from general moves such as "ask where the figure came from".

## Known thin pools (a selection asking for these reports a shortfall)
- college_student at intermediate and advanced (few sets).
- teen_9_12 beyond introductory (only 2 basic sets).
- team_lead_or_manager at intermediate (1 set) and at introductory or basic (none).
- general_adult at introductory (1) and at expert (1).
- early_career_professional at expert (1).
- Every objective has all five levels, but only 1 to 2 sets at each level.
