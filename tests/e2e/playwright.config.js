const { defineConfig, devices } = require('@playwright/test');

// Serves the built public/ dir and runs UI regression tests against it.
module.exports = defineConfig({
  testDir: '.',
  globalSetup: './global-setup.js',
  use: { baseURL: 'http://127.0.0.1:8799', trace: 'on-first-retry' },
  webServer: {
    command: 'python3 -m http.server 8799 --directory ../../public',
    url: 'http://127.0.0.1:8799/index.html',
    reuseExistingServer: !process.env.CI,
    timeout: 30000,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
