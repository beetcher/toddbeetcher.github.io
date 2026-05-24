# MASTER BUILD PROMPT v2 — todd.beetcher.com/mentor

## Your Job
Build a complete, mobile-first, single-page website as `index.html` using HTML, CSS, and minimal vanilla JS. This page lives at `todd.beetcher.com/mentor` and is deployed via Cloudflare. Do not over-engineer. No frameworks required. One file.

Set the HTML `<title>` tag to: **A Shared Moment of Growth — Todd Beetcher**
Set the favicon using a simple emoji fallback in the `<head>`: 🤠 (cowboy hat — fits the manifesto, memorable on mobile)

---

## Who This Page Is For
Primary audience: young adults aged 15-22 — high school juniors through college sophomores — who are curious about building things with technology. They are scrolling on their phone. They are a little afraid of AI. They don't know what to do with their ideas. They need a beacon, not a lecture. Write the copy so it speaks directly to someone in that 15-22 range. Not a child. Not yet a professional. Someone figuring it out.

Secondary audience: professors and institutional partners (e.g. a professor named Jeremiah at University of Colorado) who Todd will send this to and ask one question: "Would your students show up for this?"

This page is NOT for parents. It is NOT a sales pitch. It is NOT a resume. It is an invitation.

---

## The Name of the Experience
**A Shared Moment of Growth**

---

## Tone & Design Direction
- Mobile-first. Thumb-scrollable. Every frame works on a phone screen.
- Raw, warm, confident. Not corporate. Not academic. Not a LinkedIn profile.
- Feels like it was written by a real person who has actually lived something.
- Bold typography. Generous spacing. Cinematic imagery.
- Counter the fear narrative around AI — this page is a beacon, not a warning.
- Think editorial/magazine meets personal manifesto. Warm earth tones. Strong type.
- Avoid: purple gradients, Inter font, generic startup aesthetics, anything that looks like a SaaS landing page.

### Color Palette
Use these as your anchors. Build the full palette from them:
- **Background / base**: `#1A1208` (deep warm near-black)
- **Primary text**: `#F5ECD7` (warm off-white, like aged paper)
- **Accent / highlight**: `#C7783A` (burnt sienna — the fire, the desert, the energy)
- **Secondary accent**: `#8B5E3C` (saddle brown — grounded, trustworthy)
- **Frame dividers / subtle elements**: `#2E1F0E` (dark walnut)

### Typography
Use Google Fonts. Load exactly these two:
- **Display / headlines**: `Playfair Display` — bold, editorial, warm serif. Use for all major headlines and frame titles.
- **Body / copy**: `DM Sans` — clean, modern, readable at small sizes on mobile. Use for all paragraph text, questions, and captions.

Do NOT use Inter, Roboto, Arial, or any system font.

---

## Core Thesis — Never Lose This
System-level thinking is the through-line of the entire page. Everything ladders up to it.

Not knowing Python is a gift, not a penalty. AI removes the need to be a coding expert — freeing young people to think at the system level. That is what nobody is teaching. This experience teaches it.

The experience goes: **Friction → Idea → Ecosystem → Architecture → MVP**

---

## Key Phrases — Use These Verbatim
- "From problem to product"
- "A gift, not a penalty"
- "Project-based. Experiential. Collaborative."
- "System-level thinking"
- "A Shared Moment of Growth"
- "Don't tend your fire alone"
- "Come grow with us"

---

## Navigation
No top navigation bar. No hamburger menu. This is a pure scroll experience — frame to frame, top to bottom. The only navigation element is a subtle scroll-down indicator on Frame 1 (an animated chevron or arrow, pulsing gently). No sticky header. Nothing that interrupts the scroll.

---

## Scroll Animation Behavior
All text content below the fold animates in on scroll using CSS only — no JS animation libraries. Use this consistent pattern throughout:
- Elements start at `opacity: 0` and `transform: translateY(24px)`
- On entering the viewport (use IntersectionObserver in vanilla JS — minimal, clean), transition to `opacity: 1` and `transform: translateY(0)`
- Transition duration: `0.6s ease-out`
- Stagger child elements within a frame using `animation-delay` increments of `0.1s`
- Apply this to: headlines, question cards, copy paragraphs, images, and CTA elements
- Frame 1 opening image is exempt — it loads immediately, no animation

---

## Page Structure — Frame by Frame

### FRAME 1 — Opening Image (no words)
- Full-bleed image: `assets/images/opening-lift.jpg`
- Todd being lifted by groomsmen at his daughter's wedding. Arms raised. Purple lights. Pure joy.
- No caption. No copy. Just the image.
- On mobile this fills the entire screen — 100vh.
- Job: stop the thumb. Make them ask "who is this guy?"
- Subtle animated scroll indicator at bottom — a soft pulsing chevron pointing down, color `#C7783A`

---

### FRAME 2 — The Hook Questions
Short intro line above the questions:
*"A few questions. Answer honestly."*
(Set in DM Sans, smaller, uppercase tracking, accent color)

Questions styled as large, bold Playfair Display — one per stacked card with a thin left border in `#C7783A`:
1. Do you see problems everywhere but don't know what to do with them?
2. Do you have ideas but no clue how to actually build something?
3. Do you want to work with others to build something real — not just talk about it?
4. Do you want to walk out of a room having gone from idea to prototype?

Closing line below the questions, DM Sans, warm italic:
*If you said yes to any of these — keep reading.*

---

### FRAME 3 — The Reframe
Counter the fear. This is the emotional core of the page.

**Visual treatment**: Dark background frame — use `#1A1208`. Large, centered Playfair Display headline at top:
**"This isn't what you think it is."**

Then the copy beats below in DM Sans, generous line height, warm off-white text:
- This isn't a coding class.
- It isn't an entrepreneurship class.
- It isn't an engineering class.
- It's about learning to coexist with the most powerful productivity tool ever handed to a generation — before everyone else figures out they have to.
- Not knowing Python isn't a weakness. **It's a gift.**
- You don't need to speak a programming language anymore. You need to think at the system level. That's the skill that transfers everywhere — whether you're building a company, designing a product, fixing a problem in your community, or figuring out your place in a world that's moving fast.
- AI is here. It's everywhere. It's only growing. The ones who embrace it first won't just survive the change. They'll define it.

Style the words **"It's a gift."** in `#C7783A` accent color, slightly larger — this is the emotional peak of the frame.

---

### FRAME 4 — What This Experience Is
Header: **A Shared Moment of Growth**
(Playfair Display, large, centered)

Copy in DM Sans:
- Project-based. Experiential. Collaborative.
- You'll come into a room with other people who have ideas and ambition but don't know where to start.
- Together you'll identify real friction — problems you actually see in the world.
- You'll learn to think about the ecosystem around that problem.
- You'll architect a real solution.
- You'll build a real prototype — together, as a team.
- This is system-level thinking from the very first moment to the last.
- No silos. No solo coding. No theory without practice.
- At the end, you'll have something real. Something you built. Something you can show anyone.

Visual: Display the process arc below the copy as a horizontal (desktop) or vertical (mobile) flow graphic using pure CSS/HTML — no image needed:
**Friction → Idea → Ecosystem → Architecture → MVP**
Style each step as a pill/badge in `#C7783A` connected by thin lines.

---

### FRAME 5 — What You Walk Away With
Large, bold, simple. Playfair Display. Let the words breathe. Dark background `#1A1208`.

- The ability to see a problem and know what to do with it.
- Experience going from friction to prototype — start to finish.
- The confidence of a system-level thinker.
- Something you built with your own hands and your own mind.

Final line, larger, accent color `#C7783A`, Playfair Display bold italic:
**"From problem to product. That's the new résumé."**

---

### FRAME 6 — About Todd
Two-column layout on desktop. Stacked on mobile.

**Left/Top: Photo**
- `assets/images/todd-mic-drop.jpg`
- Todd in a tux, mic raised, drink in hand, daughter laughing behind him at her wedding.
- Do not caption it. Let it speak.
- Slight warm color grade on the image using CSS filter if possible — `sepia(15%) contrast(105%)`

**Right/Bottom: Copy**
DM Sans body, Playfair Display for any emphasis lines.

*My name is Todd Beetcher. I married my high school sweetheart in 1984. We're going on a date tonight.*

*We raised two daughters.*

*Both were state champions. Both earned Division I full-ride athletic scholarships. Both became doctors — one in physical therapy, one in law. Both are prom queens. Both are homecoming queens. Both are in healthy, committed relationships.*

*One is moving to Michigan. She asked us to come live near her.*

*The other is 26, billing 200 hours a month, and still comes to Sunday dinners.*

*Half my peers are divorced. Half their kids didn't make it through.*

*I'm not telling you this to brag. I'm telling you this because if you're going to trust someone to stand at the front of a room with your kid — or if you're a kid deciding whose room to walk into — you deserve to know who's standing there.*

*I have spent my career in business development, sales, and building — in rooms where ideas become products. I've been part of building things before the world knew it needed them. I know how to walk people from the beginning of something all the way to the end. That's what I do. That's what I've always done.*

*My kids are my proof. Not what I built — what I raised.*

---

**PS Section** (cheeky, smaller DM Sans type, slightly muted color, below main copy):
- `assets/images/webpad-team.jpg` — display as a small-to-medium image, slightly aged/warm treatment
- Caption beneath image: *Cyrix WebPAD Conceptual Products Group, Longmont Colorado. Todd Beetcher, second from left.*
- Copy above image: *If you're wondering who to thank for that iPad in your pocket — you're welcome.*

---

### FRAME 7 — The Manifesto
Full-bleed background image: `assets/images/cowboy-aerial.jpg`
Aerial shot of a lone cowboy by his campfire, horse nearby, surrounded on all sides by a modern city at golden hour.

Apply a dark gradient overlay: `linear-gradient(to bottom, rgba(26,18,8,0.3) 0%, rgba(26,18,8,0.75) 100%)`

Overlay text — white `#F5ECD7`, centered, generous horizontal padding (max-width 680px on desktop, full-width with padding on mobile):

**The Cowboy**
(Playfair Display, large, centered headline)

*There's nothing wrong with the cowboy.*

*He was the original get-shit-done contributor. Not for himself — for his family, his community, the people who counted on him to show up. That was the cowboy spirit. And it still is.*

*The world built highways around him. Not because he failed. Because he stopped picking up new tools.*

*AI is the next tool. And it's not coming — it's here. Everywhere. All the time. Growing.*

*The cowboys and cowgirls who thrive in this moment won't be the ones who learned to write Python. They'll be the ones who learned to think at the system level — who can look at a problem, understand the whole ecosystem around it, and build something real from that.*

*That's the new cowboy skill. That's what nobody is teaching.*

*We're not here to make you an engineer. We're not here to make you an entrepreneur. We're here to give you the confidence and the identity to pick up the most powerful tool ever handed to a generation — and use it to contribute. To your community. To your family. To the world you're about to help build.*

*You can still be a cowboy. But you have to pick up the new tools.*

*Don't tend your fire alone.*

---

### FRAME 8 — Show Up (CTA)
Clean. Simple. Dark background `#1A1208`. Nothing competes with the CTA.

Large Playfair Display headline, centered:
**This is the moment. Come grow with us.**

Single button — styled in `#C7783A` background, `#F5ECD7` text, no border-radius (square edges feel intentional and strong), generous padding, DM Sans bold uppercase:
**[ GET IN TOUCH ]**

Wire this button to: `mailto:todd@beetcher.com`
(Placeholder — Todd to replace with actual contact destination before launch)

Optional one-line subtext below button, small DM Sans, muted:
*A Shared Moment of Growth — todd.beetcher.com/mentor*

---

## Footer
Simple, minimal. Dark background `#1A1208`. Small DM Sans text, muted color `#8B5E3C`.

Left: `© 2025 Todd Beetcher`
Center: `todd.beetcher.com`
Right: Three subdomain links — `todd.beetcher.com/driver` | `todd.beetcher.com/builder` | `todd.beetcher.com/mentor`

Single thin top border in `#2E1F0E` separating footer from Frame 8.
No social icons unless Todd adds them later. Keep it clean.

---

## Assets Map
| Filename | Frame | Description |
|---|---|---|
| `assets/images/opening-lift.jpg` | Frame 1 | Todd lifted by groomsmen, arms raised, wedding dance floor |
| `assets/images/todd-mic-drop.jpg` | Frame 6 | Todd in tux, mic raised, commanding the room |
| `assets/images/webpad-team.jpg` | Frame 6 PS | Cyrix WebPAD team photo, Todd listed in caption |
| `assets/images/cowboy-aerial.jpg` | Frame 7 | Aerial cowboy campfire surrounded by modern city |
| `assets/video/wedding-dance.mov` | Optional | Background loop candidate for Frame 1 if image isn't enough |

---

## Technical Requirements
- Single `index.html` file — all CSS and JS inline or in `<style>` and `<script>` tags
- `<title>`: A Shared Moment of Growth — Todd Beetcher
- Favicon: emoji cowboy hat via `<link rel="icon" href="data:image/svg+xml,...">` inline SVG or emoji trick
- Mobile-first CSS — start with mobile styles, use `min-width` media queries to scale up to desktop
- Smooth scroll between frames: `scroll-behavior: smooth` on `html`
- Images use `object-fit: cover` for all full-bleed frames
- Deployed to Cloudflare — zero server-side dependencies, no build step, pure static
- No frameworks required — vanilla HTML, CSS, JS only
- Fonts loaded from Google Fonts: `Playfair Display` (display) + `DM Sans` (body)
- Scroll animations via IntersectionObserver — CSS transitions only, no animation libraries
- Animation pattern: `opacity 0→1`, `translateY 24px→0`, duration `0.6s ease-out`, stagger `0.1s` per child
- Frame 1 image exempt from scroll animation — loads immediately
- The page must feel fast on mobile — optimize image loading with `loading="lazy"` on all images below Frame 1
- `max-width: 800px` centered container for all text content frames
- Full-bleed frames (1, 7) break out of container to edge-to-edge

---

## What Success Looks Like
A 19-year-old scrolls through this on their phone and says: *"I want to show up for whatever this is."*

A professor reads it and says: *"Would my students resonate with this? Yes."*

A parent stumbles on it and feels something unexpected — not anxiety about their kid's future, but hope.

Build it. One shot. Make it real.