"""
Live integration test for the Evidence Retrieval Agent (#12).

Proves the retrieval path actually queries the Azure AI Search service
(`rgdevaisearch` / `dispute-knowledge`) and returns grounded, cited results —
i.e. that AI Search is genuinely used, not stubbed.

This test hits a live Azure resource, so it is OPT-IN: it is skipped unless
`AZURE_SEARCH_KEY` (or a configured managed identity via `AZURE_SEARCH_ENDPOINT`
+ RUN_LIVE_SEARCH=1) is present. CI without Azure credentials skips it cleanly;
the deterministic unit tests in test_evidence_search.py always run.

Run locally:
    $env:AZURE_SEARCH_ENDPOINT = "https://rgdevaisearch.search.windows.net"
    $env:AZURE_SEARCH_KEY      = "<query-or-admin-key>"
    python -m pytest tests/test_evidence_search_integration.py -v
"""

from __future__ import annotations

import os

import pytest

from services.evidence_search import retrieve_precedents_for_dispute, reset_search_client

_HAS_KEY = bool(os.environ.get("AZURE_SEARCH_KEY", "").strip())
_HAS_AAD = (
    bool(os.environ.get("AZURE_SEARCH_ENDPOINT", "").strip())
    and os.environ.get("RUN_LIVE_SEARCH", "").strip() in {"1", "true", "True"}
)

pytestmark = pytest.mark.skipif(
    not (_HAS_KEY or _HAS_AAD),
    reason="live AI Search creds not configured (set AZURE_SEARCH_KEY, or "
    "AZURE_SEARCH_ENDPOINT + RUN_LIVE_SEARCH=1)",
)


@pytest.fixture(autouse=True)
def _fresh_client():
    reset_search_client()
    yield
    reset_search_client()


def test_visa_13_1_hits_live_index_with_citations():
    """An exact (network, reason_code) match returns live search results."""
    dispute = {
        "disputeId": "live-visa-131",
        "networkCode": "visa",
        "reasonCode": "13.1",
        "reasonDescription": "Merchandise/Services Not Received",
        "reasonCategory": "consumer_dispute",
        "merchantName": "TechGadgets Inc",
    }
    result = retrieve_precedents_for_dispute(dispute, top_k=5)

    # Proves the query reached the live service (not the never-throws stub).
    assert result["source"] == "search", (
        f"expected live search, got source={result['source']} "
        f"(matchMode={result['matchMode']}) — check AZURE_SEARCH_* config / index"
    )
    assert result["matchMode"] == "exact"
    assert len(result["results"]) > 0
    # Every hit is grounded to a citation label.
    assert result["citations"], "expected at least one source citation"
    for item in result["results"]:
        assert item["citationLabel"]
        assert item["cardNetwork"] == "visa"


def test_unknown_code_falls_back_to_semantic_not_stub():
    """A code not in the corpus still returns live semantic hits, not the stub."""
    dispute = {
        "disputeId": "live-mc-9999",
        "networkCode": "mastercard",
        "reasonCode": "9999",
        "merchantName": "Unknown",
    }
    result = retrieve_precedents_for_dispute(dispute, top_k=5)

    assert result["source"] == "search"
    assert result["matchMode"] in {"semantic", "network_category"}
    assert len(result["results"]) > 0
