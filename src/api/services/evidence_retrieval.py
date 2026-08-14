"""
Mock Evidence Retrieval Service — All 4 Card Networks

Simulates retrieving evidence from merchant systems, payment processors, shipping
carriers, and fraud detection platforms. Returns representative evidence documents
for a given dispute case based on its reason code.

In production, this would be replaced by real integrations (e.g., Stripe Radar,
FedEx API, Salesforce CRM, etc.). The mock generates realistic-looking evidence
artifacts with proper metadata to exercise the full analyst workflow.

Usage:
    from services.evidence_retrieval import retrieve_evidence_for_dispute
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from services.reason_code_engine import (
    get_evidence_checklist,
    parse_reason_code_string,
)


# ---------------------------------------------------------------------------
# Mock Evidence Templates — Keyed by evidence_id
# ---------------------------------------------------------------------------

_EVIDENCE_TEMPLATES: dict[str, dict[str, Any]] = {
    # ── Transaction / Authorization evidence ──────────────────────────────
    "transaction_receipt": {
        "sourceSystem": "PaymentProcessor",
        "sourceLabel": "Payment Gateway",
        "documentType": "transaction",
        "title": "Transaction Receipt",
        "contentTemplate": {
            "authorizationCode": "AUTH-{auth_code}",
            "terminalId": "TRM-{terminal_id}",
            "merchantId": "MID-{merchant_id}",
            "transactionType": "Purchase",
            "responseCode": "00 — Approved",
            "cardEntryMode": "Chip",
            "batchNumber": "BTH-{batch}",
        },
    },
    "authorization_log": {
        "sourceSystem": "AuthorizationNetwork",
        "sourceLabel": "Network Authorization System",
        "documentType": "transaction",
        "title": "Authorization Log",
        "contentTemplate": {
            "authCode": "AUTH-{auth_code}",
            "requestTimestamp": "{tx_date}T14:23:01Z",
            "responseTimestamp": "{tx_date}T14:23:01.342Z",
            "responseCode": "00",
            "avsResult": "Y — Address and ZIP match",
            "cvvResult": "M — CVV Match",
            "networkReferenceId": "NRI-{ref_id}",
        },
    },
    "transaction_logs": {
        "sourceSystem": "PaymentProcessor",
        "sourceLabel": "Transaction Processing System",
        "documentType": "transaction",
        "title": "Transaction Logs",
        "contentTemplate": {
            "entries": [
                {"timestamp": "{tx_date}T10:15:22Z", "event": "Authorization Request", "amount": "${amount}", "status": "Approved"},
                {"timestamp": "{tx_date}T10:15:22.5Z", "event": "Authorization Response", "authCode": "AUTH-{auth_code}", "status": "Success"},
                {"timestamp": "{tx_date}T22:00:00Z", "event": "Batch Settlement", "batchId": "BTH-{batch}", "status": "Settled"},
            ],
        },
    },
    "batch_settlement_records": {
        "sourceSystem": "PaymentProcessor",
        "sourceLabel": "Settlement System",
        "documentType": "transaction",
        "title": "Batch Settlement Records",
        "contentTemplate": {
            "batchId": "BTH-{batch}",
            "settlementDate": "{settle_date}",
            "totalTransactions": 147,
            "totalAmount": "$42,891.33",
            "disputedTransactionIncluded": True,
            "acquirerReferenceNumber": "ARN-{ref_id}",
        },
    },
    "batch_records": {
        "sourceSystem": "PaymentProcessor",
        "sourceLabel": "Batch Processing System",
        "documentType": "transaction",
        "title": "Batch Records",
        "contentTemplate": {
            "batchId": "BTH-{batch}",
            "processedDate": "{settle_date}",
            "itemCount": 89,
            "status": "Settled",
        },
    },
    "terminal_data": {
        "sourceSystem": "POSSystem",
        "sourceLabel": "Point-of-Sale Terminal",
        "documentType": "transaction",
        "title": "Terminal Transaction Data",
        "contentTemplate": {
            "terminalId": "TRM-{terminal_id}",
            "terminalType": "Ingenico Lane/5000",
            "emvCapable": True,
            "contactlessEnabled": True,
            "entryMode": "ICC (Chip Insert)",
            "pinVerified": True,
            "kernelVersion": "EMV L2 v3.1",
        },
    },
    "transaction_records": {
        "sourceSystem": "PaymentProcessor",
        "sourceLabel": "Transaction Database",
        "documentType": "transaction",
        "title": "Transaction Records",
        "contentTemplate": {
            "transactionId": "TXN-{ref_id}",
            "amount": "${amount}",
            "currency": "USD",
            "status": "Settled",
            "merchantName": "{merchant}",
            "cardLast4": "{card_last4}",
        },
    },
    "processing_records": {
        "sourceSystem": "PaymentProcessor",
        "sourceLabel": "Processing System",
        "documentType": "transaction",
        "title": "Transaction Processing Records",
        "contentTemplate": {
            "processingDate": "{tx_date}",
            "acquirerBIN": "421345",
            "issuerBIN": "412789",
            "interchangeCategory": "Standard",
            "settlementAmount": "${amount}",
        },
    },
    "credit_voucher": {
        "sourceSystem": "PaymentProcessor",
        "sourceLabel": "Refund Processing",
        "documentType": "transaction",
        "title": "Credit/Refund Voucher",
        "contentTemplate": {
            "voucherId": "CRV-{ref_id}",
            "originalTransactionId": "TXN-{ref_id}",
            "creditAmount": "${amount}",
            "creditDate": "{settle_date}",
            "reason": "Customer refund request",
            "status": "Processed",
        },
    },
    "card_recovery_bulletin_date": {
        "sourceSystem": "CardNetwork",
        "sourceLabel": "Card Recovery Bulletin",
        "documentType": "transaction",
        "title": "Card Recovery Bulletin Date Verification",
        "contentTemplate": {
            "bulletinDate": "{tx_date}",
            "cardBIN": "4123xx",
            "listedSince": "{listed_date}",
            "reason": "Reported Lost/Stolen",
        },
    },
    "card_expiry_verification": {
        "sourceSystem": "CardNetwork",
        "sourceLabel": "Card Verification System",
        "documentType": "transaction",
        "title": "Card Expiry Verification",
        "contentTemplate": {
            "cardLast4": "{card_last4}",
            "expiryDate": "03/2024",
            "transactionDate": "{tx_date}",
            "cardExpiredAtTransactionTime": True,
        },
    },
    "settlement_data": {
        "sourceSystem": "PaymentProcessor",
        "sourceLabel": "Settlement System",
        "documentType": "transaction",
        "title": "Settlement Data",
        "contentTemplate": {
            "settlementId": "STL-{ref_id}",
            "settlementDate": "{settle_date}",
            "netAmount": "${amount}",
            "status": "Completed",
        },
    },
    "alternative_payment_proof": {
        "sourceSystem": "PaymentProcessor",
        "sourceLabel": "Alternative Payment Record",
        "documentType": "transaction",
        "title": "Alternative Payment Proof",
        "contentTemplate": {
            "alternativeMethod": "Wire Transfer",
            "alternativeRef": "WIRE-{ref_id}",
            "amount": "${amount}",
            "date": "{tx_date}",
            "matchesDispute": True,
        },
    },
    "merchant_descriptor": {
        "sourceSystem": "CardNetwork",
        "sourceLabel": "Merchant Registry",
        "documentType": "transaction",
        "title": "Merchant Descriptor Evidence",
        "contentTemplate": {
            "descriptorOnStatement": "{merchant}",
            "registeredDBA": "{merchant}",
            "merchantCategoryCode": "5732",
            "merchantCity": "San Francisco, CA",
            "merchantURL": "www.merchant-example.com",
        },
    },
    "merchant_descriptor_evidence": {
        "sourceSystem": "CardNetwork",
        "sourceLabel": "Merchant Registry",
        "documentType": "transaction",
        "title": "Merchant Descriptor Evidence",
        "contentTemplate": {
            "descriptorOnStatement": "{merchant}",
            "registeredDBA": "{merchant}",
            "mcc": "5732",
            "city": "San Francisco, CA",
        },
    },

    # ── Shipping / Delivery evidence ──────────────────────────────────────
    "shipping_confirmation": {
        "sourceSystem": "ShippingCarrier",
        "sourceLabel": "FedEx Ship Manager",
        "documentType": "shipping",
        "title": "Shipping Confirmation",
        "contentTemplate": {
            "carrier": "FedEx",
            "trackingNumber": "7489{tracking}",
            "shipDate": "{ship_date}",
            "origin": "Warehouse — Memphis, TN",
            "destination": "{cardholder_city}, {cardholder_state}",
            "service": "FedEx Ground",
            "weight": "2.4 lbs",
            "status": "Delivered",
        },
    },
    "delivery_proof": {
        "sourceSystem": "ShippingCarrier",
        "sourceLabel": "FedEx Delivery Confirmation",
        "documentType": "shipping",
        "title": "Proof of Delivery",
        "contentTemplate": {
            "carrier": "FedEx",
            "trackingNumber": "7489{tracking}",
            "deliveryDate": "{delivery_date}",
            "deliveryTime": "14:32 ET",
            "signedBy": "FRONT DOOR",
            "deliveryLocation": "{cardholder_city}, {cardholder_state}",
            "photoProof": True,
            "gpsCoordinates": "33.7490° N, 84.3880° W",
        },
    },
    "tracking_number": {
        "sourceSystem": "ShippingCarrier",
        "sourceLabel": "Carrier Tracking System",
        "documentType": "shipping",
        "title": "Carrier Tracking Number",
        "contentTemplate": {
            "carrier": "FedEx",
            "trackingNumber": "7489{tracking}",
            "events": [
                {"date": "{ship_date}", "event": "Picked up", "location": "Memphis, TN"},
                {"date": "{transit_date}", "event": "In transit", "location": "Nashville, TN"},
                {"date": "{delivery_date}", "event": "Delivered", "location": "{cardholder_city}, {cardholder_state}"},
            ],
        },
    },
    "signed_delivery": {
        "sourceSystem": "ShippingCarrier",
        "sourceLabel": "FedEx Signature Service",
        "documentType": "shipping",
        "title": "Signed Delivery Confirmation",
        "contentTemplate": {
            "trackingNumber": "7489{tracking}",
            "signedBy": "{cardholder_name}",
            "signatureImage": "[signature_capture.png]",
            "deliveryDate": "{delivery_date}",
            "deliveryAddress": "{cardholder_city}, {cardholder_state}",
        },
    },
    "shipping_proof": {
        "sourceSystem": "ShippingCarrier",
        "sourceLabel": "UPS WorldShip",
        "documentType": "shipping",
        "title": "Shipping Proof",
        "contentTemplate": {
            "carrier": "UPS",
            "trackingNumber": "1Z{tracking}",
            "shipDate": "{ship_date}",
            "deliveredDate": "{delivery_date}",
            "status": "Delivered",
        },
    },
    "delivery_confirmation": {
        "sourceSystem": "ShippingCarrier",
        "sourceLabel": "UPS Delivery Confirmation",
        "documentType": "shipping",
        "title": "Delivery Confirmation",
        "contentTemplate": {
            "carrier": "UPS",
            "trackingNumber": "1Z{tracking}",
            "deliveryDate": "{delivery_date}",
            "leftAt": "Front Door",
            "status": "Delivered",
        },
    },
    "tracking_info": {
        "sourceSystem": "ShippingCarrier",
        "sourceLabel": "Carrier Tracking",
        "documentType": "shipping",
        "title": "Carrier Tracking Information",
        "contentTemplate": {
            "carrier": "USPS",
            "trackingNumber": "9400{tracking}",
            "status": "Delivered",
            "deliveryDate": "{delivery_date}",
        },
    },
    "proof_of_delivery": {
        "sourceSystem": "ShippingCarrier",
        "sourceLabel": "Proof of Delivery System",
        "documentType": "shipping",
        "title": "Proof of Delivery",
        "contentTemplate": {
            "carrier": "FedEx",
            "trackingNumber": "7489{tracking}",
            "deliveredTo": "{cardholder_city}, {cardholder_state}",
            "deliveryDate": "{delivery_date}",
            "signatureRequired": True,
            "signedBy": "RESIDENT",
        },
    },

    # ── Receipts / Signed documents ───────────────────────────────────────
    "signed_receipt": {
        "sourceSystem": "POSSystem",
        "sourceLabel": "POS Receipt Archive",
        "documentType": "receipt",
        "title": "Signed Receipt",
        "contentTemplate": {
            "receiptNumber": "RCP-{ref_id}",
            "merchantName": "{merchant}",
            "amount": "${amount}",
            "date": "{tx_date}",
            "signaturePresent": True,
            "cardLast4": "{card_last4}",
            "entryMode": "Chip",
        },
    },
    "original_receipt": {
        "sourceSystem": "POSSystem",
        "sourceLabel": "Receipt Archive",
        "documentType": "receipt",
        "title": "Original Transaction Receipt",
        "contentTemplate": {
            "receiptNumber": "RCP-{ref_id}",
            "merchant": "{merchant}",
            "originalAmount": "${amount}",
            "date": "{tx_date}",
        },
    },
    "return_receipt": {
        "sourceSystem": "MerchantSystem",
        "sourceLabel": "Returns Processing",
        "documentType": "receipt",
        "title": "Return Receipt",
        "contentTemplate": {
            "returnId": "RTN-{ref_id}",
            "originalOrderId": "ORD-{ref_id}",
            "returnDate": "{return_date}",
            "itemsReturned": ["Product as ordered"],
            "refundAmount": "${amount}",
            "refundMethod": "Original payment method",
        },
    },
    "imprint_copy": {
        "sourceSystem": "POSSystem",
        "sourceLabel": "Card Imprint Archive",
        "documentType": "receipt",
        "title": "Card Imprint Copy",
        "contentTemplate": {
            "imprintDate": "{tx_date}",
            "cardLast4": "{card_last4}",
            "merchantName": "{merchant}",
            "imprintQuality": "Clear — full card number embossed",
        },
    },
    "signature_comparison": {
        "sourceSystem": "FraudAnalytics",
        "sourceLabel": "Signature Verification",
        "documentType": "receipt",
        "title": "Signature Comparison",
        "contentTemplate": {
            "onFileSignature": "[sig_on_file.png]",
            "transactionSignature": "[sig_transaction.png]",
            "matchScore": 0.92,
            "analystVerdict": "Consistent",
        },
    },

    # ── Fraud / Risk signals ──────────────────────────────────────────────
    "avs_cvv_results": {
        "sourceSystem": "FraudPlatform",
        "sourceLabel": "Risk Scoring Engine",
        "documentType": "fraud_signal",
        "title": "AVS/CVV Verification Results",
        "contentTemplate": {
            "avsResponseCode": "Y",
            "avsDescription": "Street address and 5-digit ZIP match",
            "cvvResponseCode": "M",
            "cvvDescription": "CVV2/CVC2 Match",
            "riskScore": 12,
            "riskLevel": "Low",
            "deviceFingerprint": "DFP-{ref_id}",
        },
    },
    "ip_geolocation": {
        "sourceSystem": "FraudPlatform",
        "sourceLabel": "IP Intelligence",
        "documentType": "fraud_signal",
        "title": "IP Geolocation Data",
        "contentTemplate": {
            "ipAddress": "192.168.x.x (masked)",
            "city": "{cardholder_city}",
            "state": "{cardholder_state}",
            "country": "US",
            "isp": "Comcast Cable",
            "proxy": False,
            "vpn": False,
            "matchesBillingAddress": True,
        },
    },
    "device_fingerprint": {
        "sourceSystem": "FraudPlatform",
        "sourceLabel": "Device Intelligence",
        "documentType": "fraud_signal",
        "title": "Device Fingerprint",
        "contentTemplate": {
            "deviceId": "DFP-{ref_id}",
            "os": "iOS 17.4",
            "browser": "Safari 17.4",
            "screenResolution": "1170x2532",
            "timezone": "America/New_York",
            "previousTransactions": 14,
            "firstSeen": "2023-09-15",
            "riskIndicators": [],
        },
    },
    "3ds_authentication": {
        "sourceSystem": "CardNetwork",
        "sourceLabel": "3-D Secure System",
        "documentType": "fraud_signal",
        "title": "3-D Secure Authentication Proof",
        "contentTemplate": {
            "protocol": "3DS 2.2",
            "eci": "05",
            "authenticationValue": "AABBCCDD... (truncated)",
            "transactionStatus": "Y — Authenticated",
            "challengeRequired": False,
            "dsTransId": "DS-{ref_id}",
        },
    },
    "emv_chip_data": {
        "sourceSystem": "POSSystem",
        "sourceLabel": "EMV Terminal",
        "documentType": "fraud_signal",
        "title": "EMV Chip Transaction Data",
        "contentTemplate": {
            "applicationId": "A0000000031010",
            "applicationLabel": "Visa Credit",
            "cryptogramType": "ARQC",
            "terminalVerificationResults": "0000000000",
            "cardholderVerificationMethod": "Online PIN",
            "transactionCertificate": "TC-{ref_id}",
        },
    },
    "emv_data": {
        "sourceSystem": "POSSystem",
        "sourceLabel": "EMV Terminal",
        "documentType": "fraud_signal",
        "title": "EMV Chip Transaction Data",
        "contentTemplate": {
            "applicationId": "A0000000041010",
            "applicationLabel": "Mastercard",
            "cryptogramType": "ARQC",
            "cvmPerformed": "Online PIN",
            "terminalType": "22 — Attended, Online",
        },
    },
    "cvv_avs_response": {
        "sourceSystem": "CardNetwork",
        "sourceLabel": "Card Verification Service",
        "documentType": "fraud_signal",
        "title": "CVV/AVS Response Data",
        "contentTemplate": {
            "cvvResult": "M — Match",
            "avsResult": "Y — Full Match",
            "timestamp": "{tx_date}T14:23:01Z",
        },
    },
    "terminal_capability": {
        "sourceSystem": "POSSystem",
        "sourceLabel": "Terminal Management",
        "documentType": "transaction",
        "title": "Terminal EMV Capability Proof",
        "contentTemplate": {
            "terminalId": "TRM-{terminal_id}",
            "emvCapable": True,
            "contactlessCapable": True,
            "pinPadPresent": True,
            "certificationDate": "2023-06-15",
            "softwareVersion": "v4.2.1",
        },
    },
    "fraud_investigation_report": {
        "sourceSystem": "FraudPlatform",
        "sourceLabel": "Fraud Investigation Unit",
        "documentType": "fraud_signal",
        "title": "Fraud Investigation Report",
        "contentTemplate": {
            "caseId": "FRD-{ref_id}",
            "investigator": "Automated Fraud System",
            "findings": "Transaction flagged for review — cardholder denies authorization",
            "riskScore": 72,
            "recommendation": "Escalate for manual review",
        },
    },
    "ip_data": {
        "sourceSystem": "FraudPlatform",
        "sourceLabel": "IP Intelligence",
        "documentType": "fraud_signal",
        "title": "IP/Device Data",
        "contentTemplate": {
            "ip": "203.0.113.x (masked)",
            "country": "US",
            "vpnDetected": False,
            "deviceId": "DFP-{ref_id}",
        },
    },

    # ── Communication records ─────────────────────────────────────────────
    "communication_records": {
        "sourceSystem": "CRM",
        "sourceLabel": "Customer Support Platform",
        "documentType": "communication",
        "title": "Communication Records",
        "contentTemplate": {
            "threads": [
                {
                    "channel": "Email",
                    "date": "{comm_date_1}",
                    "from": "{cardholder_name}",
                    "subject": "Issue with order",
                    "summary": "Customer reported issue with transaction on {tx_date}.",
                },
                {
                    "channel": "Email",
                    "date": "{comm_date_2}",
                    "from": "Support Team",
                    "subject": "RE: Issue with order",
                    "summary": "Merchant responded with resolution steps.",
                },
            ],
        },
    },
    "cancellation_confirmation": {
        "sourceSystem": "CRM",
        "sourceLabel": "Customer Service",
        "documentType": "communication",
        "title": "Cancellation Confirmation",
        "contentTemplate": {
            "confirmationId": "CXL-{ref_id}",
            "cancellationDate": "{cancel_date}",
            "method": "Email confirmation sent",
            "acknowledgedBy": "Merchant Support Team",
        },
    },
    "cancellation_request": {
        "sourceSystem": "CRM",
        "sourceLabel": "Customer Communications",
        "documentType": "communication",
        "title": "Cancellation Request Evidence",
        "contentTemplate": {
            "requestDate": "{cancel_date}",
            "channel": "Email",
            "from": "{cardholder_name}",
            "content": "Request to cancel subscription/recurring billing",
            "merchantAcknowledged": True,
        },
    },

    # ── Contract / Policy documents ───────────────────────────────────────
    "cancellation_policy": {
        "sourceSystem": "MerchantSystem",
        "sourceLabel": "Policy Management",
        "documentType": "contract",
        "title": "Cancellation Policy",
        "contentTemplate": {
            "policyVersion": "v2.3",
            "effectiveDate": "2024-01-01",
            "cancellationWindow": "30 days",
            "cancellationMethod": "Email or online account",
            "refundPolicy": "Full refund within 30 days; prorated after",
            "customerAgreedDate": "{agreement_date}",
        },
    },
    "terms_of_service": {
        "sourceSystem": "MerchantSystem",
        "sourceLabel": "Legal/Compliance",
        "documentType": "contract",
        "title": "Terms of Service (signed)",
        "contentTemplate": {
            "version": "v4.1",
            "acceptedDate": "{agreement_date}",
            "acceptedVia": "Online checkbox at checkout",
            "ipAtAcceptance": "192.168.x.x",
            "keyClause": "Recurring billing continues until cancelled per cancellation policy",
        },
    },
    "terms_agreement": {
        "sourceSystem": "MerchantSystem",
        "sourceLabel": "Legal/Compliance",
        "documentType": "contract",
        "title": "Terms Agreement (signed)",
        "contentTemplate": {
            "agreementDate": "{agreement_date}",
            "signedBy": "{cardholder_name}",
            "method": "Electronic signature",
        },
    },
    "refund_policy": {
        "sourceSystem": "MerchantSystem",
        "sourceLabel": "Policy Management",
        "documentType": "contract",
        "title": "Refund Policy",
        "contentTemplate": {
            "policyVersion": "v3.0",
            "returnWindow": "30 days from delivery",
            "refundMethod": "Original payment method",
            "restockingFee": "None",
            "conditionsForRefund": "Item must be unused and in original packaging",
        },
    },
    "return_policy": {
        "sourceSystem": "MerchantSystem",
        "sourceLabel": "Policy Management",
        "documentType": "contract",
        "title": "Return Policy",
        "contentTemplate": {
            "returnWindow": "30 days",
            "condition": "Original packaging required",
            "shippingCost": "Prepaid label provided",
            "refundTimeline": "5-7 business days after receipt",
        },
    },
    "billing_agreement": {
        "sourceSystem": "MerchantSystem",
        "sourceLabel": "Billing Management",
        "documentType": "contract",
        "title": "Billing Agreement",
        "contentTemplate": {
            "agreementId": "BA-{ref_id}",
            "startDate": "{agreement_date}",
            "billingCycle": "Monthly",
            "amount": "${amount}",
            "cardLast4": "{card_last4}",
            "autoRenewal": True,
            "customerConsent": "Electronic acceptance on signup",
        },
    },
    "merchant_agreement": {
        "sourceSystem": "Acquirer",
        "sourceLabel": "Merchant Services",
        "documentType": "contract",
        "title": "Merchant Processing Agreement",
        "contentTemplate": {
            "merchantId": "MID-{merchant_id}",
            "merchantName": "{merchant}",
            "agreementDate": "{agreement_date}",
            "processingType": "Card-Present + Card-Not-Present",
            "chargebackLiability": "Standard per network rules",
        },
    },
    "no_show_documentation": {
        "sourceSystem": "MerchantSystem",
        "sourceLabel": "Reservation System",
        "documentType": "order",
        "title": "No-Show Documentation",
        "contentTemplate": {
            "reservationId": "RSV-{ref_id}",
            "checkInDate": "{tx_date}",
            "guestName": "{cardholder_name}",
            "noShowRecorded": True,
            "cancellationDeadline": "24 hours before check-in",
            "policyDisclosed": True,
        },
    },
    "reservation_confirmation": {
        "sourceSystem": "MerchantSystem",
        "sourceLabel": "Reservation System",
        "documentType": "order",
        "title": "Reservation Confirmation",
        "contentTemplate": {
            "confirmationNumber": "RSV-{ref_id}",
            "bookedDate": "{agreement_date}",
            "checkIn": "{tx_date}",
            "guestName": "{cardholder_name}",
            "totalCharge": "${amount}",
            "cancellationPolicy": "Free cancellation up to 24h before",
        },
    },

    # ── Order / Product evidence ──────────────────────────────────────────
    "product_description": {
        "sourceSystem": "MerchantSystem",
        "sourceLabel": "Product Catalog",
        "documentType": "order",
        "title": "Original Product Description/Listing",
        "contentTemplate": {
            "productId": "SKU-{ref_id}",
            "title": "Premium Widget Pro",
            "description": "High-quality widget with premium materials",
            "price": "${amount}",
            "specifications": ["Material: Aircraft-grade aluminum", "Weight: 450g", "Warranty: 2 years"],
            "listingURL": "https://merchant.example.com/products/SKU-{ref_id}",
        },
    },
    "product_listing": {
        "sourceSystem": "MerchantSystem",
        "sourceLabel": "E-Commerce Platform",
        "documentType": "order",
        "title": "Original Product Listing",
        "contentTemplate": {
            "sku": "SKU-{ref_id}",
            "title": "Premium Item",
            "listedPrice": "${amount}",
            "description": "As described in product listing at time of purchase",
            "snapshotDate": "{tx_date}",
        },
    },
    "proof_of_service_delivery": {
        "sourceSystem": "MerchantSystem",
        "sourceLabel": "Service Management",
        "documentType": "order",
        "title": "Proof of Service Delivery",
        "contentTemplate": {
            "serviceId": "SVC-{ref_id}",
            "serviceDate": "{delivery_date}",
            "serviceType": "As contracted",
            "completedBy": "Service Team",
            "customerAcknowledgment": "Digital sign-off received",
        },
    },
    "service_completion_record": {
        "sourceSystem": "MerchantSystem",
        "sourceLabel": "Service Management",
        "documentType": "order",
        "title": "Service Completion Record",
        "contentTemplate": {
            "serviceId": "SVC-{ref_id}",
            "completionDate": "{delivery_date}",
            "status": "Completed",
            "deliverables": ["Item shipped", "Confirmation sent"],
        },
    },

    # ── Photo evidence ────────────────────────────────────────────────────
    "photos": {
        "sourceSystem": "MerchantSystem",
        "sourceLabel": "Quality Assurance",
        "documentType": "photo",
        "title": "Product Photos (as shipped)",
        "contentTemplate": {
            "photoCount": 3,
            "photos": [
                {"filename": "product_front.jpg", "description": "Front view — matches listing", "takenDate": "{ship_date}"},
                {"filename": "product_packaging.jpg", "description": "Secure packaging", "takenDate": "{ship_date}"},
                {"filename": "shipping_label.jpg", "description": "Shipping label with address", "takenDate": "{ship_date}"},
            ],
        },
    },
    "surveillance_footage": {
        "sourceSystem": "SecuritySystem",
        "sourceLabel": "CCTV/Security Camera",
        "documentType": "photo",
        "title": "Surveillance Footage",
        "contentTemplate": {
            "cameraId": "CAM-{terminal_id}",
            "timestamp": "{tx_date}T14:23:00Z",
            "duration": "45 seconds",
            "resolution": "1080p",
            "storageLocation": "Security archive — retained 90 days",
        },
    },

    # ── ATM-specific ──────────────────────────────────────────────────────
    "atm_journal": {
        "sourceSystem": "ATMNetwork",
        "sourceLabel": "ATM Management System",
        "documentType": "transaction",
        "title": "ATM Journal/Log",
        "contentTemplate": {
            "atmId": "ATM-{terminal_id}",
            "transactionDate": "{tx_date}",
            "transactionTime": "14:23:01",
            "requestedAmount": "${amount}",
            "dispensedAmount": "${amount}",
            "cassetteBalanceBefore": "$45,200",
            "cassetteBalanceAfter": "$44,900",
            "journalStatus": "Dispensed — No Error",
        },
    },
    "reconciliation_records": {
        "sourceSystem": "ATMNetwork",
        "sourceLabel": "Cash Reconciliation",
        "documentType": "transaction",
        "title": "Cash Reconciliation Records",
        "contentTemplate": {
            "atmId": "ATM-{terminal_id}",
            "reconciliationDate": "{settle_date}",
            "expectedCash": "$44,900",
            "actualCash": "$44,900",
            "variance": "$0.00",
            "status": "Balanced",
        },
    },
}


# ---------------------------------------------------------------------------
# Context Builder — Generates mock values for template interpolation
# ---------------------------------------------------------------------------


def _build_context(dispute: dict[str, Any]) -> dict[str, str]:
    """Build template interpolation context from a dispute document."""
    now = datetime.now(timezone.utc)
    tx_date_str = dispute.get("transactionDate", now.strftime("%Y-%m-%d"))

    try:
        tx_date = datetime.fromisoformat(tx_date_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        tx_date = now - timedelta(days=14)

    ship_date = tx_date + timedelta(days=1)
    transit_date = tx_date + timedelta(days=3)
    delivery_date = tx_date + timedelta(days=5)
    settle_date = tx_date + timedelta(days=2)
    comm_date_1 = tx_date + timedelta(days=7)
    comm_date_2 = tx_date + timedelta(days=9)
    cancel_date = tx_date - timedelta(days=3)
    agreement_date = tx_date - timedelta(days=60)
    return_date = tx_date + timedelta(days=10)
    listed_date = tx_date - timedelta(days=30)

    short_id = uuid.uuid4().hex[:8].upper()

    return {
        "tx_date": tx_date.strftime("%Y-%m-%d"),
        "ship_date": ship_date.strftime("%Y-%m-%d"),
        "transit_date": transit_date.strftime("%Y-%m-%d"),
        "delivery_date": delivery_date.strftime("%Y-%m-%d"),
        "settle_date": settle_date.strftime("%Y-%m-%d"),
        "comm_date_1": comm_date_1.strftime("%Y-%m-%d"),
        "comm_date_2": comm_date_2.strftime("%Y-%m-%d"),
        "cancel_date": cancel_date.strftime("%Y-%m-%d"),
        "agreement_date": agreement_date.strftime("%Y-%m-%d"),
        "return_date": return_date.strftime("%Y-%m-%d"),
        "listed_date": listed_date.strftime("%Y-%m-%d"),
        "amount": f"{dispute.get('transactionAmount', 99.99):.2f}",
        "merchant": dispute.get("merchantName", "Unknown Merchant"),
        "cardholder_name": dispute.get("cardholderName", "Cardholder"),
        "cardholder_city": dispute.get("metadata", {}).get("city", "Atlanta"),
        "cardholder_state": dispute.get("metadata", {}).get("state", "GA"),
        "card_last4": dispute.get("cardLastFour", "0000"),
        "auth_code": short_id[:6],
        "terminal_id": short_id[:5],
        "merchant_id": short_id[:8],
        "batch": short_id[:6],
        "ref_id": short_id,
        "tracking": uuid.uuid4().hex[:10].upper(),
    }


def _interpolate(obj: Any, ctx: dict[str, str]) -> Any:
    """Recursively interpolate {placeholders} in strings within a structure."""
    if isinstance(obj, str):
        for key, val in ctx.items():
            obj = obj.replace("{" + key + "}", val)
        return obj
    if isinstance(obj, dict):
        return {k: _interpolate(v, ctx) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_interpolate(item, ctx) for item in obj]
    return obj


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def retrieve_evidence_for_dispute(dispute: dict[str, Any]) -> dict[str, Any]:
    """
    Mock-retrieve all evidence for a dispute based on its reason code.

    Args:
        dispute: Dispute document (from Cosmos DB) with at least:
            - networkCode (or network)
            - reasonCode (e.g. "Visa 13.1" or just "13.1")
            - transactionDate, transactionAmount, merchantName, cardLastFour, cardholderName

    Returns:
        {
            "disputeId": str,
            "network": str,
            "reasonCode": str,
            "evidenceItems": [...],       # Successfully retrieved items
            "failedItems": [...],         # Items that "failed" to retrieve (none in mock)
            "totalRetrieved": int,
            "totalRequired": int,
            "retrievalComplete": bool,
            "retrievedAt": str,           # ISO timestamp
        }
    """
    network = (dispute.get("networkCode") or dispute.get("network") or "").lower()
    reason_code_raw = dispute.get("reasonCode", "")

    # Parse combined reason codes like "Visa 13.1" or "MC 4837"
    if not network or network == "unknown":
        parsed_net, parsed_code = parse_reason_code_string(reason_code_raw)
        network = parsed_net
        code = parsed_code
    else:
        # Strip the network prefix if present
        _, code = parse_reason_code_string(reason_code_raw)
        if code == reason_code_raw:
            # No prefix found — use as-is
            code = reason_code_raw

    checklist = get_evidence_checklist(network, code)
    ctx = _build_context(dispute)
    now = datetime.now(timezone.utc)

    evidence_items = []
    for item in checklist:
        template = _EVIDENCE_TEMPLATES.get(item["id"])
        if template:
            content = _interpolate(template["contentTemplate"], ctx)
            evidence_items.append({
                "evidenceId": f"ev-{uuid.uuid4().hex[:12]}",
                "checklistItemId": item["id"],
                "label": item["label"],
                "type": item["type"],
                "priority": item["priority"],
                "sourceSystem": template["sourceSystem"],
                "sourceLabel": template["sourceLabel"],
                "documentType": template["documentType"],
                "title": template["title"],
                "content": content,
                "retrievedAt": now.isoformat(),
                "status": "retrieved",
            })
        else:
            # Evidence type exists in checklist but no mock template — mark as unavailable
            evidence_items.append({
                "evidenceId": f"ev-{uuid.uuid4().hex[:12]}",
                "checklistItemId": item["id"],
                "label": item["label"],
                "type": item["type"],
                "priority": item["priority"],
                "sourceSystem": "Unknown",
                "sourceLabel": "Not Connected",
                "documentType": item["type"],
                "title": item["label"],
                "content": None,
                "retrievedAt": now.isoformat(),
                "status": "unavailable",
            })

    retrieved = [e for e in evidence_items if e["status"] == "retrieved"]
    failed = [e for e in evidence_items if e["status"] != "retrieved"]

    return {
        "disputeId": dispute.get("disputeId") or dispute.get("id", ""),
        "network": network,
        "reasonCode": code,
        "evidenceItems": evidence_items,
        "failedItems": failed,
        "totalRetrieved": len(retrieved),
        "totalRequired": len(checklist),
        "retrievalComplete": len(failed) == 0 and len(checklist) > 0,
        "retrievedAt": now.isoformat(),
    }
