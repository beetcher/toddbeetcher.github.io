# Discovery model: Programming Guide

For anyone who writes code against `schemas/discovery_model.schema.json`: the model store, the provider adapters and the Console Discovery station (Settings tab, Models). Read `DISCOVERY_GUIDE.md` first. Written October 17, 2026 (thread 17).

---

## 1. What it is

One AI model the Run tab can pick. Adding a model is adding a record, with no code change, as long as we already have an adapter for its provider. The record holds the prices the cost estimate and the hard spend cap are built on. It holds the NAME of the server setting that has the key, never the key.

## 2. Fields

- `provider` (required): `gemini` (Google, through the Google project, no key), `claude` or `openai`. A new company needs a new adapter and a new allowed value here (adding a value is not a breaking change).
- `model_name` (required): the provider's own name for the model.
- `label` (required): the plain-words name in the Console picker.
- `price_input_per_million_cents` (required): whole US cents per million input tokens, rounded up.
- `price_output_per_million_cents` (required): whole US cents per million output tokens, rounded up.
- `search_price_per_1000_cents`: whole US cents per 1,000 web searches, when the provider charges for them.
- `max_output_tokens`: the most output tokens one call may use. Optional; the adapter has its own default.
- `has_grounding` (required): whether the model can search the web. Without it most facts come back marked verify.
- `key_name`: the NAME of the server setting that holds the key, such as `ICDT_CLAUDE_KEY`. Required for `claude` and `openai`. Absent for `gemini`.
- `is_active` (required): the on/off switch.
- `notes`: free text.
- Server fields: `id`, `schema_version`, `created_at`, `created_by`, `updated_at`, `updated_by`, `source`, `deleted_at`, `deleted_by`.

Money rule: whole cents, rounded up when the real price has fractions of a cent, so a cap is never underestimated.

## 3. Rules the schema cannot say

1. `provider` plus `model_name` is unique among live records (handler rule: same collection).
2. Strings are trimmed before they are stored.

## 4. Service rules (not the handler's)

1. A model with `is_active` false cannot be run.
2. The setting named by `key_name` must exist in the server environment, or a run on this model is refused. The key is never read into a record, a log or a reply.
3. Soft-deleting or switching off a model never changes a past run: each run keeps its own copy of the name and prices it used.
4. The Console shows a warning beside a model whose prices are all zero (a guard against a forgotten price). It is a warning, not a refusal, because a free model is possible.

## 5. Open items

- Current model names and prices are looked up at build time, not now. The examples hold draft numbers only.
- Whether prices are re-checked on a schedule.
