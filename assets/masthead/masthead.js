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

// Authored opportunity profiles for this private review draft. These are concept
// previews, not finished employer messages. The URL alone activates a profile.
(() => {
  const profiles = Object.freeze({
    nvidia: {
      label: 'A note for the NVIDIA team',
      title: 'A different way to introduce myself.',
      message: 'A short route through what I build, how I help people learn, and how I would approach useful change with your people.',
      links: [['Inspect something I built', '#built'], ['Meet the people side of the story', '#people-helped'], ['Picture a useful beginning', '#starting-here']]
    },
    school: {
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
    const owned = url.pathname === '/' || ['/work/launch-console/', '/thinking/', '/field-notes/'].some(prefix => url.pathname.startsWith(prefix));
    if (!owned) continue;
    url.search = '';
    url.searchParams.set('for', id);
    link.href = url.pathname + url.search + url.hash;
  }
})();
