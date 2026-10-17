# Discovery prompt: Programming Guide

For anyone who writes code against `schemas/discovery_prompt.schema.json`: the prompt store, the prompt builder and the Console Discovery station (Settings tab, Prompt). Read `DISCOVERY_GUIDE.md` and `MESSAGE_TEMPLATE_GUIDE.md` first; this record copies the draft and publish pattern. Written October 17, 2026 (thread 17).

---

## 1. What it is

The instruction text sent to the AI for one finder, kept as data. Todd (2026-10-17): the Console must let the operator bring up and edit the prompts that go into the AI calls. A run stores the exact text it sent in each step, so what was sent is never a mystery.

## 2. Fields

- `finder_key` (required): which finder this prompt is for.
- `name` (required): a plain-words name in the Console.
- `text` (required): the instruction text, with `{placeholder}` slots. 20 to 12,000 characters.
- Server fields: `status` (`draft` or `published`), `version`, `previous_id`, `published_at`, `published_by`, `id`, `schema_version`, `created_at`, `created_by`, `updated_at`, `updated_by`, `source`, `deleted_at`, `deleted_by`.

## 3. Versions (same as message templates)

A draft is edited in place and is never used by a run. Publishing turns the draft into the new published record, whose `previous_id` names the record it replaces; the standing version is the published record nobody supersedes. A revert is a draft copied from an older version and then published. `x_history` is `linked_records`.

## 4. Rules the schema cannot say

1. At most one draft and one standing published record per `finder_key` (handler rule).
2. A published record's `text` is never edited; the only change allowed after publishing is soft delete of a draft.

## 5. Service rules

1. Every `{placeholder}` in `text` must be one the finder supplies. The venue finder supplies `{territory}`, `{types}`, `{fields}` and `{max_results}`. Curly braces are used only for placeholders. The Console refuses to save a prompt that breaks this.
2. A finder with no published prompt cannot run.
3. A run records the `prompt_id` and version it used.
4. Preview: the Console shows the exact final text built from the current choices (a dry run builds the same text and sends nothing).

## 6. Open items

- Todd reviews the seed prompt wording (example `venue_seed_prompt`). It is a draft.
