# BRIEF.md — Todd Beetcher CDL Web Surface
## Project Reference Document · Last Updated March 2026

> **Claude Code: Read this file at the start of every session before making any changes.**

---

## PURPOSE

A single scrolling page that converts a job application into a callback.
Primary audience: school district transportation directors and club/camp directors.
Secondary audience: technology consultants and developers — this surface is also a
demonstration of AI-assisted web development.

The bar we are clearing: every other applicant is a warm body with a license.
This surface makes clear that Todd is categorically different.

**Primary targets:** St. Vrain Valley School District (Longmont) and Dawson School (Boulder area)

Todd is not an ordinary bus driver. He built a white-glove field trip experience from scratch at BVSD and was requested by name daily — something his dispatcher Shane said he had never seen in his entire career. This site proves that.

---

## DEVELOPMENT PHILOSOPHY

Skeleton First. Build in this order:

1. Skeleton — all layers, rough content, correct structure
2. Assets — real photos, video placeholder, real copy
3. Transitions — Road animation + horizontal cards (last, not first)
4. Fine tuning — typography, spacing, color, copy polish

One CSS file per HTML file. One JS file per HTML file. No exceptions.

---

## LIVE SITE & REPO

- **Live URL:** https://beetcher.github.io/toddbeetcher.github.io/
- **Repo on M4 Mini:** `~/nd/bd/toddbeetcher.github.io/`
- **Repo on M1 MacBook Air:** `~/nd/bd/toddbeetcher.github.io/`
- **GitHub:** https://github.com/beetcher/toddbeetcher.github.io

**Push:**
```bash
cd ~/nd/bd/toddbeetcher.github.io && git add . && git commit -m "message" && git push origin main
```
**Pull:**
```bash
cd ~/nd/bd/toddbeetcher.github.io && git pull origin main
```

**Machines:** M4 Mini = primary dev. M1 MacBook Air = secondary/asset harvest/video compression.
Always verify in Live Server before committing. Commit at every clean checkpoint.

---

## TECH STACK

- HTML / CSS / JavaScript
- GSAP ScrollTrigger — Road/Tracks transition between layers (Phase 3, not yet built)
- CSS scroll-snap — horizontal swipe cards inside layers
- Firebase + Claude API — AI widget (Layer 5, build last)
- GitHub Pages — hosting
- Mobile first

---

## DESIGN SYSTEM

| Element | Value |
|---|---|
| Gold (headlines only) | `#f5c518` |
| White (all body text) | `#ffffff` |
| Deep red (interactive accents, play button) | `#c0392b` |
| Navy (dark backgrounds) | `#1a1a2e` |
| Font | Georgia serif throughout |
| Thumbnail shape | Circular, gold borders |
| Hover metaphor | Grayscale → color (images "come alive") |
| Aesthetic | Dark, cinematic — NOT cheerful or cartoonish |

---

## PAGE ARCHITECTURE — BUILD STATUS

Single scrolling page. Five layers plus easter egg. All in one `index.html`.

```
LAYER 1  — Hero                                            ✅ COMPLETE
LAYER 2  — This Is What Showing Up Looks Like (The Wheel)  ✅ BUILT (minor punch list)
LAYER 3  — Field Trips Are My Specialty (Animated Map)     🔲 SPRINT 1 NEXT
LAYER 4  — The Proof                                       🔲 SKELETON ONLY
LAYER 5  — Call to Action                                  🔲 SKELETON ONLY
```

---

## LAYER 1 — HERO
**Status: COMPLETE ✅**

**Objective:** Answer the only question that matters first.
**Visitor takeaway:** This guy is certified, available, and immediately different.

Full-bleed photo: `hero.jpg` (Todd + wife in front of BVSD bus)

**Elements:**
- Top-left: Name and credentials
  - `Todd Beetcher` — gold, Georgia serif
  - `CDL · School Bus Endorsement · Mountain Certified` — white
  - `Available to drive tomorrow.` — white, slightly smaller
- Dead center: Circular play button
  - Color: `#c0392b` ring and triangle
  - Animation: 3 concentric expanding rings (ripple), staggered 0.8s each, 2.4s loop
  - Click: Opens video lightbox
- Top-left easter egg: `✦` symbol links to Surface 2 (`one-of-a-kind/`)

**Video lightbox:**
- Source: `assets/Videos/Joy_CDL/Joy_Bumpered_01_compressed.mp4`
- CSS: `max-height: 90vh; max-width: 90vw; width: auto; height: auto;`
- Close: Escape key or click outside

---

## LAYER 2 — THE WHEEL
**Status: BUILT ✅ (minor punch list remaining)**

**Objective:** Show what exceptional looks like in this job. Establish Todd as a thought leader on field trips as a brand-building tool.
**Visitor takeaway:** He raises the brand of transportation whether you ask him to or not.

**Section title:** "THIS IS WHAT SHOWING UP LOOKS LIKE"

**Concept:** A bus wheel as the dominant visual metaphor. Dark navy background. Wheel shape (`assets/wheel_bg.png`) sits as opaque backdrop. Everything radiates from a center point of excellence.

**The Hub — center:**
- Circular video player (same `#c0392b` ring as Layer 1 — consistent pattern)
- When video NOT playing: continuously scrolling marquee of field trip best practices
- When video IS playing: marquee pauses
- One or the other — never both simultaneously

**Marquee items:**
- "Confirm with the teacher a week before."
- "Show up 15 minutes early."
- "Red carpet at the door."
- "Water bottles for every seat."
- "Music ready before they board."
- "Offer to stop after a win."
- "Send a thank you note the same night."
- "Pick a boarding song. Play it every time. Kids hear it from the parking lot."

**The Rim — 8 thumbnails in a circle:**
- Source: `assets/top_shots/thumb_bw_1.jpg` through `thumb_bw_8.jpg`
- Displayed in grayscale by default
- Hover: `filter: grayscale(0)` transition — color reveal
- Click: Opens lightbox with full-size color image + caption

**Thumbnail assignments:**

| # | Photo | Caption |
|---|---|---|
| 1 | Todd + wife in front of BVSD bus | "That's my wife. She works at a school district. It's her fault." |
| 2 | Bus 5501, red carpet, Flatirons | "The red carpet wasn't required. Neither was anything else on this list." |
| 3 | Volleyball girls on red carpet | "They didn't ask for a red carpet. I brought one anyway." |
| 4 | Ask Todd Anything selfie, mountain backdrop | "Ask Todd Anything button. Mountain route. Different job, same standard." |
| 5 | Wedding cake at dispatch | "Shane labeled it 'Cake by Shane.' Shane did not make the cake." |
| 6 | Framed letter inside the cake | "A silver dollar inside. A framed letter outside. A dispatch office that still talks about it." |
| 7 | Driver's seat, kids in mountain meadow through windshield | "That's not a stock photo. That's a Wednesday in June." |
| 8 | Christmas parade / culture shot | "Nobody asked anyone to wrap a school bus in Christmas lights. Some people do the job. Some people change the culture of the place. This is what that looks like." |

**Punch list remaining:**
- Hub text centering (minor CSS)
- Remove temporary number labels from thumbnails
- Verify marquee/video toggle works correctly

---

## LAYER 3 — FIELD TRIPS ARE MY SPECIALTY
**Status: SPRINT 1 READY TO BUILD 🔲**

**Objective:** Show he lifts the whole operation, not just his own bus.
**Visitor takeaway:** He makes your district look good.

**Concept:** Animated Longmont school district map. Dark navy. Stylized gold street grid. School bus animates along a route, stopping at 7 schools. Each stop reveals a photo with caption. Click the bus = video easter egg.

**Section title:** "Field Trips Are Your Transportation Department's Secret Weapon" *(to be finalized)*

**3 Download buttons:** Field Trip Manual | FAQ | Best Practices *(PDFs built — see ASSETS)*

**7 Route Stops — St. Vrain Valley School District:**

| # | School | SVG Position | Level |
|---|---|---|---|
| 1 | Longmont High School | Center (400, 300) | High School |
| 2 | Timberline PK-8 | East (620, 280) | PK-8 |
| 3 | Sunset Middle School | South (420, 480) | Middle |
| 4 | Trail Ridge Middle School | West (180, 300) | Middle |
| 5 | Central Elementary | Downtown (380, 250) | Elementary |
| 6 | Fall River Elementary | North (400, 120) | Elementary |
| 7 | Blue Mountain Elementary | Northwest (200, 150) | Elementary |

**Map visual spec:**
- SVG 800×600px desktop, scales to 95vw mobile
- Background: `#1a1a2e`
- Street lines: thin gold at 20% opacity, 1–2px stroke
- Major roads: 30% opacity, slightly thicker
- School dots: filled gold circles, 8px radius, `#f5c518`
- Labels: white, 11px Arial, offset above/below dot
- Pulse animation per dot: scale 1→1.4, opacity 1→0, 2s loop, staggered 0.3s

**Bus animation behavior:**
- Small SVG school bus moves route on loop
- Arrives at stop → pauses → photo + caption reveals
- Click photo or wait 4s → closes → bus continues
- Click bus at any time → video lightbox (easter egg)
- Optional background music, muted by default

**Build sprints for Claude Code:**

| Sprint | What to build | Status |
|---|---|---|
| 1 | Static map — SVG, street grid, 7 dots with labels, pulse animation | 🔲 NEXT |
| 2 | Bus icon — static SVG bus at Stop 1 | 🔲 |
| 3 | Route path — invisible path connecting all 7 stops | 🔲 |
| 4 | Bus animation — animate along path, pause at stops | 🔲 |
| 5 | Photo reveals — photo + caption at each stop | 🔲 |
| 6 | Easter egg — click bus opens video lightbox | 🔲 |
| 7 | Title + download buttons | 🔲 |
| 8 | Audio — optional background music with mute button | 🔲 |

---

## LAYER 4 — THE PROOF
**Status: SKELETON ONLY 🔲**

**Objective:** Let someone else close it.
**Visitor takeaway:** Don't take his word for it. His dispatcher said it first.

Shane's quote *(PENDING PUBLIC USE CONFIRMATION — do not publish until confirmed)*:
> "In all my years, I have never received calls specifically requesting a driver by name. I received multiple calls per day requesting Todd."
> — Shane, Dispatcher · Boulder Valley School District

Supporting proof points:
- Received tips as a school bus driver
- Multiple daily name requests — unprecedented at BVSD
- Families sought him out directly

**⚠️ Do not build this layer until Shane's quote is confirmed for public use.**

---

## LAYER 5 — CALL TO ACTION
**Status: SKELETON ONLY 🔲**

**Objective:** Make it completely frictionless to reach him.
**Visitor takeaway:** I know exactly what to do next.

Content:
- "Available now. CDL active. I can drive tomorrow."
- Contact form or email link
- LinkedIn profile link
- AI widget (Firebase + Claude API — build last)
- Easter egg tease pointing to Surface 2

---

## EASTER EGG

Subtle link in Layer 1 AND a tease before the CTA.
Links to: `one-of-a-kind/index.html`
Current implementation: `✦` symbol top-left corner, nearly invisible, turns gold on hover.

---

## FILE STRUCTURE

```
toddbeetcher.github.io/
├── index.html              — main site, all layers
├── style.css               — all styles
├── main.js                 — lightbox + marquee + thumbnail behavior
├── BRIEF.md                — THIS FILE
├── OG_brief.md             — original brief backup
├── hero.jpg                — Todd + wife in front of BVSD bus
├── bus-boulder.jpg         — Bus 5501, red carpet, Flatirons
├── assets/
│   ├── wheel_bg.png        — AI-generated bus wheel backdrop for Layer 2
│   ├── Videos/Joy_CDL/
│   │   ├── Joy_Bumpered_01_compressed.mp4     (13MB) ✅ HERO VIDEO
│   │   ├── Joy_CDL_1_compressed.mp4           (21MB) ✅
│   │   ├── Joy_CDL_04_w_Blur_compressed.mp4   (13MB) ✅
│   │   ├── Joy_CDL_04_1080p_caption_compressed.mp4 (12MB) ✅
│   │   ├── Joy_CDL_2_1080p_caption_compressed.mp4  (13MB) ✅
│   │   └── [originals — gitignored, local only, 56–125MB each]
│   ├── Voice_Recordings/   — source audio, local only
│   └── top_shots/
│       ├── 1.jpg – 8.jpg             — full-size color photos
│       ├── thumb_1.jpg – thumb_8.jpg — 300×300 color thumbnails
│       └── thumb_bw_1.jpg – thumb_bw_8.jpg — 300×300 grayscale thumbnails
└── one-of-a-kind/          — Surface 2 (not yet built)
```

**Current .gitignore:**
```
.DS_Store
*.MOV
*.mov
assets/Videos/Joy_CDL/Joy_CDL_1.mp4
assets/Videos/Joy_CDL/Joy_Bumpered_01.mp4
assets/Videos/Joy_CDL/Joy_CDL_04_w_Blur.mp4
assets/Videos/Joy_CDL/Joy_CDL_04_1080p_caption.mp4
assets/Videos/Joy_CDL/Joy_CDL_2_1080p_caption.mp4
```

---

## ASSETS — FIELD TRIP DOCUMENTS

Three downloadable docs built. Branded navy/gold, footer: `Todd Beetcher · CDL · School Bus Endorsement · Mountain Certified · ToddDrives.com`

| Document | Contents |
|---|---|
| Field Trip Handbook | White Glove Field Trip Framework — 5 phases, Shane quote |
| Field Trip FAQ | 8 questions in Todd's voice, covers BVSD departure, certs, proof |
| Field Trip Best Practices | Printable short list. Ends with "The One Rule." |

*(Rebuild from `field_trip_docs.js` if needed.)*

**Copy assets still needed from Todd:**
- Sample confirmation emails
- Sample thank you notes
- Printed joke scripts
- Spotify playlist links

---

## TODD'S DRIVING CREDENTIALS & WHITE GLOVE SYSTEM

**Credentials:**
- CDL (Commercial Driver's License)
- School Bus (S) Endorsement
- Mountain Certification
- Drove for Boulder Valley School District (BVSD)
- Drove the Boys & Girls Club of Metro Denver summer mountain route:
  - Boulder → Lakewood depot → Denver rush hour → 60–70 kids → Boulder rush hour → 17 miles up Left Hand Canyon → ~8,500 ft day camp near Ward, CO
  - No retarder. Navigated on skill and mountain cert alone.

**White glove field trip system:**
- Pre-trip confirmation emails to teachers
- Custom printed dad jokes by sport and age group
- Red carpet at the bus door
- Water bottles for every seat
- Wired music system with Spotify playlists (Golf, We Won, We Lost, General)
- Boarding song and deboarding song — kids hear it from the parking lot
- Humorous safety instructions
- Post-trip thank you notes referencing specific moments
- Late-night lost item returns
- Wedding cake for dispatcher Shane + framed letter with silver dollar inside

---

## SURFACE 2 — ONE OF A KIND (Build after Surface 1)

Location: `one-of-a-kind/`
Subject: Boys & Girls Club summer mountain route. Canyon. Two rush hours. No retarder.
The geographically unreplicable drive. Linked as easter egg from Surface 1.
Full narrative document exists.

---

## TRANSITIONS

**Reserved — build in Phase 3, not before:**
- Road/Tracks (GSAP ScrollTrigger) — vertical between layers
- CSS scroll-snap — horizontal within layers

**Reserved for future surfaces:**
- Glitch Cut
- Background Color Morph
- Big Type Slam (strong candidate for Surface 2)

---

## VIDEO PIPELINE

**ffmpeg compression:**
```bash
ffmpeg -i [input].mp4 -vcodec h264 -crf 28 -preset slow [output]_compressed.mp4
```
Result: 56–125MB → 12–21MB, no visible quality loss.

**ImageMagick thumbnail generation:**
```bash
cd assets/top_shots && for f in [1-8].jpg; do
  magick "$f" -resize 300x300^ -gravity center -extent 300x300 "thumb_${f}"
  magick "$f" -resize 300x300^ -gravity center -extent 300x300 -colorspace Gray "thumb_bw_${f}"
done
```

**HeyGen** (active paid subscription):
- Layer 3 field trip hub video — script written, not yet recorded
- Process: record footage → Digital Twin → HeyGen avatar → CapCut edit → ffmpeg compress

---

## DOMAINS

Purchasing via Hover. Final lead domain TBD: ToddDrives.com or RideWithTodd.com
PDFs reference `ToddDrives.com` as placeholder.

---

## CLAUDE CODE PROMPT GUARDRAILS

Every Claude Code prompt must:

1. Start with: `Read BRIEF.md.`
2. Name the exact layer being modified
3. List constraints — files to touch AND files NOT to touch
4. Specify: CSS → `style.css`, JS → `main.js`
5. End with: `You must wait for my explicit confirmation before making any changes. Do not proceed until I type "Confirmed".`

Verify in Live Server before every commit. Never commit broken code.

---

## OUTSTANDING WORK — PRIORITY ORDER

1. **Layer 3 Sprint 1** — Static Longmont map (SVG, 7 stops, pulse animation)
2. **Layer 3 Sprints 2–8** — Bus animation, photo reveals, easter egg, buttons, audio
3. **Layer 2 punch list** — Hub text centering, remove temp number labels
4. **Confirm Shane's quote** for public use → then build Layer 4
5. **Layer 5** — CTA, AI widget, easter egg tease
6. **Buy domain** — via Hover
7. **Record HeyGen video** for Layer 3 field trip hub
8. **Surface 2** — One of a Kind
9. **GSAP ScrollTrigger transitions** — add after all layers have real content

---

*Single source of truth. Update this file whenever architecture changes.*