# CMS (Communication Management System): Programming Guide

For anyone who writes code that sends a message, or code inside the CMS. The full design and the reasons are in the project document `claude/cms-architecture-spec.md`; this guide is the part a programmer needs in the repo. Read `SCHEMA_RULES.md` first. Written October 15, 2026 (thread 14). Status: the schemas exist; the code (`enjoy_router/comms/`, `enjoy_router/launch_comms/`) is built in steps 2 and 3.

---

## 1. The one rule

Any part of the product that wants to communicate calls the CMS and says WHAT happened and TO WHOM. The CMS decides everything else: which wording, which channel, how it is formatted and sent, what is logged.

- WHEN to communicate, and WHO to tell, is the caller's business and may live anywhere.
- HOW to communicate lives only in the CMS.
- WHAT the message says lives in template data (`message_template`), edited in the Console.
- A caller never imports an email library, builds a subject line, picks a channel or writes a log entry.

## 2. The call

```
notify(kind, recipient, context, by, trigger, refs, audience=None, suppress=None, dedupe_key=None) -> Result
notify_many(items, time_budget_s) -> list[Result]
```

- `kind`: a registered kind. Today `request_received` and `placement_confirmation`.
- `recipient`: `{type: "individual", individual_id}` or `{type: "adhoc", name, email?, phone?}` (the receipt goes out before the requester has an individual record).
- `context`: the facts of the event, plain JSON, validated against the kind's fact schema (`schemas/message_kinds/<kind>.facts.schema.json`). Facts only: no wording, no channel.
- `by`: who caused it. `trigger`: `automatic` or `manual`.
- `refs`: ids of the records the message belongs to (`request_id`, `scheduled_class_id`, `attendance_id`). Stored as fields of the log entry.
- `audience`: selects the wording; default is `default`.
- `suppress`: people or addresses that must not be contacted for this event (the "keep John out" rule). Separate from `context`.
- `dedupe_key`: optional; the default is kind + recipient + sorted refs + the event version in `context`.
- Result: `status` (`sent`, `failed`, `unknown`, `not_sent`, `skipped`), `channel`, `reason`, `log_id`.

Guarantees: `notify` never raises into the caller; the caller's own change never fails or rolls back because a message failed; callers call it only AFTER their change is committed; `context` is plain JSON so the call can be queued later without changing any caller.

## 3. The pipeline (fixed order)

1. Validate: kind registered, context valid. Else `not_sent` / `unknown_kind` or `invalid_context`.
2. Mode: `off` logs `skipped` / `cms_off` and stops.
3. Dedupe: same key already `sent` or `unknown` is `skipped` / `duplicate`. A manual send bypasses this.
4. Resolve the recipient through the directory. No usable contact: `not_sent` / `no_contact`.
5. Suppression: in `suppress`, or muted: `skipped` / `excluded` or `muted`.
6. Choose the channel from the person's preference. No adapter for it: `not_sent` / `channel_unavailable`. One channel only, never both.
7. Find the published, active template for (kind, channel, audience). None: `not_sent` / `no_template`.
8. Render. A needed fact is missing: `not_sent` / `incomplete`.
9. Apply the test redirect, if one is set.
10. Mode `log_only` stops here: `skipped` / `log_only`.
11. Send. Accepted: `sent` / `ok`. Refused: `failed` / `adapter_error`. No answer in time: `unknown` / `timeout`.
12. Write exactly one `communication_log` entry, whatever happened.
13. Return the Result.

## 4. Ports: what the product supplies

The core (`comms/`) imports nothing from LAUNCH. It talks to the product through four ports; LAUNCH implements them in `launch_comms/`.

- `RecipientDirectory`: `lookup(recipient) -> Contact` (name, email, phone, backup phone, preferred channel, muted).
- `TemplateStore`: reads published templates.
- `LogStore`: appends and reads log entries.
- `Channel` adapters: `can_carry(content)` and `send(contact, content)`. Email is first (formatting here, transport in `smtp_transport.py`). A channel never knows any kind.

The person's preference today is `individual.prefers_email` (a boolean; absent means the one contact given, email if both). A person who prefers text and has no text channel yet gets `not_sent` / `channel_unavailable` and appears in the hand-contact queue.

## 5. Adding or removing a flow

1. Write the kind's fact schema in `schemas/message_kinds/<kind>.facts.schema.json`: the facts, which are required, the audiences, the triggers (as text for the Flows tab), the dedupe rule, and any attachment.
2. Register it in `registry.json` under `message_kinds`.
3. Write the fact builder in `launch_comms/` (it turns records into facts, including derived ones such as `when_day`).
4. Seed or write its template in the Console.
5. Add the trigger in the owning service: one `notify` call after commit.
Removing a flow: switch its template off in the Console, or delete the registration and the one `notify` call. Nothing else changes.

## 6. Template blocks

See `MESSAGE_TEMPLATE_GUIDE.md`. The reference renderer `schemas/message_kinds/reference_render.py` is the executable definition of the block format, and `schemas/message_kinds/golden_masters.json` holds the exact output of the original two emails. `schemas/check.py` proves the seed templates reproduce them byte for byte.

## 7. Modes and settings

The send mode comes from the environment: `off` (nothing rendered or sent; each call logged `skipped`), `log_only` (rendered and logged, never sent), `live`. During the transition `ICDT_CMS_ENABLED=true` means live and false means off. Everything else is the `comms_setting` record (`COMMS_SETTING_GUIDE.md`); the secrets stay in the environment.

## 8. The log

See `COMMUNICATION_LOG_GUIDE.md`. Message history on an attendance row or a request card is a view of the log. The old fields `acknowledgment_email_status`, `acknowledgment_email_attempted_at`, `acknowledgment_email_error_code` (on the request) and `correspondence` (on the attendance) are DEPRECATED when the emails move in: never written again, and removed from the schemas only after the old test records are cleaned up.

## 9. The kinds today

| kind | audience | recipient | when |
|---|---|---|---|
| `request_received` | `requester` | adhoc (name and email on the request) | a registration request is saved for the first time |
| `placement_confirmation` | `student` | individual | a student is placed (assigned or confirmed) in a scheduled class with venue and start time; or an operator presses Send confirmation email |

## 10. Rules (each becomes a named test)

R-1 the core imports nothing from LAUNCH. R-2 callers use only `notify` and `notify_many`. R-3 `notify` never raises and never undoes the caller's change. R-4 callers notify only after commit. R-5 context is plain JSON checked against the fact schema. R-6 the pipeline order is fixed. R-7 exactly one log entry per recipient per call. R-8 one channel per person per message. R-9 duplicate protection by explicit key; manual bypasses. R-10 `suppress` and mute are enforced by the CMS. R-11 template found by kind, channel, audience; only published and active. R-12 a placeholder must be a fact of the kind; a missing needed fact is `incomplete`. R-13 modes and test redirect. R-14 the reason to status map is closed. R-15 the log is append-only and server-written. R-16 the log is history: a merge, an erase or a delete of a person never edits, hides or removes a log entry (Todd, 2026-10-15). R-17 message text is not stored. R-18 adapters and stores pass the contract tests; channels know no kinds. R-19 settings are data; the environment holds secrets and mode only. R-20 `not_sent` entries wait in the hand-contact queue until handled. R-21 edits are drafts until published; versions kept. R-22 `notify_many` has a time budget; people not reached are logged `time_budget`. R-23 `contract_version` on the call and the log. R-24 preference resolved as the individual schema says. R-25 one shared calendar-event helper. R-26 `message_ref` recorded when returned.
