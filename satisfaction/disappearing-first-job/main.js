// ============================================================
// SHARED CONFIGURATION — satisfaction curriculum
// If you change anything in this block, update all 5 main.js files:
// satisfaction/main.js
// satisfaction/the-full-essay/main.js
// satisfaction/why-nobody-fixed-it/main.js
// satisfaction/disappearing-first-job/main.js
// satisfaction/tractor-and-algorithm/main.js
// ============================================================
const CURRICULUM = [
  { slug: 'the-full-essay',         title: 'Are We Automating Away Our Children\'s Path to Satisfying Lives?', shortTitle: 'Essay' },
  { slug: 'why-nobody-fixed-it',    title: 'Why Nobody Fixed It',               shortTitle: 'Diagnostic' },
  { slug: 'disappearing-first-job', title: 'The Disappearing First Job',         shortTitle: 'Ledger' },
  { slug: 'tractor-and-algorithm',  title: 'The Tractor and the Algorithm',      shortTitle: 'Parallel' },
];
const STORAGE_KEY = 'satisfaction';
// ============================================================

let CURRENT_DOC = null;
let DOC_VERSION = null;

CURRENT_DOC = 'disappearing-first-job';
DOC_VERSION = '1.0';

function getProgress() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (e) {
    return null;
  }
}

function setProgress(data) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch (e) { /* silent */ }
}

function getOrInitProgress() {
  const existing = getProgress();
  if (existing) return existing;
  const fresh = { schema_version: 1, docs: {} };
  CURRICULUM.forEach(doc => {
    fresh.docs[doc.slug] = {
      visited: false,
      completed: false,
      version_seen: null,
      last_visit: null
    };
  });
  return fresh;
}

function updateNavDots() {
  const progress = getProgress();
  const dots = document.querySelectorAll('.curriculum-nav__doc');
  dots.forEach(dotEl => {
    const slug = dotEl.dataset.slug;
    dotEl.classList.remove('--completed', '--current', '--visited');
    if (slug === CURRENT_DOC) dotEl.classList.add('--current');
    if (progress && progress.docs[slug]) {
      const doc = progress.docs[slug];
      if (doc.completed) dotEl.classList.add('--completed');
      else if (doc.visited) dotEl.classList.add('--visited');
    }
  });
}

function initReadProgress() {
  if (!CURRENT_DOC) return;
  const fill = document.querySelector('.read-progress__fill');
  if (!fill) return;
  let ticking = false;
  window.addEventListener('scroll', () => {
    if (!ticking) {
      requestAnimationFrame(() => {
        const scrollTop = window.scrollY;
        const docHeight = document.body.scrollHeight - window.innerHeight;
        const pct = docHeight > 0 ? Math.min(100, (scrollTop / docHeight) * 100) : 0;
        fill.style.width = pct + '%';
        ticking = false;
      });
      ticking = true;
    }
  });
}

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
    progress.docs[CURRENT_DOC].version_seen = DOC_VERSION;
    setProgress(progress);
  }
  updateNavDots();
}

function initCompletionDetection() {
  if (!CURRENT_DOC) return;
  const endNav = document.querySelector('.doc-end-nav');
  if (!endNav) return;
  let dwellTimer = null;
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        dwellTimer = setTimeout(() => markCompleted(), 5000);
      } else {
        if (dwellTimer) clearTimeout(dwellTimer);
      }
    });
  }, { threshold: 0.5 });
  observer.observe(endNav);
}

function initVersionBanner() {
  if (!CURRENT_DOC || !DOC_VERSION) return;
  const progress = getProgress();
  if (!progress) return;
  const doc = progress.docs[CURRENT_DOC];
  if (!doc || !doc.completed) return;
  const dismissed = sessionStorage.getItem('version_dismissed_' + CURRENT_DOC);
  if (dismissed) return;
  if (doc.version_seen && doc.version_seen < DOC_VERSION) {
    const banner = document.querySelector('.version-banner');
    if (banner) {
      banner.style.display = 'flex';
      const changelogLink = banner.querySelector('.version-banner__link');
      if (changelogLink && !document.getElementById('changelog')) {
        changelogLink.style.display = 'none';
      }
      banner.querySelector('.version-banner__dismiss').addEventListener('click', () => {
        banner.style.display = 'none';
        sessionStorage.setItem('version_dismissed_' + CURRENT_DOC, '1');
      });
    }
  }
}

function initRootPage() {
  if (CURRENT_DOC !== null) return;
}

document.addEventListener('DOMContentLoaded', () => {
  updateNavDots();
  initReadProgress();
  initVersionBanner();
  recordVisit();
  initCompletionDetection();
  initRootPage();
});
