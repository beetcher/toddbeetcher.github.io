# Discovery setting: Programming Guide

For anyone who writes code against `schemas/discovery_setting.schema.json`: the settings reader and the Console Discovery station (Settings tab, Limits). Read `DISCOVERY_GUIDE.md` and `COMMS_SETTING_GUIDE.md` first; this record copies the one-record pattern. Written October 17, 2026 (thread 17).

---

## 1. What it is

The one record of Discovery settings, edited in the Console: the spend and size limits. The run MODE (`off`, `dry_run`, `live`) is not here: it comes from the environment (`ICDT_DISCOVERY_MODE`) next to the secrets, so a mistake in the Console can never turn live AI calls on.

## 2. Fields

- `settings_key` (required): always `default`. Ids are UUIDs, so this field is what makes "exactly one record" checkable.
- `default_model_id`: the model the Run tab selects first. Absent means the first active model.
- `default_spend_cap_cents` (required): the spend cap the Run tab starts with, in whole US cents.
- `max_spend_cap_cents` (required): the most any single run may be allowed to spend. The Run tab cannot go above it.
- `max_results_per_run` (required): the most candidates one run may return.
- `results_per_step` (required): how many candidates one AI call is asked for.
- Server fields: `id`, `schema_version`, `created_at`, `created_by`, `updated_at`, `updated_by`, `source`, `deleted_at`, `deleted_by`.

## 3. Rules the schema cannot say

1. Exactly one record exists. The handler creates it with the starting values if it is missing and refuses a second one. Proposed starting values (Todd changes them in the Console): `default_spend_cap_cents` 100 ($1.00), `max_spend_cap_cents` 1000 ($10.00), `max_results_per_run` 100, `results_per_step` 10.
2. `default_spend_cap_cents` is not above `max_spend_cap_cents`.
3. `results_per_step` is not above `max_results_per_run`.
4. Changes are in place and need the `updated_at` the editor read.

## 4. Service rules

1. A run's own cap and result limit cannot exceed the maximums here.
2. A run needs at most 40 steps, so `max_results_per_run` divided by `results_per_step` (rounded up) must not exceed 40. A run that would need more is refused with a plain message.
3. `default_model_id`, when set, must name a live, active model.

## 5. Open items

- The starting values in rule 1 are proposals; no real money is spent until Todd sets them and switches the mode to live.
