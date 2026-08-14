import type { Case, CaseSummary, TimelineEvent, EvidenceGap, ReasonCodeChecklistItem, RiskLevel } from '../types/case';
import { mockCases, mockCaseSummaries } from '../mocks/cases';
import { mockTimelines } from '../mocks/timeline';
import { mockPrecedentsFor } from '../mocks/precedents';

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';
const API_FALLBACK_BASE = (
  import.meta.env.VITE_API_FALLBACK_BASE_URL ||
  (import.meta.env.DEV ? 'https://func-qqvftbiyd7fmk-app.azurewebsites.net' : '')
)
  .trim()
  .replace(/\/+$/, '');

function buildApiUrl(url: string, base = ''): string {
  if (/^https?:\/\//i.test(url)) return url;
  const normalizedPath = url.startsWith('/') ? url : `/${url}`;
  const normalizedBase = (base || '').trim().replace(/\/+$/, '');
  return normalizedBase ? `${normalizedBase}${normalizedPath}` : normalizedPath;
}

export interface ActionPayload {
  analystId: string;
  comment: string;
}

export interface ActionResult {
  status: string;
}

function computeDaysRemainingFromDueDate(dueDate?: string): number {
  if (!dueDate) return 0;
  const due = new Date(dueDate).getTime();
  if (Number.isNaN(due)) return 0;
  return Math.ceil((due - Date.now()) / (1000 * 60 * 60 * 24));
}

function normalizeCaseFromDispute(dispute: Record<string, unknown>, requestedId: string): Case {
  const candidateId =
    (typeof dispute.caseId === 'string' && dispute.caseId) ||
    (typeof dispute.disputeId === 'string' && dispute.disputeId) ||
    (typeof dispute.id === 'string' && dispute.id) ||
    requestedId;

  const rawNetwork = String(dispute.cardNetwork ?? dispute.networkCode ?? '').toLowerCase();
  const cardNetwork =
    rawNetwork === 'visa' ||
    rawNetwork === 'mastercard' ||
    rawNetwork === 'amex' ||
    rawNetwork === 'discover'
      ? rawNetwork
      : undefined;

  const deadlineObj = (dispute.deadline ?? {}) as Record<string, unknown>;
  const dueDate =
    (typeof deadlineObj.dueDate === 'string' && deadlineObj.dueDate) ||
    (typeof dispute.deadlineUtc === 'string' && dispute.deadlineUtc) ||
    new Date().toISOString().slice(0, 10);
  const daysRemaining =
    typeof deadlineObj.daysRemaining === 'number'
      ? deadlineObj.daysRemaining
      : computeDaysRemainingFromDueDate(dueDate);

  const mapped: Case = {
    caseId: candidateId,
    status: (String(dispute.status ?? 'intake') as Case['status']),
    reasonCode: String(dispute.reasonCode ?? 'unknown'),
    deadline: {
      network: cardNetwork ?? 'unknown',
      dueDate,
      daysRemaining,
    },
    createdAt: String(dispute.createdAt ?? new Date().toISOString()),
    cardNetwork,
    merchantName: typeof dispute.merchantName === 'string' ? dispute.merchantName : undefined,
    cardholderName: typeof dispute.cardholderName === 'string' ? dispute.cardholderName : undefined,
    caseDescription:
      typeof dispute.caseDescription === 'string'
        ? dispute.caseDescription
        : typeof dispute.description === 'string'
          ? dispute.description
          : typeof (dispute.metadata as Record<string, unknown> | undefined)?.description === 'string'
            ? ((dispute.metadata as Record<string, unknown>).description as string)
            : typeof (dispute.metadata as Record<string, unknown> | undefined)?.disputeDescription === 'string'
              ? ((dispute.metadata as Record<string, unknown>).disputeDescription as string)
              : undefined,
    transactionAmount: typeof dispute.transactionAmount === 'number' ? dispute.transactionAmount : undefined,
    transactionDate: typeof dispute.transactionDate === 'string' ? dispute.transactionDate : undefined,
    reasonCodeLabel: typeof dispute.reasonCodeLabel === 'string' ? dispute.reasonCodeLabel : undefined,
    assignedAnalystId: typeof dispute.assignedAnalystId === 'string' ? dispute.assignedAnalystId : undefined,
    assignedAnalystName: typeof dispute.assignedAnalystName === 'string' ? dispute.assignedAnalystName : undefined,
    orchestrationId: typeof dispute.orchestrationId === 'string' ? dispute.orchestrationId : undefined,
    disputeRef: typeof dispute.disputeRef === 'string' ? dispute.disputeRef : undefined,
    winProbability: typeof dispute.winProbability === 'number' ? dispute.winProbability : undefined,
    riskLevel: typeof dispute.riskLevel === 'string' ? (dispute.riskLevel as Case['riskLevel']) : undefined,
    evidence: Array.isArray(dispute.evidence) ? (dispute.evidence as Case['evidence']) : undefined,
    evidenceGaps: Array.isArray(dispute.evidenceGaps) ? (dispute.evidenceGaps as Case['evidenceGaps']) : undefined,
    reasonCodeChecklist: Array.isArray(dispute.reasonCodeChecklist)
      ? (dispute.reasonCodeChecklist as Case['reasonCodeChecklist'])
      : undefined,
    rebuttalDraft:
      dispute.rebuttalDraft && typeof dispute.rebuttalDraft === 'object'
        ? (dispute.rebuttalDraft as Case['rebuttalDraft'])
        : undefined,
    updatedAt: typeof dispute.updatedAt === 'string' ? dispute.updatedAt : undefined,
    resolvedAt: typeof dispute.resolvedAt === 'string' ? dispute.resolvedAt : undefined,
  };

  return mapped;
}

async function tryGetCaseFromDisputes(caseId: string): Promise<Case | null> {
  try {
    const res = await fetch(`/api/disputes/${encodeURIComponent(caseId)}`);
    if (!res.ok) return null;
    const dispute = (await res.json()) as Record<string, unknown>;
    return normalizeCaseFromDispute(dispute, caseId);
  } catch {
    return null;
  }
}

async function apiFetch<T>(url: string, init?: RequestInit, fallback?: T): Promise<T> {
  if (USE_MOCK && fallback !== undefined) return fallback;

  const primaryUrl = buildApiUrl(url);
  const fallbackUrl = API_FALLBACK_BASE ? buildApiUrl(url, API_FALLBACK_BASE) : '';

  try {
    const res = await fetch(primaryUrl, init);
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    return res.json() as Promise<T>;
  } catch (err) {
    if (fallbackUrl && fallbackUrl !== primaryUrl) {
      try {
        const retry = await fetch(fallbackUrl, init);
        if (!retry.ok) throw new Error(`HTTP ${retry.status}: ${retry.statusText}`);
        return retry.json() as Promise<T>;
      } catch (fallbackErr) {
        console.warn('[API] Fallback endpoint failed for', url, fallbackErr);
      }
    }

    // Only fall back to mock data in local dev or when mock mode is explicitly enabled.
    // In production builds this block is unreachable when USE_MOCK is false, but the
    // explicit guard ensures a live-API failure is never silently swallowed.
    if ((import.meta.env.DEV || USE_MOCK) && fallback !== undefined) {
      console.warn('[API] Falling back to mock data for', url, err);
      return fallback;
    }
    throw err;
  }
}

export async function getCases(): Promise<CaseSummary[]> {
  const data = await apiFetch<{ cases: CaseSummary[] }>(
    '/api/cases',
    undefined,
    { cases: mockCaseSummaries }
  );
  return data.cases;
}

export async function getCase(caseId: string): Promise<Case> {
  const fallback = mockCases[caseId];
  try {
    return await apiFetch<Case>(`/api/cases/${caseId}`, undefined, fallback);
  } catch (err) {
    const mapped = await tryGetCaseFromDisputes(caseId);
    if (mapped) return mapped;
    throw err;
  }
}

export async function postAction(
  caseId: string,
  action: 'approve' | 'deny' | 'escalate' | 'reroute' | 'reopen',
  payload: ActionPayload
): Promise<ActionResult> {
  const mockStatusMap: Record<string, string> = {
    approve: 'approved',
    deny: 'denied',
    escalate: 'escalated',
    reroute: 'pending_review',
    reopen: 'pending_review',
  };
  const mockStatus = mockStatusMap[action] ?? 'pending_review';
  return apiFetch<ActionResult>(
    `/api/cases/${caseId}/${action}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    { status: mockStatus }
  );
}

export interface NoteResult {
  caseId: string;
  note: string;
  analystId: string;
  timestamp: string;
}

export interface RecommendationResponsePayload {
  analystId: string;
  decision: 'accept' | 'reject' | 'modify';
  recommendationDisposition: string;
  recommendationConfidence: number;
  reasoning: string[];
  comment?: string;
  modifiedRecommendation?: string;
}

export interface RecommendationResponseResult {
  caseId: string;
  analystId: string;
  decision: 'accept' | 'reject' | 'modify';
  status: 'recorded';
  timestamp: string;
}

export interface EvidenceGapRequestPayload {
  analystId: string;
  missingItem: string;
  reason: string;
  impact: 'critical' | 'high' | 'medium' | 'low';
  suggestedAction?: string;
}

export interface EvidenceGapRequestResult {
  caseId: string;
  analystId: string;
  missingItem: string;
  status: 'requested';
  timestamp: string;
}

export interface CaseDocument {
  documentId: string;
  caseId: string;
  filename: string;
  contentType: string;
  sizeBytes: number;
  uploadedAt: string;
  submittedBy?: string;
  submittedFrom?: string;
  note?: string;
  blobUrl?: string;
  analysis?: {
    evidenceScore?: number;
    documentType?: string;
    recommendation?: string;
  };
}

export interface UploadCaseDocumentResult {
  document: CaseDocument;
  scoreUpdate?: {
    adjustedWinProbability: number;
    adjustment: number;
    reason: string;
    documentsAnalyzed: number;
  };
  message: string;
}

export async function postNote(
  caseId: string,
  payload: ActionPayload
): Promise<NoteResult> {
  return apiFetch<NoteResult>(
    `/api/cases/${caseId}/add-note`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    { caseId, note: payload.comment ?? '', analystId: payload.analystId, timestamp: new Date().toISOString() }
  );
}

export async function postRecommendationResponse(
  caseId: string,
  payload: RecommendationResponsePayload
): Promise<RecommendationResponseResult> {
  return apiFetch<RecommendationResponseResult>(
    `/api/cases/${caseId}/recommendation-response`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    {
      caseId,
      analystId: payload.analystId,
      decision: payload.decision,
      status: 'recorded',
      timestamp: new Date().toISOString(),
    }
  );
}

export async function postEvidenceGapRequest(
  caseId: string,
  payload: EvidenceGapRequestPayload
): Promise<EvidenceGapRequestResult> {
  return apiFetch<EvidenceGapRequestResult>(
    `/api/cases/${caseId}/evidence-gaps/request`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    {
      caseId,
      analystId: payload.analystId,
      missingItem: payload.missingItem,
      status: 'requested',
      timestamp: new Date().toISOString(),
    }
  );
}

export async function getTimeline(caseId: string): Promise<TimelineEvent[]> {
  const fallback = mockTimelines[caseId] ?? [];
  const data = await apiFetch<{ caseId: string; events: TimelineEvent[] }>(
    `/api/cases/${caseId}/timeline`,
    undefined,
    { caseId, events: fallback }
  );
  return data.events;
}

export async function getCaseDocuments(caseId: string): Promise<CaseDocument[]> {
  const data = await apiFetch<{ caseId: string; documents: CaseDocument[] }>(
    `/api/cases/${caseId}/documents`,
    undefined,
    { caseId, documents: [] }
  );
  return data.documents ?? [];
}

export async function uploadCaseDocument(
  caseId: string,
  file: File,
  metadata: { submittedBy: string; submittedFrom: string; note?: string }
): Promise<UploadCaseDocumentResult> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('submittedBy', metadata.submittedBy);
  formData.append('submittedFrom', metadata.submittedFrom);
  if (metadata.note) {
    formData.append('note', metadata.note);
  }

  return apiFetch<UploadCaseDocumentResult>(
    `/api/cases/${caseId}/documents`,
    {
      method: 'POST',
      body: formData,
    },
    {
      document: {
        documentId: `doc-${Date.now()}`,
        caseId,
        filename: file.name,
        contentType: file.type || 'application/octet-stream',
        sizeBytes: file.size,
        uploadedAt: new Date().toISOString(),
        submittedBy: metadata.submittedBy,
        submittedFrom: metadata.submittedFrom,
        note: metadata.note,
        analysis: {
          evidenceScore: 0.5,
          documentType: 'general_document',
          recommendation: 'Mock upload fallback result.',
        },
      },
      message: `Document '${file.name}' uploaded (mock).`,
    }
  );
}

export interface GapsApiResponse {
  network: string;
  code: string;
  totalRequired: number;
  totalGathered: number;
  completionPct: number;
  gaps: Array<{ id: string; label: string; type: string; priority: string; gathered: boolean }>;
  gathered: Array<{ id: string; label: string; type: string; priority: string; gathered: boolean }>;
  readyForRebuttal: boolean;
}
/**
 * Call the evidence gaps API to compute real-time gap analysis
 * for a given reason code and set of gathered evidence types.
 */
export async function fetchEvidenceGaps(
  network: string,
  code: string,
  gatheredEvidenceIds: string[]
): Promise<EvidenceGap[]> {
  try {
    const data = await apiFetch<GapsApiResponse>(
      `/api/reason-codes/${encodeURIComponent(network)}/${encodeURIComponent(code)}/gaps`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ gatheredEvidenceIds }),
      }
    );
    // Map API gaps to EvidenceGap format expected by the panel
    return data.gaps.map(g => ({
      missingItem: g.label,
      reason: `Required ${g.type} evidence not yet gathered`,
      impact: g.priority === 'required' ? 'critical' as const : 'medium' as const,
      suggestedAction: `Retrieve ${g.label.toLowerCase()} from source systems`,
    }));
  } catch {
    return [];
  }
}

// ── Reprocess (re-run AI pipeline) ────────────────────────────────────────────

export interface ReprocessScoreResult {
  winProbability: number;
  riskLevel: RiskLevel;
  category: 'auto_approve' | 'review' | 'escalate';
  baseWinRate: number | null;
  completionPct: number;
  readyForRebuttal: boolean;
  criticalGaps: number;
}

export interface ReprocessGapsResult {
  reasonCodeChecklist: ReasonCodeChecklistItem[];
  evidenceGaps: EvidenceGap[];
  missingRequiredCount: number;
  alertThreshold: number;
  alertTriggered: boolean;
  completionPct: number;
  readyForRebuttal: boolean;
}

export interface ReprocessRebuttalResult {
  rebuttalText: string;
  citations: Array<{ evidenceId: string; excerpt: string }>;
  network: string;
  reasonCode: string;
  networkFormat: string;
  grounded: boolean;
  evidenceCited: number;
  source: 'foundry' | 'stub';
}

export interface ReprocessResult {
  disputeId: string;
  reprocessedAt: string;
  evidence: { totalRetrieved: number; totalRequired: number };
  gaps: ReprocessGapsResult;
  score: ReprocessScoreResult;
  rebuttal: ReprocessRebuttalResult;
}

/**
 * Re-trigger the full AI pipeline for a dispute: evidence retrieval -> gaps
 * detection -> win-probability/risk scoring -> maker-agent rebuttal drafting.
 * No mock fallback — this genuinely requires the backend pipeline to run.
 */
export async function reprocessDispute(caseId: string): Promise<ReprocessResult> {
  return apiFetch<ReprocessResult>(`/api/disputes/${caseId}/reprocess`, { method: 'POST' });
}

// ── Evidence Retrieval Agent (#12): precedents & network rules ────────────────

export interface PrecedentResultItem {
  id: string;
  sourceType: string;            // network_rule | evidence_requirement | precedent
  title: string;
  snippet: string;
  score: number | null;
  rerankerScore: number | null;
  citationLabel: string;
  sourceUrl: string;
  cardNetwork: string;
  reasonCode: string;
  tags: string[];
}

export interface PrecedentCitation {
  label: string;
  url: string | null;
}

export interface PrecedentResult {
  disputeId: string;
  network: string;
  reasonCode: string;
  results: PrecedentResultItem[];
  rules: PrecedentResultItem[];
  evidenceRequirements: PrecedentResultItem[];
  precedents: PrecedentResultItem[];
  citations: PrecedentCitation[];
  topK: number;
  matchMode: string;             // exact | network_category | semantic | none
  retrievedAt: string;
  source: string;                // search | agent | stub | mock
  retrievalMode?: string;        // hybrid | keyword_semantic | none
  usedVector?: boolean;
  rationale?: string;
}

/**
 * Retrieve relevant card-network rules, evidence requirements, and case
 * precedents for a dispute from Azure AI Search (#12). Falls back to sample
 * data in mock mode or when the API is unreachable in local dev.
 */
export async function retrievePrecedents(
  caseId: string,
  network: string | undefined,
  reasonCode: string,
  topK = 5,
): Promise<PrecedentResult> {
  return apiFetch<PrecedentResult>(
    `/api/disputes/${encodeURIComponent(caseId)}/retrieve-precedents`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ network, reasonCode, topK }),
    },
    mockPrecedentsFor(network, reasonCode, topK),
  );
}
