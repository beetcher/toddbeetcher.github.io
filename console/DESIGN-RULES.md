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

Last checked 2026-10-23: checkpoint push test.
