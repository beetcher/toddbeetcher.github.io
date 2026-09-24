// ============================================================
// SHARED CONFIGURATION — cert (RMAIIG × NOCTI)
// If you change anything above the PAGE-SPECIFIC line, update all 3 main.js files:
// cert/main.js
// cert/ai-ready-workforce/main.js
// cert/building-the-bridge/main.js
// ============================================================
const CERT_DOCS = [
  { slug: 'letter',              title: 'A National AI-Readiness Certification', shortTitle: 'Letter' },
  { slug: 'ai-ready-workforce',  title: 'Accelerating the AI-Ready Workforce',   shortTitle: 'Opportunity' },
  { slug: 'building-the-bridge', title: 'Building the AI-Readiness Bridge',      shortTitle: 'Bridge' },
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
// PAGE-SPECIFIC — the only line that differs between the 3 files
// ============================================================
CURRENT_DOC = 'ai-ready-workforce';

document.addEventListener('DOMContentLoaded', () => {
  recordVisit();
  updateState();
  initReadProgress();
  initCompletionDetection();
});

// Refresh dots when returning via the browser Back button (page restored from cache).
window.addEventListener('pageshow', e => { if (e.persisted) updateState(); });
