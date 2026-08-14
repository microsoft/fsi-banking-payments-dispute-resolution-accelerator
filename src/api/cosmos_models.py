"""
Data models for the Payments Dispute Resolution operational store (Cosmos DB).

Each model maps to a container in the 'disputes-db' database:
  - disputes   → DisputeCase
  - evidence   → EvidenceItem
  - timeline   → TimelineEvent
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class DisputeStatus(str, Enum):
    INTAKE = "intake"
    GATHERING = "gathering"
    DRAFTING = "drafting"
    REVIEW = "review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUBMITTED = "submitted"
    ESCALATED = "escalated"
    CLOSED = "closed"


class CardNetwork(str, Enum):
    VISA = "visa"
    MASTERCARD = "mastercard"
    AMEX = "amex"
    DISCOVER = "discover"


class EvidenceType(str, Enum):
    TRANSACTION = "transaction"
    ORDER = "order"
    SHIPPING = "shipping"
    COMMUNICATION = "communication"
    FRAUD_SIGNAL = "fraud_signal"
    RECEIPT = "receipt"
    CONTRACT = "contract"
    OTHER = "other"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def new_dispute(
    *,
    network_code: str,
    reason_code: str,
    cardholder_name: str,
    card_last_four: str,
    transaction_amount: float,
    transaction_currency: str = "USD",
    transaction_date: str,
    merchant_name: str,
    deadline_utc: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a new dispute case document."""
    dispute_id = _new_id()
    return {
        "id": dispute_id,
        "disputeId": dispute_id,
        "networkCode": network_code,
        "reasonCode": reason_code,
        "status": DisputeStatus.INTAKE.value,
        "cardholderName": cardholder_name,
        "cardLastFour": card_last_four,
        "transactionAmount": transaction_amount,
        "transactionCurrency": transaction_currency,
        "transactionDate": transaction_date,
        "merchantName": merchant_name,
        "deadlineUtc": deadline_utc,
        "winProbability": None,
        "riskScore": None,
        "assignedAnalyst": None,
        "rebuttalDraft": None,
        "submissionPackageUrl": None,
        "metadata": metadata or {},
        "createdAt": _utcnow(),
        "updatedAt": _utcnow(),
    }


def new_evidence_item(
    *,
    dispute_id: str,
    evidence_type: str,
    source_system: str,
    title: str,
    content: dict[str, Any] | None = None,
    blob_url: str | None = None,
) -> dict[str, Any]:
    """Create a new evidence item document."""
    item_id = _new_id()
    return {
        "id": item_id,
        "evidenceId": item_id,
        "disputeId": dispute_id,
        "evidenceType": evidence_type,
        "sourceSystem": source_system,
        "title": title,
        "content": content,
        "blobUrl": blob_url,
        "extractedAt": _utcnow(),
    }


def new_timeline_event(
    *,
    dispute_id: str,
    event_type: str,
    actor: str,
    detail: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a new timeline/audit event document."""
    event_id = _new_id()
    return {
        "id": event_id,
        "eventId": event_id,
        "disputeId": dispute_id,
        "eventType": event_type,
        "actor": actor,
        "detail": detail,
        "data": data or {},
        "occurredAt": _utcnow(),
    }
