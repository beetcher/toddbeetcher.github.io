# Scheduled classes: handler, service rules, venue guards and Console (as built)

Built, deployed and checkpointed 2026-10-09 (thread 13). Second collection through the schema-first method (`docs/schema-first-build-method.md`); the first to need a service layer. Test of capability, asked for by Todd: a new collection's CRUD handler and its Console screens in the SAME build. Live at https://beetcher.com/console/#/classes. Commits: 03e97fe (classes), a903d28 (rooms and hours popup); the tick-box filters were page-only and checkpointed afterwards.

## What was built
| Piece | File | Role |
|---|---|---|
| Handler | `enjoy_router/crud/scheduled_classes_crud.py` | create, get, list, update, soft_delete, set_review_summary for `scheduled_classes`. Knows only its own collection. |
| Service | `enjoy_router/crud/classes_service.py` | Wraps the handler; adds the rules that look at the venues collection. |
| Venue service | `enjoy_router/crud/venues_service.py` | Wraps the venue handler; adds the guards that look at classes. |
| Dispatcher | `enjoy_router/crud_endpoint.py` | `HANDLERS = {"venues": venues_service, "scheduled_classes": classes_service}`. Both doors (`enjoy_crud_test`, `enjoy_admin`) reach the services, not the bare handlers. |
| Schema | `schemas/scheduled_class.schema.json` | `x_retention` and `x_history` declared (see decisions). |
| Indexes | `enjoy_router/firestore.indexes.json` | 12 composite indexes now: (field, title) for status, class_type, venue_id, is_public on `scheduled_classes` and `test_scheduled_classes`, plus the venue ones. |
| Console | `console/index.html` | Classes view (`#/classes`), generated from the published schema `/schemas/scheduled_class.schema.json`. |

## Rules, by where they live (section 4.1 of the method)
**In the schema:** field types, limits, allowed values, which fields exist. **In the handler's rules block** (own fields only):
- `capacity_minimum` <= `capacity_target` <= `capacity_max` (issues `capacity_minimum:out_of_range`, `capacity_max:out_of_range`).
- `cancelled_reason` only when status is cancelled (`not_allowed`).
- `source_request_id` is not for workshops.
- Slug cannot change and is unique including soft-deleted classes.
- Counts (registered, waitlist, attended, review) start at 0 and are server-kept; the Console does not edit them.

**In the class service** (look at venues):
- The venue must exist and not be deleted (`venue_id:not_found`).
- A room label needs a venue (`venue_id:required`); the room must exist in that venue, ignoring case (`venue_room_label:not_found`).
- `capacity_max` may not exceed the room's `max_occupancy` (`capacity_max:out_of_range`).
- A class that is scheduled or enrolling needs an ACTIVE venue (`venue_id:inactive`).

**In the venue service** (look at classes):
- A venue with live classes cannot be soft-deleted: 409 `conflict`, issue `id:in_use`.
- A room used by a live class cannot be removed, renamed, or shrunk below that class's `capacity_max`: 400, issue `rooms:in_use`.
- Setting a venue inactive is allowed even when classes point at it.

## The hook that made services possible
Both handlers' `update` (and `create`) take an optional `check(doc)` callback, run on the final merged record, and `update` takes `check_fields`: fields that force the whole-record path (one read) even though no schema rule involves them. The handler stays ignorant of other collections; the service passes the callback. Classes pass `CLASS_CHECK_FIELDS = (venue_id, venue_room_label, capacity_max, status)`; venues pass `("rooms",)`.

## List support
No filter, or exactly ONE of `status`, `class_type`, `venue_id`, `is_public`, ordered by `title`; no filter may also use `-created_at`. Not ordered by `starts_at`: Firestore drops documents that lack the ordered field, so a class with no start time would vanish from the list. The Console sorts by start time itself.

## Console
- **Classes view:** list of cards, add form (capacity defaults 6 / 10 / 15), edit panel with the same section pattern as venues, delete with inline confirm, readiness list ("what is needed to schedule this class") computed from the service rules.
- **Venue and room pickers:** venue is a drop-down of live venues; room is a drop-down of that venue's rooms.
- **Start time** is typed in the class's time zone and stored as UTC (`zonedToUtc` / `utcToZoned`, Intl API); the time zone defaults from the venue.
- **Hidden for now:** `instructor_ids` and `promotion_ids` (their collections do not exist), and the counts.
- **Tick-box filters** (added after Todd created a class that did not appear in a status-filtered list): one tick box per status plus class type and public/private, all ticked by default; ticking all shows everything, unticking narrows. Choices kept per tab in sessionStorage (`console_class_filters`). A new or edited class never disappears: the list is re-read after add and save. A latest-load-wins counter (`cSeq`) means a slow earlier load cannot overwrite a newer one; a failed load shows the error with a Retry button.
- **Rooms and hours editing for venues** (same day, step 4 of the venue plan): lists editable inside the venue edit form, and a popup (`<dialog>`) opened from the "Rooms: N" and "Open days: N" links on each venue card, with an edit button per entry.

## Tests
- `enjoy_router/run_class_tests.py`: 164 in-memory checks, mutation-checked (each rule deliberately broken once to prove a test fails).
- `enjoy_router/run_crud_endpoint_tests.py`: class and guard checks added to the endpoint suite.
- Headless Chromium at 375 px wide against the real handlers: classes, edit, lists, popup, filters, and a load-race test.
- `enjoy_router/admin_curl_check.sh`: read-only live check (class list, filtered list, unknown ids 404, `set_review_summary` refused). Passed after deploy.

## Decisions (Todd, 2026-10-09)
1. Retention: "Keep classes until the owner deletes them." A written policy only; nothing enforces it yet. `x_history` is `in_place`.
2. Instructor and promotion fields stay out of the form until those collections exist.
3. Start time is typed in the venue's time zone.
4. A scheduled or enrolling class needs an active venue.
5. Filters are tick boxes, all ticked by default (Todd's request).

## Known gaps and not yet exercised live
- No venue is active yet, so a scheduled or enrolling class cannot be saved against live data. To demo: fill in the venue's active requirements (address, contact, accessibility, minors, animals, one room), activate it, then schedule a class. Todd noticed activation re-asks for all those fields; this is by design. Options if it gets in the way: fill them in, loosen the active rule in the venue schema, or leave it.
- The venue delete guard and room guards are tested in memory and in the browser harness, not on live data.
- Deleting a class is not guarded against registrations: the registration link does not exist yet.
- Venues list still has the single status drop-down (tick boxes only on classes).
- Actor is `user:admin` until Google sign-in.
- Not seen on a real phone, only at 375 px in a headless browser.

## Next
Registration request to class: a `registration_assignment` collection with service rules (class must be enrolling, capacity, waitlist) and the Console surface. Needs Todd's Go and a plan agreed first.
