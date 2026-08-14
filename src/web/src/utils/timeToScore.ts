/**
 * Computes "Time to Score" — the elapsed time from when a dispute was
 * created to the moment the AI scoring agent generated its first
 * win-probability score. This is the headline speed metric for the case
 * detail page: the PRD's value proposition is that this happens in minutes,
 * not days, so it's called out on its own rather than buried in the
 * phase-by-phase Processing Timeline.
 *
 * Looks for a ``score_generated`` timeline event (emitted by the triage
 * agent at intake, or the scoring/reprocess endpoints on a rescore). Uses
 * the EARLIEST such event, so re-scoring later does not overwrite the
 * original "time to first score" metric.
 */
import type { TimelineEvent } from '../types/case';

export interface TimeToScoreResult {
  /** True if a score_generated event was found in the timeline. */
  found: boolean;
  /** Elapsed milliseconds from createdAt to the first score_generated event. */
  elapsedMs: number;
  /** ISO timestamp of the first score_generated event, if found. */
  scoredAt: string | null;
  /** Number of score_generated events in the timeline (1 = never rescored). */
  scoreEventCount: number;
}

export function computeTimeToScore(createdAt: string, events: TimelineEvent[]): TimeToScoreResult {
  const created = new Date(createdAt).getTime();
  if (Number.isNaN(created)) {
    return { found: false, elapsedMs: 0, scoredAt: null, scoreEventCount: 0 };
  }

  const scoreEvents = events
    .filter((e) => e.eventType === 'score_generated')
    .map((e) => ({ e, t: new Date(e.timestamp).getTime() }))
    .filter(({ t }) => !Number.isNaN(t))
    .sort((a, b) => a.t - b.t);

  if (scoreEvents.length === 0) {
    return { found: false, elapsedMs: 0, scoredAt: null, scoreEventCount: 0 };
  }

  const first = scoreEvents[0];
  return {
    found: true,
    elapsedMs: Math.max(0, first.t - created),
    scoredAt: first.e.timestamp,
    scoreEventCount: scoreEvents.length,
  };
}
