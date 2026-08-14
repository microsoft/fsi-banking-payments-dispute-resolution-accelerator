"""
Dispute Case data models.

Mirrors src/shared/schemas/case.schema.json (JSON Schema draft 2020-12).
Hand-maintained for now; see src/shared/README.md for the contract.
Update this file whenever the JSON Schema changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


# ── String-literal unions (mirror $defs in the JSON Schema) ──────────────────

CaseStatus = Literal[
    "intake",
    "evidence_gathering",
    "ai_drafting",
    "pending_review",
    "approved",
    "denied",
    "escalated",
    "submitted",
    "expired",
]

CardNetwork = Literal["visa", "mastercard", "amex", "discover"]

RiskLevel = Literal["low", "medium", "high", "critical"]

EvidenceType = Literal[
    "transaction",
    "shipping",
    "communication",
    "receipt",
    "contract",
    "fraud_signal",
    "order",
]

CompletenessLevel = Literal["complete", "partial", "missing"]

ImpactLevel = Literal["critical", "high", "medium", "low"]


# ── Nested object models ──────────────────────────────────────────────────────

@dataclass
class ReasonCodeChecklistItem:
    item: str
    required: bool
    satisfied: bool


@dataclass
class Evidence:
    evidenceId: str            # UUID
    type: EvidenceType
    sourceSystem: str
    retrievedAt: str           # ISO 8601 date-time
    contentRef: str            # Blob URI or document ID
    completeness: CompletenessLevel


@dataclass
class EvidenceGap:
    missingItem: str
    reason: str
    impact: ImpactLevel


@dataclass
class Citation:
    evidenceId: str
    excerpt: str


@dataclass
class RebuttalDraft:
    text: str = ""
    citations: list[Citation] = field(default_factory=list)


@dataclass
class Deadline:
    network: str
    dueDate: str               # ISO 8601 date
    daysRemaining: int


@dataclass
class CaseSummaryDeadline:
    """Deadline subset for CaseSummary — omits network."""
    dueDate: str               # ISO 8601 date
    daysRemaining: int


# ── Top-level models ──────────────────────────────────────────────────────────

@dataclass
class Case:
    """Full dispute case record."""
    # Required fields
    caseId: str                # UUID
    status: CaseStatus
    reasonCode: str            # e.g. "Visa 13.1"
    deadline: Deadline
    createdAt: str             # ISO 8601 date-time

    # Identifiers (optional)
    orchestrationId: Optional[str] = None      # Durable Functions instance ID (equals caseId)
    disputeRef: Optional[str] = None           # Network ARN / reference
    cardNetwork: Optional[CardNetwork] = None
    merchantName: Optional[str] = None
    cardholderName: Optional[str] = None
    caseDescription: Optional[str] = None
    transactionAmount: Optional[float] = None
    transactionDate: Optional[str] = None      # ISO 8601 date

    # Reason code detail
    reasonCodeLabel: Optional[str] = None
    reasonCodeChecklist: list[ReasonCodeChecklistItem] = field(default_factory=list)

    # Evidence
    evidence: list[Evidence] = field(default_factory=list)
    evidenceGaps: list[EvidenceGap] = field(default_factory=list)

    # Scoring
    winProbability: Optional[float] = None     # 0–1
    riskLevel: Optional[RiskLevel] = None

    # Rebuttal
    rebuttalDraft: Optional[RebuttalDraft] = None

    # Timestamps
    updatedAt: Optional[str] = None            # ISO 8601 date-time
    resolvedAt: Optional[str] = None           # ISO 8601 date-time


@dataclass
class CaseSummary:
    """
    Lightweight queue-list subset.
    Mirrors CaseSummary in the JSON Schema — returned by GET /cases.
    """
    # Required fields
    caseId: str
    status: CaseStatus
    reasonCode: str
    deadline: CaseSummaryDeadline
    createdAt: str             # ISO 8601 date-time

    # Optional fields
    cardNetwork: Optional[CardNetwork] = None
    merchantName: Optional[str] = None
    caseDescription: Optional[str] = None
    transactionAmount: Optional[float] = None
    reasonCodeLabel: Optional[str] = None
    winProbability: Optional[float] = None     # 0–1
    riskLevel: Optional[RiskLevel] = None
    updatedAt: Optional[str] = None            # ISO 8601 date-time
