"""
Cosmos DB-backed case store implementation.

Implements the same public interface as the synthetic path in ``case_store``:
    list_cases(status_filter)   -> list[dict]   # CaseSummary list
    get_case(case_id)           -> dict | None  # full Case or None
    update_case_status(case_id, status) -> None

Document contract (``disputes`` container):
    Documents are stored using the Case-contract field names verbatim, with
    two extra fields added to satisfy the container's partition key:
        id           = caseId       (Cosmos document id — must equal disputeId)
        disputeId    = caseId       (partition key component)
        networkCode  = cardNetwork  (partition key component)
    Partition key: ['/networkCode', '/disputeId'] (MultiHash v2, hierarchical)
    deadline.daysRemaining is NOT persisted; it is recomputed live on every read
    from deadline.dueDate — identical to the behaviour in synthetic mode.

Lookup strategy:
    get_case uses a cross-partition query (SELECT * WHERE c.id = @id) rather
    than a point read because the caller supplies only caseId, not networkCode.
    The query returns at most one document (id == caseId is a unique constraint
    by convention).  This avoids requiring the caller to know the card network.

Import of cosmos_client is deferred to function-call time so that
``CASE_STORE=synthetic`` (the default) never touches DefaultAzureCredential
or the network.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from services.case_store import (
    MalformedCaseError,
    _compute_days_remaining,
    _require_case_id,
    _refresh_deadline,
    _to_summary,
    _with_case_description,
)

logger = logging.getLogger(__name__)


def _is_noise_event(event: dict) -> bool:
    event_type = str(event.get("eventType") or "").strip().lower()
    actor = str(event.get("actor") or "").strip().lower()
    detail = str(event.get("detail") or "").strip().lower()
    if event_type == "system_alert" and ("no update for" in detail or "dispute stale" in detail):
        return True
    if actor == "pipeline/master_refresh" and event_type == "system_alert":
        return True
    return False


def _ensure_activity_metadata(doc: dict, cosmos_client_module) -> dict:
    """Populate last-activity fields from timeline history for older documents."""
    if doc.get("lastActivityAt") and doc.get("lastActivityType"):
        return doc

    dispute_id = doc.get("disputeId") or doc.get("caseId")
    if not dispute_id:
        return doc

    try:
        events = cosmos_client_module.get_timeline_for_dispute(dispute_id)
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "[cosmos_store] timeline lookup skipped for activity enrichment dispute_id=%s: %s",
            dispute_id,
            exc,
        )
        return doc
    non_noise_events = [ev for ev in events if not _is_noise_event(ev)]
    if not non_noise_events:
        return doc

    latest = non_noise_events[-1]
    occurred_at = latest.get("occurredAt")
    if not occurred_at:
        return doc

    updated_doc = dict(doc)
    updated_doc["lastActivityAt"] = occurred_at
    updated_doc["lastActivityType"] = latest.get("eventType")
    updated_doc["lastActivityActor"] = latest.get("actor")
    updated_doc["lastActivityDetail"] = latest.get("detail")
    updated_doc["updatedAt"] = occurred_at
    try:
        cosmos_client_module.update_dispute(updated_doc)
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "[cosmos_store] activity enrichment update skipped dispute_id=%s: %s",
            dispute_id,
            exc,
        )
        return doc
    return updated_doc


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def list_cases(status_filter: str | None = None) -> list[dict]:
    """
    Return a list of CaseSummary dicts from Cosmos DB, sorted by dueDate asc.
    Optionally filtered to a single status value.
    """
    import cosmos_client  # deferred — avoids DefaultAzureCredential at import time

    if status_filter:
        query = "SELECT * FROM c WHERE c.status = @status"
        params = [{"name": "@status", "value": status_filter}]
    else:
        query = "SELECT * FROM c"
        params = []

    docs = cosmos_client.query_disputes(query, params)
    logger.info("[cosmos_store] list_cases — filter=%s returned %d docs", status_filter, len(docs))

    summaries: list[dict] = []
    for doc in docs:
        try:
            doc = _ensure_activity_metadata(doc, cosmos_client)
            summaries.append(_to_summary(doc))
        except MalformedCaseError as exc:
            logger.warning("[cosmos_store] skipping malformed case in list_cases — %s", exc)
    summaries.sort(key=lambda s: s["deadline"]["dueDate"])
    return summaries


def get_case(case_id: str) -> dict | None:
    """
    Return the full Case dict for the given caseId, or None if not found.
    Uses a cross-partition query (no networkCode required from the caller).
    deadline.daysRemaining is recomputed live from dueDate.
    """
    import cosmos_client  # deferred

    docs = cosmos_client.query_disputes(
        "SELECT * FROM c WHERE c.id = @id",
        [{"name": "@id", "value": case_id}],
        max_items=1,
    )
    if not docs:
        logger.info("[cosmos_store] get_case — caseId=%s not found", case_id)
        return None

    doc = docs[0]
    try:
        _require_case_id(doc, expected_case_id=case_id)
    except MalformedCaseError as exc:
        logger.warning("[cosmos_store] skipping malformed case in get_case — %s", exc)
        return None

    doc = _ensure_activity_metadata(doc, cosmos_client)

    logger.info("[cosmos_store] get_case — caseId=%s found", case_id)
    return _refresh_deadline(_with_case_description(doc))


def update_case_status(case_id: str, status: str) -> None:
    """
    Update the ``status`` and ``updatedAt`` fields of a case document in Cosmos.

    Performs a cross-partition lookup to retrieve the current document (so
    the caller needs only caseId), then issues a full replace with the updated
    status.

    Raises:
        KeyError: if no document with the given caseId exists.
    """
    import cosmos_client  # deferred

    docs = cosmos_client.query_disputes(
        "SELECT * FROM c WHERE c.id = @id",
        [{"name": "@id", "value": case_id}],
        max_items=1,
    )
    if not docs:
        raise KeyError(f"Case '{case_id}' not found in Cosmos DB")

    doc = dict(docs[0])
    doc["status"] = status
    doc["updatedAt"] = datetime.now(timezone.utc).isoformat()
    cosmos_client.update_dispute(doc)
    logger.info("[cosmos_store] update_case_status — caseId=%s → %s", case_id, status)
