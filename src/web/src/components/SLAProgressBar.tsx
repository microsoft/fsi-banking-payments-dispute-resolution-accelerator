import React from 'react';
import { Text, tokens } from '@fluentui/react-components';
import type { CardNetwork, CaseStatus, TimelineEvent } from '../types/case';
import { formatDuration } from '../utils/duration';

interface SLAProgressBarProps {
  status: CaseStatus;
  cardNetwork?: CardNetwork;
  dueDate: string;
  daysRemaining: number;
  createdAt: string;
  resolvedAt?: string;
  timelineEvents?: TimelineEvent[];
}

interface Phase {
  label: string;
  status: 'completed' | 'active' | 'upcoming';
  durationMs?: number;
  customerWaitMs?: number;
}

const networkSLAs: Record<string, { totalDays: number; phases: string[] }> = {
  visa: {
    totalDays: 30,
    phases: ['Intake', 'Evidence Gathering', 'AI Drafting', 'Analyst Review', 'Submit'],
  },
  mastercard: {
    totalDays: 45,
    phases: ['Intake', 'Evidence Gathering', 'AI Drafting', 'Analyst Review', 'Submit'],
  },
  amex: {
    totalDays: 20,
    phases: ['Intake', 'Evidence Gathering', 'AI Drafting', 'Analyst Review', 'Submit'],
  },
  discover: {
    totalDays: 30,
    phases: ['Intake', 'Evidence Gathering', 'AI Drafting', 'Analyst Review', 'Submit'],
  },
};

const statusToPhaseIndex: Record<string, number> = {
  intake: 0,
  evidence_gathering: 1,
  ai_drafting: 2,
  pending_review: 3,
  escalated: 3,
  approved: 4,
  denied: 4,
  submitted: 4,
  expired: 4,
};

function getUrgencyColor(daysRemaining: number): string {
  if (daysRemaining <= 0) return tokens.colorPaletteRedBorderActive;
  if (daysRemaining <= 3) return tokens.colorPaletteRedBorderActive;
  if (daysRemaining <= 7) return tokens.colorPaletteYellowBorderActive;
  return tokens.colorPaletteGreenBorderActive;
}

function getUrgencyLabel(daysRemaining: number): string {
  if (daysRemaining <= 0) return '🚨 OVERDUE';
  if (daysRemaining === 1) return '⚠️ Due Tomorrow';
  if (daysRemaining <= 3) return `⚠️ ${daysRemaining} days left`;
  if (daysRemaining <= 7) return `${daysRemaining} days left`;
  return `${daysRemaining} days remaining`;
}

const RESOLVED_STATUSES = new Set(['approved', 'denied', 'submitted', 'expired', 'closed']);

/** Compute phase durations from timeline status_change events. */
function computePhaseDurations(
  events: TimelineEvent[],
  createdAt: string,
  status: CaseStatus,
  resolvedAt?: string,
): { durations: (number | undefined)[]; customerWaitMs: number | undefined } {
  const created = new Date(createdAt).getTime();
  const isResolved = RESOLVED_STATUSES.has(status);
  const endTime = isResolved && resolvedAt ? new Date(resolvedAt).getTime() : Date.now();

  // Helper: get timestamp from event (handles both `timestamp` and `occurredAt` field names)
  const getTs = (e: TimelineEvent): number => {
    const raw = e.timestamp || (e as any).occurredAt;
    return raw ? new Date(raw).getTime() : NaN;
  };

  // Helper: get data/metadata from event (handles both field names)
  const getData = (e: TimelineEvent): Record<string, any> | undefined =>
    (e.metadata as Record<string, any>) || (e as any).data;

  const normalizedEventType = (e: TimelineEvent): string =>
    String((e as any).eventType || '').toLowerCase();

  const isEventType = (e: TimelineEvent, types: string[]): boolean =>
    types.includes(normalizedEventType(e));

  const isStatusChangeTo = (e: TimelineEvent, targets: string[]): boolean => {
    if (!isEventType(e, ['status_changed', 'status_change'])) {
      return false;
    }
    const data = getData(e) || {};
    const target = String(data.toStatus || data.to || data.status || '').toLowerCase();
    return targets.includes(target);
  };

  const earliestTimestampAfter = (
    predicate: (e: TimelineEvent) => boolean,
    notBefore: number,
  ): number | undefined => {
    const hits = events
      .filter(predicate)
      .map((e) => getTs(e))
      .filter((t) => !Number.isNaN(t) && t >= notBefore)
      .sort((a, b) => a - b);
    return hits[0];
  };

  // Derive phase boundaries from workflow events, not only status updates.
  // This prevents equal-split timelines when status transitions are sparse.
  const evidenceStart = earliestTimestampAfter(
    (e) =>
      isStatusChangeTo(e, ['evidence_gathering']) ||
      isEventType(e, ['document_uploaded', 'evidence_retrieved', 'evidence_gap_detected', 'evidence_gap_requested']),
    created,
  );

  const draftBaseline = evidenceStart ?? created;
  const draftStart = earliestTimestampAfter(
    (e) =>
      isStatusChangeTo(e, ['ai_drafting', 'drafting']) ||
      isEventType(e, ['ai_draft_generated', 'score_generated']),
    draftBaseline,
  );

  const reviewBaseline = draftStart ?? draftBaseline;
  const reviewStart = earliestTimestampAfter(
    (e) =>
      isStatusChangeTo(e, ['pending_review', 'review', 'escalated']) ||
      isEventType(e, ['analyst_note', 'ai_recommendation_response', 'analyst_assigned']),
    reviewBaseline,
  );

  const submitBaseline = reviewStart ?? reviewBaseline;
  const submitStart = earliestTimestampAfter(
    (e) =>
      isStatusChangeTo(e, ['approved', 'denied', 'submitted', 'expired', 'closed']) ||
      isEventType(e, ['case_closed_artifact_created']),
    submitBaseline,
  );

  const hasAnyBoundary =
    evidenceStart !== undefined ||
    draftStart !== undefined ||
    reviewStart !== undefined ||
    submitStart !== undefined;

  // No measurable boundaries: let caller use existing fallback model.
  if (!hasAnyBoundary) {
    return {
      durations: [undefined, undefined, undefined, undefined, undefined],
      customerWaitMs: undefined,
    };
  }

  // Compute per-phase duration: [Intake, Evidence Gathering, AI Drafting, Analyst Review, Submit]
  const durations: (number | undefined)[] = [undefined, undefined, undefined, undefined, undefined];
  if (evidenceStart !== undefined) {
    durations[0] = Math.max(0, evidenceStart - created);
  }
  if (evidenceStart !== undefined) {
    const evidenceEnd = draftStart ?? reviewStart ?? submitStart ?? endTime;
    durations[1] = Math.max(0, evidenceEnd - evidenceStart);
  }
  if (draftStart !== undefined) {
    const draftEnd = reviewStart ?? submitStart ?? endTime;
    durations[2] = Math.max(0, draftEnd - draftStart);
  }
  if (reviewStart !== undefined) {
    const reviewEnd = submitStart ?? endTime;
    durations[3] = Math.max(0, reviewEnd - reviewStart);
  }
  if (submitStart !== undefined) {
    durations[4] = Math.max(0, endTime - submitStart);
  }

  // Customer wait: time between customer_response_requested and customer_response_received
  const custRequested = events
    .filter((e) => e.eventType === 'customer_response_requested' || (e as any).eventType === 'customer_response_requested')
    .map((e) => getTs(e))
    .filter((t) => !Number.isNaN(t))
    .sort((a, b) => a - b);
  const custReceived = events
    .filter((e) => e.eventType === 'customer_response_received' || (e as any).eventType === 'customer_response_received')
    .map((e) => getTs(e))
    .filter((t) => !Number.isNaN(t))
    .sort((a, b) => a - b);

  let customerWaitMs: number | undefined;
  if (custRequested.length > 0) {
    // Sum up all request->response pairs; if no response yet, count to now
    let totalWait = 0;
    for (let i = 0; i < custRequested.length; i++) {
      const start = custRequested[i];
      const end = custReceived[i] ?? Date.now();
      totalWait += end - start;
    }
    customerWaitMs = totalWait;
  }

  return { durations, customerWaitMs };
}

function formatDays(ms: number): string {
  const days = ms / 86_400_000;
  if (days < 0.1) return '<0.1 days';
  return `${days.toFixed(1)} days`;
}

function fallbackPhaseDurations(
  createdAt: string,
  status: CaseStatus,
  resolvedAt?: string,
): (number | undefined)[] {
  const created = new Date(createdAt).getTime();
  if (Number.isNaN(created)) {
    return [undefined, undefined, undefined, undefined, undefined];
  }

  const isResolved = RESOLVED_STATUSES.has(status);
  const end = isResolved && resolvedAt ? new Date(resolvedAt).getTime() : Date.now();
  const total = Math.max(0, end - created);
  const currentPhaseIndex = statusToPhaseIndex[status] ?? 0;

  const visiblePhaseCount = isResolved ? 5 : Math.min(4, currentPhaseIndex + 1);
  if (visiblePhaseCount <= 0) {
    return [undefined, undefined, undefined, undefined, undefined];
  }

  const perPhase = total / visiblePhaseCount;
  const durations: (number | undefined)[] = [undefined, undefined, undefined, undefined, undefined];
  for (let i = 0; i < visiblePhaseCount; i += 1) {
    durations[i] = perPhase;
  }
  return durations;
}

export function SLAProgressBar({ status, cardNetwork, dueDate, daysRemaining, createdAt, resolvedAt, timelineEvents }: SLAProgressBarProps) {
  const network = cardNetwork ?? 'visa';
  const sla = networkSLAs[network] ?? networkSLAs.visa;
  const currentPhaseIndex = statusToPhaseIndex[status] ?? 0;
  const isResolved = RESOLVED_STATUSES.has(status);

  // Calculate time elapsed percentage
  const startDate = new Date(createdAt);
  const endDate = new Date(dueDate);
  const now = new Date();
  const totalDuration = endDate.getTime() - startDate.getTime();
  const elapsed = now.getTime() - startDate.getTime();
  const timeProgress = Math.min(Math.max(elapsed / totalDuration, 0), 1);

  // Total time to process this dispute: createdAt -> resolvedAt (closed) or -> now (still open).
  const processingEnd = isResolved && resolvedAt ? new Date(resolvedAt) : now;
  const processingMs = Math.max(0, processingEnd.getTime() - startDate.getTime());
  const processingTimeLabel = isResolved ? 'Total Processing Time' : 'Time in Progress';
  const processingTimeValue = formatDuration(processingMs);

  // Compute phase durations from timeline events
  const { durations: phaseDurationsRaw, customerWaitMs } = timelineEvents && timelineEvents.length > 0
    ? computePhaseDurations(timelineEvents, createdAt, status, resolvedAt)
    : { durations: [] as (number | undefined)[], customerWaitMs: undefined };

  const hasMeasuredDurations = phaseDurationsRaw.some((duration) => duration !== undefined);
  const phaseDurations = hasMeasuredDurations
    ? phaseDurationsRaw
    : fallbackPhaseDurations(createdAt, status, resolvedAt);

  const phases: Phase[] = sla.phases.map((label, i) => ({
    label,
    status: i < currentPhaseIndex ? 'completed' : i === currentPhaseIndex ? 'active' : 'upcoming',
    durationMs: phaseDurations[i],
    customerWaitMs: i === 1 ? customerWaitMs : undefined, // Evidence Gathering phase
  }));

  const urgencyColor = isResolved ? tokens.colorPaletteGreenBorderActive : getUrgencyColor(daysRemaining);
  const urgencyLabel = isResolved ? 'Closed' : getUrgencyLabel(daysRemaining);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
        <Text weight="semibold" size={400}>
          SLA Progress
        </Text>
        <span
          style={{
            color: urgencyColor,
            fontWeight: 600,
            fontSize: '12px',
          }}
        >
          {urgencyLabel}
        </span>
      </div>

      {/* Total dispute processing time (createdAt -> resolvedAt, or -> now if still open) */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '10px',
          padding: '6px 10px',
          borderRadius: '6px',
          background: tokens.colorNeutralBackground3,
        }}
      >
        <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
          ⏱️ {processingTimeLabel}
        </Text>
        <Text size={300} weight="semibold">
          {processingTimeValue}
        </Text>
      </div>

      {/* Network + Deadline info */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
        <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
          {network.toUpperCase()} · {sla.totalDays}-day window
        </Text>
        <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
          Due: {new Date(dueDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
        </Text>
      </div>

      {/* Time progress bar */}
      <div
        style={{
          height: '6px',
          borderRadius: '3px',
          background: tokens.colorNeutralBackground4,
          marginBottom: '14px',
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${timeProgress * 100}%`,
            borderRadius: '3px',
            background: urgencyColor,
            transition: 'width 0.3s ease',
          }}
        />
      </div>

      {/* Phase tracker */}
      <div style={{ display: 'flex', gap: '2px' }}>
        {phases.map((phase, i) => (
          <div key={i} style={{ flex: 1, textAlign: 'center' }}>
            {/* Phase segment */}
            <div
              style={{
                height: '4px',
                borderRadius: '2px',
                background:
                  phase.status === 'completed'
                    ? tokens.colorPaletteGreenBorderActive
                    : phase.status === 'active'
                      ? tokens.colorPaletteBlueBorderActive
                      : tokens.colorNeutralBackground4,
                marginBottom: '4px',
              }}
            />
            <Text
              size={100}
              weight={phase.status === 'active' ? 'semibold' : 'regular'}
              style={{
                color:
                  phase.status === 'active'
                    ? tokens.colorPaletteBlueBorderActive
                    : phase.status === 'completed'
                      ? tokens.colorPaletteGreenForeground1
                      : tokens.colorNeutralForeground3,
                display: 'block',
              }}
            >
              {phase.status === 'completed' ? '✓ ' : phase.status === 'active' ? '● ' : ''}
              {phase.label}
            </Text>
            {/* Phase duration */}
            {phase.durationMs !== undefined && (
              <Text
                size={100}
                style={{
                  color: tokens.colorNeutralForeground4,
                  display: 'block',
                  marginTop: '2px',
                  fontSize: '10px',
                }}
              >
                {formatDays(phase.durationMs)}
              </Text>
            )}
            {/* Customer wait sub-phase */}
            {phase.customerWaitMs !== undefined && (
              <Text
                size={100}
                style={{
                  color: tokens.colorPaletteYellowForeground2,
                  display: 'block',
                  marginTop: '1px',
                  fontSize: '10px',
                  fontStyle: 'italic',
                }}
              >
                ⏳ Customer: {formatDays(phase.customerWaitMs)}
              </Text>
            )}
          </div>
        ))}
      </div>

      {/* Multi-deadline table */}
      <div style={{ marginTop: '14px', borderTop: `1px solid ${tokens.colorNeutralStroke2}`, paddingTop: '10px' }}>
        <Text size={200} weight="semibold" style={{ display: 'block', marginBottom: '6px' }}>
          Compliance Deadlines
        </Text>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto auto', gap: '4px 12px', fontSize: '12px' }}>
          {getDeadlines(network, dueDate, daysRemaining, isResolved).map((dl) => (
            <React.Fragment key={dl.label}>
              <Text size={200}>{dl.label}</Text>
              <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>{dl.date}</Text>
              <span
                style={{
                  color: dl.closed ? tokens.colorPaletteGreenForeground1 : getUrgencyColor(dl.daysLeft),
                  fontWeight: 600,
                  fontSize: '11px',
                }}
              >
                {dl.closed ? 'Closed' : dl.daysLeft <= 0 ? '🚨 OVERDUE' : `${dl.daysLeft}d`}
              </span>
            </React.Fragment>
          ))}
        </div>
      </div>
    </div>
  );
}

interface DeadlineRow {
  label: string;
  date: string;
  daysLeft: number;
  closed?: boolean;
}

function getDeadlines(network: string, dueDate: string, networkDaysRemaining: number, isResolved: boolean): DeadlineRow[] {
  const due = new Date(dueDate);
  const fmt = (d: Date) => d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

  // Reg E: 10 business days for provisional credit, up to 45 calendar days for investigation
  const regEDate = new Date(due.getTime() - 15 * 86400_000); // Usually tighter than network
  const regEDays = Math.max(0, Math.ceil((regEDate.getTime() - Date.now()) / 86400_000));

  // Internal SLA: typically 2 days before network deadline
  const internalDate = new Date(due.getTime() - 2 * 86400_000);
  const internalDays = Math.max(0, Math.ceil((internalDate.getTime() - Date.now()) / 86400_000));

  const deadlines: DeadlineRow[] = [
    {
      label: `${network.charAt(0).toUpperCase() + network.slice(1)} Representment`,
      date: fmt(due),
      daysLeft: networkDaysRemaining,
      closed: isResolved,
    },
    { label: 'Reg E Investigation', date: fmt(regEDate), daysLeft: regEDays, closed: isResolved },
    { label: 'Internal SLA', date: fmt(internalDate), daysLeft: internalDays, closed: isResolved },
  ];

  // Add Mastercard pre-arb if MC
  if (network === 'mastercard') {
    const preArbDate = new Date(due.getTime() + 15 * 86400_000);
    const preArbDays = Math.ceil((preArbDate.getTime() - Date.now()) / 86400_000);
    deadlines.push({ label: 'MC Pre-Arbitration', date: fmt(preArbDate), daysLeft: preArbDays, closed: isResolved });
  }

  return deadlines.sort((a, b) => a.daysLeft - b.daysLeft);
}
