# Comms setting: Programming Guide

For anyone who writes code against `schemas/comms_setting.schema.json`: the CMS settings reader and the Console Communications station (Settings tab). Read `SCHEMA_RULES.md` and `CMS_GUIDE.md` first. Written October 15, 2026 (thread 14).

---

## 1. What it is

The one record of CMS settings, edited in the Console. It holds sender details, the test redirect and the per-channel switches. The send MODE (`off`, `log_only`, `live`) is not here: it comes from the environment next to the secrets, so a mistake in the Console can never turn live sending on.

## 2. Fields

- `settings_key` (required): always `default`. Ids are UUIDs, so this field is what makes "exactly one record" checkable.
- `sender_name` (required): the name people see as the sender, such as Launch.
- `from_address`: the address mail is sent from. Absent means the address built into the server. It must be an address the mail provider has verified, or sends fail. The final domain is parked (P-05).
- `reply_to`: where replies go. Absent means the from address.
- `footer`: a short closing line added under every email.
- `test_redirect_address`: when set, every message goes here instead of the real address and the log entry is marked redirected.
- `is_email_on` (required): whether the email channel may send. false makes every email attempt `not_sent` (`channel_unavailable`).
- `is_text_on` (required): whether the text channel may send. It must stay false until a text channel exists; the handler refuses true.
- Server fields: `id`, `schema_version`, `created_at`, `created_by`, `updated_at`, `updated_by`, `source`, `deleted_at`, `deleted_by`.

## 3. Rules the schema cannot say

1. Exactly one record exists. The handler creates it with the Launch defaults if it is missing and refuses a second one.
2. Changes are in place and need the `updated_at` the editor read (same stale-update rule as every record).
3. `from_address` and `reply_to` are lowercased and trimmed before they are stored.
4. The footer is added by the channel after the last block; templates never mention it.
