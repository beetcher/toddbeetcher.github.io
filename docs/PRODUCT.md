# Masthead product baseline

Source inspection: November 10, 2026, branch `finish-now`, HEAD `61cd00de475cead8c53ba3589ab0e2476da1e46b`.

This describes the Masthead at repository root, not the independent products sharing this repository. **Verified in code** means inspected in local source, not verified on the deployed site. **Documented intent** identifies written direction; **Unconfirmed** identifies gaps. Historical plans and creative archives are not blanket approval to build them.

## Purpose and visitor promise

**Verified in code:** `index.html` introduces Todd through “Make AI useful. Make people capable.” It connects hands-on AI building, business judgment, learning, mentoring and personal life. Its stated audiences include businesses, schools and people unsure where to begin. The invitation is to inspect work, explore deeper material and have a conversation.

**Inference:** The Masthead serves as a personal introduction and evidence hub for potential collaborators, employers, educators and people who might make an introduction. The NVIDIA route explicitly supports an employment conversation; the default page is broader.

**Documented intent:** `docs/masthead/WELCOME-PARKING-LOT.md` asks for an authentic, personal, entertaining, clever and discoverable experience, with a short main read and optional sideways depth. The current introduction letter describes that same reading pattern. The older CDL-focused `brief.md` and much of `CLAUDE.md` describe a previous homepage; they do not accurately inventory the current root page.

## Visitor journey and navigation

**Verified in code — `index.html`:** A `REVIEW DRAFT / 03` banner explicitly says story material is missing. A skip link targets `#main`. Header navigation retains the work, people, approach, person and conversation destinations and permanently offers Meet Todd and Take a quick tour buttons when native dialog support is available. The brand returns to `#contribution`. A sticky `.application-access` strip offers the résumé preparation route, application directory and route-welcome reopening button. Two independent invitations float above the main panel without occupying normal document flow: Meet Todd has a stronger border/background and slightly greater desktop width; Take a quick tour sits beside it. Each has its own accessible X button and original clickable invitation copy. They stack on narrow screens and scroll with the page. JavaScript/native-dialog support is required to expose letter controls.

| Order / anchor | Current content and onward path |
| --- | --- |
| Letter choices / welcome dialog | Fresh generic, school and invalid/unrecognized visits see both unserviced floaters with no automatic letter. NVIDIA retains its undismissed employer auto-welcome. Permanent letter navigation remains available after servicing either floater. See lifecycle below. |
| `#contribution` | Hero, portrait, purpose and “Start with something I built” link to `#built`. |
| `#opportunity` | Conditional authored audience note after the hero, with suggested reading and a small reveal. Hidden for generic/invalid URLs. |
| `#built` | LAUNCH venue-discovery console narrative, human-review workflow schematic, case-study link `/work/launch-console/`; range links to `/field-notes/everyday-possibilities/`. This page describes the console; it does not embed it. |
| `#people-helped` | Mentoring/speaking introduction; amber Silicon Flatirons and Beck Center story spaces awaiting Todd’s material. |
| `#becoming-capable` | Dome-light example and proposed Notice → Frame → Try → Check → Return learning sequence. `#the-moment` is a compatibility anchor here. Links to recognition field note, coaching and learning reader. |
| `#judgment` | Business/systems thinking, independent NOCTI proposal presentation, WebPAD background, and downloadable `/downloads/seeing-around-the-corner.pdf`. |
| `#the-person` | Field-trip care, family, outdoor life and curiosity; links to driver story and `/field-notes/what-we-pass-forward/`. |
| `#starting-here` | Proposed first-week and follow-up approach; capability, continued use and useful work questions. This is an approach, not a delivered engagement or measured outcome. |
| `#application-documents` | NVIDIA-only document panel; résumé and opportunity-specific cover letter preparation pages. |
| `#conversation` | “Let’s talk” mailto CTA, visible email address, conditional copy button and live status. |
| Footer | Brand return, Boulder location and LinkedIn profile. |

Meet Todd (`#meet-todd-letter`) contains all 26 exact paragraphs from the read-only approved source `docs/source/meet-todd-approved.md`, preserving punctuation, order and paragraph boundaries. Its first line is “I’m glad you’re here with me today.” The dialog’s external label supplies its title without inserting an authored heading. Take a quick tour always opens the original general letter, including on NVIDIA.

The general letter (`#generic-welcome`) begins “AI arrived. I dove in.” and explains Todd’s transition, recognition habit, human responsibility, examples, programs and invitation. It links to Enjoy and ends with Todd’s signature. The employer letter (`#employer-welcome`) is shorter, describes an application that demonstrates change, and explicitly says documents are being prepared. The school profile gets the general letter, not a separate education letter.

The persistent routes `/application/`, `/application/resume/`, and `/application/nvidia/cover-letter/` are real HTML preparation pages, usable without JavaScript. They are not completed résumé/letter documents or fake PDF downloads. See `docs/masthead/APPLICATION-CONTENT-REGISTER.md` for the source-content requirements and opportunity mapping.

## Features and non-obvious behavior

**Verified in code — `assets/masthead/masthead.js` and `.css`:**

- `.copy-email` becomes visible only when both Clipboard API and a secure context exist. It writes Todd’s displayed address; `#copy-status` announces success or asks the visitor to select/copy the address on failure. Direct mailto links remain available.
- Opportunity notes can be closed with their button or Escape while focus is inside the panel. `closeNote()` stores `masthead-note-dismissed:nvidia` or `masthead-note-dismissed:school` as `true`, hides the panel, reveals its reopening strip and focuses that button. Reopening removes that note key, focuses its heading and scrolls to it. This storage is independent of letter dismissal.
- `#surprise-button` (“One more connection”) toggles `#surprise-note` and `aria-expanded`: the backend console and brisket share the same curious person. Available only with an active profile. It is an authored reveal, not generated content.
- An `IntersectionObserver` at threshold `0.12` adds `.is-in-view` once to the opportunity panel, triggering staggered connection-node animation. Without the API the class is applied immediately. Reduced-motion CSS suppresses animations/transitions and smooth scrolling.
- Native `<details class="signal-detail">` reveal editorial prompts for missing source material; they are visible draft features, not finished visitor stories.
- Responsive CSS collapses grids and retains the existing hiding of header story links other than contact at widths up to 760px. The two permanent letter buttons remain visible in the wrapping header navigation. Document access remains separate. Print rules hide dialog/access controls and opportunity panels. These are source rules, not a current visual QA result.
- The upper-left `tb.` triple-click is a letter reset Easter egg; details below. No other hidden homepage trigger is implemented in this script.

## URL-driven experiences and precedence

**Verified in code:** `profiles` and `selectedProfile()` in `assets/masthead/masthead.js` support exactly two authored IDs. Names/`for` values are lowercased; values are not trimmed. Selection depends only on the current URL, never a stored company identity.

| Query examples | Result |
| --- | --- |
| `?nvidia`, `?NVIDIA`, `?nvidia=`, `?for=nvidia`, `?FOR=NVIDIA` | NVIDIA employer profile: employer welcome, employer document links and panel, plus NVIDIA opportunity note. |
| `?school`, `?school=`, `?for=school` | Education concept note; general welcome; no employer document panel. |
| No recognized selector, e.g. `?utm_source=example` | Generic page and general letter. Unrelated keys are ignored. |
| `?for=unknown`, `?for=`, `?nvidia=yes`, `?school=1` | Invalid selection; generic page. |
| `?nvidia&school`, `?nvidia&for=nvidia`, `?for=school&for=school` | Multiple choices, even duplicate identical choices: generic page. |
| `?for=nvidia&for=unknown` | Any invalid recognized selector invalidates the whole selection. |

There is **no first/last-wins precedence**: exactly one valid recognized choice and no invalid recognized selector is required. `?nvidia&utm_source=example` still selects NVIDIA. Arbitrary query values are not inserted as audience content.

NVIDIA note links: `#built`, `#people-helped`, `#starting-here`. School note links: `#people-helped`, `#becoming-capable`, `#the-person`. Both remain labeled “Concept preview” pending an actual opportunity message.

For an active profile, the final link-rewriting loop carries context as `?for=<id>` to same-origin links whose pathname is `/`, or starts with `/work/launch-console/`, `/thinking/`, `/field-notes/`, `/application/`. It replaces the destination’s entire existing query and preserves its hash. Fragment-only links are left alone. Other products, downloads, mailto, LinkedIn and different origins are not rewritten. Absolute `beetcher.com` links count as same-origin only when that is the current origin. Shared Masthead scripts on reader/application pages carry recognized context on eligible onward/return links; they do not supply a missing homepage dialog.

## First-visit letter lifecycle and reset

**Verified in code:** Dialog initialization requires `#welcome-dialog`, `#open-welcome` and native `dialog.showModal`. Both general floaters use independent tab-session keys: `masthead-floater-serviced:meet-v1` and `masthead-floater-serviced:tour-v1`. A fresh session shows both. Clicking an invitation’s X services only that invitation. Opening a letter from its floater and dismissing it through Close, Explore, Escape, backdrop, a dialog link or native close services only that floater. It stays absent across reloads until reset or a fresh tab session. Closing a letter never revives its floater.

Permanent Meet Todd and Take a quick tour navigation always opens the associated general letter, including on personalized routes. Opening from navigation or the route-welcome strip never services or revives either floater. The script explicitly tracks floater, navigation and personalized opening sources. When an invoking floater disappears, focus returns to its corresponding permanent nav button; ordinary nav closing restores its invoking control. Explore still focuses the hero.

Existing route-welcome storage remains separate: `masthead-welcome-dismissed:general-letter-v1` for general/school and `masthead-welcome-dismissed:nvidia` for NVIDIA. Closing the original route-default letter records its route dismissal; closing Meet Todd never does so, and closing the general tour on NVIDIA never dismisses its employer letter. NVIDIA’s original employer welcome auto-opens unless dismissed. School retains its existing personalized note and general letter with no automatic letter opening. Invalid/unrecognized URLs remain generic. No specialized content or query-selection rules were replaced.

The shared dialog selects existing meet/tour/employer markup, updates its accessible label/description, starts at the top and focuses Close. Its letter body scrolls independently of fixed header/actions; background scroll is locked while open. Meet/tour retain direct Let’s talk access, and employer retains document actions. Tab/Shift+Tab wrap among visible controls and the scroll region. Closing restores the saved page position except Explore, which scrolls to the hero. The route strip says Take a quick tour for general/school and Welcome & documents for NVIDIA, and opens the original route letter. `pagehide` retains the existing dialog-close handling.

Triple-clicking only `.site-header .brand .monogram` (upper-left `tb.`), using primary clicks without modifiers and `event.detail === 3`, clears **both floater service keys**, reveals both immediately and scrolls them into view. It opens no letter. It leaves all route-welcome and opportunity-note dismissal keys intact. First/second clicks retain brand navigation; footer/name/keyboard/modified clicks are not reset triggers. This supersedes the previous reset that opened the route welcome.

Storage is session-scoped, with no authored expiry, localStorage or cookie identity. All storage operations catch errors; in-memory visibility and manual controls still work when storage is unavailable, but persistence cannot be guaranteed. Browser restored/cloned-tab behavior follows the browser’s sessionStorage semantics.

**Verification:** See `docs/reports/masthead-floater-correction-build-report.md` for this correction’s exact checks and limits; the earlier two-letter report documents its prior behavior and provenance.

## Architecture, dependencies and serving

**Verified in local files:** Static HTML/CSS/JS, no homepage framework, package dependency, build step or inline script/style. `index.html` loads one stylesheet and one deferred script: `/assets/masthead/masthead.css?v=intro-letter-20261027` and `/assets/masthead/masthead.js?v=intro-letter-20261027`. The existing asset names differ from the generic `style.css`/`main.js` instruction; preserve the implemented structure unless a scoped plan changes it.

- `assets/masthead/`: shared styling/behavior, optimized WebP photography and schematic, favicon family and social-preview assets. Homepage responsive images use explicit dimensions; hero is prioritized and later images lazy-load.
- `work/launch-console/index.html`: deeper evidence reader, not the console application itself.
- `thinking/{ai-era-business-engineering,learning-to-navigate-the-unknown,systems-thinking,a-letter-to-parents,constellation-programming}/index.html`: static readers and PDF download links. `field-notes/{everyday-possibilities,recognizing-the-moment,what-we-pass-forward}/index.html`: narrative readers. These and application pages use the shared Masthead CSS/JS.
- `docs/masthead/`: raw-signal/application registers and creative/source archives. Source docs may lag implementation: the Mines-talk README says not yet integrated, while the homepage now includes the talk and PDF link. Creative-review notes also contain original workspace-location wording superseded by the archive README.
- Homepage outward paths include Enjoy/LAUNCH (`https://beetcher.com/enjoy/` in the letter), coaching (`/coach/` on beetcher.com), mentoring background, driver story, `https://cert.beetcher.com/` (NOCTI proposal presentation), LinkedIn and mailto. These are linked destinations, not proof of their current availability or operation. The Masthead script makes no AI/network API calls and implements no form submission or analytics.

Canonical/OG URLs use `https://beetcher.com/`; social cards use `/assets/masthead/social-preview-v2.jpg`. Homepage robots meta is `noindex, nofollow`. `_headers` includes `X-Robots-Tag` rules for `/docs/*` and several other areas, but no root-wide noindex rule. `robots.txt` disallows selected other paths, not `/`. Preserve these files; this baseline does not claim a root-wide robots/header policy exists. Actual hosting project, domain routing, deployed HEAD and response headers were not verified. Historical GitHub Pages statements and the separate-next-site AGENTS guidance are not evidence of current remote deployment state.

## Supported decisions, present state and limits

**Documented intent:** Application register: keep preparation destinations honest, preserve a base résumé fallback, and map each employer letter explicitly without cross-employer fallback. Raw-signal register: preserve source, distinguish observation/proposal/outcome, and avoid invented exchanges, metrics or claims of adoption. Parking lot: keep a short main story with optional deeper exploration and source-grounded personal discoveries.

**Verified in code:** Cream/green/terracotta palette, Georgia headings, system-sans body, portrait, personal photos, reduced-motion rules and modal presentation. **Rationale unknown** beyond the written direction above; do not invent a reason for every styling choice or treat the archived redesign as approved.

Implemented: scrolling introduction/evidence hub, two URL profiles, exact approved Meet Todd plus unchanged general/employer letters, independent session-serviced floating invitations, permanent letter navigation, route-specific welcome dismissal/reopening and floater-only reset, opportunity reveal, reader/document routes, contact and copy controls. Unfinished: résumé and NVIDIA letter content; opportunity-specific message; amber mentoring, teaching and continuation evidence. The learning sequence and first-week plan are proposals, not demonstrated durable learning or ROI. NOCTI is a proposed initiative, not a launched certification.

**Deferred creative work:** `docs/masthead/creative-review-2026-10-27/` is an archived review board with illustrations and an “Are You Ready?” prototype, not a root-page feature. Its README and parking-lot entry describe five questions/four authored paths, no production handoff, and future integration decisions. Optional video, proposed inserted panels and additional discoveries remain parked, not authorized by this baseline.

**Known limits:** The two-letter build adds focused local headless Chromium checks, not a full device/accessibility or live-link audit. Current review copy is not outreach-ready merely because it is implemented. Source inspection does not establish linked-product adoption, business outcomes or remote availability.

## Onboarding and maintenance

Read `AGENTS.md`, `CLAUDE.md`, the selected current plan and this file first. For current behavior read `index.html` and `assets/masthead/masthead.js`/`.css`; for claims and unfinished content read the application/raw-signal registers. Consult historical briefs/creative archives as labeled context, not current approval.

Verify checkout, common Git directory, branch and existing changes before work; inspect output symlinks. Preserve owner work, plain HTML/CSS/JS, noindex settings, Todd’s conversational voice and source-backed claims. Keep unrelated products, launcher/lock and deployment configuration outside a scoped Masthead change. Update this baseline when user-visible behavior changes, or explicitly report why no documentation update was needed.

The approved two-letter implementation is now present locally. Owner review of the complete rendered letter and later release actions remain separate; this build does not commit, push or deploy.

## Deferred build-system work — after the website is shareable

Package a reusable new-repository starter kit with standard `AGENTS.md`, `docs/PRODUCT.md`, Codex launcher and build workflow. Consider launcher-level enforcement of PRODUCT.md updates. This is recorded only: do not implement the kit or alter the launcher as part of this sweep.
