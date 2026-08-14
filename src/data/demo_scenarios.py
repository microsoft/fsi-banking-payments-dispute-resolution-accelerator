"""
Named Demo Scenarios — Curated dispute cases for the July demo.

These are hand-crafted cases designed to showcase specific features:
1. "Sarah Chen — Friendly Fraud" → Full lifecycle, high win probability
2. "Urgent Deadline" → Visa dispute 2 days from deadline, escalation path
3. "Multi-System Evidence" → 7+ evidence sources assembled in minutes
4. "Maker-Checker Retry" → Groundedness check fails, maker retries, passes
5. "Escalation to Supervisor" → HITL timeout triggers escalation queue
6. "Cross-Network Comparison" → Same merchant, 4 different networks
7. "High-Value Fraud Ring" → $4,500+ fraud with card-testing pattern
8. "Reg E Debit Clock" → 10-business-day countdown with debit card

These scenarios produce disputes + evidence + timeline that can be loaded
alongside the bulk synthetic data to provide walkthrough-ready stories.
"""

import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _id():
    return str(uuid.uuid4())


NOW = datetime.now(timezone.utc)


# ===========================================================================
# Scenario 1: Sarah Chen — Friendly Fraud (Visa)
# Full lifecycle from intake to closed/won. High win probability.
# Shows: evidence assembly, AI drafting, analyst approval, network submission.
# ===========================================================================

SARAH_CHEN_DISPUTE = {
    "id": "demo-sarah-chen-001",
    "disputeId": "demo-sarah-chen-001",
    "networkCode": "visa",
    "reasonCode": "13.1",
    "reasonDescription": "Merchandise/Services Not Received",
    "reasonCategory": "consumer_dispute",
    "status": "closed",
    "cardholderName": "Sarah Chen",
    "cardholderCity": "San Francisco",
    "cardholderState": "CA",
    "cardLastFour": "4821",
    "transactionAmount": 892.50,
    "transactionCurrency": "USD",
    "transactionDate": (NOW - timedelta(days=45)).isoformat(),
    "merchantName": "TechGadgets Inc",
    "merchantCategory": "Electronics",
    "merchantMcc": "5732",
    "deadlineUtc": (NOW - timedelta(days=15)).isoformat(),
    "daysUntilDeadline": 0,
    "winProbability": 0.87,
    "riskScore": 72,
    "assignedAnalyst": "analyst-001",
    "evidenceRequired": ["shipping_confirmation", "delivery_proof", "tracking_number", "signed_delivery"],
    "evidenceCollected": 6,
    "evidenceGaps": 0,
    "rebuttalDraft": "Based on our investigation, the cardholder's claim of non-receipt is contradicted by delivery confirmation signed by 'S. Chen' at the billing address on file. UPS tracking #1Z999AA10123456784 confirms delivery on July 3, 2026. The GPS coordinates of delivery match the cardholder's registered address. Additionally, the cardholder's account shows login activity consistent with product activation 2 hours after confirmed delivery.",
    "submissionPackageUrl": "https://storage.blob.core.windows.net/submissions/demo-sarah-chen-001/package.pdf",
    "outcome": "won",
    "creditAmount": 892.50,
    "metadata": {"source": "demo_scenario", "scenario": "friendly_fraud", "version": "1.0"},
    "createdAt": (NOW - timedelta(days=44)).isoformat(),
    "updatedAt": (NOW - timedelta(days=10)).isoformat(),
}

SARAH_CHEN_EVIDENCE = [
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-sarah-chen-001",
        "evidenceType": "transaction", "sourceSystem": "payment_processor",
        "title": "Transaction Record — TechGadgets Inc",
        "content": {
            "transactionId": "TXN-784521", "amount": 892.50, "currency": "USD",
            "merchantName": "TechGadgets Inc", "authorizationCode": "847291",
            "cardPresent": False, "entryMode": "ecommerce",
            "avsResponse": "Y", "cvvResponse": "M",
            "processedAt": (NOW - timedelta(days=45)).isoformat(),
        },
        "extractedAt": (NOW - timedelta(days=44)).isoformat(),
    },
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-sarah-chen-001",
        "evidenceType": "shipping", "sourceSystem": "logistics",
        "title": "Shipping Record — UPS (Delivered with Signature)",
        "content": {
            "trackingNumber": "1Z999AA10123456784", "carrier": "UPS",
            "status": "delivered", "signedBy": "S. Chen",
            "deliveryDate": (NOW - timedelta(days=42)).isoformat(),
            "deliveryAddress": {"city": "San Francisco", "state": "CA"},
            "gpsCoordinates": "37.7749,-122.4194",
        },
        "extractedAt": (NOW - timedelta(days=44)).isoformat(),
    },
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-sarah-chen-001",
        "evidenceType": "order", "sourceSystem": "oms_erp",
        "title": "Order Record — ORD-445521",
        "content": {
            "orderId": "ORD-445521", "orderDate": (NOW - timedelta(days=45)).isoformat(),
            "orderStatus": "delivered",
            "items": [{"sku": "TG-LAPTOP-PRO", "description": "TechGadgets Pro Laptop 15\"", "quantity": 1, "unitPrice": 892.50}],
            "shippingAddress": {"city": "San Francisco", "state": "CA"},
        },
        "extractedAt": (NOW - timedelta(days=44)).isoformat(),
    },
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-sarah-chen-001",
        "evidenceType": "fraud_signal", "sourceSystem": "fraud_engine",
        "title": "Fraud Risk Assessment — Friendly Fraud Indicator",
        "content": {
            "riskScore": 72, "riskLevel": "medium",
            "signals": ["friendly_fraud_indicator", "account_age_established", "prior_successful_deliveries"],
            "previousChargebacks": 2, "accountAge": "36 months",
            "friendlyFraudProbability": 0.82,
        },
        "extractedAt": (NOW - timedelta(days=44)).isoformat(),
    },
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-sarah-chen-001",
        "evidenceType": "communication", "sourceSystem": "crm",
        "title": "Customer Communication — No contact from cardholder",
        "content": {
            "communicationType": "support_ticket", "subject": "No support contact on file",
            "date": (NOW - timedelta(days=44)).isoformat(),
            "summary": "No inbound contact from Sarah Chen regarding this order. No return request, no shipping inquiry. Product activation detected 2 hours post-delivery.",
        },
        "extractedAt": (NOW - timedelta(days=44)).isoformat(),
    },
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-sarah-chen-001",
        "evidenceType": "receipt", "sourceSystem": "document_intelligence",
        "title": "Receipt — TechGadgets Inc Invoice",
        "content": {
            "documentType": "invoice", "merchantName": "TechGadgets Inc",
            "amount": 892.50, "extractionConfidence": 0.97,
        },
        "blobUrl": "https://storage.blob.core.windows.net/evidence/demo-sarah-chen-001/invoice.pdf",
        "extractedAt": (NOW - timedelta(days=44)).isoformat(),
    },
]

SARAH_CHEN_TIMELINE = [
    {"id": _id(), "eventId": _id(), "disputeId": "demo-sarah-chen-001", "eventType": "status_change", "actor": "system", "detail": "Dispute created — Visa 13.1 (Merchandise Not Received)", "data": {"fromStatus": None, "toStatus": "intake"}, "occurredAt": (NOW - timedelta(days=44)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-sarah-chen-001", "eventType": "status_change", "actor": "orchestrator_agent", "detail": "Evidence gathering initiated — 6 source systems queried", "data": {"fromStatus": "intake", "toStatus": "evidence_gathering", "systemsQueried": 6}, "occurredAt": (NOW - timedelta(days=44, hours=-0.1)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-sarah-chen-001", "eventType": "evidence_retrieved", "actor": "evidence_agent", "detail": "Transaction record retrieved from payment processor", "data": {"sourceSystem": "payment_processor"}, "occurredAt": (NOW - timedelta(days=44, hours=-0.15)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-sarah-chen-001", "eventType": "evidence_retrieved", "actor": "evidence_agent", "detail": "UPS delivery confirmation with signature retrieved", "data": {"sourceSystem": "logistics"}, "occurredAt": (NOW - timedelta(days=44, hours=-0.2)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-sarah-chen-001", "eventType": "evidence_retrieved", "actor": "evidence_agent", "detail": "Order and fulfillment record retrieved", "data": {"sourceSystem": "oms_erp"}, "occurredAt": (NOW - timedelta(days=44, hours=-0.25)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-sarah-chen-001", "eventType": "evidence_retrieved", "actor": "evidence_agent", "detail": "Fraud risk assessment completed — friendly fraud probability 82%", "data": {"sourceSystem": "fraud_engine"}, "occurredAt": (NOW - timedelta(days=44, hours=-0.3)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-sarah-chen-001", "eventType": "status_change", "actor": "maker_agent", "detail": "Rebuttal draft generation — citing delivery proof + fraud signals", "data": {"fromStatus": "evidence_gathering", "toStatus": "ai_drafting"}, "occurredAt": (NOW - timedelta(days=44, hours=-0.5)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-sarah-chen-001", "eventType": "checker_passed", "actor": "checker_agent", "detail": "Groundedness validation passed — all claims cite verified evidence", "data": {"attempt": 1, "groundednessScore": 0.96}, "occurredAt": (NOW - timedelta(days=44, hours=-0.6)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-sarah-chen-001", "eventType": "status_change", "actor": "system", "detail": "Case assigned to Ana Rivera for human review", "data": {"fromStatus": "ai_drafting", "toStatus": "pending_review", "assignedAnalyst": "analyst-001"}, "occurredAt": (NOW - timedelta(days=44, hours=-0.7)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-sarah-chen-001", "eventType": "status_change", "actor": "analyst-001", "detail": "Dispute approved by Ana Rivera — strong evidence of friendly fraud", "data": {"fromStatus": "pending_review", "toStatus": "approved"}, "occurredAt": (NOW - timedelta(days=43)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-sarah-chen-001", "eventType": "status_change", "actor": "system", "detail": "Evidence package submitted to Visa network", "data": {"fromStatus": "approved", "toStatus": "submitted"}, "occurredAt": (NOW - timedelta(days=43, hours=-1)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-sarah-chen-001", "eventType": "status_change", "actor": "system", "detail": "Case closed — dispute won. Full credit of $892.50 retained.", "data": {"fromStatus": "submitted", "toStatus": "closed", "outcome": "won", "creditAmount": 892.50}, "occurredAt": (NOW - timedelta(days=10)).isoformat()},
]


# ===========================================================================
# Scenario 2: Urgent Deadline — Mastercard, 2 days left
# Shows: deadline pressure, SLA countdown, prioritization
# ===========================================================================

URGENT_DEADLINE_DISPUTE = {
    "id": "demo-urgent-deadline-001",
    "disputeId": "demo-urgent-deadline-001",
    "networkCode": "mastercard",
    "reasonCode": "4853",
    "reasonDescription": "Cardholder Dispute — Goods/Services",
    "reasonCategory": "consumer_dispute",
    "status": "pending_review",
    "cardholderName": "James Kim",
    "cardholderCity": "Seattle",
    "cardholderState": "WA",
    "cardLastFour": "7392",
    "transactionAmount": 1247.99,
    "transactionCurrency": "USD",
    "transactionDate": (NOW - timedelta(days=43)).isoformat(),
    "merchantName": "HomeReno Solutions",
    "merchantCategory": "Home Improvement",
    "merchantMcc": "5211",
    "deadlineUtc": (NOW + timedelta(days=2)).isoformat(),
    "daysUntilDeadline": 2,
    "winProbability": 0.62,
    "riskScore": 45,
    "assignedAnalyst": "analyst-003",
    "evidenceRequired": ["shipping_proof", "delivery_confirmation", "product_description", "communication_records"],
    "evidenceCollected": 5,
    "evidenceGaps": 1,
    "rebuttalDraft": "The cardholder received the ordered materials as confirmed by FedEx tracking and signed delivery receipt. While the cardholder claims the materials were not as described, our investigation shows the product listing explicitly stated dimensions and materials. The cardholder did not contact customer service within the 30-day return window.",
    "submissionPackageUrl": None,
    "metadata": {"source": "demo_scenario", "scenario": "urgent_deadline", "version": "1.0"},
    "createdAt": (NOW - timedelta(days=42)).isoformat(),
    "updatedAt": (NOW - timedelta(hours=6)).isoformat(),
}

URGENT_DEADLINE_EVIDENCE = [
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-urgent-deadline-001",
        "evidenceType": "transaction", "sourceSystem": "payment_processor",
        "title": "Transaction Record — HomeReno Solutions",
        "content": {"transactionId": "TXN-991203", "amount": 1247.99, "entryMode": "ecommerce", "avsResponse": "Y", "cvvResponse": "M"},
        "extractedAt": (NOW - timedelta(days=42)).isoformat(),
    },
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-urgent-deadline-001",
        "evidenceType": "shipping", "sourceSystem": "logistics",
        "title": "Shipping Record — FedEx (Delivered)",
        "content": {"trackingNumber": "FX-794512380", "carrier": "FedEx", "status": "delivered", "signedBy": "J. Kim", "deliveryDate": (NOW - timedelta(days=38)).isoformat()},
        "extractedAt": (NOW - timedelta(days=42)).isoformat(),
    },
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-urgent-deadline-001",
        "evidenceType": "order", "sourceSystem": "oms_erp",
        "title": "Order Record — ORD-882201",
        "content": {"orderId": "ORD-882201", "items": [{"description": "Premium Hardwood Flooring Kit (200 sq ft)", "quantity": 1, "unitPrice": 1247.99}], "orderStatus": "delivered"},
        "extractedAt": (NOW - timedelta(days=42)).isoformat(),
    },
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-urgent-deadline-001",
        "evidenceType": "communication", "sourceSystem": "crm",
        "title": "Customer Communication — No return request",
        "content": {"communicationType": "support_ticket", "summary": "No return request filed within 30-day window. No contact from cardholder prior to dispute.", "resolution": "no_response"},
        "extractedAt": (NOW - timedelta(days=42)).isoformat(),
    },
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-urgent-deadline-001",
        "evidenceType": "receipt", "sourceSystem": "document_intelligence",
        "title": "Product Listing — Dimensions and Materials Stated",
        "content": {"documentType": "product_listing", "extractionConfidence": 0.94, "fields_extracted": 12},
        "blobUrl": "https://storage.blob.core.windows.net/evidence/demo-urgent-deadline-001/listing.pdf",
        "extractedAt": (NOW - timedelta(days=42)).isoformat(),
    },
]

URGENT_DEADLINE_TIMELINE = [
    {"id": _id(), "eventId": _id(), "disputeId": "demo-urgent-deadline-001", "eventType": "status_change", "actor": "system", "detail": "Dispute created — MC 4853, 45-day deadline set", "data": {"fromStatus": None, "toStatus": "intake"}, "occurredAt": (NOW - timedelta(days=42)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-urgent-deadline-001", "eventType": "status_change", "actor": "orchestrator_agent", "detail": "Evidence gathering initiated", "data": {"fromStatus": "intake", "toStatus": "evidence_gathering"}, "occurredAt": (NOW - timedelta(days=42, hours=-0.1)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-urgent-deadline-001", "eventType": "status_change", "actor": "maker_agent", "detail": "Rebuttal drafting started", "data": {"fromStatus": "evidence_gathering", "toStatus": "ai_drafting"}, "occurredAt": (NOW - timedelta(days=41)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-urgent-deadline-001", "eventType": "checker_passed", "actor": "checker_agent", "detail": "Groundedness validated", "data": {"attempt": 1, "groundednessScore": 0.91}, "occurredAt": (NOW - timedelta(days=41, hours=-1)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-urgent-deadline-001", "eventType": "status_change", "actor": "system", "detail": "Assigned to Priya Sharma — ⚠️ URGENT: 2 days until Mastercard deadline", "data": {"fromStatus": "ai_drafting", "toStatus": "pending_review", "assignedAnalyst": "analyst-003"}, "occurredAt": (NOW - timedelta(hours=6)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-urgent-deadline-001", "eventType": "deadline_warning", "actor": "system", "detail": "⚠️ DEADLINE ALERT: 2 days remaining. Mastercard 4853 deadline is " + (NOW + timedelta(days=2)).strftime("%Y-%m-%d"), "data": {"daysRemaining": 2, "network": "mastercard"}, "occurredAt": (NOW - timedelta(hours=1)).isoformat()},
]


# ===========================================================================
# Scenario 3: Escalation to Supervisor — Amex timeout
# Shows: HITL gate timeout, automatic escalation, supervisor queue
# ===========================================================================

ESCALATION_DISPUTE = {
    "id": "demo-escalation-001",
    "disputeId": "demo-escalation-001",
    "networkCode": "amex",
    "reasonCode": "F29",
    "reasonDescription": "Card Not Present",
    "reasonCategory": "fraud",
    "status": "escalated",
    "cardholderName": "Patricia Johnson",
    "cardholderCity": "New York",
    "cardholderState": "NY",
    "cardLastFour": "3712",
    "transactionAmount": 3450.00,
    "transactionCurrency": "USD",
    "transactionDate": (NOW - timedelta(days=18)).isoformat(),
    "merchantName": "LuxWatch Boutique",
    "merchantCategory": "Jewelry",
    "merchantMcc": "5944",
    "deadlineUtc": (NOW + timedelta(days=2)).isoformat(),
    "daysUntilDeadline": 2,
    "winProbability": 0.71,
    "riskScore": 82,
    "assignedAnalyst": "supervisor-001",
    "evidenceRequired": ["avs_cvv_results", "3ds_authentication", "ip_geolocation", "device_fingerprint"],
    "evidenceCollected": 5,
    "evidenceGaps": 1,
    "rebuttalDraft": "Investigation confirms the transaction was authenticated via 3D Secure (Amex SafeKey) with the cardholder's registered device. IP geolocation matches the cardholder's home network. Device fingerprint is consistent with 14 prior successful transactions over 8 months.",
    "submissionPackageUrl": None,
    "metadata": {"source": "demo_scenario", "scenario": "escalation_timeout", "version": "1.0"},
    "createdAt": (NOW - timedelta(days=17)).isoformat(),
    "updatedAt": (NOW - timedelta(hours=2)).isoformat(),
}

ESCALATION_EVIDENCE = [
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-escalation-001",
        "evidenceType": "transaction", "sourceSystem": "payment_processor",
        "title": "Transaction Record — LuxWatch Boutique",
        "content": {"transactionId": "TXN-553892", "amount": 3450.00, "entryMode": "ecommerce", "avsResponse": "Y", "cvvResponse": "M", "threeDSecure": True},
        "extractedAt": (NOW - timedelta(days=17)).isoformat(),
    },
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-escalation-001",
        "evidenceType": "fraud_signal", "sourceSystem": "fraud_engine",
        "title": "Fraud Assessment — Low Risk Despite High Amount",
        "content": {"riskScore": 28, "riskLevel": "low", "signals": ["3ds_authenticated", "known_device", "consistent_geo"], "friendlyFraudProbability": 0.68},
        "extractedAt": (NOW - timedelta(days=17)).isoformat(),
    },
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-escalation-001",
        "evidenceType": "shipping", "sourceSystem": "logistics",
        "title": "Shipping Record — Delivered to Billing Address",
        "content": {"trackingNumber": "DHL-9981234567", "carrier": "DHL", "status": "delivered", "signedBy": "P. Johnson", "deliveryDate": (NOW - timedelta(days=15)).isoformat()},
        "extractedAt": (NOW - timedelta(days=17)).isoformat(),
    },
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-escalation-001",
        "evidenceType": "receipt", "sourceSystem": "document_intelligence",
        "title": "3D Secure Authentication Log",
        "content": {"documentType": "authentication_log", "merchantName": "LuxWatch Boutique", "amount": 3450.00, "extractionConfidence": 0.99},
        "extractedAt": (NOW - timedelta(days=17)).isoformat(),
    },
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-escalation-001",
        "evidenceType": "communication", "sourceSystem": "crm",
        "title": "Prior Purchase History — 14 Successful Transactions",
        "content": {"communicationType": "account_history", "summary": "Cardholder has 14 successful purchases from this merchant over 8 months. No prior disputes. VIP customer tier."},
        "extractedAt": (NOW - timedelta(days=17)).isoformat(),
    },
]

ESCALATION_TIMELINE = [
    {"id": _id(), "eventId": _id(), "disputeId": "demo-escalation-001", "eventType": "status_change", "actor": "system", "detail": "Dispute created — Amex F29 (Card Not Present fraud)", "data": {"fromStatus": None, "toStatus": "intake"}, "occurredAt": (NOW - timedelta(days=17)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-escalation-001", "eventType": "status_change", "actor": "orchestrator_agent", "detail": "Evidence gathering — querying 5 source systems", "data": {"fromStatus": "intake", "toStatus": "evidence_gathering"}, "occurredAt": (NOW - timedelta(days=17, hours=-0.1)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-escalation-001", "eventType": "status_change", "actor": "maker_agent", "detail": "Rebuttal drafted citing 3DS authentication", "data": {"fromStatus": "evidence_gathering", "toStatus": "ai_drafting"}, "occurredAt": (NOW - timedelta(days=16)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-escalation-001", "eventType": "checker_passed", "actor": "checker_agent", "detail": "Groundedness passed", "data": {"attempt": 1, "groundednessScore": 0.94}, "occurredAt": (NOW - timedelta(days=16, hours=-0.5)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-escalation-001", "eventType": "status_change", "actor": "system", "detail": "Assigned to Diana Lopez for review", "data": {"fromStatus": "ai_drafting", "toStatus": "pending_review", "assignedAnalyst": "analyst-005"}, "occurredAt": (NOW - timedelta(days=15)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-escalation-001", "eventType": "sla_warning", "actor": "system", "detail": "⚠️ Review SLA: 48 hours without analyst action", "data": {"hoursElapsed": 48}, "occurredAt": (NOW - timedelta(days=13)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-escalation-001", "eventType": "status_change", "actor": "system", "detail": "🚨 ESCALATED: Review timeout exceeded SLA — moved to supervisor queue (Tanya Moore)", "data": {"fromStatus": "pending_review", "toStatus": "escalated", "reason": "sla_timeout", "escalatedTo": "supervisor-001"}, "occurredAt": (NOW - timedelta(hours=2)).isoformat()},
]


# ===========================================================================
# Scenario 4: High-Value Fraud Ring — Discover
# Shows: Multiple fraud signals, card-testing pattern, high risk
# ===========================================================================

FRAUD_RING_DISPUTE = {
    "id": "demo-fraud-ring-001",
    "disputeId": "demo-fraud-ring-001",
    "networkCode": "discover",
    "reasonCode": "UA",
    "reasonDescription": "Fraud — Card Present",
    "reasonCategory": "fraud",
    "status": "approved",
    "cardholderName": "Robert Martinez",
    "cardholderCity": "Denver",
    "cardholderState": "CO",
    "cardLastFour": "6011",
    "transactionAmount": 4589.99,
    "transactionCurrency": "USD",
    "transactionDate": (NOW - timedelta(days=22)).isoformat(),
    "merchantName": "TechGadgets Inc",
    "merchantCategory": "Electronics",
    "merchantMcc": "5732",
    "deadlineUtc": (NOW + timedelta(days=8)).isoformat(),
    "daysUntilDeadline": 8,
    "winProbability": 0.89,
    "riskScore": 94,
    "assignedAnalyst": "analyst-002",
    "evidenceRequired": ["signed_receipt", "emv_chip_data", "surveillance_footage"],
    "evidenceCollected": 6,
    "evidenceGaps": 0,
    "rebuttalDraft": "Our fraud investigation confirms a sophisticated card-present fraud attempt. The EMV chip data shows a cloned card. Surveillance footage from the merchant location shows an individual not matching the cardholder's profile. The transaction occurred in Denver, CO while the cardholder's mobile device was geolocated in Houston, TX at the same time. Three prior small-value test transactions were detected in the preceding 24 hours.",
    "submissionPackageUrl": None,
    "metadata": {"source": "demo_scenario", "scenario": "fraud_ring", "version": "1.0"},
    "createdAt": (NOW - timedelta(days=21)).isoformat(),
    "updatedAt": (NOW - timedelta(days=1)).isoformat(),
}

FRAUD_RING_EVIDENCE = [
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-fraud-ring-001",
        "evidenceType": "transaction", "sourceSystem": "payment_processor",
        "title": "Transaction Record — Cloned Card Detected",
        "content": {"transactionId": "TXN-112987", "amount": 4589.99, "entryMode": "chip", "avsResponse": "N", "cvvResponse": "N", "emvFallback": True},
        "extractedAt": (NOW - timedelta(days=21)).isoformat(),
    },
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-fraud-ring-001",
        "evidenceType": "fraud_signal", "sourceSystem": "fraud_engine",
        "title": "Fraud Assessment — Card Testing Pattern Detected",
        "content": {
            "riskScore": 94, "riskLevel": "high",
            "signals": ["card_testing_pattern", "geo_mismatch", "velocity_spike", "emv_fallback_suspicious", "amount_unusual"],
            "previousChargebacks": 0, "friendlyFraudProbability": 0.05,
            "relatedTransactions": ["TXN-112984 ($1.00)", "TXN-112985 ($2.50)", "TXN-112986 ($5.00)"],
        },
        "extractedAt": (NOW - timedelta(days=21)).isoformat(),
    },
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-fraud-ring-001",
        "evidenceType": "receipt", "sourceSystem": "document_intelligence",
        "title": "Surveillance Footage Timestamp Log",
        "content": {"documentType": "surveillance_log", "merchantName": "TechGadgets Inc", "extractionConfidence": 0.92},
        "blobUrl": "https://storage.blob.core.windows.net/evidence/demo-fraud-ring-001/surveillance.mp4",
        "extractedAt": (NOW - timedelta(days=21)).isoformat(),
    },
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-fraud-ring-001",
        "evidenceType": "communication", "sourceSystem": "crm",
        "title": "Cardholder Confirmation — Was in Houston TX",
        "content": {"communicationType": "phone_call", "subject": "Fraud report — cardholder confirms location mismatch", "summary": "Robert Martinez called in immediately after receiving transaction alert. Confirmed he was in Houston, TX at time of purchase. Card was still in his possession."},
        "extractedAt": (NOW - timedelta(days=21)).isoformat(),
    },
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-fraud-ring-001",
        "evidenceType": "fraud_signal", "sourceSystem": "fraud_engine",
        "title": "Geolocation Mismatch — Mobile Device vs Transaction",
        "content": {"riskScore": 98, "signals": ["mobile_geo_houston_tx", "transaction_geo_denver_co", "simultaneous_location_impossible"]},
        "extractedAt": (NOW - timedelta(days=21)).isoformat(),
    },
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-fraud-ring-001",
        "evidenceType": "transaction", "sourceSystem": "payment_processor",
        "title": "Card Testing Transactions (3 prior small amounts)",
        "content": {"relatedTransactions": [
            {"transactionId": "TXN-112984", "amount": 1.00, "time": (NOW - timedelta(days=22, hours=2)).isoformat()},
            {"transactionId": "TXN-112985", "amount": 2.50, "time": (NOW - timedelta(days=22, hours=1.5)).isoformat()},
            {"transactionId": "TXN-112986", "amount": 5.00, "time": (NOW - timedelta(days=22, hours=1)).isoformat()},
        ]},
        "extractedAt": (NOW - timedelta(days=21)).isoformat(),
    },
]

FRAUD_RING_TIMELINE = [
    {"id": _id(), "eventId": _id(), "disputeId": "demo-fraud-ring-001", "eventType": "status_change", "actor": "system", "detail": "Dispute created — Discover UA (Card Present Fraud)", "data": {"fromStatus": None, "toStatus": "intake"}, "occurredAt": (NOW - timedelta(days=21)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-fraud-ring-001", "eventType": "status_change", "actor": "orchestrator_agent", "detail": "High-priority evidence gathering — fraud signals detected", "data": {"fromStatus": "intake", "toStatus": "evidence_gathering"}, "occurredAt": (NOW - timedelta(days=21, hours=-0.05)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-fraud-ring-001", "eventType": "evidence_retrieved", "actor": "evidence_agent", "detail": "Card testing pattern identified — 3 small transactions preceding", "data": {"sourceSystem": "fraud_engine"}, "occurredAt": (NOW - timedelta(days=21, hours=-0.1)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-fraud-ring-001", "eventType": "evidence_retrieved", "actor": "evidence_agent", "detail": "Geolocation mismatch confirmed — Houston vs Denver", "data": {"sourceSystem": "fraud_engine"}, "occurredAt": (NOW - timedelta(days=21, hours=-0.15)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-fraud-ring-001", "eventType": "status_change", "actor": "maker_agent", "detail": "Rebuttal drafted — strong fraud evidence", "data": {"fromStatus": "evidence_gathering", "toStatus": "ai_drafting"}, "occurredAt": (NOW - timedelta(days=20)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-fraud-ring-001", "eventType": "checker_passed", "actor": "checker_agent", "detail": "Groundedness passed — all fraud claims verified", "data": {"attempt": 1, "groundednessScore": 0.98}, "occurredAt": (NOW - timedelta(days=20, hours=-0.5)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-fraud-ring-001", "eventType": "status_change", "actor": "system", "detail": "Assigned to Marcus Chen for review", "data": {"fromStatus": "ai_drafting", "toStatus": "pending_review"}, "occurredAt": (NOW - timedelta(days=19)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-fraud-ring-001", "eventType": "status_change", "actor": "analyst-002", "detail": "Approved by Marcus Chen — clear fraud evidence", "data": {"fromStatus": "pending_review", "toStatus": "approved"}, "occurredAt": (NOW - timedelta(days=1)).isoformat()},
]


# ===========================================================================
# Scenario 5: Maker-Checker Retry — Visa, groundedness fails first attempt
# Shows: AI guardrails working, checker catches ungrounded claim, retry succeeds
# ===========================================================================

MAKER_RETRY_DISPUTE = {
    "id": "demo-maker-retry-001",
    "disputeId": "demo-maker-retry-001",
    "networkCode": "visa",
    "reasonCode": "13.3",
    "reasonDescription": "Not as Described or Defective",
    "reasonCategory": "consumer_dispute",
    "status": "submitted",
    "cardholderName": "Emily Watson",
    "cardholderCity": "Chicago",
    "cardholderState": "IL",
    "cardLastFour": "4556",
    "transactionAmount": 349.99,
    "transactionCurrency": "USD",
    "transactionDate": (NOW - timedelta(days=25)).isoformat(),
    "merchantName": "Urban Threads Apparel",
    "merchantCategory": "Clothing",
    "merchantMcc": "5651",
    "deadlineUtc": (NOW + timedelta(days=5)).isoformat(),
    "daysUntilDeadline": 5,
    "winProbability": 0.58,
    "riskScore": 35,
    "assignedAnalyst": "analyst-004",
    "evidenceRequired": ["product_description", "photos", "return_policy", "communication_records"],
    "evidenceCollected": 5,
    "evidenceGaps": 0,
    "rebuttalDraft": "The item received matches the product listing description. Product photos on the listing clearly show the fabric texture and color that the cardholder received. The return policy allows 30-day returns, and the cardholder did not initiate a return within this window. Customer service was contacted once but the cardholder declined the offered exchange.",
    "submissionPackageUrl": "https://storage.blob.core.windows.net/submissions/demo-maker-retry-001/package.pdf",
    "metadata": {"source": "demo_scenario", "scenario": "maker_checker_retry", "version": "1.0"},
    "createdAt": (NOW - timedelta(days=24)).isoformat(),
    "updatedAt": (NOW - timedelta(days=2)).isoformat(),
}

MAKER_RETRY_EVIDENCE = [
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-maker-retry-001",
        "evidenceType": "transaction", "sourceSystem": "payment_processor",
        "title": "Transaction Record — Urban Threads Apparel",
        "content": {"transactionId": "TXN-667823", "amount": 349.99, "entryMode": "ecommerce", "avsResponse": "Y", "cvvResponse": "M"},
        "extractedAt": (NOW - timedelta(days=24)).isoformat(),
    },
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-maker-retry-001",
        "evidenceType": "order", "sourceSystem": "oms_erp",
        "title": "Order Record — Designer Jacket",
        "content": {"orderId": "ORD-554433", "items": [{"description": "Wool Blend Designer Jacket — Charcoal Grey, Size M", "quantity": 1, "unitPrice": 349.99}], "orderStatus": "delivered"},
        "extractedAt": (NOW - timedelta(days=24)).isoformat(),
    },
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-maker-retry-001",
        "evidenceType": "shipping", "sourceSystem": "logistics",
        "title": "Shipping Record — Delivered",
        "content": {"trackingNumber": "USPS-9400111899223100543210", "carrier": "USPS", "status": "delivered", "deliveryDate": (NOW - timedelta(days=22)).isoformat()},
        "extractedAt": (NOW - timedelta(days=24)).isoformat(),
    },
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-maker-retry-001",
        "evidenceType": "communication", "sourceSystem": "crm",
        "title": "Customer Service Chat — Exchange Offered & Declined",
        "content": {"communicationType": "chat", "subject": "Product quality complaint", "summary": "Cardholder chatted on Day 12 post-delivery. Complained about fabric feel. Agent offered free exchange. Cardholder declined, stated 'I just want my money back.' No return initiated.", "resolution": "declined_exchange"},
        "extractedAt": (NOW - timedelta(days=24)).isoformat(),
    },
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-maker-retry-001",
        "evidenceType": "receipt", "sourceSystem": "document_intelligence",
        "title": "Product Listing & Return Policy (30-day window)",
        "content": {"documentType": "terms_of_service", "extractionConfidence": 0.96, "fields_extracted": 15},
        "blobUrl": "https://storage.blob.core.windows.net/evidence/demo-maker-retry-001/listing_and_policy.pdf",
        "extractedAt": (NOW - timedelta(days=24)).isoformat(),
    },
]

MAKER_RETRY_TIMELINE = [
    {"id": _id(), "eventId": _id(), "disputeId": "demo-maker-retry-001", "eventType": "status_change", "actor": "system", "detail": "Dispute created — Visa 13.3 (Not as Described)", "data": {"fromStatus": None, "toStatus": "intake"}, "occurredAt": (NOW - timedelta(days=24)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-maker-retry-001", "eventType": "status_change", "actor": "orchestrator_agent", "detail": "Evidence gathering initiated", "data": {"fromStatus": "intake", "toStatus": "evidence_gathering"}, "occurredAt": (NOW - timedelta(days=24, hours=-0.1)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-maker-retry-001", "eventType": "status_change", "actor": "maker_agent", "detail": "First rebuttal draft generated", "data": {"fromStatus": "evidence_gathering", "toStatus": "ai_drafting"}, "occurredAt": (NOW - timedelta(days=23)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-maker-retry-001", "eventType": "checker_retry", "actor": "checker_agent", "detail": "❌ Groundedness FAILED — draft claimed 'cardholder admitted receiving correct item' but no such statement exists in evidence", "data": {"attempt": 1, "reason": "ungrounded_claim_detected", "flaggedClaim": "cardholder admitted receiving correct item"}, "occurredAt": (NOW - timedelta(days=23, hours=-0.3)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-maker-retry-001", "eventType": "status_change", "actor": "maker_agent", "detail": "Revised rebuttal — removed ungrounded claim, cited only verified facts", "data": {"revision": 2}, "occurredAt": (NOW - timedelta(days=23, hours=-0.5)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-maker-retry-001", "eventType": "checker_passed", "actor": "checker_agent", "detail": "✅ Groundedness passed on attempt 2 — all claims cite evidence", "data": {"attempt": 2, "groundednessScore": 0.92}, "occurredAt": (NOW - timedelta(days=23, hours=-0.7)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-maker-retry-001", "eventType": "status_change", "actor": "system", "detail": "Assigned to Jason Park for review", "data": {"fromStatus": "ai_drafting", "toStatus": "pending_review"}, "occurredAt": (NOW - timedelta(days=22)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-maker-retry-001", "eventType": "status_change", "actor": "analyst-004", "detail": "Approved by Jason Park", "data": {"fromStatus": "pending_review", "toStatus": "approved"}, "occurredAt": (NOW - timedelta(days=3)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-maker-retry-001", "eventType": "status_change", "actor": "system", "detail": "Evidence package submitted to Visa", "data": {"fromStatus": "approved", "toStatus": "submitted"}, "occurredAt": (NOW - timedelta(days=2)).isoformat()},
]


# ===========================================================================
# Scenario 6: Reg E Debit Clock — 10 business days
# Shows: Tighter regulatory deadline, debit card specific handling
# ===========================================================================

REG_E_DISPUTE = {
    "id": "demo-reg-e-001",
    "disputeId": "demo-reg-e-001",
    "networkCode": "visa",
    "reasonCode": "10.4",
    "reasonDescription": "Other Fraud — Card Absent Environment",
    "reasonCategory": "fraud",
    "status": "evidence_gathering",
    "cardholderName": "Kevin Nguyen",
    "cardholderCity": "Houston",
    "cardholderState": "TX",
    "cardLastFour": "4024",
    "transactionAmount": 782.00,
    "transactionCurrency": "USD",
    "transactionDate": (NOW - timedelta(days=6)).isoformat(),
    "merchantName": "GameZone Digital",
    "merchantCategory": "Digital Games",
    "merchantMcc": "5816",
    "deadlineUtc": (NOW + timedelta(days=4)).isoformat(),
    "daysUntilDeadline": 4,
    "winProbability": None,
    "riskScore": 67,
    "assignedAnalyst": None,
    "evidenceRequired": ["avs_cvv_results", "ip_geolocation", "device_fingerprint", "3ds_authentication"],
    "evidenceCollected": 2,
    "evidenceGaps": 2,
    "rebuttalDraft": None,
    "submissionPackageUrl": None,
    "isDebitCard": True,
    "regEApplies": True,
    "regEDeadline": (NOW + timedelta(days=4)).isoformat(),
    "metadata": {"source": "demo_scenario", "scenario": "reg_e_debit_clock", "version": "1.0"},
    "createdAt": (NOW - timedelta(days=5)).isoformat(),
    "updatedAt": (NOW - timedelta(hours=3)).isoformat(),
}

REG_E_EVIDENCE = [
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-reg-e-001",
        "evidenceType": "transaction", "sourceSystem": "payment_processor",
        "title": "Transaction Record — GameZone Digital (Debit)",
        "content": {"transactionId": "TXN-887654", "amount": 782.00, "entryMode": "ecommerce", "cardType": "debit", "avsResponse": "N", "cvvResponse": "N", "threeDSecure": False},
        "extractedAt": (NOW - timedelta(days=5)).isoformat(),
    },
    {
        "id": _id(), "evidenceId": _id(), "disputeId": "demo-reg-e-001",
        "evidenceType": "fraud_signal", "sourceSystem": "fraud_engine",
        "title": "Fraud Assessment — No 3DS, Failed AVS/CVV",
        "content": {"riskScore": 67, "riskLevel": "medium", "signals": ["no_3ds_authentication", "avs_mismatch", "cvv_mismatch", "unusual_amount"], "friendlyFraudProbability": 0.15},
        "extractedAt": (NOW - timedelta(days=5)).isoformat(),
    },
]

REG_E_TIMELINE = [
    {"id": _id(), "eventId": _id(), "disputeId": "demo-reg-e-001", "eventType": "status_change", "actor": "system", "detail": "🚨 DEBIT DISPUTE — Reg E 10-business-day clock started", "data": {"fromStatus": None, "toStatus": "intake", "regE": True, "deadlineDays": 10}, "occurredAt": (NOW - timedelta(days=5)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-reg-e-001", "eventType": "status_change", "actor": "orchestrator_agent", "detail": "Priority evidence gathering — Reg E deadline applies", "data": {"fromStatus": "intake", "toStatus": "evidence_gathering", "priority": "high"}, "occurredAt": (NOW - timedelta(days=5, hours=-0.05)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-reg-e-001", "eventType": "evidence_retrieved", "actor": "evidence_agent", "detail": "Transaction record retrieved — no 3DS authentication", "data": {"sourceSystem": "payment_processor"}, "occurredAt": (NOW - timedelta(days=5, hours=-0.1)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-reg-e-001", "eventType": "evidence_gap", "actor": "evidence_agent", "detail": "⚠️ EVIDENCE GAP: IP geolocation data not available from merchant", "data": {"missingEvidence": "ip_geolocation", "impact": "weakens_fraud_defense"}, "occurredAt": (NOW - timedelta(days=5, hours=-0.15)).isoformat()},
    {"id": _id(), "eventId": _id(), "disputeId": "demo-reg-e-001", "eventType": "deadline_warning", "actor": "system", "detail": "⚠️ REG E ALERT: 4 business days remaining. Provisional credit deadline approaching.", "data": {"daysRemaining": 4, "regulation": "Reg E", "consequence": "Must issue provisional credit if not resolved"}, "occurredAt": (NOW - timedelta(hours=3)).isoformat()},
]


# ===========================================================================
# Scenario 7: Cross-Network — Same merchant across Visa, MC, Amex, Discover
# Shows: How different networks handle the same type of dispute differently
# ===========================================================================

CROSS_NETWORK_DISPUTES = []
CROSS_NETWORK_EVIDENCE = []
CROSS_NETWORK_TIMELINE = []

for i, (network, code, desc) in enumerate([
    ("visa", "13.1", "Merchandise/Services Not Received"),
    ("mastercard", "4855", "Goods or Services Not Provided"),
    ("amex", "C04", "Goods/Services Not Received"),
    ("discover", "RG", "Non-Receipt of Goods/Services"),
]):
    dispute_id = f"demo-cross-network-{network}-001"
    CROSS_NETWORK_DISPUTES.append({
        "id": dispute_id,
        "disputeId": dispute_id,
        "networkCode": network,
        "reasonCode": code,
        "reasonDescription": desc,
        "reasonCategory": "consumer_dispute",
        "status": ["submitted", "pending_review", "ai_drafting", "approved"][i],
        "cardholderName": ["Daniel Wilson", "Maria Gonzalez", "William Brown", "Rachel Green"][i],
        "cardholderCity": ["Minneapolis", "Dallas", "Philadelphia", "Nashville"][i],
        "cardholderState": ["MN", "TX", "PA", "TN"][i],
        "cardLastFour": ["4111", "5432", "3782", "6011"][i],
        "transactionAmount": [524.99, 524.99, 524.99, 524.99][i],
        "transactionCurrency": "USD",
        "transactionDate": (NOW - timedelta(days=20)).isoformat(),
        "merchantName": "CloudStream Pro",
        "merchantCategory": "Digital Services",
        "merchantMcc": "5815",
        "deadlineUtc": (NOW + timedelta(days=[10, 25, 0, 10][i])).isoformat(),
        "daysUntilDeadline": [10, 25, 0, 10][i],
        "winProbability": [0.72, 0.68, 0.74, 0.70][i],
        "riskScore": 40,
        "assignedAnalyst": ["analyst-001", "analyst-003", None, "analyst-002"][i],
        "evidenceRequired": ["proof_of_delivery", "service_access_logs", "communication_records"],
        "evidenceCollected": [4, 3, 2, 4][i],
        "evidenceGaps": [0, 1, 1, 0][i],
        "metadata": {"source": "demo_scenario", "scenario": "cross_network_comparison", "version": "1.0"},
        "createdAt": (NOW - timedelta(days=19)).isoformat(),
        "updatedAt": (NOW - timedelta(days=[2, 1, 0, 3][i])).isoformat(),
    })


# ===========================================================================
# Scenario 8: Volume Spike — 15 disputes from same merchant in 48 hours
# Shows: Ops dashboard alerting, volume management, workforce planning
# ===========================================================================

VOLUME_SPIKE_DISPUTES = []
for i in range(15):
    dispute_id = f"demo-volume-spike-{i+1:03d}"
    VOLUME_SPIKE_DISPUTES.append({
        "id": dispute_id,
        "disputeId": dispute_id,
        "networkCode": ["visa", "mastercard", "visa", "mastercard", "visa"][i % 5],
        "reasonCode": ["13.2", "4853", "13.6", "4834", "13.1"][i % 5],
        "reasonDescription": ["Cancelled Recurring", "Cardholder Dispute", "Credit Not Processed", "POI Error", "Not Received"][i % 5],
        "reasonCategory": "consumer_dispute",
        "status": ["intake", "evidence_gathering", "evidence_gathering", "ai_drafting", "pending_review", "intake", "evidence_gathering", "intake", "ai_drafting", "evidence_gathering", "pending_review", "intake", "evidence_gathering", "ai_drafting", "pending_review"][i],
        "cardholderName": f"Customer {i+1:03d}",
        "cardholderCity": "Various",
        "cardholderState": "US",
        "cardLastFour": f"{4000+i}",
        "transactionAmount": round(49.99 + random.Random(i).uniform(0, 200), 2),
        "transactionCurrency": "USD",
        "transactionDate": (NOW - timedelta(hours=48 - i*3)).isoformat(),
        "merchantName": "GourmetBox Subscription",
        "merchantCategory": "Food Subscription",
        "merchantMcc": "5499",
        "deadlineUtc": (NOW + timedelta(days=28)).isoformat(),
        "daysUntilDeadline": 28,
        "winProbability": 0.45 if i % 3 == 0 else None,
        "riskScore": 30,
        "assignedAnalyst": None,
        "evidenceRequired": ["cancellation_policy", "billing_agreement", "communication_records"],
        "evidenceCollected": i % 4,
        "evidenceGaps": 3 - (i % 4),
        "metadata": {"source": "demo_scenario", "scenario": "volume_spike", "merchantAlert": True, "version": "1.0"},
        "createdAt": (NOW - timedelta(hours=48 - i*3)).isoformat(),
        "updatedAt": (NOW - timedelta(hours=max(0, 48 - i*3 - 2))).isoformat(),
    })


# ===========================================================================
# Combine all scenarios
# ===========================================================================

def get_all_demo_scenarios():
    """Return all named demo scenarios as (disputes, evidence, timeline)."""
    disputes = [
        SARAH_CHEN_DISPUTE,
        URGENT_DEADLINE_DISPUTE,
        ESCALATION_DISPUTE,
        FRAUD_RING_DISPUTE,
        MAKER_RETRY_DISPUTE,
        REG_E_DISPUTE,
        *CROSS_NETWORK_DISPUTES,
        *VOLUME_SPIKE_DISPUTES,
    ]

    evidence = [
        *SARAH_CHEN_EVIDENCE,
        *URGENT_DEADLINE_EVIDENCE,
        *ESCALATION_EVIDENCE,
        *FRAUD_RING_EVIDENCE,
        *MAKER_RETRY_EVIDENCE,
        *REG_E_EVIDENCE,
        *CROSS_NETWORK_EVIDENCE,
    ]

    timeline = [
        *SARAH_CHEN_TIMELINE,
        *URGENT_DEADLINE_TIMELINE,
        *ESCALATION_TIMELINE,
        *FRAUD_RING_TIMELINE,
        *MAKER_RETRY_TIMELINE,
        *REG_E_TIMELINE,
        *CROSS_NETWORK_TIMELINE,
    ]

    return disputes, evidence, timeline


def save_demo_scenarios(output_dir: str = "./data/seed"):
    """Save demo scenarios to separate JSON files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    disputes, evidence, timeline = get_all_demo_scenarios()

    # Save as separate demo files
    with open(output_path / "demo_disputes.json", "w") as f:
        json.dump(disputes, f, indent=2, default=str)

    with open(output_path / "demo_evidence.json", "w") as f:
        json.dump(evidence, f, indent=2, default=str)

    with open(output_path / "demo_timeline.json", "w") as f:
        json.dump(timeline, f, indent=2, default=str)

    print(f"\nDemo Scenarios Generated:")
    print(f"  Disputes: {len(disputes)} ({len([d for d in disputes if d['id'].startswith('demo-volume')])} volume spike)")
    print(f"  Evidence: {len(evidence)}")
    print(f"  Timeline: {len(timeline)}")
    print(f"\nScenarios:")
    print(f"  1. Sarah Chen — Friendly Fraud (Visa, closed/won)")
    print(f"  2. Urgent Deadline — 2 days left (Mastercard, in review)")
    print(f"  3. Escalation to Supervisor (Amex, SLA timeout)")
    print(f"  4. High-Value Fraud Ring (Discover, card testing)")
    print(f"  5. Maker-Checker Retry (Visa, groundedness failed then passed)")
    print(f"  6. Reg E Debit Clock (Visa debit, 4 days remaining)")
    print(f"  7. Cross-Network Comparison (same merchant, 4 networks)")
    print(f"  8. Volume Spike (15 disputes from GourmetBox in 48h)")

    return disputes, evidence, timeline


if __name__ == "__main__":
    save_demo_scenarios()
