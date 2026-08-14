/**
 * Types for the Customer Portal dispute submission flow.
 *
 * These types mirror the POST /api/disputes contract defined in
 * src/api/function_app.py and src/api/cosmos_models.py.
 */

// ── Card network ──────────────────────────────────────────────────────────────

export type CardNetwork = 'visa' | 'mastercard' | 'amex' | 'discover';

// ── Demo transaction (seed data, not from API) ────────────────────────────────

export interface DemoTransaction {
  id: string;
  merchantName: string;
  merchantCategory: string;
  amount: number;
  currency: string;
  date: string;          // ISO date e.g. "2026-06-15"
  cardLastFour: string;
  cardNetwork: CardNetwork;
  description: string;
}

// ── Reason code option ────────────────────────────────────────────────────────

export interface ReasonCodeOption {
  code: string;           // e.g. "Visa 13.1"
  label: string;          // e.g. "Merchandise/Services Not Received"
  network: CardNetwork;
}

// ── Document attachment metadata ──────────────────────────────────────────────

export interface DocumentMeta {
  name: string;
  size: number;   // bytes
  type: string;   // MIME type
}

// ── Dispute form data (collected across the wizard) ───────────────────────────

export interface DisputeFormData {
  reasonCode: string;
  cardholderName: string;
  description: string;
}

// ── Submission payload — matches POST /api/disputes body ─────────────────────

export interface DisputeSubmissionPayload {
  networkCode: string;
  reasonCode: string;
  cardholderName: string;
  cardLastFour: string;
  transactionAmount: number;
  transactionCurrency: string;
  transactionDate: string;
  merchantName: string;
  /**
   * Optional — omitted for the real API path so the server can auto-calculate
   * the deadline from per-network SLA rules (visa=30/mastercard=45/amex=20/
   * discover=30 days). Only populated client-side in mock/demo mode, where
   * there is no server to compute it. See _handle_create_dispute in
   * src/api/function_app.py: `body.get("deadlineUtc") or _compute_deadline_utc(...)`.
   */
  deadlineUtc?: string;
  metadata: {
    description: string;
    attachments: DocumentMeta[];
    merchantCategory: string;
    portalSubmission: true;
    customerId?: string;
  };
}

// ── API response from POST /api/disputes ─────────────────────────────────────

export interface DisputeCreatedResponse {
  id: string;
  disputeId: string;
  networkCode: string;
  reasonCode: string;
  status: string;
  cardholderName: string;
  cardLastFour: string;
  transactionAmount: number;
  transactionCurrency: string;
  transactionDate: string;
  merchantName: string;
  deadlineUtc: string;
  createdAt: string;
  updatedAt?: string;
  metadata?: {
    customerId?: string;
    description?: string;
    [key: string]: unknown;
  };
}
