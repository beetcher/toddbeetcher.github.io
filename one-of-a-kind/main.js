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

// Mission typewriter
function initMissionTypewriter() {
  if (window.__missionInitialized) return;
  window.__missionInitialized = true;

  const typewriterEl = document.getElementById('mission-typewriter');
  if (!typewriterEl) return;

  const missionMessage = `MISSION: GET THE KIDS TO HIGH-ALTITUDE MOUNTAIN CAMP.

SUMMER 2025 — ONE ROUTE. ONE BUS. NO MARGIN FOR ERROR.

SHOULD YOU CHOOSE TO ACCEPT THIS MISSION...`;

  const typingSpeed = 45; // ms per character
  const initialDelay = 750; // ms before first run
  const holdDuration = 10000; // ms to hold completed text
  const betweenDelay = 750; // ms between cycles

  function typeMessage() {
    let charIndex = 0;

    function typeChar() {
      if (charIndex < missionMessage.length) {
        typewriterEl.textContent += missionMessage[charIndex];
        charIndex++;
        setTimeout(typeChar, typingSpeed);
      } else {
        // Hold completed text
        setTimeout(clearAndReplay, holdDuration);
      }
    }

    typeChar();
  }

  function clearAndReplay() {
    typewriterEl.textContent = '';
    setTimeout(typeMessage, betweenDelay);
  }

  // Start typewriter after initial delay
  setTimeout(typeMessage, initialDelay);
}

// Initialize immediately (script is defer-loaded, DOM is ready)
initMissionTypewriter();
