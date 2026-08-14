# Shared Contract — Dispute Case

## Source of Truth

**`src/shared/schemas/case.schema.json`** (JSON Schema draft 2020-12) is the single, authoritative definition of the dispute `Case` object and its `CaseSummary` queue-list subset. When there is any ambiguity about field names, types, or enums, the JSON Schema wins.

---

## Three Representations

| Representation | Location | Used By |
|---|---|---|
| JSON Schema (authoritative) | `src/shared/schemas/case.schema.json` | Validation, docs, future codegen |
| Python dataclasses | `src/api/models/case.py` | Azure Functions back-end |
| TypeScript interfaces | `src/web/src/types/case.ts` | React SPA front-end |

All three representations must be kept in sync. The Python and TypeScript files are **hand-maintained mirrors** for now.

---

## Keeping Them in Sync

When you add, rename, or remove a field:

1. Edit `src/shared/schemas/case.schema.json` first.
2. Update `src/api/models/case.py` to match.
3. Update `src/web/src/types/case.ts` to match.
4. Include all three changes in the same PR.

A `src/shared/codegen/` directory is reserved for future automated codegen:

- `generate_py.py` — renders `src/api/models/case.py` from the schema (via Jinja or `datamodel-code-generator`)
- `generate_ts.py` — renders `src/web/src/types/case.ts` from the schema (via `json-schema-to-typescript`)

When codegen lands, the Python/TS files become generated artifacts and manual edits move to the schema only.

---

## Key Design Notes

| Decision | Detail |
|---|---|
| **`rebuttalDraft`** (not `rebuttal`) | Canonical field name — reflects that the orchestrator produces a draft before human review |
| **`orchestrationId = caseId`** | 1:1 mapping; simplifies SPA correlation and external-event routing |
| **`deadline` required** | Top-level `deadline` (`network`, `dueDate`, `daysRemaining`) is required on `Case`; `CaseSummary` uses `CaseSummaryDeadline` (omits `network`) |
| **All dates are ISO 8601 strings** | `format: date` for calendar dates, `format: date-time` for timestamps |
| **`winProbability`** | Float 0–1; omitted from the schema when the AI agent has not yet scored the case |
| **`CaseSummary` subset** | `caseId`, `status`, `cardNetwork`, `merchantName`, `transactionAmount`, `reasonCode`, `reasonCodeLabel`, `winProbability`, `riskLevel`, `deadline.dueDate`, `deadline.daysRemaining`, `createdAt`, `updatedAt` |
