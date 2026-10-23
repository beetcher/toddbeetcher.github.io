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
Applied so far: Requests (commits B-1 to B-7 on `finish-now`). Next: Attendance, then Messages.

