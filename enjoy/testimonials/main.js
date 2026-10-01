// enjoy/testimonials/main.js
// "Ask others": a Brady Bunch wall of faces. Hover or focus a tile and it comes forward; click or tap opens the voice.
// VOICES is the only thing to edit when real people say yes: set sample:false, add a real name, line/quote and a video path.
//   { id, animal, name, color, line, quote, video: 'assets/voices/name.mp4' (optional), sample: true|false }
// Animal faces are drawn in code (no images) and are stand-ins only.

const VOICES = [
  { id: 'owl',      animal: 'owl',      name: 'Olive the Owl',      color: '#e8a317', quote: 'I wasn’t sure it was for me. Then I planned our whole anniversary dinner.', video: '', sample: true },
  { id: 'bear',     animal: 'bear',     name: 'Bruno the Bear',     color: '#d2601a', quote: 'My granddaughter asked how I did it. I said, I can do that.', video: '', sample: true },
  { id: 'fox',      animal: 'fox',      name: 'Fern the Fox',       color: '#7a8b2b', quote: 'I wrote my sister a birthday poem in four minutes. She cried.', video: '', sample: true },
  { id: 'cat',      animal: 'cat',      name: 'Clementine the Cat', color: '#2e8b8b', quote: 'I didn’t need to be technical. I just needed to be curious.', video: '', sample: true },
  { id: 'you',      animal: null,       name: 'Your turn',          color: '#1b1340', quote: '', video: '', sample: false },
  { id: 'rabbit',   animal: 'rabbit',   name: 'Hazel the Hare',     color: '#a63d2f', quote: 'I finally fixed the thing I had been putting off for a year.', video: '', sample: true },
  { id: 'panda',    animal: 'panda',    name: 'Penny the Panda',    color: '#c98a1b', quote: 'We planned the whole family reunion in one evening.', video: '', sample: true },
  { id: 'frog',     animal: 'frog',     name: 'Fritz the Frog',     color: '#3f7f5f', quote: 'I laughed the whole time. It was actually fun.', video: '', sample: true },
  { id: 'penguin',  animal: 'penguin',  name: 'Percy the Penguin',  color: '#7b4a8a', quote: 'I came in nervous. I left showing everybody my phone.', video: '', sample: true },
];
// Order note: the centre tile is the invitation, like the middle square of the Brady Bunch grid.

const NS = 'http://www.w3.org/2000/svg';
function svgEl(tag, attrs) {
  const n = document.createElementNS(NS, tag);
  Object.keys(attrs || {}).forEach((k) => n.setAttribute(k, attrs[k]));
  return n;
}
const INK = '#2b1b12';
// Each animal: list of [tag, attributes], drawn back to front on a 100x100 board.
const ANIMALS = {
  owl: [
    ['polygon', { points: '22,34 26,8 44,24', fill: '#8a5a33' }],
    ['polygon', { points: '78,34 74,8 56,24', fill: '#8a5a33' }],
    ['ellipse', { cx: 50, cy: 58, rx: 34, ry: 36, fill: '#8a5a33' }],
    ['ellipse', { cx: 50, cy: 76, rx: 18, ry: 14, fill: '#e3c59b' }],
    ['circle', { cx: 35, cy: 46, r: 14, fill: '#fff6e2' }],
    ['circle', { cx: 65, cy: 46, r: 14, fill: '#fff6e2' }],
    ['circle', { cx: 36, cy: 47, r: 7, fill: INK }],
    ['circle', { cx: 64, cy: 47, r: 7, fill: INK }],
    ['circle', { cx: 38, cy: 44, r: 2.2, fill: '#fff' }],
    ['circle', { cx: 66, cy: 44, r: 2.2, fill: '#fff' }],
    ['polygon', { points: '44,56 56,56 50,68', fill: '#f0a81c' }],
  ],
  bear: [
    ['circle', { cx: 24, cy: 26, r: 13, fill: '#6b4426' }],
    ['circle', { cx: 76, cy: 26, r: 13, fill: '#6b4426' }],
    ['circle', { cx: 24, cy: 26, r: 6.5, fill: '#c9936a' }],
    ['circle', { cx: 76, cy: 26, r: 6.5, fill: '#c9936a' }],
    ['circle', { cx: 50, cy: 55, r: 35, fill: '#6b4426' }],
    ['ellipse', { cx: 50, cy: 68, rx: 17, ry: 13, fill: '#e3c59b' }],
    ['ellipse', { cx: 50, cy: 61, rx: 7, ry: 4.6, fill: INK }],
    ['circle', { cx: 37, cy: 46, r: 3.6, fill: INK }],
    ['circle', { cx: 63, cy: 46, r: 3.6, fill: INK }],
    ['path', { d: 'M50 66 L50 71 M43 74 Q50 79 57 74', stroke: INK, 'stroke-width': 2.4, fill: 'none', 'stroke-linecap': 'round' }],
  ],
  fox: [
    ['polygon', { points: '18,42 24,8 46,30', fill: '#e2761b' }],
    ['polygon', { points: '82,42 76,8 54,30', fill: '#e2761b' }],
    ['polygon', { points: '25,34 27,17 38,28', fill: INK }],
    ['polygon', { points: '75,34 73,17 62,28', fill: INK }],
    ['path', { d: 'M50 90 C22 84 12 56 16 40 C30 30 70 30 84 40 C88 56 78 84 50 90 Z', fill: '#e2761b' }],
    ['path', { d: 'M50 90 C34 86 24 70 26 56 C38 68 62 68 74 56 C76 70 66 86 50 90 Z', fill: '#fff' }],
    ['circle', { cx: 37, cy: 52, r: 3.6, fill: INK }],
    ['circle', { cx: 63, cy: 52, r: 3.6, fill: INK }],
    ['ellipse', { cx: 50, cy: 76, rx: 5, ry: 3.6, fill: INK }],
  ],
  cat: [
    ['polygon', { points: '16,46 20,10 46,30', fill: '#98a2ad' }],
    ['polygon', { points: '84,46 80,10 54,30', fill: '#98a2ad' }],
    ['polygon', { points: '24,38 25,21 37,30', fill: '#f2a7b5' }],
    ['polygon', { points: '76,38 75,21 63,30', fill: '#f2a7b5' }],
    ['ellipse', { cx: 50, cy: 58, rx: 37, ry: 31, fill: '#98a2ad' }],
    ['ellipse', { cx: 36, cy: 54, rx: 6, ry: 7.5, fill: '#b7e07a' }],
    ['ellipse', { cx: 64, cy: 54, rx: 6, ry: 7.5, fill: '#b7e07a' }],
    ['ellipse', { cx: 36, cy: 54, rx: 2.4, ry: 6, fill: INK }],
    ['ellipse', { cx: 64, cy: 54, rx: 2.4, ry: 6, fill: INK }],
    ['polygon', { points: '46,66 54,66 50,71', fill: '#f2a7b5' }],
    ['path', { d: 'M50 71 Q44 78 38 74 M50 71 Q56 78 62 74 M14 62 L32 66 M14 72 L32 70 M86 62 L68 66 M86 72 L68 70', stroke: INK, 'stroke-width': 1.8, fill: 'none', 'stroke-linecap': 'round' }],
  ],
  rabbit: [
    ['ellipse', { cx: 36, cy: 24, rx: 9, ry: 23, fill: '#f2efe9' }],
    ['ellipse', { cx: 64, cy: 24, rx: 9, ry: 23, fill: '#f2efe9' }],
    ['ellipse', { cx: 36, cy: 26, rx: 4.5, ry: 16, fill: '#f2a7b5' }],
    ['ellipse', { cx: 64, cy: 26, rx: 4.5, ry: 16, fill: '#f2a7b5' }],
    ['circle', { cx: 50, cy: 62, r: 30, fill: '#f2efe9' }],
    ['circle', { cx: 38, cy: 58, r: 3.6, fill: INK }],
    ['circle', { cx: 62, cy: 58, r: 3.6, fill: INK }],
    ['circle', { cx: 30, cy: 68, r: 5, fill: '#f7c6cf' }],
    ['circle', { cx: 70, cy: 68, r: 5, fill: '#f7c6cf' }],
    ['ellipse', { cx: 50, cy: 67, rx: 4.6, ry: 3.4, fill: '#e07a90' }],
    ['rect', { x: 46.5, y: 73, width: 7, height: 8, rx: 1.5, fill: '#fff', stroke: '#d9d2c7', 'stroke-width': 1 }],
  ],
  panda: [
    ['circle', { cx: 23, cy: 27, r: 13, fill: INK }],
    ['circle', { cx: 77, cy: 27, r: 13, fill: INK }],
    ['circle', { cx: 50, cy: 56, r: 34, fill: '#fbf7f0' }],
    ['ellipse', { cx: 36, cy: 52, rx: 9, ry: 12, fill: INK, transform: 'rotate(22 36 52)' }],
    ['ellipse', { cx: 64, cy: 52, rx: 9, ry: 12, fill: INK, transform: 'rotate(-22 64 52)' }],
    ['circle', { cx: 37, cy: 51, r: 3.4, fill: '#fff' }],
    ['circle', { cx: 63, cy: 51, r: 3.4, fill: '#fff' }],
    ['ellipse', { cx: 50, cy: 66, rx: 6.5, ry: 4.6, fill: INK }],
    ['path', { d: 'M50 70 L50 74 M43 77 Q50 82 57 77', stroke: INK, 'stroke-width': 2.4, fill: 'none', 'stroke-linecap': 'round' }],
  ],
  frog: [
    ['ellipse', { cx: 50, cy: 62, rx: 38, ry: 28, fill: '#5da13a' }],
    ['circle', { cx: 30, cy: 38, r: 14, fill: '#5da13a' }],
    ['circle', { cx: 70, cy: 38, r: 14, fill: '#5da13a' }],
    ['circle', { cx: 30, cy: 38, r: 9.5, fill: '#fff' }],
    ['circle', { cx: 70, cy: 38, r: 9.5, fill: '#fff' }],
    ['circle', { cx: 31, cy: 39, r: 4.6, fill: INK }],
    ['circle', { cx: 69, cy: 39, r: 4.6, fill: INK }],
    ['path', { d: 'M24 68 Q50 88 76 68', stroke: INK, 'stroke-width': 3, fill: 'none', 'stroke-linecap': 'round' }],
    ['circle', { cx: 45, cy: 56, r: 1.6, fill: INK }],
    ['circle', { cx: 55, cy: 56, r: 1.6, fill: INK }],
    ['circle', { cx: 19, cy: 66, r: 5, fill: '#f29a9a' }],
    ['circle', { cx: 81, cy: 66, r: 5, fill: '#f29a9a' }],
  ],
  penguin: [
    ['ellipse', { cx: 50, cy: 56, rx: 32, ry: 38, fill: '#263240' }],
    ['ellipse', { cx: 50, cy: 66, rx: 21, ry: 28, fill: '#fff' }],
    ['circle', { cx: 40, cy: 40, r: 7.5, fill: '#fff' }],
    ['circle', { cx: 60, cy: 40, r: 7.5, fill: '#fff' }],
    ['circle', { cx: 41, cy: 41, r: 3.4, fill: INK }],
    ['circle', { cx: 59, cy: 41, r: 3.4, fill: INK }],
    ['polygon', { points: '43,49 57,49 50,59', fill: '#f0a81c' }],
    ['ellipse', { cx: 38, cy: 94, rx: 11, ry: 4, fill: '#f0a81c' }],
    ['ellipse', { cx: 62, cy: 94, rx: 11, ry: 4, fill: '#f0a81c' }],
  ],
};

function avatar(animal, color) {
  const svg = svgEl('svg', { viewBox: '0 0 100 100', role: 'img', 'aria-hidden': 'true', focusable: 'false' });
  svg.appendChild(svgEl('rect', { width: 100, height: 100, fill: color }));
  svg.appendChild(svgEl('circle', { cx: 50, cy: 50, r: 46, fill: 'rgba(255,255,255,.16)' }));
  (ANIMALS[animal] || []).forEach((spec) => svg.appendChild(svgEl(spec[0], spec[1])));
  return svg;
}

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text) n.textContent = text;
  return n;
}

function initWall() {
  const grid = document.getElementById('wall');
  const dlg = document.getElementById('voice');
  if (!grid || !dlg) return;
  const stage = document.getElementById('voice-stage');
  const nameEl = document.getElementById('voice-name');
  const quoteEl = document.getElementById('voice-quote');
  const sampleEl = document.getElementById('voice-sample');
  const real = VOICES.filter((v) => v.animal);
  let current = 0;

  VOICES.forEach((v) => {
    if (!v.animal) {
      const a = el('a', 'wall__tile wall__tile--you');
      a.href = '../#register';
      a.style.setProperty('--tile', v.color);
      a.appendChild(el('span', 'wall__you', 'You?'));
      a.appendChild(el('span', 'wall__name', v.name));
      grid.appendChild(a);
      return;
    }
    const b = el('button', 'wall__tile');
    b.type = 'button';
    b.style.setProperty('--tile', v.color);
    b.setAttribute('aria-label', 'Hear from ' + v.name);
    b.appendChild(avatar(v.animal, v.color));
    b.appendChild(el('span', 'wall__name', v.name));
    b.addEventListener('click', () => { show(real.indexOf(v)); if (!dlg.open) { if (dlg.showModal) dlg.showModal(); else dlg.setAttribute('open', ''); } });
    grid.appendChild(b);
  });

  function show(i) {
    current = (i + real.length) % real.length;
    const v = real[current];
    stage.textContent = '';
    if (v.video) {
      const vid = el('video', 'voice__video');
      vid.src = v.video; vid.controls = true; vid.playsInline = true; vid.preload = 'metadata';
      stage.appendChild(vid);
    } else {
      const wrap = el('div', 'voice__portrait');
      wrap.style.setProperty('--tile', v.color);
      wrap.appendChild(avatar(v.animal, v.color));
      stage.appendChild(wrap);
    }
    nameEl.textContent = v.name;
    quoteEl.textContent = '“' + v.quote + '”';
    sampleEl.hidden = !v.sample;
  }

  document.getElementById('voice-prev').addEventListener('click', () => show(current - 1));
  document.getElementById('voice-next').addEventListener('click', () => show(current + 1));
  dlg.addEventListener('click', (e) => { if (e.target === dlg) dlg.close(); });
  dlg.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowLeft') show(current - 1);
    if (e.key === 'ArrowRight') show(current + 1);
  });
  dlg.addEventListener('close', () => { const vid = dlg.querySelector('video'); if (vid) vid.pause(); });
}

document.addEventListener('DOMContentLoaded', () => {
  document.documentElement.classList.add('js');
  initWall();
});

// ==== PEEKER BEGIN (identical in every enjoy main.js; edit enjoy/main.js first, then copy the block) ====
// Doc peeks in from a screen edge, waves, leaves, and comes back. It is the ONLY way to Meet Doc.
// Skipped on the hero, and on any device that has already met Doc (localStorage, no cookie).
// Preview any time: add ?peek to the URL (or ?peek=left|right|top|bottom to force an edge).
// To add a behavior (drift-by, banner plane...): add a function to DOC_BEHAVIORS and its name to DOC_ACTIVE.
(() => {
  const MET_KEY = 'icdt-met-doc', HIDE_KEY = 'icdt-doc-hidden', RESET_KEY = 'icdt-doc-reset';
  const read = (kind, k) => { try { return window[kind].getItem(k); } catch (e) { return null; } };
  const write = (kind, k) => { try { window[kind].setItem(k, '1'); } catch (e) { /* storage blocked: fine */ } };
  const m = location.pathname.match(/\/enjoy\/(.*)$/);
  const parts = m ? m[1].split('/').filter((p) => p && !/\.html?$/i.test(p)) : [];
  const base = '../'.repeat(parts.length);
  if (parts[0] === 'doc') { if (!read('sessionStorage', RESET_KEY)) write('localStorage', MET_KEY); return; }  // easter egg on that page (3 clicks on Doc) clears the memory
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
