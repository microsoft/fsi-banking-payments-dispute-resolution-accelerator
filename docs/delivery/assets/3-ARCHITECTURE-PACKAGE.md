# 3. Architecture Package

## Reference Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Azure Static Web Apps                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Customer Portal (React/TS) + Analyst Portal (React)    │   │
│  │  - Dispute intake                                        │   │
│  │  - Case queue with sorting                              │   │
│  │  - Timeline view                                        │   │
│  │  - Evidence upload / review                             │   │
│  │  - Cancel button                                        │   │
│  └─────────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS REST API
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│            Azure Functions (Python FastAPI)                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ POST /disputes (intake)                                 │   │
│  │ POST /disputes/{id}/customer-response                   │   │
│  │ POST /disputes/{id}/cancel                              │   │
│  │ POST /disputes/{id}/retrieve-evidence (AI trigger)      │   │
│  │ POST /disputes/{id}/score (AI scoring service)          │   │
│  │ POST /disputes/{id}/draft-rebuttal (AI maker agent)     │   │
│  │ POST /disputes/{id}/detect-gaps (AI gap analysis)       │   │
│  │ POST /disputes/{id}/reprocess (Phase 2)                 │   │
│  │ GET /disputes/{id}, GET /disputes/{id}/timeline         │   │
│  └─────────────────────────────────────────────────────────┘   │
└──────────┬───────────────────────┬───────────────────────┬──────┘
           │                       │                       │
    ┌──────▼──────┐        ┌──────▼──────┐        ┌──────▼──────┐
    │  Cosmos DB  │        │ Blob Storage│        │  Foundry    │
    │ (NoSQL)     │        │ (Artifacts) │        │  Agents     │
    │ - Disputes  │        │ - Evidence  │        │ - Scorer    │
    │ - Timeline  │        │ - Uploads   │        │ - Maker     │
    │  Events     │        │ - Rebuttals │        │ - Evidence  │
    └─────────────┘        └─────────────┘        └─────────────┘
           ▲
           │ Connection String (MSI)
           │
    ┌──────────────────────────────────────────────┐
    │  Azure Key Vault                             │
    │  - cosmos-connection-string                  │
    │  - storage-account-key                       │
    │  - foundry-api-key                           │
    └──────────────────────────────────────────────┘
```

---

## Data Flow Diagrams

### Flow 1: Customer Initiates Dispute
```
Customer Portal (intake form)
    ↓
    POST /api/disputes
        ↓
    Validate dispute input
    Upload evidence to Blob Storage (artifact versioning: {timestamp}_{customerid}_{filename})
    ↓
    Persist dispute doc to Cosmos DB (status='intake')
    Write timeline event (type='dispute_intake')
    ↓
    Response: {"disputeId": "...", "status": "intake", "evidence": [...]}
    ↓
    Customer Portal updates: Shows "Case submitted" + case ID in timeline
```

### Flow 2: Analyst Views Queue
```
Analyst Portal: GET /api/disputes?tab=open
    ↓
    Query Cosmos: SELECT * FROM disputes WHERE status IN ('intake', 'evidence_gathering', 'pending_review')
    Sort client-side by column (deadline, merchant, amount, status)
    ↓
    Response: Array of 50 disputes with summary
    ↓
    Analyst Portal renders table
    Analyst clicks column header to re-sort
```

### Flow 3: Analyst Requests AI Score
```
Analyst clicks "Score Case" button
    ↓
    POST /api/disputes/{id}/score
        ↓
        Load dispute + evidence from Cosmos + Blob
        Call Foundry scoring agent:
            Input: {dispute, evidence_items, merchant_type}
            Output: {win_probability: 0.78, risk_level: "low", reasoning: "..."}
        ↓
        Update Cosmos dispute doc: score_result = {...}, status='pending_review'
        Write timeline event (type='ai_score_computed')
        ↓
    Response: {score: 0.78, risk: "low"}
    ↓
    Analyst Portal refreshes: Shows updated score in case detail
```

### Flow 4: Customer Cancels Dispute
```
Customer Portal: Clicks "Cancel Dispute"
    ↓
    Confirmation dialog: "Are you sure? Reason?"
    Customer enters reason: "Merchant refunded the charge"
    ↓
    POST /api/disputes/{id}/cancel
        ↓
        Validate: dispute status is NOT 'closed', 'approved', 'denied'
        Update Cosmos: status='closed'
        Write timeline event (type='customer_cancellation', detail=reason)
        ↓
    Response: {"status": "closed", "message": "Dispute cancelled"}
    ↓
    Customer Portal: Updates to "Closed - Cancelled by customer"
    ↓
    Analyst Portal: Case auto-removed from Open tabs, appears in Closed tab
```

### Flow 5: Phase 2 - Auto-Reprocess on Upload (Future)
```
Customer uploads new evidence
    ↓
    POST /api/disputes/{id}/customer-response
        ↓
        Save response + evidence to Cosmos + Blob
        [NEW] Trigger reprocess chain:
            Call /api/disputes/{id}/retrieve-evidence (refresh evidence list)
            Call /api/disputes/{id}/detect-gaps (update gap analysis)
            IF gaps_closed OR quality_improved:
                Call /api/disputes/{id}/score (re-score case)
                IF score_changed:
                    Call /api/disputes/{id}/draft-rebuttal (regenerate rebuttal)
        ↓
    Response: {"status": "response_recorded", "reanalysis": {...}}
    ↓
    Both portals refresh on next load: See updated score + rebuttal
```

---

## Service Selection & Rationale

| Component | Chosen Service | Why | Alternatives Considered |
|---|---|---|---|
| **Portal UI** | Azure Static Web Apps | Cheap, auto-HTTPS, built-in auth, fast CDN | App Service (overengineered), Netlify (multi-cloud lock-in) |
| **Backend API** | Azure Functions | Stateless, scales auto, FastAPI simplifies routing, perfect for short-lived AI calls | App Service (overkill), Logic Apps (not code-native) |
| **Primary Data Store** | Cosmos DB (NoSQL) | Schema flexibility (disputes vary), natural timeline as audit log, 1ms latency, ideal for NoSQL queries | SQL Server (over-normalized for this use case), Firebase (vendor lock-in, less control) |
| **Artifact Storage** | Azure Blob Storage | Cheap, versioning built-in, integrates with AI pipelines, high throughput | File Share (slower), Database BLOBs (expensive) |
| **AI Inference** | Foundry Agents | Managed service, no GPU provisioning, batch-friendly for cost efficiency | Custom LLM (expensive infrastructure), AWS Sagemaker (cloud lock-in) |
| **Secrets Management** | Azure Key Vault | RBAC-integrated, audit logging, rotation policies, Managed Identity compatible | Environment variables (security risk), hardcoded (NO) |
| **Infrastructure as Code** | Bicep | Azure-native, readable, version-controlled, easy iteration | Terraform (multi-cloud but more verbose), ARM Templates (JSON, hard to read) |
| **Deployment** | Azure Dev CLI (azd) | One-command deploy, automatic provisioning, IaC handling, team-friendly | Manual Azure Portal (error-prone), Terraform CLI (more steps) |

---

## Integration Points

### 1. Customer Portal ↔ Azure Functions
- **Protocol**: HTTPS REST
- **Auth**: Optional (MVP: none, Phase 2: Entra ID)
- **Endpoints**: `/disputes` (POST), `/disputes/{id}/customer-response` (POST), `/disputes/{id}/cancel` (POST), `/disputes/{id}` (GET)
- **Rate Limit**: 100 req/min per customer IP

### 2. Analyst Portal ↔ Azure Functions
- **Protocol**: HTTPS REST
- **Auth**: Phase 2 - Entra ID + RBAC
- **Endpoints**: `/disputes` (GET list), `/disputes/{id}` (GET detail), `/disputes/{id}/score` (POST), `/disputes/{id}/draft-rebuttal` (POST), `/disputes/{id}/detect-gaps` (POST)
- **Rate Limit**: 1000 req/min per analyst user

### 3. Azure Functions ↔ Cosmos DB
- **Connection**: Managed Identity (no keys in code)
- **Queries**: Parameterized (prevents injection)
- **Consistency**: Strong (all reads see latest writes)
- **Throughput**: Autopilot (0-40,000 RU/s)

### 4. Azure Functions ↔ Blob Storage
- **Connection**: Managed Identity + SAS tokens for temp access
- **Retention**: 90-day lifecycle policy (auto-delete old artifacts)
- **Versioning**: Enabled (can roll back evidence if needed)

### 5. Azure Functions ↔ Foundry Agents
- **Connection**: HTTPS + API key (from Key Vault)
- **Batch Size**: 10 disputes per batch (cost optimization)
- **Timeout**: 30s per request (agent should respond within SLA)
- **Fallback**: If agent unavailable, return cached score or "pending"

### 6. Both Portals ↔ Entra ID (Phase 2)
- **SSO Protocol**: OAuth 2.0 / OpenID Connect
- **Token Expiry**: 1 hour
- **Refresh**: Automatic via refresh token

---

## Key Tradeoffs

| Decision | Chosen | Alternative | Tradeoff |
|---|---|---|---|
| **Real-time sync** | Polling on page load | WebSockets / Service Bus / SignalR | **MVP**: Simpler code, lower cost. **Phase 2**: Can add event-driven if needed. |
| **AI trigger model** | Manual (analyst button-click) | Auto on evidence upload | **MVP**: Analyst controls cost + decisions. **Phase 2**: Auto-trigger for better UX. |
| **Data consistency** | Strong (wait for writes) | Eventual (fast writes) | **Need**: Analysts see latest decision immediately. **Cost**: Slightly higher latency (10ms). |
| **Multi-region** | Single region (current) | Multi-region failover | **MVP**: Simpler, cheaper. **Phase 2**: Add if SLA demands <99.9%. |
| **Auth** | Optional (dev: anon) | Mandatory | **MVP**: Focus on features. **Phase 2**: Enforce Entra ID for security. |
| **Deployment** | azd + Bicep | Manual portal clicks | **Gain**: Repeatable, version-controlled, team scalable. **Learning curve**: Bicep syntax. |
| **AI model** | Foundry agents (inference) | Fine-tuned LLM on-site | **Choose Foundry**: No GPU provisioning, cost-efficient. **Alternative**: Full control but infrastructure burden. |

---

## Scalability

### Current Limits (MVP)
- **Concurrent Users**: 100 (mostly async, not holding connections)
- **Cases/sec**: 10 (typical SaaS throughput, limits: Cosmos + Foundry batching)
- **Storage**: 50GB (5000 disputes × 10MB avg per case with evidence)

### Phase 1 Targets (10x growth)
- **Concurrent Users**: 1000
- **Cases/sec**: 100 (peak at 200)
- **Storage**: 500GB

### Scaling Strategy
1. **API**: Autoscaling Functions (monitor CPU, scale out to 10+ instances)
2. **Database**: Cosmos autopilot scaling (monitor RU consumption, auto-adjust to 40K RU/s max if needed)
3. **Storage**: No scaling needed (blob storage is unlimited, pricing is linear)
4. **Foundry**: Batch 20 disputes per request (vs 10 now), amortize latency

---

## Deployment Architecture

```
Developer (local)
    ↓ git push main
GitHub
    ↓ webhook trigger (optional, manual for MVP)
GitHub Actions (CI/CD)
    ├─ npm run build (portals)
    ├─ pytest src/api/ (unit tests)
    ├─ azd validate (IaC validation)
    ↓
    azd deploy
        ├─ Build Functions app (Python)
        ├─ Deploy SWAs (React bundles)
        ├─ Verify Cosmos, Storage, Key Vault
        └─ Run smoke tests
    ↓
Production (Azure)
    ├─ Analyst Portal: https://{env}-web.azurestaticapps.net
    ├─ Customer Portal: https://{env}-portal.azurestaticapps.net
    └─ API: https://{env}-api.azurewebsites.net/api
```

---

**Document Version**: 1.0 | **Last Updated**: 2026-07-22
