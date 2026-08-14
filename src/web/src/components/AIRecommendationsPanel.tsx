import {
  Button,
  Spinner,
  Text,
  Textarea,
  Title3,
  tokens,
} from '@fluentui/react-components';
import { useState } from 'react';
import { postRecommendationResponse } from '../api/cases';
import type { Case } from '../types/case';

interface AIRecommendationsPanelProps {
  disputeCase: Case;
  onRecommendationRecorded?: () => void;
}

type Disposition = 'Fight' | 'Accept Loss' | 'Negotiate' | 'Escalate';
type ActionState = 'pending' | 'accepted' | 'rejected' | 'modifying';

interface Recommendation {
  disposition: Disposition;
  confidence: number;
  reasoning: string[];
}

function deriveRecommendation(c: Case): Recommendation {
  const win = c.winProbability ?? 0.5;
  const gapCount = c.evidenceGaps?.length ?? 0;
  const evidenceCount = c.evidence?.length ?? 0;
  const completeness = evidenceCount > 0 ? evidenceCount / (evidenceCount + gapCount) : 0;

  let disposition: Disposition;
  let confidence: number;
  const reasoning: string[] = [];

  if (win >= 0.7 && completeness >= 0.7) {
    disposition = 'Fight';
    confidence = Math.round((win * 0.6 + completeness * 0.4) * 100);
    reasoning.push(`Win probability is strong at ${Math.round(win * 100)}%`);
    reasoning.push(`Evidence completeness is ${Math.round(completeness * 100)}% — sufficient for representment`);
    if (c.rebuttalDraft) reasoning.push('AI-generated rebuttal draft is available for review');
  } else if (win < 0.3) {
    disposition = 'Accept Loss';
    confidence = Math.round((1 - win) * 0.7 * 100);
    reasoning.push(`Win probability is low at ${Math.round(win * 100)}%`);
    if (gapCount > 0) reasoning.push(`${gapCount} critical evidence gap(s) remain unresolved`);
    reasoning.push('Cost of continued pursuit likely exceeds recovery value');
  } else if (win >= 0.3 && win < 0.5 && gapCount > 0) {
    disposition = 'Negotiate';
    confidence = Math.round(55 + (completeness * 20));
    reasoning.push(`Moderate win probability (${Math.round(win * 100)}%) with evidence gaps`);
    reasoning.push('Partial settlement may recover more than full dispute cycle');
    reasoning.push(`${gapCount} evidence gap(s) make full representment risky`);
  } else {
    disposition = 'Escalate';
    confidence = Math.round(50 + (win * 30));
    reasoning.push(`Win probability of ${Math.round(win * 100)}% warrants senior review`);
    if (c.riskLevel === 'critical' || c.riskLevel === 'high') {
      reasoning.push(`Risk level is ${c.riskLevel} — requires additional oversight`);
    }
    reasoning.push('Additional evidence gathering or strategic decision needed');
  }

  return { disposition, confidence: Math.min(confidence, 95), reasoning };
}

const dispositionColors: Record<Disposition, string> = {
  'Fight': tokens.colorPaletteGreenForeground1,
  'Accept Loss': tokens.colorPaletteRedForeground1,
  'Negotiate': tokens.colorPaletteYellowForeground1,
  'Escalate': tokens.colorPaletteBlueBorderActive,
};

const dispositionIcons: Record<Disposition, string> = {
  'Fight': '⚔️',
  'Accept Loss': '🏳️',
  'Negotiate': '🤝',
  'Escalate': '⬆️',
};

export function AIRecommendationsPanel({ disputeCase, onRecommendationRecorded }: AIRecommendationsPanelProps) {
  const recommendation = deriveRecommendation(disputeCase);
  const [actionState, setActionState] = useState<ActionState>('pending');
  const [rejectReason, setRejectReason] = useState('');
  const [modifiedRecommendation, setModifiedRecommendation] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const analystId = disputeCase.assignedAnalystId || 'demo-analyst';

  async function saveDecision(decision: 'accept' | 'reject' | 'modify', comment?: string, modified?: string) {
    setSaving(true);
    setError(null);
    try {
      await postRecommendationResponse(disputeCase.caseId, {
        analystId,
        decision,
        recommendationDisposition: recommendation.disposition,
        recommendationConfidence: recommendation.confidence,
        reasoning: recommendation.reasoning,
        comment,
        modifiedRecommendation: modified,
      });
      if (decision === 'accept') {
        setActionState('accepted');
      } else {
        setActionState('pending');
      }
      onRecommendationRecorded?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save recommendation response.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <Title3 style={{ marginBottom: '12px' }}>AI Recommendation</Title3>

      {/* Disposition badge */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          padding: '12px 16px',
          borderRadius: '8px',
          border: `2px solid ${dispositionColors[recommendation.disposition]}`,
          marginBottom: '12px',
        }}
      >
        <span style={{ fontSize: '24px' }}>{dispositionIcons[recommendation.disposition]}</span>
        <div>
          <Text weight="bold" size={500} style={{ color: dispositionColors[recommendation.disposition] }}>
            {recommendation.disposition}
          </Text>
          <Text size={200} style={{ display: 'block', color: tokens.colorNeutralForeground3 }}>
            Confidence: {recommendation.confidence}%
          </Text>
        </div>
        {/* Confidence bar */}
        <div style={{ flex: 1, marginLeft: '8px' }}>
          <div
            style={{
              height: '6px',
              borderRadius: '3px',
              background: tokens.colorNeutralStroke2,
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                height: '100%',
                width: `${recommendation.confidence}%`,
                background: dispositionColors[recommendation.disposition],
                borderRadius: '3px',
                transition: 'width 0.3s',
              }}
            />
          </div>
        </div>
      </div>

      {/* Reasoning */}
      <div style={{ marginBottom: '14px' }}>
        <Text weight="semibold" size={200} style={{ display: 'block', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.5px', color: tokens.colorNeutralForeground3 }}>
          Reasoning
        </Text>
        <ul style={{ margin: 0, paddingLeft: '16px' }}>
          {recommendation.reasoning.map((r, i) => (
            <li key={i} style={{ marginBottom: '4px' }}>
              <Text size={200}>{r}</Text>
            </li>
          ))}
        </ul>
      </div>

      {/* Action buttons / State */}
      {actionState === 'pending' && (
        <div style={{ display: 'flex', gap: '8px' }}>
          <Button appearance="primary" size="small" disabled={saving} onClick={() => void saveDecision('accept')}>
            {saving ? <Spinner size="tiny" /> : '✓ Accept'}
          </Button>
          <Button appearance="outline" size="small" disabled={saving} onClick={() => setActionState('rejected')}>
            ✗ Reject
          </Button>
          <Button
            appearance="subtle"
            size="small"
            disabled={saving}
            onClick={() => {
              setModifiedRecommendation(`${recommendation.disposition}: ${recommendation.reasoning.join('. ')}`);
              setActionState('modifying');
            }}
          >
            ✎ Modify
          </Button>
        </div>
      )}

      {actionState === 'accepted' && (
        <div
          style={{
            padding: '10px 14px',
            borderRadius: '6px',
            background: tokens.colorPaletteGreenBackground1,
            border: `1px solid ${tokens.colorPaletteGreenBorder1}`,
          }}
        >
          <Text size={200} weight="semibold" style={{ color: tokens.colorPaletteGreenForeground1 }}>
            ✓ Recommendation accepted
          </Text>
        </div>
      )}

      {actionState === 'rejected' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <Textarea
            placeholder="Provide reason for rejecting this recommendation…"
            value={rejectReason}
            onChange={(_, data) => setRejectReason(data.value)}
            resize="vertical"
            style={{ minHeight: '60px' }}
          />
          <div style={{ display: 'flex', gap: '8px' }}>
            <Button
              appearance="primary"
              size="small"
              disabled={!rejectReason.trim() || saving}
              onClick={() => void saveDecision('reject', rejectReason.trim())}
            >
              {saving ? <Spinner size="tiny" /> : 'Submit Rejection'}
            </Button>
            <Button appearance="subtle" size="small" disabled={saving} onClick={() => setActionState('pending')}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      {actionState === 'modifying' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <Textarea
            placeholder="Modify the recommendation…"
            value={modifiedRecommendation}
            onChange={(_, data) => setModifiedRecommendation(data.value)}
            resize="vertical"
            style={{ minHeight: '60px' }}
          />
          <div style={{ display: 'flex', gap: '8px' }}>
            <Button
              appearance="primary"
              size="small"
              disabled={!modifiedRecommendation.trim() || saving}
              onClick={() => void saveDecision('modify', undefined, modifiedRecommendation.trim())}
            >
              {saving ? <Spinner size="tiny" /> : 'Save Modified Recommendation'}
            </Button>
            <Button appearance="subtle" size="small" disabled={saving} onClick={() => setActionState('pending')}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      {error && (
        <div
          style={{
            marginTop: '10px',
            padding: '10px 12px',
            borderRadius: '6px',
            border: `1px solid ${tokens.colorPaletteRedBorder1}`,
            background: tokens.colorPaletteRedBackground1,
          }}
        >
          <Text size={200} style={{ color: tokens.colorPaletteRedForeground1 }}>
            {error}
          </Text>
        </div>
      )}
    </div>
  );
}
