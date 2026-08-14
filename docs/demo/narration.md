# Architecture Demo — 5-Minute Video Narration

> **Payments Dispute Resolution Accelerator**
> Payments Dispute Resolution · July 2026
>
> Narrator guide for the architecture walkthrough demo video.
> Total runtime: ~5 minutes. Timestamps are cumulative from recording start.

---

## [0:00–0:30] Opening — What we built and why

> *Show the demo site hero section on screen.*

"Welcome to the architecture walkthrough for the Payments Dispute Resolution Accelerator —
a project built end-to-end on Azure using GitHub Copilot CLI and our Squad AI agent team.

In under five minutes I'll walk you through how a cardholder dispute travels from a customer's
browser all the way through an agentic AI pipeline, into an analyst's queue, and back to a decision —
fully automated except for the deliberate human-in-the-loop gate where it counts.

Let's start with the infrastructure blueprint."

---

## [0:30–1:10] Section 1 — Azure Application Landing Zone

> *Scroll to or highlight the landing-zone architecture diagram.*

"This is our Azure application landing zone. The pattern here is straightforward:
internet traffic enters from the top through a WAF ingress layer — Front Door Premium or
Application Gateway — which restricts web apps to only approved ingress paths.

Behind that we have two Static Web Apps on a dedicated App Service Integration Subnet.
You can see them labelled Web App 1 and Web App 2 — in our project those map to
the **Analyst Disputes Portal** and the **Customer Portal** respectively.

Both talk to a shared **Function App** that uses outbound VNet integration for private east–west calls.

On the right you see the Private PaaS layer: Cosmos DB for operational case data,
Azure Blob Storage for document artifacts, Key Vault for secrets and certificates,
Microsoft Foundry for AI models, Azure AI Search for evidence retrieval,
Event Grid for event publishing, and Application Insights through Azure Monitor Private Link Scope.

**One important note on MVP vs future phase**: the private-link plumbing — the VNet,
private endpoint subnet, and DNS zones — is provisioned by our Bicep modules and is ready to activate.
For the current MVP demo, public endpoints are used for deployment convenience.
Private isolation is the planned hardening step once the demo baseline is stable."

---

## [1:10–1:55] Section 2 — The Two Web Applications

> *Highlight the Web Apps section on the demo page.*

"Let's look at our two web applications in more detail.

The **Analyst Disputes Portal** lives in `src/web/` and is built with React 18, TypeScript, Vite,
and Fluent UI v9. It's hosted as an Azure Static Web App at Standard SKU — Standard is required
because we use the SWA linked-backend feature, which wires the Function App's `/api` proxy
directly into the SWA without any CORS config on the analyst side.

It gives analysts a case queue with SLA countdown badges, a detailed case view with the full
evidence timeline, the AI win-probability score, and approve/deny/escalate actions for the
human-in-the-loop gate.

The **Customer Portal** lives in `src/customer-portal/` — same stack, React 18, TypeScript, Vite.
It's a simulation tool, not a real bank portal. It lets us drive the end-to-end pipeline during
the demo by submitting a dispute with document uploads.

Here's a subtle but important architecture point: Azure's SWA linked-backend feature is exclusive
per Function App. Only one SWA can claim the `/api` proxy slot. The Analyst Portal takes that slot;
the Customer Portal instead calls the Function App via a direct CORS URL — injected at Vite build
time as `VITE_API_BASE_URL` through the `prepackage` hook in `azure.yaml`."

---

## [1:55–2:30] Section 3 — Cosmos DB Backend Persistence

> *Highlight the Cosmos DB section.*

"Our operational data store is Azure Cosmos DB with the NoSQL API.

We chose Cosmos for three reasons that fit this workload specifically.

First, **flexible schema**. Dispute cases vary enormously by card network — a Visa dispute
has different evidence requirements than an Amex chargeback. Cosmos' JSON document model
handles that structural variation without schema migrations.

Second, **event-oriented timeline**. Each Durable Functions orchestration step appends an event
to the case document's `timeline` array. The case document is the audit trail.
There's no separate event table to join against.

Third, **RBAC-first access**. The Function App uses its system-assigned managed identity
with the Cosmos DB Built-in Data Contributor role — granted at provision time by
`infra/modules/cosmos-rbac.bicep`. No connection string is ever in Key Vault or app settings.

We have two containers: `disputes` holds one document per case with metadata, network info,
AI score, HITL decision, and the timeline array. `evidence` holds structured evidence artifacts
linked by case ID; raw document blobs go to Azure Storage."

---

## [2:30–3:15] Section 4 — Dispute Submission Flow

> *Show the flow diagram / step cards on the demo page.*

"Let's trace a dispute end-to-end.

**Step 1 — Customer Portal**: A cardholder selects a transaction, uploads supporting documents,
and hits Submit. A POST goes to the Function App's `/api/disputes` endpoint.

**Step 2 — Function App Intake**: The Python Function App writes an initial case document to
Cosmos with status `submitted` and publishes an intake event to Event Grid.

**Step 3 — Cosmos Persistence**: Case document created, evidence metadata stored, raw blobs to Storage.

**Step 4 — Agentic Pipeline**: A Durable Functions orchestration fans out to the AI workflow:
Triage scoring, reason-code classification using an in-process static registry,
evidence retrieval, gaps detection, and win-probability scoring.

**Step 5 — Foundry Agent**: The Maker Agent — running on Azure AI Foundry with DeepSeek-V3.2 —
generates a grounded rebuttal draft. A Checker Agent validates groundedness.
The score and draft are appended to the case timeline. I'll leave the deeper agent architecture
to my colleagues Vicky and Andrey in the AI segment.

**Step 6 — HITL Gate**: A Durable Functions external-event wait suspends the orchestration.
The case appears in the analyst's queue with everything they need to decide.

**Step 7 — Analyst Portal**: The analyst approves, denies, or escalates.
The decision is persisted to Cosmos and the orchestration completes."

---

## [3:15–3:50] Section 5 — Infrastructure as Code and AZD

> *Highlight the IaC section and mention the source links.*

"Everything you just saw is provisioned and deployed from a single command: `azd up`.

`azure.yaml` is the single source of truth — it maps three services to their Azure host types:
`api` to Azure Functions, `web` to a Static Web App, and `portal` to a second Static Web App.

The infra folder contains modular Bicep: a `staticwebapp.bicep` module reused for both SWAs,
a `functions.bicep` with an explicit EasyAuth override — because Azure's async linked-backend
side-effect re-enables auth after ARM completes, so we re-assert it disabled in a `postprovision` hook —
plus Cosmos, AI Services, Key Vault, network, private endpoint, and monitoring modules.

`azd up` provisions infra, builds all three services, and deploys — making it the fastest way
to validate the full stack from a clean environment. The CD pipeline reuses the exact same
`azure.yaml` and Bicep, so there is no drift between a developer's laptop and production."

---

## [3:50–4:20] Section 6 — CI/CD Pipeline

> *Highlight the CI/CD section and the pipeline evidence panel.*

"The CI/CD pipeline is two GitHub Actions workflows.

**CI** runs on every branch push: checkout, Python 3.11 setup, Node 20 setup, `npm ci` for both apps,
a Vite build for the customer portal to catch TypeScript errors, `pip install`, `flake8` lint,
and `pytest` for the API.

**CD** triggers on successful CI against main: OIDC login to Azure — no long-lived secrets —
`azd provision`, Vite build for both SPAs, and `azd deploy` for all three services.
A self-hosted runner with VNet access handles the Function App zip deployment.

You can see live run history at
[github.com/yortch/disputes/actions](https://github.com/yortch/disputes/actions).
A completed-run screenshot can be added to the demo page once supplied."

---

## [4:20–4:50] Section 7 — Azure Portal Walkthrough

> *Open the Azure Portal and navigate to the deployed resource group.*

"Let me do a quick portal tour of the deployed resource group.

You'll see two Static Web Apps — the Analyst Portal with the linked-backend wiring shown on its
backend tab, and the Customer Portal with `VITE_API_BASE_URL` in its app settings.

The Function App shows Python 3.11 on a Flex Consumption plan, the functions list, App Insights
integration, and the managed identity blade — no keys, only identity.

In Cosmos DB, open the Data Explorer and look at a case document in the `disputes` container.
The `timeline` array shows each workflow step as a timestamped event — triage, score, rebuttal, decision.

The Microsoft Foundry resource is there as an AI Services account, S0 SKU.
Deeper Foundry configuration is in the AI segment.

Finally, notice the VNet and private endpoint resources — those are provisioned and ready,
but not yet routing traffic. They represent the private-link hardening that moves this
from an MVP demo to a production-ready deployment."

---

## [4:50–5:00] Closing — Squad and GitHub Copilot CLI

> *Highlight the credits section.*

"This entire accelerator — architecture, APIs, UI, agents, data pipelines, and IaC —
was built by a team of AI agents called **Squad**, orchestrated by **GitHub Copilot CLI**.

Squad members each own a domain: Verbal for architecture, Keaton for backend,
Redfoot for frontend, McManus for AI, Hockney for data, Fenster for DevOps, Kobayashi for QA.

They collaborate through structured handoffs, logged decisions, and human review gates —
the same pattern we used to build the dispute workflow itself.

Thanks for watching. Source links, agent config files, and the Azure Portal link are all
on the demo page."

---

## Presenter Notes

- **Audience**: Technical stakeholders, program reviewers, demo evaluators.
- **Timing discipline**: Each section is 30–60 s. Pause at section breaks for questions if live.
- **Screen flow**: Demo page → live Azure Portal → GitHub Actions runs (in that order).
- **Agent caveat**: Only name agents confirmed deployed or code-complete. Evidence Retrieval Agent (#12)
  and Gaps/Win-Probability (#18, #30) are code-complete, not deployed to live app. Say so explicitly.
- **Private-link caveat**: Always distinguish MVP (public endpoints) from future phase (private link).
  Do not say "isolated" or "private" without the qualifier.
- **Screenshot slot**: The pipeline evidence panel on the demo page has a placeholder.
  Replace it with an actual Actions run screenshot before the recorded session if possible.
