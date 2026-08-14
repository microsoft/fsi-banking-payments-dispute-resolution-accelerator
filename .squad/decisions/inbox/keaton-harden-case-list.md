# Decision: Defensive-by-default projection for Cosmos-backed case reads

**Date:** 2026-07-09  
**Author:** Keaton (Backend Dev)  
**Status:** Proposed / inbox

## Context

The production Analyst queue (`GET /api/cases`) failed with HTTP 500 for every user after a single leftover
smoke-test document in the Cosmos `disputes` container lacked the required `caseId` field. The read path
projected the entire result set through `services.case_store._to_summary()` using unconditional field access,
so one malformed document crashed the whole batch.

## Decision

Adopt a **defensive-by-default projection pattern** for Cosmos-backed list/read endpoints:

1. Projection helpers must validate required fields explicitly and raise a specific, catchable exception
   (`MalformedCaseError`) when a document is malformed.
2. Collection list paths must process documents one-by-one, log a warning with best-effort document identity
   metadata (`id`, `caseId`, `_ts`), skip malformed items, and continue returning all valid results.
3. Single-item read paths must validate the returned document before shaping it; malformed documents should be
   logged and treated as not-readable rather than surfacing as a 500 to callers.

## Rationale

Cosmos containers are shared operational stores and inevitably collect legacy, smoke-test, partial, or
schema-drifted documents over time. Read paths over a collection must therefore tolerate per-document bad data
and degrade gracefully. This preserves availability for the healthy majority of documents while still leaving a
clear warning trail for cleanup and follow-up.

## Consequences

- `GET /api/cases` now returns valid cases even if one document is malformed.
- Warning logs identify skipped documents for operational cleanup.
- Future Cosmos-backed read endpoints should follow the same validate/log/skip pattern instead of assuming a
  perfectly homogeneous container.
