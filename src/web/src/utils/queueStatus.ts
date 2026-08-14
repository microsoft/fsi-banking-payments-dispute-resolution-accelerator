import type { CaseStatus, CaseSummary } from '../types/case';

export type QueueTab = 'open' | 'active' | 'needs-review' | 'closed';

const CLOSED_STATUSES = new Set(['approved', 'denied', 'submitted', 'expired', 'closed']);
const ACTIVE_STATUSES = new Set(['intake', 'evidence_gathering', 'ai_drafting']);
const NEEDS_REVIEW_STATUSES = new Set(['pending_review', 'escalated']);

const TERMINAL_STATUS_PATTERN = /\b(approved|denied|submitted|expired|closed)\b/i;
const STATUS_ASSIGNMENT_PATTERN = /status\s*=\s*(approved|denied|submitted|expired|closed)\b/i;
const ACTION_PATTERN = /\baction\s*'?(approve|deny|submit|expire)'?\b/i;

function normalizeStatus(value?: string): CaseStatus | undefined {
  if (!value) return undefined;
  const lowered = value.trim().toLowerCase();
  if (
    lowered === 'intake' ||
    lowered === 'evidence_gathering' ||
    lowered === 'ai_drafting' ||
    lowered === 'pending_review' ||
    lowered === 'approved' ||
    lowered === 'denied' ||
    lowered === 'escalated' ||
    lowered === 'submitted' ||
    lowered === 'expired' ||
    lowered === 'closed'
  ) {
    return lowered;
  }
  return undefined;
}

function inferClosedStatusFromActivity(c: CaseSummary): CaseStatus | undefined {
  const eventType = String(c.lastActivityType || '').toLowerCase();
  const detail = String(c.lastActivityDetail || '').toLowerCase();
  const statusFromDetail = detail.match(STATUS_ASSIGNMENT_PATTERN)?.[1] || detail.match(TERMINAL_STATUS_PATTERN)?.[1];
  const normalized = normalizeStatus(statusFromDetail);
  if (normalized && CLOSED_STATUSES.has(normalized)) {
    return normalized;
  }

  // Fall back to action labels present in analyst timeline details.
  const action = detail.match(ACTION_PATTERN)?.[1];
  if (action === 'approve') return 'approved';
  if (action === 'deny') return 'denied';
  if (action === 'submit') return 'submitted';
  if (action === 'expire') return 'expired';

  // A closure artifact means the case is terminal even if stale status wasn't persisted.
  if (eventType === 'case_closed_artifact_created') {
    return 'closed';
  }

  return undefined;
}

export function getEffectiveCaseStatus(c: CaseSummary): CaseStatus {
  const raw = normalizeStatus(c.status);
  if (raw && CLOSED_STATUSES.has(raw)) {
    return raw;
  }

  return inferClosedStatusFromActivity(c) ?? (raw || 'intake');
}

/**
 * Open means the dispute is not in a terminal state yet.
 */
export function isOpen(c: CaseSummary): boolean {
  return !CLOSED_STATUSES.has(getEffectiveCaseStatus(c));
}

/**
 * Active means currently being worked (before formal review queue).
 */
export function isActive(c: CaseSummary): boolean {
  return ACTIVE_STATUSES.has(getEffectiveCaseStatus(c));
}

/**
 * Needs Review means waiting for analyst decision or escalated review.
 */
export function isNeedsReview(c: CaseSummary): boolean {
  return NEEDS_REVIEW_STATUSES.has(getEffectiveCaseStatus(c));
}

/**
 * Closed means a terminal status was reached.
 */
export function isClosed(c: CaseSummary): boolean {
  return CLOSED_STATUSES.has(getEffectiveCaseStatus(c));
}

export function filterByTab(cases: CaseSummary[], tab: QueueTab): CaseSummary[] {
  switch (tab) {
    case 'open':
      return cases.filter(isOpen);
    case 'active':
      return cases.filter(isActive);
    case 'needs-review':
      return cases.filter(isNeedsReview);
    case 'closed':
      return cases.filter(isClosed);
  }
}
