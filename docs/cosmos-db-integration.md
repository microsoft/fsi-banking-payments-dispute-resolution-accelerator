# Cosmos DB Integration — Change Summary

> **Branch:** `DN_work`
> **Author:** Danna Nemeth
> **Date:** 2026-07-06

---

## What Was Added

Azure Cosmos DB (NoSQL API) as the **operational data store** for active dispute cases. This is the transactional layer — Fabric/OneLake remains the analytics lakehouse.

### Why Cosmos DB (vs PostgreSQL)

| Factor | Cosmos DB | PostgreSQL |
|--------|-----------|------------|
| Schema flexibility | Visa/MC/Amex/Discover all have different evidence shapes — schemaless handles natively | Requires polymorphic tables or EAV |
| Change feed | Built-in — fires Azure Functions automatically on writes | Requires polling/pg_notify |
| Fabric mirroring | Native OneLake mirroring (analytical store) — zero-ETL | Requires Data Factory pipeline |
| Identity-based auth | RBAC-only (no keys) — matches team's security pattern | Needs connection strings |
| Event-driven fit | First-class with Functions, Event Grid, AI Search | More plumbing required |

---

## Files Changed / Added

### Infrastructure (Bicep)

| File | Change |
|------|--------|
| `infra/modules/cosmos.bicep` | **NEW** — Cosmos DB account (serverless, analytical store enabled), database `disputes-db`, 3 containers |
| `infra/modules/cosmos-rbac.bicep` | **NEW** — Grants the Function App managed identity data-plane access |
| `infra/main.bicep` | **MODIFIED** — Added `cosmos` and `cosmosRbac` modules; passes endpoint to Functions app settings |
| `infra/modules/functions.bicep` | **MODIFIED** — Added `COSMOS_ENDPOINT` and `COSMOS_DATABASE_NAME` app settings |
| `infra/abbreviations.json` | **MODIFIED** — Added `"cosmosDbAccount": "cosmos"` |

### Application Code (Python)

| File | Change |
|------|--------|
| `src/api/models.py` | **NEW** — Data models (DisputeCase, EvidenceItem, TimelineEvent) with factory functions |
| `src/api/cosmos_client.py` | **NEW** — Cosmos DB client using `DefaultAzureCredential` (managed identity in Azure, Azure CLI locally) |
| `src/api/function_app.py` | **MODIFIED** — Added REST endpoints: `POST /disputes`, `GET /disputes/{id}`, `GET /disputes/{id}/evidence`, `GET /disputes/{id}/timeline` |
| `src/api/requirements.txt` | **MODIFIED** — Added `azure-cosmos` and `azure-identity` |

---

## Cosmos DB Design

### Account Configuration
- **API:** NoSQL (document DB)
- **Capacity:** Serverless (pay-per-request — ideal for dev/demo, easily switch to provisioned for prod)
- **Analytical Store:** Enabled (required for Fabric mirroring)
- **Auth:** RBAC-only (`disableLocalAuth: true` — no primary keys)
- **Consistency:** Session (strong within a session, eventual across)

### Database: `disputes-db`

| Container | Partition Key | Purpose |
|-----------|---------------|---------|
| `disputes` | `/networkCode`, `/disputeId` (hierarchical) | One document per dispute case — full lifecycle state |
| `evidence` | `/disputeId` | Evidence items gathered from source systems |
| `timeline` | `/disputeId` | Audit trail — every state transition, action, decision |

### Composite Indexes (on `disputes`)
- `networkCode ASC, createdAt DESC` — list disputes by network, newest first
- `status ASC, deadlineUtc ASC` — find urgent disputes approaching deadline

---

## API Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/api/health` | Health check (unchanged) |
| `POST` | `/api/disputes` | Create a new dispute case |
| `GET` | `/api/disputes/{dispute_id}?networkCode=visa` | Get a dispute by ID |
| `GET` | `/api/disputes/{dispute_id}/evidence` | Get all evidence for a dispute |
| `GET` | `/api/disputes/{dispute_id}/timeline` | Get audit timeline for a dispute |

### Sample Request — Create Dispute

```json
POST /api/disputes
{
  "networkCode": "visa",
  "reasonCode": "13.1",
  "cardholderName": "Sarah Chen",
  "cardLastFour": "4242",
  "transactionAmount": 149.99,
  "transactionDate": "2026-06-28",
  "merchantName": "TechGadgets Inc",
  "deadlineUtc": "2026-07-28T23:59:59Z"
}
```

---

## Connectivity — How Everything Connects

```
┌──────────────────┐       ┌────────────────────────┐
│  Azure Functions │──────▶│  Cosmos DB (NoSQL)     │
│  (managed identity)      │  disputes-db           │
│                  │       │  ├── disputes           │
│  COSMOS_ENDPOINT │       │  ├── evidence           │
│  env var auto-set│       │  └── timeline           │
└──────────────────┘       └──────────┬─────────────┘
                                      │ analytical store
                                      ▼ (mirroring)
                           ┌────────────────────────┐
                           │  Microsoft Fabric      │
                           │  OneLake Lakehouse     │
                           │  (zero-ETL sync)       │
                           └────────────────────────┘
                                      │
                                      ▼
                           ┌────────────────────────┐
                           │  AI Foundry / Agents   │
                           │  (reads dispute data   │
                           │   for maker-checker)   │
                           └────────────────────────┘
```

### Fabric Mirroring Setup (post-deploy)
Once the Cosmos DB account is provisioned:
1. In Fabric workspace → **New** → **Mirrored Database** → **Azure Cosmos DB**
2. Enter the Cosmos DB account endpoint (output: `AZURE_COSMOS_ENDPOINT`)
3. Select the `disputes-db` database and all 3 containers
4. Fabric auto-syncs via the analytical store — no pipelines needed

### AI Foundry Connection
The AI agents connect to Cosmos DB the same way as Functions:
- Use the `AZURE_COSMOS_ENDPOINT` environment variable
- Authenticate with `DefaultAzureCredential` (managed identity or developer login)
- Read from `disputes` and `evidence` containers for case context

---

## Local Development

```bash
# 1. Ensure you're logged into Azure CLI (for DefaultAzureCredential)
az login

# 2. Set the environment variables in local.settings.json
# src/api/local.settings.json:
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "FUNCTIONS_EXTENSION_VERSION": "~4",
    "COSMOS_ENDPOINT": "https://<your-cosmos-account>.documents.azure.com:443/",
    "COSMOS_DATABASE_NAME": "disputes-db"
  }
}

# 3. Install dependencies
pip install -r src/api/requirements.txt

# 4. Run locally
cd src/api
func start
```

> **Note:** Your Azure CLI login must have the **Cosmos DB Built-in Data Contributor** role on the account. The Bicep grants this to the `deployerPrincipalId` automatically during `azd up`.

---

## Deploy

```bash
# Uses the existing AZD setup — Cosmos DB is now included
azd up
```

The deployment will output:
```
AZURE_COSMOS_ENDPOINT = https://cosmos-<token>.documents.azure.com:443/
AZURE_COSMOS_DATABASE_NAME = disputes-db
```

---

## RBAC Summary

| Principal | Role | Scope |
|-----------|------|-------|
| Function App (system-assigned identity) | Cosmos DB Built-in Data Contributor | Cosmos account |
| Deployer (your Azure CLI identity) | Cosmos DB Built-in Data Contributor | Cosmos account |

No keys, no connection strings — everything is identity-based.
