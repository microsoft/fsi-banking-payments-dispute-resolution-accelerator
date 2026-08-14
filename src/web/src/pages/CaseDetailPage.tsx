import {
  Button,
  MessageBar,
  MessageBarBody,
  MessageBarTitle,
  Spinner,
  Text,
  Title1,
  Title2,
  tokens,
} from '@fluentui/react-components';
import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { getCase, getCases, getTimeline, fetchEvidenceGaps, reprocessDispute } from '../api/cases';
import { AIRecommendationsPanel } from '../components/AIRecommendationsPanel';
import { ActionBar } from '../components/ActionBar';
import { CollaborationWorkspace } from '../components/CollaborationWorkspace';
import { StatusBadge } from '../components/CaseBadges';
import { CaseMetadata } from '../components/CaseMetadata';
import { DeadlineCountdown } from '../components/DeadlineCountdown';
import { DecisionInsights } from '../components/DecisionInsights';
import { EvidenceGapsPanel } from '../components/EvidenceGapsPanel';
import { EvidencePanel } from '../components/EvidencePanel';
import { useNotifications } from '../components/NotificationProvider';
import { ReasonCodeChecklist } from '../components/ReasonCodeChecklist';
import { ReasonCodeGuidance } from '../components/ReasonCodeGuidance';
import { PrecedentsPanel } from '../components/PrecedentsPanel';
import { RebuttalPanel } from '../components/RebuttalPanel';
import { RelatedCasesPanel } from '../components/RelatedCasesPanel';
import { SLAProgressBar } from '../components/SLAProgressBar';
import { TimeToScore } from '../components/TimeToScore';
import { WinProbGauge } from '../components/WinProbGauge';
import type { Case, CaseStatus, CaseSummary, TimelineEvent } from '../types/case';
import { computeTimeToScore } from '../utils/timeToScore';

const FINAL_STATUSES: ReadonlySet<CaseStatus> = new Set(['approved', 'denied', 'submitted', 'expired', 'closed']);

function deriveEffectiveStatus(disputeCase: Case, timeline: TimelineEvent[]): CaseStatus {
  if (FINAL_STATUSES.has(disputeCase.status)) {
    return disputeCase.status;
  }

  // Use the newest timeline status signal when available.
  const sorted = [...timeline].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
  );

  for (const event of sorted) {
    if (event.eventType !== 'status_changed' && event.eventType !== 'status_change') {
      continue;
    }
    const metadata = (event.metadata ?? {}) as Record<string, unknown>;
    const candidates = [metadata.toStatus, metadata.to, metadata.status]
      .filter((v): v is string => typeof v === 'string')
      .map((v) => v.toLowerCase());

    const matched = candidates.find((value): value is CaseStatus => FINAL_STATUSES.has(value as CaseStatus));
    if (matched) {
      return matched;
    }
  }

  // Closure artifacts and resolved timestamp are authoritative closure markers.
  if (sorted.some((event) => event.eventType === 'case_closed_artifact_created') || disputeCase.resolvedAt) {
    return 'closed';
  }

  return disputeCase.status;
}

/** Thin card wrapper for each detail section */
function SectionCard({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        background: tokens.colorNeutralBackground1,
        border: `1px solid ${tokens.colorNeutralStroke2}`,
        borderRadius: '8px',
        padding: '20px 24px',
      }}
    >
      {children}
    </div>
  );
}

export function CaseDetailPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const { notifyWarning, notifyError: notifyDanger, notifySuccess } = useNotifications();

  const [disputeCase, setDisputeCase] = useState<Case | null>(null);
  const [allCases, setAllCases] = useState<CaseSummary[]>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [, setTimelineLoading] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reprocessing, setReprocessing] = useState(false);

  const effectiveStatus = disputeCase ? deriveEffectiveStatus(disputeCase, timeline) : undefined;
  const isResolvedCase = effectiveStatus ? FINAL_STATUSES.has(effectiveStatus) : false;

  // ── SLA deadline warning toasts ────────────────────────────────────────────
  useEffect(() => {
    if (!disputeCase || isResolvedCase) return;
    const days = disputeCase.deadline?.daysRemaining;
    if (days === undefined) return;

    if (days <= 0) {
      notifyDanger(
        '⚠️ SLA OVERDUE',
        `This case is past its ${disputeCase.cardNetwork?.toUpperCase()} deadline (${disputeCase.deadline.dueDate}). Immediate action required.`
      );
    } else if (days <= 3) {
      notifyDanger(
        `⏰ ${days} day${days === 1 ? '' : 's'} until SLA deadline`,
        `Case must be resolved by ${disputeCase.deadline.dueDate}. Submit rebuttal or take action now.`
      );
    } else if (days <= 7) {
      notifyWarning(
        `📋 SLA deadline approaching`,
        `${days} days remaining (due ${disputeCase.deadline.dueDate}). Ensure evidence is complete.`
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [disputeCase?.caseId, isResolvedCase]);

  useEffect(() => {
    if (!caseId) {
      setError('Invalid case ID.');
      setLoading(false);
      return;
    }
    let cancelled = false;
    setError(null);
    setDisputeCase(null);
    setTimeline([]);
    setLoading(true);
    setTimelineLoading(true);

    Promise.all([getCase(caseId), getCases()])
      .then(([caseData, casesData]) => {
        if (!cancelled) {
          setDisputeCase(caseData);
          setAllCases(casesData);
          setLoading(false);

          // Fetch dynamic evidence gaps if case has a reason code
          if (caseData.cardNetwork && caseData.reasonCode) {
            const codePart = caseData.reasonCode.replace(/^(visa|mastercard|amex|discover)\s*/i, '').trim();
            const gatheredTypes = (caseData.evidence ?? []).map(e => e.type);
            fetchEvidenceGaps(caseData.cardNetwork, codePart, gatheredTypes)
              .then(gaps => {
                if (!cancelled && gaps.length > 0) {
                  setDisputeCase(prev => prev ? { ...prev, evidenceGaps: gaps } : prev);
                }
              });
          }
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load case.');
          setLoading(false);
        }
      });

    getTimeline(caseId)
      .then((events) => {
        if (!cancelled) {
          setTimeline(events);
          setTimelineLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) setTimelineLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [caseId]);

  const handleActionComplete = (newStatus: CaseStatus) => {
    setDisputeCase((prev) => (prev ? { ...prev, status: newStatus } : prev));
    if (caseId) {
      getTimeline(caseId).then(setTimeline).catch(() => undefined);
    }
  };

  const refreshTimeline = () => {
    if (!caseId) return;
    getTimeline(caseId).then(setTimeline).catch(() => undefined);
  };

  const handleReprocess = async () => {
    if (!caseId || reprocessing) return;
    setReprocessing(true);
    try {
      const result = await reprocessDispute(caseId);
      setDisputeCase((prev) =>
        prev
          ? {
              ...prev,
              reasonCodeChecklist: result.gaps.reasonCodeChecklist,
              evidenceGaps: result.gaps.evidenceGaps,
              winProbability: result.score.winProbability,
              riskLevel: result.score.riskLevel,
              rebuttalDraft: { text: result.rebuttal.rebuttalText, citations: result.rebuttal.citations },
              updatedAt: result.reprocessedAt,
            }
          : prev
      );
      // Refresh the timeline so the new "reprocessed" event shows up.
      getTimeline(caseId).then(setTimeline).catch(() => undefined);
      notifySuccess(
        '🔄 Dispute reprocessed',
        `Evidence ${result.evidence.totalRetrieved}/${result.evidence.totalRequired} retrieved · ` +
          `win probability ${Math.round(result.score.winProbability * 100)}% (${result.score.riskLevel} risk) · ` +
          `rebuttal redrafted (${result.rebuttal.source}).`
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Reprocess failed. Please try again.';
      notifyDanger('Reprocess failed', msg);
    } finally {
      setReprocessing(false);
    }
  };

  const pageStyle: React.CSSProperties = {
    maxWidth: '1400px',
    margin: '0 auto',
    padding: '20px 16px',
    fontFamily: 'var(--fontFamilyBase)',
  };

  if (loading) {
    return (
      <div style={{ ...pageStyle, display: 'flex', alignItems: 'center', justifyContent: 'center', paddingTop: '80px' }}>
        <Spinner size="large" label="Loading case…" />
      </div>
    );
  }

  if (error || !disputeCase) {
    return (
      <div style={pageStyle}>
        <MessageBar intent="error">
          <MessageBarBody>
            <MessageBarTitle>Error</MessageBarTitle>
            {error ?? 'Case not found.'}
          </MessageBarBody>
        </MessageBar>
      </div>
    );
  }

  const c: Case = {
    ...disputeCase,
    status: effectiveStatus ?? disputeCase.status,
  };
  const amount = c.transactionAmount !== undefined ? `$${c.transactionAmount.toFixed(2)}` : '—';

  return (
    <div style={pageStyle}>
      {/* ── Header Bar ── */}
      <SectionCard>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
              <Title1 as="h1">{c.merchantName ?? 'Unknown Merchant'}</Title1>
              <StatusBadge status={c.status} />
            </div>
            <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: 'block' }}>
              Case ID: {c.caseId}
            </Text>
            <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
              {c.reasonCode} · {c.reasonCodeLabel}
            </Text>
            {c.caseDescription && (
              <Text size={300} style={{ color: tokens.colorNeutralForeground2, display: 'block', marginTop: '8px', maxWidth: '720px' }}>
                {c.caseDescription}
              </Text>
            )}
            <div style={{ marginTop: '10px' }}>
              <Button
                appearance="secondary"
                size="small"
                disabled={reprocessing}
                onClick={() => void handleReprocess()}
                icon={reprocessing ? <Spinner size="tiny" /> : undefined}
              >
                {reprocessing ? 'Reprocessing…' : '🔄 Re-run AI Pipeline'}
              </Button>
              <Text
                size={100}
                style={{ display: 'block', marginTop: '4px', color: tokens.colorNeutralForeground3, maxWidth: '360px' }}
              >
                Re-retrieves evidence, re-checks gaps, rescores win probability, and redrafts the rebuttal.
              </Text>
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <Title2 style={{ display: 'block' }}>{amount}</Title2>
            {c.transactionDate && (
              <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
                {c.cardNetwork?.toUpperCase()} · {c.transactionDate}
              </Text>
            )}
            <div style={{ marginTop: '4px' }}>
              <DeadlineCountdown
                daysRemaining={c.deadline.daysRemaining}
                dueDate={c.deadline.dueDate}
                closed={isResolvedCase}
              />
            </div>
          </div>
        </div>
      </SectionCard>

      {/* ── 2-Column Layout ── */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 360px',
          gap: '16px',
          marginTop: '16px',
          alignItems: 'start',
        }}
      >
        {/* ═══ LEFT COLUMN: Primary content ═══ */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

          {/* SLA Progress */}
          <SectionCard>
            <SLAProgressBar
              status={c.status}
              cardNetwork={c.cardNetwork}
              dueDate={c.deadline.dueDate}
              daysRemaining={c.deadline.daysRemaining}
              createdAt={c.createdAt}
              resolvedAt={c.resolvedAt}
              timelineEvents={timeline}
            />
          </SectionCard>

          {/* Time to Score — headline speed metric: intake -> first AI score */}
          <SectionCard>
            <TimeToScore result={computeTimeToScore(c.createdAt, timeline)} />
          </SectionCard>

          {/* Win Probability + Decision Support */}
          {c.winProbability !== undefined && (
            <SectionCard>
              <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: '20px', alignItems: 'start' }}>
                <WinProbGauge winProbability={c.winProbability} riskLevel={c.riskLevel} />
                <DecisionInsights
                  winProbability={c.winProbability}
                  riskLevel={c.riskLevel}
                  evidence={c.evidence}
                  evidenceGaps={c.evidenceGaps}
                  cardNetwork={c.cardNetwork}
                  transactionAmount={c.transactionAmount}
                />
              </div>
            </SectionCard>
          )}

          {/* AI Recommendations */}
          {c.winProbability !== undefined && (
            <SectionCard>
              <AIRecommendationsPanel disputeCase={c} onRecommendationRecorded={refreshTimeline} />
            </SectionCard>
          )}

          {/* Evidence */}
          <SectionCard>
            <EvidencePanel
              caseId={c.caseId}
              evidence={c.evidence ?? []}
              timelineEvents={timeline}
              currentAnalystId={c.assignedAnalystId}
              currentAnalystName={c.assignedAnalystName}
              onTimelineRefresh={refreshTimeline}
            />
          </SectionCard>

          {/* Evidence Gaps */}
          {c.evidenceGaps && c.evidenceGaps.length > 0 && (
            <SectionCard>
              <EvidenceGapsPanel
                caseId={c.caseId}
                analystId={c.assignedAnalystId}
                gaps={c.evidenceGaps}
                timelineEvents={timeline}
                onGapRequested={refreshTimeline}
              />
            </SectionCard>
          )}

          {/* Reason Code Guidance */}
          <SectionCard>
            <ReasonCodeGuidance
              reasonCode={c.reasonCode}
              reasonCodeLabel={c.reasonCodeLabel}
              cardNetwork={c.cardNetwork}
              daysRemaining={c.deadline?.daysRemaining}
            />
          </SectionCard>

          {/* Precedents & Network Rules (Evidence Retrieval Agent, #12) */}
          <SectionCard>
            <PrecedentsPanel
              caseId={c.caseId}
              network={c.cardNetwork}
              reasonCode={c.reasonCode}
            />
          </SectionCard>

          {/* Rebuttal Draft */}
          {c.rebuttalDraft && (
            <SectionCard>
              <RebuttalPanel rebuttal={c.rebuttalDraft} />
            </SectionCard>
          )}

          {/* Reason Code Checklist */}
          {c.reasonCodeChecklist && c.reasonCodeChecklist.length > 0 && (
            <SectionCard>
              <ReasonCodeChecklist
                reasonCode={c.reasonCode}
                reasonCodeLabel={c.reasonCodeLabel}
                items={c.reasonCodeChecklist}
              />
            </SectionCard>
          )}

          {/* Action Bar */}
          <SectionCard>
            <ActionBar
              caseId={c.caseId}
              currentStatus={c.status}
              onActionComplete={handleActionComplete}
              onNoteAdded={() => refreshTimeline()}
            />
          </SectionCard>
        </div>
        {/* ═══ RIGHT COLUMN: Sidebar ═══ */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

          {/* Case Metadata */}
          <SectionCard>
            <CaseMetadata disputeCase={c} />
          </SectionCard>

          {/* Collaboration Workspace */}
          <SectionCard>
            <CollaborationWorkspace
              caseId={c.caseId}
              currentAnalystId={c.assignedAnalystId}
              currentAnalystName={c.assignedAnalystName}
              timelineEvents={timeline}
              onTimelineRefresh={refreshTimeline}
              onAssign={(id, name) => {
                setDisputeCase((prev) => prev ? { ...prev, assignedAnalystId: id, assignedAnalystName: name } : prev);
              }}
            />
          </SectionCard>

          {/* Related Cases */}
          <SectionCard>
            <RelatedCasesPanel
              currentCaseId={c.caseId}
              merchantName={c.merchantName}
              cardholderName={c.cardholderName}
              allCases={allCases}
            />
          </SectionCard>
        </div>
      </div>
    </div>
  );
}
