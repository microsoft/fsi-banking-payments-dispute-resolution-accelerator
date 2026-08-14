import { Button, Text, Title3, tokens } from '@fluentui/react-components';
import { useMemo, useState } from 'react';
import { postEvidenceGapRequest } from '../api/cases';
import type { EvidenceGap, ImpactLevel } from '../types/case';
import type { TimelineEvent } from '../types/case';
import { ImpactBadge } from './CaseBadges';

interface EvidenceGapsPanelProps {
  caseId: string;
  analystId?: string;
  gaps: EvidenceGap[];
  timelineEvents?: TimelineEvent[];
  onGapRequested?: () => void;
}

const IMPACT_PRIORITY: Record<ImpactLevel, number> = { critical: 0, high: 1, medium: 2, low: 3 };

export function EvidenceGapsPanel({ caseId, analystId, gaps, timelineEvents, onGapRequested }: EvidenceGapsPanelProps) {
  const [requestedGaps, setRequestedGaps] = useState<Set<number>>(new Set());
  const [savingGaps, setSavingGaps] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const effectiveAnalystId = analystId || 'demo-analyst';

  if (gaps.length === 0) {
    return (
      <div>
        <Title3 style={{ marginBottom: '12px' }}>Evidence Gaps</Title3>
        <Text style={{ color: '#107C10' }}>✓ No evidence gaps identified.</Text>
      </div>
    );
  }

  // Sort by priority (critical first)
  const sortedGaps = [...gaps].sort((a, b) => IMPACT_PRIORITY[a.impact] - IMPACT_PRIORITY[b.impact]);
  const hasCritical = gaps.some((g) => g.impact === 'critical');

  const persistedRequestedItems = useMemo(() => {
    const requested = new Set<string>();
    for (const event of timelineEvents ?? []) {
      if (event.eventType !== 'evidence_gap_requested') continue;
      const eventWithData = event as TimelineEvent & { data?: Record<string, unknown> };
      const missingItem =
        (event.metadata?.missingItem as string | undefined) ||
        (eventWithData.data?.missingItem as string | undefined) ||
        '';
      if (missingItem.trim()) requested.add(missingItem.trim().toLowerCase());
    }
    return requested;
  }, [timelineEvents]);

  const resolvedCount = sortedGaps.filter((gap, idx) => {
    const localRequested = requestedGaps.has(idx);
    const persistedRequested = persistedRequestedItems.has(gap.missingItem.trim().toLowerCase());
    return localRequested || persistedRequested;
  }).length;
  const progressPct = Math.round((resolvedCount / gaps.length) * 100);

  const handleRequest = async (idx: number, gap: EvidenceGap) => {
    setError(null);
    setSavingGaps((prev) => new Set(prev).add(idx));
    try {
      await postEvidenceGapRequest(caseId, {
        analystId: effectiveAnalystId,
        missingItem: gap.missingItem,
        reason: gap.reason,
        impact: gap.impact,
        suggestedAction: gap.suggestedAction,
      });
      setRequestedGaps((prev) => new Set(prev).add(idx));
      onGapRequested?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to request evidence gap retrieval.');
    } finally {
      setSavingGaps((prev) => {
        const next = new Set(prev);
        next.delete(idx);
        return next;
      });
    }
  };

  return (
    <div>
      <Title3 style={{ marginBottom: '12px' }}>
        Evidence Gaps ({gaps.length}){hasCritical && ' ⚠️'}
      </Title3>

      {/* Progress indicator */}
      <div style={{ marginBottom: '12px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
          <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
            Resolution progress
          </Text>
          <Text size={200} weight="semibold">
            {resolvedCount}/{gaps.length} requested
          </Text>
        </div>
        <div style={{ height: '6px', borderRadius: '3px', background: tokens.colorNeutralStroke2, overflow: 'hidden' }}>
          <div
            style={{
              height: '100%',
              width: `${progressPct}%`,
              background: progressPct === 100 ? tokens.colorPaletteGreenBorder1 : tokens.colorBrandBackground,
              borderRadius: '3px',
              transition: 'width 0.3s',
            }}
          />
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {sortedGaps.map((gap, idx) => {
          const isRequested =
            requestedGaps.has(idx) || persistedRequestedItems.has(gap.missingItem.trim().toLowerCase());
          const isSaving = savingGaps.has(idx);
          return (
            <div
              key={idx}
              style={{
                padding: '12px 16px',
                border: `2px solid ${
                  isRequested ? tokens.colorPaletteGreenBorder1 :
                  gap.impact === 'critical' ? tokens.colorStatusDangerBorder1 :
                  gap.impact === 'high'     ? tokens.colorStatusWarningBorder1 :
                                              tokens.colorNeutralStroke2
                }`,
                borderRadius: '6px',
                background: isRequested
                  ? tokens.colorPaletteGreenBackground1
                  : gap.impact === 'critical' ? tokens.colorStatusDangerBackground1 : undefined,
                opacity: isRequested ? 0.7 : 1,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                <ImpactBadge level={gap.impact} />
                <Text weight="semibold">{gap.missingItem}</Text>
                {isRequested && (
                  <Text size={200} style={{ color: tokens.colorPaletteGreenForeground1, marginLeft: 'auto' }}>
                    ✓ Requested
                  </Text>
                )}
              </div>
              <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: 'block', marginBottom: gap.suggestedAction ? '8px' : '0' }}>
                {gap.reason}
              </Text>
              {gap.suggestedAction && !isRequested && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '6px' }}>
                  <Text size={200} style={{ color: tokens.colorBrandForeground1 }}>
                    💡 {gap.suggestedAction}
                  </Text>
                  <Button
                    appearance="primary"
                    size="small"
                    disabled={isSaving}
                    onClick={() => void handleRequest(idx, gap)}
                    style={{ marginLeft: 'auto' }}
                  >
                    {isSaving ? 'Requesting…' : 'Auto-Request'}
                  </Button>
                </div>
              )}
              {!gap.suggestedAction && !isRequested && (
                <Button
                  appearance="outline"
                  size="small"
                  disabled={isSaving}
                  onClick={() => void handleRequest(idx, gap)}
                  style={{ marginTop: '6px' }}
                >
                  {isSaving ? 'Requesting…' : 'Mark Requested'}
                </Button>
              )}
            </div>
          );
        })}
      </div>

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
