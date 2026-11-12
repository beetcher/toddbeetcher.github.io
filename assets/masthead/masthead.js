'use strict';
const copyButton = document.querySelector('.copy-email');
const status = document.getElementById('copy-status');
if (copyButton && navigator.clipboard && window.isSecureContext) {
  copyButton.hidden = false;
  copyButton.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText('toddbeetcher17@gmail.com');
      status.textContent = 'Email address copied.';
    } catch {
      status.textContent = 'Please select and copy the email address above.';
    }
  });
}

// The review-draft notice stays hidden. The first plain click on the tb. monogram reveals it once;
// later clicks and the triple-click letter reset keep their normal behavior.
const reviewBanner = document.querySelector('.review-banner');
document.querySelector('.site-header .brand .monogram')?.addEventListener('click', event => {
  if (!reviewBanner || !reviewBanner.hidden) return;
  if (event.detail > 1 || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  reviewBanner.hidden = false;
  window.scrollTo({top: 0, behavior: 'instant'});
});

// Authored opportunity profiles. Current messages and documents are review placeholders.
// The current URL alone activates a profile; dismissal does not retain identity.
(() => {
  const profiles = Object.freeze({
    nvidia: {
      audience: 'employer',
      resume: null,
      coverLetter: {state: 'placeholder', url: '/application/nvidia/cover-letter/'},
      label: 'A note for the NVIDIA team',
      title: 'A different way to introduce myself.',
      message: 'A short route through what I build, how I help people learn, and how I would approach useful change with your people.',
      links: [['Inspect something I built', '#built'], ['Meet the people side of the story', '#people-helped'], ['Picture a useful beginning', '#starting-here']]
    },
    school: {
      audience: 'education',
      label: 'A note for a learning community',
      title: 'What could your students and teachers do next?',
      message: 'Begin with mentoring, explore how I approach learning, and picture a supported first experience with AI. This is a sample route for an education conversation.',
      links: [['Start with mentoring', '#people-helped'], ['Explore the learning approach', '#becoming-capable'], ['Meet the person behind the work', '#the-person']]
    }
  });
  function selectedProfile() {
    const params = new URLSearchParams(location.search);
    const choices = [];
    let invalid = false;
    for (const [key, value] of params) {
      const normalized = key.toLowerCase();
      if (normalized === 'for') {
        const id = value.toLowerCase();
        if (Object.hasOwn(profiles, id)) choices.push(id);
        else invalid = true;
      } else if (Object.hasOwn(profiles, normalized)) {
        if (value !== '') invalid = true;
        else choices.push(normalized);
      }
    }
    return !invalid && choices.length === 1 ? choices[0] : null;
  }
  const id = selectedProfile();
  const profile = id ? profiles[id] : null;

  const baseResume = {state: 'placeholder', url: '/application/resume/'};
  const resume = profile?.resume || baseResume;
  for (const link of document.querySelectorAll('[data-application-resume]')) {
    link.setAttribute('href', resume.url);
    link.textContent = resume.state === 'available' ? 'Read résumé' : 'Résumé — being prepared';
  }
  if (profile?.audience === 'employer') {
    for (const link of document.querySelectorAll('[data-application-letter]')) {
      if (!profile.coverLetter) { link.hidden = true; continue; }
      link.hidden = false;
      link.setAttribute('href', profile.coverLetter.url);
      link.textContent = profile.coverLetter.state === 'available' ? 'Read cover letter' : 'Cover letter — being prepared';
    }
    const documentsPanel = document.getElementById('application-documents');
    if (documentsPanel) {
      documentsPanel.hidden = false;
      document.getElementById('application-audience').textContent = profile.label;
    }
  }
  const dialog = document.getElementById('welcome-dialog');
  const openButton = document.getElementById('open-welcome');
  if (dialog && openButton && typeof dialog.showModal === 'function') {
    openButton.hidden = false;
    const isEmployer = profile?.audience === 'employer';
    const defaultKind = isEmployer ? 'employer' : 'tour';
    let activeKind = defaultKind;
    let openingSource = null;
    const letterScroll = dialog.querySelector('.welcome-letter-scroll');
    const choices = document.getElementById('letter-choices');
    const floaters = [...document.querySelectorAll('[data-letter-floater]')];
    const letterNav = [...document.querySelectorAll('[data-letter-nav]')];
    const serviceKey = kind => `masthead-floater-serviced:${kind}-v1`;
    for (const floater of floaters) {
      try { floater.hidden = sessionStorage.getItem(serviceKey(floater.dataset.letterFloater)) === 'true'; } catch { /* Optional storage. */ }
    }
    if (choices) choices.hidden = false;
    for (const button of letterNav) button.hidden = false;
    function serviceFloater(kind) {
      const floater = floaters.find(item => item.dataset.letterFloater === kind);
      if (!floater) return;
      const hadFocus = floater.contains(document.activeElement);
      floater.hidden = true;
      try { sessionStorage.setItem(serviceKey(kind), 'true'); } catch { /* Optional storage. */ }
      const nav = letterNav.find(button => button.dataset.letterNav === kind);
      if (floater.contains(nextFocus)) nextFocus = nav || openButton;
      if (hadFocus) (nav || openButton).focus({preventScroll: true});
    }
    for (const button of document.querySelectorAll('[data-close-floater]')) {
      button.addEventListener('click', () => serviceFloater(button.dataset.closeFloater));
    }
    openButton.textContent = isEmployer ? 'Welcome & documents ↗' : 'Take a quick tour ↗';
    function selectLetter(kind) {
      activeKind = kind;
      const employer = kind === 'employer';
      const meet = kind === 'meet';
      document.getElementById('generic-welcome').hidden = kind !== 'tour';
      document.getElementById('employer-welcome').hidden = !employer;
      document.getElementById('meet-todd-letter').hidden = !meet;
      document.getElementById('welcome-document-links').hidden = !employer;
      document.getElementById('welcome-conversation').hidden = employer;
      document.getElementById('welcome-audience').textContent = employer ? profile.label : meet ? 'Meet Todd' : 'A letter from Todd';
      dialog.setAttribute('aria-labelledby', employer ? 'employer-welcome-title' : meet ? 'welcome-audience' : 'welcome-title');
      dialog.setAttribute('aria-describedby', employer ? 'employer-welcome-intro' : meet ? 'meet-todd-intro' : 'welcome-intro');
      letterScroll.setAttribute('aria-label', employer ? 'Employer welcome letter' : meet ? 'Meet Todd letter' : 'Quick tour letter');
    }
    const welcomeKey = `masthead-welcome-dismissed:${isEmployer ? id : 'general-letter-v1'}`;
    let nextFocus = openButton;
    let dismissed = false;
    try { dismissed = sessionStorage.getItem(welcomeKey) === 'true'; } catch { /* Optional storage. */ }
    let pagePosition = {left: 0, top: 0};
    function recordDismissal() {
      if (openingSource === 'floater') serviceFloater(activeKind);
      if (activeKind !== defaultKind) return;
      try { sessionStorage.setItem(welcomeKey, 'true'); } catch { /* Optional storage. */ }
    }
    function showWelcome(kind = defaultKind, source = 'navigation') {
      if (dialog.open) return;
      nextFocus = document.activeElement instanceof HTMLElement && document.activeElement !== document.body ? document.activeElement : openButton;
      pagePosition = {left: window.scrollX, top: window.scrollY};
      openingSource = source;
      selectLetter(kind);
      dialog.showModal();
      letterScroll.scrollTop = 0;
      document.documentElement.classList.add('welcome-open');
      document.getElementById('close-welcome').focus({preventScroll: true});
    }
    function dismissWelcome(explore = false) {
      if (explore) nextFocus = document.getElementById('hero-title');
      recordDismissal();
      if (dialog.open) dialog.close();
    }
    dialog.addEventListener('keydown', event => {
      if (event.key !== 'Tab') return;
      const stops = [...dialog.querySelectorAll('button:not([disabled]), a[href], [tabindex="0"]')].filter(element => element.getClientRects().length);
      const first = stops[0], last = stops[stops.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault(); first.focus();
      }
    });
    dialog.addEventListener('cancel', recordDismissal);
    dialog.addEventListener('close', () => {
      document.documentElement.classList.remove('welcome-open');
      recordDismissal();
      if (nextFocus && nextFocus.isConnected) nextFocus.focus({preventScroll: true});
      if (nextFocus && nextFocus.id === 'hero-title') nextFocus.scrollIntoView({block: 'start'});
      else window.scrollTo({...pagePosition, behavior: 'instant'});
    });
    document.getElementById('close-welcome').addEventListener('click', () => dismissWelcome());
    document.getElementById('explore-welcome').addEventListener('click', () => dismissWelcome(true));
    for (const link of dialog.querySelectorAll('a[href]')) link.addEventListener('click', () => dismissWelcome());
    openButton.addEventListener('click', () => showWelcome());
    document.getElementById('open-meet-todd')?.addEventListener('click', () => showWelcome('meet', 'floater'));
    document.getElementById('open-tour')?.addEventListener('click', () => showWelcome('tour', 'floater'));
    for (const button of letterNav) button.addEventListener('click', () => showWelcome(button.dataset.letterNav));
    dialog.addEventListener('click', event => {
      if (event.target !== dialog) return;
      const bounds = dialog.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dismissWelcome();
    });
    // Use the browser's multi-click timing; ordinary logo navigation stays intact.
    const headerLogo = document.querySelector('.site-header .brand .monogram');
    headerLogo?.addEventListener('click', event => {
      if (event.detail !== 3 || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      for (const floater of floaters) {
        try { sessionStorage.removeItem(serviceKey(floater.dataset.letterFloater)); } catch { /* Optional storage. */ }
        floater.hidden = false;
      }
      choices?.scrollIntoView({block: 'center', behavior: 'instant'});
    });
    window.addEventListener('pagehide', () => { if (dialog.open) dialog.close(); });
    if (isEmployer && !dismissed) showWelcome(defaultKind, 'personalized');
  }

  if (!id) return;

  const panel = document.getElementById('opportunity');
  const reopen = document.getElementById('opportunity-reopen');
  const reopenButton = document.getElementById('reopen-opportunity');
  const heading = document.getElementById('opportunity-title');
  const storageKey = `masthead-note-dismissed:${id}`;
  if (panel && reopen && reopenButton && heading) {
    document.getElementById('opportunity-label').textContent = profile.label;
    heading.textContent = profile.title;
    document.getElementById('opportunity-message').textContent = profile.message;
    const routes = document.getElementById('opportunity-routes');
    for (const [text, href] of profile.links) {
      const link = document.createElement('a');
      link.textContent = `${text} ↗`;
      link.href = href;
      routes.append(link);
    }
    let dismissed = false;
    try { dismissed = sessionStorage.getItem(storageKey) === 'true'; } catch { /* Storage is optional. */ }
    panel.hidden = dismissed;
    reopen.hidden = !dismissed;
    if ('IntersectionObserver' in window) {
      const entrance = new IntersectionObserver(entries => {
        if (entries.some(entry => entry.isIntersecting)) {
          panel.classList.add('is-in-view');
          entrance.disconnect();
        }
      }, {threshold: 0.12});
      entrance.observe(panel);
    } else {
      panel.classList.add('is-in-view');
    }
    function closeNote() {
      if (panel.hidden) return;
      panel.hidden = true;
      reopen.hidden = false;
      try { sessionStorage.setItem(storageKey, 'true'); } catch { /* Storage is optional. */ }
      reopenButton.focus({preventScroll: true});
    }
    document.getElementById('close-opportunity').addEventListener('click', closeNote);
    panel.addEventListener('keydown', event => {
      if (event.key === 'Escape') { closeNote(); event.preventDefault(); }
    });
    reopenButton.addEventListener('click', () => {
      panel.hidden = false;
      reopen.hidden = true;
      try { sessionStorage.removeItem(storageKey); } catch { /* Storage is optional. */ }
      heading.focus({preventScroll: true});
      panel.scrollIntoView({block: 'start'});
    });
    const surprise = document.getElementById('surprise-button');
    const note = document.getElementById('surprise-note');
    surprise.addEventListener('click', () => {
      note.hidden = !note.hidden;
      surprise.setAttribute('aria-expanded', String(!note.hidden));
    });
  }
  // Carry this recognized context through masthead-owned evidence pages only.
  // A generic homepage visit never reads a stale company identity from storage.
  for (const link of document.querySelectorAll('a[href]')) {
    const raw = link.getAttribute('href');
    if (!raw || raw.startsWith('#')) continue;
    const url = new URL(raw, location.href);
    if (url.origin !== location.origin) continue;
    const owned = url.pathname === '/' || ['/work/launch-console/', '/thinking/', '/field-notes/', '/application/'].some(prefix => url.pathname.startsWith(prefix));
    if (!owned) continue;
    url.search = '';
    url.searchParams.set('for', id);
    link.href = url.pathname + url.search + url.hash;
  }
})();
