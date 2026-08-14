"""
seed_cosmos.py — Idempotent Cosmos DB seed script for the disputes container.

Reads src/data/synthetic/cases.json and upserts each case into the Cosmos
disputes container using the document contract defined in issue #49.

Document shape:
    { ...all Case fields..., "id": caseId, "disputeId": caseId, "networkCode": cardNetwork }

Partition key: ['/networkCode', '/disputeId'] (MultiHash v2 — matches infra)

Idempotency: upsert_item replaces by id → safe to re-run; no duplicates.

Environment variables:
    COSMOS_ENDPOINT or AZURE_COSMOS_ENDPOINT       — Cosmos account URL (required)
    COSMOS_DATABASE_NAME or AZURE_COSMOS_DATABASE_NAME — database name (default: disputes-db)

Soft-fail: if the endpoint is not configured, logs a message and exits 0.
This prevents azd postdeploy hook failures in environments where Cosmos is
not yet provisioned (e.g. local dev without `azd provision`).

Usage (standalone):
    # bash / macOS / Linux
    cd src/api
    COSMOS_ENDPOINT=https://<account>.documents.azure.com:443/ python scripts/seed_cosmos.py

    # PowerShell / Windows
    cd src/api
    $env:COSMOS_ENDPOINT = "https://<account>.documents.azure.com:443/"
    python scripts/seed_cosmos.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from azure.cosmos.exceptions import CosmosHttpResponseError

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Resolve env vars — reconcile AZURE_COSMOS_* (azd hook) with COSMOS_* (client)
# ---------------------------------------------------------------------------

def _resolve_env() -> bool:
    """
    Map AZURE_COSMOS_* azd output names → COSMOS_* names expected by cosmos_client.
    Returns True if the endpoint is available; False triggers a soft-fail.
    """
    endpoint = (
        os.environ.get("COSMOS_ENDPOINT")
        or os.environ.get("AZURE_COSMOS_ENDPOINT", "")
    )
    if not endpoint:
        logger.info("Cosmos endpoint not configured — skipping seed (COSMOS_ENDPOINT / AZURE_COSMOS_ENDPOINT not set)")
        return False

    db_name = (
        os.environ.get("COSMOS_DATABASE_NAME")
        or os.environ.get("AZURE_COSMOS_DATABASE_NAME", "disputes-db")
    )

    # Ensure cosmos_client picks up the correct names
    os.environ["COSMOS_ENDPOINT"] = endpoint
    os.environ["COSMOS_DATABASE_NAME"] = db_name
    return True


# ---------------------------------------------------------------------------
# Locate cases.json relative to this script (src/data/synthetic/cases.json)
# ---------------------------------------------------------------------------

def _find_cases_json() -> Path:
    script_dir = Path(__file__).resolve().parent   # src/api/scripts/
    # Walk up to repo root: src/api/scripts → src/api → src → repo root
    repo_root = script_dir.parent.parent.parent
    candidates = [
        repo_root / "src" / "data" / "synthetic" / "cases.json",
        script_dir.parent / "data" / "synthetic" / "cases.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        f"cases.json not found. Tried: {[str(p) for p in candidates]}"
    )


# ---------------------------------------------------------------------------
# Build the Cosmos document from a Case object
# ---------------------------------------------------------------------------

def build_document(case: dict) -> dict:
    """
    Return the Cosmos document for a Case object.

    Adds three partition-key helper fields on top of the verbatim Case fields:
        id          = caseId   (Cosmos document id)
        disputeId   = caseId
        networkCode = cardNetwork
    """
    doc = dict(case)
    doc["id"] = case["caseId"]
    doc["disputeId"] = case["caseId"]
    doc["networkCode"] = case["cardNetwork"]
    return doc


# ---------------------------------------------------------------------------
# Main seed logic — deferred import so tests can mock cosmos_client cleanly
# ---------------------------------------------------------------------------

def run_seed() -> int:
    """
    Seed the disputes container. Returns the number of upserted documents.
    Exits 0 with a log message if Cosmos is not configured (soft-fail).
    """
    if not _resolve_env():
        sys.exit(0)

    # Deferred import — cosmos_client reads COSMOS_ENDPOINT at module level,
    # so we must set env vars before importing it.
    import cosmos_client  # noqa: PLC0415

    cases_path = _find_cases_json()
    logger.info("Loading seed data from %s", cases_path)

    with cases_path.open(encoding="utf-8") as fh:
        cases: list[dict] = json.load(fh)

    logger.info("Seeding %d cases into Cosmos disputes container…", len(cases))
    count = 0
    for case in cases:
        doc = build_document(case)
        try:
            cosmos_client.upsert_dispute(doc)
        except CosmosHttpResponseError as exc:
            message = str(exc)
            if "blocked by your Cosmos DB account firewall settings" in message.lower() or "forbidden" in message.lower():
                logger.warning(
                    "Cosmos seed skipped due to firewall/policy block — exiting 0 so deployment can continue: %s",
                    exc,
                )
                return count
            raise
        logger.info("  ✓ upserted  id=%s  networkCode=%s", doc["id"], doc["networkCode"])
        count += 1

    logger.info("Seed complete — %d document(s) upserted.", count)
    return count


if __name__ == "__main__":
    run_seed()
