# Redfoot — History

## Seed Context
- **Project:** Payments Dispute Resolution (agentic evidence-assembly accelerator)
- **Program:** Payments Dispute Resolution
- **Role:** Frontend Dev — analyst review UI, case queue, HITL review experience
- **Stack:** React · TypeScript · Vite · Fluent UI v9 · Azure Static Web Apps
- **Lead developer:** Jorge Balderas
- **Joined:** 2026-07-06 (added for story #21 — analyst review UI)
- **Casting universe:** The Usual Suspects

## Story #21 decisions (at join)
- UI: React SPA on Azure Static Web Apps, calling the Functions API.
- Views: case queue + unified case detail.
- Actions (Approve/Deny/Escalate) wire to the Durable Functions external-event approval gate (#22).
- Stack chosen: TypeScript + Vite + Fluent UI v9.
- Frontend lives in `src/web/` (alongside `src/api/`); both registered as azd services.
- Auth deferred; demo-first then harden.
- Case data comes from a shared contract (JSON Schema -> TS types), backed by synthetic data.

## Learnings

### Fresh transactions + localStorage dispute filter (2026-07-09)

- **Root cause:** Static `demoTransactions` list never changed, so disputed transactions stayed visible and testers could attempt (and fail with 409) to re-dispute them. Backend dedupe is correct and was not changed.
- **Pattern — random generation with localStorage filter:** Generate a candidate pool larger than the target count (TARGET_COUNT + disputed.size + buffer), filter out any whose dedupe key matches a localStorage set, then slice to TARGET_COUNT. The lazy `useState` initializer (not `useEffect`) is the right hook for "compute once on mount" logic — it runs synchronously before the first render and never reruns unless the component unmounts and remounts.
- **Dedupe key design:** Used `network|last4|amount|date|merchant` — same fields as the backend minus reasonCode — so any dispute for a given transaction suppresses it regardless of which reason code was chosen. Simpler than a full hash and sufficient for demo persistence.
- **localStorage resilience:** Wrapped all `localStorage` calls in try/catch; private browsing and restrictive browser policies can throw. Silently degrade to "no filter" rather than crashing the page.
- **Where to mark disputed:** `ReviewPage.tsx` → `handleSubmit()` is the right place — after `submitDispute()` resolves successfully, before `navigate('/confirmation')`. `ConfirmationPage` is the wrong place (user could bookmark or reload it; we'd double-record).
- **Merchant pool:** 12 entries gives good variety; per-category amount ranges keep amounts realistic (e.g. StreamFlix 9.99–29.99, TravelNow 199–3500). Description templates with `{n}` placeholders replaced by a random 5-digit reference keep descriptions non-repetitive.
- **Build:** `tsc --noEmit && vite build` clean — 459 kB JS / 136 kB gzip. No new test framework added (no existing vitest/jest for customer-portal pages).


### deadlineUtc: portal stops overriding server SLA calc (2026-07-08)

- Keaton relaxed `POST /api/disputes`: `deadlineUtc` is optional and the
  server auto-calculates it from per-network SLA rules when omitted/falsy —
  `body.get("deadlineUtc") or _compute_deadline_utc(...)` in
  `src/api/function_app.py`. Confirmed by reading the handler directly
  (never guess a backend contract from decision docs alone).
- Fixed the portal to stop always sending a flat client-computed
  `today + 45 days` deadline that silently overrode the correct per-network
  window (visa=30/mastercard=45/amex=20/discover=30) on every real
  submission. `DisputeSubmissionPayload.deadlineUtc` is now optional;
  `ReviewPage.tsx` only populates it when `VITE_USE_MOCK=true` (no server to
  compute it in demo mode), gated on a newly-exported `USE_MOCK` flag from
  `api/disputes.ts`. `computeDeadlineUtc()` is preserved but scoped strictly
  to the mock path (also used as a fallback inside `mockDisputeResponse`).
- Checked both `ReviewPage.tsx` and `ConfirmationPage.tsx` before assuming a
  UX transition was needed: neither page actually displays `deadlineUtc`
  anywhere today, so there's no "estimate → authoritative value" swap to
  implement yet. The server's real computed value already flows through via
  `DisputeCreatedResponse` → `setSubmittedCase(result)`, so a future
  Confirmation-page enhancement to show the deadline would need zero
  additional plumbing. **Lesson:** don't build UI transition logic for a
  display that doesn't exist — verify actual usage with grep before adding
  speculative state handling.
- Spreading a conditional key as `...(cond ? { key: val } : {})` fully omits
  the property from the object literal (not just `undefined`), which is a
  clean way to match a backend's "optional/omitted field" contract exactly
  without relying on `JSON.stringify` stripping `undefined` values.
- `npm run build` in `src/customer-portal` stayed clean after the change: 0
  TS errors, Vite build 457 kB JS / 135 kB gzip (unchanged from prior MVP
  build size — `computeDeadlineUtc` didn't move, just its call sites).


### Story portal-ui — Customer Portal MVP (2026-07-08)

- **App path:** `src/customer-portal/` — standalone Vite + React + TypeScript + Fluent UI v9 app; separate from `src/web/` (analyst portal).
- **Features built:** transaction-select (6 seeded demo transactions, all 4 networks), dispute-form (reason code dropdown by network, cardholder name, description), document-upload (drag-and-drop UI; file metadata only in MVP), review page, confirmation page with case reference display.
- **UI stack:** Vite 5, React 18, TypeScript strict, Fluent UI v9, React Router v6 — same as `src/web/`. Wizard state managed via `WizardContext` in `App.tsx` (no Redux/Zustand; simple useState + context pattern).
- **API assumptions:**
  - `POST /api/disputes` — wired directly; required fields: `networkCode`, `reasonCode`, `cardholderName`, `cardLastFour`, `transactionAmount`, `transactionCurrency`, `transactionDate`, `merchantName`, `deadlineUtc`.
  - Demo/mock mode: `VITE_USE_MOCK=true` returns synthetic `DisputeCreatedResponse` without hitting the network. Dev mode falls back silently. Production re-throws errors.
  - `deadlineUtc` computed client-side as `today + 45 days` (temp; see gap doc).
  - Document upload deferred: file metadata attached to `metadata.attachments[]` in JSON payload; no byte transport.
- **API gaps documented:** `GET /api/disputes/{id}` requires `networkCode` partition key (awkward for customer portal), no multipart upload endpoint, client-side deadline computation. See `.squad/decisions/inbox/redfoot-customer-portal-gap.md`.
- **Build status:** TypeScript 0 errors, Vite production build clean (457 kB JS / 135 kB gzip).
- **Fluent UI Badge `color` note:** Fluent UI v9 `Badge` color prop does not accept `"neutral"` — use `"subtle"` for uncoloured/inactive badges. (Different from other Fluent components.)

### Story #51 — mock mode docs, vitest invariants, build fix (2026-07-08)

- **`.env.sample`**: Documents `VITE_USE_MOCK=true` (skip-fetch mode) vs. the `DEV` automatic fallback. Committed to repo so the pattern is discoverable.
- **vitest separate config**: `vitest.config.ts` must be kept separate from `vite.config.ts` — they share a config shape but vitest's `defineConfig` (from `vitest/config`) upgrades Rollup internally, which breaks the Vite production build by making previously-ignored `UNRESOLVED_IMPORT` warnings into hard errors. Never merge them into a single file.
- **`scheduler` hoisting**: vitest upgraded Rollup to 4.62.2 which became strict about `@fluentui/react-context-selector`'s import of `scheduler`. The package was nested inside `react-dom/node_modules/` and not hoisted. Fix: `npm install scheduler` + `optimizeDeps.include: ['scheduler']` in `vite.config.ts`.
- **Mock data invariant tests**: three vitest assertions catch summary/detail mismatches that cause silent queue-shows-but-detail-404 bugs. Run in < 10 ms with no DOM or browser environment needed.

### Playwright selector investigation: Fluent UI v9 renders native HTML table (2026-07-08)

Three rounds of iteration revealed the actual DOM structure:

1. `getByRole('grid')` — wrong; Fluent UI `<Table>` is `role="table"`, not `"grid"`.
2. `locator('[role=rowgroup]')` — wrong; CSS attribute selector misses native `<tbody>` which has an **implicit** role, not an explicit `role=` attribute.
3. `getByRole('rowgroup')` (Playwright accessibility-tree method) — would work, but `locator('tbody tr')` is simpler and more robust.
4. **Correct**: `page.locator('tbody tr')` — Fluent UI v9 `<Table>` renders a native `<table>`/`<tbody>`/`<tr>` with zero `role=` attributes. Confirmed by probing the live DOM (ROLES: {}, table: 1, tr: 4).

`data-testid="case-row"` passes through to the native `<tr>` (React passes `data-*` attrs), so `getByTestId('case-row')` is an equally valid alternative for the body rows.

### Azure Functions cold-start blocking E2E (2026-07-08)

The deployed SWA proxies `/api/*` to the Function App. On first hit after idle, the Function App cold-starts — the SWA proxy hangs the connection (no response for >45 s) rather than forwarding a 502/503. The browser's `fetch()` never resolves; the QueuePage spinner stays forever. Selectors can't find `tbody tr` because the table never renders. Playwright's `request.get('/api/cases')` can time out and throw "Request context disposed." Fix: generous timeout (60 s on the request, 45 s on first-row wait) and run the queue test first so it warms up the Functions before specs #2/#3 call `getLiveCases()`.

The Function App also returned 500 during the 2026-07-08T11-15Z window ("Backend call failure") — this was a separate backend outage, not cold-start, and is a Fenster/Keaton concern.



`apiFetch` in `src/web/src/api/cases.ts` had an unconditional catch-fallback: on ANY fetch error it silently returned mock data. When the SWA wasn't linked to the Function App (issue #56), every `/api/*` call returned 404 — but the UI happily showed 3 mock cases, masking a total production outage. Fix: gate the catch-fallback on `import.meta.env.DEV || USE_MOCK`. In a production build the error is re-thrown so the UI can render an error state. Local dev and `VITE_USE_MOCK=true` mock mode are fully preserved (story #51). Lesson: any "convenience fallback" in a fetch helper should be explicitly scoped to non-production environments.

### Playwright E2E baseURL pattern for SWA (2026-07-07)

Added Playwright to `src/web/` with `baseURL` read from `process.env.E2E_BASE_URL`, defaulting to the deployed SWA URL. This lets the same spec file run against local preview (`E2E_BASE_URL=http://localhost:4280 npm run test:e2e`) or the deployed app (no override needed in CI). Tests were authored as a verification harness — they are expected to fail until Fenster's infra and Keaton's API fixes are deployed. `npx playwright test --list` confirms all 6 specs parse cleanly without installing browsers.



### Mock detail map must stay in sync with mockCaseSummaries (2026-07-07)

`src/web/src/mocks/cases.ts` exports two independent structures: `mockCaseSummaries: CaseSummary[]` (the queue list) and `mockCases: Record<string, Case>` (the detail map keyed by caseId). The queue renders from the summaries; the detail page looks up `mockCases[caseId]`. If a summary exists but its matching detail record is absent from `mockCases`, `getCase()` returns `undefined` and the detail page renders "Case not found" (effectively a 404). **Every entry in `mockCaseSummaries` must have a corresponding key in `mockCases` or the detail page will 404.** Bug confirmed on case `00000000-0000-0000-0000-000000000003` — summary existed, detail entry was missing. Fixed by adding the full `Case` record for `...0003` to `mockCases`.



### README accelerator-template restructure (2026-07-06)

Rewrote `README.md` to follow the Microsoft solution-accelerator README template (matching microsoft/content-generation-solution-accelerator and microsoft/Data-and-Agent-Governance-and-Security-Accelerator):

**Template structure used:**
1. Title + 1–2 sentence description
2. Centered `<p align="center">` nav bar with anchor links: SOLUTION OVERVIEW | QUICK DEPLOY | BUSINESS SCENARIO | SUPPORTING DOCUMENTATION
3. Responsible AI / security note callout
4. `## Solution Overview` — technology bullets + architecture link + collapsible `<details open>` Features block
5. `## Quick Deploy` — prerequisites table, `azd up` flow, OIDC CI/CD, local dev (Functions + React SPA)
6. `## Guidance` — prerequisites/costs sub-section + Resources table
7. `## Business Scenario` — chargeback scenario description + **embedded screenshots** + collapsible Business Value table
8. `## Project Structure` — verified file tree
9. `## Supporting Documentation` — links verified against repo
10. CI/CD badges + Responsible AI footer

**Screenshot locations (both exist in repo):**
- `docs/images/readme/case-queue.png` — analyst Dispute Case Queue (sortable table)
- `docs/images/readme/case-detail.png` — unified Case Detail view

**Supporting doc links verified as existing:**
- `prd.md` ✓
- `product-vision.md` ✓
- `docs/architecture.md` ✓
- `CHANGELOG.md` ✓
- `src/web/README.md` ✓
- `src/shared/README.md` ✓
- `src/data/synthetic/README.md` ✓



### README documentation update (2026-07-06)

Added the React SPA to the project README.md, matching the existing style (tables, code blocks, tree format):
- Node.js 20 LTS added to both prerequisites tables + verify block.
- Step 7 "Run the React app locally" added to Local Development (dev server, mock mode, build/preview).
- `azd deploy` section updated to reflect both `api` and `web` services; `azd deploy web` for SPA-only.
- Project Structure tree expanded: `src/web/`, `src/shared/`, `src/data/synthetic/`, `infra/modules/staticwebapp.bicep`, `src/api/` subdirs.
- Review UI link added to Quick Links table.
- CHANGELOG [Unreleased] updated with a docs entry.

No doc-structure decision note created — the changes were additive and matched existing conventions without requiring a new architectural choice.

**Component structure**
- Kept components single-responsibility and small. `CaseBadges.tsx` centralises all `Badge` helpers (RiskBadge, StatusBadge, CompletenessBadge, ImpactBadge) so every page imports the same visual vocabulary without duplicating colour-mapping logic.
- `SectionCard` defined as a local wrapper inside `CaseDetailPage` (not exported) because it's layout-only and only used in that one file. Avoids premature abstraction.
- `WinProbGauge` uses a plain `<div>` progress bar instead of Fluent's `<ProgressBar>` because `ProgressBar` v9.46 has no `color` prop — avoids a silent no-op and keeps the visual intent correct.
- `DeadlineCountdown` is a reusable component shared by `CaseTable` and `CaseDetailPage` header, ensuring consistent deadline colouring in both surfaces.

**API client strategy**
- Single `apiFetch<T>` generic in `src/api/cases.ts` handles all three cases: mock-mode flag, live fetch, and live-fetch-fallback-to-mock. Callers pass the mock data as the optional `fallback` argument — no repetition.
- `VITE_USE_MOCK` env var (typed in `vite-env.d.ts`) is evaluated once at module load, not per call.
- `postAction` returns `{ status }` and the optimistic update casts it to `CaseStatus` at the call site, consistent with how the API contract is specified.

**Mock strategy**
- `src/mocks/cases.ts` exports `mockCaseSummaries: CaseSummary[]` and `mockCases: Record<string, Case>`. This keeps fixtures typed against the shared contract so any schema drift breaks the mock at compile time, not silently at runtime.
- Two full `Case` objects (Visa 13.1, MC 4853) and three `CaseSummary` objects (plus an evidence_gathering Amex case) give enough variety to exercise all badge colours, gap highlighting, and deadline urgency levels in the UI.

**TypeScript strict / build**
- `noUnusedLocals + noUnusedParameters` required `_ev` prefix on unused event args in Fluent UI onChange callbacks and prompted removing every speculative import.
- `allowImportingTsExtensions: true` requires `noEmit: true`; build script is `tsc --noEmit && vite build` (single tsconfig, no project references) to keep config minimal.
- `tokens.colorStatusDangerBackground1` / `tokens.colorStatusWarningBorder1` etc. work correctly as inline `style` values inside `FluentProvider` — they resolve as CSS custom properties set at the provider root.
- First build was clean (0 TS errors, 0 Vite errors). dist/ produced: 349 kB JS, 0.34 kB HTML.

---

📌 Team update (2026-07-06T21:15:17Z): Issue #42 decision merged. Keaton's API (#38, #40, #41) and Fenster's SWA infra (#43) are committed and ready. Your SPA is fully typed against the shared contract; mock mode (VITE_USE_MOCK=true) and live fallback allow dev/demo/test flexibility. Ready for integration testing.
— Scribe


📌 Team update (2026-07-06T22:58:00Z): Story #21 finalized — README restructure merged, E2E suite 210/210 passed, PR #45 opened develop→main — decided by Scribe in coordination with Fenster, Kobayashi, McManus, Redfoot

📌 Team update (2026-07-08T13:55:00Z): Story #51 complete; frontend E2E tests 3/3 GREEN; API fallback hardened (production errors now visible); SWA now linked to Function App backend, public access restored — decided by Coordinator

### README restructure for deploy/local-doc flow (2026-07-09)

- Reordered the top-level README flow to **Solution Overview → Business Scenario → Quick Deploy**, so readers see the product story and current analyst UI before they hit setup instructions.
- Split deployment vs. workstation guidance into distinct sections: **Quick Deploy** now stays focused on the Azure path (`azd up`, `azd provision`, `azd deploy`, teardown), while **Local Development** owns the local toolchain, React dev server, local modes, Functions setup, and Cosmos seeding.
- Promoted **GitHub Actions CI/CD** into its own top-level section beside Quick Deploy instead of leaving it mixed into local-run guidance; that keeps repo automation near deployment topics without muddying the one-command start path.
- Refreshed the README screenshots from the live analyst UI at `https://<ANALYST_SWA_HOSTNAME>`, using the populated **Active** queue tab for the queue image and the corresponding **TravelNow LLC** case detail page for the detail image.
