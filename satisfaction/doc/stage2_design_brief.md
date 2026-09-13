# STAGE 2 — WEBSITE DESIGN BRIEF
## beetcher.com/satisfaction/ Curriculum Web Surface

*Do not build until this brief is approved. Stage 3 executes directly from this document.*

---

## 1. INPUT CONFIRMATION

All Stage 1 outputs confirmed in session context:
- Complete panel maps for all 5 documents (56 panels total)
- Full image inventory, Part A and Part B
- Architecture proposal, localStorage schema, version management spec
- All 5 open questions from prior analysis resolved

All 5 source documents confirmed readable:
`00_teaser.md`, `01_main_essay.md`, `02_why_nobody_fixed_it.md`, `03_disappearing_first_job.md`, `04_tractor_and_algorithm.md`

All 18 images confirmed present in `satisfaction/doc/assets/`:
`1950s_gas_station_attendant.png`, `1970s_neighborhood_street.png`, `automated_kiosk_and_empty_bike_route.png`, `automated_neighborhood_robots.png`, `disappearing_first_job_hero.png`, `george_jetson_quote_card.png`, `invisible_damage_visible_symptoms.png`, `neighborhood_scene_triptych_divider.png`, `phone_do_not_disturb_living_room.png`, `pizza_delivery_homecoming.png`, `quiet_empty_nursery.png`, `slow_turn_at_sea.png`, `taco_johns_parking_lot.png`, `teaser_hero_background.png`, `teenager_holding_the_wheel.png`, `teens_on_phones_restaurant_booth.png`, `tractor_and_algorithm_hero.png`, `tractor_farmer_neighbor_scene.png`

Existing scaffold confirmed empty placeholders — Stage 3 builds from zero.

No contradictions with the resolved state. Proceeding.

---

## 2. PHASE 1 — DESIGN SYSTEM SPECIFICATION

### 2.1 Color Palette

Eight tokens. All justified against content register.

| Token | Hex | Name | Use |
|---|---|---|---|
| `--color-bg` | `#f8f4ef` | Warm cream | Page background throughout all 5 documents |
| `--color-bg-surface` | `#ffffff` | White | Pull-quote blocks, table cells, delivery placeholder cards |
| `--color-bg-ledger` | `#f2f0ed` | Cooler cream | Category header bands in Document 3 ledger panels |
| `--color-text` | `#1c1914` | Deep warm ink | All body text, headings |
| `--color-text-secondary` | `#6a635d` | Warm medium gray | Captions, metadata, delivery placeholder copy, curriculum nav labels |
| `--color-accent` | `#1e4c8a` | Institutional blue | Links, progress bar fill, CTA buttons, "Updated" badges |
| `--color-accent-warm` | `#8c3420` | Brick-red | Pull-quote left borders, closing-line rules, urgency callouts |
| `--color-border` | `#ddd7cf` | Warm light border | Table rules, horizontal dividers, panel separators |

**Justification by register:**

- **Cream base (`#f8f4ef`):** Evokes a well-printed document — serious journalism, a quality policy brief, an essay that was carefully prepared. Not stark white (clinical), not dark (the driver microsite). The warmth signals "this was written by a person for people," which is the curriculum's entire argument.
- **Institutional blue (`#1e4c8a`):** The color of credible organizations — Brookings, The Atlantic, policy documents. Signals trust and seriousness without alarm. Used only for interactive elements so it reliably signals "this is actionable."
- **Brick-red (`#8c3420`):** The essay's emotional register is urgency without alarm. This color does exactly that — it's warm, it's serious, it reads as important. Applied to the pull-quote border and closing-line rules for moments like "The revolving door did not relocate. It closed." Not used for body text or backgrounds — only as a 3px accent line.
- **Cooler ledger tint (`#f2f0ed`):** A 0.5% shift cooler and slightly lighter than the base cream. Used only for the narrow category-header bands in Document 3 to create visual separation between the seven ledger entries. Subtle enough to read as intentional, not accidental.
- **No dark mode:** The warm cream / deep ink palette is comfortable in ambient reading conditions and does not require a dark flip for this limited release. Dark mode is deferred to a polish pass. `prefers-color-scheme` is not implemented in Stage 3.

### 2.2 Typography

**Font families:**

- **Heading:** `'DM Sans'` — a clean humanist sans-serif, designed for display. Free on Google Fonts. Confident, contemporary, without startup-brand energy. Distinguishes titles and section headers cleanly from body text.
- **Body:** `'Lora'` — a serif specifically designed for long-form screen reading. Free on Google Fonts. Has a beautiful italic for pull-quotes. Appropriate for both the essay's literary register and the ledger's evidentiary register — the clinical feel in the ledger comes from layout, not font switching.

**Fallback stacks:**
```css
--font-heading: 'DM Sans', 'Inter', system-ui, sans-serif;
--font-body: 'Lora', 'Georgia', 'Times New Roman', serif;
```

**Loading strategy:** Google Fonts, placed in the `<head>` of each HTML file. Same `<link>` tags in all 6 HTML files — this does not violate the Strict File Rule (it is in HTML `<head>`, not a separate CSS file).

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=Lora:ital,wght@0,400;0,600;1,400;1,600&display=swap" rel="stylesheet">
```

**Type scale:**

| Token | Desktop | Mobile | Use |
|---|---|---|---|
| `--type-display` | 3rem / 48px | 2rem / 32px | Document h1 (title panel) |
| `--type-section` | 1.625rem / 26px | 1.375rem / 22px | h2 section headers |
| `--type-subsection` | 1.25rem / 20px | 1.125rem / 18px | h3 panel subheads |
| `--type-body` | 1.125rem / 18px | 1rem / 16px | Body paragraphs |
| `--type-pullquote` | 1.375rem / 22px | 1.25rem / 20px | Pull-quotes and closing-line elements |
| `--type-small` | 0.875rem / 14px | 0.875rem / 14px | Captions, metadata, delivery placeholder copy |
| `--type-nav` | 0.8125rem / 13px | — (dots only) | Curriculum progress bar labels |

**Line heights:**

| Token | Value | Use |
|---|---|---|
| `--lh-heading` | 1.2 | All headings |
| `--lh-body` | 1.75 | Body paragraphs |
| `--lh-pullquote` | 1.6 | Pull-quotes |
| `--lh-tight` | 1.4 | Navigation elements, captions |

**Font weights:**

- DM Sans: 400 (regular), 500 (medium) for navigation, 600 (semibold) for document titles
- Lora: 400 (regular) for body, 400 italic for pull-quotes, 600 (semibold) for section headers

**Numeric figures:** Apply `font-variant-numeric: tabular-nums` to all stat callouts in the ledger (Document 3) to align numbers in columns.

### 2.3 Spacing Scale and Grid

**Base unit:** 8px

| Token | Value | Use |
|---|---|---|
| `--sp-xs` | 8px | Tight internal padding, icon gaps |
| `--sp-sm` | 16px | Within-element spacing, caption margin |
| `--sp-md` | 24px | Standard paragraph margin, mobile panel padding |
| `--sp-lg` | 40px | Between panels (mobile), section header margin |
| `--sp-xl` | 64px | Panel top/bottom padding (desktop), major section breaks |
| `--sp-2xl` | 96px | Between documents (conceptual — visible pause panel margin) |
| `--sp-3xl` | 128px | Hero panel minimum height padding |

**Content column:**
- Max-width: `720px`, horizontally centered
- Horizontal padding: `--sp-md` (24px) on mobile, `--sp-xl` (64px) logical left/right margin at desktop (achieved through the centered column, not padding)

**Wide/breakout width:** `100vw` capped at `1440px` — used for hero panels, visual pause panels, and the triptych divider's containing row. Achieved with the standard breakout technique:
```css
.breakout {
  width: 100vw;
  margin-left: calc(-50vw + 50%);
  max-width: 1440px;
  margin-right: auto; /* paired with negative left margin */
}
```
On mobile (< 768px), breakout panels collapse to full width with no negative margin (they're already full-width).

**Breakpoints** (used consistently throughout):

| Name | Range | Applied to |
|---|---|---|
| Mobile | 0–767px | Single column, full-width images, dot-only nav |
| Tablet | 768px–1023px | Content column active, two-image panels still stack |
| Desktop | 1024px+ | Full side-by-side layouts, labeled nav, wide panels |
| Wide | 1440px+ | Max-width cap applied to breakout elements |

### 2.4 Component Tokens

**Links:**
- Color: `--color-accent`
- Text-decoration: none by default
- Hover: underline, color stays `--color-accent`
- Visited: no separate visited color (this is a curriculum, not a reference document — visited state is tracked in the progress bar, not in link color)

**Pull-quotes** (`.pullquote`):
- Font: `var(--font-body)`, italic, `var(--type-pullquote)`
- Line-height: `var(--lh-pullquote)`
- Color: `var(--color-text)`
- Left border: `3px solid var(--color-accent-warm)`
- Padding-left: `var(--sp-md)` (24px)
- Margin: `var(--sp-lg) 0` (40px top and bottom)
- No background, no right border — the left rule alone signals importance

**Closing-line elements** (`.closing-line`):
Used for the final paragraph of a document or section when Stage 1 flagged it for typographic isolation. Examples: "The revolving door did not relocate. It closed." / "We automate the world. And then we wonder why the kids just sit there holding the wheel."
- Font: `var(--font-body)`, `var(--type-pullquote)` (slightly larger than body)
- Line-height: `var(--lh-pullquote)`
- Margin-top: `var(--sp-xl)` (64px — generous separation from preceding text)
- A short horizontal rule above it: `width: 40px`, `height: 1px`, `background: var(--color-accent-warm)`, `margin-bottom: var(--sp-lg)`

**CTA buttons** (`.btn--primary`):
- Background: `var(--color-accent)`
- Text: `#ffffff`, `var(--font-heading)`, 500 weight
- Font size: `var(--type-body)`
- Padding: 14px 32px
- Border-radius: 2px (near-flat — consistent with serious/editorial register; not pill-shaped)
- No border
- Hover: background darkens by 10% (`#1a4278`)
- Used for: "Continue →" end-of-document CTA

**Secondary links** (`.btn--secondary`):
- No background, no border
- Color: `var(--color-text-secondary)`
- Font: `var(--font-heading)`, 400 weight
- Hover: color shifts to `var(--color-text)`
- Used for: "← Back to Curriculum" navigation links

**Divider — triptych** (`.divider--triptych`):
- A full-width `<img>` tag placed between panel containers, outside both
- Width: 100% of content column (720px desktop, 100% on mobile)
- No padding, no margin — or minimal margin `var(--sp-sm)` top and bottom
- Displays at its native aspect ratio (704:139 ≈ 5:1)
- `alt=""` (decorative, not content)

**Horizontal rules** (`.section-rule`):
- `height: 1px`, `background: var(--color-border)`
- `margin: var(--sp-xl) auto`
- `width: 100%` of content column
- Used to separate major sections within a document page where no image or visual pause panel serves as a break

**Ledger category header bands** (`.ledger-category-header`):
- Background: `var(--color-bg-ledger)`
- Padding: `var(--sp-md) 0`
- Contains the category number, title (h2), and the brief subtitle in italics
- Visually separates one category from the next without a rule or card structure

### 2.5 Favicon

A simple typographic SVG favicon: the letter "S" in DM Sans 600 weight, white on a `#1e4c8a` (institutional blue) background square with 2px rounded corners. Delivered as:
- `favicon.svg` (root of `satisfaction/`) — used as `<link rel="icon" href="../favicon.svg" type="image/svg+xml">` from document subdirectories, or `<link rel="icon" href="favicon.svg">` from root
- `favicon-180.png` (180×180px) for Apple touch icon
- The favicon lives at `satisfaction/favicon.svg` and `satisfaction/favicon-180.png`; document subdirectories reference it with `../`

Stage 3 note: the SVG favicon is simple enough to write inline in the HTML `<head>` as a data URI if preferred, avoiding a file dependency.

### 2.6 Shared Tokens Across 6 CSS Files (Strict File Rule Compliance)

The Strict File Rule prohibits additional linked CSS files; `@import` is also excluded to honor the rule's spirit. The solution: **duplicate the `:root {}` custom properties block** at the top of all 6 `style.css` files.

Each `style.css` begins with a clearly labeled shared block:

```css
/* ============================================================
   SHARED TOKENS — satisfaction curriculum design system
   If you change any value here, update all 6 style.css files:
   satisfaction/style.css
   satisfaction/the-full-essay/style.css
   satisfaction/why-nobody-fixed-it/style.css
   satisfaction/disappearing-first-job/style.css
   satisfaction/tractor-and-algorithm/style.css
   ============================================================ */
:root {
  /* Color */
  --color-bg: #f8f4ef;
  --color-bg-surface: #ffffff;
  --color-bg-ledger: #f2f0ed;
  --color-text: #1c1914;
  --color-text-secondary: #6a635d;
  --color-accent: #1e4c8a;
  --color-accent-warm: #8c3420;
  --color-border: #ddd7cf;

  /* Typography */
  --font-heading: 'DM Sans', 'Inter', system-ui, sans-serif;
  --font-body: 'Lora', 'Georgia', 'Times New Roman', serif;
  --type-display: 3rem;
  --type-section: 1.625rem;
  --type-subsection: 1.25rem;
  --type-body: 1.125rem;
  --type-pullquote: 1.375rem;
  --type-small: 0.875rem;
  --type-nav: 0.8125rem;
  --lh-heading: 1.2;
  --lh-body: 1.75;
  --lh-pullquote: 1.6;
  --lh-tight: 1.4;

  /* Spacing */
  --sp-xs: 8px;
  --sp-sm: 16px;
  --sp-md: 24px;
  --sp-lg: 40px;
  --sp-xl: 64px;
  --sp-2xl: 96px;
  --sp-3xl: 128px;

  /* Layout */
  --content-width: 720px;
  --content-padding: var(--sp-md);
}
```

Similarly, the **`main.js` shared configuration** block (the CURRICULUM array and localStorage utilities) is duplicated at the top of all 6 `main.js` files with an identical "update all 6 files" comment header. See Phase 3 for the full JS configuration block.

### 2.7 SEO and Open Graph Tags

Per-document. These tags appear in each HTML `<head>`. OG image paths are absolute (required by the spec); all other internal links are relative.

**Root — Teaser (`satisfaction/index.html`):**
```html
<title>A Crime With No Criminal — Who Stole My Child's Satisfaction?</title>
<meta name="description" content="Humans build identity through recognized contribution. Two generations of automation have quietly dismantled that pathway — and the consequences are no longer deniable.">
<meta property="og:title" content="A Crime With No Criminal — Who Stole My Child's Satisfaction?">
<meta property="og:description" content="Humans build identity through recognized contribution. Two generations of automation have quietly dismantled that pathway — and the consequences are no longer deniable.">
<meta property="og:image" content="https://beetcher.com/satisfaction/assets/teaser_hero_background.webp">
<meta property="og:url" content="https://beetcher.com/satisfaction/">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="https://beetcher.com/satisfaction/">
<meta name="doc-version" content="1.0">
<meta name="doc-updated" content="2026-09-13">
```

**Document 1 — The Full Essay (`the-full-essay/index.html`):**
```html
<title>Are We Automating Away Our Children's Path to Satisfying Lives?</title>
<meta name="description" content="The complete causal argument: how the systematic automation of household tasks and teen jobs has broken the developmental pathway that builds identity, agency, and the motivation to face the unknown.">
<meta property="og:title" content="Are We Automating Away Our Children's Path to Satisfying Lives?">
<meta property="og:description" content="The complete causal argument: how the systematic automation of household tasks and teen jobs has broken the developmental pathway that builds identity, agency, and the motivation to face the unknown.">
<meta property="og:image" content="https://beetcher.com/satisfaction/the-full-essay/assets/1970s_neighborhood_street.webp">
<meta property="og:url" content="https://beetcher.com/satisfaction/the-full-essay/">
<meta property="og:type" content="article">
<meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="https://beetcher.com/satisfaction/the-full-essay/">
<meta name="doc-version" content="1.0">
<meta name="doc-updated" content="2026-09-13">
```

**Document 2 — Why Nobody Fixed It (`why-nobody-fixed-it/index.html`):**
```html
<title>Why Nobody Fixed It — Beetcher</title>
<meta name="description" content="Why a problem this clear has gone unfixed: the villain comparison, the alarm systems calibrated to miss this, and why the developmental window for an entire generation is narrowing.">
<meta property="og:title" content="Why Nobody Fixed It">
<meta property="og:description" content="Why a problem this clear has gone unfixed: the villain comparison, the alarm systems calibrated to miss this, and why the developmental window for an entire generation is narrowing.">
<meta property="og:image" content="https://beetcher.com/satisfaction/why-nobody-fixed-it/assets/invisible_damage_visible_symptoms.webp">
<meta property="og:url" content="https://beetcher.com/satisfaction/why-nobody-fixed-it/">
<meta property="og:type" content="article">
<meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="https://beetcher.com/satisfaction/why-nobody-fixed-it/">
<meta name="doc-version" content="1.0">
<meta name="doc-updated" content="2026-09-13">
```

**Document 3 — The Disappearing First Job (`disappearing-first-job/index.html`):**
```html
<title>The Disappearing First Job — Beetcher</title>
<meta name="description" content="Company by company, category by category: the named technologies, funding numbers, and deployment scales replacing the jobs through which young people have always built identity.">
<meta property="og:title" content="The Disappearing First Job">
<meta property="og:description" content="Company by company, category by category: the named technologies, funding numbers, and deployment scales replacing the jobs through which young people have always built identity.">
<meta property="og:image" content="https://beetcher.com/satisfaction/disappearing-first-job/assets/disappearing_first_job_hero.webp">
<meta property="og:url" content="https://beetcher.com/satisfaction/disappearing-first-job/">
<meta property="og:type" content="article">
<meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="https://beetcher.com/satisfaction/disappearing-first-job/">
<meta name="doc-version" content="1.0">
<meta name="doc-updated" content="2026-09-13">
```

**Document 4 — The Tractor and the Algorithm (`tractor-and-algorithm/index.html`):**
```html
<title>The Tractor and the Algorithm — Beetcher</title>
<meta name="description" content="What invisible prerequisite knowledge looks like in the age of AI — and what the tractor story can tell us about the generation sitting on the most powerful productivity tool in history, unable to start it.">
<meta property="og:title" content="The Tractor and the Algorithm">
<meta property="og:description" content="What invisible prerequisite knowledge looks like in the age of AI — and what the tractor story can tell us about the generation sitting on the most powerful productivity tool in history, unable to start it.">
<meta property="og:image" content="https://beetcher.com/satisfaction/tractor-and-algorithm/assets/tractor_farmer_neighbor_scene.webp">
<meta property="og:url" content="https://beetcher.com/satisfaction/tractor-and-algorithm/">
<meta property="og:type" content="article">
<meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="https://beetcher.com/satisfaction/tractor-and-algorithm/">
<meta name="doc-version" content="1.0">
<meta name="doc-updated" content="2026-09-13">
```

---

## 3. PHASE 2 — PANEL-TO-MARKUP MAPPING AND IMAGE SPECIFICATION

### 3.1 Scroll Animation Decision

**Static stacking. No scroll-triggered animation in Stage 3.**

Reasons: (1) The curriculum has 56 panels across 6 separate JS files — implementing and debugging per-element IntersectionObserver or GSAP triggers at this scale is substantial added complexity that adds nothing to the argument. (2) The content is designed to be read slowly, linearly, without interruption — entrance animations would work against that. (3) GSAP ScrollTrigger is already earmarked for the driver microsite's Layer 2 Bus Wheel (per CLAUDE.md) and hasn't been built there either. Introducing it here first is scope creep. (4) This is a limited release for colleagues who will judge the argument, not the effects.

CSS transitions on hover states and interactive elements (buttons, links, progress bar fill) are included. Page-level scroll animations are not.

### 3.2 Panel Types — HTML and CSS Structure

Six panel types. Each is a `<section>` with a `data-panel` attribute for JS targeting (scroll progress, completion detection).

---

**TYPE 1 — Hero Panel** (`.panel--hero`)

Used on: Teaser root (full-viewport), and each document's title panel (partial-viewport).

Two sub-variants:

**1a — Teaser hero** (full viewport height, background image):
```html
<section class="panel panel--hero panel--hero-full" data-panel="1">
  <div class="panel--hero-full__bg">
    <img src="assets/teaser_hero_background.webp" alt="" loading="eager">
  </div>
  <div class="panel--hero-full__content">
    <h1 class="panel--hero-full__title">A Crime With No Criminal:<br>Who Stole My Child's Satisfaction?</h1>
    <p class="panel--hero-full__subtitle">The answer isn't on your child's phone. It started before your child's parents met.</p>
    <a href="#panel-2" class="panel--hero-full__scroll-cue" aria-label="Continue reading">↓</a>
  </div>
</section>
```

CSS:
- `min-height: 100svh` (small-viewport-height unit for mobile browser chrome)
- Image: `position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; object-position: center`
- Overlay: `::after` pseudo-element, `background: linear-gradient(to bottom, rgba(28,25,20,0.45) 0%, rgba(28,25,20,0.65) 100%)`
- Title color: `#ffffff`, font: `var(--font-heading)`, weight 600, size `var(--type-display)`
- Subtitle: `#ffffff` at 85% opacity, font: `var(--font-body)`, `var(--type-section)`
- Scroll cue: centered below subtitle, `--color-bg` colored arrow, visible pulse animation (CSS keyframe, not GSAP)

**1b — Document page hero** (partial height, background image with title overlay):
```html
<section class="panel panel--hero panel--hero-doc" data-panel="1">
  <div class="panel--hero-doc__bg">
    <img src="assets/[hero_image].webp" alt="" loading="eager">
  </div>
  <div class="panel--hero-doc__content">
    <span class="panel--hero-doc__sequence">Document [N] of 4</span>
    <h1 class="panel--hero-doc__title">[Document Title]</h1>
    <p class="panel--hero-doc__role">[Role descriptor]</p>
  </div>
</section>
```

CSS:
- `height: 480px` on desktop, `320px` on mobile
- Same image overlay technique as 1a
- Sequence label: `var(--type-small)`, uppercase, letter-spacing 0.1em, `--color-text-secondary` on no-overlay, or white when overlaid on image
- Title: white, `var(--font-heading)`, weight 600, `var(--type-display)`
- Role descriptor: white at 80% opacity, `var(--font-body)`, italic, `var(--type-body)`

**For Document 4 (tractor-and-algorithm):** The hero image (`tractor_and_algorithm_hero.webp`) should use `object-position: center bottom` or `center 60%` — the sky/field composition may work best anchored lower.

**For Document 2 (why-nobody-fixed-it) and Document 3 (disappearing-first-job):** These have hero images (`invisible_damage_visible_symptoms.webp` and `disappearing_first_job_hero.webp` respectively). Use variant 1b.

**For Document 1 (the-full-essay):** Panel 1 is "Before You Begin" — this is *not* a hero panel with a background image. It is a TYPE 2 (text+image) panel with `phone_do_not_disturb_living_room.webp` as an in-panel image. The document's hero treatment is handled by the curriculum progress bar and the document title rendered in the first visible panel — no full-bleed image. The essay's title appears as a large `<h1>` at the top of Panel 2 (Essay Title & Opening Thesis), with the triptych divider between Panel 1 and Panel 2. See TYPE 5 (structural divider) below.

---

**TYPE 2 — Text + Image Panel** (`.panel--text-image`)

```html
<section class="panel panel--text-image" data-panel="[N]">
  <div class="panel__content">
    <div class="panel__text">
      <!-- paragraphs, optional h2 -->
    </div>
    <figure class="panel__figure">
      <img src="assets/[image].webp" loading="lazy" alt="[descriptive alt]">
    </figure>
  </div>
</section>
```

CSS:
- `.panel__content`: `max-width: var(--content-width)`, centered, horizontal padding `var(--content-padding)`
- `.panel__text`: standard body paragraphs, `margin-bottom: var(--sp-lg)`
- `.panel__figure`: `margin: 0`, full width of content column. `img` is `width: 100%`, `height: auto`, `display: block`
- Panel padding: `var(--sp-xl) 0` (64px top/bottom on desktop)
- Mobile: padding `var(--sp-lg) var(--sp-md)` (40px top/bottom, 24px sides)

Image position: always below the associated text within the panel. No floating or wrapping — images function as emotional landing points after prose, not inline illustrations.

**Pull-quote within text panels:** When a specific sentence is designated as a pull-quote (e.g., "The revolving door did not relocate. It closed."), it is wrapped in:
```html
<blockquote class="pullquote">
  <p>The revolving door did not relocate. It closed.</p>
</blockquote>
```

**Closing-line element:** The final paragraph of a document or major section, when Stage 1 designated it for typographic isolation, is structured as:
```html
<hr class="closing-rule" aria-hidden="true">
<p class="closing-line">We automate the world. And then we wonder why the kids just sit there holding the wheel.</p>
```
The `<hr>` is styled per the `.closing-line` token specification in Phase 1.

---

**TYPE 3 — Text-Only Panel** (`.panel--text`)

```html
<section class="panel panel--text" data-panel="[N]">
  <div class="panel__content">
    <!-- h2 if section header present -->
    <!-- body paragraphs -->
  </div>
</section>
```

CSS: identical to TYPE 2's `.panel__content` rules, no `.panel__figure`. Same padding.

---

**TYPE 4 — Visual Pause Panel** (`.panel--visual-pause`)

Near-textless, image-led. A confirmed first-class panel type. No body text — the image(s) carry the content.

**Single-image variant** (not currently in the panel plan, but spec'd for future use):
```html
<section class="panel panel--visual-pause" data-panel="[N]">
  <figure class="pause-figure">
    <img src="assets/[image].webp" loading="lazy" alt="[descriptive alt]">
  </figure>
</section>
```

**Two-image variant** (Document 1, Panel 13 — `automated_neighborhood_robots.webp` + `george_jetson_quote_card.webp`):
```html
<section class="panel panel--visual-pause panel--visual-pause-duo" data-panel="13">
  <figure class="pause-figure pause-figure--primary">
    <img src="assets/automated_neighborhood_robots.webp" loading="lazy" alt="A modern suburban street with autonomous vehicles, delivery robots, a humanoid robot, a robotic lawnmower, and teenagers on a porch looking at their phones.">
  </figure>
  <figure class="pause-figure pause-figure--secondary">
    <img src="assets/george_jetson_quote_card.webp" loading="lazy" alt="This isn't George Jetson's future. The technology already exists. What's left is scale.">
  </figure>
</section>
```

CSS for the duo variant:
```css
/* Desktop (≥ 1024px): side by side, full bleed */
.panel--visual-pause-duo {
  width: 100vw;
  margin-left: calc(-50vw + 50%);
  max-width: 1440px;
  display: flex;
  gap: var(--sp-xs);
  align-items: stretch;
  padding: var(--sp-xl) 0;
}
.pause-figure--primary {
  flex: 0 0 65%;
}
.pause-figure--secondary {
  flex: 0 0 calc(35% - var(--sp-xs));
}
.panel--visual-pause-duo img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

/* Mobile (< 768px): stacked, full width */
@media (max-width: 767px) {
  .panel--visual-pause-duo {
    width: 100%;
    margin-left: 0;
    flex-direction: column;
    gap: var(--sp-sm);
  }
  .pause-figure--primary,
  .pause-figure--secondary {
    flex: none;
    width: 100%;
  }
  .panel--visual-pause-duo img {
    height: auto;
    object-fit: contain; /* on mobile, don't crop the quote card */
  }
}
```

**Note on the Jetson quote card:** The card is a designed graphic with text baked into the image. Its `alt` attribute carries the full text for screen readers. The `object-fit: contain` on mobile ensures the text remains fully readable at narrow widths.

---

**TYPE 5 — Structural Divider** (`.divider--triptych`)

Not a panel — a visual element placed between panel containers in the HTML.

```html
</section><!-- end panel 1 -->

<div class="divider--triptych" role="presentation">
  <img src="assets/neighborhood_scene_triptych_divider.webp" alt="">
</div>

<section class="panel panel--text" data-panel="2">
```

CSS:
```css
.divider--triptych {
  max-width: var(--content-width);
  margin: var(--sp-sm) auto;
  padding: 0 var(--content-padding);
}
.divider--triptych img {
  width: 100%;
  height: auto;
  display: block;
}
```

This places the triptych within the content column, not full-bleed. On mobile, the 5:1 aspect ratio produces an image approximately 375px × 75px — acceptable.

---

**TYPE 6 — Table / Data Panel** (`.panel--ledger`)

Used only in Document 3, Panel 10.

```html
<section class="panel panel--ledger" data-panel="10">
  <div class="panel__content">
    <h2>Summary: The Ledger</h2>
    <div class="ledger-table-wrapper">
      <table class="ledger-table">
        <thead>
          <tr>
            <th scope="col">Category</th>
            <th scope="col">What was the teen job</th>
            <th scope="col">Who automated it</th>
            <th scope="col">Current scale</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td data-label="Category">Fast food</td>
            <td data-label="What was the teen job">Fry cook, counter, prep</td>
            <td data-label="Who automated it">Miso Robotics / Flippy</td>
            <td data-label="Current scale">5M+ baskets fried, 7 states, expanding to pizza</td>
          </tr>
          <!-- × 6 more rows -->
        </tbody>
      </table>
    </div>
    <p class="panel__text">In July 2025, the U.S. youth unemployment rate was 10.8 percent — the highest summer rate in years. Youth employment as a share of the population declined for the third consecutive year. BLS analysts said the reasons were not clear.</p>
    <p class="closing-line">The reasons are in this table.</p>
  </div>
</section>
```

**Mobile card transformation** (CSS-only, no duplicate HTML):
```css
@media (max-width: 767px) {
  .ledger-table thead tr {
    position: absolute;
    top: -9999px;
    left: -9999px;
  }
  .ledger-table,
  .ledger-table tbody,
  .ledger-table tr,
  .ledger-table td {
    display: block;
  }
  .ledger-table tr {
    border: 1px solid var(--color-border);
    border-radius: 2px;
    margin-bottom: var(--sp-md);
    padding: var(--sp-md);
    background: var(--color-bg-surface);
  }
  .ledger-table td {
    padding: var(--sp-xs) 0;
    padding-left: calc(40% + var(--sp-sm));
    position: relative;
    font-size: var(--type-small);
    line-height: var(--lh-tight);
  }
  .ledger-table td::before {
    content: attr(data-label);
    position: absolute;
    left: 0;
    width: 40%;
    font-family: var(--font-heading);
    font-weight: 500;
    font-size: var(--type-small);
    color: var(--color-text-secondary);
  }
}

/* Desktop table styles */
@media (min-width: 768px) {
  .ledger-table-wrapper {
    overflow-x: auto;
  }
  .ledger-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--type-small);
    font-variant-numeric: tabular-nums;
  }
  .ledger-table th {
    font-family: var(--font-heading);
    font-weight: 500;
    text-align: left;
    padding: var(--sp-sm);
    border-bottom: 2px solid var(--color-border);
    color: var(--color-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.75rem;
  }
  .ledger-table td {
    padding: var(--sp-sm);
    border-bottom: 1px solid var(--color-border);
    vertical-align: top;
    line-height: var(--lh-tight);
  }
  .ledger-table td:first-child {
    font-family: var(--font-heading);
    font-weight: 500;
  }
  .ledger-table tr:last-child td {
    border-bottom: none;
  }
}
```

### 3.3 Image Specification

Images are converted from `.png` to `.webp` before Stage 3 begins. Stage 3 places final files with simple `<img>` tags. No dynamic resizing. No `srcset`. `loading="lazy"` on all images except hero images (which use `loading="eager"`).

Five delivery types, each with target dimensions, aspect ratio, and where the image is used:

**TYPE A — Teaser hero (full-viewport):**
- Dimensions: 1440 × 900 px
- Aspect ratio: 16:10
- Format: `.webp`
- Files: `teaser_hero_background.webp`

**TYPE B — Document page hero (partial-viewport band):**
- Dimensions: 1440 × 600 px
- Aspect ratio: 12:5
- Format: `.webp`
- Files: `disappearing_first_job_hero.webp`, `tractor_and_algorithm_hero.webp`
- Note: For `why-nobody-fixed-it` and `the-full-essay`, no dedicated hero image at TYPE B dimensions is needed — see their panel structures above.

**TYPE C — Visual pause panel (full-bleed, wide):**
- Dimensions: 1200 × 800 px
- Aspect ratio: 3:2
- Format: `.webp`
- Files: `automated_neighborhood_robots.webp`

**TYPE D — Quote/card graphic:**
- Dimensions: max 720 px on longest side, preserve native aspect ratio
- Format: `.webp`
- Files: `george_jetson_quote_card.webp`
- Note: This image has baked-in text. Do not crop or resize beyond 720px — preserve all text legibility.

**TYPE E — Standard in-panel photo (within 720px content column):**
- Dimensions: 720 × 480 px (3:2 ratio)
- Format: `.webp`
- Files (all 12 remaining images):
  - `phone_do_not_disturb_living_room.webp`
  - `teens_on_phones_restaurant_booth.webp`
  - `1970s_neighborhood_street.webp`
  - `taco_johns_parking_lot.webp`
  - `pizza_delivery_homecoming.webp`
  - `1950s_gas_station_attendant.webp`
  - `automated_kiosk_and_empty_bike_route.webp`
  - `quiet_empty_nursery.webp`
  - `invisible_damage_visible_symptoms.webp`
  - `slow_turn_at_sea.webp`
  - `teenager_holding_the_wheel.webp`
  - `tractor_farmer_neighbor_scene.webp`
- Note: Center-crop to 3:2 when source aspect ratio differs. Subjects should be centered.

**TYPE F — Structural divider (triptych):**
- Dimensions: 720 × 144 px (preserves the original 704:139 ≈ 5:1 ratio at content column width)
- Format: `.webp`
- Files: `neighborhood_scene_triptych_divider.webp`

**Pre-Stage-3 image prep checklist:**
Convert all 18 `.png` files from `satisfaction/doc/assets/` to `.webp` at the specified dimensions. Place final `.webp` files in the appropriate subdirectory `assets/` folders as specified in Phase 4. The source `.png` files in `satisfaction/doc/assets/` remain untouched — they are the canonical originals.

---

## 4. PHASE 3 — COMPONENT SPECIFICATIONS

### 4.1 Global Curriculum Progress Bar

Fixed at top of every page (all 6). Does not scroll. z-index: 100 (above all content).

**HTML structure** (identical across all 6 pages, placed immediately after `<body>`):
```html
<nav class="curriculum-nav" aria-label="Curriculum progress">
  <div class="curriculum-nav__inner">
    <a href="../" class="curriculum-nav__home" aria-label="Return to curriculum index">
      <span class="curriculum-nav__home-mark">S</span>
    </a>
    <ol class="curriculum-nav__docs" role="list">
      <li class="curriculum-nav__doc" data-slug="the-full-essay">
        <a href="../the-full-essay/">
          <span class="curriculum-nav__dot" aria-hidden="true"></span>
          <span class="curriculum-nav__label">Essay</span>
        </a>
      </li>
      <li class="curriculum-nav__doc" data-slug="why-nobody-fixed-it">
        <a href="../why-nobody-fixed-it/">
          <span class="curriculum-nav__dot" aria-hidden="true"></span>
          <span class="curriculum-nav__label">Diagnostic</span>
        </a>
      </li>
      <li class="curriculum-nav__doc" data-slug="disappearing-first-job">
        <a href="../disappearing-first-job/">
          <span class="curriculum-nav__dot" aria-hidden="true"></span>
          <span class="curriculum-nav__label">Ledger</span>
        </a>
      </li>
      <li class="curriculum-nav__doc" data-slug="tractor-and-algorithm">
        <a href="../tractor-and-algorithm/">
          <span class="curriculum-nav__dot" aria-hidden="true"></span>
          <span class="curriculum-nav__label">Addendum</span>
        </a>
      </li>
    </ol>
  </div>
  <div class="read-progress" aria-hidden="true">
    <div class="read-progress__fill"></div>
  </div>
</nav>
```

**Note on root page (`satisfaction/index.html`):** The home link `href="../"` becomes `href="/"` (or is removed/inert) since this IS the root. JS handles this: if `CURRENT_DOC === null`, the home mark is not a link.

**CSS dimensions:**
- Height: 48px (desktop), 36px (mobile)
- Background: `var(--color-bg-surface)` with `border-bottom: 1px solid var(--color-border)`
- `.curriculum-nav__inner`: flexbox, align-items center, height 46px (leaving 2px for the read progress track at bottom)
- Home mark: `var(--font-heading)`, weight 600, 18px, color `var(--color-accent)`, padding `0 var(--sp-md)`
- Dot: 10px × 10px circle, `border: 2px solid var(--color-border)`, border-radius 50%
  - State `--completed`: `background: var(--color-accent)`, `border-color: var(--color-accent)`
  - State `--current`: `background: transparent`, `border-color: var(--color-accent)`, `border-width: 3px`
  - State `--current --completed`: `background: var(--color-accent)`, ring treatment (box-shadow outset)
- Label: `var(--type-nav)` (0.8125rem), `var(--font-heading)`, color `var(--color-text-secondary)`, margin-left 6px
- On mobile (< 768px): labels hidden (`display: none`), dots only

**Body offset:** All pages add `padding-top: 48px` on desktop, `36px` on mobile to prevent content from hiding under the fixed nav.

**Read progress track:**
- Position: at bottom of the curriculum-nav element
- Height: 2px, full width
- Track background: `var(--color-border)`
- Fill (`read-progress__fill`): background `var(--color-accent)`, width driven by inline style set by JS
- Only visible on document pages (not on root/teaser). On root, the track remains but stays at 0% width.

### 4.2 Shared JS Configuration Block

This block appears at the top of all 6 `main.js` files, labeled with the same "update all 6 files" comment:

```javascript
// ============================================================
// SHARED CONFIGURATION — satisfaction curriculum
// If you change anything in this block, update all 6 main.js files:
// satisfaction/main.js
// satisfaction/the-full-essay/main.js
// satisfaction/why-nobody-fixed-it/main.js
// satisfaction/disappearing-first-job/main.js
// satisfaction/tractor-and-algorithm/main.js
// ============================================================
const CURRICULUM = [
  { slug: 'the-full-essay',        title: 'Are We Automating Away Our Children\'s Path to Satisfying Lives?', shortTitle: 'Essay' },
  { slug: 'why-nobody-fixed-it',   title: 'Why Nobody Fixed It',               shortTitle: 'Diagnostic' },
  { slug: 'disappearing-first-job',title: 'The Disappearing First Job',         shortTitle: 'Ledger' },
  { slug: 'tractor-and-algorithm', title: 'The Tractor and the Algorithm',      shortTitle: 'Addendum' },
];
const STORAGE_KEY = 'satisfaction';
// Set per-page by each main.js (null on root):
const CURRENT_DOC  = null;   // e.g. 'the-full-essay'
const DOC_VERSION  = null;   // e.g. '1.0'
// ============================================================
```

Each document page overrides `CURRENT_DOC` and `DOC_VERSION` immediately below the shared block:
```javascript
// PAGE-SPECIFIC (set in this file only)
const CURRENT_DOC = 'the-full-essay';
const DOC_VERSION = '1.0';
```

### 4.3 localStorage Schema and Utilities

```javascript
function getProgress() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (e) {
    return null;  // private mode or blocked — degrade silently
  }
}

function setProgress(data) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch (e) { /* silent */ }
}

function getOrInitProgress() {
  const existing = getProgress();
  if (existing) return existing;
  const fresh = {
    schema_version: 1,
    docs: {}
  };
  CURRICULUM.forEach(doc => {
    fresh.docs[doc.slug] = {
      visited: false,
      completed: false,
      version_seen: null,
      last_visit: null
    };
  });
  return fresh;
}
```

If `getProgress()` returns `null`, all progress-dependent UI (dot states, checkmarks, "Updated" badges, "continue where you left off" CTA) renders in the default first-time-visitor state. No error messages.

### 4.4 Within-Document Scroll Progress

Scroll listener updates the read progress fill width. Throttled with `requestAnimationFrame`.

```javascript
function initReadProgress() {
  if (!CURRENT_DOC) return;  // root page: no reading progress
  const fill = document.querySelector('.read-progress__fill');
  if (!fill) return;
  let ticking = false;
  window.addEventListener('scroll', () => {
    if (!ticking) {
      requestAnimationFrame(() => {
        const scrollTop = window.scrollY;
        const docHeight = document.body.scrollHeight - window.innerHeight;
        const pct = docHeight > 0 ? Math.min(100, (scrollTop / docHeight) * 100) : 0;
        fill.style.width = pct + '%';
        ticking = false;
      });
      ticking = true;
    }
  });
}
```

### 4.5 Completion Detection

Fires when the reader reaches the final panel (the end-of-document navigation section). Uses IntersectionObserver.

```javascript
function initCompletionDetection() {
  if (!CURRENT_DOC) return;
  const endNav = document.querySelector('.doc-end-nav');
  if (!endNav) return;
  let dwellTimer = null;
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        dwellTimer = setTimeout(() => markCompleted(), 5000);
      } else {
        if (dwellTimer) clearTimeout(dwellTimer);
      }
    });
  }, { threshold: 0.5 });
  observer.observe(endNav);
}

function markCompleted() {
  const progress = getOrInitProgress();
  if (!progress.docs[CURRENT_DOC].completed) {
    progress.docs[CURRENT_DOC].completed = true;
    progress.docs[CURRENT_DOC].version_seen = DOC_VERSION;
    setProgress(progress);
  }
  updateNavDots();
}
```

### 4.6 Version Update Notification

Appears as a non-blocking banner below the curriculum progress bar, above page content. Only for document pages where `completed === true` and stored `version_seen < DOC_VERSION`.

```html
<div class="version-banner" role="alert" style="display:none">
  <span class="version-banner__text">This document has been updated since you last read it.</span>
  <a href="#changelog" class="version-banner__link">See what changed ↓</a>
  <button class="version-banner__dismiss" aria-label="Dismiss">✕</button>
</div>
```

CSS: `background: var(--color-bg-surface)`, `border-bottom: 2px solid var(--color-accent)`, padding `var(--sp-sm) var(--sp-md)`, small type (`var(--type-small)`), color `var(--color-text-secondary)`.

Dismiss stores to `sessionStorage` (not localStorage — the banner should reappear on the next session):
```javascript
function initVersionBanner() {
  if (!CURRENT_DOC || !DOC_VERSION) return;
  const progress = getProgress();
  if (!progress) return;
  const doc = progress.docs[CURRENT_DOC];
  if (!doc || !doc.completed) return;
  const dismissed = sessionStorage.getItem(`version_dismissed_${CURRENT_DOC}`);
  if (dismissed) return;
  // Compare versions: simple string comparison works for N.N format
  if (doc.version_seen && doc.version_seen < DOC_VERSION) {
    const banner = document.querySelector('.version-banner');
    if (banner) {
      banner.style.display = 'flex';
      banner.querySelector('.version-banner__dismiss').addEventListener('click', () => {
        banner.style.display = 'none';
        sessionStorage.setItem(`version_dismissed_${CURRENT_DOC}`, '1');
      });
    }
  }
}
```

If no `#changelog` element exists in the document, the "See what changed" link is hidden (JS checks for the element and hides the link if not found).

### 4.7 Curriculum Progress Bar Dot States

On every page load, after reading progress data:

```javascript
function updateNavDots() {
  const progress = getProgress();
  const dots = document.querySelectorAll('.curriculum-nav__doc');
  dots.forEach(dotEl => {
    const slug = dotEl.dataset.slug;
    dotEl.classList.remove('--completed', '--current', '--visited');
    if (slug === CURRENT_DOC) dotEl.classList.add('--current');
    if (progress && progress.docs[slug]) {
      const doc = progress.docs[slug];
      if (doc.completed) dotEl.classList.add('--completed');
      else if (doc.visited) dotEl.classList.add('--visited');
    }
  });
}
```

`--visited` state: dot border color shifts to `var(--color-text-secondary)` (partially acknowledged, not completed).

On page load, also record visit:
```javascript
function recordVisit() {
  if (!CURRENT_DOC) return;
  const progress = getOrInitProgress();
  progress.docs[CURRENT_DOC].visited = true;
  progress.docs[CURRENT_DOC].last_visit = new Date().toISOString();
  setProgress(progress);
}
```

### 4.8 End-of-Document Navigation

Placed after the final content panel and the delivery placeholder section on every document page. The `doc-end-nav` class triggers completion detection.

```html
<section class="doc-end-nav" aria-label="Document navigation">
  <div class="doc-end-nav__inner">
    <!-- If not the last document: -->
    <div class="doc-end-nav__continue">
      <a href="../[next-slug]/" class="btn--primary">
        Continue →<span class="doc-end-nav__next-title">[Next Document Title]</span>
      </a>
    </div>
    <!-- If last document (tractor-and-algorithm): -->
    <!-- Replace above with the contact invitation (see below) -->
    <a href="../" class="btn--secondary doc-end-nav__back">← Back to curriculum</a>
  </div>
</section>
```

**For Document 4 (last in sequence):** No "Continue →" button. Instead:
```html
<div class="doc-end-nav__closing">
  <p class="doc-end-nav__closing-text">You've read the full curriculum. A response is being designed. If you have the leverage to help build it, Todd would welcome that conversation.</p>
  <a href="mailto:todd@beetcher.com" class="btn--primary">todd@beetcher.com</a>
</div>
<a href="../" class="btn--secondary doc-end-nav__back">← Back to curriculum</a>
```

CSS:
- `.doc-end-nav`: padding `var(--sp-2xl) 0`, border-top `1px solid var(--color-border)`, max-width `var(--content-width)`, centered
- `.btn--primary` in this context: same as Phase 1 button token
- `.doc-end-nav__next-title`: display block, `var(--type-small)`, font-weight 400, opacity 0.7, margin-top 4px
- `.doc-end-nav__back`: display block, margin-top `var(--sp-md)`, text-align center (or left, depending on layout)

### 4.9 Root Page Navigation Hub — First-Time and Returning States

**First-time visitor state** (no localStorage data, or `visited === false` for all docs):

Panel 5 renders as a curriculum list:
```html
<section class="panel panel--text" data-panel="5" id="start-reading">
  <div class="panel__content">
    <p class="curriculum-hub__intro">They are clear. The full case is in the four documents below, best read in this order:</p>
    <ol class="curriculum-hub__list">
      <li class="curriculum-hub__item" data-slug="the-full-essay">
        <a href="the-full-essay/" class="curriculum-hub__link">
          <span class="curriculum-hub__num">1</span>
          <span class="curriculum-hub__info">
            <strong class="curriculum-hub__title">Are We Automating Away Our Children's Path to Satisfying Lives?</strong>
            <span class="curriculum-hub__role">Start here. The complete causal argument.</span>
          </span>
          <span class="curriculum-hub__state" aria-hidden="true"></span>
        </a>
      </li>
      <!-- × 3 more -->
    </ol>
    <a href="the-full-essay/" class="btn--primary curriculum-hub__cta">Start with the essay →</a>
    <div class="curriculum-hub__contact">
      <p>A response is being designed. If you have the leverage to help build it, I would welcome that conversation.</p>
      <p><strong>Todd Beetcher</strong> | <a href="mailto:todd@beetcher.com">todd@beetcher.com</a> | <a href="https://linkedin.com/in/beeetcher" rel="noopener">linkedin.com/in/beeetcher</a></p>
    </div>
  </div>
</section>
```

**Returning visitor state** (localStorage has data with at least one `visited: true`):

JS modifies the rendered list on page load:
- Each `.curriculum-hub__item` with `completed: true` gets class `--completed`; the `.curriculum-hub__state` span renders a checkmark (✓, via CSS content or a small SVG)
- Items with `completed: true` AND stale version get class `--updated`; a small "Updated" badge appears inline next to the title
- The primary CTA text changes to "Continue →" pointing to the first incomplete document (first in CURRICULUM array where `completed !== true`)
- If all 4 are completed: CTA reads "Read again →" pointing to `the-full-essay/`

```javascript
function initRootPage() {
  if (CURRENT_DOC !== null) return;  // not root
  const progress = getProgress();
  if (!progress) return;

  let firstIncomplete = null;
  CURRICULUM.forEach(doc => {
    const item = document.querySelector(`.curriculum-hub__item[data-slug="${doc.slug}"]`);
    if (!item) return;
    const docData = progress.docs[doc.slug];
    if (!docData) return;
    if (docData.completed) {
      item.classList.add('--completed');
      // Check version staleness
      const currentVersion = item.querySelector('[data-doc-version]')?.dataset.docVersion;
      if (currentVersion && docData.version_seen < currentVersion) {
        item.classList.add('--updated');
      }
    }
    if (!firstIncomplete && !docData.completed) {
      firstIncomplete = doc;
    }
  });

  const cta = document.querySelector('.curriculum-hub__cta');
  if (cta && firstIncomplete) {
    cta.textContent = 'Continue →';
    cta.href = firstIncomplete.slug + '/';
  } else if (cta && !firstIncomplete) {
    cta.textContent = 'Read again →';
    cta.href = 'the-full-essay/';
  }
}
```

Note: version staleness on the root page requires each `curriculum-hub__item` to know the current version of each document. This is stored as a `data-doc-version` attribute on the list item, populated with the current version string at build time. When a document is updated and its `doc-version` meta tag incremented, the root page's list item attribute must also be updated — this is a manual sync step, documented in the same "update all 6 files" convention.

CSS for states:
```css
.curriculum-hub__item.--completed .curriculum-hub__state::after {
  content: '✓';
  color: var(--color-accent);
  font-family: var(--font-heading);
  font-weight: 500;
}
.curriculum-hub__item.--updated .curriculum-hub__title::after {
  content: 'Updated';
  display: inline-block;
  margin-left: var(--sp-sm);
  padding: 2px 8px;
  background: var(--color-accent);
  color: #fff;
  border-radius: 2px;
  font-size: 0.7rem;
  font-family: var(--font-heading);
  font-weight: 500;
  vertical-align: middle;
}
```

### 4.10 Delivery Placeholder UI

Appears on every document page, between the final content panel and the end-of-document navigation section.

```html
<section class="delivery-options" aria-label="Other ways to read this document">
  <div class="delivery-options__inner">
    <h3 class="delivery-options__heading">Other ways to engage with this document</h3>
    <ul class="delivery-options__list">
      <li class="delivery-option">
        <span class="delivery-option__name">Download as PDF</span>
        <span class="delivery-option__note">A formatted PDF for printing or offline reading is coming.</span>
      </li>
      <li class="delivery-option">
        <span class="delivery-option__name">Listen</span>
        <span class="delivery-option__note">An audio recording of this document for a walk or a commute is coming.</span>
      </li>
      <li class="delivery-option">
        <span class="delivery-option__name">Send to email</span>
        <span class="delivery-option__note">The ability to send a link to your email — for returning from another device or sharing with a specific person — is coming.</span>
      </li>
    </ul>
  </div>
</section>
```

CSS:
- `.delivery-options`: padding `var(--sp-xl) 0`, border-top `1px solid var(--color-border)`
- `.delivery-options__inner`: max-width `var(--content-width)`, centered, padding `0 var(--content-padding)`
- `.delivery-options__heading`: `var(--font-heading)`, `var(--type-small)`, uppercase, letter-spacing 0.1em, color `var(--color-text-secondary)`, margin-bottom `var(--sp-lg)`
- `.delivery-option`: display flex, flex-direction column, gap `var(--sp-xs)`, padding `var(--sp-md) 0`, border-bottom `1px solid var(--color-border)`; last-child no border
- `.delivery-option__name`: `var(--font-heading)`, weight 500, `var(--type-body)`, color `var(--color-text)`
- `.delivery-option__note`: `var(--font-body)`, `var(--type-small)`, color `var(--color-text-secondary)`, line-height `var(--lh-tight)`
- No icons, no disabled buttons, no "Coming Soon" badges. Just text, in the document's voice.

---

## 5. PHASE 4 — FILE AND BUILD MANIFEST

### 5.1 Complete File Tree

```
satisfaction/
├── favicon.svg
├── favicon-180.png
├── index.html
├── style.css
├── main.js
├── assets/
│   └── teaser_hero_background.webp
│
├── the-full-essay/
│   ├── index.html
│   ├── style.css
│   ├── main.js
│   └── assets/
│       ├── phone_do_not_disturb_living_room.webp
│       ├── neighborhood_scene_triptych_divider.webp
│       ├── teens_on_phones_restaurant_booth.webp
│       ├── 1970s_neighborhood_street.webp
│       ├── taco_johns_parking_lot.webp
│       ├── pizza_delivery_homecoming.webp
│       ├── automated_neighborhood_robots.webp
│       ├── george_jetson_quote_card.webp
│       ├── 1950s_gas_station_attendant.webp
│       ├── automated_kiosk_and_empty_bike_route.webp
│       └── quiet_empty_nursery.webp
│
├── why-nobody-fixed-it/
│   ├── index.html
│   ├── style.css
│   ├── main.js
│   └── assets/
│       ├── invisible_damage_visible_symptoms.webp
│       └── slow_turn_at_sea.webp
│
├── disappearing-first-job/
│   ├── index.html
│   ├── style.css
│   ├── main.js
│   └── assets/
│       ├── disappearing_first_job_hero.webp
│       └── teenager_holding_the_wheel.webp
│
└── tractor-and-algorithm/
    ├── index.html
    ├── style.css
    ├── main.js
    └── assets/
        ├── tractor_and_algorithm_hero.webp
        └── tractor_farmer_neighbor_scene.webp
```

**Total new files Stage 3 creates:** 6 `index.html`, 6 `style.css`, 6 `main.js`, 2 favicon files = 20 code/markup files. Plus 18 image files (`.webp`, copied from `doc/assets/` at correct dimensions). Grand total: 38 files.

**Source files that are NOT touched by Stage 3:**
- `satisfaction/doc/` — everything in this directory is source material only
- The root `satisfaction/` existing placeholder files are replaced (not appended to)

### 5.2 Document Sequence and Shared Configuration

The `CURRICULUM` array (defined in Phase 3, Section 4.2) is the single source of document ordering used for:
- Curriculum progress bar dot ordering
- Previous/next navigation link generation
- localStorage schema initialization
- Root page returning-visitor "continue" logic

It is duplicated at the top of all 6 `main.js` files under the shared configuration comment header. This is the explicit convention for maintaining it — no build tooling, no imports. Manual sync. Documented in the comment header.

**The only files that must be updated when adding a new document:**
1. All 6 `main.js` files: add the new entry to `CURRICULUM`
2. `satisfaction/index.html` (root): add a new `<li>` to the curriculum hub list, with the new `data-doc-version` attribute
3. Create the new subdirectory with its own `index.html`, `style.css`, `main.js`, `assets/`

No other files need changes.

### 5.3 Post-Build Infrastructure Notes (For Human Decision — Not Stage 3 Actions)

The following items are flagged for review after Stage 3 completes real pages:

1. **`WEBSITE_MAP.md` (if it exists at the root):** If the repo maintains a site map document, `satisfaction/` and its five document subdirectories should be added once pages are real.

2. **`robots.txt`:** If `satisfaction/` is intended to be discoverable by search engines at launch, no action needed. If it should be excluded (limited release, private audience), add `Disallow: /satisfaction/` until a public launch decision is made.

3. **`_headers` file (Netlify/Cloudflare):** If the repo uses a `_headers` file for cache-control rules, add cache directives for `satisfaction/*/assets/` images (long TTL, fingerprint-based invalidation if deployer supports it).

4. **GitHub Pages `_config.yml`:** If the repo uses a Jekyll config, confirm that the `satisfaction/` directory is not excluded.

None of these block Stage 3. All are post-build hygiene items.

---

## 6. PHASE 5 — RESOLVED JUDGMENT CALLS

### 6.1 Document 2 Panel Density: Keep 8 or Merge Panels 4 + 5?

**Decision: Keep as 8 panels.**

Panels 4 and 5 do opposite emotional work. Panel 4 establishes systemic blindness: "the instruments are calibrated to miss this — they're showing green." Panel 5 makes the invisible visible: "the damage is legible if you look at therapy waiting lists and twenty-six-year-olds still at home." Merging them forces the reader through a tonal shift ("you can't see it" → "here's how to see it") without the breath that shift requires. They serve as setup and reveal. Keep them separate.

### 6.2 Document 3 Table Mobile Treatment

**Decision: CSS table-to-card transformation using `data-label` attributes. Single HTML structure.**

Rejected alternatives:
- **Horizontal scroll:** Breaks the vertical reading rhythm and obscures comparison — the reader has to scroll right and back for each row. This is not a reference table; it's an argument. It should be readable in one direction.
- **Progressive disclosure (accordion):** Hides the "overwhelming comprehensiveness" effect that the table is specifically designed to produce. Seven collapsed rows don't feel like a complete ledger; they feel like a menu.

The stacked card approach (each row becomes a labeled card on mobile) preserves all content at any viewport width, maintains the vertical reading flow, and the cumulative weight of scrolling through seven cards closely approximates the visual weight of seeing seven rows simultaneously. See Phase 2 for the complete CSS implementation.

### 6.3 Document 1 Panel 13 Two-Image Layout

**Decision: Side-by-side at full-bleed width on desktop (65/35 split); stacked vertically on mobile.**

Panel 13 is a visual pause panel — near-textless, image-led. The two images need to coexist without either one dominating. The 65/35 split gives the wide landscape robots image its natural scale while letting the portrait Jetson quote card hold its own. The panel breaks out of the 720px content column to full viewport width (max 1440px) so both images are large enough to read.

On mobile, both images stack full-width. The `google_jetson_quote_card.webp` uses `object-fit: contain` on mobile (rather than `cover`) because the card contains baked-in text that must remain legible at small widths.

The panel is structured as `.panel--visual-pause-duo` per Phase 2 Type 4 specification.

### 6.4 Scroll Animation vs. Static

**Decision: Static. No scroll-triggered animation in Stage 3.**

This is a reading experience, not a product launch page. The curriculum's argument is sustained, linear, and depends on uninterrupted cognitive flow — the same reason the essay itself asks the reader to enable Do Not Disturb. Entrance animations interrupt that flow. Scroll triggers across 56 panels in 6 separate JS files adds substantial implementation complexity with no meaningful payoff for this audience (colleagues, not consumers).

CSS hover and transition states on interactive elements (buttons, links, progress bar fill) are included — these are expected functional responses, not spectacle. Page-level animations (panel reveals, fade-ins, parallax) are deferred to a future Polish pass and are not part of Stage 3 scope.

---

## 7. CONFIDENCE STATEMENT

**High confidence across the entire brief.**

The design system (colors, type, spacing, components) is internally consistent and grounded in the content's emotional register. Every token has a justified use case; there are no decorative decisions.

The panel-to-markup mapping covers all 6 panel types with complete HTML and CSS. The one structural complexity — the two-image Panel 13 — is fully spec'd. The table-to-card mobile transformation is a standard CSS pattern with no JavaScript dependency.

The component specifications (progress bar, completion detection, version notification, root page states) are specified at implementation-ready detail. The localStorage schema is simple, the utilities are short, and the graceful degradation is explicit.

**One area where Stage 3 may need to revisit:**

The `object-position` for the TYPE B hero images (`tractor_and_algorithm_hero.webp` and `disappearing_first_job_hero.webp`). These images have not been seen at their final dimensions — once the `.webp` files are prepared and placed, the `object-position` value on the hero `<img>` elements may need a one-line adjustment to correctly frame the subject. This is a two-second fix in the CSS once the images are in place; it does not require an architectural change.

**What would complete confidence require:**
The images prepared at final `.webp` dimensions. Once those exist, Stage 3 can execute this brief without any additional judgment calls.

---

*Stage 2 design brief complete. Do not begin Stage 3 until this brief is approved.*
*File location: `satisfaction/doc/stage2_design_brief.md`*
