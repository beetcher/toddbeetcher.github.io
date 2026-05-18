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
