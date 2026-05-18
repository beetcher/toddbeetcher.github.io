const playBtn = document.querySelector('.play-btn');
const lightbox = document.getElementById('lightbox');
const lightboxVideo = document.getElementById('lightbox-video');
const closeBtn = document.querySelector('.lightbox-close');

function openLightbox() {
  lightbox.classList.add('open');
  lightboxVideo.play();
}

function closeLightbox() {
  lightbox.classList.remove('open');
  lightboxVideo.pause();
  lightboxVideo.currentTime = 0;
}

playBtn.addEventListener('click', openLightbox);
closeBtn.addEventListener('click', closeLightbox);

lightbox.addEventListener('click', (e) => {
  if (e.target === lightbox) closeLightbox();
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeLightbox();
    closeImgLightbox();
  }
});

// ── IMAGE LIGHTBOX ──
const imgLightbox = document.getElementById('img-lightbox');
const imgLightboxInner = document.getElementById('img-lightbox-inner');
const imgLightboxImg = document.getElementById('img-lightbox-img');
const imgLightboxCaption = document.getElementById('img-lightbox-caption');

function openImgLightbox(src, caption) {
  imgLightboxImg.src = src;
  imgLightboxCaption.textContent = caption;
  imgLightbox.classList.add('open');
}

function closeImgLightbox() {
  imgLightbox.classList.remove('open');
  imgLightboxImg.src = '';
  imgLightboxCaption.textContent = '';
}

document.querySelectorAll('.wheel-thumb').forEach((thumb) => {
  thumb.addEventListener('click', () => {
    openImgLightbox(thumb.dataset.src, thumb.dataset.caption);
  });
});

imgLightbox.addEventListener('click', (e) => {
  if (!imgLightboxInner.contains(e.target)) closeImgLightbox();
});

// ── LAYER 3 VIDEO LIGHTBOX ──
const l3VideoBtn = document.querySelector('.l3-video-btn');
const l3Lightbox = document.getElementById('l3-lightbox');
const l3LightboxVideo = document.getElementById('l3-lightbox-video');
const l3CloseBtn = l3Lightbox.querySelector('.lightbox-close');

function openL3Lightbox() {
  l3Lightbox.classList.add('open');
  l3LightboxVideo.play();
}

function closeL3Lightbox() {
  l3Lightbox.classList.remove('open');
  l3LightboxVideo.pause();
  l3LightboxVideo.currentTime = 0;
}

l3VideoBtn.addEventListener('click', (e) => {
  e.preventDefault();
  openL3Lightbox();
});
l3CloseBtn.addEventListener('click', closeL3Lightbox);

l3Lightbox.addEventListener('click', (e) => {
  if (e.target === l3Lightbox) closeL3Lightbox();
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && l3Lightbox.classList.contains('open')) {
    closeL3Lightbox();
  }
});
