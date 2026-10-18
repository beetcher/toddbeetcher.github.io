// coach/main.js: gentle reveal as panels scroll into view, and the "I'm interested" popup.
// The popup never opens an email app by itself. It shows the address, a copy button,
// a Gmail link, and a plain email-app link as a last option.
(function () {
  // ---- Contact popup ----
  var dlg = document.getElementById('contact');
  var status = document.getElementById('copy-status');
  var addr = document.getElementById('contact-addr');
  var ADDRESS = 'toddbeetcher17@gmail.com';

  function openContact() {
    if (status) status.textContent = '';
    if (dlg && typeof dlg.showModal === 'function') { if (!dlg.open) dlg.showModal(); }
    else if (dlg) { dlg.setAttribute('open', ''); }
  }
  function closeContact() { if (dlg && dlg.open) { if (dlg.close) dlg.close(); else dlg.removeAttribute('open'); } }
  Array.prototype.forEach.call(document.querySelectorAll('[data-open-contact]'), function (b) { b.addEventListener('click', openContact); });
  Array.prototype.forEach.call(document.querySelectorAll('[data-close-contact]'), function (b) { b.addEventListener('click', closeContact); });
  if (dlg) dlg.addEventListener('click', function (e) { if (e.target === dlg) closeContact(); });

  function selectAddress() {
    if (!addr || !window.getSelection) return;
    var r = document.createRange(); r.selectNodeContents(addr);
    var s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
  }
  var copyBtn = document.getElementById('copy-addr');
  if (copyBtn) copyBtn.addEventListener('click', function () {
    function done(ok) {
      if (ok) { status.textContent = 'Copied. Paste it into any email.'; }
      else { selectAddress(); status.textContent = 'Address selected. Press copy on your device.'; }
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(ADDRESS).then(function () { done(true); }, function () { done(false); });
    } else {
      selectAddress();
      var ok = false; try { ok = document.execCommand('copy'); } catch (e) {}
      done(ok);
    }
  });

  // ---- Reveal ----
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
