# Seed Data for Payments Dispute Resolution

This directory contains synthetic seed data for the Cosmos DB operational data store.

## Files

| File | Description | Records |
|------|-------------|---------|
| `disputes.json` | Bulk synthetic disputes (250) | 250 |
| `evidence.json` | Evidence items for bulk disputes | ~980 |
| `timeline.json` | Timeline events for bulk disputes | ~2,510 |
| `demo_disputes.json` | Named demo scenarios (8 stories) | 25 |
| `demo_evidence.json` | Evidence for demo scenarios | 29 |
| `demo_timeline.json` | Timeline for demo scenarios | 47 |
| `stats.json` | Summary statistics | — |

## Demo Scenarios

These are hand-crafted walkthrough-ready stories for the July demo:

| # | Scenario | Network | Status | Highlights |
|---|----------|---------|--------|------------|
| 1 | **Sarah Chen — Friendly Fraud** | Visa | Closed/Won | Full lifecycle, UPS delivery proof, 87% win probability |
| 2 | **Urgent Deadline** | Mastercard | In Review | 2 days until MC 45-day deadline, analyst must act now |
| 3 | **Escalation to Supervisor** | Amex | Escalated | HITL timeout, auto-escalated to supervisor queue |
| 4 | **High-Value Fraud Ring** | Discover | Approved | $4,589 cloned card, geo-mismatch, card-testing pattern |
| 5 | **Maker-Checker Retry** | Visa | Submitted | Groundedness check fails, maker revises, passes on retry |
| 6 | **Reg E Debit Clock** | Visa | Gathering | 10-business-day debit deadline, evidence gaps blocking |
| 7 | **Cross-Network Comparison** | All 4 | Mixed | Same merchant, same reason, different network handling |
| 8 | **Volume Spike** | Visa/MC | Mixed | 15 disputes from GourmetBox in 48h — ops alert scenario |

## Data Coverage

- **Card Networks**: Visa (48%), Mastercard (21%), Amex (24%), Discover (8%)
- **Reason Codes**: 38 unique codes across all 4 networks
- **Categories**: Fraud (33%), Consumer Dispute (40%), Processing Error (22%), Authorization (6%)
- **Statuses**: All 9 lifecycle stages represented
- **Transaction Amounts**: $18 – $4,961 (avg $757)
- **Evidence Types**: transaction, order, shipping, communication, fraud_signal, receipt
- **Source Systems**: payment_processor, oms_erp, logistics, crm, fraud_engine, document_intelligence

## Regenerating Data

```bash
# Generate 250 bulk disputes (reproducible with seed=42)
python src/data/generate_seed_data.py --count 250 --output-dir data/seed

# Generate demo scenarios (fixed content)
python src/data/demo_scenarios.py

# Adjust count for larger datasets:
python src/data/generate_seed_data.py --count 1000 --output-dir data/seed
```

## Loading into Cosmos DB

```bash
# Prerequisites: az login, Cosmos DB deployed, RBAC assigned
python src/data/seed_cosmos.py \
  --data-dir data/seed \
  --endpoint https://cosmos-xxx.documents.azure.com:443/ \
  --database disputes-db
```

## Schema Notes

### Disputes Container
- **Partition Key**: Hierarchical (`/networkCode`, `/disputeId`)
- **Key Fields**: disputeId, networkCode, reasonCode, status, transactionAmount, deadlineUtc, winProbability

### Evidence Container
- **Partition Key**: `/disputeId`
- **Key Fields**: evidenceId, disputeId, evidenceType, sourceSystem, content, blobUrl

### Timeline Container
- **Partition Key**: `/disputeId`
- **Key Fields**: eventId, disputeId, eventType, actor, detail, data, occurredAt
