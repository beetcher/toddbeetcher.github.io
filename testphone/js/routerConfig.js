// Single source of truth for the Router base URL.
// Auto-detects local development (localhost / 127.0.0.1) and routes to the
// Firebase emulator; uses the production Cloud Run URL otherwise.
//
// Emulator URL: http://127.0.0.1:5001/test-phone-router/us-central1/router
// Production URL: https://router-in7qh2jyoq-uc.a.run.app
const ROUTER_BASE_URL =
  (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'http://127.0.0.1:5001/test-phone-router/us-central1/router'
    : 'https://router-in7qh2jyoq-uc.a.run.app';
