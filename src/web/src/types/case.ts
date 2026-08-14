/**
 * Dispute Case TypeScript types.
 *
 * Mirrors src/shared/schemas/case.schema.json (JSON Schema draft 2020-12).
 * Hand-maintained for now; see src/shared/README.md for the contract.
 * Update this file whenever the JSON Schema changes.
 */

// ── String-literal unions (mirror $defs in the JSON Schema) ──────────────────

export type CaseStatus =
  | "intake"
  | "evidence_gathering"
  | "ai_drafting"
  | "pending_review"
  | "approved"
  | "denied"
  | "escalated"
  | "submitted"
  | "expired"
  | "closed";

export type CardNetwork = "visa" | "mastercard" | "amex" | "discover";

export type RiskLevel = "low" | "medium" | "high" | "critical";

export type EvidenceType =
  | "transaction"
  | "shipping"
  | "communication"
  | "receipt"
  | "contract"
  | "fraud_signal"
  | "order"
  | "photo"
  | "fraud_screening"
  | "device_fingerprint";

export type CompletenessLevel = "complete" | "partial" | "missing";

export type ImpactLevel = "critical" | "high" | "medium" | "low";

// ── Nested object interfaces ──────────────────────────────────────────────────

export interface ReasonCodeChecklistItem {
  item: string;
  required: boolean;
  satisfied: boolean;
}

export interface Evidence {
  evidenceId: string;       // UUID
  type: EvidenceType;
  sourceSystem: string;
  retrievedAt: string;      // ISO 8601 date-time
  contentRef: string;       // Blob URI or document ID
  completeness: CompletenessLevel;
}

export interface EvidenceGap {
  missingItem: string;
  reason: string;
  impact: ImpactLevel;
  suggestedAction?: string;
}

export interface Citation {
  evidenceId: string;
  excerpt: string;
}

export interface RebuttalDraft {
  text: string;
  citations: Citation[];
}

export interface Deadline {
  network: string;
  dueDate: string;          // ISO 8601 date
  daysRemaining: number;
}

/** Deadline subset for CaseSummary — omits network. */
export interface CaseSummaryDeadline {
  dueDate: string;          // ISO 8601 date
  daysRemaining: number;
}

// ── Timeline types ────────────────────────────────────────────────────────────

export type TimelineEventType =
  | "case_created"
  | "evidence_retrieved"
  | "evidence_gap_detected"
  | "score_generated"
  | "ai_draft_generated"
  | "status_changed"
  | "status_change"
  | "analyst_assigned"
  | "analyst_action"
  | "escalated"
  | "deadline_warning"
  | "document_uploaded"
  | "comment_added"
  | "analyst_note"
  | "ai_recommendation_response"
  | "evidence_gap_requested"
  | "customer_response"
  | "case_closed_artifact_created"
  | "customer_response_requested"
  | "customer_response_received"
  // Transaction events
  | "authorization"
  | "clearing"
  | "settlement"
  | "refund"
  | "chargeback"
  | "representment"
  | "arbitration"
  // Customer activity
  | "customer_login"
  | "device_change"
  | "mfa_event"
  | "geolocation"
  | "previous_purchase"
  // Fraud signals
  | "velocity_alert"
  | "device_reputation"
  | "ip_reputation"
  | "high_risk_indicator"
  | "friendly_fraud_indicator";

export type TimelineCategory = "transaction" | "customer_activity" | "fraud_signals" | "case_activity";

export interface TimelineEvent {
  eventId: string;
  disputeId: string;
  eventType: TimelineEventType;
  timestamp: string;         // ISO 8601 date-time
  actor?: string;            // system | analyst name
  description: string;
  metadata?: Record<string, unknown>;
}

// ── Top-level interfaces ──────────────────────────────────────────────────────

/** Full dispute case record. */
export interface Case {
  // Required
  caseId: string;                        // UUID
  status: CaseStatus;
  reasonCode: string;                    // e.g. "Visa 13.1"
  deadline: Deadline;
  createdAt: string;                     // ISO 8601 date-time

  // Assignment (optional — null/undefined = unassigned = "Open")
  assignedAnalystId?: string;
  assignedAnalystName?: string;

  // Identifiers (optional)
  orchestrationId?: string;              // Durable Functions instance ID (equals caseId)
  disputeRef?: string;                   // Network ARN / reference
  cardNetwork?: CardNetwork;
  merchantName?: string;
  cardholderName?: string;
  caseDescription?: string;
  transactionAmount?: number;
  transactionDate?: string;              // ISO 8601 date

  // Reason code detail (optional)
  reasonCodeLabel?: string;
  reasonCodeChecklist?: ReasonCodeChecklistItem[];

  // Evidence (optional)
  evidence?: Evidence[];
  evidenceGaps?: EvidenceGap[];

  // Scoring (optional)
  winProbability?: number;               // 0–1
  riskLevel?: RiskLevel;

  // Rebuttal (optional)
  rebuttalDraft?: RebuttalDraft;

  // Timestamps (optional)
  updatedAt?: string;                    // ISO 8601 date-time
  resolvedAt?: string;                   // ISO 8601 date-time
}

/**
 * Lightweight queue-list subset.
 * Mirrors CaseSummary in the JSON Schema — returned by GET /cases.
 */
export interface CaseSummary {
  // Required
  caseId: string;
  status: CaseStatus;
  reasonCode: string;
  deadline: CaseSummaryDeadline;
  createdAt: string;                     // ISO 8601 date-time

  // Assignment (optional — null/undefined = unassigned = "Open")
  assignedAnalystId?: string;
  assignedAnalystName?: string;

  // Optional
  cardNetwork?: CardNetwork;
  merchantName?: string;
  caseDescription?: string;
  transactionAmount?: number;
  reasonCodeLabel?: string;
  winProbability?: number;               // 0–1
  riskLevel?: RiskLevel;
  updatedAt?: string;                    // ISO 8601 date-time
  lastActivityAt?: string;               // ISO 8601 date-time
  lastActivityType?: string;
  lastActivityActor?: string;
  lastActivityDetail?: string;
}
