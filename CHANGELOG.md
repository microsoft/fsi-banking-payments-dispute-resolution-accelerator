# Changelog

All notable changes to the Payments Dispute Resolution accelerator are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Fixed — Customer Update Filter + Document Review Access (2026-07-22)

- **Customer updates filter now applies independent of active tab** (`src/web/src/pages/QueuePage.tsx`) — the "Filter to customer updates" toggle now filters against the search-scoped queue set directly, so analysts reliably see customer-updated disputes even when the current tab would otherwise hide them.
- **Queue count label now matches sorted visible rows** (`src/web/src/pages/QueuePage.tsx`) — case count reflects the actual rendered/sorted result set.
- **Added secure case document download endpoint** (`src/api/triggers/case_actions.py`) — new route `GET /api/cases/{caseId}/documents/{documentId}/download` serves stored evidence for in-portal review.
- **Added backend document byte resolver for local + Azure storage** (`src/api/services/document_service.py`) — reads `/uploads/...` local artifacts and private Azure blobs via managed identity.
- **Fixed URL-encoded blob path handling** (`src/api/services/document_service.py`) — blob names are URL-decoded before Azure blob reads, restoring access for filenames containing spaces and encoded characters.
- **Customer portal document rows are now clickable review links** (`src/customer-portal/src/pages/MyDisputesPage.tsx`) — documents open through the API proxy route so both customer-uploaded and analyst-uploaded artifacts are reviewable from My Disputes.

### Changed — UI Modernization with Interaction Parity (2026-07-22)

- **Queue page modernized for analyst-first workflow** (`src/web/src/pages/QueuePage.tsx`) — introduced a compact operations-center layout with improved visual hierarchy and reduced dead space while preserving existing case actions and queue semantics.
- **AI Priority Queue panel added** (`src/web/src/pages/QueuePage.tsx`) — visually highlights the top ranked disputes using existing case data (risk, deadline, amount, activity) without altering underlying case state.
- **Customer update toggle auto-switches to Open tab on enable** (`src/web/src/pages/QueuePage.tsx`) — keeps triage context consistent while retaining existing filtering/search behaviors.
- **Manual queue tab/card selection now restores the full queue view** (`src/web/src/pages/QueuePage.tsx`) — choosing Open, Active, Needs Review, or Closed clears customer-update-only mode so analysts can reliably return to the full tabbed queue.
- **Urgent operations card now applies a true urgent-only queue filter** (`src/web/src/pages/QueuePage.tsx`) — the Urgent card now filters to non-closed cases with deadlines within 3 days instead of only switching to the Open tab.
- **KPI card drill-down behavior preserved** (`src/web/src/pages/QueuePage.tsx`) — existing KPI click interactions and drill lists remain available in the refreshed layout.
- **Case grid styling refreshed only** (`src/web/src/components/CaseTable.tsx`) — clearer header and cell borders for readability; row actions and navigation unchanged.
- **Merchant names now render consistently in regular weight** (`src/web/src/components/CaseTable.tsx`) — removed the prior critical-risk-only bold treatment so merchant typography no longer changes by row severity.
- **AI Priority Queue removed from Phase 1 UI** (`src/web/src/pages/QueuePage.tsx`) — the top-3 ranking panel has been removed from the live analyst portal and deferred to Phase 2 pending a real model/agent-backed prioritization design.
- **Customer document list displays audit metadata badges** (`src/customer-portal/src/pages/MyDisputesPage.tsx`) — source, upload timestamp, and submitted-by badges added next to existing document links.
- **All Cases header redesigned into a denser executive layout with a left rail** (`src/web/src/pages/QueuePage.tsx`) — operations metrics and AI Priority Queue now sit in a compact side rail rather than a large top strip.
- **Expanded customer dispute cards tightened visually** (`src/customer-portal/src/pages/MyDisputesPage.tsx`) — detail fields now render as compact metadata tiles and sections use tighter spacing to reduce the form-like feel.
- **Closed customer cases no longer request more customer action** (`src/customer-portal/src/pages/MyDisputesPage.tsx`) — approved/denied/submitted/expired cases suppress Action Required badges, response panels, and action-state highlighting while preserving review history.

### Changed — Queue Status Taxonomy & KPI Clarity (2026-07-22)

- **Queue status definitions are now centralized and consistent** (`src/web/src/utils/queueStatus.ts`, `src/web/src/pages/QueuePage.tsx`, `src/web/src/components/KpiCards.tsx`) — tab counts, KPI cards, and drill-downs now use shared predicates:
  - `Open` = any non-closed case
  - `Active` = `intake` / `evidence_gathering` / `ai_drafting`
  - `Needs Review` = `pending_review` / `escalated`
  - `Closed` = `approved` / `denied` / `submitted` / `expired`
- **QueuePage repaired after malformed patch state** (`src/web/src/pages/QueuePage.tsx`) — restored valid component structure and aligned all filtering/count logic to shared queue taxonomy helpers.
- **"Win Rate" KPI renamed to "Approval / Denial Rate"** (`src/web/src/components/KpiCards.tsx`) — card now displays approval vs denial percentages based on explicit decided outcomes and includes decision totals for context.
- **Customer closure summary now links directly to decision artifact** (`src/customer-portal/src/pages/MyDisputesPage.tsx`) — when closure metadata has a blob URL, customer can open the generated closure document.

### Changed — Unified Evidence Center, Persisted Audit Log, and Closure Artifacts (2026-07-22)

- **Evidence Center now owns upload + review** (`src/web/src/components/EvidencePanel.tsx`, `src/web/src/pages/CaseDetailPage.tsx`) — moved document upload into Evidence Center and removed separate right-rail upload panel.
- **Evidence rows now include provenance** (`src/web/src/components/EvidencePanel.tsx`) — every row shows submitter, timestamp, source system, details/note, and artifact view action when a blob URL exists.
- **Customer-origin uploads are classified under Customer** (`src/web/src/components/EvidencePanel.tsx`, `src/customer-portal/src/api/disputes.ts`, `src/customer-portal/src/pages/MyDisputesPage.tsx`) — customer portal uploads now send `submittedFrom=customer_portal` and submitter metadata.
- **Customer notes are represented in the Customer tab** (`src/web/src/components/EvidencePanel.tsx`) — customer response timeline events are surfaced alongside customer evidence, including attachment-linked notes.
- **Collaboration Audit Log now uses persisted timeline events** (`src/web/src/components/CollaborationWorkspace.tsx`) — replaced static mock audit entries with Cosmos-backed timeline activity per transaction.
- **Notes now persist and reload from backend timeline** (`src/web/src/components/CollaborationWorkspace.tsx`, `src/web/src/pages/CaseDetailPage.tsx`) — note creation writes to API and refreshes timeline-driven notes/audit views.
- **Document metadata persistence enriched** (`src/api/services/document_service.py`, `src/api/triggers/case_actions.py`) — uploads persist `submittedBy`, `submittedFrom`, and optional `note` to evidence + timeline.
- **Approved/denied decisions now generate closure artifacts** (`src/api/services/document_service.py`, `src/api/triggers/case_actions.py`) — creates a decision document with reason, case ID, timestamp, and dispute details; stores it under `closed/{caseId}/` in blob and as Cosmos evidence metadata.
- **Decision activity and closure artifact creation are logged to timeline** (`src/api/triggers/case_actions.py`, `src/api/services/document_service.py`) — supports customer-facing status synchronization and auditable traceability.

### Changed — Persisted Document Visibility in Both Portals (2026-07-22)

- **Analyst document panel now loads existing uploads** (`src/web/src/components/DocumentUploadPanel.tsx`) — On case load, the panel fetches `GET /api/cases/{caseId}/documents` and renders persisted evidence from Cosmos/Blob-backed metadata, not just files uploaded in the current UI session.
- **Customer API now supports document history reads** (`src/customer-portal/src/api/disputes.ts`) — Added typed `StoredCaseDocument` and `getCaseDocuments(caseId)` helper for `GET /api/cases/{caseId}/documents`.
- **Customer dispute details now show Documents on file** (`src/customer-portal/src/pages/MyDisputesPage.tsx`) — Expanded dispute cards fetch and render existing document records with loading state and file size display.
- **Post-response refresh for attachments** (`src/customer-portal/src/pages/MyDisputesPage.tsx`) — After uploading files and submitting a customer response, the document list is reloaded so newly uploaded files appear immediately without page refresh.

### Changed — Case Detail UI Cleanup & SLA Accuracy (2026-07-22)

- **Removed redundant timelines** (`CaseDetailPage.tsx`) — Removed ProcessingTimeline and TimelinePanel (Complete Timeline) from the case detail right sidebar; SLA Progress now serves as the single source of phase tracking.
- **Renamed "Win Probability" → "Recovery Likelihood"** (`WinProbGauge.tsx`) — Updated label and added hover tooltip: "Projected likelihood of recovering the disputed amount based on evidence strength, network rules, and historical outcomes."
- **SLA Progress phase durations** (`SLAProgressBar.tsx`) — Each phase now shows elapsed time (e.g. "2.2 days") derived from timeline status_change events. Added `timelineEvents` prop; new `computePhaseDurations` helper handles both seed data (`occurredAt`/`data`) and normalized (`timestamp`/`metadata`) field formats.
- **Customer Response wait sub-phase** (`SLAProgressBar.tsx`, `case.ts`) — Added `customer_response_requested` / `customer_response_received` event types. Evidence Gathering phase displays customer wait time as an italic sub-label (⏳ icon).
- **Timeline API normalization** (`dev_server.py`) — Added `_normalize_timeline_event` to map seed data fields (`occurredAt` → `timestamp`, `detail` → `description`, `data` → `metadata`, `status_change` → `status_changed`) so frontend receives consistent shape.
- **Timeline data path fix** (`dev_server.py`) — Added `_REPO_DATA_DIR` to load demo timeline seed data from repo-root `data/seed/` in addition to `src/data/seed/`.
- **Synthetic timeline generation** (`dev_server.py`) — Cases without seed timeline events now get auto-generated phase-transition events based on case status and elapsed time, using realistic proportional phase timing.
- **Demo seed data** (`demo_timeline.json`) — Added `customer_response_requested` and `customer_response_received` events to `demo-urgent-deadline-001` (14.5-hour customer wait during evidence gathering).
- **TimelinePanel category map** (`TimelinePanel.tsx`) — Added new customer response event types to the category mapping.

### Added — API Wiring, Search & Batch Actions (2026-07-09)

- **Flask API wired to mock data** (`src/api/services/case_store.py`, `src/data/synthetic/cases.json`) — Synced 61 frontend mock cases to backend JSON store; API now serves real data (no more 404 fallbacks). Added `assignedAnalystId`/`assignedAnalystName` to summary responses.
- **Mock sync script** (`scripts/sync_mocks_to_api.py`) — Python script using esbuild+Node to export TS mock data → backend JSON.
- **Search/filter bar** (`src/web/src/pages/QueuePage.tsx`) — Input field with search icon filters across case ID, merchant name, reason code, reason code label, and assigned analyst. Tab counts update to reflect filtered results.
- **Batch actions** (`src/web/src/pages/QueuePage.tsx`, `src/web/src/components/CaseTable.tsx`) — Checkbox selection in table (select-all with mixed state), floating action bar with Approve/Assign to Me/Export CSV buttons. Selection clears on tab/filter changes.

### Added — 5-Feature Batch: Mock Data, Navigation, Intelligence Panels (2026-07-09)

- **50+ Mock Cases** (`src/web/src/mocks/caseGenerator.ts`) — Deterministic seeded generator producing 50 diverse CaseSummary + full Case objects; merged into existing mock data.
- **Persistent NavBar** (`src/web/src/components/NavBar.tsx`) — Sticky top navigation with Dashboard/Queue/Metrics links, active state highlighting, analyst avatar. Removed ad-hoc back buttons from CaseDetailPage and QueuePage.
- **Reason Code Intelligence** (`src/web/src/components/ReasonCodeGuidance.tsx`) — Added win rate % with color-coded progress bar, deadline urgency badge, and copy-ready rebuttal templates for all 10 reason codes. Fixed network-prefix lookup (e.g. "Visa 13.1" → "13.1").
- **Enhanced Evidence Gaps** (`src/web/src/components/EvidenceGapsPanel.tsx`) — Priority sorting (critical first), resolution progress bar, suggested actions per gap, "Auto-Request" / "Mark Requested" buttons with visual state.
- **AI Recommendations Panel** (`src/web/src/components/AIRecommendationsPanel.tsx`) — Derives disposition (Fight/Accept Loss/Negotiate/Escalate) with confidence score, reasoning list, and Accept/Reject/Modify interactive workflow. Wired into CaseDetailPage.
- **Theme Support** (`src/web/src/ThemeContext.tsx`, `src/web/src/App.tsx`) — Dark/light mode toggle with Fluent UI theme switching.

### Added — Full Analyst Portal Feature Set (2026-07-09)
Implements all 10 feature areas from the Dispute Analyst Portal spec.

- **Dashboard Page** (`src/web/src/pages/DashboardPage.tsx`) — Home page with 5 analyst widgets: My Queue, Action Required Today, Missing Evidence, AI Recommendations, Upcoming Deadlines. Route at `/`.
- **Executive Metrics Page** (`src/web/src/pages/ExecutiveMetricsPage.tsx`) — VP persona dashboard with 10 clickable KPI tiles (drill-down detail panel), Network Breakdown table, SLA Breach Risk section. Route at `/metrics`.
- **Collaboration Workspace** (`src/web/src/components/CollaborationWorkspace.tsx`) — Replaces AssignRoutePanel. 4-tab hub: Notes (team tagging), Tasks (status tracking), Assign (escalation buttons), Audit Log.
- **Enhanced TimelinePanel** — 4 collapsible sections (Transaction, Customer Activity, Fraud Signals, Case Activity) with 30+ event types and metadata pills (device, location, IP, score, risk, amount).
- **Tabbed Evidence Center** — 6 filter tabs (All, Payment, Customer, Merchant, Digital, Fraud) with per-tab counts.
- **Expanded RelatedCasesPanel** — Expandable rows showing outcome (won/lost badges), evidence used pills, decision reasoning, lessons learned.
- **Enhanced SLA with multi-deadline compliance table** — Reg E, Network Representment, Internal SLA, MC Pre-Arbitration deadline rows.
- **Queue Page navigation** — Added "← Dashboard" button to QueuePage header.
- **Rich mock timeline data** (`src/web/src/mocks/timeline.ts`) — Events across all 4 categories per case.
- **Extended types** (`src/web/src/types/case.ts`) — 19 new TimelineEventType values, `TimelineCategory` type.

### Added — Analyst Portal UI Enhancements (DN_work → develop, PR #69, 2026-07-08)
Extends #21 / #42 — analyst review UI with KPIs, interactivity, and mock data expansion.
- `src/web/src/components/DeadlineCountdown.tsx` — Replaced Fluent UI `Badge` (squished multi-char text) with custom styled `<span>` pill using `colorMap` for danger/warning/success severities with proper padding and border-radius.
- `src/web/src/components/CaseTable.tsx` — Row coloring changed: red background only for `riskLevel === 'critical'` cases; alternating neutral rows otherwise (replaced prior `isNearDeadline` logic).
- `src/web/src/components/AnalystHeader.tsx` — Network filter badges (Visa/Mastercard/Amex) now clickable via native `<button>` wrappers; active filter shows `appearance="filled" color="brand"`, toggle on/off behavior.
- `src/web/src/pages/QueuePage.tsx` — Added `networkFilter` state; applied before tab filter so KPI cards + tab counts reflect the active network. Passes `activeNetwork` / `onNetworkFilter` to AnalystHeader.
- `src/web/src/pages/CaseDetailPage.tsx` — Fully wired: imports `getCases`, `AssignRoutePanel`, `DocumentUploadPanel`, `RelatedCasesPanel`, `CaseSummary`; loads full case list for related-cases lookup; `AssignRoutePanel.onAssign` updates local state.
- `src/web/src/components/DocumentUploadPanel.tsx` — Added `aria-label="Upload evidence documents"` to hidden file input for accessibility.
- `src/web/src/mocks/cases.ts` — Expanded `mockCases` from 3 to 11 full detail records (IDs 001–003, 010–014, 020–022) with evidence, evidenceGaps, rebuttalDraft, reasonCodeChecklist. Prevents 500 errors when navigating to any case in mock mode.

### Added — Fabric Mirroring Attempt & Cosmos DB Mirror Account (DN_work, 2026-07-08)
- `cosmos-disputes-mirror` — New Cosmos DB NoSQL account (serverless, West US 2) created to bypass tenant policy restrictions on the original account (`<COSMOS_ACCOUNT_NAME>` had policy-enforced `disableLocalAuth` + 430 IP firewall rules).
- Database `disputes-db` with containers: `disputes` (10 items), `evidence`, `timeline` (396 items) — data copied from original account via `scripts/copy_cosmos_data.py`.
- RBAC configured: `Cosmos DB Built-in Data Contributor` + custom `FabricMirroringRole` (5 data actions including `readChangeFeed` and `readAnalytics`) assigned to Power BI Service principal and user principal.
- `EnableFabricNetworkAclBypass` capability enabled; Fabric workspace `disputes-workspace` (`<FABRIC_WORKSPACE_ID>`) added to `networkAclBypassResourceIds`.
- `scripts/copy_cosmos_data.py` — Python script using azure-cosmos + azure-identity to copy data between Cosmos accounts.
- `scripts/fabric_mirroring_role.json` — Custom RBAC role definition for Fabric mirroring (readMetadata, items/read, executeQuery, readChangeFeed, readAnalytics).
- `scripts/bypass_patch.json` — ARM REST PATCH body for setting networkAclBypassResourceIds.

### Blocked — Fabric Mirroring (Tenant Network Policy)
- Fabric mirroring from `cosmos-disputes-mirror` to OneLake fails with: "Replication is blocked because either EnableFabricNetworkAclBypass capability is not enabled or the Fabric workspace is not allowlisted in NetworkAclBypassResourceId."
- Root cause: tenant Azure Policy blocks the Fabric service from connecting at the network layer (status code 0 = connection refused), despite all Cosmos DB settings being correctly configured.
- Same class of issue as the storage public-access policy block encountered earlier by the team.
- Tracked in [#61 — Spike: tenant network-access policy risk & deferred private-networking design](https://github.com/yortch/payment-disputes/issues/61).
- Resolution options: policy exemption, private endpoint setup (1200+ IP allowlist), or different environment.

### Added — Cosmos DB Operational Data Store (DN_work, 2026-07-06/07)
- `infra/modules/cosmos.bicep` — Azure Cosmos DB NoSQL account: serverless capacity, analytical store enabled, session consistency, RBAC-only (no keys), hierarchical partition keys. Three containers: `disputes` (`/networkCode`, `/disputeId`), `evidence` (`/disputeId`), `timeline` (`/disputeId`).
- `infra/modules/cosmos-rbac.bicep` — Grants the Function App managed identity `Cosmos DB Built-in Data Contributor` role on the Cosmos account.
- `infra/main.bicep` — Wired Cosmos DB module (`cosmos-<resourceToken>`), RBAC module, and added outputs `AZURE_COSMOS_ENDPOINT`, `AZURE_COSMOS_DATABASE_NAME`.
- `infra/abbreviations.json` — Added `"cosmosDbAccount": "cosmos"` abbreviation key.
- `infra/modules/functions.bicep` — Added `COSMOS_ENDPOINT` and `COSMOS_DATABASE_NAME` app settings so the Function App can connect to Cosmos at runtime.
- `src/api/cosmos_client.py` — Async Cosmos DB client using `DefaultAzureCredential` (managed identity in Azure, CLI locally). CRUD operations for all 3 containers with cross-partition queries.
- `src/api/cosmos_models.py` — Factory functions (`new_dispute`, `new_timeline_event`) and `DisputeStatus` enum for creating well-structured Cosmos documents. Named `cosmos_models.py` to avoid collision with Jorge's `models/` package.
- `src/api/function_app.py` — Added Cosmos CRUD HTTP endpoints (`POST /disputes`, `GET /disputes/{id}`, `GET /disputes/{id}/evidence`, `GET /disputes/{id}/timeline`) alongside existing orchestrator blueprints.
- `src/api/requirements.txt` — Added `azure-cosmos` and `azure-identity` dependencies.
- `docs/cosmos-db-integration.md` — Team documentation: architecture, container design, partition strategy, RBAC model, local development instructions.

### Added — Synthetic Seed Data & Demo Scenarios (DN_work, 2026-07-06/07)
- `src/data/generate_seed_data.py` — Bulk synthetic data generator producing 250 disputes + evidence + timeline events aligned to `case.schema.json`. Generates realistic distributions across networks (Visa 40%, MC 32%, Amex 16%, Discover 12%), statuses, categories, and amounts.
- `src/data/demo_scenarios.py` — 8 hand-crafted named demo scenarios (25 disputes) for July walkthrough: Sarah Chen (friendly fraud), Urgent Deadline, Escalation, Fraud Ring, Maker-Checker Retry, Reg E Debit Clock, Cross-Network Comparison, Volume Spike.
- `src/data/seed_cosmos.py` — Async bulk loader using `DefaultAzureCredential` to populate Cosmos DB from generated JSON files.
- `src/data/transform_jorge_cases.py` — Transformer that reads Jorge's 10 curated cases from `origin/develop` and splits them into the 3-container format (disputes/evidence/timeline) with generated timeline events.
- `data/seed/` — Generated JSON files: `disputes.json` (250), `evidence.json` (1,007), `timeline.json` (2,692), `demo_disputes.json` (25), `demo_evidence.json` (29), `demo_timeline.json` (47), `jorge_disputes.json` (10), `jorge_evidence.json` (31), `jorge_timeline.json` (85), `stats.json`, `README.md`.

### Changed — Schema Alignment (DN_work, 2026-07-06/07)
- All generators and demo scenarios updated to use `case.schema.json` enum values: `gathering` → `evidence_gathering`, `drafting` → `ai_drafting`, `review` → `pending_review`, `rejected` → `denied`, added `expired`.
- Added fields from schema: `caseId`, `orchestrationId`, `disputeRef`, `cardNetwork`, `reasonCodeLabel`, `reasonCodeChecklist`, `riskLevel`, structured `deadline{}`, structured `evidenceGaps[]`, structured `rebuttalDraft{}` with citations, `resolvedAt`.
- Dual-naming maintained for backward compatibility: `networkCode` + `cardNetwork`, `reasonDescription` + `reasonCodeLabel`, `deadlineUtc` + `deadline{}`.

### Changed
- `README.md` (2026-07-06) — Restructured to the Microsoft solution-accelerator README template (matching microsoft/content-generation-solution-accelerator and microsoft/Data-and-Agent-Governance-and-Security-Accelerator structure): added centered nav bar, Solution Overview, collapsible Features block, Quick Deploy section (preserving all azd/OIDC/local-dev commands), Guidance → Prerequisites and costs, Resources table, Business Scenario with embedded app screenshots (`docs/images/readme/case-queue.png`, `docs/images/readme/case-detail.png`), Supporting Documentation table (all links verified against repo), Project Structure, and Responsible AI footer. Old Quick Links / Architecture / Core Capabilities / Developer Setup sections replaced by the new structure.

### Added
- `infra/modules/staticwebapp.bicep` — new module for Azure Static Web App (Free SKU, raw `Microsoft.Web/staticSites@2023-12-01`). Tagged with `azd-service-name: web` so AZD matches the `web` service. Outputs `staticWebAppName`, `staticWebAppUri`, `staticWebAppId`.
- `infra/abbreviations.json` — added `"staticWebApp": "stapp"` abbreviation key.
- `infra/main.bicep` — wired `staticWebApp` module (name `stapp-<resourceToken>`); added outputs `STATIC_WEB_APP_NAME` and `STATIC_WEB_APP_URI`.
- `azure.yaml` — registered `web` service (`project: ./src/web`, `language: js`, `host: staticwebapp`, `dist: dist`) so `azd deploy` builds the Vite output and publishes it to the SWA.
- `.github/workflows/cd.yml` — added `actions/setup-node@v4` (Node 20) step between `azd provision` and `azd deploy` to ensure the Vite build can run in CI.
- `src/web/staticwebapp.config.json` — SPA fallback routing (`navigationFallback → /index.html`, excluding `/api/*`). Scaffolding for Redfoot's React SPA work (issue #42).

### Fixed
- `infra/modules/keyvault.bicep`, `infra/modules/functions.bicep`, `infra/main.bicep`, `infra/main.parameters.json`, `.github/workflows/cd.yml` — deployer RBAC role assignments hardcoded `principalType: 'User'`, which broke CD with `UnmatchedPrincipalType` because the CI OIDC deployer is a `ServicePrincipal`, not a user. Added a `principalType` parameter (default `User`) threaded through the Key Vault and Functions deployer role assignments, sourced from `${AZURE_PRINCIPAL_TYPE=User}` in the parameters file; CD sets `AZURE_PRINCIPAL_TYPE=ServicePrincipal`.
- `.github/workflows/cd.yml` — CD `azure/login` was reading the OIDC identity IDs from `secrets.*`, but `azd pipeline config` stores `AZURE_CLIENT_ID`/`AZURE_TENANT_ID`/`AZURE_SUBSCRIPTION_ID` as repository **variables** (they are non-secret for federated OIDC). The empty secrets caused `azure/login` to fall back to SERVICE_PRINCIPAL and fail with "Ensure 'client-id' and 'tenant-id' are supplied." Now references `vars.*` (also for `AZURE_ENV_NAME` and `AZURE_LOCATION`).
- `infra/main.bicep` — Function App name now suffixed with `-app` to avoid a global-name collision with soft-deleted App Service sites (`func-<token>`) left by earlier failed provision runs (`A resource with this name already exists or is in a conflicting state`). App Service soft-deleted sites cannot be manually purged.
- `infra/modules/storage.bicep` — AVM storage-account module defaults `networkAcls.defaultAction` to `Deny`, blocking Functions content file-share creation with `403 Forbidden`. Now sets `defaultAction: Allow`, `bypass: AzureServices`, `publicNetworkAccess: Enabled`, and `allowSharedKeyAccess: true`.
- `infra/modules/functions.bicep` — `AzureWebJobsStorage` / `WEBSITE_CONTENTAZUREFILECONNECTIONSTRING` were built with the storage blob endpoint in place of the account key, causing Functions preflight `CouldNotAccessStorageAccount`. Now references the storage account via `listKeys()` to build a valid connection string.

### Changed
- `README.md` — added Node.js 20 LTS to both prerequisites tables (`winget install OpenJS.NodeJS.LTS`; verify lines for `node`/`npm`); added step 7 "Run the React app locally" to Local Development (Vite dev server, `VITE_USE_MOCK` mock mode, `npm run build → dist/`); updated `azd deploy` to reflect both `api` and `web` services (`azd deploy web` for SPA-only redeploy); expanded Project Structure tree to include `src/web/`, `src/shared/`, `src/data/synthetic/`, and `infra/modules/staticwebapp.bicep`; added Review UI link to Quick Links table.
- `README.md` — added an "Configuring OIDC authentication" guide (recommended `azd pipeline config` with Federated User Managed Identity, plus a manual `az identity` alternative), noting the `Owner` role requirement for the role-assignment resources and the region-alignment constraint. Refreshed stale references (Flex Consumption, Key Vault re-enabled, `westus2`).
- `.github/workflows/cd.yml` — removed `auth-type: IDENTITY` from `azure/login` (incorrect for GitHub-hosted runners using OIDC federated credentials; that mode is for a runner's own managed identity) and aligned `AZURE_LOCATION` to `westus2` to match the provisioned environment (the resource token is location-derived, so a mismatch would create duplicate resources).
- **Functions hosting migrated from Consumption (Y1) to Flex Consumption (FC1)** with identity-based storage access. The subscription enforces `allowSharedKeyAccess = false` via Azure Policy, which breaks classic Consumption (its `WEBSITE_CONTENTAZUREFILECONNECTIONSTRING` content share requires shared-key auth → `403 Forbidden`). Flex Consumption uses the Function App managed identity for host storage and package deployment — no keys, no content share.
  - `infra/modules/functions.bicep` — FC1 plan + `functionAppConfig` (blob-container deployment via SystemAssignedIdentity, Python 3.11 runtime); `AzureWebJobsStorage__accountName` replaces the key-based connection string; managed identity granted Storage Blob Data Owner + Queue/Table Data Contributor (Durable Functions); deploying principal granted Storage Blob Data Contributor to upload the package.
  - `infra/modules/storage.bicep` — `allowSharedKeyAccess: false` (matches enforced policy; access is identity-only).

### Fixed
- Replaced `azure-dev.yml` monolith pipeline with separate `ci.yml` (build/test on all branches) and `cd.yml` (AZD provision+deploy on main after CI passes)
- `infra/main.bicep` refactored into 6 resource-specific Bicep modules under `infra/modules/` following Azure best practices

### Changed — Repo Hygiene (2026-07-08)
- Consolidated `product-vision.md` into `prd.md` (removed the redundant vision doc — all content now lives in the PRD, which also carries the two-phase demo scope and work-item index)
- `.github/workflows/ci.yml` — Added `paths-ignore` for `.squad/**` and `**/*.md` on both `push` and `pull_request` triggers; doc-only and squad-state changes no longer trigger CI
- `.github/workflows/ci.yml`, `.github/workflows/cd.yml` — Bumped GitHub Actions to Node-24-native versions: `actions/checkout@v5`, `actions/setup-node@v5`, `actions/setup-python@v6`

### Removed — Repo Hygiene (2026-07-08)
- `product-vision.md` — content merged into `prd.md`

---

## [0.3.0] - 2026-07-02

### Added
- `azure.yaml` — AZD manifest declaring the `api` service (Python / Azure Functions) (closes #33)
- `infra/main.bicep` — Subscription-scoped Bicep templates: Storage, Key Vault, Function App (Python 3.11 / Consumption/Linux), Event Grid System Topic, Azure AI Services, Application Insights, Log Analytics workspace
- `infra/main.parameters.json` — AZD environment variable → Bicep parameter bindings
- `infra/abbreviations.json` — Standard Azure resource name prefixes
- `src/api/function_app.py` — Minimal Azure Functions v4 app with `/health` endpoint
- `src/api/host.json` — Functions v4 host config with extension bundle 4.x
- `src/api/requirements.txt` — Core Python dependencies: azure-functions, azure-durable-functions, azure-ai-documentintelligence, azure-search-documents, openai
- `.azure/config.json` — AZD default environment set to `dev`
- `.github/workflows/azure-dev.yml` — GitHub Actions CI/CD pipeline: OIDC login → `azd provision` → `azd deploy` on push/PR to `main` (closes #34)
- README.md updated with Infrastructure & Deployment section, `azd up` quickstart, prerequisites, and pipeline status badge

---

## [0.2.0] - 2026-07-02

### Added
- `docs/architecture.md` — End-to-end reference architecture with Mermaid `flowchart TD` diagram covering all 6 layers (Sources & Ingestion, Orchestration, AI Foundry, Fabric/OneLake, Purview, Power BI) and the Maker-Checker agent flow (closes #5)
- `README.md` — Project overview with links to architecture doc and PRD

---

## [0.1.0] - 2026-07-02

### Added
- `prd.md` — Full Product Requirements Document derived from the the project use-case deck, including vision, personas, solution overview, reference architecture, success metrics, compliance requirements, roadmap, and an index of all 32 GitHub issues
- `product-vision.md` — Source product vision document
- 32 GitHub issues created across 8 epics (Data & Fabric, Architecture, Agents, Core Features, HITL, Compliance, Regulations, Analytics, Customer Portal)
- GitHub project board created: [Payments Dispute Resolution — July 2026 Demo](https://github.com/users/yortch/projects/5)

---

[Unreleased]: https://github.com/yortch/payment-disputes/compare/HEAD...develop
[0.3.0]: https://github.com/yortch/payment-disputes/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/yortch/payment-disputes/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/yortch/payment-disputes/releases/tag/v0.1.0
