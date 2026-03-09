# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a static GitHub Pages site for Todd Beetcher, a CDL school bus driver. The site's purpose is to convert a job application into a callback for school district transportation directors. Full specification is in `brief.md` — read it before making changes.

## Deployment

- Hosted on GitHub Pages from the `main` branch
- No build step — changes are live when pushed to `main`
- Preview locally by opening `index.html` directly in a browser

## Architecture

### Strict File Rule

**One CSS file per HTML file. One JS file per HTML file. No exceptions.**

Each HTML file links exactly one `style.css` and one `main.js` from its own directory. Never add `<style>` blocks or `<script>` tags with inline code to HTML files.

### Site Structure

- **Surface 1** (`index.html` + `style.css` + `main.js`) — Main job application surface. Five-layer scrolling page.
- **Surface 2** (`one-of-a-kind/index.html` + `one-of-a-kind/style.css` + `one-of-a-kind/main.js`) — Boys & Girls Club canyon route story. Linked as an easter egg from Surface 1.
- `one-of-a-kind/todd-beetcher.html` — Separate page within Surface 2, with its own `todd-beetcher.css` and `todd-beetcher.js`.

### Surface 1 Layer Architecture

| Layer | ID | Status | Purpose |
|---|---|---|---|
| 1 | `.hero` | Built | Full-bleed hero photo, headline, video lightbox |
| 2 | `#layer-2` | Built | Bus Wheel — 8 radial thumbnails around scrolling marquee hub |
| 3 | `#layer-3` | Skeleton | Raising the Brand — coworkers and families |
| 4 | `#layer-4` | Skeleton | The Proof — Shane's quote + proof points |
| 5 | `#layer-5` | Skeleton | CTA — contact form, LinkedIn, AI widget (last) |

### Build Order (per `brief.md`)

1. Skeleton — structure and rough content
2. Assets — real photos and copy
3. Transitions — GSAP ScrollTrigger road animation (Phase 3, not started)
4. Fine tuning — typography, spacing, polish

Do not build Phase 3 transitions until Phases 1 and 2 are complete.

## Design System

- Background: `#1a1a2e` (dark navy)
- Accent: `#f5c518` (gold)
- Danger/Action: `#c0392b` (red) — used on play button
- Font: Georgia, serif
- Tone: proud without performance, warm, human, never corporate

## Key Implementation Details

### Layer 2 — Bus Wheel

- `.wheel-stage` is `700×700px` with `transform: translate(23px, -52px)` for visual centering against the background
- 8 `.wheel-thumb` divs positioned absolutely via `.thumb-1` through `.thumb-8` classes on a ~280px radius circle
- Thumbnails use CSS `filter: grayscale(100%)` by default, `grayscale(0%)` on hover — color images only, BW files in `assets/top_shots/thumb_bw_*.jpg` are unused
- Marquee loop: content is duplicated (12 spans = 6 items × 2), animation goes `translateY(0)` → `translateY(-50%)`
- Click-to-lightbox: `data-src` and `data-caption` on each `.wheel-thumb` drive the image lightbox

### Lightboxes

Two lightboxes in Surface 1:
- `#lightbox` — video (`.play-btn` trigger, `Bumpered_Intro_Video.mp4`)
- `#img-lightbox` — images (`.wheel-thumb` click trigger, entrance animation: scale + blur)

Both use `display: none` → `display: flex` via `.open` class.

### Temporary Elements

- Number labels on wheel thumbnails (`.wheel-thumb::after` with `content: "1"` through `"8"`) — marked TEMPORARY in `style.css`, remove when thumbnails are identified

## Assets

- `assets/top_shots/1.jpg`–`8.jpg` — full-size lightbox images
- `assets/top_shots/thumb_1.jpg`–`thumb_8.jpg` — thumbnail circle images (color, used with CSS grayscale)
- `assets/wheel_bg.png` — Layer 2 background
- `hero.jpg` — Layer 1 full-bleed photo
- `Bumpered_Intro_Video.mp4` — video lightbox source (note underscores, not spaces)
- `assets/Driving_Shots/` — additional raw photos not yet placed on page

## Open Items (from `brief.md`)

- Shane's quote in Layer 4 — pending public use confirmation before going live
- HeyGen video — script written, not recorded; placeholder MP4 in use
- Layers 3, 4, 5 — skeleton only, not yet built
- GSAP ScrollTrigger transitions — Phase 3, not started
- Layer 5 AI widget — Firebase + Claude API, build last
- Mobile responsiveness for Layer 2 wheel — 700px stage will overflow on small screens
