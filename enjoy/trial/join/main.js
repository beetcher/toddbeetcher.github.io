// enjoy/trial/join/main.js: the trial sign-up page (no Doc peeker here, on purpose).
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

document.addEventListener('DOMContentLoaded', () => {
  document.documentElement.classList.add('js');
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
