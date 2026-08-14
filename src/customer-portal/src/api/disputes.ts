/**
 * API client for the Customer Portal dispute submission flow.
 *
 * Endpoints consumed:
 *   POST /api/disputes          — create a new dispute (required fields documented in cosmos_models.py)
 *   GET  /api/disputes/{id}?networkCode= — retrieve a created dispute for confirmation
 *
 * In demo/mock mode (`VITE_USE_MOCK=true`) the client returns synthetic data.
 * Production requests must use the live backend and surface real persistence errors.
 *
 * DEADLINE CONTRACT (per Keaton's keaton-portal-contract decision): the
 * server now auto-calculates `deadlineUtc` from per-network SLA rules
 * (visa=30/mastercard=45/amex=20/discover=30 days) whenever the field is
 * omitted (or falsy) from the POST body — see `_handle_create_dispute` in
 * src/api/function_app.py: `body.get("deadlineUtc") or _compute_deadline_utc(...)`.
 * The portal therefore no longer sends a client-computed `deadlineUtc` on the
 * real API path; `computeDeadlineUtc()` is retained only as a demo-mode
 * estimate for `mockDisputeResponse`, since there's no server there to
 * compute the real value.
 *
 * KNOWN GAP: GET /api/disputes/{id} requires a `networkCode` query parameter
 * (Cosmos DB partition key). This is an unusual requirement for a customer-
 * facing portal — the customer would need to know the networkCode to look up
 * their own dispute. For the MVP we include the networkCode in a context store
 * from the submission payload. See .squad/decisions/inbox/redfoot-customer-portal-gap.md.
 */

import type { DisputeSubmissionPayload, DisputeCreatedResponse } from '../types/dispute.ts';

export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api';

function mockDisputeResponse(payload: DisputeSubmissionPayload): DisputeCreatedResponse {
  return {
    id: 'demo-' + Math.random().toString(36).slice(2, 10),
    disputeId: 'demo-' + Math.random().toString(36).slice(2, 10),
    networkCode: payload.networkCode,
    reasonCode: payload.reasonCode,
    status: 'intake',
    cardholderName: payload.cardholderName,
    cardLastFour: payload.cardLastFour,
    transactionAmount: payload.transactionAmount,
    transactionCurrency: payload.transactionCurrency,
    transactionDate: payload.transactionDate,
    merchantName: payload.merchantName,
    // Mock mode has no server to auto-calculate the deadline, so fall back
    // to the client-side estimate if the caller didn't already supply one.
    deadlineUtc: payload.deadlineUtc ?? computeDeadlineUtc(),
    createdAt: new Date().toISOString(),
  };
}

export async function submitDispute(
  payload: DisputeSubmissionPayload
): Promise<DisputeCreatedResponse> {
  if (USE_MOCK) {
    await new Promise(r => setTimeout(r, 800)); // simulate network
    return mockDisputeResponse(payload);
  }

  try {
    const res = await fetch(`${API_BASE}/disputes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      const apiMessage = (errBody as { error?: string }).error ?? `HTTP ${res.status}: ${res.statusText}`;
      throw new Error(apiMessage);
    }
    return res.json() as Promise<DisputeCreatedResponse>;
  } catch (err) {
    if (USE_MOCK || import.meta.env.DEV) {
      console.warn('[API] submitDispute falling back to demo mode:', err);
      return mockDisputeResponse(payload);
    }
    throw err;
  }
}

export async function getDispute(
  disputeId: string,
  networkCode: string
): Promise<DisputeCreatedResponse> {
  if (USE_MOCK) {
    await new Promise(r => setTimeout(r, 400));
    throw new Error('Demo mode: GET dispute not available');
  }

  const res = await fetch(`${API_BASE}/disputes/${disputeId}?networkCode=${encodeURIComponent(networkCode)}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
  return res.json() as Promise<DisputeCreatedResponse>;
}

export async function listCustomerDisputes(
  customerId: string,
  cardholderName?: string,
  cardLastFour?: string,
): Promise<DisputeCreatedResponse[]> {
  if (USE_MOCK) {
    return [];
  }

  const params = new URLSearchParams();
  params.set('includeClosed', 'true');
  if (cardholderName?.trim()) {
    params.set('cardholderName', cardholderName.trim());
  }
  if (cardLastFour?.trim()) {
    params.set('cardLastFour', cardLastFour.trim());
  }

  const res = await fetch(
    `${API_BASE}/disputes/customer/${encodeURIComponent(customerId)}?${params.toString()}`
  );
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);

  const payload = await res.json() as { disputes?: DisputeCreatedResponse[] };
  return payload.disputes ?? [];
}

/** Compute a response deadline: 45 calendar days from today. */
export function computeDeadlineUtc(): string {
  const d = new Date();
  d.setDate(d.getDate() + 45);
  return d.toISOString();
}

// ── Document Upload ──────────────────────────────────────────────────────────

export interface UploadDocumentResponse {
  document: {
    id?: string;
    documentId?: string;
    filename: string;
    contentType: string;
    sizeBytes: number;
    uploadedAt: string;
  };
  scoreUpdate?: {
    previousScore: number;
    newScore: number;
  };
  message: string;
}

export interface StoredCaseDocument {
  documentId: string;
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
  closure?: {
    artifactType?: string;
    caseId?: string;
    disposition?: string;
    analystId?: string;
    reason?: string;
    createdAt?: string;
    details?: {
      networkCode?: string;
      reasonCode?: string;
      merchantName?: string;
      transactionAmount?: number;
      transactionDate?: string;
      cardLastFour?: string;
      deadlineUtc?: string;
    };
  };
}

export interface TimelineEvent {
  id: string;
  disputeId: string;
  eventType: string;
  actor: string;
  detail: string;
  data?: Record<string, unknown>;
  occurredAt: string;
}

export interface CustomerResponsePayload {
  customerId?: string;
  comment: string;
  attachmentDocumentIds?: string[];
}

/**
 * Upload a single file as evidence for a case.
 * Uses multipart/form-data with field name 'file'.
 */
export async function uploadDocument(
  caseId: string,
  file: File,
  metadata?: { submittedBy?: string; submittedFrom?: string; note?: string },
): Promise<UploadDocumentResponse> {
  if (USE_MOCK) {
    await new Promise(r => setTimeout(r, 300 + Math.random() * 400));
    return {
      document: {
        id: 'doc-' + Math.random().toString(36).slice(2, 10),
        filename: file.name,
        contentType: file.type,
        sizeBytes: file.size,
        uploadedAt: new Date().toISOString(),
      },
      message: `Document '${file.name}' uploaded and analyzed.`,
    };
  }

  const formData = new FormData();
  formData.append('file', file);
  if (metadata?.submittedBy) {
    formData.append('submittedBy', metadata.submittedBy);
  }
  if (metadata?.submittedFrom) {
    formData.append('submittedFrom', metadata.submittedFrom);
  }
  if (metadata?.note) {
    formData.append('note', metadata.note);
  }

  try {
    const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/documents`, {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(
        (errBody as { error?: string }).error ?? `Upload failed: HTTP ${res.status}`
      );
    }

    return res.json() as Promise<UploadDocumentResponse>;
  } catch (err) {
    if (import.meta.env.DEV) {
      console.warn('[API] uploadDocument falling back to demo mode:', err);
      return {
        document: {
          id: 'doc-' + Math.random().toString(36).slice(2, 10),
          filename: file.name,
          contentType: file.type,
          sizeBytes: file.size,
          uploadedAt: new Date().toISOString(),
        },
        message: `Document '${file.name}' uploaded (demo mode).`,
      };
    }
    throw err;
  }
}

/**
 * Fetch all documents previously uploaded for a case.
 */
export async function getCaseDocuments(caseId: string): Promise<StoredCaseDocument[]> {
  if (USE_MOCK) return [];
  const res = await fetch(`${API_BASE}/cases/${encodeURIComponent(caseId)}/documents`);
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
  const data = await res.json() as { documents?: StoredCaseDocument[] };
  return data.documents ?? [];
}

/**
 * Retrieve dispute timeline events (analyst notes, decisions, customer responses, etc.).
 */
export async function getDisputeTimeline(disputeId: string): Promise<TimelineEvent[]> {
  if (USE_MOCK) {
    return [];
  }
  const res = await fetch(`${API_BASE}/disputes/${encodeURIComponent(disputeId)}/timeline`);
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
  return res.json() as Promise<TimelineEvent[]>;
}

/**
 * Persist a customer response so analyst + AI can reference it later.
 */
export async function submitCustomerResponse(
  disputeId: string,
  payload: CustomerResponsePayload,
): Promise<{ disputeId: string; eventId?: string; status: string }> {
  if (USE_MOCK) {
    return { disputeId, status: 'recorded' };
  }
  const res = await fetch(`${API_BASE}/disputes/${encodeURIComponent(disputeId)}/customer-response`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    throw new Error((errBody as { error?: string }).error ?? `HTTP ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<{ disputeId: string; eventId?: string; status: string }>;
}

/**
 * Cancel an in-flight dispute claim that has not yet been acted on by the network.
 */
export async function cancelDispute(
  disputeId: string,
  customerId: string,
  reason?: string,
): Promise<{ disputeId: string; status: string }> {
  if (USE_MOCK) {
    await new Promise(r => setTimeout(r, 400));
    return { disputeId, status: 'cancelled' };
  }
  const res = await fetch(`${API_BASE}/disputes/${encodeURIComponent(disputeId)}/cancel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ customerId, reason: reason ?? 'Customer requested cancellation' }),
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    throw new Error((errBody as { error?: string }).error ?? `HTTP ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<{ disputeId: string; status: string }>;
}
