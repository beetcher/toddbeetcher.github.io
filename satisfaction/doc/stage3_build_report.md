# STAGE 3 — BUILD REPORT
## beetcher.com/satisfaction/ Curriculum Web Surface

Build completed: 2026-09-13

---

## 1. FILE INVENTORY

### Code files (15 total — 5 pages × 3 files each)

| File | Status | Notes |
|---|---|---|
| `satisfaction/index.html` | ✓ Written | Teaser root — 4 panels, curriculum hub |
| `satisfaction/style.css` | ✓ Written | ~1060 lines, complete shared design system |
| `satisfaction/main.js` | ✓ Written | Root page — `CURRENT_DOC = null` |
| `the-full-essay/index.html` | ✓ Written | 16 panels |
| `the-full-essay/style.css` | ✓ Written | Condensed format, full token block |
| `the-full-essay/main.js` | ✓ Written | `CURRENT_DOC = 'the-full-essay'` |
| `why-nobody-fixed-it/index.html` | ✓ Written | 8 panels |
| `why-nobody-fixed-it/style.css` | ✓ Written | Condensed format |
| `why-nobody-fixed-it/main.js` | ✓ Written | `CURRENT_DOC = 'why-nobody-fixed-it'` |
| `disappearing-first-job/index.html` | ✓ Written | 11 panels, 7 ledger categories, summary table |
| `disappearing-first-job/style.css` | ✓ Written | Condensed format, `.ledger-company__name/meta` classes |
| `disappearing-first-job/main.js` | ✓ Written | `CURRENT_DOC = 'disappearing-first-job'` |
| `tractor-and-algorithm/index.html` | ✓ Written | 6 panels, contact CTA end-nav |
| `tractor-and-algorithm/style.css` | ✓ Written | Condensed format |
| `tractor-and-algorithm/main.js` | ✓ Written | `CURRENT_DOC = 'tractor-and-algorithm'` |

### Asset files (20 total — confirmed pre-build, not modified)

| Asset | Location |
|---|---|
| `teaser_hero_background.webp` | `satisfaction/assets/` |
| `favicon.svg`, `favicon-180.png` | `satisfaction/` |
| `phone_do_not_disturb_living_room.webp` | `the-full-essay/assets/` |
| `neighborhood_scene_triptych_divider.webp` | `the-full-essay/assets/` |
| `teens_on_phones_restaurant_booth.webp` | `the-full-essay/assets/` |
| `1950s_gas_station_attendant.webp` | `the-full-essay/assets/` |
| `1970s_neighborhood_street.webp` | `the-full-essay/assets/` |
| `taco_johns_parking_lot.webp` | `the-full-essay/assets/` |
| `pizza_delivery_homecoming.webp` | `the-full-essay/assets/` |
| `automated_kiosk_and_empty_bike_route.webp` | `the-full-essay/assets/` |
| `automated_neighborhood_robots.webp` | `the-full-essay/assets/` |
| `george_jetson_quote_card.webp` | `the-full-essay/assets/` |
| `quiet_empty_nursery.webp` | `the-full-essay/assets/` |
| `invisible_damage_visible_symptoms.webp` | `why-nobody-fixed-it/assets/` |
| `slow_turn_at_sea.webp` | `why-nobody-fixed-it/assets/` |
| `disappearing_first_job_hero.webp` | `disappearing-first-job/assets/` |
| `teenager_holding_the_wheel.webp` | `disappearing-first-job/assets/` |
| `tractor_and_algorithm_hero.webp` | `tractor-and-algorithm/assets/` |
| `tractor_farmer_neighbor_scene.webp` | `tractor-and-algorithm/assets/` |

---

## 2. JUDGMENT CALLS AND DEPARTURES FROM BRIEF

### 2.1 Triptych divider position (Document 1)
Stage 1 analysis placed the triptych divider after the opening thesis paragraph. Stage 2 brief's HTML structure placed it between Panel 1 (Before You Begin) and Panel 2 (Essay Title). Build follows Stage 2: the divider appears before the `<h1>`, separating the "Before You Begin" preamble panel from the essay's title panel. The source markdown position is a presentation artifact from the original Word document; the Stage 2 decision is the correct one for the web layout.

### 2.2 Document 3 opening intro merged into Panel 2
The Stage 1 panel map called for 12 panels in Document 3 (a dedicated intro panel, then 7 category panels). The Stage 2 panel numbering implied merging. Final build: 11 panels — the 4-paragraph opening intro flows directly into Panel 2 (which also contains the Category 1 header band and company content). The `panel__content + ledger-category-header` adjacent sibling CSS rule adds 40px of space between the intro text and the first category header, providing the visual breath without a full panel break.

### 2.3 Document 3 post-table content in Panel 10
After the summary table, the source has 5 paragraphs of analysis before the "At the End of the Day" h2. These are all included in Panel 10 (the ledger table panel). "The reasons are in this table." receives `.closing-line` treatment without a preceding `hr.closing-rule` since more analysis follows — the `hr` is reserved for document-ending moments. The BLS paragraph and punchline sentence are followed by the analysis paragraphs, then Panel 11 opens the "At the End of the Day" section.

### 2.4 `let` instead of `const` for CURRENT_DOC / DOC_VERSION
The Stage 2 brief's JS code example used `const CURRENT_DOC = null` in the shared block, then `const CURRENT_DOC = 'slug'` on each document page. This would throw a `SyntaxError: Identifier 'CURRENT_DOC' has already been declared` at runtime. Fixed throughout: `let CURRENT_DOC = null; let DOC_VERSION = null;` in the shared block; bare assignment (`CURRENT_DOC = 'slug'; DOC_VERSION = '1.0';`) immediately below on each document page.

### 2.5 `object-position: center 60%` on tractor hero image
Per Stage 2 brief note ("The sky/field composition may work best anchored lower"), the `tractor-and-algorithm/style.css` sets `.panel--hero-doc__bg img { object-position: center 60%; }`. This is applied in the per-page CSS, not inline, keeping the HTML clean. May need tuning to `center bottom` once the actual composition is viewed at full viewport.

### 2.6 Document 4 panel count
Stage 1 mapped Panels 17–22 (6 panels) for the addendum. Document 4 is a standalone page so they become Panels 1–6. The addendum framing paragraph and prototyping example are merged into Panel 2 (both are analytical companion-piece framing at the same register). The tractor story is split across Panels 3 (setup) and 4 (climax + image) to give the image breathing room in a TYPE 2 layout. Invisible prerequisite knowledge and the pattern discussion are combined in Panel 5. The closing "What They Need" is Panel 6.

---

## 3. BUGS FIXED DURING BUILD

### 3.1 Firefox `min-height: auto` warning on visual pause duo panel
`.panel--visual-pause-duo` in the mobile media query originally had `min-height: auto`. Firefox does not treat `auto` as a valid value for `min-height` on flex children; it ignores it and can produce layout overflow. Fixed to `min-height: 0` in `satisfaction/style.css`. This is the correct cross-browser value for "let the flex algorithm size this element freely."

### 3.2 Double top-spacing on ledger category headers
The original `.ledger-category-header` rule included `margin-top: var(--sp-xl)` (64px). When the category header was the first element in a panel with `padding-top: var(--sp-xl)`, total top space was 128px — visually broken for the hero panel transition and the first category's appearance. Fix: removed `margin-top` from `.ledger-category-header`, added `.panel__content + .ledger-category-header { margin-top: var(--sp-lg); }`. The margin now only fires when a category header follows paragraph content — which is precisely the case in Panel 2 where the intro flows into Category 1. Applied to: `satisfaction/style.css`, `the-full-essay/style.css`, `why-nobody-fixed-it/style.css`. Written correctly from scratch in `disappearing-first-job/style.css`.

---

## 4. OPEN ITEMS — NOT BUILT IN STAGE 3

### 4.1 Hero image `object-position` tuning
Stage 2 brief flagged this explicitly: "Once the `.webp` files are prepared and placed, the `object-position` value on the hero `<img>` elements may need a one-line adjustment." The values used (`center` for `invisible_damage_visible_symptoms.webp`, `center 60%` for `tractor_and_algorithm_hero.webp`, `center` for `disappearing_first_job_hero.webp`) are reasonable starting points. Review each at 1440px wide and 320px mobile after a visual QA pass.

### 4.2 Dark mode
`prefers-color-scheme: dark` not implemented. Explicitly deferred in Stage 2 brief to a polish pass. The warm cream / deep ink palette is comfortable in ambient reading conditions without a dark flip.

### 4.3 Delivery options
All three delivery option items (Download as PDF, Listen, Send to email) are placeholders across all 4 document pages. The UI scaffold is in place; the actual delivery mechanisms are not yet built.

### 4.4 Root page returning-visitor JS state
`initRootPage()` in `satisfaction/main.js` is a stub. The Stage 2 brief described JS-driven modifications to the curriculum hub list on return visits: `--completed` class application, checkmarks, "continue where you left off" CTA replacement, and potential reordering. The HTML structure supports this (all `data-slug` attributes are in place). The JS reads localStorage but makes no DOM modifications. This is a polish-pass item.

### 4.5 GSAP ScrollTrigger transitions
Phase 3 of the overall site build. Not started. Not in scope for Stage 3. The content is designed to be read linearly without entrance effects; the static layout is the intended Stage 3 state.

### 4.6 `.ledger-company` dead CSS rule
`disappearing-first-job/style.css` includes a `.ledger-company` wrapper class (with `max-width`, `margin`, `padding`) that was defined in the CSS before the final HTML structure was determined. The HTML uses `.panel__content` directly, not a `.ledger-company` wrapper. The rule is harmless dead code. Remove on polish pass.

---

## 5. REVIEW CHECKLIST

Before first-share review:

- [ ] Open `satisfaction/index.html` in browser — confirm hero, curriculum hub, CTA render correctly
- [ ] Open `the-full-essay/index.html` — confirm triptych divider placement, visual pause duo panel, lightbox nav dots
- [ ] Open `why-nobody-fixed-it/index.html` — confirm hero, Titanic image, progress bar
- [ ] Open `disappearing-first-job/index.html` — confirm 7 category headers render, table renders correctly on desktop and mobile (card transform), pullquote, closing line
- [ ] Open `tractor-and-algorithm/index.html` — confirm tractor image panel, email CTA in end-nav
- [ ] Test localStorage progress flow: visit essay → scroll to end → confirm dot updates on return to root
- [ ] Resize to 375px — confirm all hero heights, nav labels hidden, table cards render
- [ ] Review `object-position` on all 3 hero images at 1440px and 375px widths
- [ ] Confirm Google Fonts load (no fallback flash) on each page
- [ ] Check `satisfaction/doc/` directory is not linked anywhere in built pages
