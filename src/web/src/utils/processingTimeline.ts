/**
 * Computes a phase-by-phase duration breakdown for a dispute case, for the
 * visual processing-time timeline (Case Detail page).
 *
 * Phases mirror the stage tracker already shown in SLAProgressBar:
 *   Intake -> Evidence Gathering -> AI Drafting -> Analyst Review -> (Submit)
 *
 * Boundary timestamps are derived from the case's timeline events where
 * available, with graceful degradation:
 *   - If a boundary event for a phase transition is missing, that phase
 *     collapses into the next available boundary (zero duration) rather
 *     than guessing or crashing.
 *   - If NO phase-boundary events are found at all (e.g. timeline API
 *     returned an empty list), the whole span collapses into a single
 *     "In Progress" / "Total" segment from createdAt to the end time.
 *
 * "Submit" is not modeled as a separate duration bucket — there is no
 * distinct case-level timestamp for it (it typically follows the analyst
 * decision near-instantly); it remains a discrete milestone in the existing
 * phase tracker instead.
 */
import type { CaseStatus, TimelineEvent } from '../types/case';

const RESOLVED_STATUSES: ReadonlySet<CaseStatus> = new Set(['approved', 'denied', 'submitted', 'expired']);

export interface StagePhase {
  key: 'intake' | 'evidence_gathering' | 'ai_drafting' | 'analyst_review' | 'in_progress';
  label: string;
  startedAt: string; // ISO 8601
  endedAt: string;   // ISO 8601
  durationMs: number;
  /** True for the single phase still accumulating time (case not yet resolved). */
  ongoing: boolean;
}

export interface ProcessingBreakdown {
  phases: StagePhase[];
  totalMs: number;
  resolved: boolean;
}

interface CaseTimingInput {
  status: CaseStatus;
  createdAt: string;
  updatedAt?: string;
  resolvedAt?: string;
}

function earliestTimestamp(
  events: TimelineEvent[],
  predicate: (e: TimelineEvent) => boolean,
  notBefore: number,
): number | null {
  let best: number | null = null;
  for (const e of events) {
    if (!predicate(e)) continue;
    const t = new Date(e.timestamp).getTime();
    if (Number.isNaN(t) || t < notBefore) continue;
    if (best === null || t < best) best = t;
  }
  return best;
}

function isStatusChangeTo(e: TimelineEvent, to: string): boolean {
  return e.eventType === 'status_changed' && (e.metadata as { to?: string } | undefined)?.to === to;
}

/**
 * Compute the phase-by-phase duration breakdown for a case.
 *
 * @param caseData Minimal case timing fields (status, createdAt, updatedAt, resolvedAt).
 * @param events   The case's timeline events (may be empty — degrades gracefully).
 */
export function computeProcessingBreakdown(
  caseData: CaseTimingInput,
  events: TimelineEvent[],
): ProcessingBreakdown {
  const created = new Date(caseData.createdAt).getTime();
  const resolved = RESOLVED_STATUSES.has(caseData.status);
  const now = Date.now();

  const endTime = resolved
    ? new Date(caseData.resolvedAt ?? caseData.updatedAt ?? caseData.createdAt).getTime()
    : now;

  if (Number.isNaN(created)) {
    return { phases: [], totalMs: 0, resolved };
  }

  const evidenceStart =
    earliestTimestamp(
      events,
      (e) => e.eventType === 'evidence_retrieved' || e.eventType === 'evidence_gap_detected' || isStatusChangeTo(e, 'evidence_gathering'),
      created,
    ) ?? created;

  const draftStart =
    earliestTimestamp(
      events,
      (e) => e.eventType === 'ai_draft_generated' || isStatusChangeTo(e, 'ai_drafting'),
      evidenceStart,
    ) ?? evidenceStart;

  const reviewStart =
    earliestTimestamp(
      events,
      (e) =>
        e.eventType === 'analyst_assigned' ||
        isStatusChangeTo(e, 'pending_review') ||
        isStatusChangeTo(e, 'escalated'),
      draftStart,
    ) ?? draftStart;

  // No phase-boundary signals found at all -> collapse to a single segment.
  const hasAnyBoundary = evidenceStart > created || draftStart > evidenceStart || reviewStart > draftStart;
  if (!hasAnyBoundary) {
    const durationMs = Math.max(0, endTime - created);
    return {
      phases: [
        {
          key: 'in_progress',
          label: resolved ? 'Total Processing Time' : 'In Progress',
          startedAt: caseData.createdAt,
          endedAt: new Date(endTime).toISOString(),
          durationMs,
          ongoing: !resolved,
        },
      ],
      totalMs: durationMs,
      resolved,
    };
  }

  const bounds: { key: StagePhase['key']; label: string; start: number; end: number }[] = [
    { key: 'intake', label: 'Intake', start: created, end: evidenceStart },
    { key: 'evidence_gathering', label: 'Evidence Gathering', start: evidenceStart, end: draftStart },
    { key: 'ai_drafting', label: 'AI Drafting', start: draftStart, end: reviewStart },
    { key: 'analyst_review', label: 'Analyst Review', start: reviewStart, end: endTime },
  ];

  const phases: StagePhase[] = bounds.map(({ key, label, start, end }, i) => {
    const clampedEnd = Math.max(start, end);
    return {
      key,
      label,
      startedAt: new Date(start).toISOString(),
      endedAt: new Date(clampedEnd).toISOString(),
      durationMs: clampedEnd - start,
      ongoing: i === bounds.length - 1 && !resolved,
    };
  });

  const totalMs = Math.max(0, endTime - created);
  return { phases, totalMs, resolved };
}
