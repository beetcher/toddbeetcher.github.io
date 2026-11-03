# READY U.S. citizenship and civics library: taxonomy (draft for owner review)

This is the vocabulary the U.S. citizenship and civics study library (plan R4) uses. It uses only what the READY schema allows today. Nothing in the schema was changed. `ready/tests/test_seed_library_us_citizenship.py` checks every topic, audience, objective and tag in the files against the lists on this page, because the open text fields would otherwise accept a typo silently.

## Important notice

This is original **study-practice material**. It is **not the official naturalization test**, it is **not affiliated with or endorsed by USCIS**, and it is **not legal or immigration advice**. The questions are not copied from, and do not follow the wording of, any official question list. The official civics materials change over time; check the current official USCIS materials before using this library with real applicants. Each record says this in `origin.notes`. Everything is `draft`.

## What the schema fixes and what it leaves open

| Field | Schema rule | Used here |
|---|---|---|
| `difficulty` | Closed: introductory, basic, intermediate, advanced, expert | All five |
| `status` | Closed: draft, published, retired | `draft` only |
| connection `role` | Closed: strong, ambiguous, incorrect | All three |
| `question_type` | Closed: single_choice, multiple_choice | Both |
| `topics`, `audiences`, `learning_objectives`, `tags` | Open lists of text | Defined below |
| `attributes` | Closed and empty | Not used |

## Audiences

| Value | Who | Language and context |
|---|---|---|
| `naturalization_applicant` | An adult studying for the civics part of the process | Standard study-guide English. Direct feedback that names the rule and the reason. |
| `adult_english_learner` | An adult still building English | Very plain English. Short sentences. No idioms. Uncommon words are explained inside the question. Gentle, clear feedback. Mostly introductory and basic. |
| `civics_teacher_or_tutor` | A person who teaches or tutors civics | Precise vocabulary. Reasoning, interpretation, how to explain an idea, and where interpretations differ. Mostly intermediate to expert. |
| `general_adult_learner` | An adult refreshing general civic literacy | Plain adult language. Everyday and news-free examples. |

A set names exactly one audience. A question may be placed in several sets for different audiences or levels. An answer atom's audiences are the union of the sets that offer it. Questions written for the English learner use short wording of their own rather than reusing harder wording.

## What each difficulty level means

| Level | A person at this level can... |
|---|---|
| introductory | Recall one basic fact in simple English. |
| basic | Recall a standard study-guide fact. |
| intermediate | Connect ideas: why a branch has a power, why a rule exists, what comes before or after. |
| advanced | Apply a principle to a new situation. |
| expert | Reason about nuance: how a principle can be read in more than one way, how to explain it to others, where well-informed people differ. |

Difficulty describes the thinking asked, not the length of the text. Filter on audience first, then difficulty.

## Subtopics, as topics

Every record carries the topic `us_citizenship` plus one subtopic topic per learning objective.

| Topic value | Covers |
|---|---|
| `principles_democracy` | Rule of law, popular sovereignty, separation of powers, checks and balances, the Constitution as supreme law, how it is amended |
| `system_government` | The three branches, Congress, the presidency as an office, the courts, how a bill becomes law |
| `federalism_elections` | National and state power, elections and voting rights in general terms, terms of office |
| `rights_freedoms` | The Bill of Rights and later amendments, freedoms, equal protection, due process |
| `civic_responsibilities` | Obeying laws, paying taxes, jury service, voting, staying informed |
| `colonial_founding` | Colonial period, independence, the Declaration, the Articles, writing the Constitution |
| `nineteenth_century` | Expansion, Native nations and removal, the Civil War, slavery and its end, Reconstruction amendments, women's rights |
| `modern_history` | World wars, the Great Depression, the Cold War, the civil rights movement (well-agreed level) |
| `symbols_holidays` | The flag, the anthem, national symbols, national holidays |
| `civics_geography` | The country's location and borders, oceans, the capital, civic-level geography |
| `reading_vocabulary` | Vocabulary in context, completing and choosing correct sentences (text only; no audio dictation) |

## Learning objectives (11)

| # | Objective value | In plain words | Topic | Tag |
|---|---|---|---|---|
| 1 | `explain_democratic_principles` | Explain the core ideas of American democracy | `principles_democracy` | `skill_principles_democracy` |
| 2 | `describe_branches_and_powers` | Describe what each branch does and how they limit each other | `system_government` | `skill_system_government` |
| 3 | `explain_federalism_and_elections` | Explain shared power with states, elections and who may vote | `federalism_elections` | `skill_federalism_elections` |
| 4 | `identify_rights_and_freedoms` | Identify rights and freedoms and where they come from | `rights_freedoms` | `skill_rights_freedoms` |
| 5 | `describe_civic_responsibilities` | Describe duties and responsibilities of residents and citizens | `civic_responsibilities` | `skill_civic_responsibilities` |
| 6 | `outline_colonial_and_founding_history` | Outline the colonial period and the founding | `colonial_founding` | `skill_colonial_founding` |
| 7 | `trace_nineteenth_century_changes` | Trace expansion, the Civil War and the end of slavery | `nineteenth_century` | `skill_nineteenth_century` |
| 8 | `summarize_modern_american_history` | Summarize the world wars, the Cold War and the civil rights movement | `modern_history` | `skill_modern_history` |
| 9 | `recognize_symbols_and_holidays` | Recognize national symbols and holidays | `symbols_holidays` | `skill_symbols_holidays` |
| 10 | `use_civics_geography` | Use basic geography in civic questions | `civics_geography` | `skill_civics_geography` |
| 11 | `read_civic_vocabulary_in_context` | Read and understand civic words in sentences | `reading_vocabulary` | `skill_reading_vocabulary` |

Each set has exactly one objective. A question placed in several sets keeps the same objective.

## Tag scheme

Every record has `builder_created`, `needs_owner_review`, `us_citizenship`, its batch label `ready_lib_us_citizenship_NN`, and the skill tag for each of its objectives. Batches: 01 sample; 02 principles and government; 03 rights and responsibilities; 04 history; 05 symbols, geography and reading. Questions and sets also carry one format tag: `format_fact`, `format_reasoning`, `format_scenario`, or `format_select_all` (multiple choice). Answer atoms carry no format tag.

## Content conventions

- **No officeholders and nothing recent.** No question depends on who currently holds an office, on party control, or on a recent law or ruling. Offices are asked about as offices.
- **Original questions.** Same topics that people study, original wording, no copied lists.
- **Stable facts only.** Constitutional structure, amendment topics, and widely agreed historical events and their order. Numbers are limited to ones fixed by the Constitution or by the long-settled shape of the country (for example four-year presidential terms, two senators per state).
- **Sensitive history.** Slavery, Native nations, immigration and civil rights are written plainly and accurately, without partisan framing. No questions about political parties beyond neutral definitions.
- **Roles.** `ambiguous` marks a defensible answer where terms or interpretation legitimately differ (for example "republic" or "representative democracy"). Every ambiguous choice carries an editor note.
- **Text only.** No image, map, audio or link is needed.
