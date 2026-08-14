# disputes-web

Analyst-facing React SPA for the Payments Dispute Resolution accelerator.  
Stack: **React 18 · TypeScript (strict) · Vite 5 · Fluent UI v9 · Azure Static Web Apps**

---

## Development

```bash
cd src/web
npm install
npm run dev          # Vite dev server → http://localhost:5173
```

The dev server proxies `/api/*` to `http://localhost:7071` (Azure Functions local).

### Mock mode (no backend required)

```bash
VITE_USE_MOCK=true npm run dev
```

Or create a `.env.local`:

```
VITE_USE_MOCK=true
```

Two demo cases are included in `src/mocks/cases.ts` so the UI renders standalone.

---

## Build

```bash
npm run build        # type-check (tsc --noEmit) then bundle → dist/
npm run preview      # serve dist/ locally
```

Vite outputs to `dist/` — the SWA deployment target configured in `azure.yaml`.

---

## Routes

| Path | Component | Description |
|------|-----------|-------------|
| `/` | `QueuePage` | Case queue — list of CaseSummary items from `GET /api/cases` |
| `/cases/:caseId` | `CaseDetailPage` | Unified case detail — all evidence, rebuttal, actions |

---

## API client (`src/api/cases.ts`)

All calls go to `/api` (SWA linked-backend convention).

| Function | Endpoint | Description |
|----------|----------|-------------|
| `getCases()` | `GET /api/cases` | Returns `CaseSummary[]` |
| `getCase(id)` | `GET /api/cases/:id` | Returns full `Case` |
| `postAction(id, action, payload)` | `POST /api/cases/:id/{approve\|deny\|escalate}` | Submits analyst decision |

If `VITE_USE_MOCK=true` **or** the network call fails, mock fixtures load automatically.

---

## Contract types

All TypeScript types are imported from `src/types/case.ts` (generated from  
`src/shared/schemas/case.schema.json` — Keaton owns the schema).  
**Do not redefine shapes in components.**

---

## Directory structure

```
src/web/src/
├── api/            cases.ts — typed fetch wrapper
├── components/
│   ├── ActionBar.tsx          Approve / Deny / Escalate form
│   ├── CaseBadges.tsx         Shared Badge helpers (RiskBadge, StatusBadge, …)
│   ├── CaseTable.tsx          Queue table with deadline highlighting
│   ├── DeadlineCountdown.tsx  Coloured days-remaining badge
│   ├── EvidenceGapsPanel.tsx  Gap list with impact colours
│   ├── EvidencePanel.tsx      Evidence table with completeness badges
│   ├── ReasonCodeChecklist.tsx Satisfied/required checklist items
│   ├── RebuttalPanel.tsx      AI draft + source citations
│   └── WinProbGauge.tsx       Win % bar + risk badge
├── mocks/          cases.ts — demo fixtures (CaseSummary[] + Case map)
├── pages/
│   ├── CaseDetailPage.tsx     Unified detail view
│   └── QueuePage.tsx          Case queue list view
├── types/          case.ts — contract types (do not edit; generated from schema)
├── App.tsx         FluentProvider + BrowserRouter + routes
├── main.tsx        React root mount
└── vite-env.d.ts   ImportMetaEnv type (VITE_USE_MOCK)
```
