const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
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
