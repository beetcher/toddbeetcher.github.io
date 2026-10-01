// enjoy/done/main.js: intentionally minimal.
// Static page. Register buttons use data-open-register, which opens the sign-up dialog on the main page via ../#register.
document.addEventListener('DOMContentLoaded', () => {
  document.documentElement.classList.add('js');
  document.querySelectorAll('[data-open-register]').forEach((b) => b.addEventListener('click', () => { location.href = '../#register'; }));
});

// ==== PEEKER BEGIN (identical in every enjoy main.js; edit enjoy/main.js first, then copy the block) ====
// Doc peeks in from a screen edge, waves, leaves, and comes back. It is the ONLY way to Meet Doc.
// Skipped on the hero, and on any device that has already met Doc (localStorage, no cookie).
// Preview any time: add ?peek to the URL (or ?peek=left|right|top|bottom to force an edge).
// To add a behavior (drift-by, banner plane...): add a function to DOC_BEHAVIORS and its name to DOC_ACTIVE.
(() => {
  const MET_KEY = 'icdt-met-doc', HIDE_KEY = 'icdt-doc-hidden';
  const read = (kind, k) => { try { return window[kind].getItem(k); } catch (e) { return null; } };
  const write = (kind, k) => { try { window[kind].setItem(k, '1'); } catch (e) { /* storage blocked: fine */ } };
  const m = location.pathname.match(/\/enjoy\/(.*)$/);
  const parts = m ? m[1].split('/').filter((p) => p && !/\.html?$/i.test(p)) : [];
  const base = '../'.repeat(parts.length);
  if (parts[0] === 'doc') { write('localStorage', MET_KEY); return; }
  const preview = /[?&]peek(=|&|$)/.test(location.search);
  const forced = (location.search.match(/[?&]peek=(top|bottom|left|right)/) || [])[1];
  if (!preview && (read('localStorage', MET_KEY) || read('sessionStorage', HIDE_KEY))) return;

  const rand = (a, b) => a + Math.random() * (b - a);
  const pick = (list) => list[Math.floor(Math.random() * list.length)];
  const FIRST_DELAY = preview ? 1000 : 8000;      // after leaving the hero
  const GAP = preview ? [4, 6] : [20, 60];        // seconds between peeks
  const STAY = preview ? [4, 5] : [3, 12];        // seconds on screen
  const hero = document.querySelector('header.hero');
  let heroVisible = !!hero && !preview, timer = null, current = null, hidden = false;

  // ---- behavior: Peeker (slides in from an edge, waves, slides back out) ----
  const peeker = (done) => {
    const phone = window.matchMedia('(max-width: 700px), (pointer: coarse)').matches;
    const edge = forced || (phone ? 'bottom' : pick(['bottom', 'left', 'right', 'top']));
    const box = document.createElement('div');
    box.className = 'doc-peek doc-peek--' + edge;
    box.style.setProperty('--pos', Math.round(edge === 'left' || edge === 'right' ? rand(18, 62) : rand(8, 62)) + '%');
    const link = document.createElement('a');
    link.className = 'doc-peek__link';
    link.href = base + 'doc/';
    link.setAttribute('aria-label', 'Meet Doc');
    const tilt = document.createElement('span');
    tilt.className = 'doc-peek__tilt';
    const img = document.createElement('img');
    img.className = 'doc-peek__img';
    img.src = base + 'assets/doc-peek.webp';
    img.alt = '';
    img.width = 480; img.height = 476;
    tilt.appendChild(img);
    const label = document.createElement('span');
    label.className = 'doc-peek__label';
    label.textContent = 'Meet Doc';
    link.append(tilt, label);
    link.addEventListener('click', () => write('localStorage', MET_KEY));
    const x = document.createElement('button');
    x.type = 'button';
    x.className = 'doc-peek__x';
    x.setAttribute('aria-label', 'Hide Doc for this visit');
    x.textContent = '×';
    box.append(link, x);

    let stayTimer = null, outTimer = null, over = false;
    const leave = (again) => {
      if (over) return;
      over = true;
      clearTimeout(stayTimer);
      box.classList.remove('is-in');
      outTimer = setTimeout(() => { box.remove(); done(again); }, 800);
    };
    x.addEventListener('click', () => { write('sessionStorage', HIDE_KEY); hidden = true; leave(false); });
    const start = () => {
      document.body.appendChild(box);
      void box.offsetWidth;
      box.classList.add('is-in');
      stayTimer = setTimeout(() => leave(true), rand(STAY[0], STAY[1]) * 1000);
    };
    if (img.complete) start(); else { img.addEventListener('load', start, { once: true }); img.addEventListener('error', () => done(true), { once: true }); }
    return { stop: () => leave(true) };
  };

  const DOC_BEHAVIORS = { peeker };
  const DOC_ACTIVE = ['peeker'];

  const schedule = (ms) => { clearTimeout(timer); timer = setTimeout(tick, ms); };
  const tick = () => {
    if (hidden || current) return;
    if (heroVisible || document.hidden || document.querySelector('dialog[open]')) { schedule(3000); return; }
    current = DOC_BEHAVIORS[pick(DOC_ACTIVE)]((again) => {
      current = null;
      if (again && !hidden && !heroVisible) schedule(rand(GAP[0], GAP[1]) * 1000);
    });
  };

  if (hero && 'IntersectionObserver' in window && !preview) {
    new IntersectionObserver((entries) => {
      heroVisible = entries[entries.length - 1].isIntersecting;
      if (heroVisible) { clearTimeout(timer); if (current) current.stop(); }
      else if (!current) schedule(FIRST_DELAY);
    }).observe(hero);
  } else {
    heroVisible = false;
    schedule(FIRST_DELAY);
  }
})();
// ==== PEEKER END ====
