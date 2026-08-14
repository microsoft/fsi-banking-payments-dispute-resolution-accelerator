"""
Tests for services.triage_agent_client and its integration into
the ingestion pipeline (pl_ingest_raw.intake_dispute_record).

Design choices tested:
- When FOUNDRY_PROJECT_ENDPOINT or FOUNDRY_TRIAGE_AGENT_ID are unset, the
  stub fallback is returned immediately (source="stub").
- When the Foundry agent raises any exception, score_dispute() still returns
  the stub — it never re-raises.
- When the Foundry agent is configured and succeeds, the real result
  (source="foundry") is returned.
- intake_dispute_record() persists triageScore/triageCategory/triageSource
  onto the Cosmos document via upsert_dispute.
- intake_dispute_record() completes successfully even if score_dispute()
  raises (triage failure must not block ingestion).
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch, call

import pytest

from services.triage_agent_client import (
    _build_case_summary,
    _parse_agent_response,
    score_dispute,
)
from triggers.pl_ingest_raw import intake_dispute_record


# ── Fixtures ──────────────────────────────────────────────────────────────────

_SAMPLE_CASE = {
    "id": "case-123",
    "disputeId": "case-123",
    "networkCode": "visa",
    "reasonCode": "13.1",
    "transactionAmount": 99.99,
    "merchantName": "Acme Corp",
    "evidence": [{"evidenceType": "receipt", "title": "Receipt"}],
}

_STANDARD_RECORD = {
    "networkCode": "visa",
    "reasonCode": "13.1",
    "cardholderName": "Jane Doe",
    "cardLastFour": "4242",
    "transactionAmount": "99.99",
    "transactionDate": "2026-07-01T00:00:00Z",
    "merchantName": "Acme",
    "metadata": {"externalDisputeId": "visa-123"},
}


# ── Unit tests for triage_agent_client ────────────────────────────────────────

class TestBuildCaseSummary:
    def test_includes_key_fields(self):
        summary = _build_case_summary(_SAMPLE_CASE)
        assert "visa" in summary
        assert "13.1" in summary
        assert "99.99" in summary
        assert "Acme Corp" in summary

    def test_evidence_completeness_label(self):
        no_evidence = {**_SAMPLE_CASE, "evidence": []}
        assert "no evidence" in _build_case_summary(no_evidence)

        one_item = {**_SAMPLE_CASE, "evidence": [{"type": "x"}]}
        assert "partial" in _build_case_summary(one_item)

        two_items = {**_SAMPLE_CASE, "evidence": [{"type": "x"}, {"type": "y"}]}
        assert "complete" in _build_case_summary(two_items)


class TestParseAgentResponse:
    def test_valid_json_returns_foundry_result(self):
        raw = '{"score": 0.75, "category": "auto_approve"}'
        result = _parse_agent_response(raw)
        assert result["score"] == pytest.approx(0.75)
        assert result["category"] == "auto_approve"
        assert result["source"] == "foundry"
        assert result["rawResponse"] == raw

    def test_score_is_clamped(self):
        result = _parse_agent_response('{"score": 1.5, "category": "escalate"}')
        assert result["score"] == pytest.approx(1.0)

        result2 = _parse_agent_response('{"score": -0.2, "category": "review"}')
        assert result2["score"] == pytest.approx(0.0)

    def test_invalid_json_falls_back_to_stub_defaults(self):
        result = _parse_agent_response("not json")
        assert result["score"] == pytest.approx(0.5)
        assert result["category"] == "review"
        assert result["source"] == "foundry"  # source stays "foundry" — response came from agent
        assert result["rawResponse"] == "not json"


class TestScoreDispute:
    def test_returns_stub_when_env_vars_unset(self, monkeypatch):
        monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
        monkeypatch.delenv("FOUNDRY_TRIAGE_AGENT_ID", raising=False)

        result = score_dispute(_SAMPLE_CASE)

        assert result["score"] == pytest.approx(0.5)
        assert result["category"] == "review"
        assert result["source"] == "stub"
        assert result["rawResponse"] is None

    def test_returns_stub_when_endpoint_blank(self, monkeypatch):
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "")
        monkeypatch.setenv("FOUNDRY_TRIAGE_AGENT_ID", "asst_abc")

        result = score_dispute(_SAMPLE_CASE)
        assert result["source"] == "stub"

    def test_returns_stub_when_agent_id_blank(self, monkeypatch):
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://example.ai.azure.com/api/projects/p1")
        monkeypatch.setenv("FOUNDRY_TRIAGE_AGENT_ID", "")

        result = score_dispute(_SAMPLE_CASE)
        assert result["source"] == "stub"

    def test_returns_stub_when_foundry_call_raises(self, monkeypatch):
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://example.ai.azure.com/api/projects/p1")
        monkeypatch.setenv("FOUNDRY_TRIAGE_AGENT_ID", "asst_abc")

        with patch("services.triage_agent_client._call_foundry_agent", side_effect=RuntimeError("timeout")):
            result = score_dispute(_SAMPLE_CASE)

        assert result["source"] == "stub"
        assert result["score"] == pytest.approx(0.5)

    def test_returns_foundry_result_on_success(self, monkeypatch):
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://example.ai.azure.com/api/projects/p1")
        monkeypatch.setenv("FOUNDRY_TRIAGE_AGENT_ID", "asst_abc")

        expected = {"score": 0.82, "category": "auto_approve", "source": "foundry", "rawResponse": "..."}
        with patch("services.triage_agent_client._call_foundry_agent", return_value=expected):
            result = score_dispute(_SAMPLE_CASE)

        assert result["score"] == pytest.approx(0.82)
        assert result["category"] == "auto_approve"
        assert result["source"] == "foundry"

    def test_never_raises(self, monkeypatch):
        """score_dispute must not propagate any exception."""
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://example.ai.azure.com/api/projects/p1")
        monkeypatch.setenv("FOUNDRY_TRIAGE_AGENT_ID", "asst_abc")

        with patch(
            "services.triage_agent_client._call_foundry_agent",
            side_effect=Exception("unexpected crash"),
        ):
            result = score_dispute(_SAMPLE_CASE)  # must not raise

        assert result["source"] == "stub"


# ── Integration tests — triage wired into intake_dispute_record ───────────────

class TestIntakeDisputeRecordTriageIntegration:
    def _mock_cosmos(self, mock_cosmos):
        mock_cosmos.query_disputes.return_value = []
        mock_cosmos.create_dispute.side_effect = lambda d: d
        mock_cosmos.create_timeline_event.return_value = None
        mock_cosmos.create_evidence.return_value = None
        mock_cosmos.upsert_dispute.return_value = None

    def test_triage_fields_persisted_to_cosmos(self, monkeypatch):
        """triageScore, triageCategory, triageSource must appear on the upserted document."""
        monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
        monkeypatch.delenv("FOUNDRY_TRIAGE_AGENT_ID", raising=False)

        with (
            patch("triggers.pl_ingest_raw.cosmos_client") as mock_cosmos,
            patch("triggers.pl_ingest_raw.start_dispute_orchestration", return_value="started"),
        ):
            self._mock_cosmos(mock_cosmos)
            result = intake_dispute_record(_STANDARD_RECORD)

        assert result["outcome"] == "created"
        mock_cosmos.upsert_dispute.assert_called_once()
        upserted = mock_cosmos.upsert_dispute.call_args[0][0]
        assert "triageScore" in upserted
        assert "triageCategory" in upserted
        assert "triageSource" in upserted
        assert upserted["triageScore"] == pytest.approx(0.5)
        assert upserted["triageCategory"] == "review"
        assert upserted["triageSource"] == "stub"

    def test_triage_fields_from_foundry_when_configured(self, monkeypatch):
        """When Foundry is configured and succeeds, foundry result is persisted."""
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://example.ai.azure.com/api/projects/p1")
        monkeypatch.setenv("FOUNDRY_TRIAGE_AGENT_ID", "asst_abc")

        foundry_result = {
            "score": 0.9,
            "category": "auto_approve",
            "source": "foundry",
            "rawResponse": '{"score": 0.9, "category": "auto_approve"}',
        }

        with (
            patch("triggers.pl_ingest_raw.cosmos_client") as mock_cosmos,
            patch("triggers.pl_ingest_raw.start_dispute_orchestration", return_value="started"),
            patch("triggers.pl_ingest_raw.score_dispute", return_value=foundry_result),
        ):
            self._mock_cosmos(mock_cosmos)
            result = intake_dispute_record(_STANDARD_RECORD)

        assert result["outcome"] == "created"
        upserted = mock_cosmos.upsert_dispute.call_args[0][0]
        assert upserted["triageScore"] == pytest.approx(0.9)
        assert upserted["triageCategory"] == "auto_approve"
        assert upserted["triageSource"] == "foundry"

    def test_ingestion_succeeds_if_triage_raises(self, monkeypatch):
        """Ingestion must complete even if score_dispute raises an unhandled exception."""
        monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
        monkeypatch.delenv("FOUNDRY_TRIAGE_AGENT_ID", raising=False)

        with (
            patch("triggers.pl_ingest_raw.cosmos_client") as mock_cosmos,
            patch("triggers.pl_ingest_raw.start_dispute_orchestration", return_value="started"),
            patch("triggers.pl_ingest_raw.score_dispute", side_effect=RuntimeError("agent exploded")),
        ):
            self._mock_cosmos(mock_cosmos)
            result = intake_dispute_record(_STANDARD_RECORD)

        # Ingestion must succeed — the case lands in Cosmos
        assert result["outcome"] == "created"
        mock_cosmos.create_dispute.assert_called_once()
        # upsert should NOT be called when score_dispute itself raised
        mock_cosmos.upsert_dispute.assert_not_called()

    def test_ingestion_succeeds_if_triage_raises_and_upsert_raises(self, monkeypatch):
        """Ingestion must complete even if both scoring AND the Cosmos upsert fail."""
        monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
        monkeypatch.delenv("FOUNDRY_TRIAGE_AGENT_ID", raising=False)

        with (
            patch("triggers.pl_ingest_raw.cosmos_client") as mock_cosmos,
            patch("triggers.pl_ingest_raw.start_dispute_orchestration", return_value="started"),
        ):
            self._mock_cosmos(mock_cosmos)
            mock_cosmos.upsert_dispute.side_effect = RuntimeError("cosmos write failed")
            # score_dispute returns stub, but then upsert raises — ingestion must still complete
            result = intake_dispute_record(_STANDARD_RECORD)

        assert result["outcome"] == "created"
        mock_cosmos.create_dispute.assert_called_once()
