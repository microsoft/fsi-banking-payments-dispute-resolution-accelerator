# Synthetic Dispute Case Data

Pre-generated demo fixtures for the Payments Dispute Resolution accelerator.

---

## Files

| Path | Description |
|---|---|
| `cases.json` | Combined array of all 10 cases — primary fixture for the API |
| `cases/<caseId>.json` | One file per case — same data, split for per-case blob reads |
| `generate_cases.py` | Generator script — re-run to refresh `daysRemaining` or add cases |

---

## Cases at a glance

| # | Network | Reason | Label | Status | Win | Risk | Days left |
|---|---------|--------|-------|--------|-----|------|-----------|
| 01 | Visa | 13.1 | Merchandise Not Received | `pending_review` | 72% | high | 2 |
| 02 | Mastercard | 4853 | Defective / Not as Described | `pending_review` | 58% | medium | 15 |
| 03 | Amex | C28 | Cancelled Recurring | `pending_review` | 31% | critical | 3 |
| 04 | Discover | UA02 | Card-Not-Present Fraud | `pending_review` | 88% | low | 25 |
| 05 | Visa | 10.4 | Card Absent Fraud | `evidence_gathering` | 45% | high | 8 |
| 06 | Mastercard | 4837 | No Cardholder Authorization | `pending_review` | 22% | critical | 2 |
| 07 | Amex | FR2 | Fraud Full Recourse | `escalated` | 48% | high | 6 |
| 08 | Discover | UA01 | EMV Counterfeit (Card Present) | `pending_review` | 61% | medium | 1 |
| 09 | Visa | 13.3 | Merchandise Not as Described | `approved` | 93% | low | 25 |
| 10 | Mastercard | 4855 | Goods / Services Not Provided | `pending_review` | 39% | critical | 3 |

> Days-remaining values above were seeded at **2026-07-06**. Regenerate to refresh.

### Demo highlights

- **Near-expiry drama:** Cases 01, 06 (2 days), 08 (1 day), 03, 10 (3 days)
- **Complete evidence / high win:** Case 04 (Discover, zero gaps), Case 09 (Visa, approved + resolvedAt)
- **Evidence gap showcase:** Case 05 (evidence_gathering, 3 gaps), Case 10 (2 critical + 1 medium gap)
- **Escalated status:** Case 07 (Amex, PCI-DSS cert missing)
- **All 4 networks covered:** Visa (01, 05, 09), Mastercard (02, 06, 10), Amex (03, 07), Discover (04, 08)

---

## How to regenerate

```bash
# from repo root
python src/data/synthetic/generate_cases.py
```

This will:
1. Recalculate `daysRemaining` from today's date.
2. Overwrite `cases/*.json` and `cases.json`.
3. Validate every case against `src/shared/schemas/case.schema.json`.

Optional: install `jsonschema` for full Draft 2020-12 schema validation:

```bash
pip install jsonschema
python src/data/synthetic/generate_cases.py
```

Without `jsonschema`, the script falls back to a manual field-by-field check that covers all required fields, enum values, and citation integrity.

---

## How these feed the API (Issue #41)

The `GET /api/cases` and `GET /api/cases/{caseId}` endpoints (Issue #41) read from these
files served via Azure Blob Storage for the demo:

```
blob://disputes-demo/cases.json           → GET /api/cases  (summary list)
blob://disputes-demo/cases/<id>.json      → GET /api/cases/{caseId}  (full detail)
```

For the demo, the read API loads directly from `cases.json` (or the per-file split).
In the production path, these become OneLake Delta tables ingested via Azure Data Factory.

---

## Internal consistency rules (enforced by the generator)

- `rebuttalDraft.citations[*].evidenceId` must reference an `evidenceId` present in the same case's `evidence` array.
- `reasonCodeChecklist[*].satisfied = false` for any item whose corresponding evidence type is absent or `missing`.
- `evidenceGaps` entries describe genuinely absent required items; `impact` reflects risk to the rebuttal outcome.
- `deadline.daysRemaining` is calculated from `dueDate` relative to the generation date.

---

## OneLake path (future — post-demo)

When Issue #2 (OneLake integration) lands, the generator will be wired into an Azure Data Factory
pipeline that writes to:

```
onelake://disputes-workspace/disputes-lakehouse/Tables/dispute_cases/
```

The JSON schema remains the contract; ADF will map fields to Delta column types.
