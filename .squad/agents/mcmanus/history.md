# McManus — History & Learnings

## Project Context
- **Project:** Payments Dispute Resolution (agentic evidence-assembly accelerator)
- **Lead developer:** Jorge Balderas
- **Stack:** Azure AI Foundry · GPT-4.1/5.x · Azure AI Document Intelligence · Azure AI Search · Python
- **Repo:** https://github.com/yortch/payment-disputes
- **Agent pattern:** Maker-Checker with human-in-the-loop gate (see docs/architecture.md)

## Learnings

### 2026-07-06 — df.Blueprint() vs func.Blueprint() for Durable triggers
`azure.functions.Blueprint` (`func.Blueprint()`) is the standard Azure Functions blueprint and does **not** expose durable-specific decorators (`orchestration_trigger`, `activity_trigger`, `durable_client_input`). Any file that registers durable triggers or activities must use `azure.durable_functions.Blueprint` (`df.Blueprint()`) instead. Using `func.Blueprint()` causes silent startup failures: the Azure Functions host cannot register the durable routes and no error is raised at import time — the failure only surfaces at runtime when the worker attempts to bind. Files using only `route()` (plain HTTP triggers) continue to correctly use `func.Blueprint()`. Applied as fix for Kobayashi's Bugs 1-3 on PR #40.


📌 Team update (2026-07-06T22:58:00Z): Story #21 finalized — Blueprint class + kwarg fix merged, E2E suite 210/210 passed, PR #45 opened develop→main, reviewer lockout resolved — decided by Scribe in coordination with Fenster, Kobayashi, McManus, Redfoot