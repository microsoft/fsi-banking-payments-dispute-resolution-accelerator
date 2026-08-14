# Payment Disputes Platform — Team Handoff

**Date:** July 11, 2026  
**Author:** Danna Nemeth  
**Repo:** [yortch/payment-disputes](https://github.com/yortch/payment-disputes)  
**Branch:** `main` (all branches in sync: `main`, `develop`, `DN_work` at commit `bcedb56`)

---

## 1. What Is This?

A full-stack payment disputes management platform with:
- **Analyst Portal** — React SPA for internal dispute analysts to triage, investigate, and resolve chargebacks
- **Customer Portal** — React SPA for cardholders to view transactions and file disputes
- **API Backend** — Python Azure Functions (v2, Durable) handling case lifecycle, document uploads, evidence retrieval, and AI-assisted recommendations
- **Infrastructure** — Bicep IaC deployed via Azure Developer CLI (`azd`)

---

## 2. Architecture

```
┌──────────────────────┐     ┌──────────────────────┐
│  Analyst Portal (SWA)│     │ Customer Portal (SWA) │
│  witty-bush-...      │     │ witty-beach-...       │
└──────────┬───────────┘     └──────────┬────────────┘
           │                            │
           └─────────┬──────────────────┘
                     ▼
        ┌────────────────────────┐
        │  Azure Functions (Flex)│
        │  func-qqvftbiyd7fmk    │
        └────────┬───────────────┘
                 │
     ┌───────────┼───────────────┐
     ▼           ▼               ▼
┌─────────┐ ┌──────────┐ ┌────────────────┐
│Cosmos DB│ │Blob Store│ │Azure AI Services│
│disputes │ │documents │ │(Doc Intel, OAI) │
└─────────┘ └──────────┘ └────────────────┘
```

---

## 3. Deployed Environments

| Service | URL | Azure Resource |
|---------|-----|----------------|
| Analyst Portal | https://witty-bush-0a79bbf1e.7.azurestaticapps.net/ | Static Web App |
| Customer Portal | https://witty-beach-03ee6071e.7.azurestaticapps.net/ | Static Web App |
| API | https://func-qqvftbiyd7fmk-app.azurewebsites.net/api/ | Function App (Flex Consumption) |

- **Subscription:** `<AZURE_SUBSCRIPTION_ID>`
- **Resource Group:** `rg-payment-disputes`

---

## 4. Project Structure

```
payment-disputes/
├── azure.yaml              # azd service definitions (api, web, portal)
├── infra/                  # Bicep IaC
│   ├── main.bicep
│   └── modules/            # cosmos, functions, staticwebapp, storage, ai, etc.
├── src/
│   ├── api/                # Python Azure Functions backend
│   │   ├── function_app.py       # App entry point + route registrations
│   │   ├── triggers/             # HTTP trigger blueprints
│   │   │   ├── case_actions.py   # POST approve/deny/escalate/add-note + doc upload
│   │   │   ├── case_read.py      # GET cases, case detail, timeline
│   │   │   ├── pl_ingest_raw.py  # Dispute intake pipeline
│   │   │   └── pl_master_refresh.py
│   │   ├── services/             # Business logic
│   │   │   ├── case_store.py           # Case CRUD (synthetic or Cosmos)
│   │   │   ├── document_service.py     # Blob upload + metadata
│   │   │   ├── evidence_retrieval.py   # AI evidence fetching
│   │   │   ├── reason_code_engine.py   # Network reason code rules
│   │   │   └── triage_agent_client.py  # AI triage agent integration
│   │   ├── orchestrator/        # Durable Functions orchestrator
│   │   ├── activities/           # Durable activity functions
│   │   ├── cosmos_client.py      # Cosmos DB client wrapper
│   │   ├── cosmos_models.py      # Data models
│   │   └── requirements.txt
│   ├── web/                # Analyst Portal (React + Vite + Fluent UI)
│   │   └── src/
│   │       ├── pages/            # DashboardPage, QueuePage, CaseDetailPage, ExecutiveMetricsPage
│   │       ├── components/       # 23 components (ActionBar, TimelinePanel, CollaborationWorkspace, etc.)
│   │       ├── api/cases.ts      # API client functions
│   │       └── types/case.ts     # TypeScript type definitions
│   ├── customer-portal/    # Customer-facing dispute filing portal
│   └── data/               # Synthetic test data fixtures
└── HANDOFF.md              # This file
```

---

## 5. How to Run Locally

### Prerequisites
- Node.js 18+
- Python 3.11+
- Azure Functions Core Tools v4
- Azure Developer CLI (`azd`) — optional for deploy

### API (backend)

```bash
cd src/api
cp local.settings.json.sample local.settings.json
# Edit local.settings.json — set CASE_STORE=synthetic for demo mode (no Cosmos needed)
python -m venv .venv
.venv/Scripts/activate  # Windows
pip install -r requirements.txt
func start
```

The API runs on `http://localhost:7071`. With `CASE_STORE=synthetic`, it serves 10 fixture cases with no external dependencies.

### Analyst Portal (web)

```bash
cd src/web
npm install
npm run dev
```

Runs on `http://localhost:5173`. Proxies API calls to `localhost:7071` (configured in vite.config.ts).

### Customer Portal

```bash
cd src/customer-portal
npm install
npm run dev
```

Runs on `http://localhost:5174`.

---

## 6. How to Deploy

```powershell
cd payment-disputes
$env:AZD_SKIP_FIRST_RUN = "true"

# Deploy everything
azd deploy

# Deploy a single service
azd deploy --service api     # Backend
azd deploy --service web     # Analyst portal
azd deploy --service portal  # Customer portal

# Full provision + deploy (creates Azure resources)
azd up
```

---

## 7. What's Been Completed

### Analyst Portal Features
| Feature | Status | Key Files |
|---------|--------|-----------|
| Case queue with filtering/sorting | ✅ Done | `QueuePage.tsx`, `CaseTable.tsx` |
| Case detail page (full layout) | ✅ Done | `CaseDetailPage.tsx` |
| Timeline panel (categorized, collapsible) | ✅ Done | `TimelinePanel.tsx` |
| Win probability gauge | ✅ Done | `WinProbGauge.tsx` |
| AI recommendations panel | ✅ Done | `AIRecommendationsPanel.tsx` |
| Evidence panel + evidence gaps | ✅ Done | `EvidencePanel.tsx`, `EvidenceGapsPanel.tsx` |
| Reason code guidance + checklist | ✅ Done | `ReasonCodeGuidance.tsx`, `ReasonCodeChecklist.tsx` |
| Decision actions (Approve/Deny/Escalate) | ✅ Done | `ActionBar.tsx` |
| Add Note (Update button) | ✅ Done | `ActionBar.tsx` → `postNote` API |
| Notes visible in Collaboration Workspace | ✅ Done | `CollaborationWorkspace.tsx` (wired to API) |
| Document upload (file + metadata) | ✅ Done | `DocumentUploadPanel.tsx` |
| SLA deadline countdown + toast warnings | ✅ Done | `DeadlineCountdown.tsx`, `SLAProgressBar.tsx` |
| Rebuttal letter panel | ✅ Done | `RebuttalPanel.tsx` |
| Related cases panel | ✅ Done | `RelatedCasesPanel.tsx` |
| Decision insights (AI summary) | ✅ Done | `DecisionInsights.tsx` |
| Dark/light mode toggle | ✅ Done | `AnalystHeader.tsx` |
| Toast notifications system | ✅ Done | `NotificationProvider.tsx` |
| Executive metrics dashboard | ✅ Done | `ExecutiveMetricsPage.tsx` |

### Customer Portal Features
| Feature | Status |
|---------|--------|
| Transaction list view | ✅ Done |
| Select transaction to dispute | ✅ Done |
| Dispute filing flow | ✅ Done |
| Dispute status tracking page | ✅ Done |

### API / Backend
| Feature | Status |
|---------|--------|
| Case CRUD (synthetic + Cosmos modes) | ✅ Done |
| Approve/Deny/Escalate actions | ✅ Done |
| Add-note endpoint (`POST /api/cases/{caseId}/add-note`) | ✅ Done |
| Document upload/list (`POST/GET /api/cases/{caseId}/documents`) | ✅ Done |
| Timeline events (Cosmos persistence) | ✅ Done |
| Reason code engine (Visa, Mastercard, Amex, Discover) | ✅ Done |
| Evidence retrieval service | ✅ Done |
| Triage agent client (AI-powered) | ✅ Done |
| Durable orchestration (dispute lifecycle) | ✅ Done |
| Dispute intake pipeline | ✅ Done |
| Read-only filesystem handling (Flex Consumption) | ✅ Fixed |

### Infrastructure
| Component | Status |
|-----------|--------|
| Cosmos DB (disputes-db) | ✅ Provisioned |
| Blob Storage (documents) | ✅ Provisioned |
| Azure Functions (Flex Consumption) | ✅ Provisioned |
| Static Web Apps (×2) | ✅ Provisioned |
| Azure AI Services | ✅ Provisioned |
| Key Vault | ✅ Provisioned |
| VNet + Private Endpoints | ✅ Provisioned |
| Event Grid | ✅ Provisioned |
| Monitoring (App Insights) | ✅ Provisioned |
| EasyAuth race-condition fix (postprovision hook) | ✅ Implemented |

### Bugs Fixed
- HTTP 500 on document upload (read-only filesystem in Flex Consumption)
- `NoneType` error when `winProbability` is null in Cosmos
- Update button not clickable (was incorrectly disabled)
- Customer portal 404s on fresh transactions

---

## 8. What's Left To Do

### High Priority
1. **Durable orchestration end-to-end testing** — The Durable Functions binding was removed from `case_actions.py` due to host-level 500s on Flex Consumption (see module docstring). Status persistence works; durable signaling is best-effort via HTTP webhook. Needs investigation on whether Flex Consumption fully supports Durable Python v2.

2. **Live Cosmos mode testing** — Most development used `CASE_STORE=synthetic`. Switch to `cosmos` mode and verify:
   - Timeline events persist and round-trip correctly
   - Document metadata writes to Cosmos
   - Case status transitions are durable

3. **Customer Portal ↔ API integration** — The customer portal's dispute-filing flow currently uses mocks. Wire it to the real `POST /api/disputes` intake endpoint.

4. **Authentication/Authorization** — EasyAuth is configured at the infra level but the app doesn't enforce analyst identity from tokens. Add:
   - Extract analyst identity from `X-MS-CLIENT-PRINCIPAL` header
   - Role-based access (analyst vs. manager vs. read-only)

### Medium Priority
5. **Triage Agent integration** — `triage_agent_client.py` is scaffolded. Connect to Azure AI Foundry agent for automated case triage and priority scoring.

6. **Evidence retrieval from real sources** — `evidence_retrieval.py` has the framework; wire to actual data sources (transaction processor feeds, merchant APIs, etc.).

7. **Pipeline triggers** — `pl_ingest_raw.py` and `pl_master_refresh.py` are defined but need Event Grid subscriptions or timer triggers configured to run in production.

8. **E2E / Integration tests** — Playwright config exists (`test:e2e` script) but no test files. Write critical-path tests:
   - Case detail loads and renders
   - Approve/Deny flow
   - Document upload
   - Customer dispute filing

### Low Priority / Polish
9. **Performance** — The JS bundle is 1.15 MB (gzip 326 KB). Add code-splitting with dynamic imports for the detail page components.

10. **Inline styles → CSS modules** — Lint rule flags all inline styles. Migrate to CSS modules or Griffel (Fluent UI's CSS-in-JS).

11. **Collaboration Workspace** — Tasks/Audit tabs are populated with mock data. Wire to real assignment and audit trail APIs.

12. **Assign Route Panel** — Currently client-side only. Persist analyst assignments to Cosmos when changed.

---

## 9. Additional Suggestions

### Architecture Improvements
- **API versioning** — Add `/api/v1/` prefix now before clients are hardcoded to current paths
- **Rate limiting** — No throttling on the Function App; consider APIM front-door or Azure Functions built-in limits
- **Idempotency** — Action endpoints (approve/deny) should be idempotent; add optimistic concurrency with ETags from Cosmos

### Developer Experience
- **CI/CD pipeline** — No GitHub Actions workflow exists yet. Create `.github/workflows/cd.yml` using `azd deploy` in the pipeline
- **Environment separation** — Single `rg-payment-disputes` resource group serves as prod. Add dev/staging environments via `azd env`
- **Seed data script** — `src/data/` has synthetic fixtures; create a script to bulk-load them into a fresh Cosmos instance

### AI/ML Enhancements
- **Win probability model** — Currently returns static values. Train on historical dispute outcomes for real predictions
- **Auto-rebuttal generation** — `RebuttalPanel.tsx` shows AI-generated letters; connect to Azure OpenAI with case context as prompt
- **Smart evidence gaps** — Use Document Intelligence to analyze uploaded docs and automatically check off evidence checklist items

### Observability
- **Structured logging** — Backend uses basic `logging.info()`. Add correlation IDs and structured JSON logging
- **Custom metrics** — Track: disputes resolved per hour, average time-to-resolution, evidence gap closure rate
- **Alerting** — Set up App Insights alerts for SLA breaches (cases past deadline with no action)

---

## 10. Key Technical Decisions (for context)

| Decision | Rationale |
|----------|-----------|
| Removed Durable client binding from action routes | Flex Consumption causes host-level 500 before Python executes; status persistence via direct Cosmos write is the critical path |
| `CASE_STORE=synthetic` mode | Enables fully offline development with zero Azure dependencies |
| Inline styles (not CSS modules) | Rapid prototyping priority; flagged as tech debt |
| `analyst_note` event type added | Distinct from `comment_added` (which comes from action decisions); allows filtering notes vs. decision comments |
| Fluent UI v9 | Aligns with Microsoft design system; consistent with internal tooling |

---

## 11. Contacts

- **Danna Nemeth** — Built the full stack, available for questions
- **Repo owner:** yortch (GitHub)
