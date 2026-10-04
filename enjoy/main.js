// ============================================================
// enjoy/main.js — "I Can Do That"
// Panels are data-driven: add a story by appending an object to STORIES.
// Sign-ups go to Firestore (collection below). Fill in FIREBASE_CONFIG
// to go live; until then the form says plainly that it is not connected
// and never pretends a sign-up was saved.
// ============================================================

// ---- Firebase web config (Firebase console > Project settings > Your apps > Web) ----
const FIREBASE_CONFIG = {
  apiKey: 'AIzaSyDM6TE1NpirV-jwLy1wTAU7C-Id9-aXFxI',
  authDomain: 'test-phone-router.firebaseapp.com',
  projectId: 'test-phone-router',
  appId: '1:112367027974:web:e37d5a51a547ae443d4087',
};
const SIGNUPS_COLLECTION = 'enjoy_signups';
const FIREBASE_SDK = 'https://www.gstatic.com/firebasejs/10.14.1/';
const CONTACT_EMAIL = 'toddbeetcher17@gmail.com';
// "Ask Todd" chat companion. Leave empty until the endpoint exists; the widget then
// says it isn't switched on yet and offers an email instead. When set, the page POSTs
// JSON { question } and expects JSON { answer } back.
const ASK_ENDPOINT = '';

// ---- Stories ----
// image: optional path like 'assets/san-luis-valley.webp' (shown behind the gradient).
// colors: two-stop gradient used when there is no image, and as the tint over one.
// Each panel leads with the human result (what happened to someone Todd cares about), then the story, then how he asked.
// NOTE: prompts and payoffs below are PLACEHOLDER sample content until Todd supplies real ones.
// headline: the cheeky title across the top of the panel, always tied to Doc. Todd's words: valley, brisket. Claude's drafts (flagged, tune freely): light-bulb, margarita-pancakes. PLACEHOLDERS until Todd gives the real moment: birthday-card, cocktail, hassle, this-website.
// badge: optional sticker { label, nums, sub, shout } stuck on the lower-left of the first photo, with a marker arrow to the callout (three-print layout).
// bigLine: optional second payoff line shown large and pink after the payoff.
// callout: optional kraft-paper scrap (a second, different callout) beside the photos.
// note: optional sticky note stuck on the collage board (text that belongs with the photos).
// collage: 'three' lays out sticky note, three prints and a kraft callout. payoffBig: true makes the payoff line large and pink.
// collage: 'pair' gives two landscape photos equal weight (default layout favors one large print and one small sticker).
// photos: [{ src, alt, kind: 'print' | 'cutout', rot: degrees, hold: 'tape' | 'corners' | 'magnet' | 'pin' | 'clip' | 'none' }]
// Like photos on a fridge: each one can be held up its own way.
// Text of the hover callout on every "See how I asked Doc" button. Edit freely.
// ---- Free trial layer (the OFF SWITCH) ----
// true: the letter overlay (?trial) and, once built, the plane are active.
// false: neither shows. To retire the trial completely, also delete the enjoy/trial/ folder.
const TRIAL_ON = true;
const TRIAL_JOIN_URL = 'trial/join/';

const DOC_TIP = 'This is exactly what I typed to the AI to get the result you just read about.';

const STORIES = [
  {
    id: 'san-luis-valley',
    headline: 'Doc tells stories on road trips. Wife wants more stories.',
    category: 'Driving',
    title: 'Drive through the San Luis Valley',
    line: 'I asked Doc to tell us the valley\u2019s history like a storyteller. Suzanne was so absorbed in the story that when it ended she said, \u201cWow, that was really cool. Let\u2019s do that again.\u201d We did, valley after valley, the rest of the trip.',
    promptLabel: 'See how I asked Doc',
    prompt: 'Be a storyteller with a deep, gravelly voice in the style of a Star Wars narrator. Tell me a 10-minute history and origins story of the San Luis Valley, framed for right now as I drive through it.',
    payoff: 'My capability made her enjoy the trip more, and that was very empowering.',
    colors: ['#ff3d6e', '#ff9a3d'],
    collage: 'pair',
    photos: [
      { src: 'assets/san-luis-valley.webp', kind: 'print', rot: -2, hold: 'tape', alt: 'Sunrise through the windshield of a car driving south toward the snowy Sangre de Cristo mountains in the San Luis Valley, Colorado. Caption: Driving through the San Luis Valley, I asked Doc to tell us its history like a storyteller.' },
      { src: 'assets/mesa-verde-doc.webp', kind: 'print', rot: 3, hold: 'pin', alt: 'Todd and Suzanne smiling in front of the cliff dwellings at Mesa Verde, with a speech bubble from Suzanne: Hey, Doc, tell me a story about a 12-year-old girl who used to live in these ruins. What was her day like?' },
    ],
  },
  {
    id: 'brisket',
    headline: 'Doc told me the stall is where the magic happens. Everyone wants more meat candy.',
    category: 'Cooking',
    title: 'Cook a brisket without the panic',
    line: 'It was very gratifying to watch that happen, knowing I made it for people I care about. A tool of chaos had become a source of capability, and that was very empowering.',
    note: 'I asked Doc how to cook a brisket, and our friend Diana and her daughters, Kate and Melissa, came over to eat it.',
    callout: 'It never made it from the counter to the table: everyone stood around and carved it up. Meat candy. Friends have been talking about it for years.',
    promptLabel: 'See how I asked Doc',
    prompt: 'For thirty years I let my wife cook the burgers and the chicken and pretended I didn\u2019t know the grill. Then I asked AI. The trick wasn\u2019t \u201chow do I cook a brisket?\u201d It was learning to ask like this, step by step:',
    steps: [
      'Pretend you\u2019re a master chef who has been smoking meat for 30 years. Give me the tips and tricks you\u2019d tell a junior apprentice.',
      'What am I not asking that a professional would tell me?',
      'Is there anything I\u2019m at risk of getting wrong?',
      'Go look on the internet for more information, then give me a roadmap.',
    ],
    payoff: 'Now I smoke all kinds of meat, and I use AI to buy the supplies too.',
    colors: ['#c98536', '#6f3518'],
    photos: [
      { src: 'assets/brisket-sticker.webp', kind: 'cutout', rot: -5, alt: 'A brisket smoking on a pellet grill with temperature probes.' },
      { src: 'assets/todd-brisket.webp', kind: 'print', rot: 5, hold: 'magnet', alt: 'Todd smiling in a Beetcher\u2019s Brisket T-shirt.' },
    ],
  },
  {
    id: 'light-bulb',
    headline: 'Dome lights dead through law school. Doc fixed them for $5.',
    category: 'Fixing',
    title: 'The dome lights that were out for years',
    line: 'My kid went through high school, college, law school with one of those lights out. Then another one blanked a couple years ago. Then one day I was like, wait, WTF. What does Doc have to say about this?',
    note: 'Interior lights in front are both dead. 2005 Honda Pilot. I want to replace them myself. What do I buy, and how do I install them?',
    callout: '$5. 5 minute repair.',
    promptLabel: 'See how I asked Doc',
    prompt: '\u201cThe interior lights in front are both dead. I can take a picture of the assembly. This is the 2005 Honda Pilot. I want to see if there\u2019s a way that I can get those replaced, my do-it-myself thing. So I would need to know what I need to buy, and I would need to know what the installation instructions are.\u201d',
    payoff: 'I\u2019m empowered!',
    payoffBig: true,
    colors: ['#ffc83d', '#ff7a3d'],
    collage: 'three',
    photos: [
      { src: 'assets/honda-dome-light.webp', kind: 'print', rot: -2, hold: 'tape', alt: 'The overhead light assembly in the front of a 2005 Honda Pilot, with the dead dome and map lights and three buttons.' },
      { src: 'assets/honda-bulb.webp', kind: 'print', rot: 4, hold: 'pin', cls: 'sticker--oldbulb', alt: 'The old, burned-out glass festoon bulb with silver ends, the kind that goes in the dome light.' },
      { src: 'assets/honda-pilot.webp', kind: 'print', rot: -3, hold: 'magnet', alt: 'Todd\u2019s black 2005 Honda Pilot parked in the driveway under a tree.' },
      { src: 'assets/honda-bulb-pack.webp', kind: 'print', rot: 3, hold: 'tape', cls: 'sticker--newpack', label: 'Ordered on Amazon', alt: 'The new pack of two Hella DE3175 miniature bulbs, ordered from Amazon.' },
    ],
    swap: { note: 'Thx Doc! Correct bulbs ordered < 5 min! :)' },
  },
  {
    id: 'air-conditioner',
    headline: 'From freeze-up to refrigerator beast. Doc is my 30-year-old AC\u2019s fountain of youth.',
    category: 'Fixing',
    title: 'From freeze-up to refrigerator beast',
    line: 'It started rattling. A new motor and capacitor, about $30. It wasn\u2019t getting cold and kept freezing up. It was low on refrigerant. So I charged it, cleaned it, and built a tent to shade it.',
    tag: '2 Summers, 1 Doc',
    badge: { label: 'DELTA T', nums: '17 \u2192 30', sub: 'the difference in temperature', shout: 'BEAST MODE!!!!' },
    note: 'The air conditioner lives between two houses in a bit of a hot box.',
    callout: 'Electric bill: $346 in July, $180 in August.',
    promptLabel: 'See how I asked Doc',
    prompt: '\u201cThe only thing I\u2019m thinking about is the air conditioner lives between two houses in a bit of a hot box. I\u2019m sure that the air temperature around the air conditioner is very hot. I could put a fan outside on the 100-degree day to try and move some cooler air into that pocket so that it\u2019s, you know, not just stagnant air. Think about the hot air being rejected from the air conditioner is coming back down and staying in that hot box around the air conditioner. So it\u2019s kind of warming the external area around it instead of cool air moving past it.\u201d',
    payoff: 'A new air conditioner would have cost thousands. I did it for about $30 in parts, about $100 in tools, and my chat subscription.',
    bigLine: 'It\u2019s really %#@&! amazing.',
    colors: ['#2bb8ff', '#19c37d'],
    collage: 'three',
    lead: { src: 'assets/ac-iced-evaporator.webp', note: 'I knew something was wrong. Very wrong. DOC, HELP!!!!', alt: 'The inside of the air conditioner with the evaporator coil frozen into a solid block of ice.' },
    photos: [
      { src: 'assets/ac-tent.webp', kind: 'print', rot: -2, hold: 'tape', alt: 'A white PVC-pipe frame with shade cloth over the outdoor air conditioner, with a square opening cut around the fan so the hot air can leave straight up.' },
      { src: 'assets/ac-valves.webp', kind: 'print', rot: 4, hold: 'pin', alt: 'Brass charging fittings with blue and red handles on the refrigerant service ports of the outdoor unit.' },
      { src: 'assets/ac-capacitor.webp', kind: 'print', rot: -3, hold: 'magnet', alt: 'Inside the outdoor unit: the new dual run capacitor with a handwritten install date, a blue hard-start capacitor, and a red DANGER electrical shock warning label.' },
    ],
  },
  {
    id: 'birthday-card',
    headline: 'Doc helped me write a birthday card that sounds like me.',
    category: 'Writing to people you love',
    title: 'Write a birthday card that sounds like you',
    line: 'Not a greeting-card line, your actual voice, with the right inside joke.',
    prompt: 'Help me write a birthday card for my sister. Here are three things I love about her and one joke only we get.',
    payoff: 'A card she kept.',
    colors: ['#19c37d', '#2bb8ff'],
    image: '',
    alt: '',
  },
  {
    id: 'cocktail',
    headline: 'Doc invented a cocktail nobody has had before.',
    category: 'Hosting',
    title: 'Invent a cocktail for dinner with friends',
    line: 'A drink nobody has had before, with a name and a story.',
    prompt: 'Invent a one-of-a-kind cocktail for six friends having dinner. Fall evening, bourbon fans, one person who skips alcohol.',
    payoff: 'The drink everyone asked about.',
    colors: ['#2bb8ff', '#7c4dff'],
    image: '',
    alt: '',
  },
  {
    id: 'margarita-pancakes',
    headline: 'Doc turned my margarita pulp into pancakes.',
    category: 'Cooking',
    title: 'From margaritas to pancakes',
    line: 'My wife said my margaritas were the best ever, better than any restaurant she\u2019s had. The next morning, the leftover pulp became lemon-blueberry pancakes for the kids. Same result.',
    promptLabel: 'See how I asked Doc',
    prompt: 'The gist of what I typed: \u201cI just squeezed lemons and limes for margaritas. Is there anything cool I can make with the leftover pulp?\u201d',
    payoff: 'I squeezed a pile of lemons and limes for margaritas, asked what to do with the pulp, and Doc suggested lemon-blueberry pancakes. I never would have thought of it. The kids really appreciated them. One good night turned into a better morning, and what I learned from a tool that used to feel like chaos let me do that for my family.',
    colors: ['#19c37d', '#ffc83d'],
  },
  {
    id: 'hassle',
    headline: 'Doc told me which part to order. No repairman.',
    category: 'Getting out of a hassle',
    title: 'Skip the repairman call',
    line: 'Figure out the part, order it, and know when to call a professional instead.',
    prompt: 'My dishwasher stopped draining. Here is the model number. What are the likely causes, and which ones are safe for me to try?',
    payoff: 'One small part, one small fix. (Electrical, gas and air conditioning? Call a pro.)',
    colors: ['#ff9a3d', '#19c37d'],
    image: '',
    alt: '',
  },
  {
    id: 'this-website',
    headline: 'Doc and I built the website you\u2019re looking at.',
    category: 'Building something',
    title: 'Build the website you\u2019re looking at',
    line: 'You\u2019re on it right now. An idea on a golf course, a conversation with AI, and a real page with a sign-up form that works.',
    promptLabel: 'See what I asked Doc for',
    prompt: 'The gist of what I typed: \u201cI want a fun one-page website for a clinic that teaches busy adults to use AI. Bright and playful. One big picture panel for each everyday moment, with a short title and a line about the story. A Register button that floats on the screen and opens a pop-up that explains the clinic, with a sign-up form. Keep the word AI out of the headline. Make it easy for me to add new stories later.\u201d',
    payoff: 'A live site with working sign-ups, the same day. A little irony, too: a productivity tool, used to show people this was never about productivity.',
    link: { href: 'built/', text: 'How this was built \u2192' },
    colors: ['#2bb8ff', '#7c4dff'],
    photos: [
      { src: 'assets/this-website.webp', kind: 'print', rot: -3, hold: 'pin', alt: 'A phone showing a chat conversation beside a colorful web page that it produced.' },
    ],
  },
];

// ============================================================
// PANELS
// ============================================================
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

// A crude black marker line with an arrowhead, from the badge down to the savings callout. Two drawings, one per layout (phone / wide).
function sharpieArrow(kind) {
  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('class', 'board-arrow board-arrow--' + kind);
  const BOX = { m: '0 0 100 175', d: '0 0 100 110', sm: '0 0 100 210', sd: '0 0 100 120' };
  svg.setAttribute('viewBox', BOX[kind]);
  svg.setAttribute('aria-hidden', 'true');
  // m, d: AC badge to the savings callout. sm, sd: Honda old bulb to the new pack.
  const PATHS = {
    m: ['M 12 120 C 3 127, 1 141, 10 153', 'M 10 153 L 4 147', 'M 10 153 L 17 150'],
    d: ['M 8 48 C -1 62, -1 82, 12 95', 'M 12 95 L 7 94', 'M 12 95 L 11 90'],
    sm: ['M 38 150 C 44 142, 50 140, 56 144', 'M 56 144 L 50 139', 'M 56 144 L 49 148'],
    sd: ['M 31 87 C 40 79, 52 77, 61 82', 'M 61 82 L 55 77', 'M 61 82 L 54 86'],
  };
  const paths = PATHS[kind];
  paths.forEach((d) => {
    const path = document.createElementNS(NS, 'path');
    path.setAttribute('d', d);
    svg.appendChild(path);
  });
  return svg;
}

function renderStories() {
  const host = document.getElementById('moments');
  if (!host) return;
  STORIES.forEach((story, i) => {
    const panel = el('section', story.layout === 'split' ? 'moment moment--split' : 'moment');
    if (story.collage === 'pair') panel.classList.add('moment--pair');
    if (story.collage === 'three') panel.classList.add('moment--three');
    panel.id = story.id;
    panel.style.setProperty('--c1', story.colors[0]);
    panel.style.setProperty('--c2', story.colors[1]);

    if (story.image) {
      const img = el('img', 'moment__img');
      img.src = story.image;
      img.alt = story.alt || '';
      if (story.imagePosition) img.style.objectPosition = story.imagePosition;
      img.loading = i === 0 ? 'eager' : 'lazy';
      img.decoding = 'async';
      panel.appendChild(img);
    }

    if (story.headline) {
      panel.classList.add('moment--headline');
      panel.appendChild(el('h2', 'moment__headline', story.headline));
    }

    if (story.lead) {
      panel.classList.add('moment--lead');
      const lead = el('div', 'moment__lead');
      const print = el('figure', 'lead__print sticker--print hold-tape');
      const im = el('img');
      im.src = story.lead.src;
      im.alt = story.lead.alt || '';
      im.loading = 'lazy';
      im.decoding = 'async';
      print.appendChild(im);
      if (story.lead.note) {
        const ln = el('div', 'lead__note');
        ln.appendChild(el('p', '', story.lead.note));
        print.appendChild(ln);
      }
      lead.appendChild(print);
      panel.appendChild(lead);
    }

    if (story.photos && story.photos.length) {
      panel.classList.add('moment--collage');
      const board = el('div', 'moment__photos');
      story.photos.forEach((ph) => {
        const fig = el('figure', 'sticker sticker--' + (ph.kind || 'print') + ' hold-' + (ph.hold || 'tape') + (ph.cls ? ' ' + ph.cls : ''));
        fig.style.setProperty('--rot', (ph.rot || 0) + 'deg');
        const im = el('img');
        im.src = ph.src;
        im.alt = ph.alt || '';
        im.loading = 'lazy';
        im.decoding = 'async';
        fig.appendChild(im);
        if (ph.label) fig.appendChild(el('span', 'print__label', ph.label));
        board.appendChild(fig);
      });
      if (story.note) {
        panel.classList.add('moment--note');
        const note = el('figure', 'sticker sticker--note');
        note.appendChild(el('p', '', story.note));
        board.appendChild(note);
      }
      if (story.callout) {
        const call = el('figure', 'sticker sticker--kraft');
        call.appendChild(el('p', '', story.callout));
        board.appendChild(call);
      }
      if (story.swap) {
        panel.classList.add('moment--swap');
        const note2 = el('figure', 'sticker sticker--note sticker--note2');
        note2.appendChild(el('p', '', story.swap.note));
        board.appendChild(note2);
        board.appendChild(sharpieArrow('sm'));
        board.appendChild(sharpieArrow('sd'));
      }
      if (story.badge) {
        const badge = el('figure', 'sticker sticker--badge');
        badge.appendChild(el('p', 'badge__label', story.badge.label));
        badge.appendChild(el('p', 'badge__nums', story.badge.nums));
        badge.appendChild(el('p', 'badge__sub', story.badge.sub));
        badge.appendChild(el('p', 'badge__shout', story.badge.shout));
        board.appendChild(badge);
        board.appendChild(sharpieArrow('m'));
        board.appendChild(sharpieArrow('d'));
      }
      panel.appendChild(board);
    }

    const body = el('div', 'moment__body');
    if (!story.headline) {
      body.appendChild(el('p', 'moment__cat', story.category));
      body.appendChild(el('h2', 'moment__title', story.title));
    }
    body.appendChild(el('p', 'moment__line', story.line));
    if (story.tag) body.appendChild(el('p', 'moment__tag', story.tag));
    if (story.payoff) body.appendChild(el('p', story.payoffBig ? 'moment__payoff moment__payoff--big' : 'moment__payoff', story.payoff));
    if (story.bigLine) body.appendChild(el('p', 'moment__payoff moment__payoff--big moment__payoff--long', story.bigLine));

    const more = el('details', 'moment__more');
    const summary = el('summary', '', story.promptLabel || 'See how I asked Doc');
    const tip = el('span', 'moment__tip', DOC_TIP);
    tip.id = 'tip-' + story.id;
    tip.setAttribute('role', 'tooltip');
    tip.setAttribute('aria-hidden', 'true'); // keeps it out of the button's name; aria-describedby still reads it
    summary.setAttribute('aria-describedby', tip.id);
    summary.appendChild(tip);
    more.appendChild(summary);
    const inner = el('div', 'moment__more-body');
    inner.appendChild(el('p', 'moment__prompt', story.prompt));
    if (story.steps) {
      const ol = el('ol', 'moment__steps');
      story.steps.forEach((t) => ol.appendChild(el('li', '', '\u201c' + t + '\u201d')));
      inner.appendChild(ol);
    }
    more.appendChild(inner);
    body.appendChild(more);

    if (story.link) {
      const more2 = el('a', 'moment__link', story.link.text);
      more2.href = story.link.href;
      body.appendChild(more2);
    }

    panel.appendChild(body);
    host.appendChild(panel);
  });
  // The intro text is cut into bundles; each sits after the panel named in its data-after.
  // "scroll down and you'll see" (bundle 3) now follows two examples, so check wording on review.
  document.querySelectorAll('.intro[data-after]').forEach((sec) => {
    const target = document.getElementById(sec.dataset.after);
    if (target) target.after(sec);
  });
}

// A soft ring pulses on each "See how I asked Doc" button for about 9.6 seconds every time it scrolls into view.
// Hovering, focusing or opening a button stops that button's pulse for good. Never runs with reduced motion.
function initDocPulse() {
  if (!('IntersectionObserver' in window)) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const done = new WeakSet();
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      const s = e.target;
      if (done.has(s)) return;
      if (e.intersectionRatio >= 0.6) {
        s.classList.remove('is-pulsing');
        void s.offsetWidth;                      // restart the animation from the first beat
        s.classList.add('is-pulsing');
      } else {
        s.classList.remove('is-pulsing');
      }
    });
  }, { threshold: [0, 0.6] });  // callback at 0 and at 0.6; "in view" means 60% showing
  document.querySelectorAll('.moment__more summary').forEach((s) => {
    io.observe(s);
    s.addEventListener('animationend', () => s.classList.remove('is-pulsing'));
    ['mouseenter', 'focus', 'click'].forEach((ev) => s.addEventListener(ev, () => { done.add(s); s.classList.remove('is-pulsing'); io.unobserve(s); }, { once: true }));
  });
}

function initLightbox() {
  const box = document.getElementById('lightbox');
  if (!box || typeof box.showModal !== 'function') return;
  const img = box.querySelector('.lightbox__img');
  let opener = null;
  function open(fig) {
    const src = fig.dataset.zoom;
    img.src = src;
    img.alt = (fig.querySelector('img') || {}).alt || '';
    opener = fig;
    box.showModal();
    box.scrollTop = 0;
    const mid = () => { box.scrollLeft = Math.max(0, (box.scrollWidth - box.clientWidth) / 2); };
    mid(); img.onload = mid;
  }
  document.querySelectorAll('[data-zoom]').forEach(fig => {
    fig.addEventListener('click', () => open(fig));
    fig.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(fig); } });
  });
  box.addEventListener('click', e => { if (e.target === box || e.target.closest('.lightbox__close') || e.target === img) box.close(); });
  box.addEventListener('close', () => { img.removeAttribute('src'); if (opener) opener.focus({ preventScroll: true }); });
}

function initPriceTips() {
  const tip = document.getElementById('price-tip');
  const cards = Array.from(document.querySelectorAll('.price__card[data-tip]'));
  if (!tip || !cards.length) return;
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let pinned = -1, lastType = 'mouse', touched = false;
  const stopPulse = () => { touched = true; cards.forEach((c) => c.classList.remove('is-pulsing')); };
  const show = (i) => {
    const r = cards[i].getBoundingClientRect(), t = tip.getBoundingClientRect();
    tip.textContent = cards[i].dataset.tip;
    tip.style.setProperty('--tail', Math.max(24, Math.min(t.width - 24, r.left + r.width / 2 - t.left)) + 'px');
    tip.classList.add('is-open');
    cards.forEach((c, j) => { c.classList.toggle('is-active', j === i); c.setAttribute('aria-expanded', j === i ? 'true' : 'false'); });
    // On phones the chosen print grows; re-aim the callout tail once it has settled.
    clearTimeout(show.t);
    show.t = setTimeout(() => {
      if (!cards[i].classList.contains('is-active')) return;
      const r2 = cards[i].getBoundingClientRect(), t2 = tip.getBoundingClientRect();
      tip.style.setProperty('--tail', Math.max(24, Math.min(t2.width - 24, r2.left + r2.width / 2 - t2.left)) + 'px');
    }, 360);
  };
  const hide = () => {
    tip.textContent = '';
    tip.classList.remove('is-open');
    cards.forEach((c) => { c.classList.remove('is-active'); c.setAttribute('aria-expanded', 'false'); });
  };
  const clear = () => { pinned = -1; hide(); };
  const toggle = (i) => { stopPulse(); pinned = pinned === i ? -1 : i; if (pinned >= 0) show(i); else if (lastType !== 'mouse') hide(); };
  cards.forEach((c, i) => {
    c.addEventListener('pointerdown', (e) => { lastType = e.pointerType; });
    c.addEventListener('pointerenter', (e) => { if (e.pointerType === 'mouse') { stopPulse(); show(i); } });
    c.addEventListener('pointerleave', (e) => { if (e.pointerType === 'mouse') { if (pinned >= 0) show(pinned); else hide(); } });
    c.addEventListener('focus', () => { if (c.matches(':focus-visible')) { stopPulse(); show(i); } });
    c.addEventListener('blur', () => { if (pinned < 0 && lastType === 'mouse') hide(); });
    c.addEventListener('click', () => toggle(i));
    c.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); lastType = 'key'; toggle(i); } });
  });
  document.addEventListener('click', (e) => { if (!e.target.closest('.price__cards') && !e.target.closest('#price-tip')) clear(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') clear(); });
  if (!reduce && 'IntersectionObserver' in window) {
    new IntersectionObserver((entries) => {
      if (touched) return;
      cards.forEach((c) => {
        c.classList.remove('is-pulsing');
        if (entries[0].intersectionRatio >= 0.6) { void c.offsetWidth; c.classList.add('is-pulsing'); }
      });
    }, { threshold: [0, 0.6] }).observe(document.querySelector('.price__cards'));
  }
}

function initPhoneCarousel() {
  const root = document.getElementById('zero-carousel');
  if (!root) return;
  const list = root.querySelector('.zero__phones');
  const slides = Array.from(list.children);
  const dots = Array.from(root.querySelectorAll('.zero__dots button'));
  const n = slides.length;
  const mql = window.matchMedia('(max-width: 899px)');
  const dur = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? '0s' : '.35s';
  let i = 0, busy = false, sx = 0, sy = 0, swiped = false;
  const setDots = () => dots.forEach((d, k) => { d.classList.toggle('is-on', k === i); d.setAttribute('aria-current', k === i ? 'true' : 'false'); });
  const announce = () => { list.dataset.index = i; list.dispatchEvent(new CustomEvent('zero:slide')); };
  const enable = () => {
    list.classList.add('is-carousel');
    slides.forEach((s, k) => {
      const img = s.querySelector('img'); if (img) img.loading = 'eager';
      s.style.transition = 'none';
      s.style.transform = k === i ? 'translateX(0)' : 'translateX(100%)';
      s.style.visibility = k === i ? 'visible' : 'hidden';
      s.setAttribute('aria-hidden', k === i ? 'false' : 'true');
    });
    setDots(); announce();
  };
  const disable = () => {
    list.classList.remove('is-carousel');
    slides.forEach((s) => { s.removeAttribute('style'); s.removeAttribute('aria-hidden'); });
    announce();
  };
  const go = (to, dir) => {
    if (busy || to === i) return;
    const cur = slides[i], nxt = slides[to];
    busy = true;
    nxt.style.transition = 'none';
    nxt.style.transform = 'translateX(' + dir * 100 + '%)';
    nxt.style.visibility = 'visible';
    nxt.setAttribute('aria-hidden', 'false');
    void nxt.offsetWidth;
    cur.style.transition = nxt.style.transition = 'transform ' + dur + ' ease';
    cur.style.transform = 'translateX(' + (-dir * 100) + '%)';
    nxt.style.transform = 'translateX(0)';
    setTimeout(() => { cur.style.visibility = 'hidden'; cur.style.transition = 'none'; cur.setAttribute('aria-hidden', 'true'); busy = false; }, dur === '0s' ? 0 : 360);
    i = to; setDots(); announce();
  };
  const step = (dir) => go((i + dir + n) % n, dir);
  root.querySelector('.zero__nav--prev').addEventListener('click', () => step(-1));
  root.querySelector('.zero__nav--next').addEventListener('click', () => step(1));
  dots.forEach((d, k) => d.addEventListener('click', () => { const diff = (k - i + n) % n; go(k, diff <= n / 2 ? 1 : -1); }));
  const vp = root.querySelector('.zero__viewport');
  vp.addEventListener('pointerdown', (e) => { sx = e.clientX; sy = e.clientY; swiped = false; });
  vp.addEventListener('pointerup', (e) => {
    if (!mql.matches) return;
    const dx = e.clientX - sx, dy = e.clientY - sy;
    if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy) * 1.5) { swiped = true; step(dx < 0 ? 1 : -1); }
  });
  root.addEventListener('click', (e) => { if (swiped) { e.stopPropagation(); e.preventDefault(); swiped = false; } }, true);
  root.addEventListener('keydown', (e) => {
    if (!mql.matches) return;
    if (e.key === 'ArrowLeft') { step(-1); e.preventDefault(); }
    if (e.key === 'ArrowRight') { step(1); e.preventDefault(); }
  });
  mql.addEventListener('change', (e) => { if (e.matches) enable(); else disable(); });
  if (mql.matches) enable();
}

function initReveal() {
  if (!('IntersectionObserver' in window)) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); }
    });
  }, { threshold: 0.25 });
  document.querySelectorAll('.moment').forEach((p) => { p.classList.add('will-reveal'); io.observe(p); });
}

// ============================================================
// TRIAL LETTER (door 1): Todd's letter over the real homepage when the link has ?trial
// Letter text is Todd's draft (2026-10-02), compressed from his dictation. {term} = the shared "Zero State" style.
// Button labels ("Join the free trial", "Tell me more" wording per Todd) and the sign-off are Claude's bridging.
// ============================================================
const TRIAL_LETTER = [
  'Hi. I’m sincerely excited to share my journey and discovery of how AI has made me more capable. And I want to share that with others.',
  'You probably know me, or you know somebody who does. Thank you for taking a moment to read this.',
  'A couple of years ago I dove into AI and arrived at a place I find extremely satisfying. It has changed how much I can do for the people around me and for myself.',
  'The start wasn’t smooth. People just said “use AI.” I didn’t know what a language model was or who made one, and I downloaded a knockoff with a name something like “G Chat PT.” It tried to trick me with the name and looked like the real site. Then I figured it out, got ChatGPT and Claude downloaded, and started using them. But every one of them puts a white screen in front of you and says, here, use AI. I stared at a white screen with no idea what to do. As technical as I am, I know that moment. I call it {term}.',
  'Now I can’t imagine living without it every day. Not all day. Like your phone, your TV, the toilet. It’s just there. I’ve made the most amazing meat candy brisket, learned how to charge my air conditioner, saving us thousands of dollars, and collaborated on a beautiful father of the bride speech.',
  'One thing I want to say plainly: this isn’t like the social media time suck. Yes, you download an app and log in, but it isn’t a feed and it doesn’t want your time. It becomes an assistant that’s always there, ready to help amplify your capabilities and your responsibilities. It’s about capability, not productivity.',
  'I want to show people the way out of {term}, so I’ve built a workshop, and I need to practice. If you’ve never opened it, or opened it and didn’t know what to do next, this is for you. By the end you’ll have made something and sent it to someone.',
  'I’d like to trial it with a few people, one on one or with a couple of friends, free. About an hour at a coffee shop or a local establishment. Just bring your phone. No sales pitch. If it goes well, maybe I can get a testimonial. If not, I got great practice.',
  'To join the trial, click the trial button. To learn more first, click “Tell me more” and go through the site.',
];

function initTrialLetter() {
  if (!TRIAL_ON || !/[?&]trial(=|&|$)/.test(location.search)) return;
  const dlg = document.createElement('dialog');
  dlg.className = 'trial-letter';
  dlg.setAttribute('aria-label', 'A note from Todd');
  const card = el('div', 'trial-letter__card');
  card.tabIndex = -1;
  TRIAL_LETTER.forEach((t) => {
    const p = el('p');
    p.innerHTML = t.replace(/\{term\}/g, '<span class="term">Zero State</span>');
    card.appendChild(p);
  });
  card.appendChild(el('p', 'trial-letter__sign', 'Todd'));
  const bar = el('div', 'trial-letter__bar');
  const join = el('a', 'btn btn--hero', 'Join the free trial');
  join.href = TRIAL_JOIN_URL;
  const more = el('button', 'btn btn--ghost', 'Tell me more');
  more.type = 'button';
  bar.appendChild(join);
  bar.appendChild(more);
  dlg.appendChild(card);
  dlg.appendChild(bar);
  document.body.appendChild(dlg);

  // "Washes away" into the homepage; Esc does the same as "Tell me more".
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let leaving = false;
  const dismiss = () => {
    if (leaving) return;
    leaving = true;
    try { history.replaceState(null, '', location.pathname + location.hash); } catch (e) { /* fine */ }
    if (reduce) { dlg.close(); dlg.remove(); return; }
    dlg.classList.add('is-leaving');
    setTimeout(() => { dlg.close(); dlg.remove(); }, 700);
  };
  more.addEventListener('click', dismiss);
  dlg.addEventListener('cancel', (e) => { e.preventDefault(); dismiss(); });
  if (typeof dlg.showModal === 'function') dlg.showModal(); else dlg.setAttribute('open', '');
  card.focus({ preventScroll: true });
}

// ============================================================
// TRIAL PLANE (door 2): Todd in a biplane flies into the hero, a callout invites people to the free trial.
// Homepage only. It owns the hero and leaves when the visitor scrolls past it, so it never meets the Doc peeker.
// Remembers on the device once clicked or closed (localStorage key icdt-trial-plane, in try/catch).
// Swap the picture: assets/trial-plane.webp (transparent, nose pointing LEFT: it flies in from the right and leaves to the left). Callout words are Todd's, compressed.
// ============================================================
const TRIAL_PLANE_KEY = 'icdt-trial-plane';
const TRIAL_PLANE_TEASER = 'Hi there! I’m going to be right back to offer you a trial.';
const TRIAL_PLANE_TEXT = 'I’m ready to trial this free hands-on starter AI workshop. Click the plane to become one of my first trial members.';

function initTrialPlane() {
  const hero = document.querySelector('header.hero');
  if (!TRIAL_ON || !hero || /[?&]trial(=|&|$)/.test(location.search)) return;
  const preview = /[?&]plane(=|&|$)/.test(location.search);   // ?plane previews it even after it was dismissed
  const read = () => { try { return localStorage.getItem(TRIAL_PLANE_KEY); } catch (e) { return null; } };
  const remember = () => { try { localStorage.setItem(TRIAL_PLANE_KEY, '1'); } catch (e) { /* storage blocked: fine */ } };
  if (!preview && read()) return;
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const box = el('aside', 'trial-plane');
  box.setAttribute('aria-label', 'Join the free trial');
  const bubble = el('div', 'trial-plane__bubble');
  bubble.appendChild(el('p', '', TRIAL_PLANE_TEXT));
  const x = el('button', 'trial-plane__x', '×');
  x.type = 'button';
  x.setAttribute('aria-label', 'Close');
  bubble.appendChild(x);
  const craft = el('a', 'trial-plane__craft');
  craft.href = TRIAL_JOIN_URL + '?letter';   // the join page then shows Todd's letter over itself
  const img = el('img');
  img.src = 'assets/trial-plane.webp';
  img.alt = 'Todd flying a yellow and navy biplane. Click to join the free trial.';
  img.decoding = 'async';
  craft.appendChild(img);
  box.appendChild(bubble);
  box.appendChild(craft);

  // Two passes: a short "be right back" tease, then (about 17s later) the real offer.
  // Reduced motion skips the tease and shows the offer once.
  let state = 'idle', timers = [], pass = reduce ? 2 : 1;
  const later = (fn, ms) => { const t = setTimeout(fn, ms); timers.push(t); };
  const heroGone = () => hero.getBoundingClientRect().bottom < window.innerHeight * 0.35;
  const busy = () => document.hidden || document.querySelector('dialog[open]');
  const bubbleText = bubble.querySelector('p');
  const onScroll = () => { if (state !== 'out' && heroGone()) finish(); };
  const finish = () => {
    if (state === 'out') return;
    state = 'out';
    timers.forEach(clearTimeout);
    box.classList.remove('is-landed');
    box.classList.add('is-out');
    window.removeEventListener('scroll', onScroll);
    setTimeout(() => box.remove(), reduce ? 400 : 2000);
  };
  const fly = () => {
    bubbleText.textContent = pass === 1 ? TRIAL_PLANE_TEASER : TRIAL_PLANE_TEXT;
    box.classList.remove('is-in', 'is-landed', 'is-out');
    if (!box.isConnected) document.body.appendChild(box);
    void box.offsetWidth;
    requestAnimationFrame(() => requestAnimationFrame(() => box.classList.add('is-in')));
    state = 'in';
    later(() => box.classList.add('is-landed'), reduce ? 200 : 2300);
    later(pass === 1 ? awayForNow : finish, pass === 1 ? 7000 : 22000);
  };
  const awayForNow = () => {
    state = 'away';
    box.classList.remove('is-landed');
    box.classList.add('is-out');
    later(() => box.remove(), 2000);
    later(comeBack, 17000);
  };
  const comeBack = () => {
    if (state === 'out') return;
    if (heroGone()) { finish(); return; }
    if (busy()) { later(comeBack, 3000); return; }
    pass = 2;
    fly();
  };
  craft.addEventListener('click', remember);
  x.addEventListener('click', () => { remember(); finish(); });

  const start = () => {
    if (state !== 'idle' || busy() || heroGone()) { later(start, 3000); return; }
    window.addEventListener('scroll', onScroll, { passive: true });
    fly();
  };
  const go = () => later(start, preview ? 600 : 2000);
  if (img.complete && img.naturalWidth) go(); else img.addEventListener('load', go);
}

// ============================================================
// REGISTER DIALOG
// ============================================================
function initRegister() {
  const dlg = document.getElementById('register');
  if (!dlg) return;
  const open = () => {
    if (typeof dlg.showModal === 'function') dlg.showModal();
    else dlg.setAttribute('open', '');
  };
  document.querySelectorAll('[data-open-register]').forEach((b) => b.addEventListener('click', open));
  dlg.addEventListener('click', (e) => { if (e.target === dlg) dlg.close(); });
  if (location.hash === '#register') open();
}

// ============================================================
// SIGN-UP (Firestore)
// ============================================================
function isConfigured() {
  return Object.values(FIREBASE_CONFIG).every((v) => v && !String(v).startsWith('REPLACE'));
}

async function saveSignup(data) {
  if (!isConfigured()) throw new Error('not-configured');
  const [appMod, fsMod] = await Promise.all([
    import(FIREBASE_SDK + 'firebase-app.js'),
    import(FIREBASE_SDK + 'firebase-firestore.js'),
  ]);
  const app = appMod.getApps().length ? appMod.getApp() : appMod.initializeApp(FIREBASE_CONFIG);
  const db = fsMod.getFirestore(app);
  await fsMod.addDoc(fsMod.collection(db, SIGNUPS_COLLECTION), {
    name: data.name,
    email: data.email,
    comfort: data.comfort,
    want: data.want,
    source: 'enjoy',
    createdAt: fsMod.serverTimestamp(),
  });
}

function initSignup() {
  const form = document.getElementById('signup');
  if (!form) return;
  const status = document.getElementById('signup-status');
  const btn = document.getElementById('signup-submit');

  const say = (msg, kind) => { status.textContent = msg; status.dataset.kind = kind || ''; };

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    if (fd.get('website')) return; // honeypot
    const name = String(fd.get('name') || '').trim();
    const email = String(fd.get('email') || '').trim();
    const comfort = parseInt(fd.get('comfort'), 10);
    const want = String(fd.get('want') || '').trim();

    if (!name || !/^\S+@\S+\.\S+$/.test(email) || !(comfort >= 1 && comfort <= 5)) {
      say('Please add your name, a valid email, and pick how comfortable you are.', 'error');
      return;
    }

    btn.disabled = true;
    say('Saving your spot…', '');
    try {
      await saveSignup({ name, email, comfort, want });
      form.reset();
      say('Thanks! We have noted your interest. We will email you the date and place as soon as they are set.', 'ok');
    } catch (err) {
      const mailto = 'mailto:' + CONTACT_EMAIL + '?subject=' + encodeURIComponent('Register me for the workshop') +
        '&body=' + encodeURIComponent('Name: ' + name + '\nEmail: ' + email + '\nComfort with AI (1-5): ' + comfort + '\nWhat I’d love to do: ' + want);
      status.textContent = '';
      status.dataset.kind = 'error';
      status.appendChild(document.createTextNode(
        err.message === 'not-configured'
          ? 'Sign-ups aren’t connected yet, so nothing was saved. '
          : 'We couldn’t save that just now. '));
      const a = el('a', '', 'Email us instead');
      a.href = mailto;
      status.appendChild(a);
      status.appendChild(document.createTextNode('.'));
    } finally {
      btn.disabled = false;
    }
  });
}


// ============================================================
// ASK TODD (chat companion stub)
// Real endpoint later: set ASK_ENDPOINT above. Until then it is honest about it.
// ============================================================
// More info: the floating button opens a vertical stack of links that scroll to panels on this page.
// Closes after a choice, on a tap outside, or on Esc (focus returns to the button).
// Floating buttons flip to white over dark panels (hero, navy message panel, brisket) so they never vanish into a same-colored background.
function initFabFlip() {
  const ids = ['top', 'message', 'brisket'];
  let ticking = false;
  function check() {
    ticking = false;
    const y = window.innerHeight - 45;
    let dark = false;
    for (const id of ids) {
      const el = document.getElementById(id);
      if (!el) continue;
      const r = el.getBoundingClientRect();
      if (r.top <= y && r.bottom >= y) { dark = true; break; }
    }
    document.body.classList.toggle('fab-on-dark', dark);
  }
  function queue() { if (!ticking) { ticking = true; requestAnimationFrame(check); } }
  window.addEventListener('scroll', queue, { passive: true });
  window.addEventListener('resize', queue);
  check();
}

function initMoreMenu() {
  const wrap = document.getElementById('more');
  if (!wrap) return;
  const btn = wrap.querySelector('.more__btn');
  const stack = wrap.querySelector('.more__stack');
  const label = wrap.querySelector('.more__label');
  if (!btn || !stack || !label) return;
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let t = null;
  const isOpen = () => btn.getAttribute('aria-expanded') === 'true';
  const setOpen = (open, focusBtn) => {
    clearTimeout(t);
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    label.textContent = open ? 'Close' : 'More info';
    if (open) { stack.hidden = false; void stack.offsetWidth; wrap.classList.add('is-open'); }
    else { wrap.classList.remove('is-open'); t = setTimeout(() => { stack.hidden = true; }, reduce ? 0 : 260); }
    if (focusBtn) btn.focus();
  };
  btn.addEventListener('click', () => setOpen(!isOpen()));
  stack.addEventListener('click', (e) => {
    const a = e.target.closest('a');
    if (!a) return;
    const target = document.getElementById((a.getAttribute('href') || '').slice(1));
    if (target) { e.preventDefault(); target.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' }); }
    setOpen(false);
  });
  document.addEventListener('click', (e) => { if (isOpen() && !wrap.contains(e.target)) setOpen(false); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && isOpen()) setOpen(false, true); });
}

// The "As easy as turning on the radio" pill on the leave-with panel opens a scrollable storyboard.
function initStory() {
  const dlg = document.getElementById('story');
  if (!dlg) return;
  const open = () => { if (typeof dlg.showModal === 'function') dlg.showModal(); else dlg.setAttribute('open', ''); dlg.scrollTop = 0; };
  document.querySelectorAll('[data-open-story]').forEach((b) => b.addEventListener('click', open));
  dlg.addEventListener('click', (e) => { if (e.target === dlg && typeof dlg.close === 'function') dlg.close(); });
}

function initAsk() {
  const dlg = document.getElementById('ask');
  if (!dlg) return;
  const log = document.getElementById('ask-log');
  const form = document.getElementById('ask-form');
  const input = document.getElementById('ask-input');
  const send = document.getElementById('ask-send');

  const bubble = (who, text) => {
    const b = el('div', 'bubble bubble--' + who);
    b.appendChild(document.createTextNode(text));
    log.appendChild(b);
    log.scrollTop = log.scrollHeight;
    return b;
  };

  let greeted = false;
  const open = () => {
    if (typeof dlg.showModal === 'function') dlg.showModal(); else dlg.setAttribute('open', '');
    if (!greeted) {
      greeted = true;
      bubble('bot', 'Hi, I\u2019m Todd\u2019s chat companion. Ask me anything about the workshop: who it\u2019s for, what we\u2019ll do, how it works.');
    }
    input.focus();
  };
  document.querySelectorAll('[data-open-ask]').forEach((b) => b.addEventListener('click', open));
  dlg.addEventListener('click', (e) => { if (e.target === dlg) dlg.close(); });
  if (location.hash === '#ask') open();

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q) return;
    input.value = '';
    bubble('me', q);

    if (!ASK_ENDPOINT) {
      const b = bubble('bot', 'I\u2019m not switched on yet, so I can\u2019t answer that one. ');
      const a = el('a', '', 'Email Todd your question');
      a.href = 'mailto:' + CONTACT_EMAIL + '?subject=' + encodeURIComponent('A question about the workshop') + '&body=' + encodeURIComponent(q);
      b.appendChild(a);
      b.appendChild(document.createTextNode(' and he\u2019ll write back. Or check the '));
      const f = el('a', '', 'FAQ');
      f.href = 'faq/';
      b.appendChild(f);
      b.appendChild(document.createTextNode('.'));
      return;
    }

    send.disabled = true;
    const wait = bubble('bot', '\u2026');
    try {
      const res = await fetch(ASK_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
      });
      if (!res.ok) throw new Error('bad status');
      const data = await res.json();
      wait.textContent = String(data.answer || 'Sorry, I don\u2019t have an answer for that yet.');
    } catch (err) {
      wait.textContent = 'Sorry, something went wrong. Please try again, or email ' + CONTACT_EMAIL + '.';
    } finally {
      send.disabled = false;
      log.scrollTop = log.scrollHeight;
    }
  });
}

// One arrow at the bottom of every panel after the hero: down to the next panel, and on the last one, up to the top.
function addPanelArrows() {
  const panels = [document.getElementById('message'), document.getElementById('hello'), document.getElementById('zero-state'), document.getElementById('price'), document.getElementById('testimonials'), document.getElementById('what-we-do'), document.getElementById('what-you-get'), document.getElementById('zero-bridge'), document.getElementById('zero-tractor'), document.getElementById('zero-2'), document.getElementById('zero-sixteen'), document.getElementById('zero-3'), document.getElementById('zero-town')]
    .concat(Array.from(document.querySelectorAll('#moments > section')))
    .concat([document.getElementById('ways'), document.getElementById('faq')])
    .filter(Boolean);
  panels.forEach((panel, i) => {
    const next = panels[i + 1];
    const a = el('a', 'panel-next', next ? '\u2193' : '\u2191');
    a.href = next && next.id ? '#' + next.id : '#top';
    a.setAttribute('aria-label', next ? 'Next panel' : 'Back to the top');
    panel.classList.add('has-next');
    panel.appendChild(a);
  });
}

// Zero State: the five phone screenshots each say their line in a speech bubble.
// Desktop: hover or keyboard focus. Touch: tap to show, tap again (or elsewhere) to hide.
// Idle: while the panel is on screen, one bubble at a time fades in and out in random order.
// Zero State phone call-outs: three lines per phone, one drawn at random each time the bubble shows. `start` = the line written in the HTML.
const ZERO_POOLS = {
  chatgpt: { start: 1, lines: ['Chat or Work? Which one is mine?', 'Connect Drive? Notion? I haven\u2019t even said hello. Zero instructions, thanks.', 'Two tabs, two Connect buttons, zero instructions. Cool.'] },
  gemini: { start: 2, lines: ['Ask you what, exactly?', 'The keyboard\u2019s up and the screen\u2019s empty. So I just\u2026 type?', ['Ask Gemini? Great. Ask it WHAT?', 'Useless.']] },
  claude: { start: 1, lines: ['Good morning to you too. Now what?', 'Chat about what? Nobody said. Is this a help line?', 'It\u2019s friendly. It\u2019s also useless. Where do I start?'] },
  grok: { start: 0, lines: [['Here\u2019s a coupon?', 'Coupon for what? I came here for answers, not 20% off a pizza.'], 'A free upgrade to a thing I don\u2019t understand yet. Thanks?', 'SuperGrok for $0.00? I haven\u2019t figured out regular Grok.'] },
  copilot: { start: 2, lines: ['Search. That\u2019s it. That\u2019s the whole screen.', 'Search for what? There is literally nothing here.', 'Totally blank. Is it broken, or is this the product?'] },
};
function initPhoneBubbles() {
  const wrap = document.querySelector('.zero__phones');
  if (!wrap) return;
  const figs = Array.from(wrap.querySelectorAll('.zero__fig'));
  if (!figs.length) return;
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let current = -1, timer = null, resume = null, held = -1, onScreen = false, lastType = 'mouse';
  // Each phone has a pool of three lines; every time its bubble appears it draws one at random (never the same line twice in a row).
  const last = {};
  figs.forEach((f) => { const b = f.querySelector('.zero__bubble'); const k = b && b.id.replace('zb-', ''); if (k && ZERO_POOLS[k]) last[k] = ZERO_POOLS[k].start; });
  const reroll = (f) => {
    const b = f.querySelector('.zero__bubble'); const k = b && b.id.replace('zb-', '');
    const pool = k && ZERO_POOLS[k]; if (!pool) return;
    let n; do { n = Math.floor(Math.random() * pool.lines.length); } while (n === last[k] && pool.lines.length > 1);
    last[k] = n;
    const line = pool.lines[n];
    const main = Array.isArray(line) ? line[0] : line, sub = Array.isArray(line) ? line[1] : '';
    b.textContent = '\u201c' + main + '\u201d';
    if (sub) { const sp = document.createElement('span'); sp.className = 'zero__bubble-sub'; sp.textContent = sub; b.appendChild(sp); }
  };
  const show = (i) => { figs.forEach((f, j) => { const on = j === i; if (on && !f.classList.contains('is-on')) reroll(f); f.classList.toggle('is-on', on); }); current = i; };
  const stop = () => { clearTimeout(timer); clearTimeout(resume); };
  const tick = () => {
    if (!onScreen || held >= 0 || document.hidden) return;
    let i;
    if (wrap.classList.contains('is-carousel')) { const here = Number(wrap.dataset.index || 0); i = current === here ? -1 : here; }
    else { do { i = Math.floor(Math.random() * figs.length); } while (i === current && figs.length > 1); }
    show(i);
    timer = setTimeout(tick, 2200 + Math.random() * 900);
  };
  const start = (delay) => { if (reduce) return; stop(); resume = setTimeout(tick, delay); };
  const hold = (i) => { stop(); held = i; show(i); };
  const release = (delay) => { held = -1; show(-1); start(delay); };
  figs.forEach((f, i) => {
    f.addEventListener('pointerdown', (e) => { lastType = e.pointerType; });
    f.addEventListener('pointerenter', (e) => { if (e.pointerType === 'mouse') hold(i); });
    f.addEventListener('pointerleave', (e) => { if (e.pointerType === 'mouse' && held === i) release(3000); });
    f.addEventListener('focus', () => { if (f.matches(':focus-visible')) hold(i); });
    f.addEventListener('blur', () => { if (held === i && lastType === 'mouse') release(3000); });
    f.addEventListener('click', () => {
      if (lastType === 'mouse') return;
      if (held === i) release(3000); else hold(i);
    });
  });
  document.addEventListener('click', (e) => { if (held >= 0 && !wrap.contains(e.target)) release(1500); });
  wrap.addEventListener('zero:slide', () => { stop(); held = -1; show(-1); if (onScreen) start(1200); });
  document.addEventListener('visibilitychange', () => { if (document.hidden) { stop(); } else if (onScreen && held < 0) { start(500); } });
  if ('IntersectionObserver' in window) {
    new IntersectionObserver((entries) => {
      onScreen = entries[0].isIntersecting;
      if (onScreen) { if (held < 0) start(1000); } else { stop(); held = -1; show(-1); }
    }, { threshold: 0.35 }).observe(wrap);
  }
}

// ============================================================
// DOC HI: one pop-in on the Todd panel. Doc (same picture as the peeker) slides in from the right and lands mid-screen like the trial plane,
// a short pause, then a bubble says hello for 7 seconds, then he slides out. The X (or Esc) cancels it any time.
// Once per visit (sessionStorage, try/catch). While it is up, body.doc-hi-on fades the peeker out (CSS only; the peeker code is untouched).
// Homepage only. Words are Todd's, with "Hi," added.
// ============================================================
const DOC_HI_KEY = 'icdt-doc-hi';
const DOC_HI_TEXT = 'Hi, I’m Doc, Todd’s name for AI. I help him every day!';

function initDocHi() {
  const sec = document.getElementById('hello');
  if (!sec || !('IntersectionObserver' in window)) return;
  try { if (sessionStorage.getItem(DOC_HI_KEY)) return; } catch (e) { /* storage blocked: plays once per load */ }
  let fired = false;
  const io = new IntersectionObserver((entries) => {
    if (fired || !entries[0].isIntersecting) return;
    fired = true;
    io.disconnect();
    try { sessionStorage.setItem(DOC_HI_KEY, '1'); } catch (e) { /* fine */ }
    play();
  }, { rootMargin: '0px 0px -40% 0px', threshold: 0 });
  io.observe(sec);

  function play() {
    const box = document.createElement('div');
    box.className = 'doc-hi';
    box.setAttribute('role', 'status');
    const img = document.createElement('img');
    img.className = 'doc-hi__img';
    img.src = 'assets/doc-peek.webp';
    img.alt = '';
    img.width = 480; img.height = 476;
    const bubble = document.createElement('div');
    bubble.className = 'doc-hi__bubble';
    const p = document.createElement('p');
    p.textContent = DOC_HI_TEXT;
    bubble.appendChild(p);
    const x = document.createElement('button');
    x.type = 'button';
    x.className = 'doc-hi__x';
    x.setAttribute('aria-label', 'Close Doc');
    x.textContent = '×';
    box.append(img, bubble, x);

    let talkTimer = null, endTimer = null, outTimer = null, over = false;
    const leave = () => {
      if (over) return;
      over = true;
      clearTimeout(talkTimer); clearTimeout(endTimer);
      document.removeEventListener('keydown', onKey);
      box.classList.remove('is-talking');
      box.classList.remove('is-in');
      outTimer = setTimeout(() => { box.remove(); document.body.classList.remove('doc-hi-on'); }, 900);
    };
    const onKey = (e) => { if (e.key === 'Escape') leave(); };
    x.addEventListener('click', leave);
    document.addEventListener('keydown', onKey);
    const start = () => {
      if (over) return;
      document.body.classList.add('doc-hi-on');
      document.body.appendChild(box);
      void box.offsetWidth;
      box.classList.add('is-in');
      talkTimer = setTimeout(() => {
        box.classList.add('is-talking');
        endTimer = setTimeout(leave, 7000);
      }, 1300);
    };
    if (img.complete && img.naturalWidth) start();
    else { img.addEventListener('load', start, { once: true }); img.addEventListener('error', () => { over = true; document.removeEventListener('keydown', onKey); }, { once: true }); }
  }
}

document.addEventListener('DOMContentLoaded', () => {
  renderStories();
  addPanelArrows();
  initPhoneCarousel();
  initPhoneBubbles();
  initPriceTips();
  initLightbox();
  initReveal();
  initDocPulse();
  initRegister();
  initSignup();
  initMoreMenu();
  initFabFlip();
  initStory();
  initAsk();
  initTrialLetter();
  initTrialPlane();
  initDocHi();
  // Links from the "What I've done" page (../#brisket etc.): panels are built by JS, so scroll to them here.
  const target = location.hash.length > 1 && document.querySelector('.moment' + location.hash);
  if (target) setTimeout(() => target.scrollIntoView(), 50);
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

  // Hero check: a plain scroll listener (the hero counts as gone once none of it is on screen).
  const heroOnScreen = () => { const r = hero.getBoundingClientRect(); return r.bottom > 1 && r.top < window.innerHeight; };
  const checkHero = () => {
    const v = heroOnScreen();
    if (v === heroVisible) return;
    heroVisible = v;
    if (v) { clearTimeout(timer); if (current) current.stop(); }
    else if (!current) schedule(FIRST_DELAY);
  };
  if (hero && !preview) {
    heroVisible = heroOnScreen();
    if (!heroVisible) schedule(FIRST_DELAY);
    window.addEventListener('scroll', checkHero, { passive: true });
    window.addEventListener('resize', checkHero);
  } else {
    heroVisible = false;
    schedule(FIRST_DELAY);
  }
})();
// ==== PEEKER END ====
