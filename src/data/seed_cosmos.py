"""
Cosmos DB Seeder — Loads generated seed data into Cosmos DB.

Uses DefaultAzureCredential for authentication (matches production pattern).
Supports both local development (Azure CLI credential) and deployed (managed identity).

Usage:
    python seed_cosmos.py [--data-dir ./data/seed] [--endpoint <cosmos-endpoint>] [--database disputes-db]

Prerequisites:
    - Azure CLI logged in (az login)
    - Cosmos DB account exists with containers: disputes, evidence, timeline
    - User has "Cosmos DB Built-in Data Contributor" role on the account
"""

import json
import os
import sys
import asyncio
import argparse
from pathlib import Path
from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential


# Container → partition key mapping (must match cosmos.bicep)
CONTAINER_PARTITION_KEYS = {
    "disputes": ["networkCode", "disputeId"],       # Hierarchical: /networkCode, /disputeId
    "evidence": ["disputeId"],                       # Hash: /disputeId
    "timeline": ["disputeId"],                       # Hash: /disputeId
}


async def seed_container(container, items: list[dict], container_name: str, batch_size: int = 25):
    """Seed a container with items, using upsert for idempotency."""
    total = len(items)
    success = 0
    errors = 0

    print(f"\n  Seeding '{container_name}' — {total} items...")

    for i in range(0, total, batch_size):
        batch = items[i:i + batch_size]
        for item in batch:
            try:
                await container.upsert_item(item)
                success += 1
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"    ERROR on item {item.get('id', '?')[:8]}: {e}")
                elif errors == 4:
                    print(f"    ... suppressing further errors")

        # Progress
        done = min(i + batch_size, total)
        pct = done / total * 100
        sys.stdout.write(f"\r    Progress: {done}/{total} ({pct:.0f}%) — {success} ok, {errors} err")
        sys.stdout.flush()

    print(f"\n    Done: {success} succeeded, {errors} failed")
    return success, errors


async def main(data_dir: str, endpoint: str, database_name: str):
    """Load all seed data files into Cosmos DB."""
    data_path = Path(data_dir)

    # Validate input files exist
    disputes_file = data_path / "disputes.json"
    evidence_file = data_path / "evidence.json"
    timeline_file = data_path / "timeline.json"

    for f in [disputes_file, evidence_file, timeline_file]:
        if not f.exists():
            print(f"ERROR: {f} not found. Run generate_seed_data.py first.")
            sys.exit(1)

    # Load data
    print("Loading seed data files...")
    with open(disputes_file) as f:
        disputes = json.load(f)
    with open(evidence_file) as f:
        evidence = json.load(f)
    with open(timeline_file) as f:
        timeline = json.load(f)

    print(f"  Disputes: {len(disputes)}")
    print(f"  Evidence: {len(evidence)}")
    print(f"  Timeline: {len(timeline)}")

    # Connect to Cosmos DB
    print(f"\nConnecting to Cosmos DB...")
    print(f"  Endpoint: {endpoint}")
    print(f"  Database: {database_name}")

    credential = DefaultAzureCredential()

    try:
        async with CosmosClient(endpoint, credential=credential) as client:
            database = client.get_database_client(database_name)

            # Verify database exists
            try:
                await database.read()
                print(f"  Database '{database_name}' — connected")
            except Exception as e:
                print(f"  ERROR: Cannot access database '{database_name}': {e}")
                sys.exit(1)

            # Seed each container
            results = {}

            # Disputes container
            disputes_container = database.get_container_client("disputes")
            s, e = await seed_container(disputes_container, disputes, "disputes")
            results["disputes"] = {"success": s, "errors": e}

            # Evidence container
            evidence_container = database.get_container_client("evidence")
            s, e = await seed_container(evidence_container, evidence, "evidence")
            results["evidence"] = {"success": s, "errors": e}

            # Timeline container
            timeline_container = database.get_container_client("timeline")
            s, e = await seed_container(timeline_container, timeline, "timeline")
            results["timeline"] = {"success": s, "errors": e}

            # Summary
            print(f"\n{'='*60}")
            print(f" Seeding Complete")
            print(f"{'='*60}")
            total_success = sum(r["success"] for r in results.values())
            total_errors = sum(r["errors"] for r in results.values())
            print(f"  Total items seeded: {total_success}")
            print(f"  Total errors:       {total_errors}")
            for name, r in results.items():
                print(f"    {name:12} — {r['success']} ok, {r['errors']} err")
            print(f"{'='*60}")

    finally:
        await credential.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Cosmos DB with generated dispute data")
    parser.add_argument("--data-dir", type=str, default="./data/seed", help="Directory with seed JSON files")
    parser.add_argument("--endpoint", type=str, default=os.environ.get("COSMOS_ENDPOINT", ""), help="Cosmos DB endpoint URL")
    parser.add_argument("--database", type=str, default=os.environ.get("COSMOS_DATABASE_NAME", "disputes-db"), help="Database name")
    args = parser.parse_args()

    if not args.endpoint:
        print("ERROR: --endpoint required or set COSMOS_ENDPOINT env var")
        print("  Example: python seed_cosmos.py --endpoint https://cosmos-xxx.documents.azure.com:443/")
        sys.exit(1)

    asyncio.run(main(args.data_dir, args.endpoint, args.database))
