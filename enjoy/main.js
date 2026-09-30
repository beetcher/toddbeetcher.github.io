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

// ---- Stories ----
// image: optional path like 'assets/san-luis-valley.webp' (shown behind the gradient).
// colors: two-stop gradient used when there is no image, and as the tint over one.
// NOTE: prompts and payoffs below are PLACEHOLDER sample content until Todd supplies real ones.
const STORIES = [
  {
    id: 'san-luis-valley',
    category: 'Driving',
    title: 'Drive through the San Luis Valley',
    line: 'A deep, gravelly storyteller narrated ten minutes of the valley’s history, right from the driver’s seat.',
    prompt: 'Be a storyteller with a deep, gravelly voice in the style of a Star Wars narrator. Tell me a 10-minute history and origins story of the San Luis Valley, framed for right now as I drive through it.',
    payoff: 'The same road, suddenly full of story.',
    colors: ['#ff3d6e', '#ff9a3d'],
    image: '',
    alt: '',
  },
  {
    id: 'brisket',
    category: 'Cooking',
    title: 'Cook a brisket without the panic',
    line: 'Timing, temperatures and what to do when it stalls, all in plain words.',
    prompt: 'I’m cooking a 12-pound brisket for eight people tonight. Walk me through it like a patient friend, and tell me what to do if it stalls.',
    payoff: 'Dinner on time and a very happy table.',
    colors: ['#7c4dff', '#ff3d6e'],
    image: '',
    alt: '',
  },
  {
    id: 'light-bulb',
    category: 'Fixing',
    title: 'The light that was broken for 10 years',
    line: 'One question, one minute, one fixed fixture.',
    prompt: 'Here is what my light fixture looks like and what it does. What’s wrong and how do I fix it?',
    payoff: 'Ten years of “I’ll get to it” ended in a minute.',
    colors: ['#ffc83d', '#ff7a3d'],
    image: '',
    alt: '',
  },
  {
    id: 'birthday-card',
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
    id: 'hassle',
    category: 'Getting out of a hassle',
    title: 'Skip the repairman call',
    line: 'Figure out the part, order it, and know when to call a professional instead.',
    prompt: 'My dishwasher stopped draining. Here is the model number. What are the likely causes, and which ones are safe for me to try?',
    payoff: 'One small part, one small fix. (Electrical, gas and air conditioning? Call a pro.)',
    colors: ['#ff9a3d', '#19c37d'],
    image: '',
    alt: '',
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
    const panel = el('section', 'moment');
    panel.id = story.id;
    panel.style.setProperty('--c1', story.colors[0]);
    panel.style.setProperty('--c2', story.colors[1]);

    if (story.image) {
      const img = el('img', 'moment__img');
      img.src = story.image;
      img.alt = story.alt || '';
      img.loading = i === 0 ? 'eager' : 'lazy';
      img.decoding = 'async';
      panel.appendChild(img);
    }

    const body = el('div', 'moment__body');
    body.appendChild(el('p', 'moment__cat', story.category));
    body.appendChild(el('h2', 'moment__title', story.title));
    body.appendChild(el('p', 'moment__line', story.line));

    const more = el('details', 'moment__more');
    more.appendChild(el('summary', '', 'See the exact prompt'));
    const inner = el('div', 'moment__more-body');
    inner.appendChild(el('p', 'moment__prompt', story.prompt));
    inner.appendChild(el('p', 'moment__payoff', story.payoff));
    more.appendChild(inner);
    body.appendChild(more);

    panel.appendChild(body);
    host.appendChild(panel);
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
      say('You’re on the list. We’ll be in touch soon.', 'ok');
    } catch (err) {
      const mailto = 'mailto:' + CONTACT_EMAIL + '?subject=' + encodeURIComponent('Register me for the clinic') +
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

document.addEventListener('DOMContentLoaded', () => {
  renderStories();
  initReveal();
  initRegister();
  initSignup();
});
