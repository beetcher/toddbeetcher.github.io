# Schema-first build method

How we build the data foundation of a new product, in a fixed order, with a fixed shape, so that any person or any AI agent can find things, extend them, and not make spaghetti.

Status: DRAFT 2, written 2026-10-09 from Todd Beetcher's design conversation (LAUNCH build, thread 13), with every gap from the draft-1 gap analysis integrated (section 15 is the register). Todd settled gaps 1 to 5 on 2026-10-09 by accepting the proposed defaults. The shared kit and the first handler file now exist and pass in-memory tests (`enjoy_router/crud/schema_kit.py` and `enjoy_router/crud/venues_crud.py`, the model file); the Firestore store and a key-locked test endpoint (`enjoy_crud_test`, test-prefixed collections only) are deployed and were exercised with curl on 2026-10-09, and no service calls the handlers yet. Section 14 says what exists today and what does not.

How to read this document:
- Sections 1 to 13 are **portable**. They are the method and apply to any project.
- Section 14 is **LAUNCH-specific** (this repo, this Firebase project). Another project replaces section 14 and keeps the rest.
- **(Todd)** marks a decision Todd made. **(proposal)** marks a suggestion not yet confirmed. **(open)** marks something undecided.
- The data conventions (naming, ids, timestamps, readOnly fields, error shapes, privacy) are not repeated here. They live in `schemas/SCHEMA_RULES.md`. Read that too. Some of its rules are LAUNCH-specific until that file is split into a portable core and a LAUNCH appendix; section 14.5 says which.
- Section 15 is the gap register: every gap found in review, where it is closed in this document, and which ones still need the owner's decision.

---

## 1. The foundation principle (Todd)

Imagine there is no standard way to build the foundation of a house. A 1,500 square foot ranch and a 10,000 square foot mansion do not start with the roof, the painted windows or the deck. Everybody starts with the foundation, and the foundation follows certain principles no matter what is being built: you clear the land, you move the dirt, you put in markers. It is consistent every time.

That is what this document establishes for software. Data is the foundation. The schema, the layer that guards the data, and the order we build in are the same for every product. The screens, the emails and the dashboards are the roof and the windows, and they come last.

Why it matters when an AI agent is doing the typing: left alone, every agent, and every session of the same agent, invents its own approach. Nothing is wrong with any single piece, but there is no standard, so nobody (human or AI) can tell where a rule lives or what changing it will break. A fixed method is how a build stays understandable.

## 2. The order of work

Always in this order. Do not start a step before the one above it is settled.

1. **Define the data** as schemas: one schema file per kind of record (section 5). Written first, before any code.
2. **Register** every schema in the registry (collection name, schema file, guide, examples, version).
3. **Write a guide** for each schema: why each field exists, in the owner's intent, with decisions marked.
4. **Write examples and test records**: valid and invalid, each named for what is wrong with it.
5. **Build the CRUD handler file** for the collection (section 6) and test it in memory against the test records.
6. **Build the services**: the business logic, which uses the handler files (section 4).
7. **Build the endpoints**: thin doors in front of the services.
8. **Test through the endpoints** with a script (and curl), against an emulator or a test area.
9. **Build the surfaces last**: web pages, dashboards, emails.

Todd's rule of thumb: "Don't conflate schema architecture with web surface design." The schema lists everything that could be collected. A screen may ask for only some of it.

## 3. Vocabulary

Plain definitions, because the same word can mean two things.

- **Collection** (a "room"): a named group of documents in the database, for example `venues`. Plural, snake_case.
- **Document**: one record in a collection. It has a UUID `id`.
- **Schema**: a *design document*. A plain text file that lists a collection's fields and the characteristics of each field (type, allowed values, length, required, read-only). It has no code in it and nothing runs inside it. It is a reference for people, and a precise one.
- **JSON Schema**: the standard format our schema files are written in. Because it is standard, ready-made libraries can read any such file.
- **Checker** (a "validator"): a generic, downloadable library that reads a schema file and answers "is this data valid against it?". We use `jsonschema` (Python). The checker is passive: it judges only what it is handed, and it cannot call back to ask for more data. Think of the schema as the blueprint and the checker as the inspector who knows how to read any blueprint.
- **Registry**: `schemas/registry.json`, the list of every schema with its collection name. Code looks the collection up here and never types it by hand.
- **CRUD handler file**: one file per collection holding its five operations (section 6). The only code that reads or writes that collection.
- **Service**: business logic. It decides what should happen and calls handler files to do the data work.
- **Endpoint**: a deployed, public or private web address that receives a request and passes it to a service.
- **Store**: the thing that actually talks to the database (Firestore in production, an in-memory stand-in in tests). The handler files use it. Services never do.
- **Rules block**: the one marked section inside a handler file that holds that collection's own field logic (section 6.3).
- **Shared kit**: one small module every handler file uses for the mechanical parts: loading a schema through the registry, checking a field or a document, finding the fields involved in cross-field rules, stamping the standard fields (section 6.5).
- **Handler test records**: a data file per collection that describes handler test cases (section 11).
- **Service rule**: a rule that involves another collection, the outside world, or who may see what. It belongs to a service, never to a handler (section 4.1).

## 4. The layers and who may call whom (Todd)

```
  Surfaces     web pages, dashboard, emails
     |
  Endpoints    thin doors: method, size, JSON, rate limit, lock -> call a service
     |
  Services     business logic: the rules of the product
     |
  CRUD handler files (one per collection)    <-- the protective shield
     |
  Store        Firestore (or the in-memory test store)
     |
  Data         collections of documents
```

Rules:

1. **Every call goes down one layer at a time.** A service never talks to the Store directly. An endpoint never calls a handler file directly. A surface never talks to anything but an endpoint.
2. **Handler files are not deployed endpoints.** They have no web address. They are plain functions inside the codebase, callable only by other modules in the same project. That is the point: they are a shield around the doorway into the data. (Todd: "There's no public call into them.")
3. **Firestore itself is closed to browsers.** The database rules deny all direct web reads and writes. The only way in is through our functions, which run with a service account.
4. **Handler files contain no business logic.** They validate and write. They do not know why.
5. **Business logic calls handlers.** When a service needs to create a record, it calls that collection's create function with the data, and gets back either success or a list of problems.
6. **A handler never reads another collection.** If a rule needs a second collection, it is a service rule.

### 4.1 Where each kind of rule lives

Every rule has exactly one home. When a rule is found, place it with this table before writing any code. When a collection is designed, list its rules by these kinds (section 10, step 5), including the service rules, even though the services are built later, so they are not lost.

| Kind of rule | Example | Lives in |
|---|---|---|
| One field's type, format, length or allowed values | email format; country is two capital letters | the schema |
| Fields in the same document that depend on each other, and JSON Schema can say it | an active venue requires an address; latitude requires longitude | the schema |
| Fields in the same document that depend on each other, and JSON Schema cannot say it | names listed cannot exceed the headcount; a room's preferred occupancy is not above its maximum | the rules block of that collection's handler file |
| Anything involving another collection or the outside world | the venue named by a class must exist; never delete a venue that classes point at; a class takes requests only when enrolling | a service |
| Who may see what | hide contact details and private addresses from the public class list | a service or an endpoint |
| Whether something should happen at all | flag a request that brings minors to a venue that disallows them | a service |

## 5. The schema

- One schema file per kind of record, singular, `<name>.schema.json`, in the schema folder (LAUNCH: `/schemas`). JSON Schema draft 2020-12.
- It describes every field that can exist on the stored record. Fields only the server may set are marked `"readOnly": true`.
- Field naming, ids, timestamps, read-only provenance fields, soft delete, privacy markers and error shapes are governed by `SCHEMA_RULES.md`.
- **What goes in the schema:** everything JSON Schema can express: types, formats, lengths, enums, required fields, and some multi-field rules (`dependentRequired`, `if`/`then`, `anyOf`). Example: "if `status` is `active`, these fields are required", or "`latitude` requires `longitude`".
- **What cannot go in the schema:** rules that compare fields to each other or to the world, such as "the names listed cannot exceed the headcount", "a room's preferred occupancy is not above its maximum", "this id must exist in another collection". These live in the handler file's rules block (section 6.3) or in a service, never scattered.
- The schema's `description` names the rules the schema cannot express, so a reader of the schema knows to look for them.
- Run the schema check script (LAUNCH: `python3 schemas/check.py`) whenever a schema changes.

**One definition rule:** a field's rule exists in exactly one place. If a rule can be written in the schema, it is written there, and the handlers pick it up automatically. The rules block holds only what the schema cannot say. If the same rule is typed in two places, they will drift.

### 5.1 Policy keywords and readiness

Besides its fields, every schema declares two policy keywords at the top level:

- `x_retention`: how long records are kept. Today every LAUNCH schema says `"undecided"`. SCHEMA_RULES section 9 says a schema with no retention is not ready for launch.
- `x_history` **(Todd, 2026-10-09)**: what happens to the old version of a record when it changes. One of `in_place` (the document is changed and `updated_at` and `updated_by` say who and when), `linked_records` (a change is a new record that points at the old one with `previous_id`; the handler's `update` is not used, the service creates the new record), or `history_collection` (the handler copies the old version into `<collection>_history` in the same transaction before applying the change, which costs one read). SCHEMA_RULES section 7 already says each schema must say which.

**Readiness rule (Todd, 2026-10-09):** a schema with `x_retention` set to `"undecided"` may be built against and tested, but it must not hold real data. A schema with no `x_history` is not ready for its handler to be built. The schema check script should enforce both (section 14.3, still a proposal). The retention *period* for each schema is still to be set.

## 6. The CRUD handler file

### 6.1 Name and place

One file per collection, named after it: `<collection>_crud.py` (for example `venues_crud.py`). They live together in one folder in the codebase. A new collection is built by taking an existing handler file as the model: **the shape is copied, the field-specific parts are rewritten.** It is a blueprint, not a copy-paste. A skeleton of the file is in Appendix A; once the first real handler file exists it becomes the model and this document points to it instead.

### 6.2 Anatomy of the file (the same in every file)

1. **Header**: what collection this is, which schema file, where the guide is.
2. **Setup**: asks the shared kit (section 6.5) to load the collection by its registry name. The kit returns the collection name, the schema, a ready checker, the list of readOnly fields, and the list of fields involved in cross-field rules. No names typed by hand.
3. **The rules block** (section 6.3): the one place for this collection's own field logic.
4. **The five functions** (section 6.4).
5. **Nothing else.** No business logic, no calls to other collections' handlers, no network.

### 6.3 The rules block: where field-specific logic lives

One clearly marked section per file, containing:

- **Normalizers**: small cleaning steps applied before checking (trim and lowercase an email, strip formatting from a phone number). Each is a named function.
- **Cross-field rules**: rules the schema cannot express. Each is listed in a small **table**: the rule's name, the list of fields it involves, and the function that checks it. Example for venues: *room_labels_unique* involves `rooms`; *room_preferred_not_above_max* involves `rooms`; *opens_before_closes* involves `availability_hours`.
- **Protected fields**: the readOnly fields come from the schema and need no separate list.

If a field's definition changes, there are two places to look and no more: the schema file and this block. That is the consolidation the method exists to provide.

### 6.4 The five functions

All five take the store, the actor (who is acting, such as `system:venue_service`) and may take an optional transaction (section 9). All return a **Result** and never raise for ordinary problems. A Result has:

- `ok`: true or false.
- `data`: the document (or list of documents) on success.
- `code`: on failure, one of the codes in SCHEMA_RULES section 8 (`validation_failed`, `not_found`, `server_error`, and so on) plus one new code, `conflict`, for a refused stale update **(Todd, 2026-10-09; SCHEMA_RULES section 8 still has to be amended, section 14.6)**.
- `problems`: a list of `{field, issue}` entries that **name fields and never include values** (privacy; SCHEMA_RULES sections 8 and 9). The issue words match the registration core today (`required`, `not_allowed`, and so on).

The shapes match the endpoint's reply envelope, so a service can pass a failure straight through.

| Function | Does | Does not |
|---|---|---|
| `create(data, actor)` | Refuses any readOnly field in `data`. Runs the normalizers. Checks the whole document against the schema and the cross-field rules. Adds the server fields: `id` (UUID), `schema_version`, `created_at`, `created_by`, `updated_at`, `updated_by`, `source`. Writes it. | Decide whether the record *should* exist. |
| `get(id)` | Returns one document, or `not_found`. Soft-deleted documents are treated as not found unless asked for. | Filter by business meaning. |
| `list(filters, order, limit)` | Returns documents in a stated order (venues: by name), with a hard maximum limit. No paging yet; a page is the first `limit` records. Filters are simple field comparisons. | Join across collections. |
| `update(id, changes, actor, expected_updated_at)` | See section 7. | Change readOnly fields, ever. |
| `soft_delete(id, actor)` | Sets `deleted_at` and `deleted_by`, and stamps `updated_at` and `updated_by`. Never removes the document. | Hard delete. |

### 6.5 The shared kit (proposal)

Handler files are copies of one shape, and copies drift. To keep the mechanical parts identical everywhere, every handler file imports one small shared module (proposed name `schema_kit`) that provides:

- `load_collection(name)`: reads the registry, loads the schema, builds the checker, and returns the collection name, the readOnly list and the server-required list. It replaces any loader hard-wired to one schema.
- `check_field(collection, field, value)`: validates one value against that field's own definition. Built by wrapping the field's definition with the schema's shared definitions so references resolve. Verified on the venue schema on 2026-10-09: a bad email, a three-letter country, a negative cost and a latitude of 95 each failed on their own, and valid values passed.
- `check_document(collection, doc)`: validates a whole document.
- `involved_fields(schema)`: scans the schema for `dependentRequired`, `allOf` with `if`/`then`, and `anyOf`, and returns two sets, so the update function knows which changes need the whole-record path without anyone listing them by hand. `set_involved` holds the fields whose being *set* can break a rule (triggers, fields in an `if`, fields constrained by a `then`). `remove_involved` holds the fields whose being *removed* can break a rule (anything required by the schema or by a conditional block). The collection loader attaches both sets to the loaded collection.
- `stamp_create(...)` and `stamp_update(...)`: set the standard fields in one way everywhere.
- The `Result` type.

The kit holds no field logic and no collection names. All field-specific logic stays in the handler file's rules block. **(open)** The owner may instead prefer pure copies with no shared module; the cost is that the mechanical parts must then be kept identical by hand, which is the drift the method exists to prevent.

### 6.6 Server-kept fields, and references to schemas that do not exist yet

- **Server-kept summary fields** are readOnly fields that a different part of the system keeps current, such as a venue's `review_count` and `average_rating`. The generic `update` refuses them like any readOnly field. `create` sets their starting value (`review_count` starts at zero; `average_rating` is absent until a first review exists). The one part allowed to change them gets a dedicated, named function in the handler file (for example `set_review_summary`), called only by the service that owns the reviews. **(proposal)**
- **References to documents in other collections** (a `venue_id`, a `scheduled_class_id`) are stored as UUIDs and checked for format only. A handler never checks that the target exists, because that would read another collection; that check is a service rule (section 4.1).
- **References to schemas that are not written yet** (for example `location_pin_ids`, which point at a schema still to be designed) are treated as opaque lists of UUIDs. When the target schema exists, the existence check is added as a service rule and listed in section 14.4.

## 7. Validation and the update function

**Create** checks the whole document, because there is no existing record to merge with.

**Update** receives only the fields that are changing (for example a new phone number). The rule (Todd): the handler passes *just that field's new value* to the checker, against *that field's definition* in the schema. If it is not valid, the problem is returned and nothing is written. If it is valid, only that field is written. **No read from the database is needed for an ordinary field.**

Before it checks anything, the update function:
1. Refuses any field marked readOnly.
2. Runs the normalizers for the fields being changed.

Some fields are involved in rules that depend on *other* fields. The handler must know this **before** calling the checker, because the checker cannot tell it. Two sources, both known in advance:

- **Schema-declared rules.** The schema's own `dependentRequired`, `if`/`then` and `anyOf` blocks name the fields they involve. The handler can scan the schema for these when it loads, and build a list of "involved fields" automatically. Example: changing `latitude` triggers the whole-record check because `latitude` requires `longitude`; setting `status` to `active` triggers it because `active` requires many other fields.
- **Code rules.** The cross-field table in the rules block (section 6.3).

The update procedure, therefore:

1. Is every changed field free of any cross-field rule? Then check each value against its own field definition, and write. **One write, no read.**
2. Does a changed field appear in any cross-field rule? Then read the record once, apply the changes, check the **merged** document against the schema and run the code rules, then write.
3. Either way, stamp `updated_at` and `updated_by`.

A change whose value is `None` or an empty string means *remove this optional field*. Removing a required field is refused (`required`). Setting a field uses `set_involved`; removing one uses `remove_involved`. The slug is refused with the issue word `immutable`. `update` returns `{id, changed, removed, updated_at, updated_by}` (field names only). **Soft-deleted records:** the whole-record path reads the record and answers `not_found` for a soft-deleted one; the simple path does no read and so cannot notice, and the write goes through. This is accepted for now; a service that cares reads first.

**Concurrent edits (gap 1; Todd, 2026-10-09).** `SCHEMA_RULES.md` section 7 says an update must name the `updated_at` it read, and the server refuses it if the record changed since. Mechanics: `update` takes an optional `expected_updated_at`. When it is given, the stored `updated_at` is compared with it at write time and a mismatch gives the Result `conflict` with nothing written. In the in-memory store the compare and the write are one step. In Firestore the compare is done inside a transaction (one read, only when `expected_updated_at` is given), not as an update-time precondition on the document, because a precondition can only test the document's own last-write time and that has to be compared with the *stored* `updated_at` field. Timestamps have one-second granularity, so two edits in the same second are not told apart. The whole-record path always writes with the `updated_at` it just read as the expectation, so a change between its read and its write is also a `conflict`. When `expected_updated_at` is not given on the simple path, the last write wins and is stamped. Default (Todd): a service must supply it for any edit that follows a person looking at the record (a dashboard edit), and need not for system jobs.

**History (gap 2; Todd, 2026-10-09, for venues).** What an update does with the old version depends on the schema's `x_history` keyword (section 5.1). `in_place` is the default behavior described above. `history_collection` makes the update copy the old version first, in the same transaction, and therefore costs one read. `linked_records` means `update` is not used for that collection at all. Value for venues (Todd): `in_place`, because a venue is reference data edited by its owner and `updated_at` and `updated_by` give the trace. Each other schema sets its own value when it is designed.

## 8. Reads, lists and what is returned

- A handler returns the stored document as it is. Deciding what a *person* may see (hiding contact details, hiding private addresses) is a service decision, not a handler decision.
- `list` always has a default and a hard maximum limit. Default 100, maximum 200 **(proposal, matching the LAUNCH console)**.
- Ordering by one field, or filtering and ordering on the same field, needs no special database index. Filtering on one field and ordering by a different field does.
- Indexes are declared in an index file (LAUNCH: `firestore.indexes.json`, referenced from `firebase.json`) and deployed with the code (`firebase deploy --only firestore:indexes`). Each handler file's `list` documents the filter and order combinations it supports. Any other combination is refused with `validation_failed` and a plain message, never answered by reading the whole collection and filtering in code.

## 9. Transactions

Some writes must succeed or fail together: for example a registration request and its idempotency marker. Every handler function that writes takes an optional `tx` argument (a transaction or batch supplied by the caller). When it is given, the handler adds its write to it and does not commit. When it is absent, the handler makes its own single write. The **service** owns the transaction boundary, because only the service knows which writes belong together.

## 10. Adding a new collection (checklist)

1. Write `<name>.schema.json`, the guide, and the examples file. Add them to the registry. Run the schema check.
2. **Confirm the guide's proposals with the owner.** Every field or rule marked (proposal) is confirmed, changed or removed before any handler is written. No handler is built against fields the owner has not seen and approved.
3. **Declare the policy keywords** `x_retention` and `x_history` (section 5.1). "Undecided" retention is allowed while building and testing, never with real data.
4. **List the collection's rules by kind** using the table in section 4.1: what is in the schema, what goes in this handler's rules block, and what belongs to services. Write the service rules down now, in the guide, so they are not lost.
5. **Note references to other collections and to schemas that do not exist yet** (section 6.6), and any server-kept summary fields.
6. Write examples, test records (valid and invalid, each named for what is wrong), and the **handler test records** (section 11).
7. Copy the model handler file. Rename it. Point it at the new schema through the shared kit.
8. Rewrite the rules block: normalizers, and the table of cross-field rules. Delete what does not apply.
9. Run all tests in memory, including the existing ones, and make sure a deliberate break of each rule fails a test.
10. Only then write the service that uses the handler.
11. **If the collection points at another** (a class at a venue), write the cross-collection rules in a service that passes a `check(doc)` callback to the handler, and list `check_fields`: the fields that must force a whole-record read. Add the reverse guards on the other collection's service (the venue cannot be deleted while classes use it). Register the service in `HANDLERS` in `crud_endpoint.py`. Worked example: `docs/classes-build.md`.
12. **Indexes and the Console:** add a composite index for each filtered list (field plus the order field) for both the real and the `test_` collection, then deploy `firestore:indexes`. The Console form is generated from the published schema; add a view, not a hand-written form.

## 11. Testing

- Handlers are tested **in memory** first, with a stand-in store that behaves like the real one. No database, no network. The same test runner can later run against the emulator.
- Every deliberate break of a rule should make a test fail (this was checked for the registration core: eleven deliberate breakages each failed the runner). A test that cannot fail proves nothing.
- **Handler test records (gap 7; proposal for the shape).** Each collection with a handler has a data file beside its examples, `<name>.handler_tests.json`. Each case has a `name`, an `operation` (`create`, `get`, `list`, `update`, `soft_delete`), `given` (documents already stored), `input`, and `expect` (ok or the failure code, the problem fields, the fields that must be stored, and the fields that must not change). One shared runner reads these files, so a new collection supplies data and no test code. Every file must include at least: a valid create; a failing create for every invalid example; a readOnly field refused on create and on update; a simple-path update (and an assertion that the store was **not** read); a cross-field update that triggers a schema-declared rule; a cross-field update that triggers a code rule; an update of a missing record; a stale update when concurrency is adopted (section 7); a soft delete followed by a get; and list ordering and the limit cap.
- **Test area (gap 13).** Handler files never type a collection name. The store adds an optional name prefix taken from a setting (for example `test_`, which turns `venues` into `test_venues`). Production leaves it unset. The test endpoint sets it, so test writes can never reach a real collection, and its cleanup deletes only prefixed collections. A test endpoint that starts without a prefix refuses to run.
- **Test endpoint (Todd approved the lock).** A temporary deployed function that lets curl commands exercise the handlers before they are wired into a real service. It is protected by the admin key (the same pattern as the console endpoint), uses the test prefix, and is removed or kept as an admin tool when its job is done. Nothing else may be built on it.
- Logs hold ids, codes and counts. Never personal data, never a key.

## 12. Anti-patterns (what spaghetti looks like)

- The same field rule written in the schema and again in code.
- A service that talks to the database directly, "just this once".
- A handler that knows a business reason ("only if the class is open").
- A collection name typed into code instead of read from the registry.
- A generic update that can change `processing_status` or any readOnly field.
- A public endpoint that exposes create/update/delete for a collection.
- A hard delete.
- Two handler files that have drifted into different shapes.
- An agent improvising a new structure because no model file was pointed at.
- Changing a schema without changing its tests, handlers and the deployed copy of the schema.
- A handler that reads another collection to check a reference.
- Building a handler against fields marked proposal that the owner has not confirmed.
- Storing real data in a schema whose retention is undecided.
- A list that answers an unsupported filter by reading the whole collection.

## 13. Rules for AI agents working in a repo that uses this method

1. Read this document and `SCHEMA_RULES.md` before creating or changing any schema, collection, handler or endpoint. The repo's agent instructions file points here.
2. Never improvise a structure. Find the model handler file and follow its shape. If there is no model for what you need, stop and ask.
3. Agree the plan with the owner before executing. A question or a "what do you think" is not a go. Wait for an explicit go.
4. Report in short plain sentences. The owner is a systems thinker, not a programmer: explain what a term means the first time it matters.
5. Never print, store or ask for secrets. The owner makes keys in their own terminal.
6. When a schema changes, update handlers, tests, the deployed copy of the schema and the guide in the same piece of work.
7. Do not build against anything marked (proposal) until the owner confirms it. Treat (open) items as questions to put to the owner, not choices to make.

---

## 14. LAUNCH specifics (replace this section in another project)

### 14.1 Where things are
- Repo: `toddbeetcher.github.io` (branch `finish-now`, Cloudflare Pages to beetcher.com). Schemas: `/schemas`. Registry: `schemas/registry.json`. Agent instructions: `CLAUDE.md`.
- Backend: Python codebase `enjoy_router/` (Firebase Functions, codebase `enjoy`, python312), Google project `launch-ai-workshop`, Firestore (default), rules deny all browser access. Deploy: from `enjoy_router/`, `python sync_schemas.py` then `firebase deploy --only functions:enjoy --project launch-ai-workshop`. Runtime errors: Google console, Cloud Run, the function, Logs.
- Registered schemas: `registration_request` (v2), `scheduled_class` (v2), `venue` (v1), `registration_assignment` (v1), `transaction_record` (see the registry).
- Tests: `enjoy_router/run_tests.py` (33 registration test records, in memory), `enjoy_router/run_console_tests.py`, `schemas/check.py` (passes for all five schemas as of 2026-10-09).
- Lock for admin endpoints: one admin key, `ICDT_ADMIN_KEY`, in the git-ignored `enjoy_router/.env.launch-ai-workshop`, made by Todd in his own terminal. Sent as `Authorization: Bearer <key>`, compared in constant time, refuses everything when missing or shorter than 32 characters, failed attempts rate limited. Google sign-in replaces it later.

### 14.2 What exists today versus this method
- `core.py` validates a registration request against its schema and applies its business rules in one flow. It is **not yet split** into handler file plus service. Today's `Store` interface has narrow, request-specific methods (`get_class`, `find_by_idempotency_key`, `put_request`, `list_requests` and so on), not five generic functions per collection.
- **Loader (gap 11).** `Schemas.load` in `core.py` is hard-wired to `registration_request` (it also reads the `scheduled_class` collection name). The method needs the registry-driven `load_collection(name)` of the shared kit (section 6.5). `sync_schemas.py` already copies every schema the registry names into the deploy folder, so no change is needed there.
- **Handler files, folder and model (gap 12), built 2026-10-09.** The package `enjoy_router/crud/` holds `schema_kit.py` (the shared kit), `store_errors.py` (the three errors every store raises: `DocExists`, `DocMissing`, `StaleUpdate`), `memory_doc_store.py` (in-memory store with a test prefix and a read log), and `venues_crud.py`, the model file. Tests: `schemas/examples/venue.handler_tests.json` (handler test records) run by `enjoy_router/run_crud_tests.py`, which also runs every valid and invalid venue example through `create`, checks transactions, and includes a deliberate-break check that proves the tests notice a handler that stopped validating. Also built and deployed 2026-10-09: `crud/firestore_doc_store.py` (same interface, collection prefix, stale-update compare inside a Firestore transaction, grouped writes as one batch), `crud_endpoint.py` plus the `enjoy_crud_test` function (POST `{collection, op, args}`, admin key, fixed `test_` prefix, actor `system:crud_test`), `firestore.indexes.json` (status+name and is_public_venue+name, for `venues` and `test_venues`, deployed from the terminal with `firebase deploy --only firestore:indexes`), and `crud_curl_demo.sh`. The live curl run showed create with trimming, duplicate slug, get, simple update, stale update (409), whole-record refusal (400 with the missing fields), both list forms, soft delete and get-after-delete (404), all as designed. Not yet exercised live: a successful update with a matching `expected_updated_at`, and grouped (`tx`) writes, which no endpoint op uses. Still missing: any service calling the handlers. `core.py` is not changed; later it will import its mechanical helpers from the kit.
- **Test area (gap 13).** The Firestore store takes collection names straight from the registry and has no prefix setting. It needs an optional prefix (section 11) before a test endpoint can be deployed safely.
- **Indexes (gap 14).** There is no `firestore.indexes.json` and `firebase.json` declares no indexes. The registration and console queries need none. It is created when the first handler `list` needs a filter-plus-order combination.
- Today's endpoints: `enjoy_registration_request` (create only, public, rate limited) and `enjoy_console_records` (read only, admin key). No update, soft delete or per-collection handler exists. Only the registration request collection holds live data.

### 14.3 Schema check script: additions (proposal)
`python3 schemas/check.py` should, in addition to what it does today: fail when a schema that has a handler has no `x_history`; warn when `x_retention` is `"undecided"`; fail when a collection with a handler has no `<name>.handler_tests.json`; and print, for each schema, the fields involved in schema-declared cross-field rules, so the handler's rules block can be cross-checked against it.

### 14.4 Venue readiness (the first model collection)
Facts as of 2026-10-09: 67 top-level fields (75 counting the fields inside a room); registered at version 1; guide `VENUE_GUIDE.md`; 4 valid and 22 invalid examples; passes `check.py`. A venue is created from the dashboard only, never by a public page.

**Schema-declared cross-field rules** (found automatically by the shared kit): an `active` venue requires `street_address`, `city`, `state_region`, `postal_code`, `country`, `time_zone`, `contact_name`, `rooms` (at least one), `is_accessible`, `allows_minors`, `allows_animals`, and one of `contact_email` or `contact_phone`; GPS pairs (`latitude` with `longitude`, `parking_latitude` with `parking_longitude`, `entry_latitude` with `entry_longitude`); `cost_cents` with `cost_basis`.

**Code rules for the venue rules block:** room labels are unique within a venue; each room's `preferred_occupancy` is not above its `max_occupancy`; each day's `opens_at` is before its `closes_at`.

**Service rules, to be built with the scheduled class and public class list work, not in `venues_crud.py` (gap 9):** a class's `venue_id` must name an existing venue; a class's `venue_room_label` must name a room in that venue; a class's `capacity_max` against the room's `max_occupancy` (warn or refuse, open); never delete a venue that classes point at, set it inactive; flag a request that brings minors to a venue where `allows_minors` is false; the public class list never exposes `contact_*`, `backup_contact_*` or a private venue's street address, and which fields it may show is open.

**Unconfirmed proposals to settle before the handler is built (gap 6).** VENUE_GUIDE marks these as Claude's proposals, never confirmed by Todd: `transit_description`, `website_url`, `booking_process`, `booking_lead_days`; per-room `is_accessible`, `seating_layout`, `equipment` and `notes`; `has_wifi` and `wifi_notes`; `has_step_free_entry`, `has_elevator`, `has_accessible_restroom`, `accessibility_notes`; `allows_food`, `allows_alcohol`; `requires_insurance`, `insurance_notes`; `setup_minutes_before`, `teardown_minutes_after`; `deposit_cents`, `cancellation_terms`, `cost_notes`; the `active` and `inactive` statuses; the class taking its `time_zone` from the venue; and `venue_room_label` on the class. Each is confirmed, changed or removed.

**Still missing for venues:**
- Handler test records, `venue.handler_tests.json` (gap 7): beyond create, the cases section 11 lists, including changing `status` to `active` on a venue that lacks required fields (whole-record path), changing `latitude` alone (rejected until `longitude` is present), changing one room's occupancy (code rule), a simple-path update such as `contact_phone`, and a readOnly field on update.
- `x_history` (`in_place`, decided) to be added to the venue schema, and `x_retention` (period still to be set; a private home's address is personal data).
- Opaque references (gap 8): `location_pin_ids` points at a schema not yet written. `review_count` and `average_rating` depend on a reviews collection that does not exist; `create` sets `review_count` to zero, the generic `update` refuses both, and a dedicated `set_review_summary` function is added when reviews exist (section 6.6).

### 14.5 SCHEMA_RULES: portable versus LAUNCH-specific (gap 15)
Until `SCHEMA_RULES.md` is split into a portable core and a LAUNCH appendix, treat these as LAUNCH-specific and everything else as portable:
- Section 3: money as whole US-dollar cents, paired with a `per_session` or `per_person` basis. (The cents rule is portable; the currency and bases are not.)
- Section 4: `program_slug` (the idea of a program field is portable; the slug `launch` and the collections that carry it are not) and the `source` values `web_enjoy`, `dashboard`, `import`.
- Section 5: actor names such as `web:enjoy`.
- Section 8: the error codes `over_capacity`, `class_not_found` and `class_closed`.
- Section 9: the honeypot field `website` and the specific rate limits.
- Section 11: publishing schemas as static files on Cloudflare Pages, and the choice of Ajv or `jsonschema`.
- Section 12: the registration request, assignment, scheduled class and transaction chain.
- Section 13: the legacy `enjoy_signups` collection.

The split is its own piece of work, done after the owner reviews this document. Until then this document's sections 1 to 13 treat SCHEMA_RULES as the data conventions and tell the reader to substitute their own for the items above.

### 14.6 Housekeeping
- **Docs visibility (gap 5, decided by Todd 2026-10-09).** The repo root is the site root, so this file is publicly fetchable at `beetcher.com/docs/schema-first-build-method.md`. It contains the Google project id and the architecture, no secrets. A `/docs/*` noindex rule was added to `_headers`, the same pattern as `/console/*`. It keeps search engines away; it does not make the file private.
- **SCHEMA_RULES section 8 amendment (gap 3).** Add `conflict` to the error code list. Not yet done.
- **Stale guide item (gap 10).** `VENUE_GUIDE.md` section 6 ends with "Amend `SCHEMA_RULES.md` to list the boolean prefixes in use". That is done: SCHEMA_RULES section 2 already lists `is_`, `has_`, `allows_` and `requires_`. The guide has not been edited; remove that bullet in the same change that confirms the venue proposals.

### 14.7 Order of work from here (Todd, 2026-10-09)
1. Todd reviews this document.
2. Todd settles what remains open in section 14.9 (the venue proposals and the shape questions). Gaps 1 to 5 are settled.
3. Venue readiness (section 14.4): confirm the proposals, write the handler test records, declare `x_history` and `x_retention`.
4. **Done 2026-10-09:** shared kit and `venues_crud.py` with in-memory tests (291 checks pass). It is the model file; Appendix A now points to it.
5. **Done 2026-10-09:** admin-key test endpoint with the test prefix, exercised with curl.
5a. **Done 2026-10-09: Console collection manager.** The Console has a collection picker (registration requests, venues; `#/venues` addresses) and, for venues, a list with a status filter, a detail card and an Add venue form (name, slug, kind of place; added inactive). It talks to a second door on the same dispatcher, `enjoy_admin` (`crud_endpoint.handle_admin`): real collections with no test prefix, actor `user:admin`, and only the ops in `ADMIN_OPS` (`list`, `get`, `create`). Tested with the real handlers in a real browser at phone width and verified live with `enjoy_router/admin_curl_check.sh`. This door calls the handler directly, with no service layer in between, because no cross-collection rule exists yet; the first one (a class's venue must exist, a venue with classes cannot be deleted) is where a service is introduced. 
5b. **Done 2026-10-09: edit and delete a venue in the Console, tested live by Todd.** `update` and `soft_delete` are now in `ADMIN_OPS`. The edit form is generated from the published schema (`/schemas/venue.schema.json`), so field types, limits and allowed values live in one place; it sends only changed fields plus `expected_updated_at`, shows the server's refusals next to the field, and refuses a stale edit. Lesson recorded: the first form showed all 55 fields and every active-venue requirement at once and was unusable; the fix was a page-only reshaping (essentials first, a readiness checklist computed from the schema's active rule, pick lists), not loosening the schema. The schema stays the single definition of the rules and the form adapts to it. Details in `docs/venue-edit-delete-build-plan.md`. Rooms and hours followed (5c).
5c. **Done 2026-10-09: rooms and hours editing.** The two lists inside a venue are editable in the venue form and in a popup opened from the "Rooms: N" and "Open days: N" links on each card. The server's code rules (unique room labels, preferred occupancy not above maximum, opening before closing) are shown next to the row.
5d. **Done 2026-10-09: second collection, `scheduled_classes`, handler and Console in one build** (`docs/classes-build.md`). The first service layer: `classes_service.py` (a class's venue must exist, be active when scheduled, contain the room, and fit its capacity) and `venues_service.py` (a venue with live classes cannot be deleted; a room a class uses cannot be removed, renamed or shrunk). The mechanism is a hook in the handler, not a dependency: `create` and `update` take an optional `check(doc)` callback run on the final merged record, and `update` takes `check_fields` that force the whole-record path. Handlers still know only their own collection; the dispatcher maps each collection to its service. Tick-box filters on the class list came from live use: a filtered list hid a just-created class. Lesson: a list must never silently hide a record the user just made; show all by default and let the user narrow. 164 class checks plus endpoint and browser tests; deployed and checked live with curl.
**Next:** registration request to class (a `registration_assignment` collection with enrolling, capacity and waitlist rules), then Google sign-in.
6. Wire handlers into real services. The registration core is then reworked to use a registration requests handler file.
7. Split `SCHEMA_RULES.md` (section 14.5).

### 14.8 Decisions recorded (Todd)
The layers and who may call whom (section 4). Handler files are not deployed endpoints. One file per collection, same shape, field logic in one block. The schema is the single definition of field rules, read by a standard checker. Update checks only the changed field's value against its own definition, and uses the whole-record path only for a field involved in a cross-field rule. Documentation first, reusable beyond LAUNCH. Venues is the first handler. The test endpoint is protected by the admin key. The foundation principle (section 1). On 2026-10-09 Todd also accepted the proposed defaults for gaps 1 to 5: `expected_updated_at` required for edits that follow a person looking at a record and optional for system jobs; `in_place` history for venues; the `conflict` error code; the readiness rule (undecided retention means no real data, no `x_history` means no handler); and a `/docs/*` noindex rule.

### 14.8a Venue build decisions (defaults accepted by Todd, 2026-10-09)
- `x_retention` for venues: keep until the owner deletes them; a private home's address is removed one year after the venue goes inactive. A written policy only; nothing enforces it yet. `x_history` is `in_place`.
- Slug: lowercase letters, digits and underscores, unique across all venues **including soft-deleted ones**, cannot be changed (the issue word is `immutable`). Duplicate: `validation_failed` with `slug:duplicate`.
- Normalizers: trim every string, an empty string removes an optional field, `contact_email` and `backup_contact_email` are lowercased.
- Code rules (not expressible in the schema): room labels unique (ignoring case, issue `duplicate`), each room's `preferred_occupancy` not above `max_occupancy`, each day's `opens_at` before `closes_at` (issue `out_of_range`).
- `list` supports: no filter, or exactly one of `status` or `is_public_venue`, ordered by name; no filter ordered by newest first. Anything else is refused with `not_supported`. The filter-plus-name combinations need composite indexes in Firestore (section 8); `firestore.indexes.json` is written when the Firestore store is. Soft-deleted venues are removed after the query, so a page can hold fewer than `limit` records.
- `set_review_summary` writes `review_count` and `average_rating` (the server-kept fields) with the actor `system:reviews`, no read.
- Soft-deleting a venue that a class points at is a service rule; the handler does not check.

### 14.8b Class build decisions (Todd, 2026-10-09)
Retention "keep until the owner deletes" (policy only), `x_history` `in_place`; instructor and promotion fields hidden until those collections exist; start time typed in the venue's time zone and stored in UTC; a scheduled or enrolling class needs an active venue; class lists are ordered by title (not start time, because Firestore drops documents missing the ordered field) and the Console sorts by start time itself; class filters are tick boxes, all ticked by default. Details in `docs/classes-build.md`.

### 14.9 Open decisions
Still needing Todd's decision:
1. **Venue proposals (gap 6):** settled by accepting the defaults on 2026-10-09 (section 14.8a).
2. **Retention periods (gap 4, the period itself):** venues settled (section 14.8a). Every other schema still needs its own.

Settled on 2026-10-09 (Todd accepted the defaults): gap 1 concurrent edits (section 7), gap 2 history (sections 5.1 and 7), gap 3 the `conflict` code (section 6.4), gap 4 the readiness rule (section 5.1), gap 5 the `/docs/*` noindex rule (section 14.6).

Smaller shape questions, each with a default: a shared kit or pure copies (section 6.5, default kit); the folder `enjoy_router/crud/` (section 14.2); the transaction argument optional (section 9); the test prefix mechanism (section 11); one codebase for all collections or one per program; Google sign-in replacing the admin key later.

---

## 15. Gap register

Every gap found in the draft-1 gap analysis, where this document closes it, and what is still needed. "Integrated" means the rule is written. "Decided" means Todd accepted the proposed default. "Decision open" means the owner still decides.

| # | Gap | Closed in | Status |
|---|---|---|---|
| 1 | Concurrent-edit rule for updates undecided | 7, 14.8 | Decided (Todd, 2026-10-09) |
| 2 | History handling undecided; venue schema silent | 5.1, 7, 14.4 | Decided for venues (Todd); schema keyword still to be added |
| 3 | New error code and Result shape for a refused update | 6.4, 14.6 | Decided (Todd); SCHEMA_RULES amendment still to do |
| 4 | Retention undecided on every schema | 5.1, 10, 14.4, 14.9 | Readiness rule decided (Todd); retention periods still to set |
| 5 | `/docs/*` not noindex | 14.6 | Decided (Todd); rule added to `_headers` |
| 6 | Venue proposals never confirmed | 10, 13, 14.4, 14.9 | Integrated (rule and list), owner confirms |
| 7 | No handler test records for venues | 10, 11, 14.4 | Integrated (format proposed) |
| 8 | References to schemas and collections that do not exist | 6.6, 10, 14.4 | Integrated |
| 9 | Service rules mixed in with handler rules | 4, 4.1, 10, 14.4 | Integrated |
| 10 | Stale open item in the venue guide | 14.6 | Recorded; guide not edited |
| 11 | Schema loader hard-wired to one schema | 6.2, 6.5, 14.2 | Integrated (shared kit proposed) |
| 12 | No handler folder or model file | 6.1, 14.2, 14.7, Appendix A | Integrated (skeleton, layout proposed) |
| 13 | No test area for the test endpoint | 11, 14.2 | Integrated |
| 14 | No index file for filtered lists | 8, 14.2 | Integrated |
| 15 | SCHEMA_RULES mixes portable and LAUNCH rules | 14.5, header | Integrated (inventory); the split is later work |
| 16 | No home for rules that span two collections | 4.1, 10, 14.7 (5d) | Built: service layer with `check` and `check_fields` hook (classes and venues). Method text in section 4 still to be tightened with the lesson |
| 17 | Retention periods for schemas other than venues and classes | 14.9 | Decision open |
| 18 | Class delete not guarded against registrations | `docs/classes-build.md` | Waits for the registration collection |
| 19 | Venue activation re-asks for many fields | `docs/classes-build.md` | Decision open: fill in, loosen the active rule, or leave |

---

## Appendix A. Handler file skeleton

Shape only; this skeleton is a summary. **The real, tested model file is `enjoy_router/crud/venues_crud.py`: copy that, not this.** Copy the shape, not the venue details.

```python
"""venues_crud.py: the CRUD handler file for the `venues` collection.

Schema: schemas/venue.schema.json. Guide: schemas/VENUE_GUIDE.md.
Nothing in this file is a business rule. It validates and writes.
"""
from schema_kit import load_collection, Result, stamp_create, stamp_update

VENUES = load_collection("venue")  # collection name, schema, checker, readOnly list, involved fields


# ---------------------------------------------------------------- RULES BLOCK
# The only place for this collection's own field logic.

def _normalize(changes: dict) -> dict:
    """Cleaning applied before checking: trim strings, lowercase emails, tidy phone numbers."""
    ...

def _room_labels_unique(doc: dict):
    """Return a problem for field 'rooms' when two rooms share a label, else None."""
    ...

def _room_preferred_not_above_max(doc: dict): ...
def _opens_before_closes(doc: dict): ...

# Rules the schema cannot express: the rule, the fields it involves, the check.
CROSS_FIELD_RULES = [
    {"name": "room_labels_unique",           "fields": {"rooms"},              "check": _room_labels_unique},
    {"name": "room_preferred_not_above_max", "fields": {"rooms"},              "check": _room_preferred_not_above_max},
    {"name": "opens_before_closes",          "fields": {"availability_hours"}, "check": _opens_before_closes},
]


# ------------------------------------------------------------ THE FIVE FUNCTIONS

def create(store, data: dict, actor: str, tx=None) -> Result:
    # 1 refuse any readOnly field in data        2 normalize
    # 3 check the whole document (schema + every CROSS_FIELD_RULES check)
    # 4 stamp: id, schema_version, created_*, updated_*, source, and starting values for server-kept fields
    # 5 write (into tx if given). Return Result(ok, data) or Result(code, problems naming fields).
    ...

def get(store, id: str, include_deleted: bool = False) -> Result:
    # one document, or not_found; soft-deleted counts as not_found unless asked for
    ...

def list(store, filters: dict | None = None, order: str = "name", limit: int = 100) -> Result:
    # supported filter/order combinations only (section 8); hard maximum limit
    ...

def update(store, id: str, changes: dict, actor: str, expected_updated_at=None, tx=None) -> Result:
    # 1 refuse readOnly fields     2 normalize the changed fields
    # 3 if no changed field is in VENUES.set_involved (or removed field in remove_involved) or any rule's fields:
    #       check each value with check_field, write only those fields (no read)
    #    else: read the record once, merge the changes, check the merged document and every rule, write
    # 4 stamp_update; if expected_updated_at is given, compare with the stored updated_at (inside a transaction in Firestore) -> conflict if stale
    # 5 history: follow the schema's x_history (in_place by default)
    ...

def soft_delete(store, id: str, actor: str, tx=None) -> Result:
    # set deleted_at, deleted_by, updated_at, updated_by; never remove the document
    ...

# Named functions for server-kept fields, called only by the owning service (section 6.6):
# def set_review_summary(store, id, review_count, average_rating, actor, tx=None): ...
```
