// Single source of truth for the Router base URL.
// Update this constant when:
//   - Deploying to a new Firebase project
//   - Fronting with a Cloudflare Worker or other proxy
//   - Switching from local emulator to production
//
// Emulator (local dev):
//   http://127.0.0.1:5001/test-phone-router/us-central1/router
//
// Production (set after first deploy — firebase deploy outputs the URL):
//   https://router-<hash>-uc.a.run.app
const ROUTER_BASE_URL = 'https://router-in7qh2jyoq-uc.a.run.app';
