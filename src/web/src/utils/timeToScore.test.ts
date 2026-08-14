import { describe, expect, it } from 'vitest';
import { computeTimeToScore } from './timeToScore';
import type { TimelineEvent } from '../types/case';

const T0 = '2026-06-01T00:00:00.000Z';

function ev(overrides: Partial<TimelineEvent>): TimelineEvent {
  return {
    eventId: overrides.eventId ?? 'e1',
    disputeId: 'case-1',
    eventType: 'score_generated',
    timestamp: T0,
    description: '',
    ...overrides,
  };
}

describe('computeTimeToScore', () => {
  it('returns not-found when there are no score_generated events', () => {
    const result = computeTimeToScore(T0, []);
    expect(result.found).toBe(false);
    expect(result.elapsedMs).toBe(0);
    expect(result.scoredAt).toBeNull();
    expect(result.scoreEventCount).toBe(0);
  });

  it('computes elapsed time from createdAt to the score_generated event', () => {
    const scoredAt = '2026-06-01T00:31:00.000Z'; // 31 minutes later
    const events = [ev({ timestamp: scoredAt })];
    const result = computeTimeToScore(T0, events);
    expect(result.found).toBe(true);
    expect(result.elapsedMs).toBe(31 * 60_000);
    expect(result.scoredAt).toBe(scoredAt);
    expect(result.scoreEventCount).toBe(1);
  });

  it('uses the EARLIEST score_generated event when there are multiple (rescoring)', () => {
    const first = '2026-06-01T00:14:00.000Z';
    const second = '2026-06-05T00:00:00.000Z';
    const events = [
      ev({ eventId: 'e2', timestamp: second }),
      ev({ eventId: 'e1', timestamp: first }),
    ];
    const result = computeTimeToScore(T0, events);
    expect(result.scoredAt).toBe(first);
    expect(result.elapsedMs).toBe(14 * 60_000);
    expect(result.scoreEventCount).toBe(2);
  });

  it('ignores non-score timeline events', () => {
    const events: TimelineEvent[] = [
      ev({ eventId: 'e1', eventType: 'case_created', timestamp: T0 }),
      ev({ eventId: 'e2', eventType: 'evidence_retrieved', timestamp: '2026-06-01T00:05:00.000Z' }),
    ];
    const result = computeTimeToScore(T0, events);
    expect(result.found).toBe(false);
  });

  it('never returns a negative elapsed time even with an out-of-order score event', () => {
    const beforeCreated = '2026-05-31T23:00:00.000Z'; // bad data: before createdAt
    const events = [ev({ timestamp: beforeCreated })];
    const result = computeTimeToScore(T0, events);
    expect(result.elapsedMs).toBeGreaterThanOrEqual(0);
  });

  it('returns not-found for an invalid createdAt rather than throwing', () => {
    const result = computeTimeToScore('not-a-date', [ev({ timestamp: T0 })]);
    expect(result.found).toBe(false);
  });

  it('ignores a score_generated event with an invalid timestamp', () => {
    const events = [ev({ timestamp: 'garbage' }), ev({ eventId: 'e2', timestamp: '2026-06-01T00:20:00.000Z' })];
    const result = computeTimeToScore(T0, events);
    expect(result.found).toBe(true);
    expect(result.scoredAt).toBe('2026-06-01T00:20:00.000Z');
  });
});
