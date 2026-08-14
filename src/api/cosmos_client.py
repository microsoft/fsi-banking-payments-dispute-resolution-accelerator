"""
Cosmos DB client for the Payments Dispute Resolution operational store.

Uses DefaultAzureCredential (managed identity in Azure, Azure CLI locally).
No connection strings or keys — RBAC-only access.
"""

from __future__ import annotations

import os
import logging
from typing import Any

from azure.cosmos import CosmosClient, ContainerProxy, PartitionKey
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)

_client: CosmosClient | None = None

COSMOS_ENDPOINT = os.environ.get("COSMOS_ENDPOINT", "")
COSMOS_DATABASE_NAME = os.environ.get("COSMOS_DATABASE_NAME", "disputes-db")


def _get_client() -> CosmosClient:
    """Lazy-initialise the Cosmos client with managed identity."""
    global _client
    if _client is None:
        if not COSMOS_ENDPOINT:
            raise RuntimeError("COSMOS_ENDPOINT environment variable not set")
        credential = DefaultAzureCredential()
        _client = CosmosClient(url=COSMOS_ENDPOINT, credential=credential)
    return _client


def _get_container(container_name: str) -> ContainerProxy:
    """Get a reference to a container in the disputes database."""
    client = _get_client()
    database = client.get_database_client(COSMOS_DATABASE_NAME)
    return database.get_container_client(container_name)


# ---------------------------------------------------------------------------
# Disputes container operations
# ---------------------------------------------------------------------------

def create_dispute(dispute: dict[str, Any]) -> dict[str, Any]:
    """Insert a new dispute case document."""
    container = _get_container("disputes")
    return container.create_item(body=dispute)


def get_dispute(dispute_id: str, network_code: str) -> dict[str, Any] | None:
    """Fetch a dispute by ID and network code (partition key)."""
    container = _get_container("disputes")
    try:
        return container.read_item(
            item=dispute_id,
            partition_key=[network_code, dispute_id],
        )
    except CosmosResourceNotFoundError:
        return None


def update_dispute(dispute: dict[str, Any]) -> dict[str, Any]:
    """Replace (full update) a dispute document."""
    container = _get_container("disputes")
    return container.replace_item(
        item=dispute["id"],
        body=dispute,
    )


def upsert_dispute(dispute: dict[str, Any]) -> dict[str, Any]:
    """Upsert a dispute document — insert or replace by id (idempotent)."""
    container = _get_container("disputes")
    return container.upsert_item(body=dispute)


def touch_dispute_activity(
    dispute_id: str,
    *,
    event_type: str,
    actor: str,
    detail: str,
    occurred_at: str | None = None,
) -> dict[str, Any] | None:
    """Update dispute-level activity metadata used by analyst queue sorting and display."""
    docs = query_disputes(
        "SELECT * FROM c WHERE c.id = @id",
        parameters=[{"name": "@id", "value": dispute_id}],
        max_items=1,
    )
    if not docs:
        return None

    doc = dict(docs[0])
    now_iso = occurred_at or doc.get("updatedAt") or ""
    if not now_iso:
        from datetime import datetime, timezone

        now_iso = datetime.now(timezone.utc).isoformat()

    doc["updatedAt"] = now_iso
    doc["lastActivityAt"] = now_iso
    doc["lastActivityType"] = event_type
    doc["lastActivityActor"] = actor
    doc["lastActivityDetail"] = detail
    return update_dispute(doc)


def query_disputes(
    query: str,
    parameters: list[dict[str, Any]] | None = None,
    max_items: int = 50,
) -> list[dict[str, Any]]:
    """Run a parameterised SQL query against the disputes container."""
    container = _get_container("disputes")
    results = container.query_items(
        query=query,
        parameters=parameters or [],
        max_item_count=max_items,
        enable_cross_partition_query=True,
    )
    return list(results)


# ---------------------------------------------------------------------------
# Evidence container operations
# ---------------------------------------------------------------------------

def create_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Insert a new evidence item."""
    container = _get_container("evidence")
    return container.create_item(body=evidence)


def get_evidence_for_dispute(dispute_id: str) -> list[dict[str, Any]]:
    """Fetch all evidence items for a given dispute."""
    container = _get_container("evidence")
    results = container.query_items(
        query="SELECT * FROM c WHERE c.disputeId = @disputeId",
        parameters=[{"name": "@disputeId", "value": dispute_id}],
        partition_key=dispute_id,
    )
    return list(results)


# ---------------------------------------------------------------------------
# Timeline container operations
# ---------------------------------------------------------------------------

def create_timeline_event(event: dict[str, Any]) -> dict[str, Any]:
    """Insert a new timeline event."""
    container = _get_container("timeline")
    return container.create_item(body=event)


def get_timeline_for_dispute(dispute_id: str) -> list[dict[str, Any]]:
    """Fetch the full timeline for a dispute (ordered by occurredAt)."""
    container = _get_container("timeline")
    results = container.query_items(
        query="SELECT * FROM c WHERE c.disputeId = @disputeId ORDER BY c.occurredAt ASC",
        parameters=[{"name": "@disputeId", "value": dispute_id}],
        partition_key=dispute_id,
    )
    return list(results)
