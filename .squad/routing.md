# Work Routing

How to decide who handles what.

## Routing Table

| Work Type | Route To | Examples |
|-----------|----------|----------|
| Architecture, scope, decisions, PRD review | Verbal | Reference architecture, design decisions, trade-offs, issue triage |
| Azure Functions, Durable Functions, APIs, webhooks, backend Python | Keaton | Event-driven intake, HITL gate, orchestration logic, API endpoints |
| React SPA, analyst UI, case queue, front-end, Static Web Apps, dashboards | Redfoot | Unified case view, review UI, ops dashboard, intake portal front-end |
| AI Foundry agents, GPT drafting, Doc Intelligence, AI Search, Maker-Checker | McManus | Orchestrator agent, Maker, Checker, retrieval, groundedness validation |
| Fabric, OneLake, Data Factory, Purview, data pipelines, synthetic data | Hockney | Lakehouse setup, data ingestion, governance controls, analytics |
| AZD, Bicep, GitHub Actions, Azure infra, CI/CD, deployments | Fenster | IaC templates, pipeline workflows, environment config, AZD setup |
| Tests, QA, edge cases, acceptance criteria validation | Kobayashi | Unit tests, integration tests, compliance checks, deadline logic |
| Code review | Verbal | Review PRs, check quality, enforce acceptance criteria |
| Session logging, decisions merge | Scribe | Automatic — never needs routing |
| RAI review | Rai | Content safety, bias checks, credential detection, ethical review |
| Work queue, backlog monitoring | Ralph | GitHub issues triage, PR status, CI failures |

## Issue Routing

| Label | Action | Who |
|-------|--------|-----|
| `squad` | Triage: analyze issue, assign `squad:{member}` label | Verbal |
| `squad:verbal` | Architecture, design, review tasks | Verbal |
| `squad:keaton` | Backend, Durable Functions, API work | Keaton |
| `squad:redfoot` | Frontend, React SPA, analyst UI work | Redfoot |
| `squad:mcmanus` | AI agents, GPT, Doc Intelligence work | McManus |
| `squad:hockney` | Data, Fabric, OneLake, governance work | Hockney |
| `squad:fenster` | AZD, Bicep, GitHub Actions, infra work | Fenster |
| `squad:kobayashi` | Tests, QA, validation work | Kobayashi |

### Epic → Member Mapping

| Epic Label | Primary Owner | Supporting |
|------------|--------------|------------|
| `epic: architecture` | Verbal | Fenster |
| `epic: agents` | McManus | Keaton |
| `epic: data-fabric` | Hockney | Fenster |
| `epic: hitl` | Keaton | McManus, Redfoot |
| `epic: compliance` | Keaton | Verbal |
| `epic: regulations` | Verbal | — |
| `epic: analytics` | Hockney | — |
| `epic: portal` | Keaton | McManus |
| `epic: infra-devops` | Fenster | Verbal |

### How Issue Assignment Works

1. When a GitHub issue gets the `squad` label, the **Lead** triages it — analyzing content, assigning the right `squad:{member}` label, and commenting with triage notes.
2. When a `squad:{member}` label is applied, that member picks up the issue in their next session.
3. Members can reassign by removing their label and adding another member's label.
4. The `squad` label is the "inbox" — untriaged issues waiting for Lead review.

## Rules

1. **Eager by default** — spawn all agents who could usefully start work, including anticipatory downstream work.
2. **Scribe always runs** after substantial work, always as `mode: "background"`. Never blocks.
3. **Quick facts → coordinator answers directly.** Don't spawn an agent for "what port does the server run on?"
4. **When two agents could handle it**, pick the one whose domain is the primary concern.
5. **"Team, ..." → fan-out.** Spawn all relevant agents in parallel as `mode: "background"`.
6. **Anticipate downstream work.** If a feature is being built, spawn the tester to write test cases from requirements simultaneously.
7. **Issue-labeled work** — when a `squad:{member}` label is applied to an issue, route to that member. The Lead handles all `squad` (base label) triage.
