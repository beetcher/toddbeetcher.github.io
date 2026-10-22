# Performance event: Programming Guide

For anyone who writes code against `schemas/performance_event.schema.json`: the `record_timing` op, the Performance station and the server's timing of the who-am-I call. Written October 22, 2026 (thread 22, Todd's decision: "create a log that's showing where the delay is happening and display that in Performance ... it will be a new station ... an admin or super admin panel that allows one to view performance of things, like login time, or Spend, etc.").

---

## 1. What it is

One timing measurement of the Console. Today only `kind: sign_in`: how long a sign-in took, by step, measured by the page of the person who signed in. The aim is to see where the wait is: Google, the server waking up (a cold start), the server's own work, or loading the first lists.

## 2. Fields

- `kind` (required): `sign_in`. `device` (required): `phone` or `desktop` (the page decides from the screen width). `method` (required): `google` or `key`.
- `total_ms` (required): from Google accepting the sign-in (or the key being sent) until the Console is ready to open. The decorative "Liftoff!" pause is not counted.
- `check_ms`: the first server call (who is signed in), including any cold start. `load_ms`: loading the first lists after it. `server_ms`: what the server itself spent on that first call, as the server measured it. `cold`: the answering server instance had just woken up. All optional; all whole milliseconds, 0 to 600000.
- `role_key`: the sender's role, set by the server. Server fields: `id`, `schema_version`, `created_at`, `created_by` (the person, as `user:<id>`), `updated_at`, `updated_by`, `source`, `deleted_at`, `deleted_by` (the last two are never used: there are no deletes).

## 3. Rules the schema cannot say

1. Records are created only through the `record_timing` op on the Console door. The sender cannot name who it is for: the server stamps `created_by` and `role_key`. There is no edit and no delete through any door.
2. Anyone signed in to the Console may send one (an Instructor too). The admin key may. The Global Inspector may not (view only: the server refuses every write).
3. One record per person per 10 seconds is kept; more are dropped quietly (the answer says `recorded: false`). Best effort per server instance.
4. Reading needs `view_performance` (a global capability from the role; a super admin holds every capability). The Global Inspector reads it too, view only.
5. No name, email or token is stored. The station shows the role and the device, not a person's name.
6. Not in the activity log: it is a log of its own (see ACTIVITY_EVENT_GUIDE.md section 3).
7. `cold` and `server_ms` come from the server's reply to the who-am-I call (`me`), which now carries `server_ms` and `cold`.

## 4. Open items

- Records are kept forever; the station shows the last 90 days. A purge job for older ones is parked.
- Only sign-in is measured. More sections (Spend and others) are planned for the same station.
