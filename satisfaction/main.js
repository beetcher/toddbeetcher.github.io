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

// PAGE-SPECIFIC — set per file (use let, not const, to allow assignment without redeclaration)
let CURRENT_DOC = null;   // null on root; set to slug on document pages
let DOC_VERSION = null;   // null on root; set to '1.0' on document pages

// ============================================================
// STORAGE UTILITIES
// ============================================================
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

// ============================================================
// CURRICULUM NAV DOTS
// ============================================================
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

// ============================================================
// READ PROGRESS BAR (document pages only)
// ============================================================
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

// ============================================================
// VISIT RECORDING (document pages only)
// ============================================================
function recordVisit() {
  if (!CURRENT_DOC) return;
  const progress = getOrInitProgress();
  progress.docs[CURRENT_DOC].visited = true;
  progress.docs[CURRENT_DOC].last_visit = new Date().toISOString();
  setProgress(progress);
}

// ============================================================
// COMPLETION DETECTION (document pages only)
// ============================================================
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

// ============================================================
// VERSION BANNER (document pages only)
// ============================================================
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
      // Hide changelog link if no #changelog element exists
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

// ============================================================
// ROOT PAGE — FIRST-TIME AND RETURNING VISITOR STATES
// ============================================================
function initRootPage() {
  if (CURRENT_DOC !== null) return;
  const progress = getProgress();
  if (!progress) return;

  let firstIncomplete = null;
  CURRICULUM.forEach(doc => {
    const item = document.querySelector('.curriculum-hub__item[data-slug="' + doc.slug + '"]');
    if (!item) return;
    const docData = progress.docs[doc.slug];
    if (!docData) return;
    if (docData.completed) {
      item.classList.add('--completed');
      const versionAttr = item.dataset.docVersion;
      if (versionAttr && docData.version_seen && docData.version_seen < versionAttr) {
        item.classList.add('--updated');
      }
    }
    if (!firstIncomplete && !docData.completed) {
      firstIncomplete = doc;
    }
  });

  const cta = document.querySelector('.curriculum-hub__cta');
  if (cta && firstIncomplete) {
    cta.textContent = 'Continue →';
    cta.href = firstIncomplete.slug + '/';
  } else if (cta && !firstIncomplete) {
    cta.textContent = 'Read again →';
    cta.href = 'the-full-essay/';
  }
}

// ============================================================
// EASTER EGG — click the "S" mark 3x quickly to reset your
// reading progress (root page only)
// ============================================================
function initProgressResetEgg() {
  if (CURRENT_DOC !== null) return;
  const mark = document.querySelector('.curriculum-nav__home-mark');
  if (!mark) return;
  let clicks = 0;
  let resetTimer = null;
  mark.addEventListener('click', () => {
    clicks++;
    clearTimeout(resetTimer);
    resetTimer = setTimeout(() => { clicks = 0; }, 2000);
    if (clicks >= 3) {
      clicks = 0;
      localStorage.removeItem(STORAGE_KEY);
      sessionStorage.clear();
      console.log('%cProgress cleared.', 'color:#1e4c8a;font-weight:bold;font-family:sans-serif;');
      location.reload();
    }
  });
}

// ============================================================
// INIT
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
  updateNavDots();
  initReadProgress();
  initVersionBanner();
  recordVisit();
  initCompletionDetection();
  initRootPage();
  initProgressResetEgg();
});
