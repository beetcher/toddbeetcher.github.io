# Structural Inspection Report
## one-of-a-kind/index.html

**Report Date:** 2026-05-18  
**File:** `/one-of-a-kind/index.html`  
**Status:** Read-only inspection — no modifications recommended at this time

---

## 1. Page Structure

### High-Level Layout (Top → Bottom)

1. **Hero Section** (`#hero`) — Full viewport height with staggered text animations
2. **Divider** (`<hr class="rule">`)
3. **Route Section** (`#route`) — Map visualization with SVG and elevation profile
4. **Numbers Section** (`#numbers`) — Six statistics in responsive grid
5. **Story Section** (`#story`) — Narrative with multiple sub-blocks
6. **Proof Section** (`#proof`) — Quote display with supporting statistics
7. **Credentials Section** (`#credentials`) — Four credential items in grid
8. **Connect Section** (`#connect`) — CTA with request instructions
9. **Footer** (`<footer>`) — Name, links, metadata

### Logical Frames / Sections

| Frame | ID | Type | Key Elements | Purpose |
|-------|----|----|---|---|
| Hero | `#hero` | Full-bleed | Year, eyebrow, name, credentials, hook, scroll hint | First impression; name reveal |
| Route | `#route` | Full-width background | SVG map + elevation profile | Geographic context |
| Numbers | `#numbers` | Grid | 6 stats (miles, rush hours, children, elevation, canyon miles, uniqueness) | Quantify the challenge |
| Story | `#story` | Narrative block | 5 prose sections + callout quote | Chronological experience |
| Proof | `#proof` | Full-width background | Quote + 3 proof stats (0×, ∞+, Tips) | Third-party validation |
| Credentials | `#credentials` | Grid | 4 items (CDL, endorsement, mountain cert, BVSD) | Professional qualification |
| Connect | `#connect` | CTA | Heading, description, button, request instructions | Action: request Todd |
| Footer | `<footer>` | Strip | Name, links, metadata | Closing; navigation |

### Repeating Structural Patterns

- **Reveal pattern:** All content except hero uses `.reveal` class for scroll-triggered fade-in
- **Delay stagger:** `.reveal-delay-1`, `.reveal-delay-2`, `.reveal-delay-3` for sequential animations (grid items)
- **Section wrappers:** Most sections use centered `.inner` container or `max-width: 1200px` for consistent column
- **Grid layouts:** Stats grid (3 cols / 2 cols mobile), credentials grid (2 cols / 1 col mobile)
- **Section labels:** Amber uppercase label with trailing rule line (`.section-label`)
- **Rules/borders:** Horizontal dividers between sections; vertical grid lines in stat/credential grids

---

## 2. Asset Usage

### CSS
- **Linked:** `<link rel="stylesheet" href="style.css">` (line 10)
- **Inline:** None
- **Strategy:** One external file per CLAUDE.md rule

### JavaScript
- **Linked:** `<script src="main.js" defer></script>` (line 491)
- **Inline:** None
- **Strategy:** One external file per CLAUDE.md rule

### Images
- **Referenced:** None currently present in HTML
- **Note:** No `<img>` tags; only SVG graphics embedded inline

### Video
- **Referenced:** None in this document
- **Note:** This page does not include video elements (distinct from Surface 1 hero video)

### Fonts
- **Google Fonts:** Preconnect + link (lines 7–9)
  - `Playfair Display` (wght: 400, 700, 900; ital: 0, 1) — serif headlines
  - `DM Mono` (wght: 300, 400, 500; ital: 0, 1) — monospace body copy
- **Strategy:** Preconnect for performance optimization

### Embedded Assets
- **SVG 1: Route Map** (lines 58–200)
  - Inline `<svg>` with viewBox `0 0 900 420`
  - Defs include: grid pattern, glow filter, route path
  - Content: terrain, route line, stop markers (Lakewood, Denver, Boulder, Ward), annotations, compass, scale
  
- **SVG 2: Elevation Profile** (lines 205–243)
  - Inline `<svg>` with viewBox `0 0 900 80`
  - Defs include: elevation gradient
  - Content: grid lines, fill, line path, elevation labels, canyon marker

---

## 3. CSS Strategy

### Linking Strategy
- **External file:** `style.css` (one-to-one per HTML file)
- **Inline styles:** One inline style attribute found (line 453: `style="align-self:flex-start"` on `.section-label`)
- **No `<style>` tags:** All rules in external file

### Class Naming Patterns

| Pattern | Examples | Purpose |
|---------|----------|---------|
| **Block ID** | `#hero`, `#route`, `#numbers`, `#story`, `#proof` | Section containers |
| **Utility classes** | `.reveal`, `.visible`, `.amber`, `.dim` | Reusable behavior/styling |
| **Component classes** | `.hero-eyebrow`, `.hero-name`, `.route-title`, `.stat-item` | Specific element styling |
| **Delay modifiers** | `.reveal-delay-1`, `.reveal-delay-2`, `.reveal-delay-3` | Stagger timing |
| **Grid classes** | `.stats-grid`, `.cred-grid`, `.proof-stats` | Layout containers |
| **Layout classes** | `.inner`, `.map-container`, `.elevation-container` | Content wrappers |

### Layout Techniques

| Technique | Location | Usage |
|-----------|----------|-------|
| **Flexbox** | Hero (column); footer (wrap); proof-stats (flex with wrap) | Vertical stacking, alignment, wrapping |
| **CSS Grid** | Stats (3 cols), credentials (2 cols), route-header (2 cols) | Multi-column layouts with responsive fallback |
| **Positioning** | Hero year/scroll (absolute), story-intro border-left | Accent elements and decorative lines |
| **Gradients** | Hero background (radial); elevation profile (linear) | Background atmosphere |
| **Transforms** | Hero topographic lines (skew), reveal animation (translateY) | Visual effects |
| **Media queries** | `@media (max-width: 700px)` and `@media (max-width: 600px)` | Responsive behavior |

### CSS Variables (`:root`)
```
--bg: #0d0e0f (dark navy)
--bg-warm: #111210 (slightly warmer dark)
--amber: #c8933a (gold accent)
--amber-light: #e0a84a (lighter gold)
--amber-dim: #8a6128 (darker gold)
--cream: #e8e0d0 (off-white)
--cream-dim: #a89f90 (muted cream)
--white: #f5f0e8 (bright off-white)
--rule: rgba(200,147,58,0.25) (amber border color)
--serif: 'Playfair Display', Georgia, serif
--mono: 'DM Mono', 'Courier New', monospace
```

### Key Styles
- **Box-sizing:** `border-box` globally reset
- **Smooth scroll:** `html { scroll-behavior: smooth; }`
- **Font smoothing:** `-webkit-font-smoothing: antialiased` on body
- **Hero background effect:** Radial gradients + topographic repeating-linear-gradient
- **Scroll reveal:** Opacity 0 → 1 with 32px translateY, 0.7s ease transition

---

## 4. JavaScript Behavior

### Script Present
- **File:** `main.js` (1 file, 12 lines)
- **Load strategy:** `defer` attribute (executes after DOM parse)
- **Inline code:** None

### Interactions

| Interaction | Trigger | Behavior | Implementation |
|-------------|---------|----------|-----------------|
| **Scroll Reveal** | Element enters viewport (threshold: 12%) | Fade + slide up animation | IntersectionObserver with `.reveal` / `.visible` classes |
| **Links** | Click on `<a href>` tags | Standard navigation | No JS handlers; browser default |
| **Hover states** | `.connect-link`, `.footer-links a` | Color change (CSS) | CSS `:hover` pseudo-class |

### Observer Configuration
- **API:** IntersectionObserver
- **Options:** `{ threshold: 0.12 }` — fires when 12% of element is visible
- **Action:** Add `.visible` class, then unobserve (one-time trigger)
- **Scope:** All elements with `.reveal` class

### Event Listeners
- Single loop: `document.querySelectorAll('.reveal').forEach(el => observer.observe(el));`
- No click handlers, no scroll listeners, no form submissions

---

## 5. Navigation + Linking

### Internal Links
None. No anchor links (`#section-id`) or relative page links.

### External Links
| Target | URL | Rel Attributes | Target | Usage |
|--------|-----|---|--------|-------|
| LinkedIn | `https://linkedin.com/in/beeetcher` | `rel="noopener"` | `_blank` | Line 465 (Connect section) |
| LinkedIn | `https://linkedin.com/in/beeetcher` | `rel="noopener"` | `_blank` | Line 486 (Footer) |

### Link Validation
- Both LinkedIn URLs use identical path: `linkedin.com/in/beeetcher`
- `rel="noopener"` present on both external links (security best practice)
- `target="_blank"` present on both external links

### Suspicious or Broken Paths
- None detected. All paths are full external URLs; no relative paths subject to misconfiguration.

---

## 6. Observations (Strictly Factual)

### Redundancies
1. **Duplicate section heading text:** "Todd Beetcher — Commercial Driver" appears in:
   - `<title>` tag (line 6)
   - `.footer-name` (line 484)
   - Contextual copy in hero and multiple sections
   
2. **Repeated credential types:** CDL, school bus endorsement, and mountain certification mentioned in:
   - Hero credential line (line 25)
   - Credentials section grid (lines 431–445)

3. **Duplicate LinkedIn link:** Appears in connect section (line 465) and footer (line 486) with identical URL.

4. **Route description duplication:** The route sequence appears in:
   - Hero hook (lines 29–30)
   - Route section `.route-desc` (lines 49–51)

### Inconsistencies
1. **Inline style attribute:** One inline `style="align-self:flex-start"` on `.section-label` in `#connect` (line 453), while all other styling is in external CSS.

2. **SVG styling:** SVG elements use inline `fill`, `stroke`, `font-family` attributes rather than CSS classes, making them harder to override or maintain consistent theming.

3. **Grid responsive breakpoints:** Two different max-width breakpoints used:
   - `@media (max-width: 700px)` for route-header and stats-grid
   - `@media (max-width: 600px)` for credentials grid
   - No consistent mobile-first baseline

### Obviously Unused Assets
None detected. All referenced fonts (Playfair Display, DM Mono) are used throughout the page. All CSS variables are referenced.

### Missing or Empty Elements
- No images (`<img>` tags)
- No video elements
- No form elements (despite "Request Todd" section containing instructions)

### Metric Observations
- **Total lines of HTML:** 494
- **Total SVG lines:** ~142 (inline, not separate files)
- **Total distinct sections:** 8
- **Total external assets:** 2 (style.css, main.js)
- **Total fonts loaded:** 2 (Playfair Display, DM Mono)
- **JavaScript lines:** 12 (minimal, single observer instance)

---

## Report Metadata
- **Inspection scope:** HTML structure, asset references, CSS/JS architecture, linking, observable patterns
- **Compliance note:** File adheres to CLAUDE.md strict file rule: one CSS, one JS per HTML file
- **Framework note:** Page uses vanilla JavaScript (IntersectionObserver) with no external dependencies beyond Google Fonts
- **Accessibility note:** SVG route map includes `aria-label`; other content lacks explicit ARIA annotations

---

*End of Report*
