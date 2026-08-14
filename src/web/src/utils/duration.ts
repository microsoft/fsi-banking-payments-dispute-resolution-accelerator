/** Shared human-readable duration formatting for the dispute-processing timeline. */

/** Format a millisecond duration as a compact human-readable string (e.g. "15m", "2.3h", "6.1d"). */
export function formatDuration(ms: number): string {
  const totalHours = ms / 3_600_000;
  if (totalHours < 1) return `${Math.max(1, Math.round(ms / 60_000))}m`;
  if (totalHours < 24) return `${totalHours.toFixed(1)}h`;
  const days = totalHours / 24;
  return `${days.toFixed(1)}d`;
}
