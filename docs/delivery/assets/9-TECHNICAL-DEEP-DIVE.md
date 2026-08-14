# 9. Technical Deep Dive

## Complete Technical Reference for Implementation & Integration

### Table of Contents
1. [API Specifications](#api-specifications)
2. [Data Model & Schema](#data-model--schema)
3. [Orchestration & Workflows](#orchestration--workflows)
4. [Authentication & Security](#authentication--security)
5. [AI Agent Integration](#ai-agent-integration)
6. [Error Handling & Resilience](#error-handling--resilience)
7. [Database Design](#database-design)
8. [Integration Patterns](#integration-patterns)
9. [Performance & Scalability](#performance--scalability)
10. [Deployment Architecture](#deployment-architecture)

---

## API Specifications

### Base Configuration
- **Base URL**: `https://func-{id}-app.azurewebsites.net/api`
- **Auth**: Phase 1: Function key (header: `x-functions-key`), Phase 2: Entra ID with RBAC
- **Rate Limits**: 
  - Customers: 100 req/min per IP
  - Analysts: 1000 req/min per user
  - System: 10,000 req/min global

### Dispute Management Endpoints

#### 1. Create Dispute
```
POST /api/disputes

Request:
{
  "cardNetwork": "visa|mastercard|amex|discover",
  "transactionAmount": 249.99,
  "transactionDate": "2025-03-15",
  "merchantName": "Acme Corp",
  "merchantCity": "Austin",
  "reasonCode": "4855",  // Paid by Other Means per Visa
  "cardholderStatement": "I never authorized this charge",
  "evidence": [
    {
      "type": "document|email|screenshot",
      "filename": "merchant_confirmation.pdf",
      "mimeType": "application/pdf",
      "size": 245000
    }
  ]
}

Response (201):
{
  "disputeId": "9d419cc2-8641-47f4-baf0-fcbeeca2a7cb",
  "status": "intake",
  "evidenceUploadUrls": [
    "https://stquxx.blob.core.windows.net/ingest/{timestamp}_{disputeId}_0?sv=2023-01-01..."
  ],
  "timelineEvents": [
    {
      "id": "evt_001",
      "type": "dispute_intake",
      "timestamp": "2025-03-20T14:32:00Z",
      "actor": "customer",
      "detail": "Customer initiated dispute"
    }
  ],
  "deadline": "2025-04-20T23:59:59Z",  // Network SLA: 45 days from transaction
  "createdAt": "2025-03-20T14:32:00Z"
}

Error Responses:
- 400: Validation error (invalid card network, missing required fields)
- 413: Evidence file exceeds 25 MB limit
- 429: Rate limit exceeded
- 500: Cosmos DB or Blob storage error
```

#### 2. Get Dispute
```
GET /api/disputes/{disputeId}

Response (200):
{
  "disputeId": "9d419cc2-8641-47f4-baf0-fcbeeca2a7cb",
  "cardNetwork": "visa",
  "transactionAmount": 249.99,
  "transactionDate": "2025-03-15",
  "merchantName": "Acme Corp",
  "status": "pending_review",
  "reasonCode": "4855",
  "timelineEvents": [
    {
      "id": "evt_001",
      "type": "dispute_intake",
      "timestamp": "2025-03-20T14:32:00Z",
      "actor": "customer",
      "detail": "Customer initiated dispute"
    },
    {
      "id": "evt_002",
      "type": "evidence_gathering",
      "timestamp": "2025-03-20T14:35:00Z",
      "actor": "system",
      "detail": "Evidence files uploaded and validated"
    },
    {
      "id": "evt_003",
      "type": "ai_score_computed",
      "timestamp": "2025-03-20T14:45:00Z",
      "actor": "ai_agent",
      "detail": "Score: 0.78 (high probability of win)"
    }
  ],
  "aiScoring": {
    "winProbability": 0.78,
    "riskLevel": "low",
    "reasoning": "Transaction occurred during merchant refund period; cardholder has proof of non-delivery",
    "computedAt": "2025-03-20T14:45:00Z"
  },
  "customerCancellable": true,
  "deadline": "2025-04-20T23:59:59Z"
}

Error Responses:
- 404: Dispute not found
- 401: Unauthorized (invalid auth token)
```

#### 3. Score Dispute (AI)
```
POST /api/disputes/{disputeId}/score

Request:
{
  "manualOverride": true,  // Allow analyst to force rescore
  "contextHint": "merchant_is_fraud_target"
}

Response (202 - Accepted):
{
  "orchestrationId": "abc123xyz789",
  "status": "processing",
  "estimatedSeconds": 15
}

Polling Response (GET /api/disputes/{disputeId}/score-status):
{
  "status": "completed",
  "scoring": {
    "winProbability": 0.78,
    "riskLevel": "low",
    "reasoning": "...",
    "confidenceScore": 0.95,
    "modelVersion": "foundry-deepseek-v3.2"
  },
  "computedAt": "2025-03-20T14:45:00Z"
}

Error Responses:
- 400: Invalid disputeId or already scored
- 503: AI service unavailable
- 504: Scoring timeout (>30 seconds)
```

#### 4. List Disputes (Queue)
```
GET /api/disputes?tab=open&sort=deadline&order=asc&limit=50&offset=0

Response (200):
{
  "total": 1247,
  "offset": 0,
  "limit": 50,
  "disputes": [
    {
      "disputeId": "9d419cc2-...",
      "status": "pending_review",
      "merchantName": "Acme Corp",
      "amount": 249.99,
      "reasonCode": "4855",
      "deadline": "2025-04-20T23:59:59Z",
      "aiScore": 0.78,
      "createdAt": "2025-03-20T14:32:00Z"
    }
    // ... 49 more
  ],
  "statusBreakdown": {
    "intake": 23,
    "evidence_gathering": 456,
    "pending_review": 768
  }
}
```

#### 5. Analyst Decision
```
POST /api/disputes/{disputeId}/decision

Request:
{
  "decision": "approve|deny|escalate",
  "reasoning": "Merchant unable to provide proof of delivery within 10 days",
  "autoSubmitToNetwork": false  // Phase 2
}

Response (200):
{
  "disputeId": "9d419cc2-...",
  "status": "approved",
  "decision": {
    "type": "approve",
    "analyst": "analyst@bank.com",
    "timestamp": "2025-03-20T15:30:00Z",
    "reasoning": "Merchant unable to provide proof of delivery"
  },
  "timelineEvent": {
    "id": "evt_004",
    "type": "analyst_decision",
    "actor": "analyst",
    "detail": "Approved - Merchant unable to provide proof of delivery"
  }
}

Error Responses:
- 409: Dispute already closed / decision already made
- 403: Analyst not authorized for this dispute
```

#### 6. Cancel Dispute (Customer)
```
POST /api/disputes/{disputeId}/cancel

Request:
{
  "reason": "Merchant refunded the charge"
}

Response (200):
{
  "disputeId": "9d419cc2-...",
  "status": "closed",
  "closureReason": "customer_cancellation",
  "customerReason": "Merchant refunded the charge",
  "closedAt": "2025-03-20T15:35:00Z"
}

Error Responses:
- 409: Cannot cancel - dispute already closed/approved/denied
- 400: Invalid cancellation reason
```

#### 7. Draft Rebuttal (AI)
```
POST /api/disputes/{disputeId}/draft-rebuttal

Request:
{
  "context": "Merchant is disputing our denial",
  "previousResponse": "..."  // Prior rebuttal if retry
}

Response (202):
{
  "orchestrationId": "def456uvw123",
  "status": "processing",
  "estimatedSeconds": 25
}

Polling (GET /api/disputes/{disputeId}/rebuttal-status):
{
  "status": "completed",
  "rebuttal": {
    "narrative": "Following the Visa Operating Rules Section 7.9...",
    "supportingEvidence": [
      {
        "evidenceRef": "email_001",
        "relevance": "Proves non-delivery claim"
      }
    ],
    "generatedBy": "foundry-deepseek-v3.2",
    "generatedAt": "2025-03-20T15:50:00Z"
  }
}
```

#### 8. Health Check
```
GET /api/health

Response (200):
{
  "status": "healthy",
  "components": {
    "cosmosDb": "healthy",
    "blobStorage": "healthy",
    "foundryAgent": "healthy",
    "timestamp": "2025-03-20T16:00:00Z"
  }
}
```

---

## Data Model & Schema

### Core Dispute Document (Cosmos DB)

```json
{
  "id": "9d419cc2-8641-47f4-baf0-fcbeeca2a7cb",
  "partitionKey": "visa",  // Card network
  "disputeId": "9d419cc2-8641-47f4-baf0-fcbeeca2a7cb",
  "orchestrationId": "abc123xyz789",
  
  // Cardholder & Transaction
  "cardNetwork": "visa",
  "cardholderName": "John Doe",
  "cardLast4": "4242",
  "transactionAmount": 249.99,
  "currency": "USD",
  "transactionDate": "2025-03-15",
  "transactionRef": "visa_txn_12345678",
  
  // Merchant
  "merchantName": "Acme Corp",
  "merchantCity": "Austin",
  "merchantCountry": "US",
  "merchantCategoryCode": "5734",
  "merchantId": "mcc_98765",
  
  // Dispute Details
  "status": "pending_review",  // intake → evidence_gathering → pending_review → approved|denied|escalated|closed
  "reasonCode": "4855",  // Paid by Other Means (Visa)
  "reasonCodeNetwork": "visa",
  "cardholderStatement": "I never authorized this charge",
  "requestedRefundAmount": 249.99,
  
  // Evidence
  "evidence": [
    {
      "id": "evt_evidence_001",
      "type": "document",
      "filename": "merchant_confirmation.pdf",
      "mimeType": "application/pdf",
      "blobUrl": "https://stquxx.blob.core.windows.net/evidence/2025-03-20_9d419cc2_001.pdf",
      "uploadedAt": "2025-03-20T14:35:00Z",
      "uploadedBy": "customer",
      "size": 245000
    }
  ],
  
  // AI Scoring
  "aiScoring": {
    "winProbability": 0.78,
    "riskLevel": "low",  // low|medium|high
    "reasoning": "Transaction occurred during merchant refund period; cardholder has proof of non-delivery",
    "confidenceScore": 0.95,
    "modelVersion": "foundry-deepseek-v3.2",
    "computedAt": "2025-03-20T14:45:00Z",
    "scoredBy": "ai_agent"
  },
  
  // Analyst Decision
  "decision": {
    "type": "approve|deny|escalate",
    "analyst": "analyst@bank.com",
    "timestamp": "2025-03-20T15:30:00Z",
    "reasoning": "Merchant unable to provide proof of delivery"
  },
  
  // Durable Functions
  "orchestrationId": "abc123xyz789",
  "orchestrationStatus": "Completed",
  
  // Deadlines & SLA
  "transactionSLA": 45,  // days from transaction
  "deadline": "2025-04-20T23:59:59Z",
  "daysRemaining": 31,
  "slaStatus": "on_track|at_risk|exceeded",
  
  // Timeline
  "timeline": [
    {
      "id": "evt_001",
      "type": "dispute_intake",
      "timestamp": "2025-03-20T14:32:00Z",
      "actor": "customer",
      "detail": "Customer initiated dispute via portal"
    },
    {
      "id": "evt_002",
      "type": "evidence_gathering",
      "timestamp": "2025-03-20T14:35:00Z",
      "actor": "system",
      "detail": "Evidence files uploaded and validated"
    },
    {
      "id": "evt_003",
      "type": "ai_score_computed",
      "timestamp": "2025-03-20T14:45:00Z",
      "actor": "ai_agent",
      "detail": "Score: 0.78 (high probability of win)",
      "metadata": {
        "winProbability": 0.78,
        "riskLevel": "low"
      }
    },
    {
      "id": "evt_004",
      "type": "analyst_decision",
      "timestamp": "2025-03-20T15:30:00Z",
      "actor": "analyst",
      "detail": "Approved - Merchant unable to provide proof of delivery"
    }
  ],
  
  // Metadata
  "createdAt": "2025-03-20T14:32:00Z",
  "updatedAt": "2025-03-20T15:30:00Z",
  "ttl": null,  // No expiration; compliance requires permanent retention
  "_rid": "...",  // Cosmos DB internal
  "_ts": 1711000320,  // Cosmos DB timestamp
  "_etag": "\\"0000f0d2-0000-0100-0000-660e4f2a\\"",
  "version": 1  // Schema versioning
}
```

### Timeline Event Types
```
• dispute_intake — Customer initiates dispute
• evidence_gathering — Evidence files uploaded
• ai_score_computed — AI analysis completed
• analyst_decision — Analyst approves/denies/escalates
• customer_cancellation — Customer cancels
• merchant_response — Merchant provides response (Phase 2)
• appeal_filed — Appeal filed with network (Phase 2)
• network_decision — Network renders final decision (Phase 2)
```

---

## Orchestration & Workflows

### Durable Functions Flow (Azure)

```
Customer submits dispute
    ↓
[POST /api/disputes]
    ├─ Create Cosmos document (status: intake)
    ├─ Upload evidence to Blob
    ├─ Write timeline event
    └─ Start orchestrator
           ↓
    [dispute_orchestrator]
    ├─ Activity: assemble_case
    │  └─ Gather all evidence, timeline, cardholder data
    │
    ├─ Wait for external event: 'analyst_decision'
    │  └─ Analyst UI triggers: POST /api/disputes/{id}/decision
    │  └─ Internal: app.raise_event('dispute', 'analyst_decision', {...})
    │
    ├─ (if approved) Activity: submit_to_network
    │  └─ Call network API (Visa, MC, Amex endpoint)
    │  └─ Update Cosmos: status='submitted'
    │
    └─ Complete orchestrator
```

### AI Agent Integration Flow

```
Analyst clicks "Score" button
    ↓
POST /api/disputes/{id}/score
    ├─ Check if already scored (cached result valid)
    ├─ Load dispute + evidence from Cosmos/Blob
    └─ Invoke Foundry scoring agent:
    
        [Foundry Agent: Score]
        ├─ Input:
        │  {
        │    "dispute": {dispute doc},
        │    "evidence": [{text extracts}],
        │    "merchantType": "retail",
        │    "cardNetwork": "visa"
        │  }
        │
        ├─ Output:
        │  {
        │    "winProbability": 0.78,
        │    "riskLevel": "low",
        │    "reasoning": "...",
        │    "confidenceScore": 0.95
        │  }
        │
        └─ Update Cosmos: aiScoring = {...}
           Write timeline event
           Response to UI
```

---

## Authentication & Security

### Phase 1 (Current)
- **Function Key**: All requests include `x-functions-key: {key}`
- **CORS**: Enabled for localhost + deployed SWA URLs
- **HTTPS**: Required (TLS 1.2+)

### Phase 2 (Planned)
```
┌─────────────────────┐
│  Analyst Portal     │
│  (SWA + Auth)       │
└──────────┬──────────┘
           │ (1) Browser → SWA
           │     includes auth token
           ▼
┌─────────────────────────────────┐
│  Azure Static Web App Auth       │
│  /.auth/me endpoint              │
│  Entra ID login flow             │
└──────────┬──────────────────────┘
           │ (2) SWA backend receives
           │     Bearer token
           ▼
┌─────────────────────────────────┐
│  Azure Functions                │
│  app.auth_level = AuthLevel.FUNCTION
│  Validate Bearer token          │
│  Check user roles (RBAC)        │
│  - analyst                      │
│  - supervisor                   │
│  - finance_reviewer             │
└─────────────────────────────────┘
```

### Data Protection
- **At Rest**: AES-256 (Cosmos DB + Blob Storage default encryption)
- **In Transit**: TLS 1.2+ on all API calls
- **Secrets**: Azure Key Vault for connection strings, API keys
  - Function app identity: System-assigned managed identity
  - Role assignment: Key Vault Secrets User
- **Access Tokens**: 
  - Phase 1: Function key (bearer token in Authorization header)
  - Phase 2: Entra ID tokens (JWT, 1-hour expiry)

---

## AI Agent Integration

### Scoring Agent (Foundry DeepSeek-v3.2)

**Purpose**: Predict win probability for dispute

**Input Schema**:
```python
{
    "dispute": {
        "transactionAmount": float,
        "cardNetwork": str,
        "reasonCode": str,
        "merchantCategoryCode": str,
        "daysSinceTransaction": int,
        "cardholderStatement": str
    },
    "evidence": [
        {
            "type": "email|document|screenshot|bank_statement",
            "excerpt": str,
            "relevance": "high|medium|low"
        }
    ],
    "merchantContext": {
        "history": "fraud_target|first_time|high_chargeback_rate",
        "responseTime": "fast|slow|none"
    }
}
```

**Output Schema**:
```python
{
    "winProbability": float,  # 0.0 to 1.0
    "riskLevel": "low|medium|high",
    "reasoning": str,
    "supportingFactors": [str],
    "mitigatingFactors": [str],
    "confidenceScore": float,
    "recommendedAction": "approve|deny|escalate",
    "modelVersion": str,
    "processingTimeMs": int
}
```

**Error Handling**:
- **Timeout** (>30s): Return cached score or manual review required
- **Invalid Input**: Return 400 with detailed error
- **Foundry Unavailable**: Return 503 with retry hint

---

## Error Handling & Resilience

### HTTP Status Codes

| Code | Scenario | Retry? |
|------|----------|--------|
| 200 | Success | No |
| 202 | Async processing started | No (poll status endpoint) |
| 400 | Validation error (bad input) | No |
| 401 | Unauthorized (invalid auth) | No |
| 403 | Forbidden (insufficient permissions) | No |
| 404 | Resource not found | No |
| 409 | Conflict (state mismatch) | No |
| 429 | Rate limit exceeded | Yes (exponential backoff) |
| 500 | Internal server error | Yes (exponential backoff) |
| 503 | Service unavailable | Yes (exponential backoff) |
| 504 | Gateway timeout | Yes (exponential backoff) |

### Retry Strategy (Exponential Backoff)
```python
max_retries = 3
initial_wait = 1  # second
max_wait = 30  # seconds

for attempt in range(max_retries):
    try:
        response = call_api()
        return response
    except RetryableException:
        wait_time = min(initial_wait * (2 ** attempt), max_wait)
        sleep(wait_time + random(0, wait_time * 0.1))  # jitter
    except NonRetryableException:
        raise
```

### Transient Failures
- **Cosmos DB timeout**: Automatic retry with backoff
- **Blob Storage rate limit**: Built-in retry via SDK
- **Foundry agent timeout**: Return 504 and allow manual retry
- **Network latency**: Client implements exponential backoff

### Idempotency
- All POST operations include idempotency key in URL path
- Cosmos DB patch operations use optimistic concurrency (etag)
- Duplicate API calls with same input return cached result (5-min window)

---

## Database Design

### Cosmos DB Configuration

```
Account: cosmos-{id}
Database: disputes
Containers:
├── disputes (RU/s: Autoscale 400-4000)
│  ├── Partition Key: /cardNetwork
│  ├── Indexes: status, deadline, createdAt
│  └── TTL: disabled (compliance retention)
│
├── timeline (RU/s: Autoscale 200-2000)
│  ├── Partition Key: /disputeId
│  └── Indexes: type, timestamp
│
└── evidence (RU/s: Autoscale 200-2000)
   ├── Partition Key: /disputeId
   └── Indexes: uploadedAt, type
```

### Query Patterns

```sql
-- List disputes by status
SELECT * FROM disputes
WHERE status IN ('pending_review', 'evidence_gathering')
ORDER BY deadline ASC

-- Get timeline for dispute
SELECT * FROM timeline
WHERE disputeId = 'xxx'
ORDER BY timestamp DESC

-- Aggregate statistics
SELECT 
    status,
    COUNT(*) as count,
    AVG(aiScoring.winProbability) as avgScore
FROM disputes
WHERE transactionDate > '2025-01-01'
GROUP BY status
```

### Backup & Recovery
- **Continuous backup**: Enabled (automatic snapshots every 4 hours)
- **Point-in-time restore**: Available for last 30 days
- **Export**: Monthly export to Azure Data Lake for archival

---

## Integration Patterns

### Inbound Integrations

**1. Card Network Webhooks (Phase 2)**
```
Visa/MC/Amex sends merchant response via webhook:
POST /api/webhooks/network-response
{
  "disputeRef": "visa_12345",
  "merchantResponse": {...},
  "timestamp": "2025-03-20T16:00:00Z"
}

→ Validate webhook signature
→ Update Cosmos dispute doc
→ Trigger analyst alert
```

**2. Customer Portal Integration**
```
SPA (React) → Azure Functions via:
- CORS-enabled endpoints
- Blob SAS tokens for file upload
- WebSocket for real-time status (Phase 2)
```

### Outbound Integrations

**1. Network Submission (Phase 2)**
```
Approved dispute → Network API:

POST https://api.visa.com/disputes/{disputeId}/submit
Authorization: Bearer {token}
{
  "decision": "APPROVE",
  "reasoning": "Merchant unable to provide proof of delivery",
  "evidence": [...]
}

← Receive network reference & timeline
→ Update Cosmos: networkRef, networkStatus
```

**2. Analytics & Reporting**
```
Timeline events → Event Hub → Fabric OneLake → Power BI
- Real-time processing of disputes
- Dispute metrics dashboard
- Predictive analytics on win rates
```

---

## Performance & Scalability

### Current Metrics (Phase 1)
- **Throughput**: 100 disputes/day
- **P95 Latency**: ~200ms (API call)
- **P95 AI Scoring**: ~8s (Foundry agent)
- **Storage**: ~50 KB per dispute (avg)

### Scaling Path (Phase 2 → Phase 3)

```
Phase 1 (Current)
├─ 100 disputes/day
├─ Manual analyst queue
├─ Single region
└─ ~$300/month

Phase 2 (2025-H2)
├─ 1,000 disputes/day
├─ Automated triage & scoring
├─ Durable Functions autoscale
├─ Cosmos DB autopilot
└─ ~$1,500/month

Phase 3 (2026)
├─ 10,000 disputes/day
├─ Multi-region active-active
├─ AI-driven dispute resolution
├─ Cosmos DB multi-region replication
├─ Azure Data Factory pipelines
└─ ~$5,000/month
```

### Performance Optimization

**Query Performance**:
- Partition key always included in WHERE clause
- Index scan only; avoid full scans
- Batch operations in transactions
- Cosmos DB query advisor enabled

**Caching Strategy**:
```
GET /api/disputes/{id}:
  1. Check in-memory cache (1 min TTL)
  2. Query Cosmos DB if miss
  3. Cache result
  4. Return to client
  
Invalidation: POST operations clear cache
```

**Connection Pooling**:
```python
# Reuse Cosmos client across function invocations
cosmos_client = CosmosClient(connection_string)
disputes_container = cosmos_client.get_database_client('disputes').get_container_client('disputes')

# Pool connections for HTTP calls
session = requests.Session()
session.mount('https://', HTTPAdapter(max_retries=3))
```

---

## Deployment Architecture

### CI/CD Pipeline (GitHub Actions)

```
git push to main
    ↓
[GitHub Actions Workflow: ci.yml]
    ├─ Trigger: pull_request, push to main/develop
    │
    ├─ Job 1: Validate
    │  ├─ Run linters (pylint, eslint)
    │  ├─ Type checking (mypy, tsc)
    │  └─ Unit tests (pytest, jest)
    │
    ├─ Job 2: Build
    │  ├─ Build Python functions
    │  ├─ Build React SPA
    │  └─ Generate artifact packages
    │
    ├─ Job 3: Deploy (main only)
    │  ├─ Azure Login (OIDC federation)
    │  ├─ azd provision (infrastructure)
    │  ├─ azd deploy (code)
    │  ├─ Run smoke tests
    │  └─ Notify Slack
    │
    └─ Job 4: Archive (on success)
       └─ Store artifacts for rollback
```

### Infrastructure as Code (Bicep)

```bicep
@description('Deploy Payment Disputes Resolution platform')
param environment string = 'dev'
param location string = 'eastus'

// Computed values
var uniqueSuffix = uniqueString(resourceGroup().id)
var apiName = 'func-${environment}-${uniqueSuffix}'
var storageName = 'st${uniqueSuffix}'
var cosmosName = 'cosmos-${environment}-${uniqueSuffix}'

// Storage Account
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

// Cosmos DB
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-09-15' = {
  name: cosmosName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    // ... more config
  }
}

// Functions
resource functionApp 'Microsoft.Web/sites@2023-01-01' = {
  name: apiName
  location: location
  kind: 'functionapp,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: appServicePlan.id
    // ... more config
  }
}
```

### Rollback Procedure

```bash
# If deployment fails or issues found:

# Option 1: Revert to previous version
git revert HEAD
git push origin main
# CI/CD automatically redeploys previous version

# Option 2: Emergency rollback (manual)
azd down  # Remove all resources
azd up    # Redeploy from bicep
```

---

## Monitoring & Observability

### Application Insights Instrumentation

```python
from azure.monitor.opentelemetry import configure_azure_monitor

configure_azure_monitor(
    connection_string=os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
)

# Auto-instrumentation logs:
# - HTTP requests (latency, errors)
# - Cosmos DB queries (RU consumption)
# - Exception traces
# - Dependency calls (Blob, Foundry, etc.)
```

### Key Metrics to Track

| Metric | Alert Threshold |
|--------|-----------------|
| API error rate | >5% per minute |
| Cosmos DB throttling (429) | >10 per hour |
| AI scoring timeout (>30s) | >20% of requests |
| Dispute SLA exceeded | >5% of disputes |
| Analyst queue wait time | >1 hour (median) |

### Dashboards

**Operations Dashboard**:
- Request volume (real-time)
- Error rate by endpoint
- Cosmos DB RU consumption
- Function app cold starts

**Business Dashboard**:
- Disputes created (daily)
- Average time to decision (by status)
- Approval rate (by reason code)
- Dispute value (total and average)
- AI model accuracy vs. actual outcome (Phase 2)

---

## Known Limitations & Constraints

| Constraint | Phase 1 | Phase 2 | Reason |
|-----------|---------|---------|--------|
| **Multi-region** | Single (eastus) | Active-active | Compliance & HA |
| **Auth** | Function key | Entra ID + RBAC | Security hardening |
| **AI Models** | Foundry (limited) | Multiple models | Resilience & accuracy |
| **Auto-submit** | Manual | Automated | Regulatory approval needed |
| **Evidence upload** | 25 MB limit | 100 MB | Storage & compliance |
| **Concurrent users** | ~50 | ~1000 | Cosmos DB scaling |
| **Merchant response** | Not supported | Webhook-driven | Network integration required |

---

## Reference Links

- [API Implementation](../../src/api/function_app.py)
- [Durable Functions](../../src/api/orchestrator/dispute_orchestrator.py)
- [React Components](../../src/web/src/components/)
- [Infrastructure as Code](../../infra/main.bicep)
- [Data Schema](../../src/shared/schemas/case.schema.json)
- [Architectural Decisions](../../.squad/decisions.md)
- [Full Architecture Reference](../../docs/architecture.md)

