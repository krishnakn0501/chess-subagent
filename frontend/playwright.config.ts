import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for multi-agent chess E2E tests
 * 
 * Latency optimizations for high LLM generation times (15-45 seconds per turn)
 */
export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  forbidOnly: process.env.CI !== undefined,
  retries: process.env.CI !== undefined ? 2 : 0,
  workers: 1,
  reporter: 'html',

  // Per-test timeout (3 minutes) — accounts for LLM generation latency
  timeout: 180000,

  // Global timeout for entire test run
  globalTimeout: 180000,

  // Default expect timeout (90 seconds)
  expect: {
    timeout: 90000
  },

  use: {
    baseURL: 'http://localhost:3000',
    screenshot: 'on',
    trace: 'on-first-retry',
    video: 'on-first-retry',

    // Generous timeouts for LLM latency
    actionTimeout: 30000,
    navigationTimeout: 30000,
  },
  
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: true,
    timeout: 120000
  },
  
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] }
    }
  ]
});
