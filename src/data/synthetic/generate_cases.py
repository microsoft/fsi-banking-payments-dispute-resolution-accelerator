#!/usr/bin/env python3
"""
generate_cases.py — Synthetic dispute case generator for the Payments Dispute Resolution accelerator.

Generates 10 curated demo cases that validate against src/shared/schemas/case.schema.json.

Output:
  cases/<caseId>.json   — one file per case
  cases.json            — combined array (served by the #41 read API)

Usage:
    python generate_cases.py [--output-dir OUTPUT_DIR]

Dependencies: stdlib only (uuid, json, datetime, pathlib, argparse).
Optional:     pip install jsonschema  →  full JSON Schema validation against case.schema.json.
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import date
from pathlib import Path

# ── Deterministic UUID generation ─────────────────────────────────────────────
# uuid5 over a private namespace ensures every regeneration produces the same IDs,
# so blob filenames and API references stay stable across re-runs.
_NS = uuid.UUID("d0e1f2a3-b4c5-6789-8000-000000000000")


def _uid(name: str) -> str:
    """Return a stable UUID5 string for a logical name."""
    return str(uuid.uuid5(_NS, name))


# ── Dynamic deadline calculation ──────────────────────────────────────────────

def _days_remaining(due_date_iso: str) -> int:
    """Days from today to the due date (can be negative if past due)."""
    return (date.fromisoformat(due_date_iso) - date.today()).days


# ══════════════════════════════════════════════════════════════════════════════
# Case builders — each returns a dict that conforms to case.schema.json
# ══════════════════════════════════════════════════════════════════════════════

def _case_01() -> dict:
    """Visa 13.1 — Merchandise Not Received.
    Near-expiry (2 days). High win probability. Evidence gap: missing signed proof of delivery."""
    cid   = _uid("case-01")
    e_txn = _uid("case-01-ev-txn")
    e_shp = _uid("case-01-ev-shp")
    e_ord = _uid("case-01-ev-ord")
    due   = "2026-07-08"
    return {
        "caseId":           cid,
        "orchestrationId":  cid,
        "disputeRef":       "VCA-2026-0071834",
        "cardNetwork":      "visa",
        "merchantName":     "Apex Electronics",
        "cardholderName":   "Marcus Chen",
        "transactionAmount": 847.99,
        "transactionDate":  "2026-05-12",
        "status":           "pending_review",
        "reasonCode":       "13.1",
        "reasonCodeLabel":  "Merchandise / Services Not Received",
        "reasonCodeChecklist": [
            {"item": "Proof of transaction authorization",                        "required": True,  "satisfied": True},
            {"item": "Shipping confirmation with tracking number",                "required": True,  "satisfied": True},
            {"item": "Proof of delivery — signed receipt or carrier confirmation","required": True,  "satisfied": False},
            {"item": "Customer communication log regarding non-receipt",          "required": False, "satisfied": False},
        ],
        "evidence": [
            {
                "evidenceId":   e_txn,
                "type":         "transaction",
                "sourceSystem": "Visa Authorization System",
                "retrievedAt":  "2026-06-10T08:14:22Z",
                "contentRef":   "blob://disputes-demo/case-01/txn-record.json",
                "completeness": "complete",
            },
            {
                "evidenceId":   e_shp,
                "type":         "shipping",
                "sourceSystem": "ShipTrack PRO",
                "retrievedAt":  "2026-06-10T08:16:05Z",
                "contentRef":   "blob://disputes-demo/case-01/shipment-record.pdf",
                "completeness": "partial",
            },
            {
                "evidenceId":   e_ord,
                "type":         "order",
                "sourceSystem": "Apex Commerce Platform",
                "retrievedAt":  "2026-06-10T08:17:41Z",
                "contentRef":   "blob://disputes-demo/case-01/order-record.json",
                "completeness": "complete",
            },
        ],
        "evidenceGaps": [
            {
                "missingItem": "Signed proof of delivery or final carrier scan confirmation",
                "reason":      "ShipTrack PRO returned a partial record; the signature page and final delivery scan event are unavailable due to carrier data-retention expiry (>60 days).",
                "impact":      "critical",
            },
        ],
        "winProbability": 0.72,
        "riskLevel":      "high",
        "rebuttalDraft": {
            "text": (
                "The merchant disputes this chargeback under Visa reason code 13.1. Per the transaction "
                "authorization record (see evidence [{}]), the cardholder's card was authenticated via "
                "Verified by Visa on 2026-05-12 at 14:33 UTC. The order was fulfilled and dispatched per "
                "our commerce platform (see evidence [{}]), with a tracking number assigned and confirmed "
                "as in-transit by ShipTrack PRO (see evidence [{}]). Although final delivery confirmation "
                "is pending due to a carrier data gap, all merchant obligations up to the point of dispatch "
                "have been met. We respectfully request the chargeback be reversed."
            ).format(e_txn, e_ord, e_shp),
            "citations": [
                {"evidenceId": e_txn, "excerpt": "Visa Authorization System: AUTH CODE 083741, CVV2=MATCH, 3DS2 authenticated, 2026-05-12T14:33:07Z"},
                {"evidenceId": e_ord, "excerpt": "Order #APX-2026-88341: 1× APEX-4K-MONITOR-32, fulfilled 2026-05-13, tracking DHL-9281773450 assigned"},
                {"evidenceId": e_shp, "excerpt": "ShipTrack PRO: parcel DHL-9281773450 scanned IN-TRANSIT at Chicago O'Hare hub 2026-05-14T09:22:00Z"},
            ],
        },
        "deadline": {
            "network":       "Visa",
            "dueDate":       due,
            "daysRemaining": _days_remaining(due),
        },
        "createdAt": "2026-06-10T08:00:00Z",
        "updatedAt": "2026-07-01T11:45:00Z",
    }


def _case_02() -> dict:
    """Mastercard 4853 — Cardholder Dispute: Defective / Not as Described.
    Medium win probability. Return policy disclosure missing."""
    cid   = _uid("case-02")
    e_txn = _uid("case-02-ev-txn")
    e_rct = _uid("case-02-ev-rct")
    e_com = _uid("case-02-ev-com")
    e_ord = _uid("case-02-ev-ord")
    due   = "2026-07-21"
    return {
        "caseId":           cid,
        "orchestrationId":  cid,
        "disputeRef":       "MC-4853-2026-00291",
        "cardNetwork":      "mastercard",
        "merchantName":     "TechWorld Online",
        "cardholderName":   "Sofia Ramirez",
        "transactionAmount": 1299.00,
        "transactionDate":  "2026-04-28",
        "status":           "pending_review",
        "reasonCode":       "4853",
        "reasonCodeLabel":  "Cardholder Dispute — Defective / Not as Described",
        "reasonCodeChecklist": [
            {"item": "Transaction record with itemized purchase detail",              "required": True,  "satisfied": True},
            {"item": "Itemized receipt at point of sale",                             "required": True,  "satisfied": True},
            {"item": "Return policy disclosure provided at time of purchase",         "required": True,  "satisfied": False},
            {"item": "Merchant–cardholder correspondence regarding the defect claim", "required": False, "satisfied": True},
        ],
        "evidence": [
            {
                "evidenceId":   e_txn,
                "type":         "transaction",
                "sourceSystem": "Mastercard Authorization Hub",
                "retrievedAt":  "2026-05-20T10:05:33Z",
                "contentRef":   "blob://disputes-demo/case-02/txn-record.json",
                "completeness": "complete",
            },
            {
                "evidenceId":   e_rct,
                "type":         "receipt",
                "sourceSystem": "Shopify POS",
                "retrievedAt":  "2026-05-20T10:07:12Z",
                "contentRef":   "blob://disputes-demo/case-02/receipt.pdf",
                "completeness": "partial",
            },
            {
                "evidenceId":   e_com,
                "type":         "communication",
                "sourceSystem": "Zendesk Support",
                "retrievedAt":  "2026-05-20T10:09:55Z",
                "contentRef":   "blob://disputes-demo/case-02/zendesk-export.json",
                "completeness": "complete",
            },
            {
                "evidenceId":   e_ord,
                "type":         "order",
                "sourceSystem": "TechWorld OMS",
                "retrievedAt":  "2026-05-20T10:11:20Z",
                "contentRef":   "blob://disputes-demo/case-02/order-record.json",
                "completeness": "complete",
            },
        ],
        "evidenceGaps": [
            {
                "missingItem": "Return policy disclosure dated at time of purchase",
                "reason":      "Shopify receipt is partial; the footer containing the return policy URL was not captured. Policy page version history is unavailable for 2026-04-28.",
                "impact":      "high",
            },
        ],
        "winProbability": 0.58,
        "riskLevel":      "medium",
        "rebuttalDraft": {
            "text": (
                "Merchant responds to Mastercard 4853 chargeback. The transaction of $1,299.00 on 2026-04-28 "
                "was fully authorized (see evidence [{}]). The order was fulfilled as specified — one unit of "
                "SKU TW-LAPTOP-PRO-15 shipped in original OEM packaging (see evidence [{}]). The cardholder "
                "contacted support on 2026-05-10 claiming the keyboard was defective; our support team offered "
                "an exchange within the 30-day return window, which the cardholder declined (see evidence [{}]). "
                "The cardholder's refusal of the offered remedy does not constitute grounds for a chargeback."
            ).format(e_txn, e_ord, e_com),
            "citations": [
                {"evidenceId": e_txn, "excerpt": "MC Auth Hub: TXN ID MC-2026-04-28-883821, $1,299.00, authorized, 3DS authenticated, no decline flags"},
                {"evidenceId": e_ord, "excerpt": "TechWorld OMS: Order #TW-291844, SKU TW-LAPTOP-PRO-15, shipped 2026-04-30, FedEx 776241880031"},
                {"evidenceId": e_com, "excerpt": "Zendesk #TW-88201: 'We offered an exchange unit. Cardholder responded: I just want a refund.' — agent note 2026-05-12"},
            ],
        },
        "deadline": {
            "network":       "Mastercard",
            "dueDate":       due,
            "daysRemaining": _days_remaining(due),
        },
        "createdAt": "2026-05-20T09:00:00Z",
        "updatedAt": "2026-06-28T15:22:00Z",
    }


def _case_03() -> dict:
    """Amex C28 — Cancelled Recurring Transaction.
    Low win probability. Critical risk. Near-expiry (3 days). Two evidence gaps."""
    cid   = _uid("case-03")
    e_txn = _uid("case-03-ev-txn")
    e_com = _uid("case-03-ev-com")
    due   = "2026-07-09"
    return {
        "caseId":           cid,
        "orchestrationId":  cid,
        "disputeRef":       "AMEX-C28-2026-88421",
        "cardNetwork":      "amex",
        "merchantName":     "StreamNow Premium",
        "cardholderName":   "Elena Vasquez",
        "transactionAmount": 179.88,
        "transactionDate":  "2026-06-01",
        "status":           "pending_review",
        "reasonCode":       "C28",
        "reasonCodeLabel":  "Cancelled Recurring Transaction",
        "reasonCodeChecklist": [
            {"item": "Proof of original recurring billing agreement",                      "required": True,  "satisfied": True},
            {"item": "Record confirming no cancellation request was received before rebill","required": True,  "satisfied": False},
            {"item": "Updated cancellation policy acknowledgment post-request",            "required": True,  "satisfied": False},
            {"item": "Advance renewal reminder sent to cardholder's registered email",     "required": False, "satisfied": False},
        ],
        "evidence": [
            {
                "evidenceId":   e_txn,
                "type":         "transaction",
                "sourceSystem": "Amex Authorization Platform",
                "retrievedAt":  "2026-06-12T07:30:15Z",
                "contentRef":   "blob://disputes-demo/case-03/txn-record.json",
                "completeness": "complete",
            },
            {
                "evidenceId":   e_com,
                "type":         "communication",
                "sourceSystem": "StreamNow CRM",
                "retrievedAt":  "2026-06-12T07:33:42Z",
                "contentRef":   "blob://disputes-demo/case-03/crm-export.json",
                "completeness": "partial",
            },
        ],
        "evidenceGaps": [
            {
                "missingItem": "Cancellation confirmation email or support ticket from before the 2026-06-01 rebill",
                "reason":      "Cardholder claims cancellation via web portal on 2026-05-28; StreamNow CRM contains no cancellation event for this account prior to the rebill date.",
                "impact":      "critical",
            },
            {
                "missingItem": "Updated cancellation policy acknowledgment (version in effect since 2026-02-15)",
                "reason":      "CRM record shows terms version 2025-11-01; it is unclear whether the cardholder viewed or accepted the updated policy before the dispute arose.",
                "impact":      "high",
            },
        ],
        "winProbability": 0.31,
        "riskLevel":      "critical",
        "rebuttalDraft": {
            "text": (
                "Merchant disputes Amex C28 chargeback for $179.88 recurring charge on 2026-06-01. "
                "The cardholder agreed to annual auto-renewal terms at sign-up, confirmed by our "
                "authorization record (see evidence [{}]). Our CRM shows no cancellation request on "
                "record before the 2026-06-01 billing date (see evidence [{}]). A 30-day advance "
                "renewal reminder was sent to the cardholder's registered email on 2026-05-02. "
                "We request the chargeback be reversed; as a goodwill gesture we are prepared to "
                "issue a pro-rated refund for unused service days upon confirmation."
            ).format(e_txn, e_com),
            "citations": [
                {"evidenceId": e_txn, "excerpt": "Amex Auth: CHARGE $179.88 (annual renewal), AUTH CODE AMX-20260601-7741, recurring_indicator=Y"},
                {"evidenceId": e_com, "excerpt": "StreamNow CRM: Account EVasquez@email.com — no cancellation event logged; last login 2026-05-29; renewal email sent 2026-05-02 (delivered, not bounced)"},
            ],
        },
        "deadline": {
            "network":       "Amex",
            "dueDate":       due,
            "daysRemaining": _days_remaining(due),
        },
        "createdAt": "2026-06-12T07:00:00Z",
        "updatedAt": "2026-07-03T09:10:00Z",
    }


def _case_04() -> dict:
    """Discover UA02 — Fraudulent Transaction, Card Not Present.
    Complete evidence. Very high win probability. No evidence gaps. Demo 'best case' showcase."""
    cid   = _uid("case-04")
    e_txn = _uid("case-04-ev-txn")
    e_frd = _uid("case-04-ev-frd")
    e_com = _uid("case-04-ev-com")
    e_rct = _uid("case-04-ev-rct")
    due   = "2026-07-31"
    return {
        "caseId":           cid,
        "orchestrationId":  cid,
        "disputeRef":       "DFS-UA02-2026-44102",
        "cardNetwork":      "discover",
        "merchantName":     "LuxeTravel Bookings",
        "cardholderName":   "James O'Brien",
        "transactionAmount": 2340.00,
        "transactionDate":  "2026-05-20",
        "status":           "pending_review",
        "reasonCode":       "UA02",
        "reasonCodeLabel":  "Fraudulent Transaction — Card Not Present",
        "reasonCodeChecklist": [
            {"item": "Transaction authorization record with CVV2 and AVS match", "required": True,  "satisfied": True},
            {"item": "3D Secure v2 authentication proof",                        "required": True,  "satisfied": True},
            {"item": "Customer identity verification log",                       "required": True,  "satisfied": True},
            {"item": "IP address and device fingerprint report",                 "required": False, "satisfied": True},
        ],
        "evidence": [
            {
                "evidenceId":   e_txn,
                "type":         "transaction",
                "sourceSystem": "Discover Authorization System",
                "retrievedAt":  "2026-06-02T09:00:44Z",
                "contentRef":   "blob://disputes-demo/case-04/txn-record.json",
                "completeness": "complete",
            },
            {
                "evidenceId":   e_frd,
                "type":         "fraud_signal",
                "sourceSystem": "FraudShield AI v3",
                "retrievedAt":  "2026-06-02T09:02:18Z",
                "contentRef":   "blob://disputes-demo/case-04/fraud-signal.json",
                "completeness": "complete",
            },
            {
                "evidenceId":   e_com,
                "type":         "communication",
                "sourceSystem": "LuxeTravel CRM",
                "retrievedAt":  "2026-06-02T09:04:01Z",
                "contentRef":   "blob://disputes-demo/case-04/crm-comms.json",
                "completeness": "complete",
            },
            {
                "evidenceId":   e_rct,
                "type":         "receipt",
                "sourceSystem": "LuxeTravel Booking Engine",
                "retrievedAt":  "2026-06-02T09:05:30Z",
                "contentRef":   "blob://disputes-demo/case-04/booking-receipt.pdf",
                "completeness": "complete",
            },
        ],
        "evidenceGaps": [],
        "winProbability": 0.88,
        "riskLevel":      "low",
        "rebuttalDraft": {
            "text": (
                "Merchant disputes Discover UA02 chargeback. The $2,340.00 transaction on 2026-05-20 passed "
                "all fraud controls: CVV2 matched, AVS returned a full match, and 3D Secure v2.2 "
                "authentication was completed by the cardholder's issuing bank (see evidence [{}]). "
                "FraudShield AI scored this transaction 12/100 (low risk) at authorization time, with the "
                "device fingerprint matching the cardholder's registered browser profile (see evidence [{}]). "
                "The booking confirmation was sent to the cardholder's verified email address and the "
                "cardholder subsequently interacted with the booking portal on 2026-05-21 (see evidence [{}]). "
                "The full booking receipt is attached for reference (see evidence [{}]). Merchant requests reversal."
            ).format(e_txn, e_frd, e_com, e_rct),
            "citations": [
                {"evidenceId": e_txn, "excerpt": "Discover Auth: TXN DFS-2026-05-20-44102, $2,340.00, CVV2=MATCH, AVS=FULL, 3DS2 ECI=05 (fully authenticated)"},
                {"evidenceId": e_frd, "excerpt": "FraudShield AI: risk_score=12, device_match=TRUE, ip_geo=US-IL (matches billing state), velocity_flag=FALSE"},
                {"evidenceId": e_com, "excerpt": "LuxeTravel CRM: Booking BKG-LT-7821 confirmed by email 2026-05-20T19:45Z; portal login by JOBrien@email.com on 2026-05-21T08:12Z"},
                {"evidenceId": e_rct, "excerpt": "LuxeTravel receipt: Round-trip ORD→MIA, depart 2026-06-14, return 2026-06-21, total $2,340.00, ref LT-7821"},
            ],
        },
        "deadline": {
            "network":       "Discover",
            "dueDate":       due,
            "daysRemaining": _days_remaining(due),
        },
        "createdAt": "2026-06-02T08:30:00Z",
        "updatedAt": "2026-06-28T16:00:00Z",
    }


def _case_05() -> dict:
    """Visa 10.4 — Card Absent Fraud. Still in evidence_gathering.
    High risk. Three evidence gaps; no rebuttal draft yet (AI hasn't drafted)."""
    cid   = _uid("case-05")
    e_txn = _uid("case-05-ev-txn")
    due   = "2026-07-14"
    return {
        "caseId":           cid,
        "orchestrationId":  cid,
        "disputeRef":       "VCA-2026-0084512",
        "cardNetwork":      "visa",
        "merchantName":     "NightMarket Global",
        "cardholderName":   "Priya Krishnamurthy",
        "transactionAmount": 534.50,
        "transactionDate":  "2026-06-15",
        "status":           "evidence_gathering",
        "reasonCode":       "10.4",
        "reasonCodeLabel":  "Card Absent Fraud",
        "reasonCodeChecklist": [
            {"item": "Original transaction authorization record",               "required": True,  "satisfied": True},
            {"item": "Fraud signal / velocity report from risk engine",         "required": True,  "satisfied": False},
            {"item": "IP geolocation log for session at transaction time",      "required": True,  "satisfied": False},
            {"item": "Device fingerprint token",                                "required": False, "satisfied": False},
        ],
        "evidence": [
            {
                "evidenceId":   e_txn,
                "type":         "transaction",
                "sourceSystem": "Visa Authorization Network",
                "retrievedAt":  "2026-06-20T11:00:00Z",
                "contentRef":   "blob://disputes-demo/case-05/txn-record.json",
                "completeness": "complete",
            },
        ],
        "evidenceGaps": [
            {
                "missingItem": "Fraud signal velocity report from FraudShield AI",
                "reason":      "FraudShield AI integration timed out during case assembly; retry is queued but has not yet completed.",
                "impact":      "critical",
            },
            {
                "missingItem": "IP geolocation log for session NMG-SESSION-20260615-44812",
                "reason":      "Geo-IP service returned null for this session ID; a re-query has been dispatched but is awaiting response.",
                "impact":      "high",
            },
            {
                "missingItem": "Device fingerprint token",
                "reason":      "Session cookie unavailable; device data purged after NightMarket platform's 90-day retention window.",
                "impact":      "medium",
            },
        ],
        "winProbability": 0.45,
        "riskLevel":      "high",
        "deadline": {
            "network":       "Visa",
            "dueDate":       due,
            "daysRemaining": _days_remaining(due),
        },
        "createdAt": "2026-06-20T10:30:00Z",
        "updatedAt": "2026-07-01T08:00:00Z",
    }


def _case_06() -> dict:
    """Mastercard 4837 — No Cardholder Authorization.
    Very low win probability. Critical risk. Near-expiry (2 days). Two critical evidence gaps."""
    cid   = _uid("case-06")
    e_txn = _uid("case-06-ev-txn")
    e_frd = _uid("case-06-ev-frd")
    e_ctr = _uid("case-06-ev-ctr")
    due   = "2026-07-08"
    return {
        "caseId":           cid,
        "orchestrationId":  cid,
        "disputeRef":       "MC-4837-2026-01847",
        "cardNetwork":      "mastercard",
        "merchantName":     "GoldTech Supplies",
        "cardholderName":   "David Thompson",
        "transactionAmount": 3200.00,
        "transactionDate":  "2026-05-05",
        "status":           "pending_review",
        "reasonCode":       "4837",
        "reasonCodeLabel":  "No Cardholder Authorization",
        "reasonCodeChecklist": [
            {"item": "Transaction authorization log with timestamps",                           "required": True,  "satisfied": True},
            {"item": "Cardholder-signed authorization form or verified verbal consent record",  "required": True,  "satisfied": False},
            {"item": "3DS v2 authentication data proving issuer verification",                  "required": True,  "satisfied": False},
            {"item": "IP address and device metadata at authorization time",                    "required": False, "satisfied": True},
        ],
        "evidence": [
            {
                "evidenceId":   e_txn,
                "type":         "transaction",
                "sourceSystem": "Mastercard Authorization Hub",
                "retrievedAt":  "2026-05-18T14:20:00Z",
                "contentRef":   "blob://disputes-demo/case-06/txn-record.json",
                "completeness": "complete",
            },
            {
                "evidenceId":   e_frd,
                "type":         "fraud_signal",
                "sourceSystem": "RiskMatrix v2",
                "retrievedAt":  "2026-05-18T14:22:30Z",
                "contentRef":   "blob://disputes-demo/case-06/risk-signal.json",
                "completeness": "partial",
            },
            {
                "evidenceId":   e_ctr,
                "type":         "contract",
                "sourceSystem": "GoldTech CRM",
                "retrievedAt":  "2026-05-18T14:24:55Z",
                "contentRef":   "blob://disputes-demo/case-06/contract-partial.pdf",
                "completeness": "partial",
            },
        ],
        "evidenceGaps": [
            {
                "missingItem": "Cardholder-signed authorization form or verified verbal consent recording",
                "reason":      "GoldTech CRM has a partial contract on file; the authorization signature page is absent from the uploaded document.",
                "impact":      "critical",
            },
            {
                "missingItem": "3DS v2 authentication proof",
                "reason":      "Transaction was processed via a legacy path without 3DS enrollment; liability shift back to merchant cannot be established.",
                "impact":      "critical",
            },
        ],
        "winProbability": 0.22,
        "riskLevel":      "critical",
        "rebuttalDraft": {
            "text": (
                "Merchant responds to Mastercard 4837 chargeback for $3,200.00. The transaction was "
                "processed through our standard authorization channel and received a positive authorization "
                "code from the issuing bank (see evidence [{}]). RiskMatrix flagged no elevated fraud "
                "velocity at the time of authorization (see evidence [{}]). While the full signed "
                "authorization form is pending urgent retrieval from archive, the merchant notes that "
                "this was a returning customer with prior order history. We are actively working to "
                "supply the signature record before the deadline."
            ).format(e_txn, e_frd),
            "citations": [
                {"evidenceId": e_txn, "excerpt": "MC Auth Hub: TXN MC-2026-05-05-01847, $3,200.00, AUTH CODE 509234, APPROVED, no decline flags"},
                {"evidenceId": e_frd, "excerpt": "RiskMatrix v2: velocity_score=24 (normal range), no prior chargebacks on this BIN in 90 days"},
            ],
        },
        "deadline": {
            "network":       "Mastercard",
            "dueDate":       due,
            "daysRemaining": _days_remaining(due),
        },
        "createdAt": "2026-05-18T13:00:00Z",
        "updatedAt": "2026-07-04T10:00:00Z",
    }


def _case_07() -> dict:
    """Amex FR2 — Fraud Full Recourse / Issuer Liability. Escalated status.
    High risk. Evidence gap: PCI-DSS certificate missing. Good rebuttal despite gap."""
    cid   = _uid("case-07")
    e_txn = _uid("case-07-ev-txn")
    e_frd = _uid("case-07-ev-frd")
    e_com = _uid("case-07-ev-com")
    e_rct = _uid("case-07-ev-rct")
    due   = "2026-07-12"
    return {
        "caseId":           cid,
        "orchestrationId":  cid,
        "disputeRef":       "AMEX-FR2-2026-00733",
        "cardNetwork":      "amex",
        "merchantName":     "CryptoVault Exchange",
        "cardholderName":   "Rebecca Williams",
        "transactionAmount": 8500.00,
        "transactionDate":  "2026-04-10",
        "status":           "escalated",
        "reasonCode":       "FR2",
        "reasonCodeLabel":  "Fraud — Full Recourse / Issuer Liability",
        "reasonCodeChecklist": [
            {"item": "Transaction record with Amex SafeKey / EMV data",                   "required": True,  "satisfied": True},
            {"item": "Fraud chargeback notification date within Amex SLA window",         "required": True,  "satisfied": True},
            {"item": "PCI-DSS compliance certificate (current calendar year)",            "required": True,  "satisfied": False},
            {"item": "Merchant response to cardholder contact",                           "required": False, "satisfied": True},
        ],
        "evidence": [
            {
                "evidenceId":   e_txn,
                "type":         "transaction",
                "sourceSystem": "Amex Authorization Platform",
                "retrievedAt":  "2026-05-01T08:10:00Z",
                "contentRef":   "blob://disputes-demo/case-07/txn-record.json",
                "completeness": "complete",
            },
            {
                "evidenceId":   e_frd,
                "type":         "fraud_signal",
                "sourceSystem": "FraudShield AI v3",
                "retrievedAt":  "2026-05-01T08:12:44Z",
                "contentRef":   "blob://disputes-demo/case-07/fraud-signal.json",
                "completeness": "complete",
            },
            {
                "evidenceId":   e_com,
                "type":         "communication",
                "sourceSystem": "CryptoVault CRM",
                "retrievedAt":  "2026-05-01T08:14:20Z",
                "contentRef":   "blob://disputes-demo/case-07/crm-comms.json",
                "completeness": "complete",
            },
            {
                "evidenceId":   e_rct,
                "type":         "receipt",
                "sourceSystem": "CryptoVault Ledger",
                "retrievedAt":  "2026-05-01T08:16:05Z",
                "contentRef":   "blob://disputes-demo/case-07/ledger-receipt.pdf",
                "completeness": "partial",
            },
        ],
        "evidenceGaps": [
            {
                "missingItem": "PCI-DSS compliance certificate for calendar year 2026",
                "reason":      "Certificate renewal was due 2026-06-30; the compliance team did not upload the renewed certificate before the case SLA elapsed. Matter escalated to VP of Compliance.",
                "impact":      "high",
            },
        ],
        "winProbability": 0.48,
        "riskLevel":      "high",
        "rebuttalDraft": {
            "text": (
                "Merchant disputes Amex FR2 chargeback of $8,500.00 dated 2026-04-10. The transaction was "
                "fully authenticated via Amex SafeKey and EMV data is on record (see evidence [{}]). "
                "FraudShield AI reported a low-risk score of 18/100 at authorization time with no velocity "
                "anomalies (see evidence [{}]). Our CRM confirms the cardholder contacted support on "
                "2026-04-11 and our team responded within 4 hours (see evidence [{}]). "
                "PCI-DSS certification renewal is in progress; the renewed certificate will be submitted "
                "as supplemental evidence prior to the response deadline."
            ).format(e_txn, e_frd, e_com),
            "citations": [
                {"evidenceId": e_txn, "excerpt": "Amex Auth: CHARGE $8,500.00, EMV_CHIP=YES, AMEX_SAFEKEY=PASS, AUTH CODE AMX-20260410-0733"},
                {"evidenceId": e_frd, "excerpt": "FraudShield AI: risk_score=18, transaction_type=digital_asset_purchase, no prior chargebacks on BIN in 180 days"},
                {"evidenceId": e_com, "excerpt": "CryptoVault CRM: Ticket #CVX-4491 opened 2026-04-11 by R.Williams; agent responded 2026-04-11T14:22Z — transaction confirmed as cardholder-initiated"},
            ],
        },
        "deadline": {
            "network":       "Amex",
            "dueDate":       due,
            "daysRemaining": _days_remaining(due),
        },
        "createdAt": "2026-05-01T07:30:00Z",
        "updatedAt": "2026-07-05T09:00:00Z",
    }


def _case_08() -> dict:
    """Discover UA01 — EMV Counterfeit Fraud, Card Present.
    DEMO DRAMA: 1 day remaining. Medium win. Legacy POS chip log unavailable."""
    cid   = _uid("case-08")
    e_txn = _uid("case-08-ev-txn")
    e_frd = _uid("case-08-ev-frd")
    due   = "2026-07-07"
    return {
        "caseId":           cid,
        "orchestrationId":  cid,
        "disputeRef":       "DFS-UA01-2026-89901",
        "cardNetwork":      "discover",
        "merchantName":     "GearOutlet Pro",
        "cardholderName":   "Anthony Nguyen",
        "transactionAmount": 762.44,
        "transactionDate":  "2026-06-20",
        "status":           "pending_review",
        "reasonCode":       "UA01",
        "reasonCodeLabel":  "Fraudulent Transaction — Card Present / EMV Counterfeit",
        "reasonCodeChecklist": [
            {"item": "EMV chip transaction log from POS terminal",               "required": True,  "satisfied": False},
            {"item": "Transaction authorization record",                         "required": True,  "satisfied": True},
            {"item": "Fraud velocity report from risk engine",                   "required": True,  "satisfied": True},
            {"item": "Cardholder notification / dispute acknowledgment on file", "required": False, "satisfied": True},
        ],
        "evidence": [
            {
                "evidenceId":   e_txn,
                "type":         "transaction",
                "sourceSystem": "Discover POS Network",
                "retrievedAt":  "2026-06-25T13:15:00Z",
                "contentRef":   "blob://disputes-demo/case-08/txn-record.json",
                "completeness": "complete",
            },
            {
                "evidenceId":   e_frd,
                "type":         "fraud_signal",
                "sourceSystem": "FraudShield AI v3",
                "retrievedAt":  "2026-06-25T13:17:22Z",
                "contentRef":   "blob://disputes-demo/case-08/fraud-signal.json",
                "completeness": "complete",
            },
        ],
        "evidenceGaps": [
            {
                "missingItem": "EMV chip transaction log from POS terminal (model GOP-8812)",
                "reason":      "POS firmware v3.1.4 predates the chip-and-pin upgrade; raw EMV tag data was not captured in the legacy transaction format at this store location.",
                "impact":      "high",
            },
        ],
        "winProbability": 0.61,
        "riskLevel":      "medium",
        "rebuttalDraft": {
            "text": (
                "Merchant disputes Discover UA01 chargeback for $762.44. The transaction was processed "
                "card-present with chip-read attempted on our POS terminal (see evidence [{}]). "
                "FraudShield AI scored this transaction at 29/100 with no velocity flags, and the card "
                "BIN had no prior chargebacks in 90 days (see evidence [{}]). While the raw EMV tag "
                "data is unavailable due to a legacy firmware limitation, terminal telemetry confirms a "
                "chip-read event occurred prior to fallback-swipe. The merchant fulfilled all due-diligence "
                "requirements available under the terminal's capabilities and requests reversal."
            ).format(e_txn, e_frd),
            "citations": [
                {"evidenceId": e_txn, "excerpt": "Discover POS: TXN DFS-2026-06-20-89901, $762.44, CHIP_READ_ATTEMPTED=Y, FALLBACK_SWIPE=Y, AUTH CODE 774821"},
                {"evidenceId": e_frd, "excerpt": "FraudShield AI: risk_score=29, velocity_flag=FALSE, bin_chargeback_rate_90d=0.1%, no prior fraud at this location"},
            ],
        },
        "deadline": {
            "network":       "Discover",
            "dueDate":       due,
            "daysRemaining": _days_remaining(due),
        },
        "createdAt": "2026-06-25T12:00:00Z",
        "updatedAt": "2026-07-05T18:30:00Z",
    }


def _case_09() -> dict:
    """Visa 13.3 — Merchandise Not as Described. Already approved.
    Five complete evidence items. Very high win probability. Demo 'resolved' showcase."""
    cid   = _uid("case-09")
    e_txn = _uid("case-09-ev-txn")
    e_ord = _uid("case-09-ev-ord")
    e_rct = _uid("case-09-ev-rct")
    e_com = _uid("case-09-ev-com")
    e_shp = _uid("case-09-ev-shp")
    due   = "2026-07-31"
    return {
        "caseId":           cid,
        "orchestrationId":  cid,
        "disputeRef":       "VCA-2026-0063301",
        "cardNetwork":      "visa",
        "merchantName":     "FurniCraft Direct",
        "cardholderName":   "Hannah Sorenson",
        "transactionAmount": 1845.00,
        "transactionDate":  "2026-03-22",
        "status":           "approved",
        "reasonCode":       "13.3",
        "reasonCodeLabel":  "Merchandise / Services Not as Described or Defective",
        "reasonCodeChecklist": [
            {"item": "Original order confirmation matching transaction amount",         "required": True,  "satisfied": True},
            {"item": "Product description at time of sale",                            "required": True,  "satisfied": True},
            {"item": "Itemized receipt",                                               "required": True,  "satisfied": True},
            {"item": "Merchant–cardholder correspondence regarding the dispute",       "required": True,  "satisfied": True},
            {"item": "Shipping and delivery confirmation record",                      "required": False, "satisfied": True},
        ],
        "evidence": [
            {
                "evidenceId":   e_txn,
                "type":         "transaction",
                "sourceSystem": "Visa Authorization Network",
                "retrievedAt":  "2026-04-15T09:00:00Z",
                "contentRef":   "blob://disputes-demo/case-09/txn-record.json",
                "completeness": "complete",
            },
            {
                "evidenceId":   e_ord,
                "type":         "order",
                "sourceSystem": "FurniCraft OMS",
                "retrievedAt":  "2026-04-15T09:02:10Z",
                "contentRef":   "blob://disputes-demo/case-09/order-record.json",
                "completeness": "complete",
            },
            {
                "evidenceId":   e_rct,
                "type":         "receipt",
                "sourceSystem": "FurniCraft Shopify",
                "retrievedAt":  "2026-04-15T09:03:45Z",
                "contentRef":   "blob://disputes-demo/case-09/receipt.pdf",
                "completeness": "complete",
            },
            {
                "evidenceId":   e_com,
                "type":         "communication",
                "sourceSystem": "Zendesk Support",
                "retrievedAt":  "2026-04-15T09:05:20Z",
                "contentRef":   "blob://disputes-demo/case-09/zendesk-export.json",
                "completeness": "complete",
            },
            {
                "evidenceId":   e_shp,
                "type":         "shipping",
                "sourceSystem": "FedEx Tracking API",
                "retrievedAt":  "2026-04-15T09:07:00Z",
                "contentRef":   "blob://disputes-demo/case-09/fedex-tracking.json",
                "completeness": "complete",
            },
        ],
        "evidenceGaps": [],
        "winProbability": 0.93,
        "riskLevel":      "low",
        "rebuttalDraft": {
            "text": (
                "Merchant disputes Visa 13.3 chargeback for $1,845.00. The transaction was authorized on "
                "2026-03-22 (see evidence [{}]). Order #FC-2026-63301 was fulfilled exactly as described — "
                "one Scandinavian oak dining table, model FC-DT-OAK-180, as itemized on the receipt "
                "(see evidence [{}] and [{}]). The cardholder contacted support on 2026-04-02 claiming the "
                "wood grain did not match the website photo; our agent provided a photographic comparison "
                "confirming the item is within documented natural-variation tolerances (see evidence [{}]). "
                "Delivery is confirmed by FedEx with photo proof of doorstep placement and recipient signature "
                "(see evidence [{}]). All evidence is complete and the chargeback has been approved for reversal."
            ).format(e_txn, e_ord, e_rct, e_com, e_shp),
            "citations": [
                {"evidenceId": e_txn, "excerpt": "Visa Auth: TXN VCA-2026-0063301, $1,845.00, APPROVED, 3DS2 ECI=05, 2026-03-22T16:44:09Z"},
                {"evidenceId": e_ord, "excerpt": "FurniCraft OMS: Order #FC-2026-63301, SKU FC-DT-OAK-180 'Scandinavian Oak Dining Table 180 cm', qty 1, $1,845.00"},
                {"evidenceId": e_rct, "excerpt": "Shopify receipt: FC-DT-OAK-180 × 1 @ $1,845.00, color=Natural Oak, finish=Matte — matches listing snapshot at time of purchase"},
                {"evidenceId": e_com, "excerpt": "Zendesk #FC-77211: Agent note 2026-04-03 — photo comparison sent; item confirmed within natural grain variation; cardholder acknowledged"},
                {"evidenceId": e_shp, "excerpt": "FedEx: TRK# 776241880031, DELIVERED 2026-04-01T14:22Z, PHOTO_POD=YES, recipient signature obtained at door"},
            ],
        },
        "deadline": {
            "network":       "Visa",
            "dueDate":       due,
            "daysRemaining": _days_remaining(due),
        },
        "createdAt":  "2026-04-15T08:30:00Z",
        "updatedAt":  "2026-07-05T14:30:00Z",
        "resolvedAt": "2026-07-05T14:30:00Z",
    }


def _case_10() -> dict:
    """Mastercard 4855 — Goods or Services Not Provided.
    Critical risk. Near-expiry (3 days). Two critical + one medium gap. Partial rebuttal."""
    cid   = _uid("case-10")
    e_txn = _uid("case-10-ev-txn")
    e_ord = _uid("case-10-ev-ord")
    e_com = _uid("case-10-ev-com")
    due   = "2026-07-09"
    return {
        "caseId":           cid,
        "orchestrationId":  cid,
        "disputeRef":       "MC-4855-2026-07744",
        "cardNetwork":      "mastercard",
        "merchantName":     "AirRoute Connect",
        "cardholderName":   "Carlos Mendez",
        "transactionAmount": 4100.00,
        "transactionDate":  "2026-06-28",
        "status":           "pending_review",
        "reasonCode":       "4855",
        "reasonCodeLabel":  "Goods or Services Not Provided",
        "reasonCodeChecklist": [
            {"item": "Booking or service confirmation tied to transaction",    "required": True,  "satisfied": True},
            {"item": "Proof of service delivery or fulfillment",              "required": True,  "satisfied": False},
            {"item": "Customer communication log",                            "required": True,  "satisfied": True},
            {"item": "Delivery manifest or service completion record",        "required": True,  "satisfied": False},
        ],
        "evidence": [
            {
                "evidenceId":   e_txn,
                "type":         "transaction",
                "sourceSystem": "Mastercard Authorization Hub",
                "retrievedAt":  "2026-07-01T10:00:00Z",
                "contentRef":   "blob://disputes-demo/case-10/txn-record.json",
                "completeness": "complete",
            },
            {
                "evidenceId":   e_ord,
                "type":         "order",
                "sourceSystem": "AirRoute OMS",
                "retrievedAt":  "2026-07-01T10:02:30Z",
                "contentRef":   "blob://disputes-demo/case-10/order-record.json",
                "completeness": "partial",
            },
            {
                "evidenceId":   e_com,
                "type":         "communication",
                "sourceSystem": "AirRoute CRM",
                "retrievedAt":  "2026-07-01T10:04:15Z",
                "contentRef":   "blob://disputes-demo/case-10/crm-comms.json",
                "completeness": "partial",
            },
        ],
        "evidenceGaps": [
            {
                "missingItem": "Proof of flight / service fulfillment (departure manifest)",
                "reason":      "AirRoute OMS returned a partial booking record; the departure manifest confirming the service was rendered has not been attached to the case.",
                "impact":      "critical",
            },
            {
                "missingItem": "Service completion or delivery manifest PDF",
                "reason":      "OMS marks booking #ARC-20260628-7744 as 'FULFILLED' but the manifest PDF is absent from blob storage — likely a pipeline ingestion failure.",
                "impact":      "critical",
            },
            {
                "missingItem": "Customer service escalation log (Zendesk ticket #ARC-28811)",
                "reason":      "CRM note references this Zendesk ticket but it was not ingested into the evidence store during case assembly.",
                "impact":      "medium",
            },
        ],
        "winProbability": 0.39,
        "riskLevel":      "critical",
        "rebuttalDraft": {
            "text": (
                "Merchant disputes Mastercard 4855 chargeback for $4,100.00 (booking date 2026-06-28). "
                "The transaction was authorized and the booking was confirmed by our OMS "
                "(see evidence [{}] and [{}]). AirRoute CRM shows customer contact was received and "
                "responded to on 2026-06-29 (see evidence [{}]). The departure manifest and fulfillment "
                "records are being urgently retrieved from our operations system and will be submitted as "
                "supplemental evidence. We assert the service was rendered as booked and request the "
                "chargeback be reversed pending submission of the complete fulfillment documentation."
            ).format(e_txn, e_ord, e_com),
            "citations": [
                {"evidenceId": e_txn, "excerpt": "MC Auth Hub: TXN MC-2026-06-28-07744, $4,100.00, AUTH CODE 661230, APPROVED"},
                {"evidenceId": e_ord, "excerpt": "AirRoute OMS: Booking #ARC-20260628-7744, status=FULFILLED, route=DFW→LHR, service_date=2026-07-02 (partial record — manifest not attached)"},
                {"evidenceId": e_com, "excerpt": "AirRoute CRM: C.Mendez contacted 2026-06-29T10:15Z; agent responded 2026-06-29T11:02Z confirming booking details"},
            ],
        },
        "deadline": {
            "network":       "Mastercard",
            "dueDate":       due,
            "daysRemaining": _days_remaining(due),
        },
        "createdAt": "2026-07-01T09:30:00Z",
        "updatedAt": "2026-07-05T22:00:00Z",
    }


# ══════════════════════════════════════════════════════════════════════════════
# Validation
# ══════════════════════════════════════════════════════════════════════════════

_VALID_STATUSES  = {"intake","evidence_gathering","ai_drafting","pending_review",
                    "approved","denied","escalated","submitted","expired"}
_VALID_NETWORKS  = {"visa","mastercard","amex","discover"}
_VALID_RISK      = {"low","medium","high","critical"}
_VALID_EV_TYPES  = {"transaction","shipping","communication","receipt",
                    "contract","fraud_signal","order"}
_VALID_COMPLETE  = {"complete","partial","missing"}
_VALID_IMPACT    = {"critical","high","medium","low"}


def _manual_validate(cases: list[dict]) -> None:
    required_top = {"caseId", "status", "reasonCode", "deadline", "createdAt"}
    errors: list[str] = []

    for case in cases:
        cid = case.get("caseId", "?")

        for f in required_top:
            if f not in case:
                errors.append(f"{cid}: missing required field '{f}'")

        if case.get("status") not in _VALID_STATUSES:
            errors.append(f"{cid}: invalid status '{case.get('status')}'")
        if "cardNetwork" in case and case["cardNetwork"] not in _VALID_NETWORKS:
            errors.append(f"{cid}: invalid cardNetwork '{case['cardNetwork']}'")
        if "riskLevel" in case and case["riskLevel"] not in _VALID_RISK:
            errors.append(f"{cid}: invalid riskLevel '{case['riskLevel']}'")
        if "winProbability" in case:
            wp = case["winProbability"]
            if not (isinstance(wp, (int, float)) and 0 <= wp <= 1):
                errors.append(f"{cid}: winProbability {wp!r} out of range 0–1")

        ev_ids: set[str] = set()
        for ev in case.get("evidence", []):
            for f in ("evidenceId", "type", "sourceSystem", "retrievedAt", "contentRef", "completeness"):
                if f not in ev:
                    errors.append(f"{cid}: evidence item missing field '{f}'")
            if ev.get("type") not in _VALID_EV_TYPES:
                errors.append(f"{cid}: invalid evidence type '{ev.get('type')}'")
            if ev.get("completeness") not in _VALID_COMPLETE:
                errors.append(f"{cid}: invalid evidence completeness '{ev.get('completeness')}'")
            ev_ids.add(ev.get("evidenceId", ""))

        for gap in case.get("evidenceGaps", []):
            for f in ("missingItem", "reason", "impact"):
                if f not in gap:
                    errors.append(f"{cid}: evidenceGap missing field '{f}'")
            if gap.get("impact") not in _VALID_IMPACT:
                errors.append(f"{cid}: invalid gap impact '{gap.get('impact')}'")

        rb = case.get("rebuttalDraft")
        if rb is not None:
            for cit in rb.get("citations", []):
                for f in ("evidenceId", "excerpt"):
                    if f not in cit:
                        errors.append(f"{cid}: citation missing field '{f}'")
                if cit.get("evidenceId") not in ev_ids:
                    errors.append(f"{cid}: citation evidenceId '{cit.get('evidenceId')}' not found in evidence list")

        dl = case.get("deadline", {})
        for f in ("network", "dueDate", "daysRemaining"):
            if f not in dl:
                errors.append(f"{cid}: deadline missing field '{f}'")

    if errors:
        print("\n  VALIDATION ERRORS:")
        for e in errors:
            print(f"    FAIL {e}")
        raise SystemExit(1)
    print(f"  [OK] All {len(cases)} cases pass manual field validation.")


def _schema_validate(cases: list[dict], schema_path: Path) -> None:
    if not schema_path.exists():
        print(f"  [WARN] Schema not found at {schema_path} -- skipping JSON Schema validation.")
        _manual_validate(cases)
        return

    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    try:
        import jsonschema
        # Prefer Draft202012Validator if available (jsonschema >= 4.18)
        try:
            from jsonschema import Draft202012Validator as Validator
        except ImportError:
            from jsonschema import Draft7Validator as Validator  # type: ignore[assignment]

        errors: list[str] = []
        for case in cases:
            v = Validator(schema)
            errs = sorted(v.iter_errors(case), key=lambda e: list(e.path))
            for err in errs:
                path = " > ".join(str(p) for p in err.absolute_path) or "(root)"
                errors.append(f"  FAIL {case.get('caseId','?')} [{path}]: {err.message}")
        if errors:
            for e in errors:
                print(e)
            raise SystemExit(1)
        print(f"  [OK] All {len(cases)} cases pass JSON Schema (jsonschema) validation.")

    except ImportError:
        print("  [INFO] jsonschema not installed -- running manual field validation instead.")
        _manual_validate(cases)


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

_BUILDERS = [
    _case_01, _case_02, _case_03, _case_04, _case_05,
    _case_06, _case_07, _case_08, _case_09, _case_10,
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic dispute cases for the demo."
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).parent),
        help="Root output directory (default: directory containing this script)",
    )
    args = parser.parse_args()

    output_root = Path(args.output_dir)
    cases_dir   = output_root / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nGenerating {len(_BUILDERS)} synthetic cases -> {output_root}\n")
    print(f"  {'caseId (short)':<38} {'code':<6} {'network':<12} {'status':<22} {'days':>4}  win")
    print("  " + "-" * 92)

    all_cases: list[dict] = []
    for builder in _BUILDERS:
        case = builder()
        case_file = cases_dir / f"{case['caseId']}.json"
        case_file.write_text(json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8")
        all_cases.append(case)

        short_id = case["caseId"][:8] + "…"
        wp = case.get("winProbability")
        wp_str = f"{wp:.0%}" if wp is not None else "n/a"
        print(
            f"  {short_id:<38} {case['reasonCode']:<6} {case['cardNetwork']:<12} "
            f"{case['status']:<22} {case['deadline']['daysRemaining']:>4}  {wp_str}"
        )

    combined_file = output_root / "cases.json"
    combined_file.write_text(json.dumps(all_cases, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  [OK] Individual files -> {cases_dir}")
    print(f"  [OK] Combined array   -> {combined_file}  ({len(all_cases)} cases)")

    # Validate — prefer JSON Schema, fall back to manual
    schema_path = Path(__file__).parent.parent.parent / "shared" / "schemas" / "case.schema.json"
    print(f"\nValidating against schema at {schema_path} ...")
    _schema_validate(all_cases, schema_path)
    print()


if __name__ == "__main__":
    main()
