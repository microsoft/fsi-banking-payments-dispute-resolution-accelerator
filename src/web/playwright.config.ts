import { defineConfig, devices } from '@playwright/test';

const baseURL =
  process.env.E2E_BASE_URL ?? 'https://<ANALYST_SWA_HOSTNAME>';

export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,          // Azure Functions cold-start can take 30-60 s
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL,
    headless: true,
    screenshot: 'only-on-failure',
    video: 'off',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
