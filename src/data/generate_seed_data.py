"""
Synthetic Data Generator for Payments Dispute Resolution

Generates realistic dispute cases across all 4 card networks with:
- Proper reason codes per network
- Multi-system evidence (transactions, orders, shipping, comms, fraud, receipts)
- Full lifecycle timelines (intake → gathering → drafting → review → outcome)
- Win probability and risk scores
- Reg E / card network deadline compliance scenarios
- Edge cases: escalations, timeouts, missed deadlines, friendly fraud

Output: JSON files ready to seed into Cosmos DB or load into Fabric/OneLake.

Usage:
    python generate_seed_data.py [--count 200] [--output-dir ./data/seed]
"""

import json
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
import argparse

# ---------------------------------------------------------------------------
# Reference Data — Card Networks & Reason Codes
# ---------------------------------------------------------------------------

REASON_CODES = {
    "visa": [
        {"code": "10.1", "description": "EMV Liability Shift Counterfeit Fraud", "category": "fraud", "evidence_required": ["transaction_receipt", "emv_chip_data", "authorization_log"]},
        {"code": "10.4", "description": "Other Fraud — Card Absent Environment", "category": "fraud", "evidence_required": ["avs_cvv_results", "ip_geolocation", "device_fingerprint", "3ds_authentication"]},
        {"code": "11.1", "description": "Card Recovery Bulletin", "category": "authorization", "evidence_required": ["authorization_log", "card_recovery_bulletin_date"]},
        {"code": "12.5", "description": "Incorrect Amount", "category": "processing_error", "evidence_required": ["transaction_receipt", "signed_receipt", "terminal_data"]},
        {"code": "12.6", "description": "Duplicate Processing", "category": "processing_error", "evidence_required": ["transaction_logs", "batch_settlement_records", "authorization_log"]},
        {"code": "13.1", "description": "Merchandise/Services Not Received", "category": "consumer_dispute", "evidence_required": ["shipping_confirmation", "delivery_proof", "tracking_number", "signed_delivery"]},
        {"code": "13.2", "description": "Cancelled Recurring Transaction", "category": "consumer_dispute", "evidence_required": ["cancellation_policy", "terms_of_service", "communication_records"]},
        {"code": "13.3", "description": "Not as Described or Defective", "category": "consumer_dispute", "evidence_required": ["product_description", "photos", "return_policy", "communication_records"]},
        {"code": "13.6", "description": "Credit Not Processed", "category": "consumer_dispute", "evidence_required": ["refund_policy", "return_receipt", "credit_voucher", "communication_records"]},
        {"code": "13.7", "description": "Cancelled Merchandise/Services", "category": "consumer_dispute", "evidence_required": ["cancellation_policy", "terms_of_service", "proof_of_service_delivery"]},
    ],
    "mastercard": [
        {"code": "4834", "description": "Point-of-Interaction Error", "category": "processing_error", "evidence_required": ["transaction_receipt", "terminal_data", "batch_records"]},
        {"code": "4837", "description": "No Cardholder Authorization", "category": "fraud", "evidence_required": ["signed_receipt", "authorization_log", "cvv_avs_response"]},
        {"code": "4840", "description": "Fraudulent Processing of Transactions", "category": "fraud", "evidence_required": ["authorization_log", "merchant_agreement", "processing_records"]},
        {"code": "4853", "description": "Cardholder Dispute — Goods/Services", "category": "consumer_dispute", "evidence_required": ["shipping_proof", "delivery_confirmation", "product_description", "communication_records"]},
        {"code": "4855", "description": "Goods or Services Not Provided", "category": "consumer_dispute", "evidence_required": ["proof_of_delivery", "tracking_info", "service_completion_record"]},
        {"code": "4859", "description": "Addendum, No-show, or ATM Dispute", "category": "consumer_dispute", "evidence_required": ["reservation_confirmation", "cancellation_policy", "no_show_documentation"]},
        {"code": "4863", "description": "Cardholder Does Not Recognize", "category": "fraud", "evidence_required": ["transaction_receipt", "authorization_log", "merchant_descriptor_evidence"]},
        {"code": "4871", "description": "Chip/PIN Liability Shift", "category": "fraud", "evidence_required": ["emv_data", "terminal_capability", "authorization_log"]},
    ],
    "amex": [
        {"code": "C02", "description": "Credit Not Processed", "category": "consumer_dispute", "evidence_required": ["refund_policy", "credit_voucher", "communication_records"]},
        {"code": "C04", "description": "Goods/Services Not Received", "category": "consumer_dispute", "evidence_required": ["proof_of_delivery", "tracking_number", "shipping_confirmation"]},
        {"code": "C05", "description": "Goods/Services Cancelled", "category": "consumer_dispute", "evidence_required": ["cancellation_policy", "terms_agreement", "communication_records"]},
        {"code": "C08", "description": "Goods/Services Not as Described", "category": "consumer_dispute", "evidence_required": ["product_listing", "photos", "communication_records", "return_policy"]},
        {"code": "C14", "description": "Paid by Other Means", "category": "processing_error", "evidence_required": ["alternative_payment_proof", "transaction_records"]},
        {"code": "C18", "description": "Cancel of Recurring Billing", "category": "consumer_dispute", "evidence_required": ["billing_agreement", "cancellation_request", "processing_records"]},
        {"code": "F10", "description": "Missing Imprint", "category": "fraud", "evidence_required": ["signed_receipt", "imprint_copy", "authorization_log"]},
        {"code": "F14", "description": "Missing Signature", "category": "fraud", "evidence_required": ["signed_receipt", "signature_comparison", "authorization_log"]},
        {"code": "F24", "description": "No Cardmember Authorization", "category": "fraud", "evidence_required": ["authorization_log", "fraud_investigation_report", "ip_data"]},
        {"code": "F29", "description": "Card Not Present", "category": "fraud", "evidence_required": ["avs_cvv_results", "3ds_authentication", "ip_geolocation", "device_fingerprint"]},
    ],
    "discover": [
        {"code": "AA", "description": "Cardholder Does Not Recognize", "category": "fraud", "evidence_required": ["transaction_receipt", "authorization_log", "merchant_descriptor"]},
        {"code": "AP", "description": "Cancelled Recurring Transaction", "category": "consumer_dispute", "evidence_required": ["billing_agreement", "cancellation_confirmation", "processing_records"]},
        {"code": "AW", "description": "Altered Amount", "category": "processing_error", "evidence_required": ["original_receipt", "terminal_data", "authorization_log"]},
        {"code": "CD", "description": "Credit/Debit Posted Incorrectly", "category": "processing_error", "evidence_required": ["transaction_records", "batch_settlement", "authorization_log"]},
        {"code": "DP", "description": "Duplicate Processing", "category": "processing_error", "evidence_required": ["transaction_logs", "batch_records", "settlement_data"]},
        {"code": "EX", "description": "Expired Card", "category": "authorization", "evidence_required": ["authorization_log", "card_expiry_verification"]},
        {"code": "NF", "description": "Non-receipt of Cash from ATM", "category": "consumer_dispute", "evidence_required": ["atm_journal", "surveillance_footage", "reconciliation_records"]},
        {"code": "RG", "description": "Non-Receipt of Goods/Services", "category": "consumer_dispute", "evidence_required": ["shipping_proof", "delivery_confirmation", "tracking_info"]},
        {"code": "RM", "description": "Quality Discrepancy", "category": "consumer_dispute", "evidence_required": ["product_description", "photos", "communication_records", "return_policy"]},
        {"code": "UA", "description": "Fraud — Card Present", "category": "fraud", "evidence_required": ["signed_receipt", "emv_chip_data", "surveillance_footage"]},
    ],
}

# Deadline rules per network
DEADLINE_DAYS = {
    "visa": 30,
    "mastercard": 45,
    "amex": 20,
    "discover": 30,
}

# ---------------------------------------------------------------------------
# Reference Data — Merchants, Cardholders, Analysts
# ---------------------------------------------------------------------------

MERCHANTS = [
    {"name": "TechGadgets Inc", "mcc": "5732", "category": "Electronics"},
    {"name": "CloudStream Pro", "mcc": "5815", "category": "Digital Services"},
    {"name": "FreshMart Grocery", "mcc": "5411", "category": "Grocery"},
    {"name": "SkyHigh Airlines", "mcc": "3000", "category": "Airlines"},
    {"name": "Urban Threads Apparel", "mcc": "5651", "category": "Clothing"},
    {"name": "AutoParts Direct", "mcc": "5533", "category": "Auto Parts"},
    {"name": "GourmetBox Subscription", "mcc": "5499", "category": "Food Subscription"},
    {"name": "FitLife Gym Membership", "mcc": "7941", "category": "Health & Fitness"},
    {"name": "QuickStay Hotels", "mcc": "7011", "category": "Hotels"},
    {"name": "StreamVault Entertainment", "mcc": "7829", "category": "Streaming"},
    {"name": "PetCare Plus", "mcc": "5995", "category": "Pet Supplies"},
    {"name": "HomeReno Solutions", "mcc": "5211", "category": "Home Improvement"},
    {"name": "SafeGuard Insurance", "mcc": "6300", "category": "Insurance"},
    {"name": "EduLearn Online", "mcc": "8220", "category": "Education"},
    {"name": "LuxWatch Boutique", "mcc": "5944", "category": "Jewelry"},
    {"name": "RideShare Express", "mcc": "4121", "category": "Transportation"},
    {"name": "GameZone Digital", "mcc": "5816", "category": "Digital Games"},
    {"name": "PharmaCare RX", "mcc": "5912", "category": "Pharmacy"},
    {"name": "TravelWise Agency", "mcc": "4722", "category": "Travel"},
    {"name": "GreenEnergy Solar", "mcc": "5999", "category": "Misc Retail"},
]

CARDHOLDERS = [
    {"name": "Sarah Chen", "city": "San Francisco", "state": "CA"},
    {"name": "Michael Rodriguez", "city": "Austin", "state": "TX"},
    {"name": "Emily Watson", "city": "Chicago", "state": "IL"},
    {"name": "James Kim", "city": "Seattle", "state": "WA"},
    {"name": "Patricia Johnson", "city": "New York", "state": "NY"},
    {"name": "David Okafor", "city": "Atlanta", "state": "GA"},
    {"name": "Lisa Patel", "city": "Boston", "state": "MA"},
    {"name": "Robert Martinez", "city": "Denver", "state": "CO"},
    {"name": "Amanda Thompson", "city": "Portland", "state": "OR"},
    {"name": "Christopher Lee", "city": "Miami", "state": "FL"},
    {"name": "Jennifer Davis", "city": "Phoenix", "state": "AZ"},
    {"name": "Daniel Wilson", "city": "Minneapolis", "state": "MN"},
    {"name": "Maria Gonzalez", "city": "Dallas", "state": "TX"},
    {"name": "William Brown", "city": "Philadelphia", "state": "PA"},
    {"name": "Rachel Green", "city": "Nashville", "state": "TN"},
    {"name": "Thomas Anderson", "city": "Charlotte", "state": "NC"},
    {"name": "Samantha White", "city": "San Diego", "state": "CA"},
    {"name": "Kevin Nguyen", "city": "Houston", "state": "TX"},
    {"name": "Michelle Park", "city": "Los Angeles", "state": "CA"},
    {"name": "Andrew Scott", "city": "Washington", "state": "DC"},
    {"name": "Jessica Taylor", "city": "Detroit", "state": "MI"},
    {"name": "Brian Campbell", "city": "Columbus", "state": "OH"},
    {"name": "Nicole Adams", "city": "Raleigh", "state": "NC"},
    {"name": "Steven Clark", "city": "Indianapolis", "state": "IN"},
    {"name": "Laura Mitchell", "city": "Salt Lake City", "state": "UT"},
]

ANALYSTS = [
    {"name": "Ana Rivera", "id": "analyst-001", "level": "senior"},
    {"name": "Marcus Chen", "id": "analyst-002", "level": "senior"},
    {"name": "Priya Sharma", "id": "analyst-003", "level": "mid"},
    {"name": "Jason Park", "id": "analyst-004", "level": "mid"},
    {"name": "Diana Lopez", "id": "analyst-005", "level": "junior"},
    {"name": "Kwame Asante", "id": "analyst-006", "level": "junior"},
    {"name": "Supervisor: Tanya Moore", "id": "supervisor-001", "level": "supervisor"},
]

# Dispute statuses aligned with case.schema.json (src/shared/schemas/case.schema.json)
STATUS_DISTRIBUTION = [
    ("intake", 0.05),
    ("evidence_gathering", 0.08),
    ("ai_drafting", 0.07),
    ("pending_review", 0.12),
    ("approved", 0.25),
    ("submitted", 0.20),
    ("denied", 0.08),
    ("escalated", 0.05),
    ("expired", 0.03),
    ("closed", 0.07),  # terminal state with resolvedAt
]

# Risk level thresholds (derived from numeric risk score)
RISK_LEVELS = [
    (75, "critical"),
    (55, "high"),
    (35, "medium"),
    (0, "low"),
]

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _new_id() -> str:
    return str(uuid.uuid4())


def _random_date(start_days_ago: int = 90, end_days_ago: int = 1) -> datetime:
    """Generate a random datetime between start_days_ago and end_days_ago."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=start_days_ago)
    end = now - timedelta(days=end_days_ago)
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=random_seconds)


def _random_amount(min_val: float = 15.0, max_val: float = 5000.0) -> float:
    """Generate a realistic transaction amount with bias toward smaller amounts."""
    # 70% chance of amount under $500, 20% $500-2000, 10% $2000-5000
    r = random.random()
    if r < 0.70:
        return round(random.uniform(min_val, 500.0), 2)
    elif r < 0.90:
        return round(random.uniform(500.0, 2000.0), 2)
    else:
        return round(random.uniform(2000.0, max_val), 2)


def _weighted_choice(choices: list[tuple]) -> str:
    """Choose from a list of (value, weight) tuples."""
    values, weights = zip(*choices)
    return random.choices(values, weights=weights, k=1)[0]


def _card_last_four() -> str:
    return f"{random.randint(1000, 9999)}"


def _risk_level(score: int) -> str:
    """Convert numeric risk score to categorical risk level."""
    for threshold, level in RISK_LEVELS:
        if score >= threshold:
            return level
    return "low"


def _network_dispute_ref(network: str) -> str:
    """Generate a network-specific dispute reference number."""
    num = random.randint(10000, 99999)
    year = 2026
    prefix = {"visa": "VISA", "mastercard": "MC", "amex": "AMEX", "discover": "DISC"}
    return f"{prefix[network]}-{year}-{num:05d}"


def generate_reason_code_checklist(reason: dict, evidence_collected: int) -> list[dict]:
    """Generate a reason code checklist showing which evidence requirements are satisfied."""
    checklist = []
    required_items = reason.get("evidence_required", [])
    for i, item in enumerate(required_items):
        # Items are satisfied based on how much evidence has been gathered
        satisfied = i < evidence_collected
        checklist.append({
            "item": item.replace("_", " ").title(),
            "required": True,
            "satisfied": satisfied,
        })
    # Add 1-2 optional bonus items
    optional_items = ["IP address and device metadata", "Customer communication history", "Prior dispute history"]
    for opt in random.sample(optional_items, k=min(2, len(optional_items))):
        checklist.append({
            "item": opt,
            "required": False,
            "satisfied": random.random() > 0.4,
        })
    return checklist


def generate_evidence_gaps(reason: dict, status: str, checklist: list[dict]) -> list[dict]:
    """Generate structured evidence gaps based on unsatisfied checklist items."""
    if status in ("approved", "submitted", "closed"):
        return []  # No gaps for completed cases

    gaps = []
    unsatisfied = [c for c in checklist if c["required"] and not c["satisfied"]]
    impact_map = {"critical": 0.3, "high": 0.3, "medium": 0.3, "low": 0.1}

    reasons_pool = [
        "Source system returned empty response; manual retrieval pending.",
        "Document exists but is partially illegible; re-scan requested.",
        "Third-party vendor has not responded to data request within SLA.",
        "Record exists in legacy system; migration to API access in progress.",
        "Cardholder has not provided requested documentation.",
        "System integration pending — data available via manual export only.",
    ]

    for item in unsatisfied:
        impact = random.choices(
            list(impact_map.keys()),
            weights=list(impact_map.values()),
            k=1,
        )[0]
        gaps.append({
            "missingItem": item["item"],
            "reason": random.choice(reasons_pool),
            "impact": impact,
        })
    return gaps


def generate_rebuttal_draft(dispute: dict, evidence_ids: list[str]) -> dict | None:
    """Generate a structured rebuttal draft with evidence citations."""
    if dispute["status"] in ("intake", "evidence_gathering"):
        return None

    # Build draft text
    merchant = dispute["merchantName"]
    network = dispute["cardNetwork"].title()
    amount = dispute["transactionAmount"]
    reason_code = dispute["reasonCode"]
    reason_label = dispute["reasonCodeLabel"]

    templates = [
        f"Merchant responds to {network} {reason_code} ({reason_label}) chargeback for ${amount:,.2f}. ",
        f"In response to the {network} dispute ({reason_code} — {reason_label}) for ${amount:,.2f}, the merchant provides the following evidence. ",
        f"This rebuttal addresses the {reason_label} claim ({reason_code}) filed against {merchant} for ${amount:,.2f}. ",
    ]

    text = random.choice(templates)
    citations = []

    # Add 1-3 citations referencing actual evidence
    cite_count = min(len(evidence_ids), random.randint(1, 3))
    for eid in evidence_ids[:cite_count]:
        excerpts = [
            f"Transaction authorized and settled normally via standard {network} processing path.",
            f"Delivery confirmed with signature on file matching cardholder name.",
            f"Risk assessment shows normal velocity and no prior chargebacks in 90-day window.",
            f"Customer communication records show no cancellation request was received.",
            f"Order fulfillment records confirm goods shipped and delivered within SLA.",
        ]
        citations.append({
            "evidenceId": eid,
            "excerpt": random.choice(excerpts),
        })
        text += f"See evidence [{eid[:8]}]. "

    if dispute["status"] in ("evidence_gathering", "ai_drafting"):
        text += "Draft is pending final evidence retrieval before submission."

    return {"text": text.strip(), "citations": citations}


# ---------------------------------------------------------------------------
# Evidence Generators
# ---------------------------------------------------------------------------

def generate_transaction_evidence(dispute: dict) -> dict:
    """Generate a transaction record evidence item."""
    return {
        "id": _new_id(),
        "evidenceId": _new_id(),
        "disputeId": dispute["disputeId"],
        "type": "transaction",
        "evidenceType": "transaction",
        "sourceSystem": "payment_processor",
        "title": f"Transaction Record — {dispute['merchantName']}",
        "content": {
            "transactionId": f"TXN-{random.randint(100000, 999999)}",
            "amount": dispute["transactionAmount"],
            "currency": dispute["transactionCurrency"],
            "merchantName": dispute["merchantName"],
            "merchantId": f"MID-{random.randint(10000, 99999)}",
            "terminalId": f"TID-{random.randint(1000, 9999)}",
            "authorizationCode": f"{random.randint(100000, 999999)}",
            "responseCode": "00",
            "cardPresent": random.choice([True, False]),
            "entryMode": random.choice(["chip", "contactless", "keyed", "swiped", "ecommerce"]),
            "avsResponse": random.choice(["Y", "N", "U", "A", "Z"]),
            "cvvResponse": random.choice(["M", "N", "U"]),
            "processedAt": dispute["transactionDate"],
            "settlementDate": (datetime.fromisoformat(dispute["transactionDate"]) + timedelta(days=random.randint(1, 3))).isoformat(),
        },
        "contentRef": f"blob://disputes-data/{dispute['disputeId']}/txn-record.json",
        "completeness": "complete",
        "retrievedAt": dispute["createdAt"],
        "blobUrl": None,
        "extractedAt": dispute["createdAt"],
    }


def generate_order_evidence(dispute: dict) -> dict:
    """Generate an order/fulfillment evidence item."""
    order_date = datetime.fromisoformat(dispute["transactionDate"])
    ship_date = order_date + timedelta(days=random.randint(1, 5))
    delivery_date = ship_date + timedelta(days=random.randint(2, 7))

    return {
        "id": _new_id(),
        "evidenceId": _new_id(),
        "disputeId": dispute["disputeId"],
        "type": "order",
        "evidenceType": "order",
        "sourceSystem": "oms_erp",
        "title": f"Order Record — #{random.randint(100000, 999999)}",
        "content": {
            "orderId": f"ORD-{random.randint(100000, 999999)}",
            "orderDate": order_date.isoformat(),
            "orderStatus": random.choice(["delivered", "shipped", "processing", "cancelled"]),
            "items": [
                {
                    "sku": f"SKU-{random.randint(1000, 9999)}",
                    "description": f"Product item from {dispute['merchantName']}",
                    "quantity": random.randint(1, 3),
                    "unitPrice": round(dispute["transactionAmount"] / random.randint(1, 3), 2),
                }
            ],
            "shippingAddress": {
                "city": random.choice(CARDHOLDERS)["city"],
                "state": random.choice(CARDHOLDERS)["state"],
                "country": "US",
            },
            "shipDate": ship_date.isoformat(),
            "deliveryDate": delivery_date.isoformat(),
        },
        "contentRef": f"blob://disputes-data/{dispute['disputeId']}/order-record.json",
        "completeness": random.choice(["complete", "complete", "partial"]),
        "retrievedAt": dispute["createdAt"],
        "blobUrl": None,
        "extractedAt": dispute["createdAt"],
    }


def generate_shipping_evidence(dispute: dict) -> dict:
    """Generate a shipping/logistics evidence item."""
    carriers = ["UPS", "FedEx", "USPS", "DHL", "OnTrac"]
    carrier = random.choice(carriers)
    delivered = random.random() > 0.15  # 85% delivered

    return {
        "id": _new_id(),
        "evidenceId": _new_id(),
        "disputeId": dispute["disputeId"],
        "type": "shipping",
        "evidenceType": "shipping",
        "sourceSystem": "logistics",
        "title": f"Shipping Record — {carrier}",
        "content": {
            "trackingNumber": f"{carrier[:2].upper()}{random.randint(1000000000, 9999999999)}",
            "carrier": carrier,
            "status": "delivered" if delivered else random.choice(["in_transit", "out_for_delivery", "exception"]),
            "shipDate": (datetime.fromisoformat(dispute["transactionDate"]) + timedelta(days=random.randint(1, 3))).isoformat(),
            "deliveryDate": (datetime.fromisoformat(dispute["transactionDate"]) + timedelta(days=random.randint(4, 10))).isoformat() if delivered else None,
            "signedBy": random.choice(CARDHOLDERS)["name"].split()[0] if delivered and random.random() > 0.5 else None,
            "deliveryAddress": {
                "city": random.choice(CARDHOLDERS)["city"],
                "state": random.choice(CARDHOLDERS)["state"],
            },
            "weight": f"{random.uniform(0.5, 25.0):.1f} lbs",
        },
        "contentRef": f"blob://disputes-data/{dispute['disputeId']}/shipping-record.json",
        "completeness": "complete" if delivered else "partial",
        "retrievedAt": dispute["createdAt"],
        "blobUrl": None,
        "extractedAt": dispute["createdAt"],
    }


def generate_communication_evidence(dispute: dict) -> dict:
    """Generate a customer communication evidence item."""
    comm_types = ["email", "chat", "phone_call", "support_ticket"]
    comm_type = random.choice(comm_types)

    subjects = [
        f"RE: Order issue with {dispute['merchantName']}",
        f"Dispute inquiry — transaction on {dispute['transactionDate']}",
        f"Refund request — {dispute['merchantName']}",
        f"Service complaint — {dispute['merchantName']}",
        f"Cancellation confirmation",
    ]

    return {
        "id": _new_id(),
        "evidenceId": _new_id(),
        "disputeId": dispute["disputeId"],
        "type": "communication",
        "evidenceType": "communication",
        "sourceSystem": "crm",
        "title": f"Customer Communication — {comm_type.replace('_', ' ').title()}",
        "content": {
            "communicationType": comm_type,
            "subject": random.choice(subjects),
            "date": (datetime.fromisoformat(dispute["transactionDate"]) + timedelta(days=random.randint(0, 14))).isoformat(),
            "direction": random.choice(["inbound", "outbound"]),
            "summary": f"Customer contacted regarding {dispute['reasonCode']} — {dispute['merchantName']} transaction of ${dispute['transactionAmount']}",
            "resolution": random.choice(["pending", "refund_offered", "escalated", "resolved", "no_response"]),
            "agentName": random.choice(ANALYSTS)["name"],
        },
        "contentRef": f"blob://disputes-data/{dispute['disputeId']}/comm-{comm_type}.json",
        "completeness": random.choice(["complete", "complete", "partial"]),
        "retrievedAt": dispute["createdAt"],
        "blobUrl": None,
        "extractedAt": dispute["createdAt"],
    }


def generate_fraud_signal_evidence(dispute: dict) -> dict:
    """Generate a fraud signal/risk evidence item."""
    risk_score = random.randint(10, 99)

    return {
        "id": _new_id(),
        "evidenceId": _new_id(),
        "disputeId": dispute["disputeId"],
        "type": "fraud_signal",
        "evidenceType": "fraud_signal",
        "sourceSystem": "fraud_engine",
        "title": f"Fraud Risk Assessment — Score: {risk_score}",
        "content": {
            "riskScore": risk_score,
            "riskLevel": "high" if risk_score > 75 else "medium" if risk_score > 40 else "low",
            "signals": random.sample([
                "velocity_spike",
                "geo_mismatch",
                "device_fingerprint_new",
                "unusual_amount",
                "time_of_day_anomaly",
                "merchant_category_unusual",
                "card_testing_pattern",
                "account_takeover_indicator",
                "friendly_fraud_indicator",
                "first_party_fraud_pattern",
            ], k=random.randint(1, 4)),
            "previousChargebacks": random.randint(0, 5),
            "accountAge": f"{random.randint(1, 120)} months",
            "friendlyFraudProbability": round(random.uniform(0.0, 1.0), 2),
            "assessmentDate": dispute["createdAt"],
        },
        "contentRef": f"blob://disputes-data/{dispute['disputeId']}/fraud-signal.json",
        "completeness": "complete",
        "retrievedAt": dispute["createdAt"],
        "blobUrl": None,
        "extractedAt": dispute["createdAt"],
    }


def generate_receipt_evidence(dispute: dict) -> dict:
    """Generate a receipt/document evidence item."""
    doc_type = random.choice(["receipt", "invoice", "contract", "terms_of_service"])
    ocr_quality = random.choice(["excellent", "good", "fair"])
    completeness = "complete" if ocr_quality == "excellent" else "partial" if ocr_quality == "good" else "partial"

    return {
        "id": _new_id(),
        "evidenceId": _new_id(),
        "disputeId": dispute["disputeId"],
        "type": "receipt",
        "evidenceType": "receipt",
        "sourceSystem": "document_intelligence",
        "title": f"Receipt — {dispute['merchantName']}",
        "content": {
            "documentType": doc_type,
            "merchantName": dispute["merchantName"],
            "amount": dispute["transactionAmount"],
            "date": dispute["transactionDate"],
            "extractionConfidence": round(random.uniform(0.85, 0.99), 3),
            "fields_extracted": random.randint(8, 20),
            "ocr_quality": ocr_quality,
        },
        "contentRef": f"blob://disputes-data/{dispute['disputeId']}/{doc_type}_{_new_id()[:8]}.pdf",
        "completeness": completeness,
        "retrievedAt": dispute["createdAt"],
        "blobUrl": f"https://storage.blob.core.windows.net/evidence/{dispute['disputeId']}/receipt_{_new_id()[:8]}.pdf",
        "extractedAt": dispute["createdAt"],
    }


# ---------------------------------------------------------------------------
# Timeline Event Generator
# ---------------------------------------------------------------------------

def generate_timeline(dispute: dict) -> list[dict]:
    """Generate a realistic timeline of events for a dispute."""
    events = []
    dispute_id = dispute["disputeId"]
    created = datetime.fromisoformat(dispute["createdAt"])
    status = dispute["status"]

    # All disputes start with intake
    events.append({
        "id": _new_id(),
        "eventId": _new_id(),
        "disputeId": dispute_id,
        "eventType": "status_change",
        "actor": "system",
        "detail": "Dispute created — intake initiated",
        "data": {"fromStatus": None, "toStatus": "intake", "networkCode": dispute["networkCode"]},
        "occurredAt": created.isoformat(),
    })

    if status == "intake":
        return events

    # Evidence gathering
    gather_time = created + timedelta(minutes=random.randint(2, 30))
    events.append({
        "id": _new_id(),
        "eventId": _new_id(),
        "disputeId": dispute_id,
        "eventType": "status_change",
        "actor": "orchestrator_agent",
        "detail": "Evidence gathering initiated across source systems",
        "data": {"fromStatus": "intake", "toStatus": "evidence_gathering", "systemsQueried": random.randint(3, 8)},
        "occurredAt": gather_time.isoformat(),
    })

    # Evidence retrieved events
    evidence_count = random.randint(3, 7)
    for i in range(evidence_count):
        ev_time = gather_time + timedelta(minutes=random.randint(1, 15) * (i + 1))
        events.append({
            "id": _new_id(),
            "eventId": _new_id(),
            "disputeId": dispute_id,
            "eventType": "evidence_retrieved",
            "actor": "evidence_agent",
            "detail": f"Evidence item {i+1}/{evidence_count} retrieved",
            "data": {"sourceSystem": random.choice(["payment_processor", "oms_erp", "logistics", "crm", "fraud_engine", "document_intelligence"])},
            "occurredAt": ev_time.isoformat(),
        })

    if status == "evidence_gathering":
        return events

    # AI Drafting
    draft_time = gather_time + timedelta(minutes=random.randint(20, 60))
    events.append({
        "id": _new_id(),
        "eventId": _new_id(),
        "disputeId": dispute_id,
        "eventType": "status_change",
        "actor": "maker_agent",
        "detail": "Rebuttal draft generation started",
        "data": {"fromStatus": "evidence_gathering", "toStatus": "ai_drafting"},
        "occurredAt": draft_time.isoformat(),
    })

    # Checker validation
    check_time = draft_time + timedelta(minutes=random.randint(5, 20))
    checker_pass = random.random() > 0.2  # 80% pass on first try
    if not checker_pass:
        events.append({
            "id": _new_id(),
            "eventId": _new_id(),
            "disputeId": dispute_id,
            "eventType": "checker_retry",
            "actor": "checker_agent",
            "detail": "Groundedness check failed — retrying maker draft",
            "data": {"attempt": 1, "reason": "ungrounded_claim_detected"},
            "occurredAt": check_time.isoformat(),
        })
        check_time += timedelta(minutes=random.randint(5, 15))

    events.append({
        "id": _new_id(),
        "eventId": _new_id(),
        "disputeId": dispute_id,
        "eventType": "checker_passed",
        "actor": "checker_agent",
        "detail": "Groundedness validation passed",
        "data": {"attempt": 2 if not checker_pass else 1, "groundednessScore": round(random.uniform(0.85, 0.99), 3)},
        "occurredAt": check_time.isoformat(),
    })

    if status == "ai_drafting":
        return events

    # Pending review
    review_time = check_time + timedelta(minutes=random.randint(5, 30))
    analyst = random.choice(ANALYSTS)
    events.append({
        "id": _new_id(),
        "eventId": _new_id(),
        "disputeId": dispute_id,
        "eventType": "status_change",
        "actor": "system",
        "detail": f"Case assigned to {analyst['name']} for human review",
        "data": {"fromStatus": "ai_drafting", "toStatus": "pending_review", "assignedAnalyst": analyst["id"]},
        "occurredAt": review_time.isoformat(),
    })

    if status == "pending_review":
        return events

    # Outcome — depends on final status
    outcome_time = review_time + timedelta(hours=random.randint(1, 48))

    if status == "escalated":
        events.append({
            "id": _new_id(),
            "eventId": _new_id(),
            "disputeId": dispute_id,
            "eventType": "status_change",
            "actor": "system",
            "detail": "Review timeout — escalated to supervisor queue",
            "data": {"fromStatus": "pending_review", "toStatus": "escalated", "reason": "sla_timeout"},
            "occurredAt": outcome_time.isoformat(),
        })
        return events

    if status == "expired":
        events.append({
            "id": _new_id(),
            "eventId": _new_id(),
            "disputeId": dispute_id,
            "eventType": "status_change",
            "actor": "system",
            "detail": "Network deadline passed — dispute expired without submission",
            "data": {"fromStatus": "pending_review", "toStatus": "expired", "reason": "deadline_exceeded"},
            "occurredAt": outcome_time.isoformat(),
        })
        return events

    if status == "denied":
        events.append({
            "id": _new_id(),
            "eventId": _new_id(),
            "disputeId": dispute_id,
            "eventType": "status_change",
            "actor": analyst["id"],
            "detail": f"Dispute denied by {analyst['name']} — insufficient evidence",
            "data": {"fromStatus": "pending_review", "toStatus": "denied", "reason": random.choice(["insufficient_evidence", "friendly_fraud_confirmed", "policy_exclusion"])},
            "occurredAt": outcome_time.isoformat(),
        })
        return events

    # Approved
    events.append({
        "id": _new_id(),
        "eventId": _new_id(),
        "disputeId": dispute_id,
        "eventType": "status_change",
        "actor": analyst["id"],
        "detail": f"Dispute approved by {analyst['name']}",
        "data": {"fromStatus": "pending_review", "toStatus": "approved"},
        "occurredAt": outcome_time.isoformat(),
    })

    if status == "approved":
        return events

    # Submitted
    submit_time = outcome_time + timedelta(minutes=random.randint(5, 60))
    events.append({
        "id": _new_id(),
        "eventId": _new_id(),
        "disputeId": dispute_id,
        "eventType": "status_change",
        "actor": "system",
        "detail": f"Evidence package submitted to {dispute['networkCode'].title()} network",
        "data": {"fromStatus": "approved", "toStatus": "submitted", "networkCode": dispute["networkCode"]},
        "occurredAt": submit_time.isoformat(),
    })

    if status == "submitted":
        return events

    # Closed (terminal with resolvedAt)
    close_time = submit_time + timedelta(days=random.randint(5, 30))
    outcome = random.choice(["won", "lost", "partial_credit"])
    events.append({
        "id": _new_id(),
        "eventId": _new_id(),
        "disputeId": dispute_id,
        "eventType": "status_change",
        "actor": "system",
        "detail": f"Case closed — outcome: {outcome}",
        "data": {"fromStatus": "submitted", "toStatus": "closed", "outcome": outcome, "creditAmount": dispute["transactionAmount"] if outcome == "won" else dispute["transactionAmount"] * 0.5 if outcome == "partial_credit" else 0},
        "occurredAt": close_time.isoformat(),
    })

    return events


# ---------------------------------------------------------------------------
# Main Generator
# ---------------------------------------------------------------------------

def generate_dispute(network: str = None) -> dict:
    """Generate a single realistic dispute case aligned with case.schema.json."""
    if network is None:
        network = random.choices(
            ["visa", "mastercard", "amex", "discover"],
            weights=[0.40, 0.30, 0.20, 0.10],  # Visa dominant market share
            k=1,
        )[0]

    reason = random.choice(REASON_CODES[network])
    cardholder = random.choice(CARDHOLDERS)
    merchant = random.choice(MERCHANTS)
    status = _weighted_choice(STATUS_DISTRIBUTION)

    transaction_date = _random_date(90, 5)
    created_at = transaction_date + timedelta(days=random.randint(1, 10))
    deadline_date = created_at + timedelta(days=DEADLINE_DAYS[network])
    days_remaining = max(0, (deadline_date - datetime.now(timezone.utc)).days)

    # Win probability correlates with evidence strength and fraud category
    if reason["category"] == "fraud":
        win_prob = round(random.uniform(0.55, 0.90), 2)
    elif reason["category"] == "consumer_dispute":
        win_prob = round(random.uniform(0.35, 0.75), 2)
    else:
        win_prob = round(random.uniform(0.40, 0.80), 2)

    # Risk score → risk level (aligned with schema enum)
    risk_base = 30 if reason["category"] == "fraud" else 15
    risk_score = min(99, risk_base + random.randint(0, 50))
    risk_level = _risk_level(risk_score)

    dispute_id = _new_id()

    # Assign analyst for cases past evidence_gathering stage
    assigned_analyst = None
    if status in ("pending_review", "approved", "submitted", "denied", "escalated", "closed"):
        assigned_analyst = random.choice(ANALYSTS)["id"]

    # Evidence collected count (for checklist generation)
    evidence_collected_count = random.randint(3, len(reason["evidence_required"]) + 3) if status != "intake" else 0

    # Generate reason code checklist
    reason_code_checklist = generate_reason_code_checklist(reason, evidence_collected_count)

    # Generate structured evidence gaps
    evidence_gaps = generate_evidence_gaps(reason, status, reason_code_checklist)

    # Updated timestamp
    updated_at = created_at + timedelta(hours=random.randint(1, 720))

    # Resolved timestamp for closed cases
    resolved_at = None
    if status == "closed":
        resolved_at = (updated_at + timedelta(days=random.randint(5, 30))).isoformat()

    dispute = {
        # Cosmos DB & canonical identifiers
        "id": dispute_id,
        "caseId": dispute_id,
        "disputeId": dispute_id,
        "orchestrationId": dispute_id,
        "disputeRef": _network_dispute_ref(network),
        # Network & reason (dual naming for backward compat + schema compliance)
        "networkCode": network,  # Cosmos partition key
        "cardNetwork": network,  # Schema canonical name
        "reasonCode": reason["code"],
        "reasonCodeLabel": reason["description"],
        "reasonDescription": reason["description"],  # backward compat
        "reasonCategory": reason["category"],
        "reasonCodeChecklist": reason_code_checklist,
        # Status
        "status": status,
        # Cardholder
        "cardholderName": cardholder["name"],
        "cardholderCity": cardholder["city"],
        "cardholderState": cardholder["state"],
        "cardLastFour": _card_last_four(),
        # Transaction
        "transactionAmount": _random_amount(),
        "transactionCurrency": "USD",
        "transactionDate": transaction_date.isoformat(),
        # Merchant
        "merchantName": merchant["name"],
        "merchantCategory": merchant["category"],
        "merchantMcc": merchant["mcc"],
        # Deadline (structured per schema)
        "deadline": {
            "network": network.title(),
            "dueDate": deadline_date.strftime("%Y-%m-%d"),
            "daysRemaining": days_remaining,
        },
        "deadlineUtc": deadline_date.isoformat(),  # backward compat
        "daysUntilDeadline": days_remaining,  # backward compat
        # Risk & probability
        "winProbability": win_prob if status not in ("intake", "evidence_gathering") else None,
        "riskLevel": risk_level,
        "riskScore": risk_score,  # backward compat (operational analytics)
        # Evidence tracking
        "evidenceGaps": evidence_gaps,
        "assignedAnalyst": assigned_analyst,
        "evidenceRequired": reason["evidence_required"],
        "evidenceCollected": evidence_collected_count,
        # Rebuttal (placeholder — enriched after evidence generation)
        "rebuttalDraft": None,
        # Submission
        "submissionPackageUrl": f"https://storage.blob.core.windows.net/submissions/{dispute_id}/package.pdf" if status in ("submitted", "closed") else None,
        # Metadata
        "metadata": {
            "source": "synthetic_seed_data",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "version": "2.0",
        },
        # Timestamps
        "createdAt": created_at.isoformat(),
        "updatedAt": updated_at.isoformat(),
        "resolvedAt": resolved_at,
    }

    return dispute


def generate_evidence_for_dispute(dispute: dict) -> list[dict]:
    """Generate a realistic set of evidence items for a dispute."""
    evidence = []

    # Always include transaction record
    evidence.append(generate_transaction_evidence(dispute))

    # Based on reason category, add relevant evidence types
    category = dispute.get("reasonCategory", "consumer_dispute")

    if category == "consumer_dispute":
        evidence.append(generate_order_evidence(dispute))
        evidence.append(generate_shipping_evidence(dispute))
        evidence.append(generate_communication_evidence(dispute))
        if random.random() > 0.3:
            evidence.append(generate_receipt_evidence(dispute))

    elif category == "fraud":
        evidence.append(generate_fraud_signal_evidence(dispute))
        if random.random() > 0.4:
            evidence.append(generate_communication_evidence(dispute))
        if random.random() > 0.5:
            evidence.append(generate_receipt_evidence(dispute))

    elif category == "processing_error":
        evidence.append(generate_receipt_evidence(dispute))
        if random.random() > 0.5:
            evidence.append(generate_order_evidence(dispute))

    elif category == "authorization":
        evidence.append(generate_fraud_signal_evidence(dispute))

    # Randomly add extra evidence items
    if random.random() > 0.6:
        evidence.append(generate_communication_evidence(dispute))
    if random.random() > 0.7:
        evidence.append(generate_fraud_signal_evidence(dispute))

    return evidence


def generate_dataset(count: int = 200) -> tuple[list[dict], list[dict], list[dict]]:
    """Generate a complete dataset with disputes, evidence, and timeline events."""
    disputes = []
    all_evidence = []
    all_timeline = []

    for _ in range(count):
        dispute = generate_dispute()
        disputes.append(dispute)

        # Generate evidence for non-intake disputes
        if dispute["status"] != "intake":
            evidence = generate_evidence_for_dispute(dispute)
            all_evidence.extend(evidence)

            # Enrich dispute with rebuttal draft referencing actual evidence IDs
            evidence_ids = [e["evidenceId"] for e in evidence]
            dispute["rebuttalDraft"] = generate_rebuttal_draft(dispute, evidence_ids)
        else:
            dispute["rebuttalDraft"] = None

        # Generate timeline
        timeline = generate_timeline(dispute)
        all_timeline.extend(timeline)

    return disputes, all_evidence, all_timeline


def save_dataset(output_dir: str, count: int = 200):
    """Generate and save the dataset to JSON files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"Generating {count} dispute cases...")
    disputes, evidence, timeline = generate_dataset(count)

    # Save to JSON files
    disputes_file = output_path / "disputes.json"
    evidence_file = output_path / "evidence.json"
    timeline_file = output_path / "timeline.json"

    with open(disputes_file, "w") as f:
        json.dump(disputes, f, indent=2, default=str)

    with open(evidence_file, "w") as f:
        json.dump(evidence, f, indent=2, default=str)

    with open(timeline_file, "w") as f:
        json.dump(timeline, f, indent=2, default=str)

    # Summary statistics
    print(f"\n{'='*60}")
    print(f" Seed Data Generated Successfully")
    print(f"{'='*60}")
    print(f" Disputes:       {len(disputes):>6}")
    print(f" Evidence items: {len(evidence):>6}")
    print(f" Timeline events:{len(timeline):>6}")
    print(f"{'='*60}")
    print(f"\n Network distribution:")
    for net in ["visa", "mastercard", "amex", "discover"]:
        n = sum(1 for d in disputes if d["networkCode"] == net)
        print(f"   {net.title():12} {n:>4} ({n/len(disputes)*100:.0f}%)")

    print(f"\n Status distribution:")
    for status, _ in STATUS_DISTRIBUTION:
        n = sum(1 for d in disputes if d["status"] == status)
        print(f"   {status:12} {n:>4} ({n/len(disputes)*100:.0f}%)")

    print(f"\n Category distribution:")
    categories = set(d.get("reasonCategory", "unknown") for d in disputes)
    for cat in sorted(categories):
        n = sum(1 for d in disputes if d.get("reasonCategory") == cat)
        print(f"   {cat:18} {n:>4} ({n/len(disputes)*100:.0f}%)")

    print(f"\n Amounts:")
    amounts = [d["transactionAmount"] for d in disputes]
    print(f"   Min:    ${min(amounts):>10,.2f}")
    print(f"   Max:    ${max(amounts):>10,.2f}")
    print(f"   Avg:    ${sum(amounts)/len(amounts):>10,.2f}")
    print(f"   Total:  ${sum(amounts):>10,.2f}")

    print(f"\n Output files:")
    print(f"   {disputes_file}")
    print(f"   {evidence_file}")
    print(f"   {timeline_file}")

    # Also save a summary/stats file
    stats = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "disputes": len(disputes),
            "evidence": len(evidence),
            "timeline": len(timeline),
        },
        "networks": {net: sum(1 for d in disputes if d["networkCode"] == net) for net in ["visa", "mastercard", "amex", "discover"]},
        "statuses": {s: sum(1 for d in disputes if d["status"] == s) for s, _ in STATUS_DISTRIBUTION},
        "categories": {cat: sum(1 for d in disputes if d.get("reasonCategory") == cat) for cat in sorted(categories)},
        "amounts": {"min": min(amounts), "max": max(amounts), "avg": round(sum(amounts)/len(amounts), 2), "total": round(sum(amounts), 2)},
    }
    stats_file = output_path / "stats.json"
    with open(stats_file, "w") as f:
        json.dump(stats, f, indent=2)

    return disputes, evidence, timeline


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic dispute seed data")
    parser.add_argument("--count", type=int, default=200, help="Number of disputes to generate (default: 200)")
    parser.add_argument("--output-dir", type=str, default="./data/seed", help="Output directory (default: ./data/seed)")
    args = parser.parse_args()

    random.seed(42)  # Reproducible output
    save_dataset(args.output_dir, args.count)
