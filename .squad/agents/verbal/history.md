# Verbal — History & Learnings

## Project Context
- **Project:** Payments Dispute Resolution (agentic evidence-assembly accelerator)
- **Lead developer:** Jorge Balderas
- **Stack:** Python · Azure Functions (Durable) · Azure AI Foundry · Microsoft Fabric / OneLake · Event Grid · Logic Apps · APIM · Bicep / AZD · GitHub Actions · Power BI · Microsoft Purview
- **Target demo:** Third week of July 2026
- **Repo:** https://github.com/yortch/payment-disputes
- **PRD:** prd.md | **Architecture:** docs/architecture.md

## Learnings

### 2026-07-08 — Two-Phase Demo Scope Finalized

**Decision:** The team finalized a two-phase delivery model for the Payments Dispute Resolution accelerator (requested by Jorge Balderas).

- **Phase 1 (Demo / Feasibility Proof Point, ~3rd week July 2026):** Cosmos DB ingestion slice, AI Search evidence retrieval (#12), Maker agent with rebuttal drafting (#13, absorbs #20), Event Grid intake (#15), reason-code engine (#16), mock evidence retrieval for 1 card network (#17 slice), lightweight completeness detection (#18 slice), HITL approval gate (#22), Reg E/Z documentation (#27/#28), win-probability scoring (#30), dispute intake simulation (#31), mock document upload (#32), and Power BI on Fabric for reporting (#1 slice). Already-done items: #2, #6, #8, #21, #54.
- **Phase 2 (Production-Ready Accelerator, post-demo):** OneLake lakehouse (#1/#3 parent), Data Factory (#4), full event ingestion topology (#7), Purview governance (#9), Orchestrator Agent (#10), Doc Intelligence (#11), Checker Agent (#14), full multi-system retrieval (#17 parent), Teams notifications (#23), escalation queue (#24), network-compliant packaging (#25/#26), VP ops dashboard (#29).
- **TBD:** Mock evidence data (#3 facet), deadline/SLA timers (#19).

**Docs updated as part of this decision:**
1. `prd.md` — Added §13a "Delivery Phases (Demo Scope)" (phase tables for P1/P2/Done/TBD); added Phase column to §15 Work Items table.
2. `docs/architecture.md` — Added "Phase Overlay" section with Mermaid legend and full layer-by-layer phase mapping table.
3. `docs/ingestion-flow.md` — Added "Phase 1 / Phase 2 Scope Reconciliation" section noting Cosmos ingestion is Phase 1 and OneLake load is Phase 2.
4. `.squad/decisions/inbox/verbal-two-phase-demo-scope.md` — Created scope decision document with full phase mapping and rationale.
📌 Team update (2026-07-08T19:56:32Z): Portal SWA architecture includes cost trade-off — two Standard-tier SWAs required for linked backends, doubling hosting cost vs. Free tier. Post-MVP optimization: consolidate both SPAs behind single SWA. Relevant for future architecture reviews. — Fenster


📌 Team update (2026-07-08T17:18:37Z): Portal SWA linked-backend exclusivity is an architectural constraint — the Function App backend can only serve one linked-backend at a time. Analyst SWA holds the link; portal SWA uses CORS + absolute URL. This pattern is binding for the MVP and needs to be documented in architecture.md when creating a "Future Service Additions" section. Future services (e.g., internal audit portal, network settlement API) must use independent backends, API Management gateways, or internal forwarding rather than attempting to link the same Function App. — Fenster (DevOps/Infrastructure)

### 2026-07-09 — Documented Phase 1 Private Networking Architecture

**What:** Added a new "Phase 1 — Private Networking Architecture (Deployment & CD Infrastructure)" section to `docs/architecture.md`, covering the mandatory-private-networking design (VNet with `func-integration`/`private-endpoints`/`runner` subnets, NAT Gateway, ephemeral in-VNet CD runner via ACI mirrored through GHCR, private endpoints for Cosmos DB + Storage). Verified the details against `.squad/decisions.md` ("MANDATORY Private Networking"), `infra/main.bicep`, `infra/modules/network.bicep`, `infra/modules/private-endpoints.bicep`, and `.github/workflows/cd.yml` rather than trusting the task summary at face value. Included a Mermaid diagram matching the existing doc's style/conventions and a public-vs-private reachability table. Called out the prior public-access band-aid as superseded/historical rather than deleting it. Deliberately did NOT reference the unresolved `SecurityControl: 'Ignore'` Azure Policy bypass experiment (PR #80) per instructions — that stays out of the confirmed architecture until resolved.

**Validation:** Rendered all three Mermaid blocks in the file (including the new one) with `@mermaid-js/mermaid-cli` locally to confirm valid syntax before committing.

**Outcome:** Committed to branch `docs/phase1-architecture-diagram`, opened PR #81 (https://github.com/yortch/payment-disputes/pull/81) against `main`. Left unmerged for review per usual discipline — docs changes get the same review bar as infra work on this project.

### 2026-07-09 — Corrected Phase 1 Architecture to the Final Tag-Bypass Model

**What:** Corrected `docs/architecture.md` so it no longer presents the abandoned self-hosted-runner-in-VNet path as the live Phase 1 design. The doc now reflects the architecture that is actually working today: GitHub-hosted runners for all CD, Storage and Cosmos with `publicNetworkAccess: Enabled`, `SecurityControl: 'Ignore'` in `infra/main.bicep` as the real Azure Policy governance bypass, and `Azure/functions-action@v1` with `remote-build: true` for Function App deployment on Flex Consumption. The stale VNet runner, NAT Gateway, private endpoints, and Function VNet integration are now described as orphaned tech debt rather than load-bearing controls, with cleanup tracked in issue #86.

**Why it mattered:** PR #81 captured a then-believed "mandatory private networking" answer, but the repo's final working state diverged. Leaving the old diagram in place would mislead future infra changes, security discussions, and demo-readiness reviews by implying the Phase 1 deployment path depends on private networking when it does not.

### 2026-08-12 — Public Repo Scope Trimmed for `docs/delivery/`

**Decision:** Kept only the technical companion docs in `docs/delivery/` and removed audience-specific business/discovery/demo collateral before public release.

- **Kept:** `3-ARCHITECTURE-PACKAGE.md`, `5-REUSABLE-CODE.md`, `6-DEPLOYMENT-GUIDE.md`, `8-LEARNING-LOG.md`, `9-TECHNICAL-DEEP-DIVE.md`.
- **Removed:** `1-BUSINESS-NARRATIVE.md`, `2-DISCOVERY-KIT.md`, `4-SECURITY-GOVERNANCE.md`, `7-DEMO-KIT.md`, `10-TEAM-DEMO-SCRIPT.md`, the bundled `Delivery-Package.docx`, and the delivery-package generator scripts.
- **Reasoning:** The public repo should showcase the accelerator's architecture and implementation, not internal-style qualification, sales, or scripted demo material. Even the security/governance package read more like delivery collateral than a source-of-truth engineering document, so it was excluded with the other audience-shaped assets.
- **Follow-through:** Rewrote `docs/delivery/README.md` and `docs/delivery/DELIVERY-SUMMARY.md` to present the folder as a technical companion only, and scrubbed remaining internal program name references from public-facing docs/infra comments so repo-wide searches no longer surface internal program names outside squad records.
