"""
Tests for services.maker_agent_client (Issue #13 — Maker agent).

Design choices tested:
- When FOUNDRY_PROJECT_ENDPOINT or FOUNDRY_MAKER_AGENT_ID are unset, a grounded
  deterministic stub draft is returned (source="stub").
- The stub cites ONLY supplied evidence — no hallucinated facts. Every citation
  maps to a real evidence id.
- All four card-network formats are covered.
- The Foundry JSON response is parsed and citations referencing unknown evidence
  ids are dropped (grounding enforcement), including fenced ```json output.
- draft_rebuttal never raises — on any Foundry failure it falls back to the stub.
- to_rebuttal_draft adapts the result to the persisted RebuttalDraft shape.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from services.maker_agent_client import (
    _NETWORK_FORMATS,
    _build_stub_draft,
    _normalize_network,
    _parse_agent_response,
    _strip_code_fences,
    draft_rebuttal,
    to_rebuttal_draft,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

_EVIDENCE = [
    {
        "evidenceId": "ev-001",
        "title": "Transaction Receipt",
        "sourceSystem": "PaymentProcessor",
        "sourceLabel": "Payment Gateway",
        "type": "transaction",
        "content": {"authorizationCode": "AUTH-ABC123", "responseCode": "00 Approved"},
    },
    {
        "evidenceId": "ev-002",
        "title": "Proof of Delivery",
        "sourceSystem": "FedEx",
        "sourceLabel": "Logistics",
        "type": "shipping",
        "content": {"trackingNumber": "TRK-9988", "signedBy": "J. Doe"},
    },
]

_DISPUTE = {
    "disputeId": "d-123",
    "networkCode": "visa",
    "reasonCode": "13.1",
    "merchantName": "Acme Corp",
    "transactionAmount": 99.99,
    "transactionDate": "2026-07-01",
    "evidence": _EVIDENCE,
}


# ── Network normalization ─────────────────────────────────────────────────────

class TestNormalizeNetwork:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("visa", "visa"),
            ("VISA", "visa"),
            ("mastercard", "mastercard"),
            ("mc", "mastercard"),
            ("amex", "amex"),
            ("american express", "amex"),
            ("discover", "discover"),
            ("jcb", "unknown"),
            ("", "unknown"),
        ],
    )
    def test_networks(self, raw, expected):
        assert _normalize_network({"networkCode": raw}) == expected

    def test_falls_back_to_cardnetwork_field(self):
        assert _normalize_network({"cardNetwork": "mastercard"}) == "mastercard"


# ── Stub grounding ────────────────────────────────────────────────────────────

class TestStubDraft:
    def test_cites_only_supplied_evidence(self):
        core = _build_stub_draft(_DISPUTE, _EVIDENCE, "visa")
        cited_ids = {c["evidenceId"] for c in core["citations"]}
        assert cited_ids == {"ev-001", "ev-002"}
        assert core["grounded"] is True
        assert core["evidenceCited"] == 2

    def test_no_hallucination_every_citation_in_evidence(self):
        core = _build_stub_draft(_DISPUTE, _EVIDENCE, "visa")
        valid = {e["evidenceId"] for e in _EVIDENCE}
        for c in core["citations"]:
            assert c["evidenceId"] in valid

    def test_facts_appear_in_text(self):
        core = _build_stub_draft(_DISPUTE, _EVIDENCE, "visa")
        assert "AUTH-ABC123" in core["rebuttalText"]
        assert "TRK-9988" in core["rebuttalText"]

    def test_empty_evidence_is_not_grounded(self):
        core = _build_stub_draft(_DISPUTE, [], "visa")
        assert core["citations"] == []
        assert core["grounded"] is False
        assert core["evidenceCited"] == 0

    @pytest.mark.parametrize("network", ["visa", "mastercard", "amex", "discover"])
    def test_all_four_networks_have_format(self, network):
        core = _build_stub_draft({**_DISPUTE, "networkCode": network}, _EVIDENCE, network)
        assert _NETWORK_FORMATS[network]["addressee"] in core["rebuttalText"]
        assert _NETWORK_FORMATS[network]["closing"] in core["rebuttalText"]


# ── draft_rebuttal (public API, stub mode) ────────────────────────────────────

class TestDraftRebuttalStub:
    def test_returns_stub_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
        monkeypatch.delenv("FOUNDRY_MAKER_AGENT_ID", raising=False)

        result = draft_rebuttal(_DISPUTE)
        assert result["source"] == "stub"
        assert result["network"] == "visa"
        assert result["networkFormat"] == _NETWORK_FORMATS["visa"]["label"]
        assert result["grounded"] is True
        assert result["rawResponse"] is None

    def test_explicit_evidence_arg_takes_precedence(self, monkeypatch):
        monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
        monkeypatch.delenv("FOUNDRY_MAKER_AGENT_ID", raising=False)

        one_item = [_EVIDENCE[0]]
        result = draft_rebuttal({**_DISPUTE, "evidence": _EVIDENCE}, one_item)
        assert result["evidenceCited"] == 1
        assert result["citations"][0]["evidenceId"] == "ev-001"

    @pytest.mark.parametrize("network", ["visa", "mastercard", "amex", "discover"])
    def test_all_networks_end_to_end(self, network, monkeypatch):
        monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
        monkeypatch.delenv("FOUNDRY_MAKER_AGENT_ID", raising=False)

        result = draft_rebuttal({**_DISPUTE, "networkCode": network})
        assert result["network"] == network
        assert result["grounded"] is True


# ── Foundry response parsing / grounding enforcement ──────────────────────────

class TestParseAgentResponse:
    def test_valid_json(self):
        raw = '{"rebuttalText": "letter", "citations": [{"evidenceId": "ev-001", "excerpt": "x"}]}'
        result = _parse_agent_response(raw, {"ev-001", "ev-002"})
        assert result["rebuttalText"] == "letter"
        assert result["grounded"] is True
        assert result["evidenceCited"] == 1

    def test_drops_ungrounded_citations(self):
        raw = (
            '{"rebuttalText": "letter", "citations": ['
            '{"evidenceId": "ev-001", "excerpt": "x"},'
            '{"evidenceId": "ev-999", "excerpt": "hallucinated"}]}'
        )
        result = _parse_agent_response(raw, {"ev-001", "ev-002"})
        assert {c["evidenceId"] for c in result["citations"]} == {"ev-001"}
        # A dropped (hallucinated) citation means the draft is NOT fully grounded.
        assert result["grounded"] is False

    def test_strips_json_code_fences(self):
        raw = '```json\n{"rebuttalText": "letter", "citations": [{"evidenceId": "ev-001", "excerpt": "x"}]}\n```'
        result = _parse_agent_response(raw, {"ev-001"})
        assert result["rebuttalText"] == "letter"
        assert result["grounded"] is True

    def test_invalid_json_returns_empty(self):
        result = _parse_agent_response("not json", {"ev-001"})
        assert result["rebuttalText"] == ""
        assert result["grounded"] is False


class TestStripCodeFences:
    def test_plain_json_untouched(self):
        assert _strip_code_fences('{"a": 1}') == '{"a": 1}'

    def test_fenced_json(self):
        assert _strip_code_fences('```json\n{"a": 1}\n```') == '{"a": 1}'

    def test_bare_fence(self):
        assert _strip_code_fences('```\n{"a": 1}\n```') == '{"a": 1}'


# ── Foundry integration (mocked) ──────────────────────────────────────────────

class TestDraftRebuttalFoundry:
    def test_returns_foundry_result_on_success(self, monkeypatch):
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://x.services.ai.azure.com/api/projects/p")
        monkeypatch.setenv("FOUNDRY_MAKER_AGENT_ID", "asst_abc")

        foundry_core = {
            "rebuttalText": "grounded letter",
            "citations": [{"evidenceId": "ev-001", "excerpt": "x"}],
            "grounded": True,
            "evidenceCited": 1,
            "rawResponse": "raw",
        }
        with patch(
            "services.maker_agent_client._call_foundry_agent", return_value=foundry_core
        ):
            result = draft_rebuttal(_DISPUTE)

        assert result["source"] == "foundry"
        assert result["rebuttalText"] == "grounded letter"
        assert result["rawResponse"] == "raw"

    def test_falls_back_to_stub_on_exception(self, monkeypatch):
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://x.services.ai.azure.com/api/projects/p")
        monkeypatch.setenv("FOUNDRY_MAKER_AGENT_ID", "asst_abc")

        with patch(
            "services.maker_agent_client._call_foundry_agent",
            side_effect=RuntimeError("boom"),
        ):
            result = draft_rebuttal(_DISPUTE)  # must not raise

        assert result["source"] == "stub"
        assert result["grounded"] is True

    def test_falls_back_to_stub_on_empty_draft(self, monkeypatch):
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://x.services.ai.azure.com/api/projects/p")
        monkeypatch.setenv("FOUNDRY_MAKER_AGENT_ID", "asst_abc")

        empty_core = {
            "rebuttalText": "   ",
            "citations": [],
            "grounded": False,
            "evidenceCited": 0,
            "rawResponse": "raw",
        }
        with patch(
            "services.maker_agent_client._call_foundry_agent", return_value=empty_core
        ):
            result = draft_rebuttal(_DISPUTE)

        assert result["source"] == "stub"
        assert result["grounded"] is True


# ── RebuttalDraft adapter ─────────────────────────────────────────────────────

class TestToRebuttalDraft:
    def test_shape_matches_model(self):
        result = draft_rebuttal(_DISPUTE)
        draft = to_rebuttal_draft(result)
        assert "text" in draft
        assert "citations" in draft
        assert all("evidenceId" in c and "excerpt" in c for c in draft["citations"])
