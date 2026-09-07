import { defineConfig, devices } from '@playwright/test'

/**
 * Browser tests for the flows that matter most: signing in, saving a workout,
 * reading history, surviving a token refresh, and failing gracefully when the
 * API does not answer.
 *
 * These drive the built frontend against a stubbed API by default, so they run
 * in CI without a database or a Groq key. Point E2E_BASE_URL at a running dev
 * server to drive a real stack instead.
 */

const PORT = 4173
// `localhost`, not 127.0.0.1: vite preview binds to the hostname, which
// resolves to ::1 first on this platform, and the literal IPv4 address is
// then refused.
const baseURL = process.env.E2E_BASE_URL ?? `http://localhost:${PORT}`

export default defineConfig({
  testDir: './e2e',
  // A failing flow should be a real failure, not a flake to be retried away.
  // One retry in CI absorbs genuine infrastructure noise without hiding much.
  retries: process.env.CI ? 1 : 0,
  forbidOnly: !!process.env.CI,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['github'], ['list']] : [['list']],

  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        // Playwright's bundled Chromium by default, which is what CI installs.
        // PLAYWRIGHT_CHANNEL=chrome runs the machine's installed Google Chrome
        // instead — useful when the browser download is unavailable behind a
        // slow or filtered network.
        ...(process.env.PLAYWRIGHT_CHANNEL
          ? { channel: process.env.PLAYWRIGHT_CHANNEL }
          : {}),
      },
    },
  ],

  // Serve the production build: the point is to test what ships, and the dev
  // server's error overlay would otherwise mask runtime failures.
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: `npm run build && npm run preview -- --port ${PORT} --strictPort`,
        url: baseURL,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
        env: { VITE_API_BASE_URL: '' },
      },
})
