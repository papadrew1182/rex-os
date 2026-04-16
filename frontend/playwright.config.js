import { defineConfig, devices } from '@playwright/test';

// Mobile-overflow regression requires WebKit + iPhone device emulation to
// reproduce the iOS Safari bug at https://rex-os.vercel.app. Every project
// inherits the shared use{} block below. Point the suite at a real deploy
// via REX_E2E_URL, or leave it default for a local `npm run dev`.

const iPhone12 = devices['iPhone 12'];

export default defineConfig({
  testDir: './e2e',
  timeout: 30000,
  expect: { timeout: 5000 },
  use: {
    baseURL: process.env.REX_E2E_URL || 'http://localhost:5173',
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
  },
  workers: 1,
  reporter: [
    ['list'],
    ['html', { open: 'never', outputFolder: 'playwright-report' }],
  ],
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
    {
      name: 'iphone-portrait',
      use: {
        ...iPhone12,
        // devices['iPhone 12'] already ships portrait 390x844 + iOS Safari UA.
      },
    },
    {
      name: 'iphone-landscape',
      use: {
        ...iPhone12,
        // Swap viewport axes while keeping the iOS Safari user agent and
        // WebKit engine. Playwright's built-in iPhone-landscape device
        // entries exist (`iPhone 12 landscape`) but we keep the pair
        // explicit so intent is obvious when reading the config.
        viewport: { width: 844, height: 390 },
      },
    },
  ],
  // Skip auto-starting the webserver — point at a running dev server or
  // a deployed instance via REX_E2E_URL.
});
