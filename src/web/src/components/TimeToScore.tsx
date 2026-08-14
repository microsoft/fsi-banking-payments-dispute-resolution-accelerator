import { Text, tokens } from '@fluentui/react-components';
import { formatDuration } from '../utils/duration';
import type { TimeToScoreResult } from '../utils/timeToScore';

interface TimeToScoreProps {
  result: TimeToScoreResult;
}

/**
 * Headline "speed" callout: how long the AI pipeline took to go from
 * dispute intake to a computed win-probability score. Distinct from the
 * broader Processing Timeline (which breaks down every stage) — this is a
 * single, prominent number meant to make the PRD's core claim ("minutes,
 * not days") immediately visible on the case detail page.
 */
export function TimeToScore({ result }: TimeToScoreProps) {
  if (!result.found) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          padding: '10px 14px',
          borderRadius: '8px',
          background: tokens.colorNeutralBackground3,
        }}
      >
        <span style={{ fontSize: '20px' }}>⚡</span>
        <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
          No AI score generated yet for this case.
        </Text>
      </div>
    );
  }

  const isFast = result.elapsedMs < 3_600_000; // under 1 hour — the PRD's target

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '12px',
        padding: '12px 16px',
        borderRadius: '8px',
        background: isFast ? `${tokens.colorPaletteGreenBackground2}` : tokens.colorNeutralBackground3,
        border: `1px solid ${isFast ? tokens.colorPaletteGreenBorderActive : tokens.colorNeutralStroke2}`,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <span style={{ fontSize: '22px' }}>⚡</span>
        <div>
          <Text weight="semibold" size={400} style={{ display: 'block' }}>
            Time to Score: {formatDuration(result.elapsedMs)}
          </Text>
          <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
            From dispute intake to first AI win-probability score
            {result.scoreEventCount > 1 ? ` (rescored ${result.scoreEventCount - 1}× since)` : ''}
          </Text>
        </div>
      </div>
      {isFast && (
        <Text size={200} weight="semibold" style={{ color: tokens.colorPaletteGreenForeground1, whiteSpace: 'nowrap' }}>
          ✓ Under 1 hour
        </Text>
      )}
    </div>
  );
}
