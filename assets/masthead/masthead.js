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
  if (!id) return;
  const profile = profiles[id];

  const baseResume = {state: 'placeholder', url: '/application/resume/'};
  const resume = profile.resume || baseResume;
  for (const link of document.querySelectorAll('[data-application-resume]')) {
    link.setAttribute('href', resume.url);
    link.textContent = resume.state === 'available' ? 'Read résumé' : 'Résumé — being prepared';
  }
  if (profile.audience === 'employer') {
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
    const dialog = document.getElementById('welcome-dialog');
    const openButton = document.getElementById('open-welcome');
    if (dialog && openButton && typeof dialog.showModal === 'function') {
      openButton.hidden = false;
      document.getElementById('welcome-audience').textContent = profile.label;
      const welcomeKey = `masthead-welcome-dismissed:${id}`;
      let nextFocus = openButton;
      let dismissed = false;
      try { dismissed = sessionStorage.getItem(welcomeKey) === 'true'; } catch { /* Optional storage. */ }
      function showWelcome() {
        if (dialog.open) return;
        nextFocus = document.activeElement instanceof HTMLElement && document.activeElement !== document.body ? document.activeElement : openButton;
        dialog.showModal();
        document.documentElement.classList.add('welcome-open');
        document.getElementById('close-welcome').focus({preventScroll: true});
      }
      function dismissWelcome(explore = false) {
        if (explore) nextFocus = document.getElementById('hero-title');
        try { sessionStorage.setItem(welcomeKey, 'true'); } catch { /* Optional storage. */ }
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
      dialog.addEventListener('close', () => {
        document.documentElement.classList.remove('welcome-open');
        try { sessionStorage.setItem(welcomeKey, 'true'); } catch { /* Optional storage. */ }
        if (nextFocus && nextFocus.isConnected) nextFocus.focus({preventScroll: true});
        if (nextFocus && nextFocus.id === 'hero-title') nextFocus.scrollIntoView({block: 'start'});
      });
      document.getElementById('close-welcome').addEventListener('click', () => dismissWelcome());
      document.getElementById('explore-welcome').addEventListener('click', () => dismissWelcome(true));
      for (const link of dialog.querySelectorAll('a[href]')) link.addEventListener('click', () => dismissWelcome());
      openButton.addEventListener('click', showWelcome);
      window.addEventListener('pagehide', () => { if (dialog.open) dialog.close(); });
      if (!dismissed) showWelcome();
    }
  }

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
