# Discovery: overview and the shared AI block

For anyone who builds or reads the Discovery module (the AI venue loader, P-27, and every finder that follows it). Read `SCHEMA_RULES.md`, `docs/schema-first-build-method.md` and `CMS_GUIDE.md` first; Discovery copies the CMS shape. The full plan is in the project doc `claude/discovery-module-plan.md`. Written October 17, 2026 (thread 17). Step 1 of the plan: schemas only. Nothing in this guide is built yet.

---

## 1. What it is

Discovery is a reusable machine that asks an AI to find things in a place and saves the answers as candidate records for a person to review and activate. Venues are the first thing it finds (the venue finder). Aimed at something else later (high school tracks, say), it needs only a new finder, its types, a prompt and a result saver. The model list, the areas, the spend cap, the marks, the run history and the Console station do not change.

It is a Console tool only. No consumer page touches it.

## 2. Words (one word per idea)

- Finder: a definition of what to find (venue today).
- Type: one kind of thing a finder looks for, such as independent coffee shops. Kept in `discovery_type`. (The plan's early word was "category"; it became "type" because the schema rules need a collection name that pluralizes regularly, and because "type" is Todd's own word.)
- Area: a state or a named region inside a state. Kept in `discovery_area`. (The plan's early word was "territory"; same reason.) In talk, "territory" still means an area.
- Model entry: one AI model the Console can pick, kept in `discovery_model`.
- Prompt: the instruction text, kept in `discovery_prompt`, edited in the Console.
- Run: one press of Go, kept in `discovery_run`. Its id is the batch marker.
- Step: one AI call inside a run.
- Candidate: one result before a person activates it.
- Mark: sure or verify, per fact. A fact with no value and no mark is unknown.
- Mode: off, dry_run or live. Comes from the environment, never from the Console.

## 3. The collections

| Schema | Collection | Holds | Guide |
|---|---|---|---|
| `discovery_model` | `discovery_models` | AI models, prices, key name | `DISCOVERY_MODEL_GUIDE.md` |
| `discovery_area` | `discovery_areas` | states (on/off) and named regions | `DISCOVERY_AREA_GUIDE.md` |
| `discovery_type` | `discovery_types` | the types a finder looks for | `DISCOVERY_TYPE_GUIDE.md` |
| `discovery_prompt` | `discovery_prompts` | the prompt text, draft and published | `DISCOVERY_PROMPT_GUIDE.md` |
| `discovery_setting` | `discovery_settings` | the one settings record | `DISCOVERY_SETTING_GUIDE.md` |
| `discovery_run` | `discovery_runs` | one record per press of Go | `DISCOVERY_RUN_GUIDE.md` |

Plus one optional block on the target record, the `discovery` block (section 5).

## 4. The venue finder (PROPOSAL: Todd confirms the field list)

The AI is asked for a short list only. Todd: "It doesn't need to capture everything, for example, how many rooms." The contract the AI answers in is generated from `venue.schema.json` (types and limits come from the schema, so there is one definition), plus the place address and the operator, plus a mark and a source for each fact.

| Asked for | Becomes | Tier |
|---|---|---|
| name | venue `name` | needed |
| operator name (the business or institution that runs it) | an organization, linked `operated_by` | needed |
| city and state | the place's address | needed |
| street address and postal code | the place's address | asked; if the street is missing the candidate is kept and flagged `no_street_address` (Todd, 2026-10-17) |
| what it is and why it is good for a small meeting | venue `description` | optional |
| website | venue `website_url` | optional |
| phone | venue `phone` | optional |
| public email, only if the venue's own site shows one | venue `email` | optional |
| has wifi, is accessible, allows minors | venue `has_wifi`, `is_accessible`, `allows_minors` | optional |
| the place's public opening hours, one line | venue `availability_notes`, as the text "Public hours per the web (check before relying on them): ..." (never the structured `availability_hours`: opening hours are not when a class can be held) | optional |
| anything else worth knowing | venue `notes` | optional |

Every candidate is created `inactive`, `is_public_venue` true (it cannot reach the public picker until a person activates it), `source` import, with the `discovery` block. Never private homes. Nobody is contacted. Needed means the candidate is rejected without it; optional means it is simply absent when the AI does not know it. These tiers belong to the finder, not to the venue schema, so no venue field becomes required.

The prompt placeholders for the venue finder are `{territory}`, `{types}`, `{fields}` and `{max_results}`. A draft of the seed prompt is the valid example `venue_seed_prompt` in `examples/discovery_prompt.examples.json`; Todd edits the wording in the Console.

## 5. The `discovery` block

An optional, read-only object on the target record (on `venue` today). It is defined once in `schemas/discovery_mark.fragment.json` and embedded unchanged in each schema an AI finder can create; `check.py` fails if a copy drifts. A record loaded by hand never has it. It is read-only because only the server sets it, through a named function (the way `review_count` is kept), not through create or the edit form.

- `run_id` (required): the `discovery_run` that found it.
- `model_name` (required): the AI model that produced it.
- `prompt_version` (required): the version of the published prompt used.
- `found_at` (required): when the AI result was received (UTC).
- `source_urls`: web pages the AI cited, up to 20.
- `marks`: how sure the AI was about each fact, by field name: `sure` or `verify`. A fact with a value but no mark was not marked; a fact the AI did not know is absent. Todd's three states: sure (one color), verify (a different color), unknown (blank).
- `needs_attention`: true when a person should check the record before activating it. Absent means false.
- `attention_reasons`: why, as codes: `no_street_address`, `address_not_matched`, `operator_unconfirmed`. Required, at least one, when `needs_attention` is true.

Rules the schema cannot say: `run_id` names a run that exists; each key in `marks` names a field the record holds; a fact marked `sure` must have a source in `source_urls`, otherwise it is stored as `verify`.

LATER (step 4, not now): a "mark verified" action in the Console that updates a mark after a person checks a fact, through a second named function.

## 6. Rules the whole module keeps (each becomes a named test in step 2)

The eighteen rules are in the plan, section 14 (D-1 to D-18). The ones that touch the schemas: a run record is never removed; candidates are created inactive only; duplicates are skipped, never merged (same place, same name, same operator; with no street address, same name, operator and city); a `sure` fact needs a source; a spend never goes above the cap; the mode is read from the environment and fails closed.

## 7. Where each kind of rule lives (method section 4.1)

Field shape, limits and the simple cross-field rules are in each schema. The few same-record rules JSON Schema cannot say are in the handler's rules block (each guide lists them). Everything that involves another collection, the ZIP table, the outside world or the AI is a service rule and lives in the Discovery service (each guide lists them so they are not lost). The Console never creates or edits a run, or the `discovery` block, directly: `discovery_run` is added to `ADMIN_BLOCKED_COLLECTIONS` for generic create, update and delete, and only the Discovery service writes runs.

## 8. Open items

- Todd confirms the venue finder's field list (section 4) and the wording of the seed prompt.
- Prices, model names and the Vertex AI setup are checked against current provider documentation before step 3.
- The 50-state ZIP list: source and license to be checked before step 3.
- Retention periods are written policies only; nothing enforces them yet.
