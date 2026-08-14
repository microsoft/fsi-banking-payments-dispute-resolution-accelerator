# Hockney — History & Learnings

## Project Context
- **Project:** Payments Dispute Resolution (agentic evidence-assembly accelerator)
- **Lead developer:** Jorge Balderas
- **Stack:** Microsoft Fabric · OneLake · Azure Data Factory · Microsoft Purview · Power BI
- **Repo:** https://github.com/yortch/payment-disputes
- **Data domains:** disputes · transactions · orders · comms · fraud · shipments

## Learnings

### 2026-07-06 — Issue #39 Synthetic Demo Case Data Generator

- **Schema location:** `src/shared/schemas/case.schema.json` uses JSON Schema draft 2020-12 with `$defs` (not `definitions`). Use `jsonschema.Draft202012Validator` for validation; `jsonschema.validate()` defaults may not resolve `$defs` refs correctly on older library versions.
- **additionalProperties: false is strict** — every generated object must contain only fields declared in the schema. No extra keys anywhere (case, evidence, evidenceGap, citation, deadline, checklist item).
- **orchestrationId = caseId** — enforce this in every generated case; the API and SPA rely on it for correlation.
- **Deterministic UUIDs via uuid5** — seeding `uuid.uuid5(namespace, logical_name)` guarantees stable IDs across regenerations, which is essential for blob filenames referenced by the API.
- **daysRemaining is dynamic** — compute from `date.today()` at generation time, not hardcoded. Forces re-run before each demo to keep deadline drama realistic.
- **Citation integrity check** — always verify that `rebuttalDraft.citations[*].evidenceId` appears in the case's `evidence` array. Easy to break when copy-editing cases; the manual validator catches this.
- **Windows console Unicode** — print statements using `→`, `✓`, `✗`, `…` fail with `UnicodeEncodeError` on Windows cp1252 terminals. Use ASCII equivalents (`->`, `[OK]`, `FAIL`, `...`) for all `print()` calls. Unicode is fine in JSON file content written with `encoding="utf-8"`.
- **Case 05 intentionally has no rebuttalDraft** — the `evidence_gathering` status means the AI agent hasn't drafted yet. Schema allows `rebuttalDraft` to be absent; the API and UI must handle this null case.

---

📌 Team update (2026-07-06T21:15:17Z): Issue #39 decision merged. Your synthetic data generator is committed (commit 7036618). Keaton's #41 (read API) uses your `cases.json` fixture; Redfoot's #42 (SPA) can use your data to replace mock fixtures. Assemble_case stub in Keaton's #40 is no longer a blocker — production integration next.
— Scribe
