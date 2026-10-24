# Console architecture (the policy)

Read this before touching anything in `console/`. Written 2026-10-23 from the Messages extraction (the first station to leave `console.js`), so every rule below was needed by a real move, not guessed. Look and feel is in `DESIGN-RULES.md` (read it too); this file is about where code lives.

## Where we are
`console.js` is the legacy script: one very large file that still holds most stations (Requests, Attendance, Classes, Venues, People, Places, the rosters, and the rest). It only gets smaller from here. Stations that have left it live in their own files, and every new station starts in its own file. The end state is no `console.js` at all, only the small shared files and one file per station.

## The files and the order they load (see the bottom of `index.html`)
| File | What it is |
|---|---|
| `firebase-config.js`, `console-config.js` | Settings (the swap point for another licensee's name, logo, endpoints) |
| `ui.js` | Shared parts: confirm dialog, status chip, banner, empty state, skeleton rows, the old filter bar |
| `filters.js` | `UI.chipFilters`, the one filter control (chips with popovers, and the switch chip) |
| `console.js` | The legacy script, and the owner of `window.ConsoleKit` |
| `names.js` | Shared data (`window.ConsoleNames`): the venue and curriculum names; loads after `console.js`, before the stations |
| `messages.js`, `activity.js`, `performance.js`, `access.js`, `discovery.js` | One station each |

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
| `words()` | The shared word tables (`corrKind`, `reasonWord`) |

Rules for the kit:
1. **Functions, not values.** What they read is filled in later or replaced on reset, so a value copied at load time would go stale.
2. **Add an item only when a second place needs it**, and add it in its **own commit with no behaviour change** (the M-1 pattern), before the move that uses it.
3. **Never copy a helper into a station file.** If two stations need a word table or a formatter, it goes in the kit (or in `ui.js` if it draws something).
4. A station may use `UI` (`ui.js`, `filters.js`) directly. That is shared by design.

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
3. **Shared dialogs**: `dialogs.js` (`window.ConsoleDialogs`): Put in a class, the Journal. One owner. Added in the Requests run (R-2).
4. **Shared UI**: `ui.js`, `filters.js`. Used directly.
5. **Stations**: one file each. They use layers 1 to 4 and **never another station**.

Shared files (`names.js`, `dialogs.js`) load after `console.js` and before the stations. They are not stations: no `show`, but they empty their data on sign-out. A shared file never names a station (checked).

| Kit item | Owner today | Meaning |
|---|---|---|
| `mk` | Core (`console.js`) | Build an element |
| `admin`, `adminProblem` | Core: transport | The one door to the server; the plain sentence for a failed call |
| `toast` | Core: notices | The small notice |
| `lock`, `key`, `can`, `me` | Core: session | Lock the Console; the current key; what this person may do; who they are |
| `sessionMinutes`, `lastButton` | Core: session | Idle limit; the button just pressed |
| `when`, `time`, `clock` | Core: date words | Date and time words |
| `go` | Core: routing | Go to another page |
| `attName` | Attendance (still in `console.js`) | A person's display name from an attendance row |
| `classChoices`, `classById`, `openAttendance` | Attendance and Classes (still in `console.js`) | The class list; look a class up; open its attendance |
| `requests` | Requests (still in `console.js` until R-4) | The loaded registration requests |
| `words` | Core: shared word tables | `corrKind`, `reasonWord` |

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
- **No borrowed names (lint).** A station file must not use anything that only exists inside `console.js`. With ESLint available: `npx eslint --no-eslintrc -c <config> console/<name>.js` where the config sets `env: {browser: true, es2020: true}`, `rules: {"no-undef": "error"}` and `globals: {UI: "readonly", ConsoleNames: "readonly", ConsoleDialogs: "readonly"}`. A clean run means no hidden dependency on the big file (this is how the Messages move was checked).

## Still inside `console.js` (to be extracted, each with its own sheet and GO)
Requests (next), Attendance, Classes, Venues, People, Places, Organizations, the three rosters (Instructors, Students, Curriculum), Workflows, Journal, sign-in, idle timeout, and the shared kit itself. The order is in `claude/console-build-order-bookmark.md`.
