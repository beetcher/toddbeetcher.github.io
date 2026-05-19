// Update progress indicator based on which frame is closest to viewport center
function updateProgressIndicator() {
    const frames = document.querySelectorAll('.frame');
    if (frames.length === 0) return;

    const viewportCenter = window.innerHeight / 2;
    let closestFrame = null;
    let closestDistance = Infinity;

    frames.forEach(frame => {
        const rect = frame.getBoundingClientRect();
        const frameCenter = rect.top + rect.height / 2;
        const distance = Math.abs(frameCenter - viewportCenter);

        if (distance < closestDistance) {
            closestDistance = distance;
            closestFrame = frame;
        }
    });

    if (closestFrame) {
        const frameNumber = closestFrame.dataset.frame;
        const currentFrameElement = document.getElementById('current-frame');
        if (currentFrameElement && frameNumber) {
            currentFrameElement.textContent = frameNumber;
        }
    }
}

// Use requestAnimationFrame to throttle scroll updates
let scrollScheduled = false;
function scheduleProgressUpdate() {
    if (!scrollScheduled) {
        scrollScheduled = true;
        requestAnimationFrame(() => {
            updateProgressIndicator();
            scrollScheduled = false;
        });
    }
}

// Initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', updateProgressIndicator);
} else {
    updateProgressIndicator();
}

// Update progress on scroll
window.addEventListener('scroll', scheduleProgressUpdate, { passive: true });

// Update progress on resize
window.addEventListener('resize', updateProgressIndicator);
