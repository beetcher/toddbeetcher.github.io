// Playwright globalSetup — runs once before all tests when USE_ROUTER=1.
//
// 1. Starts a mock webhook server on port 3099 that auto-replies via the emulator,
//    enabling the auto-reply and incoming-message Playwright tests.
// 2. Pre-initializes the router state: triggers ensureSeeded (so seed_meta/init is
//    marked), then clears the routing table so tests start from a known empty state.
//    Without this, tests that open the Config Editor find the 3 seed entries instead
//    of an empty table.

const http = require('http');
const { URLSearchParams } = require('url');

const EMULATOR_URL = 'http://127.0.0.1:5001/test-phone-router/us-central1/router';
const MOCK_PORT = 3099;

module.exports = async function globalSetup() {
  // Start mock webhook that auto-replies via the emulator's /messages endpoint.
  const server = await new Promise((resolve) => {
    const s = http.createServer(async (req, res) => {
      if (req.method !== 'POST') {
        res.writeHead(405);
        res.end();
        return;
      }
      let body = '';
      req.on('data', chunk => { body += chunk; });
      req.on('end', async () => {
        const params = Object.fromEntries(new URLSearchParams(body));
        try {
          await fetch(`${EMULATOR_URL}/messages`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({
              From: params.To || '',
              To: params.From || '',
              Body: `[mock-reply] Got: ${params.Body || ''}`,
            }).toString(),
          });
        } catch (e) {
          console.error('[global-setup] Failed to send auto-reply:', e.message);
        }
        res.writeHead(200, { 'Content-Type': 'text/xml' });
        res.end('<Response></Response>');
      });
    });
    s.listen(MOCK_PORT, '127.0.0.1', () => resolve(s));
  });
  console.log(`[global-setup] Mock webhook listening on 127.0.0.1:${MOCK_PORT}`);

  // Pre-initialize router state:
  // GET /config triggers ensureSeeded (seeds 3 entries and marks seed_meta/init as seeded).
  // PUT /config [] then clears the routing table, leaving seed_meta set.
  // After this, any subsequent GET /config call returns [] without re-seeding.
  try {
    await fetch(`${EMULATOR_URL}/config`);
    await fetch(`${EMULATOR_URL}/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: '[]',
    });
    console.log('[global-setup] Router state initialized: seed_meta seeded, routing table empty');
  } catch (e) {
    console.warn('[global-setup] Could not initialize router state:', e.message);
  }

  return async function teardown() {
    await new Promise(resolve => server.close(resolve));
    console.log('[global-setup] Mock webhook stopped');
  };
};
