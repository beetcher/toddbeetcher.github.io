// walk/main.js — reading progress bar

function initReadProgress() {
  const fill = document.querySelector('.read-progress__fill');
  if (!fill) return;
  let ticking = false;
  window.addEventListener('scroll', () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      const docHeight = document.body.scrollHeight - window.innerHeight;
      const pct = docHeight > 0 ? Math.min(100, (window.scrollY / docHeight) * 100) : 0;
      fill.style.width = pct + '%';
      ticking = false;
    });
  }, { passive: true });
}

document.addEventListener('DOMContentLoaded', initReadProgress);
