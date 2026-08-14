# Regulatory Requirements — Reg E, Reg Z & Card-Network Dispute Rules

**Status:** Phase 1 documentation deliverable (Issues [#27](https://github.com/yortch/payment-disputes/issues/27) and [#28](https://github.com/yortch/payment-disputes/issues/28))
**Scope:** Debit dispute regulation (Reg E), credit dispute regulation (Reg Z), and the four in-scope card-network rule sets (Visa, Mastercard, American Express, Discover), plus the reason-code-to-evidence mapping table that backs `services/reason_code_engine.py` and the deadline-management feature (`services/scoring_service.py`, `services/gaps_service.py`, `triggers/pl_ingest_raw.py::_calculate_deadline`).

This document is descriptive of publicly available regulatory text and standard network operating-regulations summaries. It is **not legal advice** — Compliance/Legal should review before this accelerator is used with real disputes.

---

## 1. Regulation E — Debit Dispute Requirements (Issue #27)

Regulation E (12 CFR Part 1005), implementing the Electronic Fund Transfer Act (EFTA), governs disputes on **debit card / electronic fund transfer** transactions. It is the regulatory backbone for the platform's debit-network deadline handling.

### 1.1 Key requirements

| Requirement | Rule |
|---|---|
| **Error notice window** | The cardholder must notify the bank within **60 days** of the statement on which the disputed transaction first appeared. |
| **Investigation window** | The bank must investigate and determine whether an error occurred within **10 business days** of receiving the notice (the "10-business-day clock" referenced throughout the PRD). |
| **Extended investigation** | If the bank cannot complete the investigation in 10 business days, it may take up to **45 calendar days** total — but **only if** provisional credit is issued to the cardholder within the original 10-business-day window. |
| **New-account extension** | For accounts open ≤30 days, the point-of-sale/foreign-transaction/new-account investigation window extends to **20 business days**, and the total extended window to **90 calendar days**. |
| **Resolution notice** | The bank must report results to the cardholder within **3 business days** of completing the investigation. |
| **Reversal of provisional credit** | If the bank determines no error occurred, it may reverse the provisional credit, but must give the cardholder **5 business days' notice** before doing so and provide a written explanation. |

### 1.2 10-business-day clock — logic specification

```
notice_received_date  = date the cardholder's dispute notice is received
investigation_deadline = notice_received_date + 10 business days
  (business day = Mon–Fri, excluding federal holidays)

IF investigation NOT complete by investigation_deadline:
    IF provisional_credit issued by investigation_deadline:
        extended_deadline = notice_received_date + 45 calendar days
                            (90 calendar days if account age <= 30 days)
    ELSE:
        → regulatory violation risk (must issue provisional credit or resolve)

resolution_notice_deadline = investigation_completion_date + 3 business days
```

This is the debit-side deadline the platform's SLA/countdown feature (`DeadlineCountdown.tsx`, `SLAProgressBar.tsx`, and `_calculate_deadline` in `pl_ingest_raw.py`) must track in addition to the card-network response deadline (§3) — **the earlier of the two governs the analyst's action window** for debit disputes.

### 1.3 Provisional credit rules

- Provisional credit = the amount in dispute, **minus** any applicable Reg E liability limit already assessed to the cardholder.
- Must be made available for the cardholder's use no later than the end of the 10-business-day (or extended) investigation period whenever the investigation is not yet complete.
- The bank must notify the cardholder of the provisional credit amount and its availability date within 1 business day of crediting the account.
- If the dispute is resolved in the bank's favor, the bank may debit the provisional credit back — but only after the 5-business-day notice above, and it cannot re-debit before that notice period lapses.

### 1.4 Linkage to system deadline management

| Reg E deadline | Feature | Field / Function |
|---|---|---|
| 10-business-day investigation | Case SLA countdown | `deadline.dueDate` / `deadline.daysRemaining` (Case model), `_calculate_deadline()` in `triggers/pl_ingest_raw.py` |
| Extended 45/90-day window | Escalation timer | `SLA_HOURS` in `orchestrator/dispute_orchestrator.py` (currently network-only; **Reg E debit extension should be layered in as a follow-up** since it can exceed the network's own response window) |
| Provisional credit issuance | Not yet modeled | No current field — recommend adding `provisionalCreditIssuedAt` / `provisionalCreditAmount` to the Case model in Phase 2 |
| Resolution notice (3 business days) | Timeline event | `analyst_note` / decision timeline events already capture the resolution timestamp |

---

## 2. Regulation Z — Credit Dispute Requirements (Issue #28)

Regulation Z (12 CFR Part 1026), implementing the Truth in Lending Act (TILA), governs **credit card** billing-error disputes (distinct from the debit/EFTA rules above).

### 2.1 Key requirements

| Requirement | Rule |
|---|---|
| **Billing-error notice window** | Cardholder must submit a written billing-error notice within **60 days** of the first statement containing the error. |
| **Acknowledgment** | The issuer must acknowledge receipt of the notice within **30 days** (unless resolved within that time). |
| **Resolution window** | The issuer must resolve the dispute within **2 complete billing cycles**, not to exceed **90 days**, from receipt of the notice. |
| **Payment withholding** | The cardholder may withhold payment on the disputed amount (and related finance charges) while the dispute is pending — the issuer cannot report the amount delinquent during this period. |
| **No adverse credit reporting** | The issuer cannot close, restrict, or accelerate payment on the account solely because of the dispute, nor report it as delinquent, while under active dispute. |
| **Chargeback rights (§1026.12(c) / §1026.13)** | Cardholders retain claims-and-defenses rights against the issuer for disputes over $50 involving purchases in their home state or within 100 miles, mirroring the card-network reason-code framework used for representment. |

### 2.2 Logic specification

```
notice_received_date  = date the written billing-error notice is received
acknowledgment_deadline = notice_received_date + 30 days
resolution_deadline    = min(notice_received_date + 2 billing cycles, notice_received_date + 90 days)

WHILE dispute pending:
    disputed_amount NOT payable/delinquent-reportable
    account NOT closable/restrictable solely due to dispute
```

Reg Z's 90-day statutory ceiling is generally **longer** than the card-network response windows in §3 below, so in practice the **network deadline is the binding constraint** for credit disputes — Reg Z acts as a backstop ensuring the cardholder is never worse off even if network timelines were somehow longer.

---

## 3. Card-Network Dispute Rules & Timelines

All four in-scope networks are supported end-to-end by `services/reason_code_engine.py`. Response-deadline constants live in `NETWORK_DEADLINES`; per-reason-code evidence requirements and win-rate benchmarks live in `REASON_CODES`.

### 3.1 Visa

- **Response window:** ~**30 days** from the chargeback notification to submit representment (`NETWORK_DEADLINES["visa"] = 30`).
- **Category framework:** Visa groups reason codes into **Fraud (10.x)**, **Authorization (11.x)**, **Processing Errors (12.x)**, and **Consumer Disputes (13.x)** — matching `CATEGORY_LABELS` in the engine.
- **Representment format:** Visa Claims Resolution (VCR) dispute response, addressed to Visa Claims Resolution — Dispute Response (see `maker_agent_client._NETWORK_FORMATS["visa"]`).

### 3.2 Mastercard

- **Response window:** **20–45 days**, depending on chargeback cycle/reason code (`NETWORK_DEADLINES["mastercard"] = 45`, used as the outer bound the platform tracks).
- **Category framework:** 4-digit codes (48xx) spanning **Fraud**, **Authorization/Processing Errors**, and **Consumer Disputes**.
- **Representment format:** Second Presentment via Mastercom, addressed to Mastercard Dispute Resolution — Second Presentment.

### 3.3 American Express

- **Response window:** ~**20 days** (`NETWORK_DEADLINES["amex"] = 20`) — the shortest of the four networks; the platform's deadline countdown must flag Amex cases earliest.
- **Category framework:** Alphanumeric codes — **C-series** (Consumer Disputes / Processing) and **F-series** (Fraud).
- **Representment format:** Chargeback Reversal submission, addressed to American Express Merchant Services — Dispute Response.

### 3.4 Discover

- **Response window:** ~**30 days** (`NETWORK_DEADLINES["discover"] = 30`).
- **Category framework:** Two-letter codes spanning **Fraud**, **Authorization**, **Processing Errors**, and **Consumer Disputes**.
- **Representment format:** Dispute Representment, addressed to Discover Network — Dispute Resolution.

### 3.5 Network summary table

| Network | Response Window | Reason-Code Format | Categories | Representment Format |
|---|---|---|---|---|
| Visa | ~30 days | Numeric `NN.N` (e.g. 10.4, 13.1) | Fraud, Authorization, Processing Error, Consumer Dispute | Visa Claims Resolution (VCR) |
| Mastercard | 20–45 days | Numeric 4-digit (e.g. 4837) | Fraud, Processing Error, Consumer Dispute | Second Presentment (Mastercom) |
| American Express | ~20 days | Alphanumeric (`Cxx` / `Fxx`) | Consumer Dispute/Processing (C), Fraud (F) | Chargeback Reversal |
| Discover | ~30 days | Two-letter (e.g. RG, AA) | Fraud, Authorization, Processing Error, Consumer Dispute | Dispute Representment |

*(Evidence submission windows in the engine's `time_limit_days` field are modeled as 120 days across all codes — the outer bound for gathering supporting evidence — while the network response deadlines above are the binding submission-to-network SLA the case countdown tracks.)*

---

## 4. Reason-Code-to-Evidence Mapping Table

Generated from the live `REASON_CODES` registry in `services/reason_code_engine.py` (source of truth — regenerate this table if the registry changes). **Win Rate** is the historical benchmark used as the base rate in `services/scoring_service.py`.

### Visa (30-day response window)

| Code | Description | Category | Win Rate | Required Evidence | Recommended Evidence |
|---|---|---|---|---|---|
| 10.1 | EMV Liability Shift Counterfeit Fraud | Fraud | 62% | Transaction Receipt; EMV Chip Transaction Data; Authorization Log | — |
| 10.4 | Other Fraud — Card Absent Environment | Fraud | 55% | AVS/CVV Verification Results; IP Geolocation Data | Device Fingerprint; 3-D Secure Authentication Proof |
| 11.1 | Card Recovery Bulletin | Authorization | 70% | Authorization Log; Card Recovery Bulletin Date Verification | — |
| 12.5 | Incorrect Amount | Processing Error | 75% | Transaction Receipt; Signed Receipt | Terminal Transaction Data |
| 12.6 | Duplicate Processing | Processing Error | 80% | Transaction Logs (both charges); Batch Settlement Records; Authorization Log | — |
| 13.1 | Merchandise/Services Not Received | Consumer Dispute | 72% | Shipping Confirmation; Proof of Delivery; Carrier Tracking Number | Signed Delivery Confirmation |
| 13.2 | Cancelled Recurring Transaction | Consumer Dispute | 60% | Cancellation Policy; Terms of Service (signed) | Communication Records |
| 13.3 | Not as Described or Defective | Consumer Dispute | 58% | Original Product Description/Listing; Product Photos (as shipped) | Return Policy; Customer Communication Records |
| 13.6 | Credit Not Processed | Consumer Dispute | 65% | Refund Policy; Return Receipt; Credit/Refund Voucher | Communication Records |
| 13.7 | Cancelled Merchandise/Services | Consumer Dispute | 63% | Cancellation Policy; Terms of Service; Proof of Service Delivery | — |

### Mastercard (20–45 day response window)

| Code | Description | Category | Win Rate | Required Evidence | Recommended Evidence |
|---|---|---|---|---|---|
| 4834 | Point-of-Interaction Error | Processing Error | 70% | Transaction Receipt; Terminal Transaction Data | Batch Settlement Records |
| 4837 | No Cardholder Authorization | Fraud | 68% | Signed Receipt/Invoice; Authorization Log; CVV/AVS Response Data | — |
| 4840 | Fraudulent Processing of Transactions | Fraud | 50% | Authorization Log; Merchant Processing Agreement; Transaction Processing Records | — |
| 4853 | Cardholder Dispute — Goods/Services | Consumer Dispute | 52% | Shipping Proof; Delivery Confirmation | Product Description; Communication Records |
| 4855 | Goods or Services Not Provided | Consumer Dispute | 65% | Proof of Delivery; Carrier Tracking Information; Service Completion Record | — |
| 4859 | Addendum, No-show, or ATM Dispute | Consumer Dispute | 60% | Reservation Confirmation; Cancellation/No-Show Policy | No-Show Documentation |
| 4863 | Cardholder Does Not Recognize | Fraud | 55% | Transaction Receipt; Authorization Log; Merchant Descriptor Evidence | — |
| 4871 | Chip/PIN Liability Shift | Fraud | 60% | EMV Chip Transaction Data; Terminal EMV Capability Proof; Authorization Log | — |

### American Express (20-day response window)

| Code | Description | Category | Win Rate | Required Evidence | Recommended Evidence |
|---|---|---|---|---|---|
| C02 | Credit Not Processed | Consumer Dispute | 65% | Refund Policy; Credit/Refund Voucher | Communication Records |
| C04 | Goods/Services Not Received | Consumer Dispute | 70% | Proof of Delivery; Carrier Tracking Number; Shipping Confirmation | — |
| C05 | Goods/Services Cancelled | Consumer Dispute | 62% | Cancellation Policy; Terms Agreement (signed) | Communication Records |
| C08 | Goods/Services Not as Described | Consumer Dispute | 55% | Original Product Listing; Product Photos | Communication Records; Return Policy |
| C14 | Paid by Other Means | Processing Error | 78% | Alternative Payment Proof; Transaction Records | — |
| C18 | Cancel of Recurring Billing | Consumer Dispute | 58% | Billing Agreement; Cancellation Request Evidence | Processing Records |
| F10 | Missing Imprint | Fraud | 72% | Signed Receipt; Card Imprint Copy; Authorization Log | — |
| F14 | Missing Signature | Fraud | 70% | Signed Receipt; Signature Comparison; Authorization Log | — |
| F24 | No Cardmember Authorization | Fraud | 50% | Authorization Log; Fraud Investigation Report | IP/Device Data |
| F29 | Card Not Present | Fraud | 52% | AVS/CVV Verification Results; 3-D Secure Authentication | IP Geolocation Data; Device Fingerprint |

### Discover (30-day response window)

| Code | Description | Category | Win Rate | Required Evidence | Recommended Evidence |
|---|---|---|---|---|---|
| AA | Cardholder Does Not Recognize | Fraud | 55% | Transaction Receipt; Authorization Log; Merchant Descriptor Evidence | — |
| AP | Cancelled Recurring Transaction | Consumer Dispute | 60% | Billing Agreement; Cancellation Confirmation | Processing Records |
| AW | Altered Amount | Processing Error | 75% | Original Transaction Receipt; Terminal Data; Authorization Log | — |
| CD | Credit/Debit Posted Incorrectly | Processing Error | 78% | Transaction Records; Batch Settlement Records; Authorization Log | — |
| DP | Duplicate Processing | Processing Error | 82% | Transaction Logs (both charges); Batch Records; Settlement Data | — |
| EX | Expired Card | Authorization | 85% | Authorization Log; Card Expiry Verification | — |
| NF | Non-receipt of Cash from ATM | Consumer Dispute | 60% | ATM Journal/Log; Cash Reconciliation Records | Surveillance Footage |
| RG | Non-Receipt of Goods/Services | Consumer Dispute | 68% | Shipping Proof; Delivery Confirmation; Carrier Tracking Information | — |
| RM | Quality Discrepancy | Consumer Dispute | 52% | Product Description/Listing; Product Photos | Communication Records; Return Policy |
| UA | Fraud — Card Present | Fraud | 58% | Signed Receipt; EMV Chip Data | Surveillance Footage |

---

## 5. Sources & References

- 12 CFR Part 1005 (Regulation E) — Electronic Fund Transfer Act implementing regulation, Consumer Financial Protection Bureau.
- 12 CFR Part 1026 (Regulation Z) — Truth in Lending Act implementing regulation, Consumer Financial Protection Bureau.
- Visa Core Rules and Visa Product and Service Rules — dispute/chargeback provisions.
- Mastercard Chargeback Guide.
- American Express Merchant Operating Guide — dispute/chargeback provisions.
- Discover Network Operating Regulations — dispute provisions.
- Internal source of truth for reason codes, win rates, and evidence requirements: `src/api/services/reason_code_engine.py` (`REASON_CODES`, `NETWORK_DEADLINES`, `CATEGORY_LABELS`).

**Note:** Network operating rules and CFPB regulations are updated periodically. This document reflects the rule set encoded in the accelerator as of July 2026 and should be reviewed against current network bulletins and the CFPB's eCFR before production use.
