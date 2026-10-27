# Console design rules (button and colour cues)

Same meaning on every page. Source: Todd, 2026-10-23. Research and measurements: project doc `claude/console-colour-button-research.md`; step list: `claude/requests-run-sheet.md`. Any station added or changed must follow this table.

| Cue | Look | Means | Rule |
|---|---|---|---|
| Orange fill, dark text, dark edge | the one bright button | Do this next (Submit, Save, Put in a class) | at most one per card or page |
| White fill, dark outline | quiet button | Normal secondary action (Mark handled, Cancel, Send reminders) | up to three |
| Red fill, white text, label starts "Delete" | the only red button | Deletes something | red is never used for anything else on a button; the click still asks to confirm; warnings are amber |
| Plain underlined text | no box | Look at more (History, Show them) | never changes data |
| Flat tinted chip with words | not button-shaped | Status only | green done, amber waiting, grey neutral, red only for a problem |

Same height and corner radius for every button on a page (40 px desktop, 44 px phone). Order in a card: orange first, outlined next, Delete last at the far right, set apart. Orange text only on black; lime only on dark; white text on orange fails contrast, so orange buttons use dark text.

## How to use them in code (added with the Requests tune, B-1 to B-8)
Classes live in `console/console.css`, just under the base `button` rules. Add the class to a `<button>`; nothing else is needed.
- `btn-primary`: orange fill, dark text, dark edge. The one "do this next" button per card or page (Requests: Put in a class, Open class, Show them).
- `btn-secondary`: white with a dark outline. Normal actions (Mark handled, Send reminders now, Refresh).
- `btn-danger`: red fill, white text. Delete only. Keep the two-press confirmation ("Really delete?"); both states keep the class. Put it last, at the far right (`margin-left:auto`).
- `btn-link`: plain underlined text. Looks at more, never changes data (History, How placing works).
- Status is a chip (`.qchip`, `.chips span`, `.type`), never a button. Waiting is amber, done is green, kind is grey. Red is for Delete only.
- Heights: 40 px; 44 px at 520 px wide and under. Focus ring: 3 px ink outline.
- A card says what is next in one plain line (`.qnext`), for example "Next: put this request in a class."
- Old `quiet` and `danger` classes still exist for stations not yet tuned; convert a station by replacing them with the classes above and updating its browser test labels in the same commit.

## Added with run sheet 2 (C-1 to C-9)
- **Card tone (list pages with statuses):** a 4 px left edge plus a faint tint that repeats the chip's words, never alone. `data-tone` = `wait` (amber: waiting), `ok` (green: placed or done), `done` (grey: handled or closed), `none` (white). Colours are tokens `--tone-wait-edge`, `--tone-wait-bg`, `--tone-ok-bg`, `--tone-done-bg` in `console.css`; all text on them is above 5:1.
- **Steady heights:** cards in a row share one height; the action row sits at the bottom of every card (`.qacts`, pushed down with `margin-top:auto`).
- **Progress strip:** `.qstrip` of spans (not list items, so list selectors in tests do not count them): New, Placed, Confirmed, Attended; done steps green, current step dark.
- **Filter counts:** each segment of the Show filter carries its count in a `.segn` chip; a count that cannot be known yet is left off.
- **Detail:** a short plain summary first, every stored field under "All details".
- **Spoken names:** every card button names the person (`aria-label` "Put in a class… (Dana Test)"); the Delete label follows its armed state.
- **One orange per card:** banners use outlined buttons; the orange button is the card's own main action.
- **Sidebar:** items are not boxed; the active station is the black pill with an orange marker on its left edge.
Applied so far: Requests (B-1 to B-9, C-1 to C-9). Next: Attendance, then Messages, using the same classes.

## Added with the Attendance tune (D-1 to D-5)
- Same classes as Requests. The page's one orange button is Search; Refresh, Remove and Send confirmation email are quiet (white); Show all and the class name are plain text links. Remove arms to red "Really remove?" on the second press only.
- Cards: status chip plus tone edge and tint from the person's status (amber waiting: assigned, on the waiting list; green: confirmed, attended, late; grey: did not show, declined, withdrawn, cancelled), and a "Next:" / "Done:" / "Closed:" line. Steady heights; the Send confirmation button sits at the bottom.
- Status filter boxes show a count chip each (`.segn`); counts come from the loaded records.
- Spoken names: "Remove (Ann Able, Evening Basics)", "Send confirmation email (Ann Able)", "Open class attendance: <class>". Armed Remove reads "Really remove? (…)".
- Class dialog: the Show, Instructors and Students bands are neutral white; colour only means a person's status (tone edge and chip on each row), never the band.
Applied so far: Requests, Attendance. Next: Messages.

## Added with the Messages tune (E-1 to E-4)
- Page-level: Manual is a plain link, Refresh is quiet; the "Needs attention" toggle keeps its pill shape (40 px). No orange on the page itself. (Show all was replaced by the chip row's Clear all, see "Chip filters" below.)
- Inside an open entry: **Mark handled** is the one orange button (it is the "do this next", shown only for a not-sent entry nobody handled); Add note is quiet; Copy entry, Copy as JSON and Open the class attendance are plain links.
- Chips are flat and tinted: green Sent, red only for a problem (Failed, Unknown, Not sent), grey Skipped. Card edge and tint follow: green sent, red needs attention, grey skipped or handled. Orange is never an edge colour.
- A needs-attention row carries one "Next:" line (what to do). Avoid putting a button's own label inside such text, tests and screen readers match by label.
- Spoken names: "Mark handled (Placement confirmation to bea@example.com)". A button whose text changes (Copy → "Copied ✓") changes its aria-label too.
- Status filter boxes show a count chip.
Applied so far: Requests, Attendance, Messages.

## Chip filters (H-1 to H-3): the standard for every station
Source: Todd, 2026-10-23 (a column of tick boxes "looks dumb"). One shared control draws every filter on every page.
- **Where the code lives:** `console/filters.js`, loaded after `ui.js`, exposes `UI.chipFilters`. A station never draws its own tick-box list and never copies the component: it declares its filters and reacts to `onChange`. Nothing about filters goes into `console.js`. Contract and examples are in the comment at the top of `filters.js`; styles are the "Chip filters" block at the end of `console.css`.
- **Layout:** Search gets its own full-width row; the chips sit in one row under it. A quick yes/no filter such as Needs attention is the **first chip** in that row (a switch chip, below), never a separate pill beside Search. Old stations still on `UI.filterBar` (Venues) move over when they are converted.
- **Four kinds:** switch (`kind:"toggle"`, below), multi (tick boxes; `start:"all"` = everything ticked and the filter is off until something is unticked; `start:"none"` = "Only show" style, off until something is ticked), pick-one (radio; the first entry is "any"), search-multi (a search box inside the popover; use it for lists longer than about ten, for example regions).
- **Switch chip (J-1):** for one yes/no filter (Needs attention). Same size and shape as the other chips, but it is a button that is pressed or not: no ▾, no popover. Off = plain; on = filled dark. The number of matching records sits beside the words (`setBadge`), and a screen reader hears "Needs attention filter, on, 6 messages". Clear all switches it off too. Space or Enter toggles it.
- **What a chip says:** off = its plain name ("Status"). Narrowing = filled dark with the choice ("Status: Not sent, Failed", or "Status: 3 of 5" when it is long). A **Clear all** link appears only while something is narrowed. A chip is a control, never a status chip: no red, no orange.
- **Popover:** the entries with a count beside each when the page knows it (`setCounts`, from the loaded records, blank until loaded), then **Clear** (this filter back to off) and **Done**. The list shows 7 and a half rows, then scrolls inside the popover, so a long list never looks complete. One popover open at a time; closes on Escape, a click elsewhere, Done, or Tab out. Opening a search list starts with the search empty.
- **Live result line (J-1):** the popover covers the first rows of the list, so every popover carries one quiet line above Clear and Done that says how many are showing ("4 messages of 74"; `setResult`, polite live region, hidden when empty). The page fills it with the same words as its count line.
- **Focus on open (J-1):** opened by keyboard (Enter, Space, Down), focus goes to the first entry. Opened by mouse or touch, focus rests on the popover itself so no entry shows a focus ring it was never given. A search list always focuses its search box.
- **Entries that come from the data** (message kinds, regions): `setOptions`; the person's choices are kept and a brand new entry starts ticked.
- **Phone (520 px and under):** the popover is a bottom sheet with the filter's name as a title, a dimmed page behind it, 48 px rows; chips are 44 px (40 px on desktop).
- **Keyboard and spoken:** Tab to a chip, Enter, Space or Down opens it, Up and Down move between ticks, Space ticks, Escape closes and returns to the chip. A chip's spoken name is "Status filter, 3 of 5 selected"; Clear and Done say which filter ("Done with Status filter").
- **Search wins:** when a page has a Search box that looks at the whole log, the filters are ignored while searching; say so with `setNote` ("Searching the whole log for ...: the filters are ignored.").
- **Tests:** the control has its own test, `enjoy_router/run_chipfilters_browser_test.py`. A station test works the chips through `#<mount> .cf-chip`, the entry labels, and the "Done with <Name> filter" button.
Applied so far: Messages (Needs attention switch, Status, Message, How it was sent, Only show) and Attendance (Status, Role, Came from; they apply at once to the loaded records, Search narrows as you type, Refresh reloads from the server). Next: Requests as it is extracted. Next: Requests and Attendance as they are extracted.

## Tabs, plain names, paging and phone (Access and Activity, 2026-10-27)
- **Tabs:** a station with several jobs uses the `.tabs` row (`role=tablist`, arrow keys, Home and End), one panel (`role=tabpanel`) and an address `#/<station>/<tab>` set with `ConsoleKit.setHash`, so Back and a pasted link land on the same tab. A tab a person cannot use is not drawn. Filters live in the address as `?name=value` and are read back on load.
- **Plain names:** a person sees "Manage registration requests", never `manage_requests`. Keep a table of plain names in the station (`PLAIN`) and show the technical name only as a small `code` or a tooltip ("Technical name: ..."). People are shown by name, never by id; an id with no match reads "A person who is no longer listed". Sources read "Automatic job" and "Website form".
- **Ask before risk:** switching off something people depend on (a super admin, an admin role, yourself, a role people hold) asks first with `UI.confirm` and says what happens ("N people hold the X role. While it is switched off they cannot sign in"). Everything else switches without a dialog.
- **Long lists page:** a log or list that can grow shows the newest 50 and "Load 50 more"; with a search or chip on it says how many were searched and offers "Search older entries". Focus moves to the first new entry. The server marks the page edge (`before`, `more`, `marker`).
- **States:** loading is `UI.skeleton`, an error is one plain sentence plus "Try again", and an empty list says what to do next. "Nothing matches these filters" and "Nothing has been recorded" are two different messages.
- **Phone (390 px):** fields and tick rows are 44 px, buttons that belong together stay on one row, a required field carries a red star (`.acreq`, hidden from screen readers; the field has `aria-required`), and a long reference table is folded in a `<details>` that is closed on a phone and open on a wide screen.
