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
