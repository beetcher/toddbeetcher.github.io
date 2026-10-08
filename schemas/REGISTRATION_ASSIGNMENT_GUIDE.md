# Registration Assignment: Programming Guide

For anyone who writes code against `schemas/registration_assignment.schema.json`: the processing handlers, the dashboard, the endpoints. Read `SCHEMA_RULES.md` first, then `REGISTRATION_REQUEST_GUIDE.md` and `SCHEDULED_CLASS_GUIDE.md`. Where a decision is Claude's proposal and not Todd's it is marked **(proposal)**; where nothing is decided it is marked **(open)**.

Written October 8, 2026, from the schema conversation (thread 12).

---

## 1. What an assignment is

A request is not a registration. An **assignment** is what processing writes after it decides: this party is in, in overflow, or waitlisted for this scheduled class. It is the link between a registration request and a scheduled class.

The chain, in order:
1. **Registration request** (`registration_requests`): what comes in from the public pages. Unfiltered. Never changes except its processing status.
2. **Registration assignment** (`registration_assignments`): the decision. Written by processing, never by a public page.
3. **Scheduled class** (`scheduled_classes`): the unit people are assigned to. One date, one time, one room at one venue. It is of a type: private, group or workshop.

Todd: private, group and workshop are all scheduled classes of a certain type. A private or group request has no class when it arrives; when processing accepts it, a scheduled class of that type is created (with `source_request_id` pointing back) and the party is assigned to it. A class request picks an existing workshop.

## 2. Fields

### What is being decided
- `request_id`: the registration request. Required.
- `scheduled_class_id`: the class the party is assigned to. Required. For a private or group request it is the class processing created.
- `status`: required. `accepted` (a seat up to the class target), `overflow` (a seat between target and maximum), `waitlisted` (waiting for a seat), `declined` (not given a seat), `cancelled` (was in, now out). The class's `registered_count` counts accepted and overflow seats only **(proposal)**.
- `attendee_count`: how many seats this decision covers, 1 to 50. Required. May be fewer than the request asked for, for example when only part of a group fits.
- `decision_note`: why, in the organizer's words. Optional.

### Program
- `program_slug`: which program the assignment belongs to, copied from the class. Set by the server. See `SCHEMA_RULES.md`.

### Decision record (set by the server)
- `decided_at` and `decided_by`: when and who. Actors look like `user:<uuid>` or `system:<handler>`.

### Identity and provenance (set by the server)
`id`, `schema_version`, `created_at`, `created_by`, `updated_at`, `updated_by`, `source` (`dashboard`, `import` or `system`), `previous_id`, `deleted_at`, `deleted_by`.

## 3. Rules the endpoint enforces

- The request and the class must exist.
- `attendee_count` may not exceed the request's `attendee_count`.
- Status changes are new linked records: a waitlisted party who is later accepted gets a new assignment whose `previous_id` is the waitlisted one. The earlier record is kept as history **(proposal)**.
- Only a class that is `enrolling` (or a private or group class being created for this request) can receive new accepted, overflow or waitlisted assignments.
- Any fields marked readOnly are rejected if a sender includes them.

## 4. What it deliberately does not carry

No names, emails, phone numbers or other personal details. They stay on the request. This keeps one copy of personal data and makes it easier to protect and to delete under the retention rule. A dashboard that needs names for a class looks up the requests by `request_id`.

## 5. Open

- Payment: whether `is_paid` and the payment id move from the request to the assignment once payments exist **(open)**. Today payment fields live on the request.
- A person record: later the assignment may point at individual people, not only at a request **(open)**.
- Retention period (`x_retention` is undecided; required before launch).
- Series: a party that wants several sessions is not modeled; each scheduled class is one date and time **(open)**.
