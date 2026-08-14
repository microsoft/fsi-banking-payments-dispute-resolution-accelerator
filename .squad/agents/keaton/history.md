# Keaton — History & Learnings

## Project Context
- **Project:** Payments Dispute Resolution (agentic evidence-assembly accelerator)
- **Lead developer:** Jorge Balderas
- **Stack:** Python · Azure Functions (Durable) · Azure AI Foundry · Microsoft Fabric / OneLake · Event Grid · Bicep / AZD
- **Repo:** https://github.com/yortch/payment-disputes
- **Functions app:** `src/api/function_app.py` (Python v4, health endpoint at `/health`)

## Learnings

### 2026-07-09 — PR #91: Make private endpoints opt-in (default off)
### 2026-07-09 — EasyAuth Async Race Condition (Follow-up to commit 03e6918)

- **Root cause confirmed:** Linking a Function App as a Static Web App backend via `linkedBackends` (in `staticwebapp.bicep`) causes Azure's platform to ASYNCHRONOUSLY re-enable EasyAuth v2 on the Function App AFTER the ARM deployment finishes. This is an out-of-band platform reconciliation job triggered by the backend-link association — NOT by ARM ordering. Using `dependsOn` in Bicep cannot prevent it, since it fires well after the ARM deployment completes.
- **Failure mode:** After `azd provision`, the Function App's `authsettingsV2` reverts to `platform.enabled: true` with `unauthenticatedClientAction: RedirectToLoginPage` and no identity providers configured, causing HTTP 400 `{"code":400,"message":"Login not supported for provider azureStaticWebApps"}` for cross-origin callers (specifically the `portal` SWA making `POST /api/disputes`).
- **Existing Bicep resource still correct:** The `authsettingsV2` resource in `infra/modules/functions.bicep` (added in commit 03e6918) sets the right values during ARM and should NOT be removed — it's the ARM-time guard and documents the auth model. The race-condition issue is that Azure's async platform job fires AFTER ARM and overwrites it.
- **Fix chosen:** Added a `postprovision` azd hook in `azure.yaml` that: (1) waits 90 seconds after ARM provision completes to let Azure's async EasyAuth re-enable job settle, then (2) re-asserts `authsettingsV2` via `az rest PUT` (`platform.enabled: false`, `unauthenticatedClientAction: AllowAnonymous`). This hook runs as part of every `azd provision` / `azd up` cycle, making the correct disabled-EasyAuth state durable.
- **Why not deploymentScript?** A `Microsoft.Resources/deploymentScripts` would run DURING ARM, which is still BEFORE Azure's async job fires — it would not win the race. The postprovision hook (which runs after ARM) is the correct seam.
- **Idempotent:** The `az rest PUT` is safe to run on every provision regardless of current state. `continueOnError: false` ensures a failure is visible rather than silently skipped.
- **Validation in CD:** The "Provision & Build" job's `AZD Provision` step will run the postprovision hook automatically. After that step, `az webapp auth show --name <func-app> --resource-group <rg>` should show `enabled: false`.
- **PR:** Opened referencing commit 03e6918 and this async race-condition follow-up.

### 2026-07-09 — PR #93: Agent Framework triage placeholder (Issue #92)

- **Package choice:** Used `azure-ai-projects>=2.3.0` (latest stable as of 2026-07-09, production/stable status). This is the official Microsoft Foundry Python SDK — not the older `azure-ai-agents` or the experimental `agent-framework` umbrella package. The `azure-ai-projects` SDK provides `AIProjectClient` with a `.agents` sub-client that has `.threads`, `.messages`, and `.runs` (including `create_and_poll`) — the right call path for hosted Foundry agents.
- **New module:** `src/api/services/triage_agent_client.py` — single public function `score_dispute(case_doc)` returns `{score: float, category: str, source: "foundry"|"stub", rawResponse: str|None}`. Private `_call_foundry_agent` does the actual Foundry SDK call; `_build_case_summary` produces a compact NL string from case fields; `_parse_agent_response` parses JSON from agent output with fallback to stub defaults.
- **Stub fallback behavior (decision):** Returns `{score: 0.5, category: "review", source: "stub", rawResponse: None}` whenever: (a) FOUNDRY_PROJECT_ENDPOINT or FOUNDRY_TRIAGE_AGENT_ID are unset/blank, or (b) any exception occurs in the Foundry call path. The stub is always logged at INFO level (not WARNING) when env vars are unset (expected in dev), WARNING when an actual error occurs. `score_dispute()` NEVER raises — by design.
- **Field names chosen:** `triageScore` (float), `triageCategory` (str), `triageSource` (str). These follow camelCase convention matching the rest of the Cosmos document contract. Added via `upsert_dispute()` after the original `create_dispute()` — the initial write always commits first, the triage upsert is best-effort inside a separate `try/except`.
- **Ingestion resilience:** The entire triage block (score_dispute + upsert_dispute) is wrapped in a single `try/except Exception` in `intake_dispute_record`. If either call raises, a WARNING is logged and ingestion continues — the case is already in Cosmos from `create_dispute()`.
- **Tests:** 15 new tests in `tests/test_triage_agent_client.py`. All 306 tests pass (no regressions). Test coverage: stub on unset env, stub on blank env, stub on exception, foundry success path, score clamping, invalid JSON fallback, Cosmos field persistence (via upserted doc), ingestion success when triage raises, ingestion success when triage+upsert both raise.
- **Out of scope deferred:** UI surfacing of triageScore/triageCategory (noted in PR); real Foundry Bicep provisioning (tracked in #10).
- **PR:** #93 — https://github.com/yortch/payment-disputes/pull/93



- **Root cause of recurring CD 403s:** `infra/modules/private-endpoints.bicep` was invoked unconditionally in `main.bicep`. Every `azd provision` recreated private endpoints for Cosmos DB (Sql) and Storage (blob/queue/table). When a Cosmos DB private endpoint exists in **Approved** state, the data-plane firewall rejects ALL public-network requests with `403 Forbidden` — even with `publicNetworkAccess: Enabled`, `ipRules: []`, and `isVirtualNetworkFilterEnabled: false` at the account level. The presence of an Approved PE connection overrides the "Enabled" public access setting at the firewall level.
- **Fix:** Added `param deployPrivateEndpoints bool = false` to `infra/main.bicep` and gated both `module privateDns` and `module privateEndpoints` with `if (deployPrivateEndpoints)`. Both modules are gated because `privateDns` outputs are only consumed by `privateEndpoints`. No other modules reference private-endpoints outputs.
- **ARM behavior on next provision:** Since the PEs currently exist in Azure but the new default is `false`, ARM will delete the lingering private endpoints rather than leave them — matching the desired state.
- **Bicep validation:** `az bicep build --file infra/main.bicep` exits 0; all warnings are pre-existing in the unchanged private-dns/private-endpoints modules (hardcoded env URLs).
- **Refs:** Issue #86 (tech debt — remove orphaned Phase-1 private-networking infra). PR #91.

### 2026-07-07 — Issue #56: Anonymous auth + Cosmos status persistence

- **SWA-linked Function App auth pattern**: When a Static Web App proxies `/api/*` to a BYO (bring-your-own) Function App, it does NOT inject function keys. The app-level `http_auth_level` in `function_app.py` must be `func.AuthLevel.ANONYMOUS` for the SWA to forward requests successfully. The SWA itself is the auth boundary.
- **Per-route FUNCTION auth is additive**: Blueprints that set `auth_level=func.AuthLevel.FUNCTION` on individual `@bp.route()` decorators (e.g., `pl_ingest_raw`, `pl_master_refresh`) stay secured even when the app-level default is ANONYMOUS. The per-route level overrides the app default — so pipeline HTTP endpoints can remain key-protected while case UI routes are anonymous.
- **Cosmos status persistence gap**: The HITL action triggers (`approve`, `deny`, `escalate` in `case_actions.py`) were raising the Durable external event but never writing the analyst decision back to Cosmos. The fix: call `update_case_status(case_id, new_status)` inside `_raise_analyst_decision` immediately after `raise_event`. Wrap in a try/except so a transient Cosmos failure never breaks the 200 HTTP response.
- **`update_case_status` is synthetic-safe**: In `CASE_STORE=synthetic` mode (the default for local dev), `update_case_status` is a no-op that logs a warning. Calling it unconditionally from the action triggers is safe — no Cosmos connection attempted.
- **Terminal "submitted" state**: The `submit_to_network` activity (called by the orchestrator on the approve path) now also calls `update_case_status(case_id, "submitted")` so the final terminal state is persisted after the network submission completes.
- **Test pattern for persistence**: Patch `triggers.case_actions.update_case_status` (the name at the import site in the module under test) to verify it is called with the correct status per action. Assert it is NOT called on 404 paths. Assert that `side_effect=KeyError(...)` on the mock does not change the HTTP response status (resilience guard).

### 2026-08-14 — Team update: Public-Repo Security Prep Complete
**By:** Fenster, Coordinator
📌 **Team update (2026-08-14T18:15:50Z):** Multi-phase public-repo security redaction completed. Phase 1: redacted subscription ID & internal program names at HEAD. Phase 2: rewrote commit messages to scrub sensitive reference. Phase 3: redacted Azure resource identifiers (7 resource tokens, tenant domain, 2 SWA hostnames) across 16 files, squashed 278-commit history into single root commit, deleted tags, verified 403 tests pass with zero sensitive-pattern matches. Known outstanding risk: 51 PR refs remain accessible (pre-squash history). Mitigation: service principal credential rotation (pending organizational action). Repository ready for publication. — Fenster (DevOps), Coordinator (verification)
### 2026-07-08 — Story #51: Synthetic mode guarantee + local-dev docs

- **Synthetic mode is zero-Cosmos by design**: `case_store.py` imports `services.cosmos_store` only inside the `CASE_STORE=cosmos` branch (lazy import inside function body). In synthetic mode, neither `services.cosmos_store` nor `cosmos_client` are ever imported. Proven by the `sys.modules` eviction pattern: evict both modules, call `list_cases()`, assert still absent.
- **Test pattern — RuntimeError side_effect as a guard**: `patch("cosmos_client.query_disputes", side_effect=RuntimeError(...))` in a test that calls the code path proves the function is NEVER called — any accidental call would blow up the test with a clear message. Better than just `assert_not_called()` as it surfaces the bug in the stack trace too.
- **local.settings.json is committed (not gitignored)**: The file has safe defaults (`CASE_STORE=synthetic`, blank `COSMOS_ENDPOINT`) so it's safe to track. The `.sample` file is a documented twin. README updated to match.
- **Three local-dev modes documented**: (1) UI mock-only (`VITE_USE_MOCK=true npm run dev`), (2) API synthetic (`func start` with `CASE_STORE=synthetic`), (3) full local stack (both together, Vite proxies `/api → localhost:7071` via vite.config.ts).

- **Extract testable helpers from decorated HTTP triggers**: Azure Functions `@bp.route()` wraps functions for host invocation; calling them directly in unit tests returns `None`. Pattern: extract inner logic into a `_handle_*` private function (non-decorated, pure Python), have the decorated function delegate to it, and test the helper. Example: `_handle_start_review(case_id)` is tested directly; `start_review(req)` just calls it.
- **df.Blueprint vs func.Blueprint**: Use `df.Blueprint()` only for modules that need durable decorators (`orchestration_trigger`, `activity_trigger`, `durable_client_input`). Plain HTTP-only modules should use `func.Blueprint()`. Update `test_blueprint_types.py` when intentionally changing a module's blueprint type.

### 2026-07-06 — Issue #38: Case data contract & shared types

- **Schema location:** `src/shared/schemas/case.schema.json` (JSON Schema draft 2020-12) — single source of truth for the Case contract.
- **Python models:** `src/api/models/case.py` — stdlib dataclasses (no Pydantic); avoids adding a heavy dep. Typing via `Literal` for all enums. Python 3.10+ `list[X]` annotations used with `from __future__ import annotations`.
- **TypeScript types:** `src/web/src/types/case.ts` — interfaces + string-literal union types. Created the `src/web/src/types/` directory (the web app itself does not exist yet; Redfoot owns #42).
- **Field name decision:** `rebuttalDraft` (not `rebuttal`) — matches the brief and signals the orchestrator produces a draft before analyst review.
- **`CaseSummaryDeadline`** is a separate nested type in both schema and code (omits `network` vs full `Deadline`).
- **No requirements.txt change** — dataclasses is stdlib; no new dep needed.
- **Codegen placeholder:** `src/shared/codegen/` is reserved for future `generate_py.py` / `generate_ts.py` automation; types are hand-maintained mirrors for now.

### 2026-07-06 — Issue #40: Durable orchestrator + HITL approval gate

- **Orchestrator function name:** `dispute_orchestrator` — registered via `bp.orchestration_trigger(context_parameter="context")` on a `func.Blueprint()`.
- **Activity function names:** `assemble_case`, `submit_to_network`, `notify_supervisor` — all in `src/api/activities/case_activities.py` on a shared Blueprint.
- **External event name:** `analyst_decision` — payload `{ "action": "approve"|"deny"|"escalate", "analystId": str, "comment": str|None }`.  Exactly as specified in the design brief.
- **SLA timeout:** `SLA_HOURS = 72` hard-coded in `dispute_orchestrator.py`.  `context.task_any([decision_task, timeout_task])` pattern used; the winning task is compared by identity to branch.
- **Instance ID = caseId** — `start_new(instance_id=case_id)` enforces the 1:1 mapping.  The SPA raises events by caseId directly.
- **HTTP action triggers:** All four routes (`start-review`, `approve`, `deny`, `escalate`) are in `src/api/triggers/case_actions.py`, registered on their own Blueprint.  Each uses `@bp.durable_client_input(client_parameter="client")` with `df.DurableOrchestrationClient(client)`.
- **Status returned by action triggers:** The HTTP response immediately reflects the analyst's decision (`approved` / `denied` / `escalated`).  The orchestrator asynchronously reaches the terminal state (`submitted` on approve path after `submit_to_network`).
- **404 guard:** `client.get_status(caseId)` → `runtime_status not in {"Running","Pending"}` → 404.  Compared as strings since `OrchestrationRuntimeStatus` is a `str` enum in the library.
- **Blueprint registration:** `function_app.py` imports and calls `app.register_blueprint()` for all three blueprints; health endpoint untouched.
- **`azure-functions-durable` already in `requirements.txt`** — no change needed.
- **Assemble case stub:** Tries `data/synthetic/output/<caseId>.json` (Hockney's output); falls back to a minimal inline stub so the loop is exercisable before #39 ships.
- **Syntax check:** All new files pass `py_compile.compile` with zero errors.

### 2026-07-06 — Issue #41: Case read API (GET endpoints)

- **New files:** `src/api/services/case_store.py` (store/loader), `src/api/triggers/case_read.py` (Blueprint with two routes).
- **Data sources loaded:** `src/data/synthetic/cases.json` (full array) **and** `src/data/synthetic/cases/<uuid>.json` (individual files) — merged at startup via `lru_cache`; individual files win on caseId collision.
- **Path resolution in case_store:** `__file__` walked up three `dirname()` levels (`services/ → api/ → src/`) then joined `data/synthetic` — works regardless of cwd at function host startup.
- **Live daysRemaining:** `_compute_days_remaining(dueDate)` runs `(date.fromisoformat(dueDate) - date.today()).days` at serve time. The stored `daysRemaining` from the fixture is silently overridden. This pattern is applied both in `list_cases()` (via `_to_summary`) and `get_case()` (via `_refresh_deadline`).
- **CaseSummary projection:** `_to_summary(case: dict) -> dict` derives the queue-list shape from the full Case dict. Single source of truth — no duplicated copies.
- **Status filter:** `GET /api/cases?status=pending_review` — `req.params.get("status")` passed directly to `list_cases(status_filter)`.
- **Sorted output:** `list_cases()` sorts results by `deadline.dueDate` ascending so most-urgent cases appear first in the queue.
- **Swap seam:** `_load_array_file()` and `_load_individual_files()` are the two private functions to replace for blob/OneLake; public interface (`list_cases`, `get_case`) stays identical.
- **Integration test result (2026-07-06):** 10 cases in store, 7 `pending_review`, `daysRemaining` matched live computation for all tested cases.

### 2026-07-07 — Issue #49: Cosmos DB case store (env-selectable, CASE_STORE)

- **CASE_STORE env var**: `synthetic` (default) or `cosmos`. Read inline via `os.environ.get("CASE_STORE", "synthetic")` at call time so tests can monkeypatch it and so `CASE_STORE=synthetic` never touches `DefaultAzureCredential` or the network.
- **Facade pattern**: `case_store.py` remains the single public module (`list_cases`, `get_case`, `update_case_status`). It lazily imports `services.cosmos_store` only when `CASE_STORE=cosmos`. Synthetic code path is 100% unchanged.
- **New module**: `src/api/services/cosmos_store.py` — Cosmos-backed implementation. Imports `cosmos_client` inside each function body (lazy) to guarantee zero Cosmos connection in synthetic mode.
- **Case⇄Cosmos document contract**: documents in the `disputes` container are stored using the Case-contract field names verbatim, augmented with: `id = caseId`, `disputeId = caseId`, `networkCode = cardNetwork`. Partition key: `['/networkCode', '/disputeId']` (MultiHash v2). `deadline.daysRemaining` is NOT persisted — recomputed live from `deadline.dueDate` on every read (identical to synthetic mode behaviour).
- **get_case lookup strategy**: cross-partition `SELECT * FROM c WHERE c.id = @id` — avoids requiring the caller to supply `networkCode`. Returns at most 1 doc; `id = caseId` is unique by convention.
- **update_case_status(case_id, status)**: new public method. In cosmos mode — queries by caseId, stamps `updatedAt`, issues `update_dispute`. In synthetic mode — no-op (logs warning). Exposed for future orchestrator hookup.
- **Orchestrator persistence TODO**: `case_activities.py` has a documented TODO — terminal activities (`submit_to_network`, deny, escalate paths) should call `update_case_status` to keep the Cosmos doc in sync. Deferred to coordinate with HITL flow (#48).
- **Key files**: `src/api/services/case_store.py` (facade), `src/api/services/cosmos_store.py` (new), `src/api/tests/test_cosmos_store.py` (new, 17 tests), `src/api/local.settings.json` (new template).
- **Test result**: 227 passed (was 210 — added 17 new cosmos-store tests). All mocked; no real Cosmos account required.


📌 Team update (2026-07-08T13:55:00Z): Story #51 complete; Cosmos persistence tests 12/12 GREEN; analyst decisions persisted immediately on HTTP action triggers; deployed app shows 7 pending_review cases properly seeded — decided by Coordinator

### 2026-07-08 — Portal contract review (customer-portal MVP enablement)

**Task:** Review backend contract for new `src/customer-portal` portal MVP (`submissionMode=real-api`, `dataHandling=hybrid`).

**Files inspected:**
- `src/api/function_app.py` — main entry point (modified)
- `src/api/cosmos_models.py` — `new_dispute`, `new_timeline_event`, `new_evidence_item` factories
- `src/api/cosmos_client.py` — lazy Cosmos client; `query_disputes` already has `enable_cross_partition_query=True`
- `src/api/models/case.py` — Case/CaseSummary dataclasses (JSON Schema mirror; separate from operational cosmos_models)
- `src/api/triggers/pl_ingest_raw.py` — `_calculate_deadline` pattern reused for `_compute_deadline_utc`
- `src/api/triggers/case_read.py` — reads from synthetic JSON; NOT wired to Cosmos disputes container
- `src/api/tests/` — all tests; 277 passed after changes (was 252)

**Two-model reality:** The codebase has TWO distinct data models:
1. `cosmos_models.py` / `cosmos_client.py` — operational Cosmos documents (`disputeId`, `networkCode`, `deadlineUtc`…)
2. `models/case.py` / `services/case_store.py` — analyst queue Case model (`caseId`, `cardNetwork`, `deadline.dueDate`…)
The portal's `create-dispute` flow uses the Cosmos model (POST /disputes). The analyst queue (GET /cases) uses the Case model. These are intentionally separate.

**Backend changes made (low-risk, in `function_app.py`):**
- `POST /disputes`: Removed `reasonCode` and `deadlineUtc` from required fields. `reasonCode` defaults to `"unknown"`. `deadlineUtc` auto-calculated via `_compute_deadline_utc(network_code, transaction_date)` using per-network SLA (Visa 30d, MC 45d, Amex 20d, Discover 30d). Optional `disputeDescription` stored in `metadata`.
- `GET /disputes/{id}`: `networkCode` query param made optional. When absent, falls back to `cosmos_client.query_disputes` cross-partition query. Enables portal confirmation page to use only `disputeId` from the 201 response.
- Both handlers extracted into `_handle_create_dispute(body)` and `_handle_get_dispute(dispute_id, network_code)` for testability (established team pattern).
- 25 new tests in `src/api/tests/test_portal_contract.py` — all green.

**API assumptions confirmed:**
- `AuthLevel.ANONYMOUS` at app level is already set (Issue #56 work) — portal requests work without keys ✓
- `local.settings.json` `CORS: "*"` is fine for local dev ✓
- `query_disputes` in `cosmos_client.py` already has `enable_cross_partition_query=True` — safe to use for cross-partition GET ✓

**Open gaps documented in `.squad/decisions/inbox/keaton-portal-contract.md`:**
- GAP-1: Document upload — no `POST /disputes/{id}/evidence` or SAS URL endpoint yet; recommend UI-only SAS pattern for MVP
- GAP-2: CORS for separate portal SWA — Bicep/infra config needed (not code)
- GAP-3: `transaction-select` — recommend portal uses bundled demo JSON for MVP, no new backend endpoint
- GAP-4: Portal auth model — `ANONYMOUS` works for demo MVP; full customer identity deferred

### 2026-07-08 — Issue #63 live E2E verification (dispute intake → Cosmos)

- **`POST /api/disputes` is fully verified working in production**: exercised live against the deployed
  Function App via the Analyst SWA proxy — 201, `status="intake"`, `deadlineUtc` correctly auto-computed
  server-side (Visa 30-day SLA), `GET /api/disputes/{id}` and `GET /api/disputes/{id}/timeline` both confirm
  persistence in Cosmos with a `status_change`→`intake` timeline event. Test doc id:
  `9a307795-2a0d-40c0-9767-4b7b4362a441` (tagged "SMOKE TEST", safe to delete).
- **PowerShell `curl.exe -d`/`ConvertTo-Json` gotcha**: `[System.Text.Encoding]::UTF8` in .NET writes a BOM,
  which breaks `req.get_json()` server-side ("Invalid JSON body") even though the JSON text itself is valid.
  Use `New-Object System.Text.UTF8Encoding $false` (no-BOM) when writing a JSON payload file for `curl.exe --data-binary @file`.
- **Function App has EasyAuth (App Service Authentication) enabled at the platform level**
  (`az resource show ... config/authsettingsV2`): `requireAuthentication=true`, only the Analyst UI SWA
  (`<ANALYST_SWA_HOSTNAME>`) is an allowed `azureStaticWebApps` identity provider. This causes **every** direct,
  unauthenticated call to `*.azurewebsites.net` to return 401 — even with a valid function key appended
  (EasyAuth intercepts before the function runtime's own key check). This blocks the customer portal's
  entire "call the Function App directly via CORS + absolute URL" design as currently deployed. Likely
  inherited from the Analyst SWA's "linked backend" auto-configuration (only one SWA can be linked; the
  portal was added later without being added to the EasyAuth allow-list).
- **Portal's deployed bundle doesn't contain the Function App URL at all**: `azure.yaml`'s `portal` prebuild
  hook is supposed to bake `VITE_API_BASE_URL=$AZURE_FUNCTION_APP_URI/api` into `.env.production.local`
  before `npm run build`, but the live JS bundle (`<PORTAL_SWA_HOSTNAME>azurestaticapps.net/assets/index-*.js`)
  has no reference to `<FUNCTION_APP_NAME>.azurewebsites.net` — it's falling back to relative `/api`,
  which 404s since the portal SWA has no linked backend. Root cause not diagnosed (CD/infra scope, not `src/api`).
- **Event Grid → ingestion function path is NOT wired in Azure** despite `pl_ingest_raw.py` having a working
  `@bp.event_grid_trigger` handler: `infra/modules/eventgrid.bicep` only creates a System Topic, no
  `eventSubscriptions` resource targets the function. Confirmed live: the only subscription on
  `<EVENT_GRID_TOPIC_NAME>` is Storage Defender's own `StorageAntimalwareSubscription`. This is a real infra gap,
  separate from the portal's direct-API path (which is unrelated — the portal never touches blob storage).
- **Issue #15 vs #63 scope**: #63 ("Phase 1 slice") is done at the code level except the Event Grid wiring
  (infra gap above). #15 (full webhook + network-file-ingestion epic) is mostly still open: no per-network
  (Visa/MC/Amex/Discover) file format parsing, no duplicate detection, and intake never auto-starts the
  Durable orchestrator (`dispute_orchestrator`) — only the analyst's manual "start review" action does.
  Only "deadline clock starts on intake" is done. Don't conflate "portal is wired" with "#15 is done."

### 2026-07-09 — Incident hardening: malformed Cosmos dispute documents must not take down `/api/cases`

- **Incident / root cause**: The Analyst queue 500'd for all users because one leftover smoke-test document in the `disputes` container used the intake-style schema (`disputeId`, `status`) but had no `caseId`. `services.case_store._to_summary()` accessed `case["caseId"]` unconditionally, and `services.cosmos_store.list_cases()` projected the whole batch in one comprehension, so one malformed document crashed the entire endpoint.
- **Permanent fix**: `case_store.py` now raises a specific `MalformedCaseError` when a document is missing `caseId` (or has an identity mismatch), and both synthetic and Cosmos list/read paths catch it per document, log a warning including best-effort document metadata (`id`, `caseId`, `_ts`), and skip the bad item instead of returning a blanket 500.
- **General principle**: Never assume Cosmos documents are perfectly well-formed. Shared containers accumulate legacy, test, partial, and drifted documents over time, so collection list/read paths must tolerate malformed items per document and degrade gracefully rather than letting one bad record break the whole batch.

### 2026-07-09 — Issues #15 / #63: event-driven intake completion

- **Event Grid wiring**: `infra/modules/eventgrid.bicep` now creates a child `Microsoft.EventGrid/systemTopics/eventSubscriptions` resource targeting the Function App resource `.../functions/pl_ingest_raw_event` with `endpointType: 'AzureFunction'`, filtered to `Microsoft.Storage.BlobCreated` events whose `subjectBeginsWith` points at the `ingest` container. `infra/modules/storage.bicep` now explicitly creates that `ingest` container so `azd provision` stands up both the drop location and the subscription together.
- **Network-file intake is real, not stubbed**: `src/api/triggers/pl_ingest_raw.py` now downloads blobs from the `ingest` container via `BlobServiceClient` + managed identity, parses JSON and CSV payloads, and normalizes Visa, Mastercard, Amex, and Discover records through a shared alias-based mapping layer. Assumption: the phase-1 network files are UTF-8 JSON/CSV batches whose filenames or payload metadata identify the card network (e.g. `visa-tc40-*.json`, `mastercard-gcms-*.csv`).
- **Shared intake path**: both `POST /api/pipelines/ingest` and `POST /api/disputes` now flow through the same intake logic, so webhook/manual payloads and the portal API share deadline calculation, dedupe, timeline writes, and orchestration startup. Portal intake still defaults missing `reasonCode` to `"unknown"` before entering the shared pipeline.
- **Deduplication rule**: intake first checks `metadata.dedupeKey`; if absent it derives one from the best available external reference (`externalDisputeId`, ARN, TC40 case, GCMS case, etc.), otherwise falls back to a fingerprint of network + reasonCode + last4 + amount + txn-date + merchant.
- **Case-store compatibility**: freshly ingested dispute docs are now decorated with `caseId`, `cardNetwork`, `deadline`, and `orchestrationId` fields so the Cosmos-backed analyst queue can surface them without a separate projection job.
- **Durable start / signal approach**: because the Flex Consumption durable client binding was previously removed, orchestration start and analyst decision signaling now use the Durable Task HTTP webhook API through a small helper service. Assumption: environments that need live durable signaling provide a reachable webhook base URL and, in Azure, a valid `DURABLE_WEBHOOK_CODE` app setting for the durable extension system key.
