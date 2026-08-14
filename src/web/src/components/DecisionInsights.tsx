import { Text, tokens } from '@fluentui/react-components';
import type { CardNetwork, Evidence, EvidenceGap, RiskLevel } from '../types/case';

interface DecisionInsightsProps {
  winProbability?: number;
  riskLevel?: RiskLevel;
  evidence?: Evidence[];
  evidenceGaps?: EvidenceGap[];
  cardNetwork?: CardNetwork;
  transactionAmount?: number;
}

interface Factor {
  label: string;
  impact: 'positive' | 'negative' | 'neutral';
  weight: number; // 0-1
  description: string;
}

function computeFactors(props: DecisionInsightsProps): Factor[] {
  const { evidence = [], evidenceGaps = [], cardNetwork, transactionAmount } = props;
  const factors: Factor[] = [];

  // Evidence completeness
  const completeEvidence = evidence.filter((e) => e.completeness === 'complete').length;
  const totalEvidence = evidence.length;
  if (totalEvidence > 0) {
    const ratio = completeEvidence / totalEvidence;
    factors.push({
      label: 'Evidence Completeness',
      impact: ratio >= 0.8 ? 'positive' : ratio >= 0.5 ? 'neutral' : 'negative',
      weight: ratio,
      description: `${completeEvidence}/${totalEvidence} evidence items are complete`,
    });
  }

  // Evidence gaps
  const criticalGaps = evidenceGaps.filter((g) => g.impact === 'critical' || g.impact === 'high').length;
  if (evidenceGaps.length > 0) {
    factors.push({
      label: 'Evidence Gaps',
      impact: criticalGaps > 0 ? 'negative' : 'neutral',
      weight: Math.max(0, 1 - criticalGaps * 0.3),
      description: criticalGaps > 0
        ? `${criticalGaps} critical/high-impact gaps detected`
        : `${evidenceGaps.length} low-impact gaps (manageable)`,
    });
  } else {
    factors.push({
      label: 'Evidence Gaps',
      impact: 'positive',
      weight: 1,
      description: 'No evidence gaps detected',
    });
  }

  // Network bias
  const networkWinRates: Record<string, number> = {
    visa: 0.52,
    mastercard: 0.48,
    amex: 0.35,
    discover: 0.55,
  };
  if (cardNetwork) {
    const rate = networkWinRates[cardNetwork] ?? 0.5;
    factors.push({
      label: 'Network Historical Win Rate',
      impact: rate >= 0.5 ? 'positive' : 'negative',
      weight: rate,
      description: `${cardNetwork.toUpperCase()} disputes have ~${Math.round(rate * 100)}% historical win rate`,
    });
  }

  // Transaction amount risk
  if (transactionAmount !== undefined) {
    const isHigh = transactionAmount > 2000;
    factors.push({
      label: 'Transaction Amount',
      impact: isHigh ? 'negative' : 'positive',
      weight: isHigh ? 0.4 : 0.8,
      description: isHigh
        ? `High-value ($${transactionAmount.toFixed(0)}) — increased scrutiny from network`
        : `Standard amount ($${transactionAmount.toFixed(0)}) — typical processing`,
    });
  }

  // Source system diversity
  const uniqueSources = new Set(evidence.map((e) => e.sourceSystem)).size;
  if (uniqueSources >= 3) {
    factors.push({
      label: 'Multi-Source Corroboration',
      impact: 'positive',
      weight: 0.85,
      description: `Evidence from ${uniqueSources} different source systems strengthens case`,
    });
  } else if (uniqueSources === 1 && totalEvidence > 0) {
    factors.push({
      label: 'Single Source Risk',
      impact: 'negative',
      weight: 0.4,
      description: 'All evidence from one source — consider gathering from additional systems',
    });
  }

  return factors;
}

function getRecommendedAction(winProb: number, riskLevel?: RiskLevel): { action: string; reasoning: string } {
  if (winProb >= 0.75) {
    return {
      action: '✅ Recommend: Approve & Submit',
      reasoning: 'High win probability with strong evidence. Submit rebuttal to network.',
    };
  }
  if (winProb >= 0.5 && riskLevel !== 'critical') {
    return {
      action: '📝 Recommend: Review & Strengthen',
      reasoning: 'Moderate probability — review evidence gaps and strengthen rebuttal before submission.',
    };
  }
  if (winProb >= 0.35) {
    return {
      action: '⚡ Recommend: Escalate for Senior Review',
      reasoning: 'Borderline case — escalate to senior analyst for strategic decision.',
    };
  }
  return {
    action: '🚫 Recommend: Consider Denial',
    reasoning: 'Low win probability. Assess whether pursuing is cost-effective given the evidence gaps.',
  };
}

export function DecisionInsights(props: DecisionInsightsProps) {
  const { winProbability, riskLevel } = props;
  const factors = computeFactors(props);
  const recommendation = getRecommendedAction(winProbability ?? 0, riskLevel);

  return (
    <div>
      <Text weight="semibold" size={400} style={{ display: 'block', marginBottom: '12px' }}>
        Decision Support
      </Text>

      {/* Recommendation Banner */}
      <div
        style={{
          background: (winProbability ?? 0) >= 0.5
            ? tokens.colorPaletteGreenBackground1
            : (winProbability ?? 0) >= 0.35
              ? tokens.colorPaletteYellowBackground1
              : tokens.colorPaletteRedBackground1,
          border: `1px solid ${(winProbability ?? 0) >= 0.5
            ? tokens.colorPaletteGreenBorder1
            : (winProbability ?? 0) >= 0.35
              ? tokens.colorPaletteYellowBorder1
              : tokens.colorPaletteRedBorder1}`,
          borderRadius: '6px',
          padding: '10px 14px',
          marginBottom: '14px',
        }}
      >
        <Text weight="semibold" size={300} style={{ display: 'block' }}>
          {recommendation.action}
        </Text>
        <Text size={200} style={{ display: 'block', marginTop: '4px' }}>
          {recommendation.reasoning}
        </Text>
      </div>

      {/* Factor Breakdown */}
      <Text weight="semibold" size={200} style={{ display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.5px', color: tokens.colorNeutralForeground3 }}>
        Independent Decision Signals
      </Text>

      <Text size={100} style={{ display: 'block', marginBottom: '8px', color: tokens.colorNeutralForeground3 }}>
        These are standalone signals used to explain the recommendation. They do not represent a percentage breakdown and will not add up to 100%.
      </Text>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {factors.map((factor, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {/* Impact indicator */}
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background:
                  factor.impact === 'positive'
                    ? tokens.colorPaletteGreenBorderActive
                    : factor.impact === 'negative'
                      ? tokens.colorPaletteRedBorderActive
                      : tokens.colorPaletteYellowBorderActive,
                flexShrink: 0,
              }}
            />
            {/* Bar */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
                <Text size={200} weight="semibold">{factor.label}</Text>
                <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>
                  {Math.round(factor.weight * 100)}%
                </Text>
              </div>
              <div
                style={{
                  height: '4px',
                  borderRadius: '2px',
                  background: tokens.colorNeutralBackground4,
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    height: '100%',
                    width: `${factor.weight * 100}%`,
                    borderRadius: '2px',
                    background:
                      factor.impact === 'positive'
                        ? tokens.colorPaletteGreenBorderActive
                        : factor.impact === 'negative'
                          ? tokens.colorPaletteRedBorderActive
                          : tokens.colorPaletteYellowBorderActive,
                  }}
                />
              </div>
              <Text size={100} style={{ color: tokens.colorNeutralForeground3, display: 'block', marginTop: '1px' }}>
                {factor.description}
              </Text>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
