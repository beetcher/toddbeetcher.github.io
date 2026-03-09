# Todd Beetcher — CDL Web Surface

## Surface 1 · Project Brief · March 2026

---

## PURPOSE

A single scrolling page that converts a job application into a callback.
Primary audience: school district transportation directors and club/camp directors.
Secondary audience: technology consultants and developers (this surface is also a
demonstration of AI-assisted web development).

The bar we are clearing: every other applicant is a warm body with a license.
This surface makes clear that Todd is categorically different.

---

## DEVELOPMENT PHILOSOPHY

Skeleton First. Build in this order:

1. Skeleton — all layers, rough content, correct structure
2. Assets — real photos, video placeholder, real copy
3. Transitions — Road animation + horizontal cards (last, not first)
4. Fine tuning — typography, spacing, color, copy polish

One CSS file per HTML file. One JS file per HTML file. No exceptions.

---

## TECH STACK

- HTML / CSS / JavaScript
- GSAP ScrollTrigger — Road/Tracks transition between layers
- CSS scroll-snap — horizontal swipe cards inside Layer 2
- Firebase + Claude API — AI widget (Layer 5, build last)
- GitHub Pages — hosting
- Mobile first

---

## DESIGN SYSTEM

- Background: #1a1a2e (dark navy)
- Accent: #f5c518 (gold)
- Font: Georgia serif
- Tone: proud without performance, warm, human, never corporate

---

## PAGE ARCHITECTURE

Single scrolling page. Five layers plus easter egg.

### LAYER 1 — Hero

Objective: Answer the only question that matters first.
Visitor takeaway: This guy is certified, available, and immediately different.

Content:

- Full bleed photo (hero.jpg — Todd + wife in front of BVSD bus)
- Headline: "Todd Beetcher"
- Subhead: "I can drive tomorrow."
- Credentials line: CDL · School Bus Endorsement · Mountain Certified · Relief Driver
- 60-second video (placeholder for now — swap when HeyGen version is ready)
- Easter egg: subtle fast-track link to Surface 2 (one-of-a-kind/)

### LAYER 2 — Field Trips Are My Specialty — The Wheel
Objective: Show what exceptional looks like in this job. Establish Todd as 
a thought leader on field trips as a brand-building tool.
Visitor takeaway: He raises the brand of transportation whether you ask him 
to or not. And he's thought about this more than anyone you've ever met.

Visual concept — The Bus Wheel:
A bus wheel as the dominant visual metaphor. Dark background. The wheel 
shape is opaque but present. All elements connect to the hub — metaphor 
is intentional: everything radiates from a center point of excellence.

The Hub — center of the wheel:
- A circular video player (consistent with Layer 1 play button pattern)
- Behind the play button: a continuously scrolling marquee of field trip 
  best practices — tips and tricks Todd developed through experience
- Sample marquee items: "Confirm with the teacher a week before.", 
  "Show up 15 minutes early.", "Red carpet at the door.", 
  "Water bottles for every seat.", "Music ready before they board.", 
  "Offer to stop after a win.", "Send a thank you note the same night."
- When video is playing: marquee pauses
- When video is not playing: marquee scrolls continuously
- One or the other — never both simultaneously

The Rim — thumbnails arranged in a circle around the hub:
- 6-8 real artifact photos from Todd's BVSD driving experience
- Displayed in GRAYSCALE by default — intentional, elegant against dark wheel
- On hover: color reveal animation (desaturation to full color)
- Each thumbnail is a spoke — evidence radiating from the best practices hub
- Planned thumbnail subjects (pending asset harvest):
  · Red carpet at bus door
  · Volleyball girls on carpet with Ask Todd button
  · Decorated bus interior
  · Printed joke scripts
  · Water bottles laid out on seats
  · Christmas parade uniform
  · Wedding cake for dispatcher
  · Kids on the bus

Theme copy:
- Section label: "Field Trips Are Your Brand"
- Subhead: "Most drivers show up. Todd shows out. Here's what that looks like."

Technical approach:
- CSS for wheel shape and thumbnail circle positioning
- CSS filter: grayscale(100%) default, filter: none on hover with transition
- JavaScript for marquee scroll behavior and video/marquee toggle
- GSAP ScrollTrigger for Road transition entering this layer (Phase 3)
- All CSS in style.css, all JS in main.js

Assets needed before building:
- 6-8 selected photos from asset harvest (Todd's phone)
- Color + grayscale versions generated via ImageMagick
- Field trip video script written, HeyGen recording pending
- Marquee best practices copy — draft below, Todd to refine

Status: Skeleton placeholder in place. Ready to build after asset harvest.

### LAYER 3 — Raising the Brand

Objective: Show he lifts the whole operation, not just his own bus.
Visitor takeaway: He makes your district look good.

Content — two columns:

- With Coworkers: dressed sharp, Christmas parade, donuts, wedding cake for dispatcher
- With Families & Schools: good mornings, helps with instruments, holiday jokes,
  genuinely present

### LAYER 4 — The Proof

Objective: Let someone else close it.
Visitor takeaway: Don't take his word for it. His dispatcher said it first.

Content:

- Shane's quote (PLACEHOLDER — pending public use confirmation):
  "In all my years, I have never received calls specifically requesting a driver
  by name. I received multiple calls per day requesting Todd."
  — Shane, Dispatcher · Boulder Valley School District
- Supporting proof points:
  · Received tips as a school bus driver
  · Multiple daily name requests — unprecedented at BVSD
  · Families sought him out directly

### LAYER 5 — Call to Action

Objective: Make it completely frictionless to reach him.
Visitor takeaway: I know exactly what to do next.

Content:

- "Available now. CDL active. I can drive tomorrow."
- Contact form or email link
- LinkedIn profile link
- AI widget placeholder (Firebase + Claude API — build last)

---

## EASTER EGG

A subtle link woven into Layer 1 AND a tease before the CTA.
Links to: one-of-a-kind/index.html
Purpose: There's another chapter. Creates curiosity.
Current implementation: ✦ symbol top-left corner, nearly invisible, turns gold on hover.

---

## TRANSITIONS (build in Phase 3, not before)

Selected:

- Road/Tracks animation (GSAP ScrollTrigger) — vertical transition between all layers
- Horizontal swipe cards (CSS scroll-snap) — inside Layer 2 only

Reserved for future use:

- Glitch Cut
- Background Color Morph
- Big Type Slam (strong candidate for Surface 2)

---

## ASSETS AVAILABLE

Photos:

- hero.jpg — Todd + wife in front of BVSD bus (live)
- bus-boulder.jpg — Bus 5501, Flatirons backdrop, red carpet (live)
- Volleyball team photo — red carpet, Ask Todd button, Bus 5501 (to be added)
- Additional photos from BVSD driving (to be harvested from phone)

Video:

- 60-second HeyGen script written, not yet recorded
- Use placeholder until ready

Copy assets:

- Sample confirmation emails (Todd to supply)
- Sample thank you notes (Todd to supply)
- Printed joke scripts (Todd to supply)
- Spotify playlist links (Todd to supply)

---

## OPEN ITEMS

- [ ] Shane's quote — confirm public use
- [ ] Record HeyGen video
- [ ] Upload volleyball/red carpet photo to repo
- [ ] Harvest additional photos from phone
- [ ] Supply sample confirmation email
- [ ] Supply Spotify playlist links
- [ ] Define AI widget concept for Layer 5

---

## SURFACE 2 — ONE OF A KIND (separate, build after Surface 1)

Located at: one-of-a-kind/
Purpose: The Boys & Girls Club summer route. Canyon. Rush hours. No retarder.
The geographically unreplicable drive. Linked as easter egg from Surface 1.

```

---

Once it's in the repo, tell Claude Code:
```

Read BRIEF.md before doing anything.
This is the project specification.
