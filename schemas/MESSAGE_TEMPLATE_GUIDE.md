# Message template: Programming Guide

For anyone who writes code against `schemas/message_template.schema.json`: the CMS template store, the Console Communications station (Messages tab) and the seed script. Read `SCHEMA_RULES.md` and `CMS_GUIDE.md` first. Written October 15, 2026 (thread 14).

---

## 1. What it is

The wording of one message, for one channel and one audience, kept as data so it can be edited in the Console without a code change or a deploy. The CMS finds the template for a message by `kind`, `channel` and `audience`, fills in the facts of the event, and hands the result to the channel. Nothing about the wording lives in code.

The body is a list of blocks, not HTML. The email channel turns the blocks into the plain-text version and the HTML version, so the Console never edits raw HTML and a template cannot break the page layout.

## 2. Fields

- `kind` (required): the message kind, a key registered in `registry.json` under `message_kinds`, such as `placement_confirmation`.
- `channel` (required): `email` today. A short text-message version is added later as another record for the same kind.
- `audience` (required): which people get this wording (`student`, `requester`). It must be one of the audiences the kind lists. The caller names the audience; the CMS does not know what the word means.
- `name` (required): a plain-words name for the Console.
- `subject` (required): the subject line, one line, placeholders for required facts only.
- `blocks` (required): the body, 1 to 40 blocks (section 3).
- `is_active` (required): the on/off switch. Off means the message is not sent and the attempt is logged `not_sent` with reason `no_template`. Flipping it makes no new version.
- Server fields: `status` (`draft` or `published`), `version`, `previous_id`, `published_at`, `published_by`, `id`, `schema_version`, `created_at`, `created_by`, `updated_at`, `updated_by`, `source`, `deleted_at`, `deleted_by`.

## 3. Blocks

Every block has a `type`.

- `paragraph`: `text` (required) is the words. `**bold**` is bold in the HTML version and plain in the text version. `plain` (optional) replaces `text` in the plain-text version when the two must differ (for example a colon where the HTML version has a button after it). `show_if` (optional) names a fact; the paragraph appears only when that fact has a value.
- `facts_table`: `rows` (required) is a list of rows. Each row has a `label` (left, no placeholders), a `value` (right, with placeholders) and an optional `show_if` fact name. In text each row is one `Label: value` line; in HTML it is a table.
- `button`: `label` (the words on the button) and `link` (normally one placeholder such as `{map_url}`) are required. `show_if` (optional) hides the button when the fact is empty. `plain_prefix` (optional) is put before the link in the text version (`Map:`). `has_fallback_line` (optional, default false) adds a line under the HTML button that shows the address to copy if the button does not work.

A block may carry only the fields its type uses; the schema refuses the rest (a paragraph with `rows`, a button with `text`).

## 4. Placeholders

1. A placeholder is a fact name in curly braces: `{name}`. Curly braces mean nothing else; a stray brace is refused.
2. Only facts of the template's kind may be used. The kind's fact schema is the list. The Console offers exactly those and the checker refuses any other.
3. A placeholder for a REQUIRED fact may be used anywhere.
4. A placeholder for an OPTIONAL fact may be used only inside a block or row guarded by that same fact's `show_if`. This is what keeps a template from ever printing an empty value.
5. If a fact the template needs is missing at send time, nothing is sent: the attempt is logged `not_sent` with reason `incomplete`.
6. In the HTML version, literal words are escaped (`&`, `<`, `>`) and substituted values are escaped as well (`&`, `<`, `>`, quotes). In the text version nothing is escaped.
7. Templates compute nothing. Facts such as `when_day` or `map_url` are worked out by the kind's fact builder in the product, so a template only ever puts values in place.

## 5. Versions, drafts and publishing (linked records)

1. There is at most one DRAFT and one STANDING published record per `kind`, `channel` and `audience`. The standing one is the published record that no other published record has in `previous_id`.
2. Only a published and active record is ever sent. A draft never sends.
3. Creating a draft from the standing record copies its content and sets the draft's `previous_id` to the standing record's id. A first template has no `previous_id`.
4. A draft is edited in place. Publishing turns the draft into the new published record: `status` becomes `published`, `version` becomes the old version plus one (1 for a first template), `published_at` and `published_by` are set. The old record stays as history.
5. Publishing is refused if the standing record changed since the draft was made (someone else published first). The Console then offers a fresh draft.
6. Revert means: make a draft from an older published record, then publish it. History is never rewritten.
7. Every log entry records the `version` it used, so what a person received can be explained after the wording changes.

## 6. What writes what

- The seed script (step 3 of the CMS refactor) writes the two seed templates (`schemas/examples/message_template.seed.json`) as published records, once, when Todd runs it.
- The Console (step 5) creates drafts, edits them, publishes, flips `is_active`, and reverts.
- Nothing else writes templates. The CMS only reads published ones.
