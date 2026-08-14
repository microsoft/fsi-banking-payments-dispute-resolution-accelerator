# Payments Dispute Resolution — Product Requirements Document

> Source material based on the project's use-case requirements (June 2026). Where a section is marked *(draft / planning)*, treat it as directional rather than final.

---

## 1. Product Snapshot

| Field | Value |
|-------|-------|
| **Product / Project name** | Payments Dispute Resolution (agentic evidence-assembly accelerator) |
| **Program** | Payments Dispute Resolution |
| **Domain** | Financial Services (Banking) — card payments / chargebacks |
| **One-liner** | An agentic AI accelerator that assembles chargeback evidence in minutes — not days. |
| **Platform** | Microsoft Azure / Fabric FSI |
| **Card networks in scope** | Visa · Mastercard · American Express · Discover |
| **Target demo** | Third week of July 2026 (feasibility proof point to be used as a production-ready accelerator in phase 2) |

### Recent Implementation Updates (2026-07-22)

- Analyst queue now supports a reliable customer-response triage mode: "Filter to customer updates" applies across the search-scoped queue set rather than being constrained by the current tab view.
- Analyst queue tab and summary-card selection now clear customer-update-only mode so Open/Active/Needs Review/Closed reliably restore the full queue slice.
- The Urgent operations card now applies a true urgent-only filter for non-closed cases with deadlines within 3 days.
- The queue layout now uses a denser executive-style All Cases header with a compact operations rail.
- Customer dispute history now supports direct document review in-portal for uploaded evidence (customer and analyst artifacts).
- Document review uses an API-backed download path to support private blob storage and preserve auditable access patterns.
- Closed customer cases no longer request additional customer action after approved/denied/submitted/expired resolution states, though messages and artifacts remain visible for auditability.
- The AI-driven top-3 priority queue has been removed from the live Phase 1 analyst UI and deferred to Phase 2 until a real agent/model-based prioritization design is implemented.
- Analyst queue merchant names now use consistent regular-weight typography; severity remains communicated via row/background/badge treatment rather than text-weight changes.

---

## 2. Vision & Value Proposition

When a cardholder disputes a charge, a bank analyst must hand-assemble an evidence package — gathering proof from system after system to either refund the customer or fight the chargeback. It is slow, error-prone, and every dispute runs against a hard regulatory clock.

This product automates the entire motion with agentic AI on Azure: detecting the dispute, assembling evidence across source systems, scoring win-probability and risk, drafting a grounded rebuttal, and packaging a network-compliant submission — always with a human in the loop before anything leaves the bank.

It is designed as a **[reusable accelerator](https://accelerators.ms/#section=accelerators&industries=financial%2520services)**, repeatable across banking, insurance, and capital markets — wherever money moves.

---

## 3. The Opportunity (Why Now)

Dispute handling is slow, manual, and deadline-bound. Key opportunity metrics:

| Metric | Value | Context |
|--------|-------|---------|
| Target evidence-assembly time | **< 1 hour** | Down from 2–5 days today |
| Penalty exposure | **$50–200K / month** | From missed network thresholds |
| Friendly / first-party fraud | **~70%** | Share of chargebacks that are friendly/first-party fraud |

---

## 4. Problem Statement

Why dispute handling breaks down today:

1. **Fragmented evidence** — Evidence is scattered across **8–15 disconnected systems**. Analysts screen-scrape it together over 2–5 days, often without API access.
2. **Unforgiving deadlines** — Visa ~30 days, Mastercard 20–45 days, and the **Reg E 10-business-day clock** for debit. Miss one and it's an automatic loss.
3. **Volume outpaces capacity** — Dispute volume grows faster than the team can staff, so backlogs build against fixed, non-negotiable deadlines.
4. **Reason codes that mislead** — Reason codes are often inaccurate, so analysts burn time finding the right evidence and the current network rules.

---

## 5. Target Users & Personas

The cardholder *initiates* the dispute — but the AI **works for the bank's internal disputes team**.

### Persona A — Dispute Analyst / Chargeback Specialist (operational)
- **Pains:**
  - 8–15 logins per case
  - 2–5 day manual assembly
  - Wrong evidence per reason code
  - Knowledge gaps — reason codes that "lie"
  - Evidence requirements are complex
  - Work is manual and repetitive
- **Needs:**
  - Unified case view
  - Auto-pulled evidence
  - Reason-code checklists
  - Deadline alerts & templated rebuttals

### Persona B — VP, Disputes Operations (operations leader)
- **Pains:**
  - No real-time deadline visibility
  - Unpredictable volume spikes
  - Monitoring-program fines
- **Needs:**
  - Ops dashboard & win-probability
  - SLA escalation
  - Policy / rule engine
  - Workforce & exposure analytics

### Persona C — Cardholder / Customer (dispute initiator, low priority in scope)
- Logs into a portal to review card transactions and raises a dispute on a charge; provides supporting docs and receipts when prompted.

---

## 6. Solution Overview — What We're Building

An agentic evidence-assembly platform with a **human in the loop**. The core five-step motion:

| # | Step | Description |
|---|------|-------------|
| 1 | **Detect** | Dispute lands; the deadline clock starts automatically. |
| 2 | **Assemble** | Agents pull evidence from every source system. |
| 3 | **Score** | Risk, win-probability, and missing-evidence gaps. |
| 4 | **Recommend** | Approve / deny / escalate + a drafted rebuttal letter. |
| 5 | **Approve** | Analyst confirms; network-compliant pack submitted. |

Works across all four card networks — Visa · Mastercard · Amex · Discover.

---

## 7. Core Capabilities (Feature Set)

| Capability | What it does |
|------------|--------------|
| **Event-driven intake** | Ingest webhooks & network files the moment they arrive. |
| **Reason-code-aware engine** | Map each code to its required evidence set & rules. |
| **Multi-system retrieval** | Pull transaction, order, shipping, fraud & comms data. |
| **Document extraction** | Typed + multimodal reads of receipts, PDFs, emails. |
| **Completeness & gaps** | Flag missing evidence before the deadline hits. |
| **Grounded AI drafting** | Rebuttal narrative cites only verified facts. |
| **Deadline & SLA management** | Countdown timers, escalation, exposure forecasts. |
| **Human-in-the-loop** | Maker-checker review before anything is submitted. |
| **Compliant packaging** | Render to each network's format & submit. |

---

## 8. End-to-End User Flow (Demo Scenario)

From a customer click to a resolved dispute:

| Stage | Actor | Timing | Action |
|-------|-------|--------|--------|
| Intake | **Customer** | Day 0 | Logs into the portal, reviews card transactions, and raises a dispute on one charge. |
| Intake | **Customer** | Day 0 | Prompted for supporting docs & receipts; the system ingests and validates them. |
| Review | **Agents** | Minutes | Assemble the evidence pack and score win-probability and risk. |
| Review | **Analyst** | Minutes | Sees the recommendation — approve / deny / escalate; low-risk auto-approves. |
| Resolved | **Bank** | — | Human confirms; network-compliant pack submitted and the cardholder is updated. |

*(Planning note: draft timeline references Day 0 intake → Bank review → Day 10 resolution window.)*

---

## 9. Reference Architecture (Built end-to-end on Azure)

| Layer | Technology | Components |
|-------|-----------|------------|
| **Sources & Ingestion** | Connectors | Payment processor · OMS / ERP / CRM · Fraud · Logistics · Email/contracts → Event Grid · Logic Apps + APIM · Data Factory |
| **Orchestration** | Durable Functions + HITL | Fan-out · timers · approval gate · Review UI · Power Automate + Teams |
| **AI** | Azure AI Foundry | Orchestrator Agent · Doc Intelligence + Content Understanding · Azure AI Search (agentic) · GPT-4.1/5.x drafting · Content Safety |
| **Data** | Microsoft Fabric / OneLake | Lakehouse: disputes · transactions · orders · comms · fraud · shipments · OneLake Shortcuts (ADLS / S3 / Dataverse) |
| **Governance** | Microsoft Purview | Unified Catalog + Lineage · Sensitivity labels + DLP · DSPM for AI · Audit & retention |
| **Analytics** | Power BI on Fabric | Surfaces ops & compliance dashboards and deadline alerts across every layer. |

---

## 10. How the Agents Work (Maker-Checker Pattern with a Human Gate)

| Step | Description |
|------|-------------|
| **Dispute event** | Webhook starts the workflow & deadline clock. |
| **Orchestrator** | Foundry agent routes the case to the right tools. |
| **Gather** | Extraction (Doc Intelligence) + Retrieval (AI Search: precedents & rules). |
| **Draft & verify** | Maker drafts with GPT; Checker validates groundedness — retries on fail. |
| **Human approval** | Durable Functions gate — analyst signs off before submission. |

**Decision outcomes from the human-approval gate:**
- **Approve** → submit to acquirer / network API. *No evidence pack leaves the bank without analyst sign-off.*
- **Timeout** → escalate to supervisor queue.

---

## 11. Success Metrics & Target Value

| Metric | Target | Baseline |
|--------|--------|----------|
| Evidence assembly time | **< 1 hr** | From 2–5 days |
| Win rate | **60–70%** (best-in-class) | From ~45–50% |
| Deadline adherence | **100%** | No missed Reg E clocks |
| Target network fines | **$0** | From $50–200K / month |

Positioned as a reusable accelerator, repeatable across banking, insurance & capital markets.

---

## 12. Compliance & Regulatory Requirements

- **Reg E** — 10-business-day clock for debit disputes.
- **Reg Z** — credit dispute regulations (to be documented).
- **Card-network rules** — Visa (~30 days), Mastercard (20–45 days), Amex, Discover — reason-code-specific evidence requirements.
- **Governance controls** — Unified catalog + lineage, sensitivity labels + DLP, DSPM for AI, audit & retention (via Microsoft Purview).
- **Grounded AI** — rebuttal narratives must cite only verified facts; groundedness validated by a checker agent with retry-on-fail.

---

## 13. Roadmap / Delivery Plan (Road to the July Demo)

| Workstream | Scope | Owner(s) | Status |
|------------|-------|----------|--------|
| **Data & Fabric** | Generate & load dispute data into OneLake. | Andrey · Danna | ⚠️ BLOCKED — Fabric mirroring blocked by tenant network policy ([#61](https://github.com/yortch/payment-disputes/issues/61)). Cosmos DB operational store complete; seed data loaded. |
| **Architecture & build** | Agent orchestration + Durable Functions workflow. | Team | ⏳ In progress — infra deployed, API scaffolded, agents not started |
| **Regulations** | Document Reg E / Z and card-network rules. | Vicky | ⏸ Not started |
| **Repo & tenant** | GitHub source control in the shared Azure tenant. | Adam | ✅ Done |

**Milestone:** Final demo — third week of July 2026. A production-ready accelerator is phase 2; the demo is the feasibility proof point.

*(Planning backlog from the deck: understand the flow of events/entities involved; define personas & problems; data generation moved into Fabric workspace; architecture diagram; source control; regulations documentation.)*

---

## 13a. Delivery Phases (Demo Scope)

> **Decision date:** 2026-07-08 | **Owner:** Verbal (Lead/Architect)

The team has committed to a **two-phase delivery model**:

| Phase | Label | Target | Description |
|-------|-------|--------|-------------|
| **Phase 1** | Demo / Feasibility Proof Point | ~3rd week of July 2026 | End-to-end agentic loop with mocked/sliced integrations; proves the core dispute-resolution motion on Azure. |
| **Phase 2** | Production-Ready Accelerator | Post-demo | Full multi-system evidence retrieval, OneLake lakehouse, governance, compliant packaging, and network submission. |

### Phase 1 — In Scope for Demo

| # | Item | Notes |
|---|------|-------|
| [#62](https://github.com/yortch/payment-disputes/issues/62) | Microsoft Fabric workspace | **SLICE of #1** — Power BI on Fabric for reporting only. OneLake lakehouse load stays in #1 (Phase 2). |
| [#63](https://github.com/yortch/payment-disputes/issues/63) | Dispute ingestion | **SLICE of #3** — Cosmos DB via API + Event Grid (#15). OneLake data load stays in #3 (Phase 2). Mock evidence data = TBD. |
| [#12](https://github.com/yortch/payment-disputes/issues/12) | Evidence retrieval agent | AI Search: precedents & rules. |
| [#13](https://github.com/yortch/payment-disputes/issues/13) | Maker agent | GPT rebuttal drafting. **Absorbs #20** (grounded AI rebuttal drafting is part of #13). |
| [#15](https://github.com/yortch/payment-disputes/issues/15) | Event-driven intake | Webhook + Event Grid — pairs with #3 Cosmos ingestion. |
| [#16](https://github.com/yortch/payment-disputes/issues/16) | Reason-code-aware engine | Maps reason codes to required evidence sets and rules. |
| [#64](https://github.com/yortch/payment-disputes/issues/64) | Evidence retrieval mock | **SLICE of #17** — mock for ONE card network only. Full 8–15 source-system retrieval stays in #17 (Phase 2). |
| [#18](https://github.com/yortch/payment-disputes/issues/18) | Completeness & gaps detection | **LIGHTWEIGHT SLICE** — completeness-only. Checker/groundedness agent (#14) is Phase 2. |
| [#22](https://github.com/yortch/payment-disputes/issues/22) | HITL approval gate | Durable Functions implementation. |
| [#27](https://github.com/yortch/payment-disputes/issues/27) | Document Reg E requirements | Needed for #19 deadline/SLA work. |
| [#28](https://github.com/yortch/payment-disputes/issues/28) | Document Reg Z and card-network rules | Card-network rules documentation. |
| [#30](https://github.com/yortch/payment-disputes/issues/30) | Win-probability scoring & risk assessment | Part of the agent pipeline. |
| [#31](https://github.com/yortch/payment-disputes/issues/31) | Customer dispute intake | **SIMULATION/TOOL** — not a real customer portal; simulates dispute submission for demo. |
| [#32](https://github.com/yortch/payment-disputes/issues/32) | Document/receipt upload | **MOCK MVP** — a few pre-loaded docs only. |

### Already Done ✅

| # | Item |
|---|------|
| [#2](https://github.com/yortch/payment-disputes/issues/2) | Synthetic dispute test data |
| [#6](https://github.com/yortch/payment-disputes/issues/6) | Azure AI Foundry environment |
| [#8](https://github.com/yortch/payment-disputes/issues/8) | Durable Functions orchestration engine |
| [#21](https://github.com/yortch/payment-disputes/issues/21) | Analyst review UI (unified case view) |
| [#54](https://github.com/yortch/payment-disputes/issues/54) | Cosmos DB end-to-end activation |

### Phase 2 — Deferred (Production-Ready Accelerator)

| # | Item | Notes |
|---|------|-------|
| [#1](https://github.com/yortch/payment-disputes/issues/1) | OneLake / Fabric lakehouse | Parent scope deferred; Phase 1 covers Power BI reporting slice only. |
| [#3](https://github.com/yortch/payment-disputes/issues/3) | Load dispute/transaction/evidence data into OneLake | Full lakehouse load deferred. |
| [#4](https://github.com/yortch/payment-disputes/issues/4) | Data Factory pipelines | Full batch/CDC ingestion pipelines. |
| [#7](https://github.com/yortch/payment-disputes/issues/7) | Event Grid + Logic Apps + APIM full event ingestion | Production event ingestion topology. |
| [#9](https://github.com/yortch/payment-disputes/issues/9) | Microsoft Purview governance | Unified catalog, lineage, DLP, DSPM for AI. |
| [#10](https://github.com/yortch/payment-disputes/issues/10) | Orchestrator Agent | Full case routing across all tool pipelines. |
| [#11](https://github.com/yortch/payment-disputes/issues/11) | Document extraction agent | Doc Intelligence structured extraction. |
| [#14](https://github.com/yortch/payment-disputes/issues/14) | Checker agent | Groundedness validation with retry. |
| [#17](https://github.com/yortch/payment-disputes/issues/17) | Full multi-system evidence retrieval | 8–15 source systems (parent scope). |
| [#23](https://github.com/yortch/payment-disputes/issues/23) | Teams/Power Automate notifications | May become email-based instead. |
| [#24](https://github.com/yortch/payment-disputes/issues/24) | Escalation & supervisor queue | Timeout-based escalation paths. |
| [#25](https://github.com/yortch/payment-disputes/issues/25) | Network-compliant packaging | Visa / Mastercard / Amex / Discover. |
| [#26](https://github.com/yortch/payment-disputes/issues/26) | Network submission API integration | Live submission to card networks. |
| [#29](https://github.com/yortch/payment-disputes/issues/29) | Ops dashboard for VP persona | VP Operations persona dashboards. |
| TBD | AI-driven analyst priority queue | Deferred until Phase 2; requires real case-ranking logic/agent design rather than heuristic-only UI scoring. |

### TBD — Nice-to-Have (Not Committed)

| # | Item |
|---|------|
| [#3](https://github.com/yortch/payment-disputes/issues/3) | MVP mock evidence data (facet of #3) |
| [#19](https://github.com/yortch/payment-disputes/issues/19) | Deadline & SLA management with countdown timers |

### 13b. Implementation Update — Evidence, Audit, and Decision Closure (2026-07-22)

This update reflects current implementation behavior in the Azure-hosted rg-dev environment:

1. **Unified Evidence Center in analyst portal**
- Upload and evidence review are now combined in a single Evidence Center experience.
- Evidence rows include: artifact type, source system, submitter identity, timestamp, notes/details, completeness, and view action.

2. **Customer-origin artifacts in Customer category**
- Documents uploaded from customer portal are tagged as customer-origin and shown under Customer evidence.
- Customer response notes are surfaced alongside their related attachments.

3. **Persistent, transaction-level audit log**
- Audit timeline is persisted to Cosmos timeline container and rendered in the analyst Collaboration > Audit Log tab.
- Captured events include note additions, document uploads, customer responses, analyst decisions, and closure artifact creation.

4. **Persistent notes and artifacts in Cosmos + Blob**
- Notes are persisted as timeline events.
- Document metadata is persisted to Cosmos evidence container.
- Files/artifacts are persisted to Blob storage and referenced from Cosmos metadata.

5. **Approve/Deny customer sync and closure artifact**
- Analyst approve/deny updates dispute status for customer-portal consumption.
- A closure decision artifact is generated with reason, case ID, timestamp, and dispute details.
- Closure artifacts are saved under a `closed/{caseId}/` blob path and indexed in Cosmos evidence.

### 13c. Implementation Update — Queue Semantics and Decision KPI Clarity (2026-07-22)

This update clarifies analyst queue definitions and resolves count ambiguity in the operational UI:

1. **Standardized queue taxonomy (single source of truth)**
- `Open`: all non-closed cases.
- `Active`: `intake`, `evidence_gathering`, or `ai_drafting`.
- `Needs Review`: `pending_review` or `escalated`.
- `Closed`: `approved`, `denied`, `submitted`, or `expired`.
- Tab counts, KPI cards, and drill-down lists now use the same status predicates.

2. **Decision KPI terminology updated**
- The analyst KPI previously labeled "Win Rate" is now labeled **Approval / Denial Rate**.
- KPI now reports approval and denial percentages from explicit decided outcomes with accompanying decision totals for transparency.

3. **Customer closure artifact accessibility**
- In customer dispute details, closure summaries now include a direct view link to the generated decision artifact when available.

---

## 14. Open Questions / Assumptions

- Exact list and integration method for the 8–15 source systems (APIs vs. file-based).
- Auto-approval risk threshold and criteria for "low-risk" cases.
- Data retention periods and residency requirements.
- Scale targets (disputes/day, concurrent cases, peak volume handling).
- SLA definitions for escalation and supervisor-queue timeouts.
- Model selection specifics (GPT-4.1 vs 5.x) and content-safety policies.
- Portal scope — is the customer-facing dispute portal in scope or an external dependency?

---

## 15. Work Items (GitHub Issues)

All work items are tracked on the [project board](https://github.com/users/yortch/projects/5).

| # | Epic | Title | Phase |
|---|------|-------|-------|
| [#1](https://github.com/yortch/payment-disputes/issues/1) | Data & Fabric | Set up Microsoft Fabric workspace and OneLake | **P1 (slice)** — Power BI/Fabric reporting; OneLake load → P2 |
| [#2](https://github.com/yortch/payment-disputes/issues/2) | Data & Fabric | Generate synthetic dispute test data | ✅ Done |
| [#3](https://github.com/yortch/payment-disputes/issues/3) | Data & Fabric | Load dispute, transaction, and evidence data into OneLake | **P1 (slice)** — Cosmos ingestion; OneLake load → P2 |
| [#4](https://github.com/yortch/payment-disputes/issues/4) | Data & Fabric | Configure Data Factory pipelines for ingestion | Phase 2 |
| [#5](https://github.com/yortch/payment-disputes/issues/5) | Architecture | Document and finalize reference architecture diagram | Phase 1 |
| [#6](https://github.com/yortch/payment-disputes/issues/6) | Architecture | Set up Azure AI Foundry environment | ✅ Done |
| [#7](https://github.com/yortch/payment-disputes/issues/7) | Architecture | Configure Event Grid, Logic Apps, and APIM for event ingestion | Phase 2 |
| [#8](https://github.com/yortch/payment-disputes/issues/8) | Architecture | Set up Durable Functions orchestration engine | ✅ Done |
| [#9](https://github.com/yortch/payment-disputes/issues/9) | Architecture | Configure Microsoft Purview governance controls | Phase 2 |
| [#10](https://github.com/yortch/payment-disputes/issues/10) | Agents | Implement Orchestrator Agent (case routing) | Phase 2 |
| [#11](https://github.com/yortch/payment-disputes/issues/11) | Agents | Implement document extraction agent (Doc Intelligence) | Phase 2 |
| [#12](https://github.com/yortch/payment-disputes/issues/12) | Agents | Implement evidence retrieval agent (AI Search: precedents & rules) | **Phase 1** |
| [#13](https://github.com/yortch/payment-disputes/issues/13) | Agents | Implement Maker agent (GPT rebuttal drafting) | **Phase 1** (absorbs #20) |
| [#14](https://github.com/yortch/payment-disputes/issues/14) | Agents | Implement Checker agent (groundedness validation with retry) | Phase 2 |
| [#15](https://github.com/yortch/payment-disputes/issues/15) | Core Features | Build event-driven intake (webhook + network file ingestion) | **Phase 1** |
| [#16](https://github.com/yortch/payment-disputes/issues/16) | Core Features | Build reason-code-aware engine | **Phase 1** |
| [#17](https://github.com/yortch/payment-disputes/issues/17) | Core Features | Build multi-system evidence retrieval (8–15 source systems) | **P1 (slice)** — mock, 1 network; full → P2 |
| [#18](https://github.com/yortch/payment-disputes/issues/18) | Core Features | Build completeness and gaps detection | **P1 (slice)** — completeness-only; Checker → P2 |
| [#19](https://github.com/yortch/payment-disputes/issues/19) | Core Features | Build deadline and SLA management with countdown timers | TBD |
| [#20](https://github.com/yortch/payment-disputes/issues/20) | Core Features | Build grounded AI rebuttal drafting | **Phase 1** (absorbed into #13) |
| [#21](https://github.com/yortch/payment-disputes/issues/21) | HITL | Build analyst review UI (unified case view) | ✅ Done |
| [#22](https://github.com/yortch/payment-disputes/issues/22) | HITL | Implement HITL approval gate (Durable Functions) | **Phase 1** |
| [#23](https://github.com/yortch/payment-disputes/issues/23) | HITL | Set up Teams/Power Automate notifications for analysts | Phase 2 |
| [#24](https://github.com/yortch/payment-disputes/issues/24) | HITL | Implement escalation and supervisor queue for timeouts | Phase 2 |
| [#25](https://github.com/yortch/payment-disputes/issues/25) | Compliance | Build network-compliant packaging (Visa, Mastercard, Amex, Discover) | Phase 2 |
| [#26](https://github.com/yortch/payment-disputes/issues/26) | Compliance | Integrate network submission APIs | Phase 2 |
| [#27](https://github.com/yortch/payment-disputes/issues/27) | Regulations | Document Reg E requirements (10-business-day debit clock) | **Phase 1** |
| [#28](https://github.com/yortch/payment-disputes/issues/28) | Regulations | Document Reg Z and card-network rules | **Phase 1** |
| [#29](https://github.com/yortch/payment-disputes/issues/29) | Analytics | Build ops dashboard for VP/operations leader persona | Phase 2 |
| [#30](https://github.com/yortch/payment-disputes/issues/30) | Analytics | Implement win-probability scoring and risk assessment | **Phase 1** |
| [#31](https://github.com/yortch/payment-disputes/issues/31) | Customer Portal | Build customer dispute intake portal | **Phase 1** (simulation/tool only) |
| [#32](https://github.com/yortch/payment-disputes/issues/32) | Customer Portal | Implement document/receipt upload and validation | **Phase 1** (mock MVP) |

---

*Source: Project use-case requirements — "Payments Dispute Resolution," Microsoft FSI, June 2026.*
