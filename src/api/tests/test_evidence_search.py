"""
Tests for services.evidence_search (Evidence Retrieval Agent, #12).

Design choices tested:
- Pure helpers (network/code resolution, filter building, result mapping) work
  without any Azure dependency.
- retrieve_precedents_for_dispute returns the mapped contract on an exact match.
- It relaxes exact -> network+category -> semantic when earlier attempts return
  no documents, and reports the matchMode used.
- It never raises: any SearchClient exception yields a stub result
  (source="stub").
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from services import evidence_search as es


# ── Fixtures ──────────────────────────────────────────────────────────────────

_DISPUTE = {
    "id": "d1",
    "disputeId": "d1",
    "networkCode": "visa",
    "reasonCode": "13.1",
    "reasonDescription": "Merchandise/Services Not Received",
    "reasonCategory": "consumer_dispute",
    "merchantName": "TechGadgets Inc",
    "merchantCategory": "Electronics",
}


def _doc(**overrides):
    base = {
        "id": "visa-13-1-precedent-001",
        "title": "Precedent - Visa 13.1 Carrier Delivery",
        "content": "A merchant prevailed by providing carrier tracking...",
        "source_type": "precedent",
        "card_network": "visa",
        "reason_code": "13.1",
        "dispute_category": "consumer_dispute",
        "source_url": "https://example.com/demo/precedents/visa-13-1",
        "citation_label": "Demo Precedent - Visa 13.1 Carrier Delivery",
        "merchant_category": "retail",
        "region": "US",
        "tags": ["precedent", "delivery"],
        "chunk_id": "visa-13-1-precedent-001",
        "@search.score": 1.23,
        "@search.reranker_score": 2.71,
    }
    base.update(overrides)
    return base


# ── Pure helpers ──────────────────────────────────────────────────────────────

class TestResolveNetworkAndCode:
    def test_explicit_network_and_code(self):
        assert es._resolve_network_and_code(_DISPUTE) == ("visa", "13.1")

    def test_prefixed_reason_code(self):
        net, code = es._resolve_network_and_code({"reasonCode": "Visa 13.1"})
        assert net == "visa"
        assert code == "13.1"

    def test_bare_code_no_network(self):
        net, code = es._resolve_network_and_code({"reasonCode": "4837"})
        assert code == "4837"


class TestBuildFilter:
    def test_exact(self):
        f = es._build_filter("visa", "13.1", "consumer_dispute", "exact")
        assert "card_network eq 'visa'" in f
        assert "reason_code eq '13.1'" in f

    def test_network_category(self):
        f = es._build_filter("visa", "13.1", "consumer_dispute", "network_category")
        assert "dispute_category eq 'consumer_dispute'" in f

    def test_semantic_has_no_filter(self):
        assert es._build_filter("visa", "13.1", "consumer_dispute", "semantic") is None

    def test_odata_escaping(self):
        f = es._build_filter("o'brien", "x", "y", "exact")
        assert "o''brien" in f


class TestMapResult:
    def test_maps_expected_fields(self):
        r = es._map_result(_doc())
        assert r["sourceType"] == "precedent"
        assert r["score"] == pytest.approx(1.23)
        assert r["rerankerScore"] == pytest.approx(2.71)
        assert r["citationLabel"] == "Demo Precedent - Visa 13.1 Carrier Delivery"
        assert r["cardNetwork"] == "visa"

    def test_snippet_truncation(self):
        long_content = "x" * 600
        r = es._map_result(_doc(content=long_content))
        assert len(r["snippet"]) == es._SNIPPET_MAX
        assert r["snippet"].endswith("...")


# ── retrieve_precedents_for_dispute ───────────────────────────────────────────

class TestRetrieve:
    def test_exact_match(self, monkeypatch):
        client = MagicMock()
        client.search.return_value = [_doc(), _doc(id="visa-13-1-evidence-001", source_type="evidence_requirement")]
        monkeypatch.setattr(es, "_get_search_client", lambda: client)

        out = es.retrieve_precedents_for_dispute(_DISPUTE, top_k=5)

        assert out["source"] == "search"
        assert out["matchMode"] == "exact"
        assert out["topK"] == 5
        assert len(out["results"]) == 2
        assert len(out["precedents"]) == 1
        assert len(out["evidenceRequirements"]) == 1
        assert {"label": "Demo Precedent - Visa 13.1 Carrier Delivery",
                "url": "https://example.com/demo/precedents/visa-13-1"} in out["citations"]

    def test_relaxes_to_network_category(self, monkeypatch):
        client = MagicMock()
        # exact -> empty, network_category -> a rule, (semantic not reached)
        client.search.side_effect = [[], [_doc(source_type="network_rule")], []]
        monkeypatch.setattr(es, "_get_search_client", lambda: client)

        out = es.retrieve_precedents_for_dispute(_DISPUTE, top_k=5)

        assert out["matchMode"] == "network_category"
        assert len(out["rules"]) == 1

    def test_falls_through_to_semantic(self, monkeypatch):
        client = MagicMock()
        # exact -> empty, network_category -> empty, semantic -> a hit
        client.search.side_effect = [[], [], [_doc()]]
        monkeypatch.setattr(es, "_get_search_client", lambda: client)

        out = es.retrieve_precedents_for_dispute(_DISPUTE, top_k=5)

        assert out["matchMode"] == "semantic"
        assert len(out["results"]) == 1

    def test_never_raises_returns_stub(self, monkeypatch):
        client = MagicMock()
        client.search.side_effect = RuntimeError("search exploded")
        monkeypatch.setattr(es, "_get_search_client", lambda: client)

        out = es.retrieve_precedents_for_dispute(_DISPUTE, top_k=3)

        assert out["source"] == "stub"
        assert out["results"] == []
        assert out["matchMode"] == "none"
        assert out["topK"] == 3
        # network/code still resolved for the stub
        assert out["network"] == "visa"
        assert out["reasonCode"] == "13.1"
