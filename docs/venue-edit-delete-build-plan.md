# Console: edit and delete a venue. Build plan

Status: steps 1 to 4 BUILT and DEPLOYED on 2026-10-09 (edit and delete tested live by Todd; rooms, hours and the popup built after and checkpointed). Step 5 (docs) is this pass; a live walk-through of activating a venue is still to do. Written as a plan on 2026-10-09 (thread 13); the "As built" section below records what changed on the way. It follows the collection manager (picker, venues list, Add venue), live at beetcher.com/console/#/venues. Method: `docs/schema-first-build-method.md`.

## Goal
From the Console, open a venue and change any of its fields (address, contact, rooms, hours, rules, cost, notes), make it active, and delete it. All changes go through the venue handler file (`enjoy_router/crud/venues_crud.py`), which already does the checking, so the page never decides what is valid.

## What already exists (verified 2026-10-09)
- `venues_crud.update` and `soft_delete`: field checks, cross-field rules, slug cannot change, a blank value removes an optional field, `expected_updated_at` refuses a stale edit (`conflict`). 291 in-memory checks pass.
- The `enjoy_admin` endpoint carries them, but `update` and `soft_delete` are switched off (`ADMIN_OPS` in `crud_endpoint.py`). Switching them on is a one-line change plus tests.
- The venue schema is published at https://beetcher.com/schemas/venue.schema.json (fetched and confirmed). The page can read field types, limits and allowed values from it instead of copying them.
- The venues list shows every field in the card detail, read only.

## What the venue schema gives the form (55 editable fields; slug and 7 server-kept fields are read only)
Grouped as the form will show them:

| Section | Fields |
|---|---|
| Basics | name, description, status, is_public_venue (slug shown, locked) |
| Address | street_address, address_line_2, city, state_region, postal_code, country (two capital letters), time_zone (e.g. America/Denver) |
| Map and access | latitude, longitude, parking_description, parking_latitude, parking_longitude, entry_description, entry_latitude, entry_longitude, transit_description |
| Contact | contact_name, contact_email, contact_phone, backup_contact_name, backup_contact_email, backup_contact_phone |
| Booking | website_url, booking_process, booking_lead_days, availability_notes, setup_minutes_before, teardown_minutes_after |
| Facilities and rules | has_wifi, wifi_notes, is_accessible, has_step_free_entry, has_elevator, has_accessible_restroom, accessibility_notes, allows_minors, allows_animals, allows_food, allows_alcohol, requires_insurance, insurance_notes |
| Cost | cost_cents, cost_basis, deposit_cents, cancellation_terms, cost_notes |
| Notes | notes |
| Rooms (list) | per room: label, preferred_occupancy, max_occupancy, is_accessible, seating_layout, equipment (list), notes |
| Hours (list) | per day: day_of_week, opens_at, closes_at (HH:MM) |
| Not in pass 1 | location_pin_ids (the location pin schema is not written yet) |

Rules the page must make easy to meet (the server enforces all of them and names the fields):
- **Active needs:** street_address, city, state_region, postal_code, country, time_zone, contact_name, at least one room, is_accessible, allows_minors, allows_animals, and a contact_email or contact_phone.
- **Pairs:** latitude with longitude (also parking and entry), cost_cents with cost_basis.
- **Code rules:** room labels unique; a room's preferred occupancy not above its maximum; opening time before closing time.

## Design
1. **Edit panel.** Tapping Edit on a venue card opens a full-width panel with collapsible sections (above), Save and Cancel. Sections that hold a problem open themselves.
2. **Form from the schema.** The page fetches the published venue schema once and builds each input from it: short text, a larger box for long text (over 200 characters), a select for allowed values, a number box for numbers (with the schema's limits), email and web-address types for those formats. Field names and rules are never typed into the page by hand.
3. **Yes/No fields have three states: not answered, yes, no.** Absent is not the same as false, and an active venue must have answers to is_accessible, allows_minors and allows_animals.
4. **Only changed fields are sent.** The page compares with the record it loaded. A cleared optional field is sent as a removal. The loaded record's `updated_at` goes along as `expected_updated_at`.
5. **Server refusals appear next to the field**, in plain words, using the same issue-word table as the Add form. For "make active" the server lists every missing field, so the page opens those sections and marks them.
6. **A stale edit** (the venue changed since you opened it) shows "This venue changed since you opened it" with a Reload button. Nothing is overwritten.
7. **Delete.** A Delete button on the card opens an inline confirmation ("Delete this venue? It is hidden from lists but kept.") with Delete and Cancel. Server side it is `soft_delete`: the record stays, with who and when.
8. **Unsaved changes.** Leaving the panel with edits asks first.

## Build steps (each tested before the next)
1. **Server.** Add `update` and `soft_delete` to `ADMIN_OPS`. Extend the in-memory endpoint tests: both ops work, wrong key still 401, stale edit is 409, slug change refused, deleted venue disappears from `list`. Deploy and run a curl check on a throwaway venue.
2. **Edit panel, simple fields.** Everything above except Rooms and Hours. Tested in a real browser at phone width against the real handlers: a field edit, a removal, the latitude-without-longitude refusal, the cost pair, activation refused with the missing-field list, a stale edit.
3. **Delete.** The confirmation and the call, with browser tests.
4. **Rooms and Hours.** Add, change and remove rows. Room labels and times are checked by the server rules above.
5. **Docs and live test.** Method doc and project docs updated; Todd tries it on his phone.

## Decisions for Todd (defaults in bold)
1. **Money:** the schema stores cents. The form shows **dollars** (`75.00`) and converts, so nobody types 7500.
2. **Layout:** **one panel with collapsible sections**, instead of a page per section.
3. **Time zone:** **a text box with the hint "America/Denver"**, not a dropdown of all zones. Country: a two-letter text box with hint "US".
4. **Delete guard:** the schema says never soft-delete a venue that classes point at (set it inactive instead). There are no classes yet, and the page cannot check. **For now the Console warns in words; a venue service enforces it when classes exist.**
5. **Rooms and Hours** come in a second pass (step 4), so the simple fields can be used sooner. Agreed?
6. **Location pins** stay out until their schema exists.

## Not in this build
Google sign-in (the key still locks the Console; the actor stays `user:admin`), undelete, change history beyond updated_at and updated_by, and any other collection's editor (the same panel is built to be reused: a collection supplies its schema and its handler).

## As built (2026-10-09)
Commits: f850f0f (server ops on, edit panel, delete), 2f66d5b (edit form reshaped).

- **Step 1, server:** `update` and `soft_delete` added to `ADMIN_OPS` in `crud_endpoint.py`. `set_review_summary` stays server-only. Endpoint tests extended (update, stale 409, slug refused, activation refused with the missing fields, null removes a field, delete hides and keeps the record). `admin_curl_check.sh` now checks update and delete on an unknown id (404, writes nothing).
- **Step 2, edit panel:** built as planned, form generated from the published schema (`/schemas/venue.schema.json`), only changed fields sent, `expected_updated_at` always sent, server refusals shown next to the field, stale edit refused with a reload button, discard prompt on Cancel and on switching collection.
- **Step 3, delete:** inline confirmation, `soft_delete`, the record is kept with `deleted_at` and `deleted_by` (`user:admin`).

### Change after Todd's first try: the edit form was overwhelming
Todd found the first version unusable: every section loaded at once, about a dozen orange stars, and free-text country and time zone. Todd's suggestion was to drop the required fields from the schema; the decision (Todd agreed, "go") was to **keep the schema and fix the form**. The required list was never the problem (creating a venue needs only name, slug, status and kind of place; the long list applies only when status is active), and the active rule protects the class picker from venues with no address or contact. Changes, all in `console/index.html` only (no schema, server or test changes):
- Opens with Basics, Address and Contact expanded; Rooms and hours is its own collapsed section; everything else sits under one collapsed "More details". A section holding an error opens itself.
- No stars, no legend. Field help text is hidden behind a "Show field help" button.
- "What's needed to make this active?" is a quiet link under Basics. It opens a checklist computed from the schema's own active rule and the form as it stands (updates live as fields are filled).
- Pick lists: country (names; saves the two-letter code; United States first), state or region (US states saved as two-letter codes, plus "Other (type it)" so a region like Ontario works), time zone (US zones first, then the browser's full list). Phone fields use the phone keypad. Money fields are shown in dollars and saved as cents. Friendlier labels (a small `LABELS` table in the page).
- Tested in a real browser at 375 px wide against the real handlers (50+ checks: edit, removal, pairs, bad email, activation refusal, stale edit from a second window, discard prompts, delete, pick lists, checklist, Other region, error opening "More details").

### Decisions settled (defaults accepted)
Dollars in the form; collapsible sections in one panel; Rooms and Hours in a second pass; location pins left out until their schema exists; the delete guard is a warning in words only for now (the venue service will enforce "no classes point here" when classes exist). Time zone and country changed from text boxes to pick lists after Todd's feedback.

### Step 4, rooms and hours (built 2026-10-09)
- Rooms and hours are lists inside the venue record (not collections). The venue edit form has list editors: add, change and remove rows; rooms carry label, preferred and maximum occupancy, accessible, seating layout, equipment and notes; hours carry day, opens and closes (shown as clock times).
- Each venue card has "Rooms: N" and "Open days: N" links that open a scrollable popup (`<dialog>`) with an edit button on each entry, so a room can be changed without opening the whole form. Saves send the whole list with `expected_updated_at`.
- The server's code rules show next to the row: duplicate room label, preferred above maximum, opens not before closes.
- Guards added once classes existed (venue service): a venue with live classes cannot be deleted (409, `id:in_use`, the message names the classes); a room used by a live class cannot be removed, renamed or shrunk below the class's maximum (400, `rooms:in_use`). This closes the "delete guard" decision that had been a warning in words only. Details: `docs/classes-build.md`.
- Tested at 375 px in a headless browser against the real handlers.

### Still to do
- Live walk-through: fill in a venue, activate it, schedule a class there, try the delete and room guards on live data.
- Open: Google sign-in replacing the key; undelete; whether venue activation should demand so many fields (see `docs/classes-build.md`).
