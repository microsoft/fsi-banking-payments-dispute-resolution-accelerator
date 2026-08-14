import {
  Button,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Tab,
  TabList,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Text,
  Title3,
  Spinner,
  tokens,
} from '@fluentui/react-components';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { getCaseDocuments, uploadCaseDocument, type CaseDocument } from '../api/cases';
import type { Evidence, EvidenceType, TimelineEvent } from '../types/case';
import { CompletenessBadge } from './CaseBadges';
import { useNotifications } from './NotificationProvider';

interface EvidencePanelProps {
  caseId: string;
  evidence: Evidence[];
  timelineEvents?: TimelineEvent[];
  currentAnalystId?: string;
  currentAnalystName?: string;
  onTimelineRefresh?: () => void;
}

type EvidenceCategory = 'all' | 'payment' | 'customer' | 'merchant' | 'digital' | 'fraud';

type EvidenceRow = {
  id: string;
  category: EvidenceCategory;
  typeLabel: string;
  sourceSystem: string;
  submittedBy: string;
  timestamp: string;
  completeness?: 'complete' | 'partial' | 'missing';
  note?: string;
  blobUrl?: string;
  reference?: string;
  fileName?: string;
  contentType?: string;
  sizeBytes?: number;
  downloadUrl?: string;
  rawData?: unknown;
};

type PreviewState = {
  loading: boolean;
  error?: string;
  text?: string;
};

const CATEGORY_CONFIG: Record<EvidenceCategory, { label: string; icon: string; types: EvidenceType[] }> = {
  all: { label: 'All', icon: '📁', types: [] },
  payment: {
    label: 'Payment Data',
    icon: '💳',
    types: ['transaction'],
  },
  customer: {
    label: 'Customer',
    icon: '👤',
    types: ['communication', 'contract'],
  },
  merchant: {
    label: 'Merchant',
    icon: '🏪',
    types: ['receipt', 'order'],
  },
  digital: {
    label: 'Digital Evidence',
    icon: '📎',
    types: ['shipping', 'photo'],
  },
  fraud: {
    label: 'Fraud Evidence',
    icon: '🚨',
    types: ['fraud_signal', 'fraud_screening', 'device_fingerprint'],
  },
};

const ACCEPTED_TYPES = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp'];
const MAX_SIZE_MB = 10;

function normalizeTimelineTimestamp(ev: TimelineEvent): string {
  const raw = (ev as TimelineEvent & { occurredAt?: string }).timestamp || (ev as TimelineEvent & { occurredAt?: string }).occurredAt;
  return raw || new Date().toISOString();
}

function normalizeTimelineDetail(ev: TimelineEvent): string {
  const raw = (ev as TimelineEvent & { detail?: string }).description || (ev as TimelineEvent & { detail?: string }).detail;
  return raw || '';
}

function normalizeTimelineMetadata(ev: TimelineEvent): Record<string, unknown> {
  const raw = (ev as TimelineEvent & { data?: Record<string, unknown> }).metadata || (ev as TimelineEvent & { data?: Record<string, unknown> }).data;
  return raw || {};
}

function isPreviewableText(contentType?: string, fileName?: string): boolean {
  const type = (contentType || '').toLowerCase();
  const name = (fileName || '').toLowerCase();
  return type.includes('json') || type.startsWith('text/') || name.endsWith('.json') || name.endsWith('.txt');
}

function isPreviewableImage(contentType?: string, fileName?: string): boolean {
  const type = (contentType || '').toLowerCase();
  const name = (fileName || '').toLowerCase();
  return type.startsWith('image/') || /\.(png|jpg|jpeg|webp|gif)$/i.test(name);
}

function isPreviewablePdf(contentType?: string, fileName?: string): boolean {
  const type = (contentType || '').toLowerCase();
  const name = (fileName || '').toLowerCase();
  return type.includes('pdf') || name.endsWith('.pdf');
}

function inferFileNameFromReference(reference?: string): string | undefined {
  if (!reference) return undefined;
  const trimmed = reference.trim();
  if (!trimmed) return undefined;
  const lastSlash = Math.max(trimmed.lastIndexOf('/'), trimmed.lastIndexOf('\\'));
  return lastSlash >= 0 ? trimmed.slice(lastSlash + 1) : trimmed;
}

function inferContentType(reference?: string): string | undefined {
  const fileName = inferFileNameFromReference(reference)?.toLowerCase() || '';
  if (fileName.endsWith('.json')) return 'application/json';
  if (fileName.endsWith('.txt')) return 'text/plain';
  if (fileName.endsWith('.pdf')) return 'application/pdf';
  if (fileName.endsWith('.svg')) return 'image/svg+xml';
  return undefined;
}

export function EvidencePanel({
  caseId,
  evidence,
  timelineEvents = [],
  currentAnalystId,
  currentAnalystName,
  onTimelineRefresh,
}: EvidencePanelProps) {
  const [activeTab, setActiveTab] = useState<EvidenceCategory>('all');
  const [documents, setDocuments] = useState<CaseDocument[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [preseeding, setPreseeding] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedRow, setSelectedRow] = useState<EvidenceRow | null>(null);
  const [preview, setPreview] = useState<PreviewState>({ loading: false });
  const inputRef = useRef<HTMLInputElement>(null);
  const { notifySuccess, notifyWarning, notifyError } = useNotifications();

  const loadDocuments = useCallback(async () => {
    setLoadingDocs(true);
    try {
      const docs = await getCaseDocuments(caseId);
      setDocuments(docs);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to load documents';
      setError(msg);
    } finally {
      setLoadingDocs(false);
    }
  }, [caseId]);

  const preseedSyntheticArtifacts = useCallback(async () => {
    setPreseeding(true);
    try {
      const response = await fetch(`/api/cases/${encodeURIComponent(caseId)}/evidence/preseed`, {
        method: 'POST',
      });
      if (!response.ok && response.status !== 404) {
        // Synthetic pre-seeding is best-effort only and should never interrupt analyst workflow.
        return;
      }
    } catch {
      // Best-effort path: ignore transient failures and continue with normal evidence experience.
    } finally {
      setPreseeding(false);
    }
  }, [caseId]);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  useEffect(() => {
    void preseedSyntheticArtifacts();
  }, [preseedSyntheticArtifacts]);

  useEffect(() => {
    let cancelled = false;
    if (!selectedRow) {
      setPreview({ loading: false });
      return;
    }

    if (selectedRow.downloadUrl && isPreviewableText(selectedRow.contentType, selectedRow.fileName)) {
      setPreview({ loading: true });
      fetch(selectedRow.downloadUrl)
        .then(async (res) => {
          if (!res.ok) throw new Error(`Unable to load preview (${res.status})`);
          return res.text();
        })
        .then((text) => {
          if (!cancelled) setPreview({ loading: false, text });
        })
        .catch((e: unknown) => {
          if (!cancelled) setPreview({ loading: false, error: e instanceof Error ? e.message : 'Preview unavailable' });
        });
      return () => {
        cancelled = true;
      };
    }

    setPreview({ loading: false });
    return () => {
      cancelled = true;
    };
  }, [selectedRow]);

  const uploadFiles = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setError(null);

    const valid: File[] = [];
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (!ACCEPTED_TYPES.includes(file.type)) {
        setError(`"${file.name}" is not supported. Use PDF, JPG, PNG, or WebP.`);
        continue;
      }
      if (file.size > MAX_SIZE_MB * 1024 * 1024) {
        setError(`"${file.name}" exceeds ${MAX_SIZE_MB}MB limit.`);
        continue;
      }
      valid.push(file);
    }

    if (valid.length === 0) return;

    setUploading(true);
    try {
      for (const file of valid) {
        const result = await uploadCaseDocument(caseId, file, {
          submittedBy: currentAnalystName || currentAnalystId || 'analyst',
          submittedFrom: 'analyst_portal',
        });
        const score = result.document.analysis?.evidenceScore ?? 0.5;
        if (score >= 0.8) {
          notifySuccess('High-value evidence uploaded', `${file.name} scored ${Math.round(score * 100)}%`);
        } else if (score >= 0.6) {
          notifyWarning('Document uploaded', `${file.name} has moderate evidence value.`);
        } else {
          notifyWarning('Low-value document', `${file.name} may need stronger supporting evidence.`);
        }
      }
      await loadDocuments();
      onTimelineRefresh?.();
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Upload failed';
      setError(msg);
      notifyError('Upload failed', msg);
    } finally {
      setUploading(false);
    }
  }, [caseId, currentAnalystId, currentAnalystName, loadDocuments, notifyError, notifySuccess, notifyWarning, onTimelineRefresh]);

  const rows = useMemo(() => {
    const customerResponses = timelineEvents
      .filter(ev => {
        const type = ((ev as TimelineEvent & { eventType?: string }).eventType || '').toLowerCase();
        return type === 'customer_response';
      })
      .map(ev => {
        const metadata = normalizeTimelineMetadata(ev);
        const ids = Array.isArray(metadata.attachmentDocumentIds) ? metadata.attachmentDocumentIds as string[] : [];
        return {
          responseId: (ev as TimelineEvent & { eventId?: string }).eventId || String(Math.random()),
          text: normalizeTimelineDetail(ev),
          timestamp: normalizeTimelineTimestamp(ev),
          customerId: String(metadata.customerId || 'customer'),
          attachmentDocumentIds: ids,
        };
      });

    const noteByDocumentId = new Map<string, string>();
    for (const response of customerResponses) {
      for (const docId of response.attachmentDocumentIds) {
        noteByDocumentId.set(docId, response.text);
      }
    }

    const evidenceRows: EvidenceRow[] = evidence.map((ev) => {
      const category: EvidenceCategory = ev.type === 'transaction'
        ? 'payment'
        : (ev.type === 'communication' || ev.type === 'contract')
          ? 'customer'
          : (ev.type === 'receipt' || ev.type === 'order')
            ? 'merchant'
            : (ev.type === 'shipping' || ev.type === 'photo')
              ? 'digital'
              : (ev.type === 'fraud_signal' || ev.type === 'fraud_screening' || ev.type === 'device_fingerprint')
                ? 'fraud'
                : 'all';
      return {
        id: ev.evidenceId,
        category,
        typeLabel: ev.type,
        sourceSystem: ev.sourceSystem,
        submittedBy: ev.sourceSystem,
        timestamp: ev.retrievedAt,
        completeness: ev.completeness,
        blobUrl: ev.contentRef?.startsWith('http') ? ev.contentRef : undefined,
        reference: ev.contentRef,
        fileName: inferFileNameFromReference(ev.contentRef),
        contentType: inferContentType(ev.contentRef),
        downloadUrl: `/api/cases/${encodeURIComponent(caseId)}/evidence/${encodeURIComponent(ev.evidenceId)}/download`,
        rawData: ev,
      };
    });

    const documentRows: EvidenceRow[] = documents.map((doc) => {
      const fromCustomer = (doc.submittedFrom || '').toLowerCase() === 'customer_portal';
      return {
        id: doc.documentId,
        category: fromCustomer ? 'customer' : 'digital',
        typeLabel: doc.analysis?.documentType || 'document',
        sourceSystem: doc.submittedFrom || 'portal_upload',
        submittedBy: doc.submittedBy || 'unknown',
        timestamp: doc.uploadedAt,
        completeness: 'complete',
        note: noteByDocumentId.get(doc.documentId) || doc.note,
        blobUrl: doc.blobUrl,
        reference: doc.documentId,
        fileName: doc.filename,
        contentType: doc.contentType,
        sizeBytes: doc.sizeBytes,
        downloadUrl: `/api/cases/${encodeURIComponent(caseId)}/documents/${encodeURIComponent(doc.documentId)}/download`,
        rawData: doc,
      };
    });

    const customerNoteRows: EvidenceRow[] = customerResponses
      .filter(r => r.text)
      .map(r => ({
        id: `customer-note-${r.responseId}`,
        category: 'customer',
        typeLabel: 'customer_note',
        sourceSystem: 'customer_portal',
        submittedBy: r.customerId,
        timestamp: r.timestamp,
        note: r.text,
        completeness: 'complete',
        reference: r.responseId,
        rawData: r,
      }));

    return [...evidenceRows, ...documentRows, ...customerNoteRows].sort(
      (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
  }, [documents, evidence, timelineEvents]);

  const filtered = activeTab === 'all'
    ? rows
    : rows.filter((row) => row.category === activeTab);

  // Count per category
  const counts = Object.entries(CATEGORY_CONFIG).reduce<Record<string, number>>((acc, [key]) => {
    acc[key] = key === 'all' ? rows.length : rows.filter((row) => row.category === key).length;
    return acc;
  }, {});

  const downloadAllEvidence = () => {
    const url = `/api/cases/${encodeURIComponent(caseId)}/evidence/download-all`;
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = '';
    anchor.rel = 'noopener';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 12 }}>
        <Title3 style={{ marginBottom: 0 }}>Evidence Center ({rows.length})</Title3>
        <Button appearance="secondary" size="small" onClick={downloadAllEvidence}>
          Download All Evidence (.zip)
        </Button>
      </div>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); void uploadFiles(e.dataTransfer.files); }}
        onClick={() => !uploading && inputRef.current?.click()}
        style={{
          border: `2px dashed ${dragOver ? tokens.colorBrandStroke1 : tokens.colorNeutralStroke2}`,
          borderRadius: '8px',
          padding: '18px',
          textAlign: 'center',
          cursor: uploading ? 'wait' : 'pointer',
          background: dragOver ? tokens.colorBrandBackground2 : 'transparent',
          marginBottom: '12px',
          opacity: uploading ? 0.6 : 1,
        }}
      >
        {uploading ? (
          <Spinner size="tiny" label="Uploading evidence..." />
        ) : (
          <Text size={200}>
            Upload documents and evidence here (PDF, JPG, PNG, WebP — max {MAX_SIZE_MB}MB)
          </Text>
        )}
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED_TYPES.join(',')}
          style={{ display: 'none' }}
          onChange={(e) => {
            void uploadFiles(e.target.files);
            e.target.value = '';
          }}
          aria-label="Upload evidence documents"
        />
      </div>

      {(loadingDocs || uploading) && (
        <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: 'block', marginBottom: '8px' }}>
          {loadingDocs ? 'Loading persisted evidence...' : 'Processing uploads...'}
        </Text>
      )}

      {preseeding && (
        <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: 'block', marginBottom: '8px' }}>
          Pre-seeding synthetic evidence artifacts...
        </Text>
      )}

      {error && (
        <Text size={200} style={{ color: tokens.colorPaletteRedForeground1, display: 'block', marginBottom: '8px' }}>
          {error}
        </Text>
      )}

      <TabList
        selectedValue={activeTab}
        onTabSelect={(_, data) => setActiveTab(data.value as EvidenceCategory)}
        size="small"
        style={{ marginBottom: '12px' }}
      >
        {Object.entries(CATEGORY_CONFIG).map(([key, cfg]) => (
          <Tab key={key} value={key}>
            {cfg.icon} {cfg.label} {counts[key] > 0 && key !== 'all' ? `(${counts[key]})` : ''}
          </Tab>
        ))}
      </TabList>

      {filtered.length === 0 ? (
        <Text size={200} style={{ color: tokens.colorNeutralForeground3, padding: '16px 0' }}>
          No evidence in this category.
        </Text>
      ) : (
        <Table aria-label="Evidence list" style={{ width: '100%' }}>
          <TableHeader>
            <TableRow>
              <TableHeaderCell>Type</TableHeaderCell>
              <TableHeaderCell>Source System</TableHeaderCell>
              <TableHeaderCell>Submitted By</TableHeaderCell>
              <TableHeaderCell>Timestamp</TableHeaderCell>
              <TableHeaderCell>Details</TableHeaderCell>
              <TableHeaderCell>Completeness</TableHeaderCell>
              <TableHeaderCell>Artifact</TableHeaderCell>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((ev) => (
              <TableRow
                key={ev.id}
                onClick={() => setSelectedRow(ev)}
                style={{ cursor: 'pointer' }}
              >
                <TableCell>
                  <Button
                    appearance="transparent"
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedRow(ev);
                    }}
                    style={{ padding: 0, minWidth: 'auto', height: 'auto' }}
                  >
                    <Text weight="semibold">{ev.typeLabel.replace(/_/g, ' ')}</Text>
                  </Button>
                </TableCell>
                <TableCell>{ev.sourceSystem}</TableCell>
                <TableCell>{ev.submittedBy}</TableCell>
                <TableCell>
                  <Text size={200}>{new Date(ev.timestamp).toLocaleString()}</Text>
                </TableCell>
                <TableCell>
                  <Text size={200}>{ev.note || '—'}</Text>
                </TableCell>
                <TableCell>
                  <CompletenessBadge level={ev.completeness || 'complete'} />
                </TableCell>
                <TableCell>
                  {ev.downloadUrl || ev.blobUrl ? (
                    <Button
                      size="small"
                      appearance="subtle"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedRow(ev);
                      }}
                    >
                      View artifact
                    </Button>
                  ) : (
                    <Button
                      size="small"
                      appearance="subtle"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedRow(ev);
                      }}
                    >
                      View details
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Dialog open={!!selectedRow} onOpenChange={(_, data) => !data.open && setSelectedRow(null)}>
        <DialogSurface>
          <DialogBody>
            <DialogTitle>{selectedRow?.typeLabel.replace(/_/g, ' ') || 'Evidence detail'}</DialogTitle>
            <DialogContent>
              {selectedRow && (
                <div style={{ display: 'grid', rowGap: '8px' }}>
                  <Text size={200}><strong>Source:</strong> {selectedRow.sourceSystem}</Text>
                  <Text size={200}><strong>Submitted by:</strong> {selectedRow.submittedBy}</Text>
                  <Text size={200}><strong>Timestamp:</strong> {new Date(selectedRow.timestamp).toLocaleString()}</Text>
                  <Text size={200}><strong>Completeness:</strong> {selectedRow.completeness || 'complete'}</Text>
                  {selectedRow.fileName && <Text size={200}><strong>File:</strong> {selectedRow.fileName}</Text>}
                  {selectedRow.contentType && <Text size={200}><strong>Content type:</strong> {selectedRow.contentType}</Text>}
                  {typeof selectedRow.sizeBytes === 'number' && (
                    <Text size={200}><strong>Size:</strong> {Math.max(1, Math.round(selectedRow.sizeBytes / 1024))} KB</Text>
                  )}
                  {selectedRow.note && <Text size={200}><strong>Details:</strong> {selectedRow.note}</Text>}
                  {selectedRow.reference && <Text size={200}><strong>Reference:</strong> {selectedRow.reference}</Text>}
                  {!!(selectedRow.downloadUrl || selectedRow.rawData) && (
                    <div style={{ marginTop: '12px' }}>
                      <Text weight="semibold" size={200} style={{ display: 'block', marginBottom: '8px' }}>
                        Evidence Preview
                      </Text>
                      {preview.loading ? (
                        <Spinner size="tiny" label="Loading preview..." />
                      ) : isPreviewableImage(selectedRow.contentType, selectedRow.fileName) && selectedRow.downloadUrl ? (
                        <img
                          src={selectedRow.downloadUrl}
                          alt={selectedRow.fileName || selectedRow.typeLabel}
                          style={{ maxWidth: '100%', maxHeight: '360px', borderRadius: '6px', border: `1px solid ${tokens.colorNeutralStroke2}` }}
                        />
                      ) : isPreviewablePdf(selectedRow.contentType, selectedRow.fileName) && selectedRow.downloadUrl ? (
                        <iframe
                          src={selectedRow.downloadUrl}
                          title={selectedRow.fileName || selectedRow.typeLabel}
                          style={{ width: '100%', height: '420px', border: `1px solid ${tokens.colorNeutralStroke2}`, borderRadius: '6px' }}
                        />
                      ) : preview.text ? (
                        <pre
                          style={{
                            margin: 0,
                            padding: '12px',
                            background: tokens.colorNeutralBackground2,
                            border: `1px solid ${tokens.colorNeutralStroke2}`,
                            borderRadius: '6px',
                            overflowX: 'auto',
                            whiteSpace: 'pre-wrap',
                            maxHeight: '320px',
                          }}
                        >
                          {preview.text}
                        </pre>
                      ) : selectedRow.rawData ? (
                        <pre
                          style={{
                            margin: 0,
                            padding: '12px',
                            background: tokens.colorNeutralBackground2,
                            border: `1px solid ${tokens.colorNeutralStroke2}`,
                            borderRadius: '6px',
                            overflowX: 'auto',
                            whiteSpace: 'pre-wrap',
                            maxHeight: '320px',
                          }}
                        >
                          {JSON.stringify(selectedRow.rawData, null, 2)}
                        </pre>
                      ) : preview.error ? (
                        <Text size={200} style={{ color: tokens.colorPaletteRedForeground1 }}>
                          {preview.error}
                        </Text>
                      ) : null}
                    </div>
                  )}
                </div>
              )}
            </DialogContent>
            <DialogActions>
              {selectedRow?.downloadUrl && (
                <>
                  <Button as="a" href={selectedRow.downloadUrl} target="_blank" rel="noopener noreferrer" appearance="primary">
                    Open document
                  </Button>
                  <Button as="a" href={selectedRow.downloadUrl} download={selectedRow.fileName || selectedRow.reference || 'evidence'} appearance="secondary">
                    Download file
                  </Button>
                </>
              )}
              {!selectedRow?.downloadUrl && selectedRow?.rawData && (
                <Button
                  appearance="secondary"
                  onClick={() => {
                    const blob = new Blob([JSON.stringify(selectedRow.rawData, null, 2)], { type: 'application/json' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `${selectedRow.reference || selectedRow.id}.json`;
                    a.click();
                    URL.revokeObjectURL(url);
                  }}
                >
                  Download data
                </Button>
              )}
              <Button appearance="secondary" onClick={() => setSelectedRow(null)}>Close</Button>
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </div>
  );
}
