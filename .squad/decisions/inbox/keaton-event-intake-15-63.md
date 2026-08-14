# Decision Proposal: Shared intake pipeline + Event Grid subscription for dispute ingestion

**Date:** 2026-07-09  
**Author:** Keaton  
**Status:** Proposed

## Context

Issues #15 and #63 both depended on the same missing backbone:

1. the Storage System Topic had no Event Grid subscription targeting `pl_ingest_raw_event`, so blob-drop ingestion was never invoked in Azure;
2. webhook/API intake and network-file intake had diverged, leaving dedupe/orchestration behavior inconsistent; and
3. the Cosmos-backed analyst queue expected case-style fields (`caseId`, `cardNetwork`, `deadline`) that raw intake documents did not populate.

## Decision

Adopt a **single shared intake path** for dispute creation, used by:

- `POST /api/pipelines/ingest`
- `POST /api/disputes`
- `pl_ingest_raw_event` (Event Grid blob-created path)

The shared intake path will:

1. normalize webhook and file records into one canonical dispute payload;
2. calculate the deadline clock at intake when `deadlineUtc` is absent;
3. derive or preserve a `metadata.dedupeKey` and skip duplicates before insert;
4. create the dispute + `status=intake` timeline event in Cosmos;
5. decorate the document with case-compatible fields so `CASE_STORE=cosmos` can list it; and
6. best-effort start the Durable orchestrator using the Durable Task HTTP webhook API.

Infra will provision the `ingest` blob container and an Event Grid subscription filtered to `Microsoft.Storage.BlobCreated` events under that container, with an Azure Function destination pointing at `pl_ingest_raw_event`.

## Rationale

- Keeps all intake surfaces behaviorally consistent instead of re-implementing deadline/dedupe/orchestration logic in multiple routes.
- Solves the concrete Azure gap for #63 (subscription wiring) while also making the Event Grid handler actually useful for #15.
- Avoids waiting for the Flex Consumption durable client binding issue to be solved by using the supported Durable Task webhook surface as a best-effort management path.

## Assumptions / Risks

- Phase-1 network files are UTF-8 JSON or CSV batches and expose enough metadata (filename or payload fields) to infer the network.
- Live Azure environments that need durable start/signal behavior must provide a valid `DURABLE_WEBHOOK_CODE` for the Durable Task webhook endpoints; without it, intake still succeeds but orchestration start is logged as failed.
- This is a compatibility bridge: long-term, a cleaner projection or unified case/dispute schema may still be preferable.
