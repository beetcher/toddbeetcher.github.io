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
// callout: optional kraft-paper scrap (a second, different callout) beside the photos.
// note: optional sticky note stuck on the collage board (text that belongs with the photos).
// collage: 'three' lays out sticky note, three prints and a kraft callout. payoffBig: true makes the payoff line large and pink.
// collage: 'pair' gives two landscape photos equal weight (default layout favors one large print and one small sticker).
// photos: [{ src, alt, kind: 'print' | 'cutout', rot: degrees, hold: 'tape' | 'corners' | 'magnet' | 'pin' | 'clip' | 'none' }]
// Like photos on a fridge: each one can be held up its own way.
// Text of the hover callout on every "See how I asked Doc" button. Edit freely.
const DOC_TIP = 'This is exactly what I typed to the AI to get the result you just read about.';

const STORIES = [
  {
    id: 'san-luis-valley',
    zero: 'from zero to a road trip story',
    category: 'Driving',
    title: 'Drive through the San Luis Valley',
    line: 'Suzanne was so absorbed in the story that when it ended she said, \u201cWow, that was really cool. Let\u2019s do that again.\u201d We did, valley after valley, the rest of the trip.',
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
    zero: 'from zero to brisket',
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
    zero: 'from zero to a lit dome light',
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
      { src: 'assets/honda-bulb.webp', kind: 'print', rot: 4, hold: 'pin', alt: 'A small glass festoon bulb with silver ends, the kind that goes in the dome light.' },
      { src: 'assets/honda-pilot.webp', kind: 'print', rot: -3, hold: 'magnet', alt: 'Todd\u2019s black 2005 Honda Pilot parked in the driveway under a tree.' },
    ],
  },
  {
    id: 'birthday-card',
    zero: 'from zero to a birthday card',
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
    zero: 'from zero to my own cocktail',
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
    zero: 'from zero to pancakes',
    category: 'Cooking',
    title: 'From margaritas to pancakes',
    line: 'My wife said my margaritas were the best ever, better than any restaurant she\u2019s had. The next morning, the leftover pulp became lemon-blueberry pancakes for the kids. Same result.',
    promptLabel: 'See how I asked Doc',
    prompt: 'The gist of what I typed: \u201cI just squeezed lemons and limes for margaritas. Is there anything cool I can make with the leftover pulp?\u201d',
    payoff: 'I squeezed a pile of lemons and limes for margaritas, asked what to do with the pulp, and it suggested lemon-blueberry pancakes. I never would have thought of it. The kids really appreciated them. One good night turned into a better morning, and this thing I learned from a tool that used to feel like chaos let me do that for my family.',
    colors: ['#19c37d', '#ffc83d'],
  },
  {
    id: 'hassle',
    zero: 'from zero to knowing the part',
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
    zero: 'from zero to a live website',
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

    if (story.photos && story.photos.length) {
      panel.classList.add('moment--collage');
      const board = el('div', 'moment__photos');
      story.photos.forEach((ph) => {
        const fig = el('figure', 'sticker sticker--' + (ph.kind || 'print') + ' hold-' + (ph.hold || 'tape'));
        fig.style.setProperty('--rot', (ph.rot || 0) + 'deg');
        const im = el('img');
        im.src = ph.src;
        im.alt = ph.alt || '';
        im.loading = 'lazy';
        im.decoding = 'async';
        fig.appendChild(im);
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
      panel.appendChild(board);
    }

    const body = el('div', 'moment__body');
    if (story.zero) body.appendChild(el('p', 'moment__zero', story.zero));
    body.appendChild(el('p', 'moment__cat', story.category));
    body.appendChild(el('h2', 'moment__title', story.title));
    body.appendChild(el('p', 'moment__line', story.line));
    if (story.payoff) body.appendChild(el('p', story.payoffBig ? 'moment__payoff moment__payoff--big' : 'moment__payoff', story.payoff));

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
    // Live "Meet Doc" button appears when the panel opens (Todd's call: label stays plain text).
    const meet = el('a', 'moment__meetdoc', 'Meet Doc');
    meet.href = 'doc/';
    inner.appendChild(meet);
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

// A soft ring pulses a few times on the "See how I asked Doc" button of the panel on screen.
// It stops for good once the visitor hovers or opens any of them, and never runs with reduced motion.
function initDocPulse() {
  if (!('IntersectionObserver' in window)) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const summaries = [...document.querySelectorAll('.moment__more summary')];
  let off = false;
  const stop = () => {
    off = true;
    io.disconnect();
    summaries.forEach((s) => s.classList.remove('is-pulsing'));
  };
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (!e.isIntersecting || off) return;
      const s = e.target;
      io.unobserve(s);
      s.classList.add('is-pulsing');
      s.addEventListener('animationend', () => s.classList.remove('is-pulsing'), { once: true });
    });
  }, { threshold: 0.9 });
  summaries.forEach((s) => {
    io.observe(s);
    ['mouseenter', 'focus', 'click'].forEach((ev) => s.addEventListener(ev, stop, { once: true }));
  });
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

document.addEventListener('DOMContentLoaded', () => {
  renderStories();
  initReveal();
  initDocPulse();
  initRegister();
  initSignup();
  initAsk();
  // Links from the "What I've done" page (../#brisket etc.): panels are built by JS, so scroll to them here.
  const target = location.hash.length > 1 && document.querySelector('.moment' + location.hash);
  if (target) setTimeout(() => target.scrollIntoView(), 50);
});
