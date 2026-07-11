const { defineConfig } = require('@playwright/test');

// Set USE_ROUTER=1 to run tests against the live Fake Twilio Router (Firebase Emulator).
// The emulator must already be running: cd router && npm run serve
// Without USE_ROUTER, router.spec.js is excluded and the four original specs run in
// mock-only mode (routerClient calls will fail gracefully but router-dependent tests
// will skip or show network-error behavior).
const useRouter = !!process.env.USE_ROUTER;

module.exports = defineConfig({
  testDir: './tests',
  testIgnore: useRouter ? [] : ['**/router.spec.js'],
  // Sequential — tests share a browser context and must not race on localStorage
  workers: 1,
  fullyParallel: false,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:8787',
    viewport: { width: 1280, height: 800 },
  },
  webServer: {
    command: 'npx http-server . -p 8787 -s -c-1',
    url: 'http://localhost:8787',
    // Reuse a running server in local dev; always start fresh in CI
    reuseExistingServer: !process.env.CI,
  },
});
