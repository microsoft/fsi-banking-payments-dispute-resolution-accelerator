import { Text, tokens } from '@fluentui/react-components';
import { formatDuration } from '../utils/duration';
import type { ProcessingBreakdown, StagePhase } from '../utils/processingTimeline';

interface ProcessingTimelineProps {
  breakdown: ProcessingBreakdown;
}

const PHASE_COLORS: Record<StagePhase['key'], string> = {
  intake: tokens.colorPaletteBlueBorderActive,
  evidence_gathering: tokens.colorPaletteTealBorderActive,
  ai_drafting: tokens.colorPalettePurpleBorderActive,
  analyst_review: tokens.colorPaletteMarigoldBorderActive,
  in_progress: tokens.colorBrandForeground1,
};

// Minimum visual width so short phases (e.g. a 15-minute AI draft) remain visible
// and clickable alongside multi-day phases.
const MIN_SEGMENT_PCT = 4;

/**
 * Horizontal Gantt-style bar showing how long a dispute spent in each
 * processing phase, plus a legend with exact durations. Degrades to a single
 * "In Progress" / "Total Processing Time" segment when no phase-boundary
 * timeline events are available (see utils/processingTimeline.ts).
 */
export function ProcessingTimeline({ breakdown }: ProcessingTimelineProps) {
  const { phases, totalMs, resolved } = breakdown;

  if (phases.length === 0 || totalMs <= 0) {
    return (
      <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
        Not enough data to compute a processing timeline yet.
      </Text>
    );
  }

  // Rescale so every segment gets at least MIN_SEGMENT_PCT width, without
  // exceeding 100% total (proportionally shrink the remainder).
  const rawPcts = phases.map((p) => (totalMs > 0 ? (p.durationMs / totalMs) * 100 : 0));
  const boosted = rawPcts.map((pct) => Math.max(pct, phases.length > 1 ? MIN_SEGMENT_PCT : 100));
  const boostedTotal = boosted.reduce((a, b) => a + b, 0);
  const widths = boosted.map((pct) => (pct / boostedTotal) * 100);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '8px' }}>
        <Text weight="semibold" size={300}>
          Processing Timeline
        </Text>
        <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
          {resolved ? 'Total: ' : 'Elapsed so far: '}
          <span style={{ fontWeight: 600, color: tokens.colorNeutralForeground1 }}>{formatDuration(totalMs)}</span>
        </Text>
      </div>

      {/* Segmented bar */}
      <div
        style={{
          display: 'flex',
          height: '22px',
          borderRadius: '5px',
          overflow: 'hidden',
          border: `1px solid ${tokens.colorNeutralStroke2}`,
        }}
      >
        {phases.map((phase, i) => (
          <div
            key={phase.key}
            title={`${phase.label}: ${formatDuration(phase.durationMs)}${phase.ongoing ? ' (ongoing)' : ''}`}
            style={{
              width: `${widths[i]}%`,
              background: PHASE_COLORS[phase.key],
              opacity: phase.ongoing ? 0.55 : 1,
              backgroundImage: phase.ongoing
                ? 'repeating-linear-gradient(45deg, rgba(255,255,255,0.25) 0, rgba(255,255,255,0.25) 4px, transparent 4px, transparent 8px)'
                : undefined,
              borderRight: i < phases.length - 1 ? `1px solid ${tokens.colorNeutralBackground1}` : undefined,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {widths[i] > 10 && (
              <Text size={100} style={{ color: 'white', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {formatDuration(phase.durationMs)}
              </Text>
            )}
          </div>
        ))}
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px 16px', marginTop: '10px' }}>
        {phases.map((phase) => (
          <div key={phase.key} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span
              style={{
                width: '10px',
                height: '10px',
                borderRadius: '2px',
                background: PHASE_COLORS[phase.key],
                opacity: phase.ongoing ? 0.55 : 1,
                display: 'inline-block',
              }}
            />
            <Text size={200}>
              {phase.label}
              {phase.ongoing ? ' (current)' : ''}
            </Text>
            <Text size={200} weight="semibold" style={{ color: tokens.colorNeutralForeground3 }}>
              {formatDuration(phase.durationMs)}
            </Text>
          </div>
        ))}
      </div>
    </div>
  );
}
