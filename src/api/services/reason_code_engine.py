"""
Reason Code Engine — Card Network Dispute Requirements

Centralized runtime service for querying reason codes, required evidence,
response deadlines, and win-rate benchmarks across all 4 major card networks
(Visa, Mastercard, Amex, Discover).

Usage:
    from services.reason_code_engine import (
        get_reason_codes_for_network,
        get_reason_code_detail,
        get_evidence_checklist,
        get_deadline_days,
        identify_evidence_gaps,
    )
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Reason Code Registry — All 4 Networks
# ---------------------------------------------------------------------------

REASON_CODES: dict[str, list[dict[str, Any]]] = {
    "visa": [
        {
            "code": "10.1",
            "description": "EMV Liability Shift Counterfeit Fraud",
            "category": "fraud",
            "win_rate": 0.62,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "transaction_receipt", "label": "Transaction Receipt", "type": "transaction", "priority": "required"},
                {"id": "emv_chip_data", "label": "EMV Chip Transaction Data", "type": "fraud_signal", "priority": "required"},
                {"id": "authorization_log", "label": "Authorization Log", "type": "transaction", "priority": "required"},
            ],
        },
        {
            "code": "10.4",
            "description": "Other Fraud — Card Absent Environment",
            "category": "fraud",
            "win_rate": 0.55,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "avs_cvv_results", "label": "AVS/CVV Verification Results", "type": "fraud_signal", "priority": "required"},
                {"id": "ip_geolocation", "label": "IP Geolocation Data", "type": "fraud_signal", "priority": "required"},
                {"id": "device_fingerprint", "label": "Device Fingerprint", "type": "fraud_signal", "priority": "recommended"},
                {"id": "3ds_authentication", "label": "3-D Secure Authentication Proof", "type": "fraud_signal", "priority": "recommended"},
            ],
        },
        {
            "code": "11.1",
            "description": "Card Recovery Bulletin",
            "category": "authorization",
            "win_rate": 0.70,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "authorization_log", "label": "Authorization Log", "type": "transaction", "priority": "required"},
                {"id": "card_recovery_bulletin_date", "label": "Card Recovery Bulletin Date Verification", "type": "transaction", "priority": "required"},
            ],
        },
        {
            "code": "12.5",
            "description": "Incorrect Amount",
            "category": "processing_error",
            "win_rate": 0.75,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "transaction_receipt", "label": "Transaction Receipt", "type": "receipt", "priority": "required"},
                {"id": "signed_receipt", "label": "Signed Receipt", "type": "receipt", "priority": "required"},
                {"id": "terminal_data", "label": "Terminal Transaction Data", "type": "transaction", "priority": "recommended"},
            ],
        },
        {
            "code": "12.6",
            "description": "Duplicate Processing",
            "category": "processing_error",
            "win_rate": 0.80,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "transaction_logs", "label": "Transaction Logs (both charges)", "type": "transaction", "priority": "required"},
                {"id": "batch_settlement_records", "label": "Batch Settlement Records", "type": "transaction", "priority": "required"},
                {"id": "authorization_log", "label": "Authorization Log", "type": "transaction", "priority": "required"},
            ],
        },
        {
            "code": "13.1",
            "description": "Merchandise/Services Not Received",
            "category": "consumer_dispute",
            "win_rate": 0.72,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "shipping_confirmation", "label": "Shipping Confirmation", "type": "shipping", "priority": "required"},
                {"id": "delivery_proof", "label": "Proof of Delivery", "type": "shipping", "priority": "required"},
                {"id": "tracking_number", "label": "Carrier Tracking Number", "type": "shipping", "priority": "required"},
                {"id": "signed_delivery", "label": "Signed Delivery Confirmation", "type": "shipping", "priority": "recommended"},
            ],
        },
        {
            "code": "13.2",
            "description": "Cancelled Recurring Transaction",
            "category": "consumer_dispute",
            "win_rate": 0.60,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "cancellation_policy", "label": "Cancellation Policy", "type": "contract", "priority": "required"},
                {"id": "terms_of_service", "label": "Terms of Service (signed)", "type": "contract", "priority": "required"},
                {"id": "communication_records", "label": "Communication Records", "type": "communication", "priority": "recommended"},
            ],
        },
        {
            "code": "13.3",
            "description": "Not as Described or Defective",
            "category": "consumer_dispute",
            "win_rate": 0.58,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "product_description", "label": "Original Product Description/Listing", "type": "order", "priority": "required"},
                {"id": "photos", "label": "Product Photos (as shipped)", "type": "photo", "priority": "required"},
                {"id": "return_policy", "label": "Return Policy", "type": "contract", "priority": "recommended"},
                {"id": "communication_records", "label": "Customer Communication Records", "type": "communication", "priority": "recommended"},
            ],
        },
        {
            "code": "13.6",
            "description": "Credit Not Processed",
            "category": "consumer_dispute",
            "win_rate": 0.65,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "refund_policy", "label": "Refund Policy", "type": "contract", "priority": "required"},
                {"id": "return_receipt", "label": "Return Receipt", "type": "receipt", "priority": "required"},
                {"id": "credit_voucher", "label": "Credit/Refund Voucher", "type": "transaction", "priority": "required"},
                {"id": "communication_records", "label": "Communication Records", "type": "communication", "priority": "recommended"},
            ],
        },
        {
            "code": "13.7",
            "description": "Cancelled Merchandise/Services",
            "category": "consumer_dispute",
            "win_rate": 0.63,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "cancellation_policy", "label": "Cancellation Policy", "type": "contract", "priority": "required"},
                {"id": "terms_of_service", "label": "Terms of Service", "type": "contract", "priority": "required"},
                {"id": "proof_of_service_delivery", "label": "Proof of Service Delivery", "type": "order", "priority": "required"},
            ],
        },
    ],
    "mastercard": [
        {
            "code": "4834",
            "description": "Point-of-Interaction Error",
            "category": "processing_error",
            "win_rate": 0.70,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "transaction_receipt", "label": "Transaction Receipt", "type": "receipt", "priority": "required"},
                {"id": "terminal_data", "label": "Terminal Transaction Data", "type": "transaction", "priority": "required"},
                {"id": "batch_records", "label": "Batch Settlement Records", "type": "transaction", "priority": "recommended"},
            ],
        },
        {
            "code": "4837",
            "description": "No Cardholder Authorization",
            "category": "fraud",
            "win_rate": 0.68,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "signed_receipt", "label": "Signed Receipt/Invoice", "type": "receipt", "priority": "required"},
                {"id": "authorization_log", "label": "Authorization Log", "type": "transaction", "priority": "required"},
                {"id": "cvv_avs_response", "label": "CVV/AVS Response Data", "type": "fraud_signal", "priority": "required"},
            ],
        },
        {
            "code": "4840",
            "description": "Fraudulent Processing of Transactions",
            "category": "fraud",
            "win_rate": 0.50,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "authorization_log", "label": "Authorization Log", "type": "transaction", "priority": "required"},
                {"id": "merchant_agreement", "label": "Merchant Processing Agreement", "type": "contract", "priority": "required"},
                {"id": "processing_records", "label": "Transaction Processing Records", "type": "transaction", "priority": "required"},
            ],
        },
        {
            "code": "4853",
            "description": "Cardholder Dispute — Goods/Services",
            "category": "consumer_dispute",
            "win_rate": 0.52,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "shipping_proof", "label": "Shipping Proof", "type": "shipping", "priority": "required"},
                {"id": "delivery_confirmation", "label": "Delivery Confirmation", "type": "shipping", "priority": "required"},
                {"id": "product_description", "label": "Product Description", "type": "order", "priority": "recommended"},
                {"id": "communication_records", "label": "Communication Records", "type": "communication", "priority": "recommended"},
            ],
        },
        {
            "code": "4855",
            "description": "Goods or Services Not Provided",
            "category": "consumer_dispute",
            "win_rate": 0.65,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "proof_of_delivery", "label": "Proof of Delivery", "type": "shipping", "priority": "required"},
                {"id": "tracking_info", "label": "Carrier Tracking Information", "type": "shipping", "priority": "required"},
                {"id": "service_completion_record", "label": "Service Completion Record", "type": "order", "priority": "required"},
            ],
        },
        {
            "code": "4859",
            "description": "Addendum, No-show, or ATM Dispute",
            "category": "consumer_dispute",
            "win_rate": 0.60,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "reservation_confirmation", "label": "Reservation Confirmation", "type": "order", "priority": "required"},
                {"id": "cancellation_policy", "label": "Cancellation/No-Show Policy", "type": "contract", "priority": "required"},
                {"id": "no_show_documentation", "label": "No-Show Documentation", "type": "order", "priority": "recommended"},
            ],
        },
        {
            "code": "4863",
            "description": "Cardholder Does Not Recognize",
            "category": "fraud",
            "win_rate": 0.55,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "transaction_receipt", "label": "Transaction Receipt", "type": "receipt", "priority": "required"},
                {"id": "authorization_log", "label": "Authorization Log", "type": "transaction", "priority": "required"},
                {"id": "merchant_descriptor_evidence", "label": "Merchant Descriptor Evidence", "type": "transaction", "priority": "required"},
            ],
        },
        {
            "code": "4871",
            "description": "Chip/PIN Liability Shift",
            "category": "fraud",
            "win_rate": 0.60,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "emv_data", "label": "EMV Chip Transaction Data", "type": "fraud_signal", "priority": "required"},
                {"id": "terminal_capability", "label": "Terminal EMV Capability Proof", "type": "transaction", "priority": "required"},
                {"id": "authorization_log", "label": "Authorization Log", "type": "transaction", "priority": "required"},
            ],
        },
    ],
    "amex": [
        {
            "code": "C02",
            "description": "Credit Not Processed",
            "category": "consumer_dispute",
            "win_rate": 0.65,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "refund_policy", "label": "Refund Policy", "type": "contract", "priority": "required"},
                {"id": "credit_voucher", "label": "Credit/Refund Voucher", "type": "transaction", "priority": "required"},
                {"id": "communication_records", "label": "Communication Records", "type": "communication", "priority": "recommended"},
            ],
        },
        {
            "code": "C04",
            "description": "Goods/Services Not Received",
            "category": "consumer_dispute",
            "win_rate": 0.70,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "proof_of_delivery", "label": "Proof of Delivery", "type": "shipping", "priority": "required"},
                {"id": "tracking_number", "label": "Carrier Tracking Number", "type": "shipping", "priority": "required"},
                {"id": "shipping_confirmation", "label": "Shipping Confirmation", "type": "shipping", "priority": "required"},
            ],
        },
        {
            "code": "C05",
            "description": "Goods/Services Cancelled",
            "category": "consumer_dispute",
            "win_rate": 0.62,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "cancellation_policy", "label": "Cancellation Policy", "type": "contract", "priority": "required"},
                {"id": "terms_agreement", "label": "Terms Agreement (signed)", "type": "contract", "priority": "required"},
                {"id": "communication_records", "label": "Communication Records", "type": "communication", "priority": "recommended"},
            ],
        },
        {
            "code": "C08",
            "description": "Goods/Services Not as Described",
            "category": "consumer_dispute",
            "win_rate": 0.55,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "product_listing", "label": "Original Product Listing", "type": "order", "priority": "required"},
                {"id": "photos", "label": "Product Photos", "type": "photo", "priority": "required"},
                {"id": "communication_records", "label": "Communication Records", "type": "communication", "priority": "recommended"},
                {"id": "return_policy", "label": "Return Policy", "type": "contract", "priority": "recommended"},
            ],
        },
        {
            "code": "C14",
            "description": "Paid by Other Means",
            "category": "processing_error",
            "win_rate": 0.78,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "alternative_payment_proof", "label": "Alternative Payment Proof", "type": "transaction", "priority": "required"},
                {"id": "transaction_records", "label": "Transaction Records", "type": "transaction", "priority": "required"},
            ],
        },
        {
            "code": "C18",
            "description": "Cancel of Recurring Billing",
            "category": "consumer_dispute",
            "win_rate": 0.58,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "billing_agreement", "label": "Billing Agreement", "type": "contract", "priority": "required"},
                {"id": "cancellation_request", "label": "Cancellation Request Evidence", "type": "communication", "priority": "required"},
                {"id": "processing_records", "label": "Processing Records", "type": "transaction", "priority": "recommended"},
            ],
        },
        {
            "code": "F10",
            "description": "Missing Imprint",
            "category": "fraud",
            "win_rate": 0.72,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "signed_receipt", "label": "Signed Receipt", "type": "receipt", "priority": "required"},
                {"id": "imprint_copy", "label": "Card Imprint Copy", "type": "receipt", "priority": "required"},
                {"id": "authorization_log", "label": "Authorization Log", "type": "transaction", "priority": "required"},
            ],
        },
        {
            "code": "F14",
            "description": "Missing Signature",
            "category": "fraud",
            "win_rate": 0.70,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "signed_receipt", "label": "Signed Receipt", "type": "receipt", "priority": "required"},
                {"id": "signature_comparison", "label": "Signature Comparison", "type": "receipt", "priority": "required"},
                {"id": "authorization_log", "label": "Authorization Log", "type": "transaction", "priority": "required"},
            ],
        },
        {
            "code": "F24",
            "description": "No Cardmember Authorization",
            "category": "fraud",
            "win_rate": 0.50,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "authorization_log", "label": "Authorization Log", "type": "transaction", "priority": "required"},
                {"id": "fraud_investigation_report", "label": "Fraud Investigation Report", "type": "fraud_signal", "priority": "required"},
                {"id": "ip_data", "label": "IP/Device Data", "type": "fraud_signal", "priority": "recommended"},
            ],
        },
        {
            "code": "F29",
            "description": "Card Not Present",
            "category": "fraud",
            "win_rate": 0.52,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "avs_cvv_results", "label": "AVS/CVV Verification Results", "type": "fraud_signal", "priority": "required"},
                {"id": "3ds_authentication", "label": "3-D Secure Authentication", "type": "fraud_signal", "priority": "required"},
                {"id": "ip_geolocation", "label": "IP Geolocation Data", "type": "fraud_signal", "priority": "recommended"},
                {"id": "device_fingerprint", "label": "Device Fingerprint", "type": "fraud_signal", "priority": "recommended"},
            ],
        },
    ],
    "discover": [
        {
            "code": "AA",
            "description": "Cardholder Does Not Recognize",
            "category": "fraud",
            "win_rate": 0.55,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "transaction_receipt", "label": "Transaction Receipt", "type": "receipt", "priority": "required"},
                {"id": "authorization_log", "label": "Authorization Log", "type": "transaction", "priority": "required"},
                {"id": "merchant_descriptor", "label": "Merchant Descriptor Evidence", "type": "transaction", "priority": "required"},
            ],
        },
        {
            "code": "AP",
            "description": "Cancelled Recurring Transaction",
            "category": "consumer_dispute",
            "win_rate": 0.60,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "billing_agreement", "label": "Billing Agreement", "type": "contract", "priority": "required"},
                {"id": "cancellation_confirmation", "label": "Cancellation Confirmation", "type": "communication", "priority": "required"},
                {"id": "processing_records", "label": "Processing Records", "type": "transaction", "priority": "recommended"},
            ],
        },
        {
            "code": "AW",
            "description": "Altered Amount",
            "category": "processing_error",
            "win_rate": 0.75,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "original_receipt", "label": "Original Transaction Receipt", "type": "receipt", "priority": "required"},
                {"id": "terminal_data", "label": "Terminal Data", "type": "transaction", "priority": "required"},
                {"id": "authorization_log", "label": "Authorization Log", "type": "transaction", "priority": "required"},
            ],
        },
        {
            "code": "CD",
            "description": "Credit/Debit Posted Incorrectly",
            "category": "processing_error",
            "win_rate": 0.78,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "transaction_records", "label": "Transaction Records", "type": "transaction", "priority": "required"},
                {"id": "batch_settlement", "label": "Batch Settlement Records", "type": "transaction", "priority": "required"},
                {"id": "authorization_log", "label": "Authorization Log", "type": "transaction", "priority": "required"},
            ],
        },
        {
            "code": "DP",
            "description": "Duplicate Processing",
            "category": "processing_error",
            "win_rate": 0.82,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "transaction_logs", "label": "Transaction Logs (both charges)", "type": "transaction", "priority": "required"},
                {"id": "batch_records", "label": "Batch Records", "type": "transaction", "priority": "required"},
                {"id": "settlement_data", "label": "Settlement Data", "type": "transaction", "priority": "required"},
            ],
        },
        {
            "code": "EX",
            "description": "Expired Card",
            "category": "authorization",
            "win_rate": 0.85,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "authorization_log", "label": "Authorization Log", "type": "transaction", "priority": "required"},
                {"id": "card_expiry_verification", "label": "Card Expiry Verification", "type": "transaction", "priority": "required"},
            ],
        },
        {
            "code": "NF",
            "description": "Non-receipt of Cash from ATM",
            "category": "consumer_dispute",
            "win_rate": 0.60,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "atm_journal", "label": "ATM Journal/Log", "type": "transaction", "priority": "required"},
                {"id": "surveillance_footage", "label": "Surveillance Footage", "type": "photo", "priority": "recommended"},
                {"id": "reconciliation_records", "label": "Cash Reconciliation Records", "type": "transaction", "priority": "required"},
            ],
        },
        {
            "code": "RG",
            "description": "Non-Receipt of Goods/Services",
            "category": "consumer_dispute",
            "win_rate": 0.68,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "shipping_proof", "label": "Shipping Proof", "type": "shipping", "priority": "required"},
                {"id": "delivery_confirmation", "label": "Delivery Confirmation", "type": "shipping", "priority": "required"},
                {"id": "tracking_info", "label": "Carrier Tracking Information", "type": "shipping", "priority": "required"},
            ],
        },
        {
            "code": "RM",
            "description": "Quality Discrepancy",
            "category": "consumer_dispute",
            "win_rate": 0.52,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "product_description", "label": "Product Description/Listing", "type": "order", "priority": "required"},
                {"id": "photos", "label": "Product Photos", "type": "photo", "priority": "required"},
                {"id": "communication_records", "label": "Communication Records", "type": "communication", "priority": "recommended"},
                {"id": "return_policy", "label": "Return Policy", "type": "contract", "priority": "recommended"},
            ],
        },
        {
            "code": "UA",
            "description": "Fraud — Card Present",
            "category": "fraud",
            "win_rate": 0.58,
            "time_limit_days": 120,
            "evidence_required": [
                {"id": "signed_receipt", "label": "Signed Receipt", "type": "receipt", "priority": "required"},
                {"id": "emv_chip_data", "label": "EMV Chip Data", "type": "fraud_signal", "priority": "required"},
                {"id": "surveillance_footage", "label": "Surveillance Footage", "type": "photo", "priority": "recommended"},
            ],
        },
    ],
}

# Network-level response deadlines (calendar days from transaction date)
NETWORK_DEADLINES: dict[str, int] = {
    "visa": 30,
    "mastercard": 45,
    "amex": 20,
    "discover": 30,
}

# Category display labels
CATEGORY_LABELS: dict[str, str] = {
    "fraud": "Fraud",
    "consumer_dispute": "Consumer Dispute",
    "processing_error": "Processing Error",
    "authorization": "Authorization",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_supported_networks() -> list[str]:
    """Return list of supported card networks."""
    return list(REASON_CODES.keys())


def get_reason_codes_for_network(network: str) -> list[dict[str, Any]]:
    """
    Return all reason codes for a given network.

    Returns a list of code summaries (code, description, category, win_rate).
    Returns empty list for unknown networks.
    """
    network_lower = network.lower()
    codes = REASON_CODES.get(network_lower, [])
    return [
        {
            "code": rc["code"],
            "description": rc["description"],
            "category": rc["category"],
            "categoryLabel": CATEGORY_LABELS.get(rc["category"], rc["category"]),
            "winRate": rc["win_rate"],
            "evidenceCount": len(rc["evidence_required"]),
        }
        for rc in codes
    ]


def get_reason_code_detail(network: str, code: str) -> dict[str, Any] | None:
    """
    Return full detail for a specific reason code including evidence requirements.

    Args:
        network: Card network (visa, mastercard, amex, discover)
        code: Reason code (e.g. "13.1", "4837", "C08", "RG")

    Returns:
        Full reason code detail dict, or None if not found.
    """
    network_lower = network.lower()
    codes = REASON_CODES.get(network_lower, [])
    for rc in codes:
        if rc["code"] == code:
            return {
                "network": network_lower,
                "code": rc["code"],
                "description": rc["description"],
                "category": rc["category"],
                "categoryLabel": CATEGORY_LABELS.get(rc["category"], rc["category"]),
                "winRate": rc["win_rate"],
                "timeLimitDays": rc["time_limit_days"],
                "networkDeadlineDays": NETWORK_DEADLINES.get(network_lower, 30),
                "evidenceRequired": rc["evidence_required"],
            }
    return None


def get_evidence_checklist(network: str, code: str) -> list[dict[str, Any]]:
    """
    Return the evidence checklist for a specific reason code.

    Each item has: id, label, type, priority, gathered (always False initially).
    Returns empty list if code not found.
    """
    detail = get_reason_code_detail(network, code)
    if not detail:
        return []
    return [
        {**item, "gathered": False}
        for item in detail["evidenceRequired"]
    ]


def get_deadline_days(network: str) -> int:
    """Return the network-level response deadline in calendar days."""
    return NETWORK_DEADLINES.get(network.lower(), 30)


def identify_evidence_gaps(
    network: str,
    code: str,
    gathered_evidence_ids: list[str],
) -> dict[str, Any]:
    """
    Compare required evidence against what has been gathered.

    Args:
        network: Card network
        code: Reason code
        gathered_evidence_ids: List of evidence IDs that have been collected

    Returns:
        {
            "totalRequired": int,
            "totalGathered": int,
            "completionPct": float,
            "gaps": [...],          # Missing items
            "gathered": [...],      # Collected items
            "readyForRebuttal": bool,  # True if all required items gathered
        }
    """
    checklist = get_evidence_checklist(network, code)
    if not checklist:
        return {
            "totalRequired": 0,
            "totalGathered": 0,
            "completionPct": 0.0,
            "gaps": [],
            "gathered": [],
            "readyForRebuttal": False,
        }

    gathered_set = set(gathered_evidence_ids)
    gaps = []
    gathered = []

    for item in checklist:
        if item["id"] in gathered_set:
            gathered.append({**item, "gathered": True})
        else:
            gaps.append({**item, "gathered": False})

    required_items = [i for i in checklist if i["priority"] == "required"]
    required_gathered = [i for i in required_items if i["id"] in gathered_set]
    ready = len(required_gathered) == len(required_items)

    total = len(checklist)
    total_gathered = len(gathered)
    completion = (total_gathered / total * 100) if total > 0 else 0.0

    return {
        "totalRequired": total,
        "totalGathered": total_gathered,
        "completionPct": round(completion, 1),
        "gaps": gaps,
        "gathered": gathered,
        "readyForRebuttal": ready,
    }


def parse_reason_code_string(reason_code_str: str) -> tuple[str, str]:
    """
    Parse a combined reason code string like "Visa 13.1" or "MC 4837" into (network, code).

    Returns ("unknown", reason_code_str) if it can't be parsed.
    """
    if not reason_code_str:
        return ("unknown", "")

    rc = reason_code_str.strip()
    network_prefixes = {
        "visa": "visa",
        "mc": "mastercard",
        "mastercard": "mastercard",
        "amex": "amex",
        "discover": "discover",
    }

    for prefix, network in network_prefixes.items():
        if rc.lower().startswith(prefix + " "):
            code = rc[len(prefix) + 1:].strip()
            return (network, code)

    return ("unknown", rc)
