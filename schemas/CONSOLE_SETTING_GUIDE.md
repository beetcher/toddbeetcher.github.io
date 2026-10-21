# Console setting: Programming Guide

For anyone who writes code against `schemas/console_setting.schema.json`: the settings handler, the Console's sign-out timer and the Access station's Sign-in box. Read `DISCOVERY_SETTING_GUIDE.md` first; this record copies the one-record pattern. Written October 21, 2026 (thread 21, Todd's decision: "a time out for the console window ... an option in settings by the super admin").

---

## 1. What it is

The one record of Console settings, edited by a super admin. Today it holds one setting: the number of minutes of inactivity after which the Console signs a person out. Inactivity means no click, key press, scroll or touch in the Console window. A Discovery run that is in progress counts as activity, because the run is driven from the browser and signing out would stop it.

## 2. Fields

- `settings_key` (required): always `default`. Ids are UUIDs, so this field is what makes "exactly one record" checkable.
- `session_timeout_minutes` (required): whole minutes, 1 to 480 (eight hours). There is no off setting, on purpose: nobody may switch the protection off. Starting value 10.
- Server fields: `id`, `schema_version`, `created_at`, `created_by`, `updated_at`, `updated_by`, `source`, `deleted_at`, `deleted_by`.

## 3. Rules the schema cannot say

1. Exactly one record exists. The handler creates it (with 10 minutes, unless the sender gives a value) when none exists and refuses a second.
2. Only a super admin may create or change it (`access/policy.py`, write needs SUPER_ONLY). Any signed-in Console person may read it (`view_console`), because the page needs the number to know when to lock.
3. Changes are in place and need the `updated_at` the editor read.
4. Deleting is refused.
5. Every change is also written to the activity log, because the record goes through the Console's logged store.

## 4. Service rules (not in the handler)

1. If no record exists, or it cannot be read, the Console uses 10 minutes. It fails closed, never open.
2. The lock is a lock on the browser page: it clears the key and signs out of Google in that browser. It does NOT make the server refuse an old credential. The admin key stays valid until it is changed, and a Google sign-in lasts about an hour on its own. A server-side session limit is a separate, larger design (parking lot).
3. The window where the super admin saves the number uses it at once. Every other open Console window takes it the next time it signs in or reloads.
4. A remembered admin key or restored Google sign-in that sat idle longer than the limit is dropped when the page loads (closing the tab does not get around the timer). The idle time is shared between windows of the same browser. A person who may not read the setting (no `view_console`) uses the last known number, or 10.

## 5. Open items

- A "warn before sign-out" length is fixed in the page at 60 seconds; it is not a field.
- No per-person or per-role timeouts. One number for everybody.
