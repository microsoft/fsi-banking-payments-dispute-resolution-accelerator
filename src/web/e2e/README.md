# E2E Tests — Disputes UI

Playwright end-to-end tests that verify the three production bugs from issue #56 are resolved.

## What they test

| Test | Bug it catches |
|------|---------------|
| Queue shows 10 cases | Silent mock fallback was hiding API outage and returning only 3 mock cases |
| Case detail renders for seeded IDs | `/api/cases/{id}` returning 404 when SWA wasn't linked to the Function App |
| Approve persists after reload | Status was not persisted (approval only existed in-memory) |

## Prerequisites

- Node 20 LTS with `npm install` already run in `src/web/`
- Playwright browsers: `npx playwright install chromium`
- The SWA must be deployed **and** linked to a live Function App (Fenster's infra fix)
- The Function API must be anonymous + seed data loaded (Keaton's API fix)

## Running

```bash
# Against the default deployed SWA
npm run test:e2e

# Against a specific URL (local preview, staging, etc.)
E2E_BASE_URL=http://localhost:4280 npm run test:e2e

# List tests without running them
npx playwright test --list
```

## Notes

- Tests will **fail** until Fenster's SWA→Function link and Keaton's API fixes are deployed.
- The `test:e2e` script is intentionally gated from the main `build` pipeline so CI doesn't block on an unlinked SWA.
- Add `PLAYWRIGHT_HTML_REPORT=playwright-report` to the env to generate an HTML report.
