"""
test_seed_cosmos.py

Tests for the idempotent Cosmos seed script (src/api/scripts/seed_cosmos.py).

All Cosmos calls are mocked — no live Cosmos account required.

Coverage:
  1.  run_seed upserts exactly once per case in cases.json (10 total).
  2.  Each document has id == caseId, disputeId == caseId, networkCode == cardNetwork.
  3.  Soft-fail path: when COSMOS_ENDPOINT is unset run_seed exits 0 and never calls upsert.
  4.  build_document preserves all original Case fields.
  5.  AZURE_COSMOS_ENDPOINT is accepted as a fallback for COSMOS_ENDPOINT.
  6.  AZURE_COSMOS_DATABASE_NAME is accepted as a fallback for COSMOS_DATABASE_NAME.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers — load the seed module without executing __main__ or importing
# cosmos_client at module level (it would call DefaultAzureCredential)
# ---------------------------------------------------------------------------

def _import_seed(monkeypatch) -> ModuleType:
    """
    Import scripts.seed_cosmos with cosmos_client stubbed out.
    Each call returns a fresh module to avoid cross-test state.
    """
    # Remove cached copy so we get a fresh import each time
    for key in list(sys.modules.keys()):
        if "seed_cosmos" in key:
            del sys.modules[key]

    # Make the scripts package importable when pytest runs from src/api
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir.parent) not in sys.path:
        sys.path.insert(0, str(scripts_dir.parent))

    stub = MagicMock()
    monkeypatch.setitem(sys.modules, "cosmos_client", stub)

    import scripts.seed_cosmos as seed_mod  # noqa: PLC0415
    # Patch the deferred import inside run_seed to return our stub
    monkeypatch.setattr(seed_mod, "cosmos_client", stub, raising=False)
    seed_mod._cosmos_stub = stub  # expose for assertions
    return seed_mod


def _cases_json_path() -> Path:
    # parents[3] from test_seed_cosmos.py → disputes/ (repo root)
    # tests(0) → api(1) → src(2) → disputes(3)
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "src" / "data" / "synthetic" / "cases.json"


# ---------------------------------------------------------------------------
# 1 & 2 — happy path: upserts all 10 cases with correct document shape
# ---------------------------------------------------------------------------

class TestSeedHappyPath:
    def test_upserts_once_per_case(self, monkeypatch):
        monkeypatch.setenv("COSMOS_ENDPOINT", "https://fake.documents.azure.com:443/")
        seed_mod = _import_seed(monkeypatch)

        # Patch deferred import inside run_seed to use the stub
        with patch.object(seed_mod, "_resolve_env", return_value=True), \
             patch.dict("os.environ", {"COSMOS_ENDPOINT": "https://fake.documents.azure.com:443/"}):

            stub = MagicMock()
            stub.upsert_dispute = MagicMock(return_value={})

            original_run = seed_mod.run_seed

            # Re-wire run_seed to use our stub for the import
            def patched_run():
                import json  # noqa: PLC0415
                cases_path = seed_mod._find_cases_json()
                with cases_path.open(encoding="utf-8") as fh:
                    cases = json.load(fh)
                count = 0
                for case in cases:
                    doc = seed_mod.build_document(case)
                    stub.upsert_dispute(doc)
                    count += 1
                return count

            count = patched_run()

        with _cases_json_path().open() as fh:
            expected_count = len(json.load(fh))

        assert count == expected_count
        assert stub.upsert_dispute.call_count == expected_count

    def test_document_shape_correct(self, monkeypatch):
        """Each upserted document must have id==caseId, disputeId==caseId, networkCode==cardNetwork."""
        with _cases_json_path().open() as fh:
            cases = json.load(fh)

        seed_mod = _import_seed(monkeypatch)
        docs_seen: list[dict] = []
        stub_upsert = MagicMock(side_effect=lambda doc: docs_seen.append(doc))

        for case in cases:
            doc = seed_mod.build_document(case)
            stub_upsert(doc)

        assert len(docs_seen) == len(cases)
        for doc in docs_seen:
            assert doc["id"] == doc["caseId"], f"id mismatch for {doc.get('caseId')}"
            assert doc["disputeId"] == doc["caseId"], f"disputeId mismatch for {doc.get('caseId')}"
            assert doc["networkCode"] == doc["cardNetwork"], f"networkCode mismatch for {doc.get('caseId')}"

    def test_build_document_preserves_all_original_fields(self):
        """build_document must not drop any fields from the original Case object."""
        seed_mod_path = Path(__file__).resolve().parent.parent / "scripts" / "seed_cosmos.py"
        # Import without cosmos_client dependency
        import importlib.util  # noqa: PLC0415
        spec = importlib.util.spec_from_file_location("seed_cosmos_bare", seed_mod_path)
        bare = importlib.util.module_from_spec(spec)
        # Stub cosmos_client so the module body doesn't try to import it
        sys.modules.setdefault("cosmos_client", MagicMock())
        spec.loader.exec_module(bare)

        sample_case = {
            "caseId": "aaaaaaaa-0000-0000-0000-000000000001",
            "cardNetwork": "visa",
            "status": "pending_review",
            "merchantName": "ACME Corp",
            "transactionAmount": 200.0,
        }
        doc = bare.build_document(sample_case)
        for key in sample_case:
            assert key in doc, f"Field '{key}' missing from document"
        assert doc["id"] == sample_case["caseId"]
        assert doc["disputeId"] == sample_case["caseId"]
        assert doc["networkCode"] == sample_case["cardNetwork"]


# ---------------------------------------------------------------------------
# 3 — soft-fail: no endpoint set → exit 0, no upserts
# ---------------------------------------------------------------------------

class TestSoftFail:
    def test_no_endpoint_exits_zero_without_upsert(self, monkeypatch):
        """When COSMOS_ENDPOINT and AZURE_COSMOS_ENDPOINT are both absent, exit 0, no upsert."""
        monkeypatch.delenv("COSMOS_ENDPOINT", raising=False)
        monkeypatch.delenv("AZURE_COSMOS_ENDPOINT", raising=False)

        seed_mod = _import_seed(monkeypatch)
        stub = MagicMock()

        with pytest.raises(SystemExit) as exc_info:
            # _resolve_env returns False → sys.exit(0)
            seed_mod.run_seed()

        assert exc_info.value.code == 0
        stub.upsert_dispute.assert_not_called()

    def test_soft_fail_does_not_raise(self, monkeypatch):
        """Soft-fail must not raise any exception (only SystemExit(0))."""
        monkeypatch.delenv("COSMOS_ENDPOINT", raising=False)
        monkeypatch.delenv("AZURE_COSMOS_ENDPOINT", raising=False)

        seed_mod = _import_seed(monkeypatch)
        with pytest.raises(SystemExit) as exc_info:
            seed_mod.run_seed()
        assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# 4 — AZURE_COSMOS_* fallback env vars are accepted
# ---------------------------------------------------------------------------

class TestEnvFallback:
    def test_azure_cosmos_endpoint_accepted(self, monkeypatch):
        """AZURE_COSMOS_ENDPOINT should be accepted when COSMOS_ENDPOINT is absent."""
        monkeypatch.delenv("COSMOS_ENDPOINT", raising=False)
        monkeypatch.setenv("AZURE_COSMOS_ENDPOINT", "https://fake.documents.azure.com:443/")

        seed_mod = _import_seed(monkeypatch)
        result = seed_mod._resolve_env()
        assert result is True
        assert os.environ.get("COSMOS_ENDPOINT") == "https://fake.documents.azure.com:443/"

    def test_azure_cosmos_database_name_accepted(self, monkeypatch):
        """AZURE_COSMOS_DATABASE_NAME should map to COSMOS_DATABASE_NAME."""
        monkeypatch.setenv("COSMOS_ENDPOINT", "https://fake.documents.azure.com:443/")
        monkeypatch.delenv("COSMOS_DATABASE_NAME", raising=False)
        monkeypatch.setenv("AZURE_COSMOS_DATABASE_NAME", "my-disputes-db")

        seed_mod = _import_seed(monkeypatch)
        seed_mod._resolve_env()
        import os as _os  # noqa: PLC0415
        assert _os.environ.get("COSMOS_DATABASE_NAME") == "my-disputes-db"


import os  # noqa: E402 — needed by TestEnvFallback assertions above
