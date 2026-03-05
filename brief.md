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

### LAYER 2 — Field Trips Are My Specialty
Objective: Show what exceptional looks like in this job.
Visitor takeaway: He raises the brand of transportation whether you ask him to or not.

Content — horizontal swipe cards (photo album feel, CSS scroll-snap):
- Card 1: The Confirmation Email
  "Months after booking, families hadn't heard a word. Todd reached out first."
- Card 2: The Red Carpet
  Photo: bus-boulder.jpg or volleyball photo with red carpet + Ask Todd button
  "Red carpet at the door. Water bottles. Custom dad jokes. Every trip."
- Card 3: The Music
  Pre-built Spotify playlists: Golf · We Won · We Lost · General
  Link to actual playlists when available.
- Card 4: The Follow-Through
  "Thank you note after every trip. Something specific. Offer to drive again.
  Returns lost items at 10pm if needed."

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