// coach/main.js: gentle reveal as each panel scrolls into view. Nothing else.
// The "I'm interested" pill is a plain mailto link in index.html, so it works without any script.
(function () {
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduce || !('IntersectionObserver' in window)) return;
  var targets = Array.prototype.slice.call(document.querySelectorAll('.panel, .hero__photo'));
  document.documentElement.classList.add('js');
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); }
    });
  }, { threshold: 0.12 });
  targets.forEach(function (t) { io.observe(t); });
  // Safety: never leave content hidden if the observer is slow.
  setTimeout(function () { targets.forEach(function (t) { t.classList.add('is-in'); }); }, 2500);
})();
