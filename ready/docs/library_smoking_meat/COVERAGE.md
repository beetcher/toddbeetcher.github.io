# Coverage: smoking-meat library (draft)

Counts are of sets (a set is one question with its offered answers) unless said otherwise. Generated from the files after the final build.

## Files

| File | Questions | Answers | Sets |
|---|---|---|---|
| `smoking_meat_lib_02_introductory.json` | 15 | 57 | 17 |
| `smoking_meat_lib_03_basic.json` | 15 | 56 | 18 |
| `smoking_meat_lib_04_intermediate.json` | 16 | 60 | 17 |
| `smoking_meat_lib_05_advanced.json` | 11 | 46 | 14 |
| `smoking_meat_lib_06_expert.json` | 8 | 34 | 12 |
| `smoking_meat_sample_01.json` | 9 | 36 | 10 |

## Objective by difficulty (main library, sets)

Every objective appears at more than one level.

| Objective | introductory | basic | intermediate | advanced | expert |
|---|---|---|---|---|---|
| `choose_equipment_and_fuel` | 1 | 1 | 1 | 0 | 1 |
| `diagnose_and_fix_problems` | 1 | 1 | 1 | 3 | 2 |
| `judge_doneness_by_temperature_and_feel` | 2 | 4 | 1 | 0 | 2 |
| `keep_food_safe_start_to_finish` | 4 | 4 | 1 | 4 | 3 |
| `manage_fire_and_airflow` | 1 | 1 | 4 | 0 | 0 |
| `plan_timing_stall_and_rest` | 1 | 0 | 5 | 4 | 1 |
| `produce_clean_smoke` | 2 | 2 | 0 | 0 | 2 |
| `select_and_prepare_meat` | 1 | 2 | 2 | 1 | 0 |
| `slice_and_serve_well` | 1 | 1 | 0 | 1 | 0 |
| `stay_safe_around_fire_and_smoke` | 3 | 2 | 2 | 1 | 1 |

### Main library (files 02 to 06)

Questions 65, answers 253, sets 78.

| Difficulty | Sets |
|---|---|
| `introductory` | 17 |
| `basic` | 18 |
| `intermediate` | 17 |
| `advanced` | 14 |
| `expert` | 12 |

| Audience | Sets |
|---|---|
| `aspiring_competitor_or_caterer` | 15 |
| `backyard_host_for_a_crowd` | 14 |
| `hobbyist_beginner` | 22 |
| `home_enthusiast` | 27 |

| Learning objective | Sets |
|---|---|
| `choose_equipment_and_fuel` | 4 |
| `diagnose_and_fix_problems` | 8 |
| `judge_doneness_by_temperature_and_feel` | 9 |
| `keep_food_safe_start_to_finish` | 16 |
| `manage_fire_and_airflow` | 6 |
| `plan_timing_stall_and_rest` | 11 |
| `produce_clean_smoke` | 6 |
| `select_and_prepare_meat` | 6 |
| `slice_and_serve_well` | 3 |
| `stay_safe_around_fire_and_smoke` | 9 |

| Subtopic (topic value) | Sets |
|---|---|
| `equipment_fuel` | 4 |
| `fire_airflow` | 6 |
| `fire_safety` | 9 |
| `food_safety` | 16 |
| `meat_prep` | 6 |
| `slicing_serving` | 3 |
| `temps_doneness` | 9 |
| `timing_stall_rest` | 11 |
| `troubleshooting` | 8 |
| `wood_smoke` | 6 |

| Question type | Sets |
|---|---|
| `multiple_choice` | 11 |
| `single_choice` | 67 |

| Connection role | Offered choices |
|---|---|
| ambiguous | 30 |
| incorrect | 193 |
| strong | 89 |

Answer atoms used in 1 set: 195; in 2 sets: 57; in 3 or more: 1. Reused at least once: 58 of 253 atoms. Atoms that carry different roles in different sets: 6.
Questions placed in more than one set: 13 of 65.

### Sample (file 01)

Questions 9, answers 36, sets 10.

| Difficulty | Sets |
|---|---|
| `introductory` | 2 |
| `basic` | 3 |
| `intermediate` | 5 |
| `advanced` | 0 |
| `expert` | 0 |

| Audience | Sets |
|---|---|
| `backyard_host_for_a_crowd` | 2 |
| `hobbyist_beginner` | 4 |
| `home_enthusiast` | 4 |

| Learning objective | Sets |
|---|---|
| `judge_doneness_by_temperature_and_feel` | 4 |
| `keep_food_safe_start_to_finish` | 2 |
| `plan_timing_stall_and_rest` | 2 |
| `produce_clean_smoke` | 1 |
| `stay_safe_around_fire_and_smoke` | 1 |

| Subtopic (topic value) | Sets |
|---|---|
| `fire_safety` | 1 |
| `food_safety` | 2 |
| `temps_doneness` | 4 |
| `timing_stall_rest` | 2 |
| `wood_smoke` | 1 |

| Question type | Sets |
|---|---|
| `multiple_choice` | 1 |
| `single_choice` | 9 |

| Connection role | Offered choices |
|---|---|
| ambiguous | 5 |
| incorrect | 24 |
| strong | 11 |

Answer atoms used in 1 set: 32; in 2 sets: 4; in 3 or more: 0. Reused at least once: 4 of 36 atoms. Atoms that carry different roles in different sets: 2.
Questions placed in more than one set: 1 of 9.

## Notes
- Reuse is within a file only, because an import file must resolve its own references. The batches are split by difficulty, so reuse is strongest between sets at the same level (different audiences, or contrasting contexts).
- Host and competitor/caterer audiences have fewer sets than beginner and enthusiast; this is deliberate for a first draft and is the easiest gap to fill next.
- `slice_and_serve_well` and `choose_equipment_and_fuel` are the thinnest objectives (3 and 4 sets).
- Single-choice sets where the strong answer is the longest option: reported in REVIEW-NOTES.
