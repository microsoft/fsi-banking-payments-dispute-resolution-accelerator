import { test, expect } from '@playwright/test';

/** Shape of a single item in the GET /api/cases response. */
interface CaseSummary {
  caseId: string;
  status: string;
}

/**
 * Fetch all cases from the live API using Playwright's request fixture.
 * Fast-fails with a descriptive error so downstream locator failures don't
 * obscure a real API outage.
 */
async function getLiveCases(
  request: Parameters<Parameters<typeof test>[1]>[0]['request'],
): Promise<CaseSummary[]> {
  // Generous timeout: Azure Functions cold-start can take 30-60 s on first hit
  const res = await request.get('/api/cases', { timeout: 60_000 });
  expect(res.ok(), `GET /api/cases returned ${res.status()}`).toBeTruthy();
  const body = (await res.json()) as { cases: CaseSummary[] };
  expect(body.cases?.length, 'Expected at least one case from API').toBeGreaterThan(0);
  return body.cases;
}

// ---------------------------------------------------------------------------
// Bug #1 — Queue shows all 10 seeded cases (regression: mock returned only 3)
//
// Selector rationale: Fluent UI v9 <Table> renders a native <table> element
// with no explicit role= attributes — roles are implicit (semantic HTML).
// Therefore CSS attribute selectors like [role=rowgroup] miss <tbody>, and
// getByRole('grid') was wrong to begin with. The reliable selector is:
//   page.locator('tbody tr')   — body rows only, no header, no role deps.
// data-testid="case-row" is also present on <tr> (added in CaseTable.tsx)
// and can be used as an alternative once that build is deployed.
// ---------------------------------------------------------------------------
test('queue displays all 10 seeded cases', async ({ page }) => {
  await page.goto('/');

  // Wait until at least the first body row is visible (cold-start aware: 45 s)
  await expect(page.locator('tbody tr').first()).toBeVisible({ timeout: 45_000 });

  // Assert full count of data rows
  await expect(page.locator('tbody tr')).toHaveCount(10);
});

// ---------------------------------------------------------------------------
// Bug #2 — Case detail loads without 404 for live case IDs
//
// IDs are fetched from the live API so they work with real (hashed) GUIDs.
// Load gate: "← Back to Queue" button — present in the loaded detail page
// and the error state, but NOT during the loading spinner. Waiting for it
// confirms the fetch finished. The subsequent "case not found" negative check
// then distinguishes error vs. success.
// Note: <Title1 as="h1"> was also added to CaseDetailPage so
// getByRole('heading',{level:1}) will work after that build deploys.
// ---------------------------------------------------------------------------
test('case detail renders for first 3 cases from the live queue', async ({ page, request }) => {
  const cases = await getLiveCases(request);
  const sample = cases.slice(0, 3);

  for (const { caseId } of sample) {
    await page.goto(`/cases/${caseId}`);

    // "← Back to Queue" appears once loading is done (not during spinner)
    await expect(
      page.getByRole('button', { name: /back to queue/i }),
    ).toBeVisible({ timeout: 30_000 });

    // Not-found error must be absent
    await expect(page.getByText(/case not found/i)).not.toBeVisible();

    // Case ID rendered as "Case ID: <uuid>" in monospace block
    await expect(page.getByText(caseId, { exact: false })).toBeVisible();
  }
});

// ---------------------------------------------------------------------------
// Bug #3 — Approve persists across page reload (regression: status reverted)
//
// Selector fixes:
//   • getByPlaceholder(/comment/i) → getByLabel(/comment/i)
//     Actual placeholder: "Add a note or justification…"
//     Field label: "Comment (optional)" — matches /comment/i
//   • getByText(/pending_review/i) → getByText(/pending review/i)
//     StatusBadge renders status.replace(/_/g,' '), so pending_review → "pending review"
// ---------------------------------------------------------------------------
test('approving a pending case persists after reload', async ({ page, request }) => {
  const cases = await getLiveCases(request);

  const pendingCase = cases.find((c) => c.status === 'pending_review');
  if (!pendingCase) {
    // No pending_review case — all already actioned. Skip to avoid false negatives.
    test.skip(true, 'No pending_review case available in the live queue');
    return;
  }

  await page.goto(`/cases/${pendingCase.caseId}`);

  // "← Back to Queue" button confirms loading is done (not present during spinner)
  await expect(
    page.getByRole('button', { name: /back to queue/i }),
  ).toBeVisible({ timeout: 30_000 });

  // Fill in the comment field — Field label is "Comment (optional)", matches /comment/i
  const commentField = page.getByLabel(/comment/i);
  if (await commentField.isVisible()) {
    await commentField.fill('Approved by E2E test');
  }

  // Approve button text is "✓ Approve" — /approve/i matches substring
  const approveBtn = page.getByRole('button', { name: /approve/i });
  await approveBtn.click();

  // Wait for success banner / status badge to show "approved"
  // (.first() because ActionBar also shows "Case status updated to approved")
  await expect(page.getByText(/approved/i).first()).toBeVisible({ timeout: 30_000 });

  // Hard reload — status must come from Cosmos, not optimistic state
  await page.reload();
  // Wait for the page to finish loading again
  await expect(
    page.getByRole('button', { name: /back to queue/i }),
  ).toBeVisible({ timeout: 30_000 });

  // Status badge now shows "approved"
  // (.first() because ActionBar terminal message also contains "approved")
  await expect(page.getByText(/approved/i).first()).toBeVisible({ timeout: 30_000 });
  // "pending review" (the badge label for pending_review) must be gone
  await expect(page.getByText(/pending review/i)).not.toBeVisible();
});
