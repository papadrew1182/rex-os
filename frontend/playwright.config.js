import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30000,
  expect: { timeout: 5000 },
  use: {
    baseURL: process.env.REX_E2E_URL || 'http://localhost:5173',
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  workers: 1,
  reporter: [['list']],
  // Skip auto-starting webserver — assume the dev server is already running
  // or use REX_E2E_URL to point at a deployed instance
});
