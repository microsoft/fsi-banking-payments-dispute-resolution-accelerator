import { Text } from '@fluentui/react-components';
import type { RiskLevel } from '../types/case';
import { RiskBadge } from './CaseBadges';

interface WinProbGaugeProps {
  winProbability: number;
  riskLevel?: RiskLevel;
}

export function WinProbGauge({ winProbability, riskLevel }: WinProbGaugeProps) {
  const pct = Math.round(winProbability * 100);
  const barColor =
    winProbability >= 0.7 ? '#107C10' :
    winProbability >= 0.4 ? '#C19C00' :
                             '#C50F1F';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', minWidth: '160px' }}>
      <Text size={200} weight="semibold" style={{ color: '#555' }} title="Projected likelihood of recovering the disputed amount based on evidence strength, network rules, and historical outcomes">Recovery Likelihood</Text>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
        <Text size={900} weight="bold" style={{ color: barColor, lineHeight: 1 }}>
          {pct}%
        </Text>
      </div>
      {/* Progress bar */}
      <div
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Win probability: ${pct}%`}
        style={{
          width: '100%',
          height: '10px',
          background: '#E0E0E0',
          borderRadius: '5px',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            background: barColor,
            transition: 'width 0.4s ease',
          }}
        />
      </div>
      {riskLevel && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Text size={200} style={{ color: '#555' }}>Risk:</Text>
          <RiskBadge level={riskLevel} />
        </div>
      )}
    </div>
  );
}
