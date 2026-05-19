// Scroll reveal
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('visible');
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.12 });

document.querySelectorAll('.reveal').forEach(el => observer.observe(el));

// Mission audio setup
let missionAudioUnlocked = false;
let missionTypeSound = null;
let missionTypewriterTimeouts = [];

function initMissionAudio() {
  if (missionTypeSound) return;
  try {
    missionTypeSound = new Audio('assets/type.mp3');
    missionTypeSound.volume = 0.2;
    missionTypeSound.load();
  } catch (e) {
    // Silent fail if audio unavailable
  }
}

function clearMissionTypewriterTimeouts() {
  missionTypewriterTimeouts.forEach(id => clearTimeout(id));
  missionTypewriterTimeouts = [];
}

function unlockMissionAudio() {
  if (missionAudioUnlocked) return;
  missionAudioUnlocked = true;
  if (!missionTypeSound) initMissionAudio();

  // Restart typewriter to play sounds during typing
  const typewriterEl = document.getElementById('mission-typewriter');
  if (typewriterEl) {
    clearMissionTypewriterTimeouts();
    typewriterEl.textContent = '';
    restartMissionTypewriter();
  }
}

// Unlock audio on first click anywhere on page
document.addEventListener('click', unlockMissionAudio, { once: false });

// Mission typewriter
const missionMessage = `MISSION: GET THE KIDS TO HIGH-ALTITUDE MOUNTAIN CAMP.

SUMMER 2025 — ONE ROUTE. ONE BUS. NO MARGIN FOR ERROR.

SHOULD YOU CHOOSE TO ACCEPT THIS MISSION...`;
const typingSpeed = 45; // ms per character
const initialDelay = 750; // ms before first run
const holdDuration = 10000; // ms to hold completed text
const betweenDelay = 750; // ms between cycles

function startMissionTyping() {
  const typewriterEl = document.getElementById('mission-typewriter');
  if (!typewriterEl) return;

  let charIndex = 0;
  let nonSpaceCount = 0;

  function typeChar() {
    if (charIndex < missionMessage.length) {
      const currentChar = missionMessage[charIndex];
      typewriterEl.textContent += currentChar;

      // Play sound for non-space, non-newline characters
      if (missionAudioUnlocked && missionTypeSound && currentChar !== ' ' && currentChar !== '\n') {
        nonSpaceCount++;
        // Play sound every 3 non-space characters
        if (nonSpaceCount % 3 === 0) {
          const tick = missionTypeSound.cloneNode();
          tick.volume = 0.2;
          tick.play().catch(() => {});
        }
      }

      charIndex++;
      const timeoutId = setTimeout(typeChar, typingSpeed);
      missionTypewriterTimeouts.push(timeoutId);
    } else {
      // Hold completed text, then clear and replay
      const holdTimeoutId = setTimeout(() => {
        typewriterEl.textContent = '';
        const replayTimeoutId = setTimeout(startMissionTyping, betweenDelay);
        missionTypewriterTimeouts.push(replayTimeoutId);
      }, holdDuration);
      missionTypewriterTimeouts.push(holdTimeoutId);
    }
  }

  typeChar();
}

function restartMissionTypewriter() {
  startMissionTyping();
}

function initMissionTypewriter() {
  if (window.__missionInitialized) return;
  window.__missionInitialized = true;

  const typewriterEl = document.getElementById('mission-typewriter');
  if (!typewriterEl) return;

  // Start typewriter after initial delay
  const initialTimeoutId = setTimeout(startMissionTyping, initialDelay);
  missionTypewriterTimeouts.push(initialTimeoutId);

  // Also unlock audio on ACCEPT MISSION click
  const acceptBtn = document.querySelector('.mission-accept-button');
  if (acceptBtn) {
    acceptBtn.addEventListener('click', unlockMissionAudio);
  }
}

// Initialize immediately (script is defer-loaded, DOM is ready)
initMissionTypewriter();
