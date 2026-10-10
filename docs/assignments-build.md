# Registration assignments: handler, service rules, Needs attention, one-touch assign and Console (as built)

Built 2026-10-09 (thread 13), tested in memory and in a headless browser at phone width; NOT yet deployed when this was written (Todd deploys after his movie). Third collection through the schema-first method (`docs/schema-first-build-method.md`); same shape as classes (`docs/classes-build.md`). An assignment links one registration request to one scheduled class and records the decision (accepted, overflow, waitlisted, declined, cancelled).

## Decisions (Todd, 2026-10-09)
1. Keep assignments until the owner deletes them (a written retention policy; nothing enforces it).
2. The server decides the status first. If it cannot, it raises an exception that shows as **Needs attention** on Console Home for the operator.
3. Stations: an Assignments station, a roster popup on class cards, and a one-touch assign button on each request card, built from the server's suggestion ("the delicate mission, tweak at the end").
4. A private or group request may only go into the class made from it (`source_request_id`).
5. The request's own `processing_status` is left untouched.
6. Payments and transaction ids stay out (the note and transaction id fields can be edited later, nothing else).

## What was built
| Piece | File | Role |
|---|---|---|
| Handler | `enjoy_router/crud/registration_assignments_crud.py` | create, get, list, update (note and transaction ids only), soft_delete for `registration_assignments`. Knows only its own collection. |
| Service | `enjoy_router/crud/assignments_service.py` | Wraps the handler; looks at requests and classes; decides status; keeps class counts; offers `suggest` and `queue`. |
| Classes | `scheduled_classes_crud.py`, `classes_service.py` | Counts setter `set_registration_counts`; `capacity_max` cannot drop below `registered_count`; a class holding registrations cannot be deleted (409 `id:in_use`). |
| Dispatcher | `enjoy_router/crud_endpoint.py` | `registration_assignments` maps to the service. New ops `suggest` and `queue`, in `ADMIN_OPS`, answered only by modules that have them (else 400 `op:not_supported`). |
| Schema | `schemas/registration_assignment.schema.json` | `x_retention` and `x_history: linked_records`. |
| Indexes | `enjoy_router/firestore.indexes.json` | 18 now: status, scheduled_class_id, request_id, each with created_at DESC, on real and test collections. |
| Console | `console/index.html` | Assignments station (`#/assignments`), Needs attention panel on Home, one-touch buttons on request cards, roster popup from class cards, manuals. |

## The model: decisions are never overwritten (x_history `linked_records`)
Changing a decision creates a NEW record whose `previous_id` names the old one. A move to another class is a cancel plus a new assignment. The **standing** decision for a request and class is the record that is not soft-deleted and not named as `previous_id` by another record. Seat statuses `accepted` and `overflow` count toward the class `registered_count`; `waitlisted` counts toward `waitlist_count`. The Console list shows standing decisions by default, with "Also show replaced decisions" to see history.

## Service rules
- Request and class must exist: `request_id:not_found`, `scheduled_class_id:not_found`.
- Private or group request only into the class whose `source_request_id` equals it: `scheduled_class_id:wrong_class`.
- Seats may not exceed the request's `attendee_count`: `attendee_count:out_of_range`.
- A decision identical to the standing one is refused: `status:unchanged`.
- **Automatic (`judge`)** when no status is given: the class must be `enrolling`; accepted up to the target; overflow up to the maximum (a party is never split); otherwise waitlisted if the class has a waitlist with room; otherwise a conflict (`class_closed`, `class_full`, `waitlist_full`).
- **By hand (`verify`)**: operator-chosen status is checked (`over_target`, `class_full`, `waitlist_off`, `waitlist_full`, `class_closed`); declined and cancelled are always allowed.
- Refusals use code `conflict` (HTTP 409).
- Class counts are rewritten in the same transaction as the create; a failed count write rolls the whole thing back (server_error), tested.
- Assignment delete is refused (`id:not_allowed`); update accepts only note and transaction ids (`immutable` for request_id, scheduled_class_id, status, attendee_count).

## The two new ops
- `suggest(request_id)`: the best class and status the server would pick, with seats and a plain reason.
- `queue(limit=100)`: one pass over the newest requests; each is **assigned**, **ready** (has a suggestion), **needs_attention** (class_closed, class_full, waitlist_full, class_not_found), **no_class** (`no_class_fits` or `no_class_yet`), or **closed** (declined or cancelled), plus counts.

## Console
- Request cards show the queue state; **ready** requests get an orange one-touch button: "Assign: Accept N seats in <class>". It creates the assignment with the server choosing the status.
- Needs attention: a panel on Home (above "Flight basics") with a badge, listing requests the server could not place, each with "Decide by hand", which opens the Assignments station with the request pre-filled.
- Assignments station: list, tick-box filters, New decision form, Change decision, Decide again automatically, Edit note.
- Roster popup: the Registered and Waiting chips on a class card open it (registered, waitlisted, declined or cancelled, seats taken versus target and maximum) with an "Open in Assignments" button.
- Manuals: a Station 4 Assignments manual; Requests and Classes manuals updated.

## Known limits
- Two decisions made at the same instant for one class could overshoot capacity (single operator assumed).
- `queue` looks at the newest 100 requests and 500 assignments.
- Creating a class FROM a private or group request (which sets `source_request_id`) is not built yet; tests seed it.
- The request's `processing_status` is not updated by assignments (decision 5).
- No venue is active yet, so live scheduling demos need one.

## Tests
- `run_assignment_tests.py`: 116 checks, mutation-checked (19 mutants, none survived).
- `run_crud_endpoint_tests.py` extended; `run_class_tests.py` 164 and `run_crud_tests.py` 291 still pass.
- Browser tests at 375 px: `ui_assign_test.py` (about 45 checks) plus the older suites (venues, lists, popup, classes, race, home).
- `admin_curl_check.sh` gained read-only checks for queue, list, list by status, suggest unknown (404), create unknown request (400), delete refused (400), venues queue (400).

## Deploy steps (Todd)
From `enjoy_router/`: `python3 sync_schemas.py`, then `firebase deploy --only functions:enjoy,firestore:indexes --project launch-ai-workshop` (indexes take a few minutes), then `./admin_curl_check.sh`. Also run `python3 schemas/check.py` once (needs `pip install jsonschema`).
