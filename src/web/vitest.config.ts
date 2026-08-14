import { defineConfig } from 'vitest/config';

/**
 * Vitest-specific config — kept separate from vite.config.ts so the Vite
 * production build is not affected by vitest's internal Rollup version.
 * `npm test` (vitest run) prefers vitest.config.ts over vite.config.ts.
 */
export default defineConfig({
  test: {
    // Run only unit tests under src/; exclude Playwright e2e specs in e2e/
    include: ['src/**/*.test.ts', 'src/**/*.spec.ts'],
    environment: 'node',
  },
});
