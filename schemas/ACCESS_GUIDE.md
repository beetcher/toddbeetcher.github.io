# Access (sign-in and per-person access): Overview

Read this first, then `ACCESS_ROLE_GUIDE.md` and `ACCESS_PERSON_GUIDE.md`. Written October 19, 2026 (thread 18, P-62). Plan: project doc `claude/signin-build-plan.md`.

---

## 1. What it is for

Today the Console has one lock: a single admin key, `ICDT_ADMIN_KEY`, checked the same way by three doors (`enjoy_admin` and the CRUD test door, `enjoy_discovery`, and the Console records door). Everyone with the key is the same person, with every power, and the record of who did what says only `user:admin`.

Access replaces carrying the key around. A person signs in to the Console with their Google account. Google says who they are (a verified email). The two collections here say what they may do:

- `access_role`: a named bundle of capabilities (Super admin, Region head).
- `access_person`: one invited Google account, its role, and an optional region limit.

## 2. How a request is decided (built in the next steps)

1. The Console sends either the admin key or a Google sign-in token as `Authorization: Bearer ...`.
2. One shared check, used by all three doors, turns it into an actor:
   - the admin key is the back door: it acts as a super admin, with the actor string `key:backdoor`;
   - a Google token is verified; its email must be verified by Google and must match an active `access_person` whose role is active; the actor string is `user:<access_person id>` (SCHEMA_RULES section 5).
3. The door names the capability the operation needs (the operation-to-capability table is code, step 3). A super admin passes everything.
4. No matching person, a person switched off, or a role switched off means refused with a plain message ("This Google account has not been invited").

## 3. Rules that hold everywhere

1. Google proves identity only. Nothing about what a person may do comes from Google.
2. A super admin is the only one who can invite, change or switch off access (`manage_access`).
3. The last active super admin cannot be switched off or deleted, so the owner cannot lock themselves out (the admin key also stays as the back door).
4. A removed person is switched off and kept, never erased, so history still names them.
5. The server decides. The Console hides what a role may not use, but hiding is a convenience, never the lock.
6. The admin key, Google keys and any secret live only in the git-ignored env file or Google's console, never in a record, a page or the chat.

## 4. What is not here yet

Enforcing `scope_region_id` (the region head's territory) waits for P-60. Journaling every edit waits for P-46. Delegated admins who can invite others, other sign-in methods, and consumer accounts are not part of this.
