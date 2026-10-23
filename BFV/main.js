const panels = [...document.querySelectorAll('.panel')];
const previous = document.querySelector('#previous');
const next = document.querySelector('#next');
const position = document.querySelector('#position');
const bar = document.querySelector('.progress');
let current = 0;
function update() {
  let best = Infinity;
  panels.forEach((panel, index) => {
    const distance = Math.abs(panel.getBoundingClientRect().top - 65);
    if (distance < best) { best = distance; current = index; }
  });
  previous.disabled = current === 0;
  next.disabled = current === panels.length - 1;
  position.value = `${String(current + 1).padStart(2, '0')} / ${panels.length}`;
  bar.style.width = `${(current + 1) / panels.length * 100}%`;
}
function go(index) {
  const panel = panels[Math.max(0, Math.min(panels.length - 1, index))];
  history.replaceState(null, '', '#' + panel.id);
  panel.scrollIntoView({block: 'start'});
  panel.focus({preventScroll: true});
}
previous.addEventListener('click', () => go(current - 1));
next.addEventListener('click', () => go(current + 1));
let ticking = false;
window.addEventListener('scroll', () => {if (!ticking) {requestAnimationFrame(() => {update(); ticking = false;}); ticking = true;}}, {passive: true});
window.addEventListener('resize', update);
document.addEventListener('keydown', event => {
  if (document.querySelector('dialog[open]') || /INPUT|TEXTAREA|SELECT|BUTTON|SUMMARY|A/.test(event.target.tagName) || event.altKey || event.metaKey || event.ctrlKey) return;
  if (event.key === 'ArrowRight') {event.preventDefault(); go(current + 1);}
  if (event.key === 'ArrowLeft') {event.preventDefault(); go(current - 1);}
});
const picture = document.querySelector('#picture');
document.querySelectorAll('[data-picture]').forEach(button => button.addEventListener('click', () => {
  const img = picture.querySelector('img');
  img.src = button.dataset.picture;
  img.alt = button.querySelector('img').alt;
  picture.querySelector('a').href = button.dataset.picture;
  picture.querySelector('p').textContent = button.dataset.caption || 'Original illustration. Pinch to zoom on your device.';
  picture.showModal();
}));
document.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
document.querySelector('#open-contents').addEventListener('click', () => document.querySelector('#contents').showModal());
document.querySelectorAll('#contents a').forEach(link => link.addEventListener('click', () => document.querySelector('#contents').close()));
document.querySelectorAll('dialog').forEach(dialog => dialog.addEventListener('click', event => {if (event.target === dialog && (event.clientX < dialog.getBoundingClientRect().left || event.clientX > dialog.getBoundingClientRect().right || event.clientY < dialog.getBoundingClientRect().top || event.clientY > dialog.getBoundingClientRect().bottom)) dialog.close();}));
update();
