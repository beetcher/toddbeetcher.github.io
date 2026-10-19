// ============================================================
// SHARED CONFIGURATION — cert (NOCTI AI-readiness certification)
// If you change anything above the PAGE-SPECIFIC line, update all 3 main.js files:
// cert/main.js
// cert/ai-ready-workforce/main.js
// cert/impact/main.js
// ============================================================
const CERT_DOCS = [
  { slug: 'invitation',          title: 'The Invitation',                        shortTitle: 'Invitation' },
  { slug: 'ai-ready-workforce',  title: 'Accelerating the AI-Ready Workforce',   shortTitle: 'Opportunity' },
  { slug: 'impact',              title: 'The Impact',                            shortTitle: 'Impact' },
];
const STORAGE_KEY = 'cert';

// Set per page (bare assignment in the PAGE-SPECIFIC block at the bottom).
let CURRENT_DOC = null;

// ============================================================
// STORAGE UTILITIES — progress is a per-browser convenience only
// ============================================================
function getProgress() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

function setProgress(data) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch (e) { /* storage unavailable — pages still work */ }
}

function getOrInitProgress() {
  const progress = getProgress() || { schema_version: 1, docs: {} };
  CERT_DOCS.forEach(doc => {
    if (!progress.docs[doc.slug]) {
      progress.docs[doc.slug] = { visited: false, completed: false, last_visit: null };
    }
  });
  return progress;
}

// ============================================================
// NAV DOTS + PAPER HUB STATE
// ============================================================
function applyState(selector) {
  const progress = getProgress();
  document.querySelectorAll(selector).forEach(el => {
    const slug = el.dataset.slug;
    el.classList.remove('--completed', '--current', '--visited');
    if (slug === CURRENT_DOC && el.classList.contains('cert-nav__doc')) el.classList.add('--current');
    const doc = progress && progress.docs[slug];
    if (doc && doc.completed) el.classList.add('--completed');
    else if (doc && doc.visited) el.classList.add('--visited');
  });
}

function updateState() {
  applyState('.cert-nav__doc');
  applyState('.cert-hub__item');
}

// ============================================================
// READ PROGRESS BAR
// ============================================================
function initReadProgress() {
  const fill = document.querySelector('.read-progress__fill');
  if (!fill) return;
  let ticking = false;
  const update = () => {
    const docHeight = document.body.scrollHeight - window.innerHeight;
    const pct = docHeight > 0 ? Math.min(100, (window.scrollY / docHeight) * 100) : 0;
    fill.style.width = pct + '%';
    ticking = false;
  };
  window.addEventListener('scroll', () => {
    if (!ticking) {
      requestAnimationFrame(update);
      ticking = true;
    }
  }, { passive: true });
  update();
}

// ============================================================
// VISIT + COMPLETION
// ============================================================
function recordVisit() {
  if (!CURRENT_DOC) return;
  const progress = getOrInitProgress();
  progress.docs[CURRENT_DOC].visited = true;
  progress.docs[CURRENT_DOC].last_visit = new Date().toISOString();
  setProgress(progress);
}

function markCompleted() {
  const progress = getOrInitProgress();
  if (!progress.docs[CURRENT_DOC].completed) {
    progress.docs[CURRENT_DOC].completed = true;
    setProgress(progress);
  }
  updateState();
}

// A page counts as read once its end section has been on screen for 5 seconds.
function initCompletionDetection() {
  if (!CURRENT_DOC || !('IntersectionObserver' in window)) return;
  const end = document.querySelector('[data-completion-target]');
  if (!end) return;
  let dwellTimer = null;
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        dwellTimer = setTimeout(markCompleted, 5000);
      } else if (dwellTimer) {
        clearTimeout(dwellTimer);
      }
    });
  }, { threshold: 0.5 });
  observer.observe(end);
}

// ============================================================
// CONTACT PANEL — same pattern as /coach: shows the address, a copy button,
// a Gmail link and a plain email-app link. Never opens an email app by itself.
// ============================================================
function initContact() {
  const dlg = document.getElementById('contact');
  if (!dlg) return;
  const status = document.getElementById('copy-status');
  const addr = document.getElementById('contact-addr');
  const ADDRESS = 'toddbeetcher17@gmail.com';
  const NOTE = "Hi Todd,\n\nI'd like to learn more about NOCTI's AI-readiness certification and the founding sponsorship. (Or: I'd like to introduce someone.)\n\nA little about me (or them):\n\nA good time to talk:\n";
  const say = m => { if (status) status.textContent = m; };

  function openContact() {
    say('');
    if (typeof dlg.showModal === 'function') { if (!dlg.open) dlg.showModal(); }
    else { dlg.setAttribute('open', ''); }
  }
  function closeContact() { if (dlg.open) { if (dlg.close) dlg.close(); else dlg.removeAttribute('open'); } }
  document.querySelectorAll('[data-open-contact]').forEach(b => b.addEventListener('click', openContact));
  document.querySelectorAll('[data-close-contact]').forEach(b => b.addEventListener('click', closeContact));
  dlg.addEventListener('click', e => { if (e.target === dlg) closeContact(); });
  dlg.querySelectorAll('a[href*="#meet-"]').forEach(a => a.addEventListener('click', closeContact));

  function selectAddress() {
    if (!addr || !window.getSelection) return;
    const r = document.createRange(); r.selectNodeContents(addr);
    const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
  }
  function copyText(text, onDone) {
    function fallback() {
      let ok = false;
      try {
        const ta = document.createElement('textarea'); ta.value = text; ta.setAttribute('readonly', '');
        ta.style.position = 'fixed'; ta.style.opacity = '0'; document.body.appendChild(ta); ta.select();
        ok = document.execCommand('copy'); document.body.removeChild(ta);
      } catch (e) {}
      onDone(ok);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => onDone(true), fallback);
    } else { fallback(); }
  }

  const copyBtn = document.getElementById('copy-addr');
  if (copyBtn) copyBtn.addEventListener('click', () => copyText(ADDRESS, ok => {
    if (ok) say('Copied. Paste it into any email.');
    else { selectAddress(); say('Address selected. Press copy on your device.'); }
  }));
  const noteBtn = document.getElementById('copy-note');
  if (noteBtn) noteBtn.addEventListener('click', () => copyText(NOTE, ok => {
    say(ok ? 'Copied. Paste it into an email to ' + ADDRESS + '.' : 'Could not copy here. Just write a few lines about you.');
  }));

  document.querySelectorAll('[data-share]').forEach(b => b.addEventListener('click', () => {
    const url = location.href.split('#')[0];
    const data = { title: 'NOCTI AI-Readiness Certification', text: 'NOCTI, a nonprofit, is building an AI-readiness certification and inviting a few founding sponsors.', url };
    if (navigator.share) { navigator.share(data).catch(() => {}); }
    else { copyText(url, ok => say(ok ? 'Link copied. Paste it into a text or email.' : 'Copy this link: ' + url)); }
  }));
}

// ============================================================
// OPENING SCENE — TIMINGS (Invitation hero; runs only on a page with [data-intro])
// EASY CHANGES: every number below is in milliseconds (1000 = 1 second).
// Colors and sizes are the --intro-* settings in style.css under "OPENING SCENE".
// ============================================================
const INTRO_TIMINGS = {
  startDelay:   500,   // the bare picture, before anything appears
  titleFadeIn:  900,   // red title fades in, centered over the canyon
  titleHold:   2200,   // red title holds in the center
  titleMove:   1200,   // red title rises to the top of the window
  paraDelay:    300,   // pause after the title docks, before the paragraph appears
  paraFadeIn:  1000,   // paragraph fades in, in its final place under the title, glowing
  paraGlow:    4000,   // paragraph keeps its glow (reading time)
  glowFade:     600,   // glow fades down to a faint halo
  arcDelay:     125,   // pause before the orange arch
  arcAppear:    600,   // orange arch fades in up in the sky
  arcHold:      700,   // arch holds in the sky before it drops
  arcFloat:    2500,   // arch floats down into place
  arcDrop:      150,   // how far above its place the arch starts (pixels, not milliseconds)
};
const PILL_DELAY = 800; // pages without the opening: when the "I'm interested" pill appears

// ============================================================
// FLOATING "I'M INTERESTED" PILL — opens the same contact panel
// ============================================================
function initPill() {
  if (!document.getElementById('contact')) return;
  const pill = document.createElement('button');
  pill.type = 'button';
  pill.className = 'pill-interested is-hidden';
  pill.setAttribute('data-open-contact', '');
  pill.textContent = 'I’m interested';
  document.body.appendChild(pill);

  // "Meet Erin of NOCTI" pill, above it: goes to the Meet Erin card on the Invitation
  const meetLink = document.querySelector('.contact__meet a[href*="#meet-erin"]');
  if (!meetLink) return;
  const base = meetLink.getAttribute('href').replace('#meet-erin', '');
  const erin = document.createElement('a');
  erin.className = 'pill-erin is-hidden';
  erin.href = base + '#meet-erin';
  erin.innerHTML = '<img src="' + base + 'assets/erin-maruzzella.webp" alt="" width="30" height="30"><span>Meet Erin of <span class="nocti">NOCTI</span></span>';
  document.body.appendChild(erin);

  // On the Invitation, step aside while the card itself is on screen
  const card = document.getElementById('meet-erin');
  if (card && 'IntersectionObserver' in window) {
    new IntersectionObserver(es => es.forEach(e => erin.classList.toggle('is-aside', e.isIntersecting)), { threshold: 0.3 }).observe(card);
  }
}

function showPill() {
  document.querySelectorAll('.pill-interested, .pill-erin').forEach(p => p.classList.remove('is-hidden'));
}

// ============================================================
// OPENING SCENE
// Final arrangement is the plain CSS; the opening animates into it.
// Click, tap, key or scroll skips to the end. Leaving the picture and
// coming back to the top of the page plays it again.
// Reduced-motion and no-JavaScript visitors see the final arrangement.
// ============================================================
function initIntro() {
  const hero = document.querySelector('[data-intro]');
  if (!hero) return false;
  const stage = hero.querySelector('.intro-stage');
  const title = hero.querySelector('.intro-title');
  const para = hero.querySelector('.intro-para');
  const arc = hero.querySelector('.intro-arc');
  const T = INTRO_TIMINGS;
  const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const canAnimate = !reduce && typeof Element.prototype.animate === 'function';
  let running = false, runId = 0, anims = [], timers = [], leftHero = false, replayTimer = null;

  const placePara = () => stage.style.setProperty('--intro-para-top', (title.offsetHeight + 2) + 'px');
  const band = () => title.classList.toggle('is-banded', window.scrollY > 4);
  const wait = ms => new Promise(res => timers.push(setTimeout(res, ms)));
  const play = (el, frames, ms, easing) => {
    const a = el.animate(frames, { duration: ms, fill: 'both', easing: easing || 'ease-out' });
    anims.push(a);
    return a.finished.catch(() => {});
  };

  function finish() {
    runId++;
    running = false;
    timers.forEach(clearTimeout); timers = [];
    anims.forEach(a => { try { a.cancel(); } catch (e) {} }); anims = [];
    document.body.classList.remove('intro-on');
    document.documentElement.classList.remove('intro-wait');
    placePara(); band();
    showPill();
  }

  async function run() {
    if (!canAnimate) { finish(); return; }
    const id = ++runId;
    const alive = () => id === runId;
    timers.forEach(clearTimeout); timers = [];
    anims.forEach(a => { try { a.cancel(); } catch (e) {} }); anims = [];
    running = true;
    document.body.classList.add('intro-on');
    document.documentElement.classList.remove('intro-wait');
    placePara(); band();

    await wait(T.startDelay); if (!alive()) return;

    // Start positions, measured now (fonts and picture are in place)
    const s = stage.getBoundingClientRect();
    const t = title.getBoundingClientRect();
    const scale = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--intro-title-start-scale')) || 2;
    const raise = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--intro-title-start-raise')) || 0;
    const midY = s.top + s.height / 2;
    const titleStart = `translateY(${midY - raise - (t.top + t.height / 2)}px) scale(${scale})`;
    const glow = getComputedStyle(document.documentElement).getPropertyValue('--intro-para-glow').trim();
    const halo = getComputedStyle(document.documentElement).getPropertyValue('--intro-para-halo').trim();
    const glide = 'cubic-bezier(.45,0,.2,1)';

    // 1. Red title appears, centered over the canyon, and holds
    await play(title, [{ opacity: 0, transform: titleStart }, { opacity: 1, transform: titleStart }], T.titleFadeIn); if (!alive()) return;
    await wait(T.titleHold); if (!alive()) return;

    // 2. Title rises to the top of the window
    await play(title, [{ opacity: 1, transform: titleStart }, { opacity: 1, transform: 'none' }], T.titleMove, glide); if (!alive()) return;

    // 3. Paragraph fades in where it stays, glowing; then the glow fades to a faint halo
    await wait(T.paraDelay); if (!alive()) return;
    await play(para, [{ opacity: 0, textShadow: glow }, { opacity: 1, textShadow: glow }], T.paraFadeIn); if (!alive()) return;
    await wait(T.paraGlow); if (!alive()) return;
    await play(para, [{ opacity: 1, textShadow: glow }, { opacity: 1, textShadow: halo }], T.glowFade, 'ease-in-out'); if (!alive()) return;

    // 4. Orange arch floats down from the sky into place across the gorge
    await wait(T.arcDelay); if (!alive()) return;
    const sky = `translateY(${-T.arcDrop}px)`;
    await play(arc, [{ opacity: 0, transform: sky }, { opacity: 1, transform: sky }], T.arcAppear); if (!alive()) return;
    await wait(T.arcHold); if (!alive()) return;
    await play(arc, [{ opacity: 1, transform: sky }, { opacity: 1, transform: 'none' }], T.arcFloat, 'cubic-bezier(.3,0,.25,1)'); if (!alive()) return;
    finish();
  }

  // Skip to the final arrangement
  ['click', 'keydown', 'wheel', 'touchstart'].forEach(type =>
    window.addEventListener(type, () => { if (running) finish(); }, { passive: true, capture: true }));

  window.addEventListener('scroll', () => {
    band();
    if (running && window.scrollY > 4) finish();
    if (stage.getBoundingClientRect().bottom <= 48) leftHero = true;
    clearTimeout(replayTimer);
    if (leftHero && window.scrollY <= 2) {
      replayTimer = setTimeout(() => {
        if (window.scrollY <= 2) { leftHero = false; run(); }
      }, 350);
    }
  }, { passive: true });

  window.addEventListener('resize', () => { if (running) finish(); else placePara(); });
  window.addEventListener('pageshow', e => { if (e.persisted && window.scrollY <= 2) run(); });

  if (window.scrollY <= 2 && !location.hash) run(); else finish();
  return true;
}

// ============================================================
// MEET CARDS — a link to #meet-erin (from the contact panel or another page)
// scrolls to the card and opens it.
// ============================================================
function initMeet() {
  const openFromHash = () => {
    const id = decodeURIComponent(location.hash.slice(1));
    const el = id && document.getElementById(id);
    if (!el || el.tagName !== 'DETAILS') return;
    el.open = true;
    el.scrollIntoView({ block: 'start' });
    // Take #meet-erin back out of the address bar, so a reload plays the opening again
    if (history.replaceState) history.replaceState(null, '', location.pathname + location.search);
  };
  openFromHash();
  window.addEventListener('hashchange', openFromHash);
  document.querySelectorAll('a[href^="#"]').forEach(a => a.addEventListener('click', () => setTimeout(openFromHash, 0)));
}

// ============================================================
// PAGE-SPECIFIC — the only line that differs between the 3 files
// ============================================================
CURRENT_DOC = 'ai-ready-workforce';

document.addEventListener('DOMContentLoaded', () => {
  recordVisit();
  updateState();
  initReadProgress();
  initCompletionDetection();
  initPill();
  initContact();
  initMeet();
  if (!initIntro()) setTimeout(showPill, PILL_DELAY);
});

// Refresh dots when returning via the browser Back button (page restored from cache).
window.addEventListener('pageshow', e => { if (e.persisted) updateState(); });
