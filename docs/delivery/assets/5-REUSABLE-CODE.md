# 5. Reusable Code or Configuration

## Repository Contents

**Location**: https://github.com/yortch/payment-disputes

### Key Directories

```
payment-disputes/
├── infra/
│   ├── main.bicep                 # Root IaC template (provisions all resources)
│   ├── modules/
│   │   ├── cosmos.bicep           # Cosmos DB + containers
│   │   ├── functions.bicep        # Azure Functions app + runtime
│   │   ├── storage.bicep          # Blob Storage + lifecycle policies
│   │   ├── swa.bicep              # Static Web Apps (portals)
│   │   └── keyvault.bicep         # Key Vault + secrets
│   └── parameters.json            # Environment-specific values
│
├── src/
│   ├── api/
│   │   ├── function_app.py        # FastAPI app with all endpoints
│   │   ├── services/
│   │   │   ├── document_service.py    # Blob artifact upload/retrieval
│   │   │   ├── cosmos_service.py      # Cosmos DB queries
│   │   │   ├── scoring_service.py     # Foundry agent orchestration
│   │   │   └── email_service.py       # (future) Notifications
│   │   ├── models/
│   │   │   └── cosmos_models.py   # Data models (Dispute, Timeline, etc.)
│   │   ├── requirements.txt       # Python dependencies
│   │   ├── local.settings.json    # Function app local debug config
│   │   └── Dockerfile            # Container image (optional)
│   │
│   ├── web/
│   │   ├── src/
│   │   │   ├── components/
│   │   │   │   ├── CaseTable.tsx          # Sortable queue component ✅
│   │   │   │   ├── CaseBadges.tsx         # Status badge rendering
│   │   │   │   └── Timeline.tsx           # Timeline event display
│   │   │   ├── pages/
│   │   │   │   ├── CasesQueuePage.tsx     # Analyst queue (sortable columns)
│   │   │   │   ├── CaseDetailPage.tsx     # Analyst case view
│   │   │   │   └── ... (other routes)
│   │   │   ├── types/
│   │   │   │   └── case.ts              # TypeScript case interface
│   │   │   ├── utils/
│   │   │   │   ├── queueStatus.ts       # Queue filtering + closed case logic
│   │   │   │   └── api.ts               # API client
│   │   │   ├── App.tsx                   # Router + main layout
│   │   │   └── styles/                   # CSS (Fluent UI components)
│   │   ├── package.json           # npm dependencies
│   │   ├── vite.config.ts         # Build config
│   │   └── dist/                  # (Generated) Build output
│   │
│   └── customer-portal/
│       ├── src/
│       │   ├── pages/
│       │   │   ├── MyDisputesPage.tsx        # Customer dispute list + cancellation ✅
│       │   │   └── DisputeDetailPage.tsx     # Customer case detail + upload
│       │   ├── api/
│       │   │   └── disputes.ts               # API client methods
│       │   └── types/
│       │       └── dispute.ts                # Dispute TypeScript interface
│       ├── package.json
│       ├── vite.config.ts
│       └── dist/                  # (Generated) Build output
│
├── data/
│   └── sample_disputes.json       # 5 pre-populated test cases for seeding
│
├── scripts/
│   ├── seed-db.sh                 # Load sample_disputes.json into Cosmos
│   ├── test-api.sh                # cURL examples for all endpoints
│   └── backup-cosmos.sh           # Manual backup script (future)
│
├── .github/
│   └── workflows/
│       └── cd.yml                 # CI/CD: build, test, deploy on main branch push
│
├── docs/
│   ├── README.md                  # Quick start + architecture overview
│   ├── DEPLOYMENT.md              # Detailed deployment guide
│   ├── API.md                     # API endpoint documentation
│   └── delivery/                  # Technical companion docs
│       ├── README.md
│       └── assets/                # Architecture, deployment, and deep-dive notes
│
├── azure.yaml                     # Azure Dev CLI manifest
├── CHANGELOG.md                   # Version history + release notes
├── README.md                      # Root readme
└── .gitignore, .env.*, ...        # Standard files
```

### Important Files to Review

#### 1. **azure.yaml** (5-min read)
Defines the project for `azd`:
```yaml
name: payment-disputes
services:
  api:
    project: ./src/api
    language: py
    host: function
  web:
    project: ./src/web
    language: js
    host: staticwebapp
    dist: dist
  portal:
    project: ./src/customer-portal
    language: js
    host: staticwebapp
    dist: dist
```
**Key Point**: This is how `azd up` knows what to deploy.

#### 2. **src/api/function_app.py** (Core backend, 200 lines)
All REST endpoints:
- `POST /disputes` — Intake
- `POST /disputes/{id}/cancel` — Customer cancellation
- `POST /disputes/{id}/customer-response` — Evidence upload
- `POST /disputes/{id}/score` — AI scoring trigger
- `GET /disputes/{id}/timeline` — Audit events

#### 3. **src/web/src/components/CaseTable.tsx** (Sortable queue, 80 lines)
```typescript
// Features: Click column header to sort ascending/descending
// State: sortKey (which column), sortDir ('asc'|'desc')
// Renders: Fluent UI Table with custom sort handlers
```

#### 4. **src/customer-portal/src/pages/MyDisputesPage.tsx** (Customer view, 120 lines)
```typescript
// Features: Timeline view + cancel button
// State: cancelConfirm (dialog open?), cancelReason (text input)
// Actions: handleCancelDispute() calls API, updates UI
```

### Reusable Patterns

#### Pattern 1: Timeline Event Audit Log
Every action is a Cosmos document:
```json
{
  "id": "event-12345",
  "dispute_id": "dispute-abc",
  "event_type": "customer_cancellation",
  "timestamp": "2026-07-22T10:30:00Z",
  "actor": "customer",
  "actor_id": "customer-xyz",
  "detail": "Merchant refunded the charge",
  "data": {
    "reason": "refunded",
    "refund_amount": 150.00
  }
}
```
**Benefit**: Single document type handles all audit; UI renders timeline naturally; compliance compliance.

#### Pattern 2: Shared Data Model
Both portals query same Cosmos DB documents:
```typescript
interface Dispute {
  id: string;
  customerId: string;
  merchantId: string;
  status: "intake" | "evidence_gathering" | "pending_review" | "approved" | "denied" | "escalated" | "closed";
  amount: number;
  reason: string;
  createdAt: string;
  timeline: TimelineEvent[];  // All events for this dispute
  evidenceItems: Evidence[];   // All uploaded artifacts
  aiScoring?: {
    winProbability: number;
    riskLevel: "low" | "medium" | "high";
    reasoning: string;
  };
}
```
**Benefit**: No sync issues; changes visible immediately to both portals.

#### Pattern 3: Managed Identity for Auth
Functions authenticate to Cosmos/Blob using Managed Identity (no keys):
```python
from azure.identity import DefaultAzureCredential
from azure.cosmos import CosmosClient

credential = DefaultAzureCredential()
client = CosmosClient(url=cosmos_url, credential=credential)
```
**Benefit**: Secure, rotates automatically, scales to many services.

#### Pattern 4: Artifact Versioning
Each upload gets unique blob name:
```
customer-response-{dispute_id}-{timestamp}.txt
evidence-{dispute_id}-{upload_number}.pdf
rebuttal-{dispute_id}-v{version}.md
```
**Benefit**: Can rollback, never overwrites, audit trail built-in.

#### Pattern 5: Feature Flags (Future)
```python
def should_auto_reprocess(dispute_id: str) -> bool:
    # Check Feature Flag service or config
    return os.getenv("AUTO_REPROCESS_ENABLED") == "true"
```
**Benefit**: Deploy code but enable features gradually; Phase 2 can plug this in.

---

## Scripts

### `scripts/seed-db.sh`
Loads sample disputes into Cosmos DB:
```bash
bash scripts/seed-db.sh
```
Creates 5 test disputes for demo purposes. Useful for:
- Local development
- Demo to customers
- Load testing baseline

### `scripts/test-api.sh`
cURL examples for all endpoints:
```bash
# Create dispute
curl -X POST https://api.azurewebsites.net/api/disputes \
  -H "Content-Type: application/json" \
  -d @payload.json

# Get case detail
curl -X GET https://api.azurewebsites.net/api/disputes/{id}

# Score case
curl -X POST https://api.azurewebsites.net/api/disputes/{id}/score

# Cancel dispute
curl -X POST https://api.azurewebsites.net/api/disputes/{id}/cancel \
  -d '{"reason": "Merchant refunded"}'
```

---

## Configuration

### `.env.development` (Local dev)
```
AZURE_COSMOS_ENDPOINT=https://localhost:8081
AZURE_COSMOS_KEY=C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2pIFAoeCMrMnO7sq+J3ysrQ0ONEYflqQdqsSUCUEsDw==
AZURE_STORAGE_ACCOUNT_NAME=localhost
AZURE_FUNCTION_URI=http://localhost:7071
```

### `.env.production` (Azure)
```
AZURE_COSMOS_ENDPOINT=${COSMOS_ENDPOINT}  # Reference to Key Vault
AZURE_KEYVAULT_URI=https://{vaultname}.vault.azure.net/
# All secrets fetched from Key Vault at runtime
```

### `src/api/config.py`
Scoring thresholds and behavior:
```python
MIN_APPROVAL_SCORE = 0.65  # Only recommend approval if confidence > 65%
CONFIDENCE_THRESHOLD = 0.50
AI_AGENT_TIMEOUT = 30  # seconds
BATCH_SIZE = 10  # disputes per batch for Foundry
```

---

## Dependencies

### Python (`src/api/requirements.txt`)
- fastapi
- azure-cosmos
- azure-storage-blob
- azure-identity
- python-dotenv
- pydantic

### Node.js (`src/web/package.json`, `src/customer-portal/package.json`)
- react, react-dom
- typescript
- @fluentui/react (UI components)
- axios (API client)
- vite (build tool)

---

## Next Steps for Teams Using This Code

1. **Clone the repo**: `git clone ...`
2. **Read docs**: Start with `README.md`, then `docs/DEPLOYMENT.md`
3. **Deploy locally**: `azd up` in your Azure subscription
4. **Modify for your use case**:
   - Update `src/api/config.py` for your business rules
   - Customize `src/web/src/components/CaseTable.tsx` for your data model
   - Train Foundry agents on your historical disputes
5. **Share with team**: This codebase is a starting point; adapt as needed

---

**Document Version**: 1.0 | **Last Updated**: 2026-07-22
