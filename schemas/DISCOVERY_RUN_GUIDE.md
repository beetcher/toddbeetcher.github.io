# Discovery run: Programming Guide

For anyone who writes code against `schemas/discovery_run.schema.json`: the Discovery service, the run store and the Console Discovery station (Run and Runs tabs). Read `DISCOVERY_GUIDE.md` first. Written October 17, 2026 (thread 17).

---

## 1. What it is

One press of Go: what was asked, the model and prices used, what it cost, what came back and every record it created. THE RUN RECORD IS HISTORY (same spirit as the message log): it is never removed. Withdrawing a run soft-deletes the records it created and marks the run `withdrawn`. Only the Discovery service writes runs; the Console never creates or edits one directly (`discovery_run` is added to `ADMIN_BLOCKED_COLLECTIONS` for generic writes in step 3).

The run id is the batch marker that is stored on every record the run creates, in the `discovery` block.

## 2. Fields

What was asked:
- `finder_key` (required): which finder ran.
- `run_mode` (required): `dry_run` (prompts built and cost estimated, nothing sent) or `live`.
- `model_id` (required): the model record used. The run keeps its own copy of what it needs: `model_name`, `model_price_input_per_million_cents`, `model_price_output_per_million_cents` (all required) and `model_price_search_per_1000_cents`. Every run stores the price it used.
- `area_ids` (required): the states or regions searched, with `area_labels` as the names at the time.
- `type_keys` (required): the types searched.
- `prompt_id` and `prompt_version` (required): the published prompt used.
- `max_results` (required): the most candidates the run could return.

Money:
- `spend_cap_cents` (required): the hard cap for this run.
- `estimated_cost_low_cents`, `estimated_cost_high_cents` (required): the estimate shown before Go.
- `actual_cost_cents` (required): what it has cost so far, rounded up. A step with no answer has an unknown cost and is not counted here.
- `input_tokens`, `output_tokens`, `search_count`: totals the provider reported.

Progress and result:
- `status` (required): `planned`, `running`, `finished`, `stopped`, `failed` or `withdrawn`.
- `stop_reason`: for a stopped run: `cap_reached`, `results_limit`, `operator`, `mode_off` or `too_many_no_answers`.
- `steps_planned`, `steps_done`.
- `steps`: one entry per step, up to 40. Each has `step_number`, `type_key`, `area_id`, `status` (`ok`, `no_answer`, `rejected`, `skipped`), `result_count`, `input_tokens`, `output_tokens`, `cost_cents`, `error_code` (a short code, never provider text) and `prompt_text` (the exact text sent, up to 8,000 characters).
- `found_count`, `created_count`, `duplicate_count`, `rejected_count`, `attention_count`.
- `rejections`: what was rejected and why, up to 100. Each has a `name`, a `reason` code and the `fields` involved (field names only, never values).

What it created (so Withdraw can take it back):
- `created_organization_ids`, `created_location_ids`, `created_venue_ids`, `created_organization_link_ids`, `created_location_link_ids`.

When:
- `started_at`, `finished_at`, `withdrawn_at`, `withdrawn_by`.
- `notes`: free text from the operator.
- Server fields: `id`, `schema_version`, `created_at`, `created_by`, `updated_at`, `updated_by`, `source`, `deleted_at`, `deleted_by`.

## 3. Rules the schema says

`stopped` requires `stop_reason`. `withdrawn` requires `withdrawn_at` and `withdrawn_by`, and those two come together. `finished`, `stopped` and `failed` require `finished_at`.

## 4. Rules the schema cannot say (handler rules block)

1. `actual_cost_cents` is not above `spend_cap_cents`.
2. `estimated_cost_low_cents` is not above `estimated_cost_high_cents`.
3. `steps_done` is not above `steps_planned`.
4. Status moves forward only: planned, running, then finished, stopped or failed; withdrawn only from finished, stopped or failed.

## 5. Service rules

1. `max_results` and `spend_cap_cents` are not above the maximums in `discovery_setting`.
2. Every area, type, model and prompt named must have existed and been active when the run started; a dry run builds the prompts and estimate but never calls a provider.
3. Withdraw soft-deletes links, then venues, then places, then organizations that THIS run created, using the `created_*` lists. A venue that was activated, edited by a person or used by a class is not removed; it is reported back. A place or organization something else now uses is left.
4. A run is one record. Its size stays under the database's 1 MiB limit because steps are capped at 40, each `prompt_text` at 8,000 characters, and each created list at 1,000.
5. Bulk loads are not journaled until the activity log (P-46); the run record and the `discovery` block are the trail until then.

## 6. Open items

- Whether to keep full `prompt_text` on every step or only the first (size is safe either way at these caps).
