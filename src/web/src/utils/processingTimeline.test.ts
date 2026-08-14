import { describe, expect, it } from 'vitest';
import { computeProcessingBreakdown } from './processingTimeline';
import type { TimelineEvent } from '../types/case';

const T0 = '2026-06-01T00:00:00.000Z';

function ev(overrides: Partial<TimelineEvent>): TimelineEvent {
  return {
    eventId: overrides.eventId ?? 'e1',
    disputeId: 'case-1',
    eventType: 'status_changed',
    timestamp: T0,
    description: '',
    ...overrides,
  };
}

describe('computeProcessingBreakdown', () => {
  it('collapses to a single "In Progress" segment when there are no boundary events', () => {
    const result = computeProcessingBreakdown(
      { status: 'pending_review', createdAt: T0 },
      [],
    );
    expect(result.phases).toHaveLength(1);
    expect(result.phases[0].key).toBe('in_progress');
    expect(result.phases[0].label).toBe('In Progress');
    expect(result.phases[0].ongoing).toBe(true);
    expect(result.resolved).toBe(false);
  });

  it('collapses to "Total Processing Time" for a resolved case with no boundary events', () => {
    const resolvedAt = '2026-06-05T00:00:00.000Z';
    const result = computeProcessingBreakdown(
      { status: 'approved', createdAt: T0, resolvedAt },
      [],
    );
    expect(result.phases).toHaveLength(1);
    expect(result.phases[0].label).toBe('Total Processing Time');
    expect(result.phases[0].ongoing).toBe(false);
    expect(result.totalMs).toBe(new Date(resolvedAt).getTime() - new Date(T0).getTime());
  });

  it('splits into 4 phases when full boundary events are present (open case)', () => {
    const events: TimelineEvent[] = [
      ev({ eventId: 'e1', eventType: 'case_created', timestamp: '2026-06-01T00:00:00.000Z' }),
      ev({ eventId: 'e2', eventType: 'evidence_retrieved', timestamp: '2026-06-01T02:00:00.000Z' }),
      ev({ eventId: 'e3', eventType: 'ai_draft_generated', timestamp: '2026-06-02T02:00:00.000Z' }),
      ev({
        eventId: 'e4',
        eventType: 'status_changed',
        timestamp: '2026-06-02T03:00:00.000Z',
        metadata: { from: 'ai_drafting', to: 'pending_review' },
      }),
    ];

    const result = computeProcessingBreakdown(
      { status: 'pending_review', createdAt: T0 },
      events,
    );

    expect(result.phases.map((p) => p.key)).toEqual([
      'intake',
      'evidence_gathering',
      'ai_drafting',
      'analyst_review',
    ]);

    const [intake, evidence, drafting, review] = result.phases;
    expect(intake.durationMs).toBe(2 * 3_600_000); // 0 -> 02:00
    expect(evidence.durationMs).toBe(24 * 3_600_000); // 02:00 day1 -> 02:00 day2
    expect(drafting.durationMs).toBe(1 * 3_600_000); // 02:00 -> 03:00
    expect(review.ongoing).toBe(true); // case still pending_review
    expect(review.durationMs).toBeGreaterThan(0);

    // Total should equal now - created (approximately; review phase runs to "now")
    const expectedTotal = Date.now() - new Date(T0).getTime();
    expect(result.totalMs).toBeGreaterThan(0);
    expect(result.totalMs).toBeLessThanOrEqual(expectedTotal + 1000);
  });

  it('marks the analyst_review phase as not ongoing and uses resolvedAt as the end for resolved cases', () => {
    const resolvedAt = '2026-06-03T00:00:00.000Z';
    const events: TimelineEvent[] = [
      ev({ eventId: 'e2', eventType: 'evidence_retrieved', timestamp: '2026-06-01T02:00:00.000Z' }),
      ev({ eventId: 'e3', eventType: 'ai_draft_generated', timestamp: '2026-06-01T04:00:00.000Z' }),
      ev({
        eventId: 'e4',
        eventType: 'status_changed',
        timestamp: '2026-06-01T05:00:00.000Z',
        metadata: { to: 'pending_review' },
      }),
    ];

    const result = computeProcessingBreakdown(
      { status: 'approved', createdAt: T0, resolvedAt },
      events,
    );

    const review = result.phases.find((p) => p.key === 'analyst_review')!;
    expect(review.ongoing).toBe(false);
    expect(review.endedAt).toBe(resolvedAt);
    expect(result.resolved).toBe(true);
  });

  it('degrades a partial boundary set gracefully (only evidence event present)', () => {
    const events: TimelineEvent[] = [
      ev({ eventId: 'e2', eventType: 'evidence_retrieved', timestamp: '2026-06-01T05:00:00.000Z' }),
    ];
    const result = computeProcessingBreakdown(
      { status: 'evidence_gathering', createdAt: T0 },
      events,
    );
    // Still produces 4 phases; drafting/review collapse to zero duration since
    // no later boundary events exist yet.
    expect(result.phases).toHaveLength(4);
    const [intake, evidence, drafting] = result.phases;
    expect(intake.durationMs).toBe(5 * 3_600_000);
    expect(evidence.durationMs).toBeGreaterThanOrEqual(0);
    expect(drafting.durationMs).toBe(0);
  });

  it('never produces negative durations even with out-of-order event timestamps', () => {
    const events: TimelineEvent[] = [
      ev({ eventId: 'e2', eventType: 'evidence_retrieved', timestamp: '2026-06-02T00:00:00.000Z' }),
      // ai_draft_generated BEFORE evidence_retrieved (bad data) — must not go negative.
      ev({ eventId: 'e3', eventType: 'ai_draft_generated', timestamp: '2026-06-01T00:00:00.000Z' }),
    ];
    const result = computeProcessingBreakdown(
      { status: 'evidence_gathering', createdAt: T0 },
      events,
    );
    for (const phase of result.phases) {
      expect(phase.durationMs).toBeGreaterThanOrEqual(0);
    }
  });

  it('returns an empty breakdown for an invalid createdAt rather than throwing', () => {
    const result = computeProcessingBreakdown(
      { status: 'pending_review', createdAt: 'not-a-date' },
      [],
    );
    expect(result.phases).toEqual([]);
    expect(result.totalMs).toBe(0);
  });
});
