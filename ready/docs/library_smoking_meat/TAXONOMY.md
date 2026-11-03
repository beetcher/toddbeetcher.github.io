# READY smoking-meat library: taxonomy (draft for owner review)

This is the vocabulary the smoking-meat library (plan R2) uses. It uses only what the READY schema allows today. Nothing in the schema was changed. `ready/tests/test_seed_library_smoking_meat.py` checks every value in the files against the lists on this page, because the open text fields would otherwise accept a typo silently.

## What the schema fixes and what it leaves open

| Field | Schema rule | Used here |
|---|---|---|
| `difficulty` | Closed: introductory, basic, intermediate, advanced, expert. One value per record. | All five |
| `status` | Closed: draft, published, retired | `draft` only |
| connection `role` | Closed: strong, ambiguous, incorrect | All three |
| `question_type` | Closed: single_choice, multiple_choice | Both |
| `topics`, `audiences`, `learning_objectives`, `tags` | Open lists of text | Defined below |
| `attributes` | Closed and empty | Not used |

## Subtopics, as topics

Every record carries the topic `smoking_meat`, plus the one subtopic topic that matches its learning objective. The twelve subtopics in the plan are merged into ten families so that each objective has one home:

| Topic value | Covers |
|---|---|
| `food_safety` | danger zone and two-hour rule, safe minimum temperatures, cross-contamination, thawing, chilling, leftovers, thermometer use |
| `equipment_fuel` | offset, kamado, pellet, electric, kettle; charcoal types; how each type behaves |
| `fire_airflow` | building and holding a fire, intake and exhaust, temperature swings, weather, flare-ups as a heat problem |
| `wood_smoke` | wood types and condition, clean versus dirty smoke, how much smoke |
| `meat_prep` | meat selection, trimming, seasoning, brining and rubs, injecting |
| `temps_doneness` | target temperatures, probe use and placement, probe feel, calibration |
| `timing_stall_rest` | stalls, wrapping, planning a schedule, resting, holding hot |
| `slicing_serving` | slicing direction, pulling, portioning, serving and keeping warm |
| `troubleshooting` | bitter, dry, tough, uneven, unstable temperature |
| `fire_safety` | outdoor-only use, carbon monoxide, distance from buildings, never unattended, ash disposal, cleanup |

## Audiences

| Value | Meaning |
|---|---|
| `hobbyist_beginner` | Has never smoked meat or is on the first few cooks. Follows recipes. |
| `home_enthusiast` | Cooks regularly for family. Wants to manage the fire and the meat without a recipe. |
| `backyard_host_for_a_crowd` | Cooks for a group on a fixed dinner time. Cares about timing, holding and serving safely. |
| `aspiring_competitor_or_caterer` | Cooks for judges or paying guests. Needs repeatability, scale and food-safety discipline. |

These are the four suggested in the plan, unchanged. Each set names exactly one audience. A question may be placed in several sets for different audiences.

## What each difficulty level means

Difficulty describes the judgment asked, not the length of the text. Same length does not mean same difficulty.

| Level | A person at this level can... |
|---|---|
| introductory | Light and run a cooker outdoors safely on a first cook. Know the basic safety rules and vocabulary (danger zone, probe, bark, rest). Make a one-step common-sense choice. |
| basic | Follow a recipe reliably. Use a probe in the right place. Handle meat safely from fridge to table. Recognise clean and dirty smoke. |
| intermediate | Manage the fire and the meat without a recipe. Recognise and fix common faults (bitter smoke, temperature swings, a stall, dry meat). Weigh two reasonable techniques. |
| advanced | Plan the timing for a crowd and a fixed dinner hour. Adapt to weather and equipment. Diagnose subtle or combined faults. Hold, chill and reheat food safely at volume. |
| expert | Refine technique and explain the reasons. Teach others. Reason about trade-offs where respected schools of thought differ, and know where safety leaves no room for them. |

## Learning objectives (10)

| # | Objective value | In plain words | Topic | Tag |
|---|---|---|---|---|
| 1 | `keep_food_safe_start_to_finish` | Keep meat safe from the store to the leftovers | `food_safety` | `skill_food_safety` |
| 2 | `choose_equipment_and_fuel` | Know how each cooker and fuel behaves, and what suits the job | `equipment_fuel` | `skill_equipment` |
| 3 | `manage_fire_and_airflow` | Build, hold and correct a fire and the cooker temperature | `fire_airflow` | `skill_fire` |
| 4 | `produce_clean_smoke` | Choose and use wood to get clean, pleasant smoke | `wood_smoke` | `skill_smoke` |
| 5 | `select_and_prepare_meat` | Choose, trim, season and brine meat sensibly | `meat_prep` | `skill_prep` |
| 6 | `judge_doneness_by_temperature_and_feel` | Use the probe, the number and the feel together | `temps_doneness` | `skill_doneness` |
| 7 | `plan_timing_stall_and_rest` | Plan a cook, handle the stall, rest and hold | `timing_stall_rest` | `skill_timing` |
| 8 | `slice_and_serve_well` | Slice, pull, portion and serve well | `slicing_serving` | `skill_serving` |
| 9 | `diagnose_and_fix_problems` | Work out what went wrong and what to change | `troubleshooting` | `skill_troubleshooting` |
| 10 | `stay_safe_around_fire_and_smoke` | Use fire outdoors safely, handle ash, avoid carbon monoxide | `fire_safety` | `skill_fire_safety` |

## Tag scheme

Every record has `builder_created`, `needs_owner_review` and its batch label `ready_lib_smoking_meat_NN` (01 is the sample; 02 to 06 are the main batches by difficulty). Each record also has the skill tag for its objective. Questions and sets also have one format tag: `format_scenario` (a concrete situation), `format_concept` (a direct judgment question) or `format_select_all` (a multiple-choice, select-all question).

## Where the plan's vocabulary was adapted

- Twelve subtopics merged into ten (above). Nothing was dropped: equipment and fuel are one family; seasoning, brining, rubs, selection and trimming are one (`meat_prep`); stalls, wrapping, timing, resting and holding are one (`timing_stall_rest`); cleanup is with fire safety.
- No schema vocabulary was extended.

## Roles and disagreement in this category

- Food-safety questions have firm right answers. Use only widely agreed guidance; where unsure of a number, the question tests the principle.
- Technique has real schools of thought (wood choice, spritzing, wrap material, hot-and-fast versus low-and-slow, injecting, rest time). Those choices are marked `ambiguous`, with an editor note and a feedback line that states the trade-off.
