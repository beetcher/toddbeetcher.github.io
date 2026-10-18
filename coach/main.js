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
  function copyText(text, onDone) {
    function fallback() {
      var ok = false;
      try {
        var ta = document.createElement('textarea'); ta.value = text; ta.setAttribute('readonly', '');
        ta.style.position = 'fixed'; ta.style.opacity = '0'; document.body.appendChild(ta); ta.select();
        ok = document.execCommand('copy'); document.body.removeChild(ta);
      } catch (e) {}
      onDone(ok);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { onDone(true); }, fallback);
    } else { fallback(); }
  }
  var copyBtn = document.getElementById('copy-addr');
  if (copyBtn) copyBtn.addEventListener('click', function () {
    copyText(ADDRESS, function (ok) {
      if (ok) { status.textContent = 'Copied. Paste it into any email.'; }
      else { selectAddress(); status.textContent = 'Address selected. Press copy on your device.'; }
    });
  });

  var NOTE = "Hi Todd,\n\nI'm interested. (Or: I'd like to introduce someone.)\n\nA little about me (or them):\n\nWhat I might like to build:\n";
  var noteBtn = document.getElementById('copy-note');
  if (noteBtn) noteBtn.addEventListener('click', function () {
    copyText(NOTE, function (ok) {
      status.textContent = ok ? 'Copied. Paste it into an email to ' + ADDRESS + '.' : 'Could not copy here. Just write a few lines about you and what you might build.';
    });
  });

  // ---- Share this page ----
  function pageUrl() {
    var c = document.querySelector('link[rel="canonical"]');
    return (c && c.href) || location.href;
  }
  Array.prototype.forEach.call(document.querySelectorAll('[data-share]'), function (b) {
    b.addEventListener('click', function () {
      var inDialog = !!b.closest('dialog');
      var out = inDialog ? status : document.getElementById('share-status');
      var data = { title: 'Learn to build software with AI', text: 'Do you know anyone who\u2019d like to learn to build software with AI? Todd Beetcher is offering free coaching.', url: pageUrl() };
      function say(m) { if (out) out.textContent = m; }
      if (navigator.share) {
        navigator.share(data).catch(function () {});
      } else {
        copyText(pageUrl(), function (ok) { say(ok ? 'Link copied. Paste it into a text or email.' : 'Copy this link: ' + pageUrl()); });
      }
    });
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
