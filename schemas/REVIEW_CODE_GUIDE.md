# Review code: Programming Guide

For anyone who writes code against `schemas/review_code.schema.json`: the review-code module (`enjoy_router/access/review_code.py`), the two Console operations and the Access station's "Review access code" section. Read `CONSOLE_SETTING_GUIDE.md` first; this record follows the same one-record pattern.

---

## 1. What it is

A temporary, view-only way into the Console for a reviewer (a person or a model that cannot use Google sign-in). A super admin types a code in the Access station. The code works for 24 hours. Typing another code replaces it and restarts the 24 hours. There is only ever one code. The reviewer types the code into the Console's existing "Key" box and is signed in as the view-only Global Inspector: everything visible, private contact details masked, nothing changeable.

## 2. Fields

- `access_key` (required): always `current`. Ids are UUIDs, so this field is what makes "exactly one record" checkable.
- `code_hash`: a salted hash (HMAC-SHA256, hex) of the code. The code itself is never kept. Never returned. Marked personal so the activity log withholds the value.
- `salt`: random text mixed into the hash, new for every code. Never returned. Withheld from the activity log.
- `expires_at`: when the code stops working (UTC), 24 hours after it was set. The server compares it with its own clock on every request.
- Server fields: `id`, `schema_version`, `created_at`, `created_by`, `updated_at`, `updated_by`, `source`, `deleted_at`, `deleted_by`. `updated_at` and `updated_by` say when and by whom the current code was set.

All fields are set by the server only (readOnly). A sender may supply nothing but `access_key`.

## 3. Rules the schema cannot say

1. Exactly one record exists. Setting a code creates it when none exists and replaces the hash, salt and expiry when it does. An older code stops working the moment a new one is set.
2. A code is 8 to 64 printable characters (spaces allowed). It may not equal the admin key and may not look like a Google token (two dots). Short codes are refused.
3. Only a super admin (or the admin key) may set a code or ask its status, through the Console door's two operations `set_review_code` and `review_code_status`. The collection is blocked from the generic CRUD operations, so no list or get can ever return it. A view-only account, a manager and every other role are refused, and so is a sign-in by code.
4. `review_code_status` returns only whether a code is active and when it expires (and who set it). Never the hash, the salt or the code.
5. `set_review_code` returns the expiry and nothing else. The Console shows the code once from what the super admin typed; the server cannot show it again.
6. A sign-in by code acts as the Global Inspector role (looked up by its key, so it follows that role's capabilities): view only at every door, private details masked, activity actor text "Review access". If that role is missing or switched off, the code is refused.
7. A sign-in by code may not start, step or stop a Discovery run (reading, quoting and the ZIP lookup are allowed).
8. Wrong codes count against the visitor's rate limit like any wrong credential.
9. Every change is also written to the activity log (hash and salt withheld, never the code), because the record goes through the Console's logged store.

## 4. Service rules (not in the handler)

1. The expiry is judged on the server on every request; the page never decides it. After expiry the next request is refused as unauthorized and the Console locks.
2. The admin key is unchanged and still opens the Console as a super admin.
3. Nothing here is a password manager: the code is meant to be short-lived and easy to type.

## 5. Open items

- No "turn off now" button (Todd, 2026-10-22: typing a new code is how to shut the old one).
- The reviewer's sign-in is not listed in the Performance station by name.
