// enjoy/trial/join/main.js: the trial sign-up page (no Doc peeker here, on purpose).
// The plane sends people here with ?letter, which opens Todd's letter over this page (see initLetter below).
// Saves to the same Firestore collection as Register, tagged source: 'trial'.
// If the save fails, it falls back to an email link so nobody is lost.
// Firebase web config (same project as enjoy/main.js; these are public web keys, not secrets).
const FIREBASE_CONFIG = {
  apiKey: 'AIzaSyDM6TE1NpirV-jwLy1wTAU7C-Id9-aXFxI',
  authDomain: 'test-phone-router.firebaseapp.com',
  projectId: 'test-phone-router',
  appId: '1:112367027974:web:e37d5a51a547ae443d4087',
};
const SIGNUPS_COLLECTION = 'enjoy_signups';
const FIREBASE_SDK = 'https://www.gstatic.com/firebasejs/10.14.1/';
const CONTACT_EMAIL = 'toddbeetcher17@gmail.com';

async function saveTrial(data) {
  const [appMod, fsMod] = await Promise.all([
    import(FIREBASE_SDK + 'firebase-app.js'),
    import(FIREBASE_SDK + 'firebase-firestore.js'),
  ]);
  const app = appMod.getApps().length ? appMod.getApp() : appMod.initializeApp(FIREBASE_CONFIG);
  const db = fsMod.getFirestore(app);
  await fsMod.addDoc(fsMod.collection(db, SIGNUPS_COLLECTION), {
    name: data.name,
    email: data.email,
    phone: data.phone,
    contact: data.contact,       // 'phone' | 'email' | 'both'
    usedBefore: data.used,       // 'never' | 'stuck' | 'sometimes' | ''
    friends: data.friends,
    source: 'trial',
    createdAt: fsMod.serverTimestamp(),
  });
}

// ---- Letter overlay: shown when someone arrives from the plane (trial/join/?letter). ----
// Same letter and same behavior as initTrialLetter() in enjoy/main.js. KEEP THE LETTER TEXT IN SYNC WITH THAT FILE (two copies).
// On this page: "Join the free trial" washes the letter away and scrolls to the sign-up form; "Tell me more" washes it away and
// leaves the reader at the top of this page. Esc does the same as "Tell me more". Reload or a direct visit shows no letter.
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

function mk(tag, className, text) {
  const n = document.createElement(tag);
  if (className) n.className = className;
  if (text) n.textContent = text;
  return n;
}

function initLetter() {
  if (!/[?&]letter(=|&|$)/.test(location.search)) return;
  const dlg = mk('dialog', 'trial-letter');
  dlg.setAttribute('aria-label', 'A note from Todd');
  const card = mk('div', 'trial-letter__card');
  card.tabIndex = -1;
  TRIAL_LETTER.forEach((t) => {
    const p = mk('p');
    p.innerHTML = t.replace(/\{term\}/g, '<span class="term">Zero State</span>');
    card.appendChild(p);
  });
  card.appendChild(mk('p', 'trial-letter__sign', 'Todd'));
  const bar = mk('div', 'trial-letter__bar');
  const join = mk('button', 'btn btn--hero', 'Join the free trial');
  join.type = 'button';
  const more = mk('button', 'btn btn--ghost', 'Tell me more');
  more.type = 'button';
  bar.appendChild(join);
  bar.appendChild(more);
  dlg.appendChild(card);
  dlg.appendChild(bar);
  document.body.appendChild(dlg);

  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let leaving = false;
  const dismiss = (toForm) => {
    if (leaving) return;
    leaving = true;
    try { history.replaceState(null, '', location.pathname + location.hash); } catch (e) { /* fine */ }
    const finish = () => {
      dlg.close();
      dlg.remove();
      if (toForm) {
        const form = document.getElementById('trial-form');
        if (form) form.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
      }
    };
    if (reduce) { finish(); return; }
    dlg.classList.add('is-leaving');
    setTimeout(finish, 700);
  };
  join.addEventListener('click', () => dismiss(true));
  more.addEventListener('click', () => dismiss(false));
  dlg.addEventListener('cancel', (e) => { e.preventDefault(); dismiss(false); });
  if (typeof dlg.showModal === 'function') dlg.showModal(); else dlg.setAttribute('open', '');
  card.focus({ preventScroll: true });
}

document.addEventListener('DOMContentLoaded', () => {
  document.documentElement.classList.add('js');
  initLetter();
  const form = document.getElementById('trial-form');
  const done = document.getElementById('trial-done');
  const status = document.getElementById('trial-status');
  const btn = document.getElementById('trial-submit');
  if (!form) return;
  const say = (msg, kind) => { status.textContent = msg; status.dataset.kind = kind || ''; };

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    if (fd.get('website')) return; // honeypot
    const name = String(fd.get('name') || '').trim();
    const email = String(fd.get('email') || '').trim();
    const phone = String(fd.get('phone') || '').trim();
    const used = String(fd.get('used') || '');
    const friends = String(fd.get('friends') || '').trim();
    const goodEmail = /^\S+@\S+\.\S+$/.test(email);
    const goodPhone = phone.replace(/\D/g, '').length >= 7;

    if (!name) { say('Please add your name.', 'error'); return; }
    if (!email && !phone) { say('Please leave a phone number or an email, whichever is easiest for you.', 'error'); return; }
    if (email && !goodEmail) { say('That email doesn\u2019t look right. Please check it, or leave just a phone number.', 'error'); return; }
    if (phone && !goodPhone) { say('That phone number looks short. Please check it, or leave just an email.', 'error'); return; }
    const contact = email && phone ? 'both' : (phone ? 'phone' : 'email');

    btn.disabled = true;
    say('Saving\u2026', '');
    try {
      await saveTrial({ name, email, phone, contact, used, friends });
      form.hidden = true;
      done.hidden = false;
      done.focus();
    } catch (err) {
      const mailto = 'mailto:' + CONTACT_EMAIL + '?subject=' + encodeURIComponent('Count me in: the free trial') +
        '&body=' + encodeURIComponent('Name: ' + name + '\nEmail: ' + email + '\nPhone: ' + phone + '\nUsed AI before: ' + used + '\nFriends: ' + friends);
      status.textContent = '';
      status.dataset.kind = 'error';
      status.appendChild(document.createTextNode('We couldn\u2019t save that just now. '));
      const a = document.createElement('a');
      a.href = mailto;
      a.textContent = 'Email me instead';
      status.appendChild(a);
      status.appendChild(document.createTextNode('.'));
    } finally {
      btn.disabled = false;
    }
  });
});
