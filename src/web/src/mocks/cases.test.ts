/**
 * Mock data invariant tests.
 *
 * The queue (QueuePage) renders from mockCaseSummaries; the detail page looks
 * up mockCases[caseId].  A mismatch causes a silent "Case not found" 404 on
 * the detail route — this test prevents that regression (originally hit on
 * case 00000000-0000-0000-0000-000000000003).
 */
import { describe, it, expect } from 'vitest';
import { mockCases, mockCaseSummaries } from './cases';

describe('mock data invariants', () => {
  it('every summary id has a matching detail entry in mockCases', () => {
    const missing = mockCaseSummaries
      .filter((s) => mockCases[s.caseId] === undefined)
      .map((s) => s.caseId);

    expect(
      missing,
      `Summaries with no matching detail — detail page would 404: [${missing.join(', ')}]`,
    ).toHaveLength(0);
  });

  it('every mockCases key matches the caseId field inside that record', () => {
    const mismatched = Object.entries(mockCases)
      .filter(([key, detail]) => key !== detail.caseId)
      .map(([key, detail]) => `key=${key} vs caseId=${detail.caseId}`);

    expect(
      mismatched,
      `Keys that don't match their own caseId field: [${mismatched.join(', ')}]`,
    ).toHaveLength(0);
  });

  it('every detail entry has a matching summary (no orphan detail records)', () => {
    const summaryIds = new Set(mockCaseSummaries.map((s) => s.caseId));
    const orphans = Object.keys(mockCases).filter((id) => !summaryIds.has(id));

    expect(
      orphans,
      `Detail entries with no matching queue summary: [${orphans.join(', ')}]`,
    ).toHaveLength(0);
  });
});
