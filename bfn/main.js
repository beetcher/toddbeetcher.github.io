document.addEventListener('DOMContentLoaded', () => {
  const counters = document.querySelectorAll('.stat-num[data-target]');
  if (!counters.length) return;

  function runCounter(el) {
    const target = parseInt(el.dataset.target, 10);
    const duration = 1800;
    const start = performance.now();

    function tick(now) {
      const elapsed = now - start;
      const t = Math.min(elapsed / duration, 1);
      const ease = 1 - Math.pow(1 - t, 3);
      const value = Math.round(target * ease);
      el.textContent = value >= 1000 ? value.toLocaleString() : String(value);
      if (t < 1) requestAnimationFrame(tick);
    }

    requestAnimationFrame(tick);
  }

  const proofBar = document.querySelector('.proof-bar');
  if (!proofBar) return;

  const observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting) {
      counters.forEach(runCounter);
      observer.disconnect();
    }
  }, { threshold: 0.3 });

  observer.observe(proofBar);
});
