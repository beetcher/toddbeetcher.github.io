const chapters = [...document.querySelectorAll('.chapter')];
const names = ['The thesis','Two engines','The production unlock','The two clocks','The commercial bridge','The venture system','What could endure','The next decisions'];
const previous = document.querySelector('#previous');
const next = document.querySelector('#next-chapter');
let current = 0;
function updateProgress() {
  let nearest = Infinity;
  chapters.forEach((chapter, index) => {
    const distance = Math.abs(chapter.getBoundingClientRect().top - 80);
    if (distance < nearest) {nearest = distance; current = index;}
  });
  document.querySelector('#chapter-count').value = `${String(current + 1).padStart(2,'0')} / 08`;
  document.querySelector('#chapter-name').textContent = names[current];
  document.querySelector('.reading-progress span').style.width = `${(current + 1) / chapters.length * 100}%`;
  previous.disabled = current === 0;
  next.disabled = current === chapters.length - 1;
}
function navigate(index) {
  const chapter = chapters[Math.max(0,Math.min(chapters.length - 1,index))];
  history.replaceState(null,'','#' + chapter.id);
  chapter.scrollIntoView({block:'start'});
  chapter.focus({preventScroll:true});
}
previous.addEventListener('click',() => navigate(current - 1));
next.addEventListener('click',() => navigate(current + 1));
let scheduled = false;
window.addEventListener('scroll',() => {
  if (!scheduled) {requestAnimationFrame(() => {updateProgress(); scheduled = false;}); scheduled = true;}
},{passive:true});
window.addEventListener('resize',updateProgress);
document.addEventListener('keydown',event => {
  if (document.querySelector('dialog[open]') || event.altKey || event.ctrlKey || event.metaKey || event.target.closest('a,button,input,textarea,select,summary,[role=tab]')) return;
  if (event.key === 'ArrowRight') {event.preventDefault();navigate(current + 1);}
  if (event.key === 'ArrowLeft') {event.preventDefault();navigate(current - 1);}
});
const storyMap = document.querySelector('#story-map');
document.querySelector('#open-map').addEventListener('click',() => storyMap.showModal());
document.querySelectorAll('#story-map a').forEach(link => link.addEventListener('click',() => storyMap.close()));
const art = document.querySelector('#art-view');
document.querySelectorAll('[data-art]').forEach(button => button.addEventListener('click',() => {
  const image = art.querySelector('img');
  image.src = button.dataset.art;
  image.alt = button.querySelector('img').alt;
  art.querySelector('a').href = button.dataset.art;
  art.showModal();
}));
const stages = [
  {title:'The code is finished.\nThe waiting isn’t.',copy:'Give one programmer a tool with today’s AI coding capabilities. He completes an assignment in minutes. Reviews, integration, testing, and release still run on human time.',takeaway:'One person accelerates. The system still sets the pace.',alt:'Imagined intern completes his code quickly while the surrounding organization remains on human time.'},
  {title:'Everyone gets faster.\nProjects still wait.',copy:'Give the tool to every programmer. Code generation accelerates across the company, but coordination, dependencies, integration, testing, and approvals remain constraints.',takeaway:'Scaling coding tools does not automatically transform production.',alt:'Imagined IBM programmers all receive the coding tool, yet project delivery is constrained by the unchanged organization.'},
  {title:'Change the factory.\nMove more execution to machine time.',copy:'Apply AI-native orchestration across workflows, dependencies, integration, testing, correction, and release preparation. People retain product direction, quality standards, risk decisions, and governance.',takeaway:'The economic unlock is a production system that can keep up.',alt:'Comparison of human-coordinated production with an AI-native factory that automates more execution while preserving human direction.'}
];
const tabs = [...document.querySelectorAll('[data-stage]')];
function selectStage(index,focus = false) {
  const stage = stages[index];
  tabs.forEach((tab,i) => {tab.setAttribute('aria-selected',String(i === index));tab.tabIndex = i === index ? 0 : -1;});
  document.querySelector('#stage-title').textContent = stage.title;
  document.querySelector('#stage-title').style.whiteSpace = 'pre-line';
  document.querySelector('#stage-copy').textContent = stage.copy;
  document.querySelector('#stage-takeaway').textContent = stage.takeaway;
  document.querySelector('#stage-panel').setAttribute('aria-labelledby',tabs[index].id);
  const image = document.querySelector('#stage-image');
  image.src = `assets/ibm-${index + 1}.png`;
  image.alt = stage.alt;
  document.querySelector('#stage-art').dataset.art = image.getAttribute('src');
  if (focus) tabs[index].focus();
}
tabs.forEach((tab,index) => {
  tab.addEventListener('click',() => selectStage(index));
  tab.addEventListener('keydown',event => {
    let target;
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') target = (index + 1) % tabs.length;
    if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') target = (index + tabs.length - 1) % tabs.length;
    if (event.key === 'Home') target = 0;
    if (event.key === 'End') target = tabs.length - 1;
    if (target !== undefined) {event.preventDefault();selectStage(target,true);}
  });
});
updateProgress();
