# Console architecture (the policy)

Read this before touching anything in `console/`. Written 2026-10-23 from the Messages extraction (the first station to leave `console.js`), so every rule below was needed by a real move, not guessed. Look and feel is in `DESIGN-RULES.md` (read it too); this file is about where code lives.

## Where we are
`console.js` is the legacy script: one very large file that still holds most stations (Classes, Venues, People, Places, the rosters, and the rest). It only gets smaller from here. Stations that have left it live in their own files, and every new station starts in its own file. The end state is no `console.js` at all, only the small shared files and one file per station.

## The files and the order they load (see the bottom of `index.html`)
| File | What it is |
|---|---|
| `firebase-config.js`, `console-config.js` | Settings (the swap point for another licensee's name, logo, endpoints) |
| `ui.js` | Shared parts: confirm dialog, status chip, banner, empty state, skeleton rows, the old filter bar |
| `filters.js` | `UI.chipFilters`, the one filter control (chips with popovers, and the switch chip) |
| `forms.js` | The form engine (`window.ConsoleForms`): `buildField`, `readValue`, `humanize`, `choicesFor`, the shared `labels`. Venues and Classes both build their forms with it; it needs nothing from `console.js` |
| `console.js` | The legacy script, and the owner of `window.ConsoleKit` |
| `names.js` | Shared data (`window.ConsoleNames`): the venue and curriculum names; loads after `console.js`, before the stations |
| `dialogs.js` | Shared dialogs (`window.ConsoleDialogs`): the Journal (`openJournal`); loads after `names.js` |
| `requests.js` | The Requests station (`window.RequestsStation`), its Search box and Region chip, and the placed-requests data; loads after `dialogs.js` |
| `attendance.js` | The Attendance station (`window.AttendanceStation`: show, reset, `openAttendance(cls, host)` (no host: the dialog; a host: draws inline on the class page), `personHistory`, `attLine`); loads after `requests.js`. The placing machinery (about 400 lines) still lives in `console.js` (DT-18) |
| `venues.js` | The Venues station (`window.VenuesStation`: show, stop, reset, dirty, forget): list, filters, Details, Add, Edit form, Rooms and Open days popups, the venue's Place panel and Contact picker; loads after `attendance.js` |
| `classes.js` | The Classes station (`window.ClassesStation`: show, stop, reset, dirty, forget, and putInClass, assignForm, classWhen, choices, byId for the kit): list and filters, Add, the class page (tabs Overview, People, Attendance, Edit: the Edit form, the Instructors box and the add form live there), time-zone helpers, and the placing machinery (Put in a class, add a person, the class builder); loads after `venues.js` |
| `curriculum.js` | The Curriculum station (`window.CurriculumStation`: show, reset, forget): the list with its status filter, Add, Edit, the active/inactive switch and Delete; builds its own page into `#curriculumsView` at load; loads after `classes.js`. Needs nothing new from the kit |
| `addresses.js` | Shared address machinery (`window.ConsoleAddresses`: addrForm, lProblems, locAddr, locSummary, placeInput, placeText, forgetSaved): the address form, recent city/state/ZIP memory, the place words, the saved-places pick; loads after `dialogs.js`, before `roster-engine.js` and the stations |
| `roster-engine.js` | Shared builder (`window.ConsoleRoster.build(cfg)`): the one engine behind the Instructors and Students pages (list, filter, search, Add window, Edit form, remove, instructor hours, curricula, regions and private address); loads after `dialogs.js`, before the stations |
| `instructors.js` | The Instructors station (`window.InstructorsStation`: show, reset, forget): only its settings; the engine builds its page into `#instructorsView` at load |
| `students.js` | The Students station (`window.StudentsStation`: show, reset, forget): only its settings; the engine builds its page into `#studentsView` at load |
| `places.js` | The Places station (`window.PlacesStation`: show, reset, forget, refresh): the list, filter, search, Add, GPS and address editing, retire and delete, who is linked here; loads after `students.js` |
| `people.js` | The People station (`window.PeopleStation`: show, reset, forget, and list, matches, full, problems, dateOut, forgetPick, stale, words for the kit): the list, filter, search, Add, Edit, Merge and undo, Delete, change history, and the Addresses panel on a person's card; the cached pick list and name matching other pages borrow; loads after `places.js` |
| `organizations.js` | The Organizations station (`window.OrganizationsStation`: show, reset, forget): the list with filter and search, Add, Edit, the active/inactive switch, Delete, and the links panel (people, venues, organizations and places linked to an organization); builds its own page into `#organizationsView` at load; loads after `students.js` |
| `messages.js`, `activity.js`, `performance.js`, `access.js`, `discovery.js` | One station each |
| `access-roles.js` | Shared part of the Access page (`window.ConsoleAccessRoles`: CAPS, TERR, drawRoles, drawCaps, roleForm): the Roles tab and the permission list; loads after `roster-engine.js`, before the stations; access.js hands in what it owns |
| `access-territory.js` | Shared part of the Access page (`window.ConsoleAccessTerritory`: draw): the Territory tab (who works where); same loading rule |

A station file loads **after** `console.js` (it needs `ConsoleKit`) and **after** `filters.js`. `console.css` is the one stylesheet.

## The station file pattern
```
/* <Name> station for the Console: what it shows and does. Loaded by index.html after console.js. */
(function () {
  "use strict";
  var K = window.ConsoleKit;
  if (!K) return;
  var $ = function (id) { return document.getElementById(id); };
  var mk = K.mk, admin = K.admin;           // take only what you use
  ...                                        // state, helpers, render, load
  window.<Name>Station = { show: ..., reset: ... };
})();
```
- **One global per station**, `window.<Name>Station`, with `show()` (the person opened the page; load it) and `reset()` (the Console locked or signed out: **empty the data from the page**, search box included).
- **Hooks in `console.js`** (two lines per station, nothing else): in `route()`, `if (r === "<name>" && window.<Name>Station) window.<Name>Station.show();` and in the lock/sign-out line, `if (window.<Name>Station) window.<Name>Station.reset();`.
- **Markup** (`<section id="<name>View">`) stays in `index.html`, and the **manual text** stays in the stations list in `console.js`, for now. Moving them is a later tidy, not part of an extraction.
- **No station talks to another station's code.** To open something that belongs to another station (a class's attendance), use the kit (`K.openAttendance`, `K.go`).

## ConsoleKit: the only door into `console.js`
`window.ConsoleKit` is built once, in `console.js`. A station file reaches the big file **only** through it.

| Item | What it gives |
|---|---|
| `mk(tag, class, text)` | Build an element |
| `admin(op, payload, collection)` | The one door to the server (`enjoy_admin`); returns `{status, body}` |
| `adminProblem(status)` | The plain sentence for a failed server call (too many tries, no answer, ...) |
| `toast(kind, text, ms)` | The small notice |
| `lock(message)` | Lock the Console (use on a 401) |
| `key()` | The current key, or empty when locked (a late answer must check it) |
| `can(capability)`, `me()` | What this person may do; who they are |
| `when(iso)`, `time(date)`, `clock(date)` | Date words: full "... Mountain", short Denver date and time, time of day |
| `go(id)` | Go to another page |
| `sessionMinutes(n)`, `lastButton()` | Idle limit; the button just pressed |
| `attName(record)` | A person's display name from an attendance row |
| `classChoices()`, `classById(id)` | Load the class list; look one up |
| `openAttendance(class)` | Open a class's attendance dialog |
| `requests()` | The loaded registration requests (fetched if none are loaded yet) |
| `words()` | The shared word tables (`corrKind`, `reasonWord`, `attWord`, `roleWord`) |
| `historyBtn(id, label)` | The "Change history" button for a record (null when not allowed) |
| `fetchT(url, opts, ms)`, `netShow(timedOut)` | The timed read and the "could not reach the server" banner |
| `fetchRecords(since, opt)` | The read of registration requests (sign-in uses it as its key check); `opt` = `{q, region}` asks the server to search |
| `canPlaced()` | May this person see placing (manage requests or classes) |
| `putInClass(rec, host, said)` | The Put in a class form on a request card |
| `line(label, value)`, `str(v)` | The detail-row helpers every list card uses |
| `problem(status)` | The plain sentence for a failed sign-in read |
| `consts()` | True constants only: `MAX`, `READ_MS`, `ATT_RANK`, `ATT_GONE`, `RECORDS_URL` |
| `attConsts()` | The shared attendance tables (`ATT`, `ATT_STATUSES`, `ATT_WORD`, `ROLE_WORD`, `ATT_TONE`, `ATT_OPEN`, `ATT_OFF`, `CORR_KIND`, `REASON_WORD`) and `leftOpen(from, to)`; constants and one pure function |
| `attFail(res)` | The plain sentence for a failed attendance write (now `AttendanceStation.fail`, DT-34) |
| `classWhen(class)` | A class's date and time as words |
| `refreshPlaced()` | Reload the placed requests after placing or removing someone |
| `assignForm(opts)` | The add-a-person-to-a-class form (the placing machinery) |

Rules for the kit:
1. **Functions, not values.** What they read is filled in later or replaced on reset, so a value copied at load time would go stale.
2. **Add an item only when a second place needs it**, and add it in its **own commit with no behaviour change** (the M-1 pattern), before the move that uses it.
3. **Never copy a helper into a station file.** If two stations need a word table or a formatter, it goes in the kit (or in `ui.js` if it draws something).
4. A station may use `UI` (`ui.js`, `filters.js`, `forms.js`) directly. That is shared by design.

## The list page template
Every list station has the same shape, top to bottom: page head (title, Manual, Refresh), summary line, **Search on its own full-width row**, the **chip row** (`UI.chipFilters`, quick yes/no filters first as switch chips), notice, message, the list, the empty message. Filters use `UI.chipFilters` and nothing else; the rules (switch chip, live result line, focus, phone sheet) are in `DESIGN-RULES.md`. A station never draws its own tick-box list.

## Hard rules
1. **New station code never goes into `console.js`.** New station = new file.
2. **`console.js` may not grow.** It only shrinks. (Enforced: see below.)
3. **Every station file has a browser test** that loads `console/index.html`, named `enjoy_router/run_<name>*_browser_test.py`. (Enforced.)
4. **Reach the big file only through `ConsoleKit`.** (Checked by lint, below.)
5. **An extraction changes no behaviour.** Prove it with before and after pictures of the real page at 1440 and 390 (pixel for pixel; a difference is explained or the step is reverted) plus the station's test. Deliberate differences are listed in the run log (the Messages move had one: sign-out now empties the list).
6. **Sign-out takes the data off the page** (`reset()`).
7. **One stylesheet, `console.css`**, with the tokens in `DESIGN-RULES.md`; no inline `<style>`.
8. **The server decides.** A page never enforces a rule the server also needs; it only explains it.

## Who owns what
The cure for tangling is one owner per shared thing. A station never reaches into another station; it asks the owner. **Before you borrow or add anything, find its row here. If it has no row, add one in the same commit** (the architecture test fails if a `ConsoleKit` item has no row).

Layers, from the bottom. A layer depends only on the layers below it.
1. **Core** (still inside `console.js`, reached only through the kit): sign-in and session, server transport and the network banner, config and constants. Planned to leave `console.js` later (`claude/detangling-parking-lot.md`, DT-1 and DT-2).
2. **Shared data**: `names.js` (`window.ConsoleNames`): the venue and curriculum name caches. One owner. Done (Requests run, R-1): read it as `ConsoleNames.venues()`, `.venueById(id)`, `.curricula()`, `.venueAsked(id)`, `.curriculumAsked(id)`; it empties on sign-out.
2c. **Shared formatters**: `format.js` (`window.ConsoleFormat`): `when(iso)`, `time(date)`, `clock(date)`, `attName(row)`. Pure functions, load BEFORE `console.js`; read as `ConsoleFormat.when(...)`. Done (DT-9); the kit doors `when`, `time`, `clock` and `attName` are gone.
2b. **Shared word tables**: `words.js` (`window.ConsoleWords`): `corrKind`, `reasonWord`, `roleWord`, `attWord`, `personLabel`, `personIssue`. Plain data, loads BEFORE `console.js`; read it as `ConsoleWords.attWord` etc. Done (DT-8); the kit door `words` is gone and the attendance status tables (`ConsoleWords.att`: DT-20; the kit door `attConsts` is gone).
2a. **Shared data tables**: `data.js` (`window.ConsoleData`): the collection names (`COLL_P`, `COLL_L`, `COLL_LK`) the relation words (`REL`, `PERSON_RELS`) and the person word tables (`PLABEL`, `PISSUE`). Plain data, loads BEFORE `console.js`; read it as `ConsoleData.REL` etc. Done (DT-33); the kit doors `colls`, `rel` and `personRels` are gone.
3a. **Help drawer**: `help.js` (`window.ConsoleHelp`): the manuals (one per station), the Workflows tab and the drawer; `ConsoleHelp.close()` and `.openWorkflows(ids)`. Done (H-1). The station list stays in `console.js`; the manual text lives in `help.js` (`MANUALS`, keyed by station id).
3. **Shared dialogs**: `dialogs.js` (`window.ConsoleDialogs`): the Journal (`ConsoleDialogs.openJournal(filter, title, hist)`), one owner. Done (Requests run, R-2). **Put in a class is not here**: it uses eight things that belong to Attendance (`ATT`, `aClasses`, `assignForm`, `attLine`, `attName`, `loadClassChoices`, `loadPlaced`, `openWorkflows`), so it stays in `console.js` (reached through the kit) and moves with Attendance (DT-18).
4. **Shared UI**: `ui.js`, `filters.js`, `forms.js`. Used directly.
5. **Stations**: one file each. They use layers 1 to 4 and **never another station**.

Shared files (`names.js`, `dialogs.js`) load after `console.js` and before the stations. They are not stations: no `show`, but they empty their data on sign-out. A shared file never names a station (checked).

| Kit item | Owner today | Meaning |
|---|---|---|
| `mk` | Core (`console.js`) | Build an element |
| `admin`, `adminProblem` | Core: transport | The one door to the server; the plain sentence for a failed call |
| `toast` | Core: notices | The small notice |
| `lock`, `key`, `can`, `me` | Core: session | Lock the Console; the current key; what this person may do; who they are |
| `sessionMinutes`, `lastButton` | Core: session | Idle limit; the button just pressed |
| `go` | Core: routing | Go to another page |
| `surfaces` | Core (`console.js`: the station list) | The station list (id, name, short name, blurb, admin flag); `help.js` reads it to build the manual pages and buttons |
| `allowed` | Core: session | Whether this person's role may open a station (`stationAllowed`); `home.js` uses it to hide tiles |
| `hash` | Core: routing | Read the address: `{route, sub: [path pieces], query: {…}}` (S-0) |
| `setHash` | Core: routing | Write path and query into the address without reloading the station (`history.replaceState`) (S-0) |
| `openAttendance` | Attendance (`attendance.js`, through a forwarder in `console.js`, DT-23) | Open a class's attendance |
| `requests` | Requests (`requests.js`) | The loaded registration requests (fetched if none are loaded yet) |
| `historyBtn` | Core (the link to the Activity page) | The "Change history" button for a record, or nothing when this person may not see the log |
| `fetchT`, `netShow` | Core: transport | The timed read; the network banner (DT-2) |
| `fetchRecords` | Core: transport and sign-in | The read of requests that doubles as the key check (DT-2) |
| `canPlaced` | Core: session | Placing permission |
| `line`, `str` | Core: detail-row helpers | Used by many cards; to become shared UI (DT-19) |
| `problem` | Core: sign-in | The failed sign-in sentence (DT-1) |
| `consts` | Core: constants (transport) | `MAX`, `READ_MS`, `RECORDS_URL`: constants only, never a value that changes; they go with the transport module (DT-2) |
| `attFail` | Attendance (`attendance.js`, `AttendanceStation.fail`; the person words are `ConsoleData.PLABEL` and `.PISSUE`) | The failed-write sentence (DT-34) |
| `refreshPlaced` | Core: a forwarder to Requests | Calls `RequestsStation.loadPlaced` |
| `lProblems` | **Shared addresses** (`addresses.js`) | The plain sentence for a failed place save (used by Venues' Add and Place panel) |
| `placeInput`, `placeText` | **Shared addresses** (`addresses.js`) | The address form with saved-place offer, and the one-line address text |
| `forgetSavedPlaces` | **Shared addresses** (`addresses.js`) | Forget the cached saved places after a place changed |
| `peopleList`, `peopleMatches`, `pFull` | **People station** (`people.js`) | The cached list of people, name matching, a person's full name (Venues' Contact picker) |
| `statusToggle` | Core: shared list helper (still in `console.js`) | The Active/Inactive switch that collects taps into one save |
| `askDiscard` | Core: shared dialog helper (still in `console.js`) | "Discard unsaved changes?" before leaving a form |
| `openWorkflows`, `attLine`, `afNext`, `forgetPeople` | Help (`help.js`, `ConsoleHelp.openWorkflows`) / Attendance / People (`forgetPeople` forwards to the People station) | Open the Help drawer on the Workflows tab; one Attendance line (straight to `AttendanceStation`); the shared id counter for address and assign forms; forget the cached people list after one was created |
| `addrForm`, `pProblems`, `refreshPlaces`, `peopleStale` | Shared addresses (`addrForm`) / Places (`refreshPlaces`) / People station (`pProblems`, `peopleStale`) | The address form block; the plain sentences for a failed person save; reload the Places page after a place changed; mark the People list and the pick list stale after a person changed (read by the roster engine) |
| `personHistory` | Core: a forwarder to Attendance | One person's attendance history |
| `skelOn`, `skelOff`, `currentRoute` | Core: shared list helpers and routing (still in `console.js`) | The loading skeleton on/off for a list; the page the Console is on (read by Places) |
| `pDateOut`, `locAddr` | People station (`pDateOut`) / Shared addresses (`locAddr`) | A stored date as words; a place's address on one line |
| `putInClass`, `assignForm`, `classWhen`, `classChoices`, `classById` | **Classes station** (`classes.js`, `ClassesStation`) | The kit only forwards to it, so Requests and Attendance still ask the kit and never another station |

Rows for later items (names, dialogs, placed requests, the connection helpers) are added in the same commit as the kit item.

## How to add a station
1. Add the markup section to `index.html` and one entry in the stations list (name, blurb, manual) in `console.js`.
2. Create `console/<name>.js` from the pattern above; add its `<script>` after `console.js`.
3. Add the two hook lines in `console.js` (show, reset).
4. Build the list with the template and `UI.chipFilters`.
5. Write `enjoy_router/run_<name>_browser_test.py` (copy `run_messages_browser_test.py`: it shows how to fake the server, work the chips, and check sign-out).
6. Run the architecture test and lint (below).

## How to extract a station from `console.js` (the Messages method)
Write a run sheet and get a GO first, then four steps, one commit each:
1. **Kit additions** only (no behaviour change; add each item's row to "Who owns what"); take the BEFORE pictures.
2. **The move**: new file holds the block verbatim, every borrowed name read from the kit; delete the block; two hook lines; pictures AFTER, compared pixel for pixel; the station's test and the neighbours (sidebar, Help, timeout, net).
3. **The test follows the code**: add checks that the file loaded, that nothing of the station is left in `console.js`, that sign-out empties the page; break something on purpose once to prove the test guards it.
4. **Records**: run log, bookmark, parking lot. Lower the cap in the architecture test to the new `console.js` size.

## Checks you can run
- `python3 enjoy_router/run_console_architecture_test.py` : the size cap on `console.js`, every station file has its browser test, every script in `console/` is loaded in `index.html` in a legal order, station files use `ConsoleKit`.
- **No borrowed names (lint).** A station file must not use anything that only exists inside `console.js`. With ESLint available: `npx eslint --no-eslintrc -c <config> console/<name>.js` where the config sets `env: {browser: true, es2020: true}`, `rules: {"no-undef": "error"}` and `globals: {UI: "readonly", ConsoleNames: "readonly", ConsoleDialogs: "readonly"}`. A clean run means no hidden dependency on the big file (this is how the Messages move was checked). **Since DT-12 the architecture test (`enjoy_router/run_console_architecture_test.py`, section 7) runs this check by itself on every `console/*.js`**: it installs ESLint 9 once into the temp folder, gives each file the browser globals plus the shared objects, lets only `console.js` name the stations, and skips with a note if Node or the install is not available. A new shared object needs no setup (it is read from `window.X = ...`); a bare name that exists only in another file fails the test.

## Still inside `console.js` (to be extracted, each with its own sheet and GO)
Sign-in, idle timeout, transport, routing and the shared kit itself, plus the station list (`SURFACES`), the drop-down and the sidebar. Every station is now in its own file: Home (`home.js`, H-2) and the Help drawer with Workflows (`help.js`, H-1) were the last to leave. The order is in `claude/console-build-order-bookmark.md`.
