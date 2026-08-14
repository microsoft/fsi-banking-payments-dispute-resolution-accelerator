import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Text,
  Title1,
  Title2,
  Body1,
  tokens,
  Button,
  Badge,
  Divider,
  Tooltip,
  Textarea,
} from '@fluentui/react-components';
import type { BadgeProps } from '@fluentui/react-components';
import { AppShell } from '../components/AppShell.tsx';
import { useAccount, useWizard } from '../App.tsx';
import { getStoredDisputes, setStoredDisputes } from '../utils/storedDisputes.ts';
import type { StoredDispute, AnalystComment } from '../utils/storedDisputes.ts';
import {
  getDispute,
  listCustomerDisputes,
  getCaseDocuments,
  getDisputeTimeline,
  submitCustomerResponse,
  cancelDispute,
  uploadDocument,
  type StoredCaseDocument,
  type TimelineEvent,
} from '../api/disputes.ts';
import { getCustomerId, getPreferredCardholderName } from '../utils/customerProfile.ts';
import { DEMO_CARDHOLDER_NAME } from '../mocks/transactions.ts';

const STATUS_CONFIG: Record<string, { label: string; color: BadgeProps['color']; icon: string }> = {
  intake:             { label: 'Received',              color: 'informative', icon: '📥' },
  evidence_gathering: { label: 'Gathering Evidence',    color: 'warning',     icon: '🔍' },
  ai_drafting:        { label: 'Drafting Rebuttal',     color: 'warning',     icon: '📝' },
  pending_review:     { label: 'Under Review',          color: 'warning',     icon: '👀' },
  approved:           { label: 'Resolved in Your Favor', color: 'success',    icon: '✅' },
  denied:             { label: 'Denied',                color: 'danger',      icon: '❌' },
  submitted:          { label: 'Submitted to Network',  color: 'brand',       icon: '📤' },
  escalated:          { label: 'Escalated',             color: 'danger',      icon: '⚠️' },
  closed:             { label: 'Cancelled',             color: 'subtle',      icon: '🚫' },
};

function getStatusDisplay(status: string) {
  return STATUS_CONFIG[status] ?? { label: status, color: 'subtle' as const, icon: '❓' };
}

function toReadableSource(submittedFrom?: string): string {
  switch ((submittedFrom || '').toLowerCase()) {
    case 'customer_portal':
      return 'Customer Portal';
    case 'analyst_portal':
      return 'Analyst Portal';
    default:
      return submittedFrom ? submittedFrom.replace(/_/g, ' ') : 'Unknown Source';
  }
}

function toReadableTimestamp(iso?: string): string {
  if (!iso) return 'Unknown time';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 'Unknown time';
  return d.toLocaleString();
}

function isCustomerActionableStatus(status?: string): boolean {
  switch ((status || '').toLowerCase()) {
    case 'approved':
    case 'denied':
    case 'closed':
    case 'submitted':
    case 'expired':
      return false;
      return false;
    default:
      return true;
  }
}

function mapTimelineToComments(events: TimelineEvent[]): AnalystComment[] {
  return events
    .filter(ev => ev.eventType === 'analyst_note' || ev.eventType === 'customer_response')
    .map(ev => ({
      id: ev.id,
      author: ev.actor === 'customer' ? 'You' : ev.actor,
      role: ev.actor === 'customer' ? 'system' : 'analyst',
      message: ev.detail,
      timestamp: ev.occurredAt,
      requiresAction:
        ev.eventType === 'analyst_note' &&
        (/need|required|please provide|please upload/i.test(ev.detail)),
    }));
}

function mergeDisputes(existing: StoredDispute[], incoming: StoredDispute[]): StoredDispute[] {
  const byId = new Map<string, StoredDispute>();
  for (const dispute of existing) {
    byId.set(dispute.disputeId, dispute);
  }

  for (const dispute of incoming) {
    const prev = byId.get(dispute.disputeId);
    byId.set(dispute.disputeId, {
      ...prev,
      ...dispute,
      reasonLabel: prev?.reasonLabel || dispute.reasonLabel,
      description: prev?.description || dispute.description,
      analystComments: prev?.analystComments || dispute.analystComments || [],
    });
  }

  return Array.from(byId.values()).sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  );
}

export function MyDisputesPage() {
  const navigate = useNavigate();
  const { reset } = useWizard();
  const { account } = useAccount();
  const [disputes, setDisputes] = useState<StoredDispute[]>(() => getStoredDisputes());
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [replyText, setReplyText] = useState<Record<string, string>>({});
  const [cancelConfirm, setCancelConfirm] = useState<string | null>(null);
  const [cancelReason, setCancelReason] = useState('');
  const [cancelling, setCancelling] = useState<string | null>(null);
  const [cancelledIds, setCancelledIds] = useState<Set<string>>(new Set());
  const [attachedFiles, setAttachedFiles] = useState<Record<string, File[]>>({});
  const [existingDocs, setExistingDocs] = useState<Record<string, StoredCaseDocument[]>>({});
  const [docsLoading, setDocsLoading] = useState<Record<string, boolean>>({});
  const [submitted, setSubmitted] = useState<Record<string, boolean>>({});
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});
  const customerId = getCustomerId();

  // Load stored disputes, then hydrate with backend history and latest statuses.
  useEffect(() => {
    const run = async () => {
      const stored = getStoredDisputes();
      const customerId = getCustomerId();
      const cardholderName = getPreferredCardholderName(DEMO_CARDHOLDER_NAME);

      let merged = stored;
      try {
        let serverDisputes = await listCustomerDisputes(customerId, cardholderName, account.lastFour);
        if (serverDisputes.length === 0 && cardholderName !== DEMO_CARDHOLDER_NAME) {
          serverDisputes = await listCustomerDisputes(customerId, DEMO_CARDHOLDER_NAME, account.lastFour);
        }
        const mappedFromServer: StoredDispute[] = serverDisputes.map((d) => ({
          ...d,
          reasonLabel: d.reasonCode,
          description: typeof d.metadata?.description === 'string' ? d.metadata.description : undefined,
          analystComments: [],
        }));
        merged = mergeDisputes(stored, mappedFromServer);
      } catch {
        merged = stored;
      }

      const realDisputes = merged.filter(d => !d.disputeId.startsWith('demo-'));
      if (realDisputes.length === 0) {
        setDisputes(merged);
        setStoredDisputes(merged);
        return;
      }

      const hydrated = await Promise.allSettled(
        realDisputes.map(async d => {
          const dispute = await getDispute(d.disputeId, d.networkCode).catch(() => null);
          const timeline = await getDisputeTimeline(d.disputeId).catch(() => [] as TimelineEvent[]);
          return { dispute, timeline };
        })
      );

      const next = merged.map(d => {
        const idx = realDisputes.findIndex(rd => rd.disputeId === d.disputeId);
        if (idx === -1) return d;
        const result = hydrated[idx];
        if (result.status !== 'fulfilled') return d;

        const apiCase = result.value.dispute;
        const comments = mapTimelineToComments(result.value.timeline || []);
        if (!apiCase) {
          return { ...d, analystComments: comments };
        }

        return {
          ...d,
          ...apiCase,
          status: apiCase.status,
          analystComments: comments,
        };
      });

      setStoredDisputes(next);
      setDisputes(next);
    };

    void run();
  }, [account.lastFour]);

  useEffect(() => {
    if (!expandedId || expandedId.startsWith('demo-') || existingDocs[expandedId]) return;
    setDocsLoading(prev => ({ ...prev, [expandedId]: true }));
    getCaseDocuments(expandedId)
      .then(docs => {
        setExistingDocs(prev => ({ ...prev, [expandedId]: docs }));
      })
      .catch(() => {
        setExistingDocs(prev => ({ ...prev, [expandedId]: [] }));
      })
      .finally(() => {
        setDocsLoading(prev => ({ ...prev, [expandedId]: false }));
      });
  }, [expandedId, existingDocs]);

  const copyRefNumber = (e: React.MouseEvent, disputeId: string) => {
    e.stopPropagation();
    navigator.clipboard.writeText(disputeId);
    setCopiedId(disputeId);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleFileSelect = (disputeId: string, files: FileList | null) => {
    if (!files) return;
    setAttachedFiles(prev => ({
      ...prev,
      [disputeId]: [...(prev[disputeId] || []), ...Array.from(files)],
    }));
  };

  const removeFile = (disputeId: string, index: number) => {
    setAttachedFiles(prev => ({
      ...prev,
      [disputeId]: (prev[disputeId] || []).filter((_, i) => i !== index),
    }));
  };

  const handleCancelDispute = async (disputeId: string) => {
    setCancelling(disputeId);
    try {
      await cancelDispute(disputeId, customerId, cancelReason.trim() || undefined);
      const next = disputes.map(d =>
        d.disputeId === disputeId ? { ...d, status: 'closed' } : d
      );
      setStoredDisputes(next);
      setDisputes(next);
      setCancelledIds(prev => new Set(prev).add(disputeId));
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Failed to cancel dispute.');
    } finally {
      setCancelling(null);
      setCancelConfirm(null);
      setCancelReason('');
    }
  };

  const handleSubmitResponse = async (disputeId: string) => {
    const message = (replyText[disputeId] || '').trim();
    const files = attachedFiles[disputeId] || [];
    if (!message && files.length === 0) return;

    const uploadedDocIds: string[] = [];
    for (const file of files) {
      const uploaded = await uploadDocument(disputeId, file, {
        submittedBy: customerId,
        submittedFrom: 'customer_portal',
        note: message || 'Customer attachment',
      });
      const docId = uploaded.document?.id || uploaded.document?.documentId;
      if (docId) uploadedDocIds.push(docId);
    }

    await submitCustomerResponse(disputeId, {
      customerId,
      comment: message,
      attachmentDocumentIds: uploadedDocIds,
    });

    if (uploadedDocIds.length > 0) {
      const docs = await getCaseDocuments(disputeId).catch(() => existingDocs[disputeId] || []);
      setExistingDocs(prev => ({ ...prev, [disputeId]: docs }));
    }

    const timeline = await getDisputeTimeline(disputeId).catch(() => [] as TimelineEvent[]);
    const comments = mapTimelineToComments(timeline);

    const next = disputes.map(d => d.disputeId === disputeId ? { ...d, analystComments: comments } : d);
    setStoredDisputes(next);
    setDisputes(next);
    setReplyText(prev => ({ ...prev, [disputeId]: '' }));
    setAttachedFiles(prev => ({ ...prev, [disputeId]: [] }));
    setSubmitted(prev => ({ ...prev, [disputeId]: true }));
    setTimeout(() => setSubmitted(prev => ({ ...prev, [disputeId]: false })), 3000);
  };

  if (disputes.length === 0) {
    return (
      <AppShell>
        <Title1 style={{ marginBottom: tokens.spacingVerticalL }}>My Disputes</Title1>
        <Body1 style={{ color: tokens.colorNeutralForeground2, display: 'block', marginBottom: tokens.spacingVerticalXL }}>
          You have no disputes yet. When you file a dispute, it will appear here and remain visible through review, approval, and closure.
        </Body1>
        <Button appearance="primary" onClick={() => { reset(); navigate('/'); }}>File a new dispute</Button>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <Title1 style={{ marginBottom: tokens.spacingVerticalS }}>My Disputes</Title1>
      <Body1 style={{ color: tokens.colorNeutralForeground2, display: 'block', marginBottom: tokens.spacingVerticalXL }}>
      Below are your disputes, including newly filed, in-review, approved, and closed cases.
      </Body1>

      <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalL }}>
        {disputes.map(d => {
          const statusInfo = getStatusDisplay(d.status);
          const isExpanded = expandedId === d.disputeId;
          const isCustomerActionable = isCustomerActionableStatus(d.status);
          const hasActionRequired = isCustomerActionable && (d.analystComments?.some(c => c.requiresAction) ?? false);

          return (
            <div
              key={d.disputeId}
              style={{
                background: tokens.colorNeutralBackground1,
                border: `1px solid ${hasActionRequired ? tokens.colorStatusWarningBorder1 : tokens.colorNeutralStroke1}`,
                borderRadius: tokens.borderRadiusMedium,
                overflow: 'hidden',
              }}
            >
              {/* Dispute header row */}
              <button
                onClick={() => setExpandedId(isExpanded ? null : d.disputeId)}
                style={{
                  width: '100%',
                  background: 'none',
                  border: 'none',
                  padding: tokens.spacingVerticalM,
                  cursor: 'pointer',
                  textAlign: 'left',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: tokens.spacingHorizontalM,
                  flexWrap: 'wrap',
                }}
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalXXS }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: tokens.spacingHorizontalS, flexWrap: 'wrap' }}>
                    <Text weight="semibold" size={400}>{d.merchantName}</Text>
                    <Badge appearance="filled" color={statusInfo.color} size="small">
                      {statusInfo.icon} {statusInfo.label}
                    </Badge>
                    {hasActionRequired && (
                      <Badge appearance="filled" color="warning" size="small">
                        ⚡ Action Required
                      </Badge>
                    )}
                  </div>
                  <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Tooltip content={copiedId === d.disputeId ? 'Copied!' : 'Click to copy'} relationship="label">
                      <span
                        onClick={(e) => copyRefNumber(e, d.disputeId)}
                        style={{ cursor: 'pointer', textDecoration: 'underline dotted', textUnderlineOffset: '2px' }}
                      >
                        {d.disputeId}
                      </span>
                    </Tooltip>
                    {copiedId === d.disputeId && <span style={{ color: tokens.colorStatusSuccessForeground1, fontSize: '11px' }}>✓ Copied</span>}
                    <span> · Filed {new Date(d.createdAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</span>
                  </Text>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: tokens.spacingHorizontalM }}>
                  <Text weight="bold" size={500}>
                    {new Intl.NumberFormat('en-US', { style: 'currency', currency: d.transactionCurrency }).format(d.transactionAmount)}
                  </Text>
                  <Text size={300} style={{ color: tokens.colorNeutralForeground3 }}>
                    {isExpanded ? '▲' : '▼'}
                  </Text>
                </div>
              </button>

              {/* Expanded details */}
              {isExpanded && (
                <div style={{ padding: `0 ${tokens.spacingHorizontalM} ${tokens.spacingVerticalM}`, borderTop: `1px solid ${tokens.colorNeutralStroke2}` }}>
                  {/* Case details */}
                  <div
                    style={{
                      padding: `${tokens.spacingVerticalS} 0 ${tokens.spacingVerticalM}`,
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
                      gap: `${tokens.spacingVerticalS} ${tokens.spacingHorizontalS}`,
                    }}
                  >
                    {[
                      { label: 'Reason', value: d.reasonLabel || d.reasonCode },
                      { label: 'Transaction Date', value: new Date(d.transactionDate + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) },
                      { label: 'Card', value: `•••• ${d.cardLastFour} (${d.networkCode})` },
                      { label: 'Deadline', value: new Date(d.deadlineUtc).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) },
                    ].map((item) => (
                      <div
                        key={item.label}
                        style={{
                          padding: `${tokens.spacingVerticalXS} ${tokens.spacingHorizontalS}`,
                          borderRadius: tokens.borderRadiusMedium,
                          border: `1px solid ${tokens.colorNeutralStroke2}`,
                          background: tokens.colorNeutralBackground2,
                        }}
                      >
                        <Text size={100} style={{ color: tokens.colorNeutralForeground3, display: 'block', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                          {item.label}
                        </Text>
                        <Text size={300} weight="semibold">{item.value}</Text>
                      </div>
                    ))}
                  </div>

                  {d.description && (
                    <div
                      style={{
                        marginBottom: tokens.spacingVerticalM,
                        padding: `${tokens.spacingVerticalS} ${tokens.spacingHorizontalS}`,
                        borderRadius: tokens.borderRadiusMedium,
                        background: tokens.colorNeutralBackground2,
                        border: `1px solid ${tokens.colorNeutralStroke2}`,
                      }}
                    >
                      <Text size={100} weight="semibold" style={{ color: tokens.colorNeutralForeground3, display: 'block', marginBottom: tokens.spacingVerticalXXS, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Your description</Text>
                      <Text size={300} style={{ lineHeight: 1.4 }}>"{d.description}"</Text>
                    </div>
                  )}

                  <div style={{ marginBottom: tokens.spacingVerticalM }}>
                    <Text size={100} weight="semibold" style={{ color: tokens.colorNeutralForeground3, display: 'block', marginBottom: tokens.spacingVerticalXXS, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      Documents on file
                    </Text>
                    {docsLoading[d.disputeId] ? (
                      <Text size={300} style={{ color: tokens.colorNeutralForeground3 }}>Loading documents...</Text>
                    ) : (existingDocs[d.disputeId] && existingDocs[d.disputeId].length > 0) ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalXXS }}>
                        {existingDocs[d.disputeId].map(doc => {
                          const proxyUrl = `/api/cases/${encodeURIComponent(d.disputeId)}/documents/${encodeURIComponent(doc.documentId)}/download`;
                          return (
                            <div
                              key={doc.documentId}
                              style={{
                                border: `1px solid ${tokens.colorNeutralStroke2}`,
                                borderRadius: tokens.borderRadiusMedium,
                                padding: `${tokens.spacingVerticalXS} ${tokens.spacingHorizontalS}`,
                                background: tokens.colorNeutralBackground2,
                              }}
                            >
                              <a
                                href={proxyUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{ color: tokens.colorBrandForeground1, textDecoration: 'underline', fontWeight: 600 }}
                              >
                                {doc.filename}
                              </a>
                              <Text size={100} style={{ display: 'block', marginTop: 2, color: tokens.colorNeutralForeground3 }}>
                                {Math.max(1, Math.round(doc.sizeBytes / 1024))} KB
                              </Text>
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
                                <Badge appearance="filled" color="informative">Source: {toReadableSource(doc.submittedFrom)}</Badge>
                                <Badge appearance="outline" color="subtle">Uploaded: {toReadableTimestamp(doc.uploadedAt)}</Badge>
                                <Badge appearance="outline" color="brand">Submitted by: {doc.submittedBy || 'Unknown'}</Badge>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <Text size={300} style={{ color: tokens.colorNeutralForeground3 }}>No documents uploaded yet.</Text>
                    )}
                  </div>

                  {(() => {
                    const docs = existingDocs[d.disputeId] || [];
                    const closureDoc = docs.find(doc => doc.closure?.artifactType === 'closure_decision' || doc.filename.startsWith('closure-'));
                    if (!closureDoc?.closure) return null;
                    const closure = closureDoc.closure;
                    const disposition = (closure.disposition || 'closed').toLowerCase();
                    const dispositionLabel = disposition === 'approved' ? 'Approved' : disposition === 'denied' ? 'Denied' : 'Closed';
                    return (
                      <div
                        style={{
                          marginBottom: tokens.spacingVerticalM,
                          padding: `${tokens.spacingVerticalS} ${tokens.spacingHorizontalS}`,
                          borderRadius: tokens.borderRadiusMedium,
                          border: `1px solid ${tokens.colorNeutralStroke2}`,
                          background: disposition === 'approved'
                            ? tokens.colorStatusSuccessBackground1
                            : disposition === 'denied'
                              ? tokens.colorStatusDangerBackground1
                              : tokens.colorNeutralBackground2,
                        }}
                      >
                        <Text size={300} weight="semibold" style={{ display: 'block', marginBottom: tokens.spacingVerticalXXS }}>
                          Case decision: {dispositionLabel}
                        </Text>
                        <Text size={200} style={{ display: 'block' }}>
                          Case ID: {closure.caseId || d.disputeId}
                        </Text>
                        <Text size={200} style={{ display: 'block' }}>
                          Timestamp: {closure.createdAt ? new Date(closure.createdAt).toLocaleString() : '—'}
                        </Text>
                        <Text size={200} style={{ display: 'block' }}>
                          Reason: {closure.reason || 'No additional reason provided.'}
                        </Text>
                        {closureDoc.blobUrl && (
                          <a
                            href={closureDoc.blobUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{
                              display: 'inline-block',
                              marginTop: tokens.spacingVerticalXXS,
                              color: tokens.colorBrandForeground1,
                              textDecoration: 'underline',
                            }}
                          >
                            View decision artifact
                          </a>
                        )}
                      </div>
                    );
                  })()}

                  <Divider style={{ margin: `${tokens.spacingVerticalS} 0` }} />

                  {/* Cancel dispute */}
                  {isCustomerActionable && !cancelledIds.has(d.disputeId) && (
                    <div style={{ marginBottom: tokens.spacingVerticalM }}>
                      {cancelConfirm !== d.disputeId ? (
                        <Button
                          appearance="subtle"
                          size="small"
                          style={{ color: tokens.colorStatusDangerForeground1, borderColor: tokens.colorStatusDangerBorder1, border: `1px solid ${tokens.colorStatusDangerBorder1}` }}
                          onClick={() => { setCancelConfirm(d.disputeId); setCancelReason(''); }}
                        >
                          🚫 Cancel this dispute
                        </Button>
                      ) : (
                        <div style={{ padding: tokens.spacingVerticalS, border: `1px solid ${tokens.colorStatusDangerBorder1}`, borderRadius: tokens.borderRadiusMedium, background: tokens.colorStatusDangerBackground1 }}>
                          <Text weight="semibold" size={300} style={{ display: 'block', marginBottom: tokens.spacingVerticalXS, color: tokens.colorStatusDangerForeground1 }}>
                            Cancel this dispute?
                          </Text>
                          <Text size={200} style={{ display: 'block', marginBottom: tokens.spacingVerticalS, color: tokens.colorNeutralForeground2 }}>
                            This cannot be undone. The claim will be closed and no further action will be taken.
                          </Text>
                          <Textarea
                            placeholder="Optional: reason for cancellation"
                            value={cancelReason}
                            onChange={(_, data) => setCancelReason(data.value)}
                            style={{ width: '100%', marginBottom: tokens.spacingVerticalS }}
                            rows={2}
                          />
                          <div style={{ display: 'flex', gap: tokens.spacingHorizontalS }}>
                            <Button
                              appearance="primary"
                              size="small"
                              disabled={cancelling === d.disputeId}
                              style={{ background: tokens.colorStatusDangerBackground3, border: 'none' }}
                              onClick={() => void handleCancelDispute(d.disputeId)}
                            >
                              {cancelling === d.disputeId ? 'Cancelling…' : 'Yes, cancel dispute'}
                            </Button>
                            <Button appearance="secondary" size="small" onClick={() => { setCancelConfirm(null); setCancelReason(''); }}>
                              Keep dispute
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                  {cancelledIds.has(d.disputeId) && (
                    <div style={{ marginBottom: tokens.spacingVerticalM, padding: tokens.spacingVerticalS, borderRadius: tokens.borderRadiusMedium, background: tokens.colorNeutralBackground2, border: `1px solid ${tokens.colorNeutralStroke2}` }}>
                      <Text size={300} style={{ color: tokens.colorNeutralForeground2 }}>✓ Dispute cancellation submitted. The case has been closed.</Text>
                    </div>
                  )}

                  {/* Analyst comments */}
                  <Title2 style={{ fontSize: '15px', marginBottom: tokens.spacingVerticalS }}>Messages from Review Team</Title2>

                  {(!d.analystComments || d.analystComments.length === 0) ? (
                    <Text size={300} style={{ color: tokens.colorNeutralForeground3, display: 'block' }}>
                      No messages yet. The team is reviewing your case.
                    </Text>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalS }}>
                      {d.analystComments.map(comment => (
                        <CommentBubble key={comment.id} comment={comment} showActionState={isCustomerActionable} />
                      ))}
                    </div>
                  )}

                  {/* Response section when action is required */}
                  {hasActionRequired && (
                    <>
                      <Divider style={{ margin: `${tokens.spacingVerticalM} 0` }} />
                      <div style={{
                        padding: `${tokens.spacingVerticalS} ${tokens.spacingHorizontalS}`,
                        borderRadius: tokens.borderRadiusMedium,
                        backgroundColor: tokens.colorNeutralBackground2,
                        border: `1px solid ${tokens.colorStatusWarningBorder1}`,
                      }}>
                        <Text weight="semibold" size={300} style={{ display: 'block', marginBottom: tokens.spacingVerticalS }}>
                          Respond to the review team
                        </Text>

                        {submitted[d.disputeId] ? (
                          <div style={{ padding: tokens.spacingVerticalM, textAlign: 'center' }}>
                            <Text size={400} style={{ color: tokens.colorStatusSuccessForeground1 }}>
                              ✓ Your response has been submitted. The team will review it shortly.
                            </Text>
                          </div>
                        ) : (
                          <>
                            <Textarea
                              placeholder="Add a message or explanation..."
                              style={{ width: '100%', marginBottom: tokens.spacingVerticalS }}
                              rows={3}
                              value={replyText[d.disputeId] || ''}
                              onChange={(_e, data) => setReplyText(prev => ({ ...prev, [d.disputeId]: data.value }))}
                            />

                            <div style={{ display: 'flex', alignItems: 'center', gap: tokens.spacingHorizontalS, flexWrap: 'wrap', marginBottom: tokens.spacingVerticalS }}>
                              <Button
                                appearance="subtle"
                                size="small"
                                onClick={() => fileInputRefs.current[d.disputeId]?.click()}
                              >
                                📎 Attach file
                              </Button>
                              <input
                                type="file"
                                multiple
                                ref={el => { fileInputRefs.current[d.disputeId] = el; }}
                                style={{ display: 'none' }}
                                onChange={e => handleFileSelect(d.disputeId, e.target.files)}
                              />
                              {(attachedFiles[d.disputeId] || []).map((file, i) => (
                                <Badge key={i} appearance="outline" color="informative" size="small">
                                  {file.name}
                                  <span
                                    style={{ cursor: 'pointer', marginLeft: '4px' }}
                                    onClick={() => removeFile(d.disputeId, i)}
                                  >✕</span>
                                </Badge>
                              ))}
                            </div>

                            <Button
                              appearance="primary"
                              size="small"
                              disabled={!(replyText[d.disputeId]?.trim() || (attachedFiles[d.disputeId] || []).length > 0)}
                              onClick={() => { void handleSubmitResponse(d.disputeId); }}
                            >
                              Submit response
                            </Button>
                          </>
                        )}
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div style={{ marginTop: tokens.spacingVerticalXL }}>
        <Button appearance="primary" onClick={() => { reset(); navigate('/'); }}>File a new dispute</Button>
      </div>
    </AppShell>
  );
}

function CommentBubble({ comment, showActionState = true }: { comment: AnalystComment; showActionState?: boolean }) {
  const isSystem = comment.role === 'system';
  const highlightAction = showActionState && comment.requiresAction;

  return (
    <div
      style={{
        padding: tokens.spacingVerticalS,
        borderRadius: tokens.borderRadiusMedium,
        backgroundColor: highlightAction
          ? tokens.colorStatusWarningBackground1
          : isSystem
            ? tokens.colorNeutralBackground3
            : tokens.colorNeutralBackground4,
        border: highlightAction
          ? `1px solid ${tokens.colorStatusWarningBorder1}`
          : `1px solid ${tokens.colorNeutralStroke2}`,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: tokens.spacingVerticalXXS }}>
        <Text size={200} weight="semibold" style={{ color: isSystem ? tokens.colorNeutralForeground3 : tokens.colorNeutralForeground1 }}>
          {comment.author}
          {highlightAction && <Badge appearance="tint" color="warning" size="small" style={{ marginLeft: tokens.spacingHorizontalS }}>Action Needed</Badge>}
        </Text>
        <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>
          {new Date(comment.timestamp).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
        </Text>
      </div>
      <Text size={300} style={{ color: tokens.colorNeutralForeground2 }}>
        {comment.message}
      </Text>
    </div>
  );
}
