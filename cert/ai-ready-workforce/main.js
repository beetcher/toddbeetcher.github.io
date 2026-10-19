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
// PAGE-SPECIFIC — the only line that differs between the 3 files
// ============================================================
CURRENT_DOC = 'ai-ready-workforce';

document.addEventListener('DOMContentLoaded', () => {
  recordVisit();
  updateState();
  initReadProgress();
  initCompletionDetection();
  initContact();
});

// Refresh dots when returning via the browser Back button (page restored from cache).
window.addEventListener('pageshow', e => { if (e.persisted) updateState(); });
