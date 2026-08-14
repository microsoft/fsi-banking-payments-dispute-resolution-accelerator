"""
test_cosmos_store.py

Tests for the env-selectable Cosmos DB store (``CASE_STORE=cosmos``) and for
the synthetic-mode guardrail that no Cosmos client is invoked when
``CASE_STORE`` is unset or ``synthetic``.

All Cosmos calls are mocked — tests require no real Cosmos account or network.

Coverage:
  1.  CASE_STORE=cosmos — list_cases returns CaseSummary dicts with live daysRemaining.
  2.  CASE_STORE=cosmos — status filter forwarded to Cosmos query.
  3.  CASE_STORE=cosmos — empty result → empty list.
  4.  CASE_STORE=cosmos — get_case returns full Case dict with live daysRemaining.
  5.  CASE_STORE=cosmos — get_case for missing caseId returns None.
  6.  CASE_STORE=cosmos — update_case_status patches status + updatedAt.
  7.  CASE_STORE=cosmos — update_case_status raises KeyError for unknown caseId.
  8.  CASE_STORE=synthetic (default) — list_cases does NOT call cosmos_client.
  9.  CASE_STORE=synthetic (default) — get_case does NOT call cosmos_client.
  10. CASE_STORE=cosmos — list_cases results sorted by dueDate ascending.
"""
from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from services.case_store import (
    _compute_days_remaining,
    get_case,
    list_cases,
    update_case_status,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_case(
    case_id: str = "aaaaaaaa-0000-0000-0000-000000000001",
    status: str = "pending_review",
    card_network: str = "visa",
    days_from_now: int = 10,
) -> dict:
    """Return a minimal Case-contract document as would be stored in Cosmos."""
    due_date = (date.today() + timedelta(days=days_from_now)).isoformat()
    return {
        # Case-contract fields
        "caseId": case_id,
        "status": status,
        "cardNetwork": card_network,
        "merchantName": "Test Merchant",
        "transactionAmount": 150.00,
        "reasonCode": "10.4",
        "reasonCodeLabel": "Other Fraud",
        "winProbability": 0.72,
        "riskLevel": "medium",
        "deadline": {
            "network": card_network,
            "dueDate": due_date,
            "daysRemaining": 999,  # stale — must be recomputed live
        },
        "evidence": [{"type": "transaction", "id": "ev-1"}],
        "evidenceGaps": [],
        "rebuttalDraft": {"text": "draft text", "citations": []},
        "createdAt": "2026-06-01T00:00:00Z",
        "updatedAt": "2026-06-01T12:00:00Z",
        # Cosmos PK helper fields
        "id": case_id,
        "disputeId": case_id,
        "networkCode": card_network,
    }


@pytest.fixture
def cosmos_case():
    """A single minimal Case-contract Cosmos document."""
    return _make_case()


@pytest.fixture
def cosmos_case_list():
    """Three Case-contract Cosmos documents with varying dueDates."""
    return [
        _make_case("aaaaaaaa-0000-0000-0000-000000000001", days_from_now=5),
        _make_case("aaaaaaaa-0000-0000-0000-000000000002", days_from_now=20),
        _make_case("aaaaaaaa-0000-0000-0000-000000000003", days_from_now=1),
    ]


# ---------------------------------------------------------------------------
# 1–3: list_cases in cosmos mode
# ---------------------------------------------------------------------------

class TestCosmosListCases:
    def test_returns_case_summary_dicts(self, cosmos_case, monkeypatch):
        monkeypatch.setenv("CASE_STORE", "cosmos")
        with patch("cosmos_client.query_disputes", return_value=[cosmos_case]) as mock_qd:
            results = list_cases()

        assert len(results) == 1
        s = results[0]
        assert s["caseId"] == cosmos_case["caseId"]
        assert s["status"] == cosmos_case["status"]
        assert "deadline" in s
        assert "daysRemaining" in s["deadline"]
        # CaseSummary must NOT include 'network' in deadline
        assert "network" not in s["deadline"]
        mock_qd.assert_called_once()

    def test_days_remaining_recomputed_live(self, cosmos_case, monkeypatch):
        monkeypatch.setenv("CASE_STORE", "cosmos")
        with patch("cosmos_client.query_disputes", return_value=[cosmos_case]):
            results = list_cases()

        s = results[0]
        expected = _compute_days_remaining(s["deadline"]["dueDate"])
        assert s["deadline"]["daysRemaining"] == expected
        # The stale value 999 must NOT appear
        assert s["deadline"]["daysRemaining"] != 999

    def test_status_filter_forwarded_to_query(self, cosmos_case, monkeypatch):
        monkeypatch.setenv("CASE_STORE", "cosmos")
        with patch("cosmos_client.query_disputes", return_value=[cosmos_case]) as mock_qd:
            list_cases(status_filter="pending_review")

        call_args = mock_qd.call_args
        query: str = call_args[0][0]
        params: list = call_args[0][1]
        assert "@status" in query
        assert any(p.get("value") == "pending_review" for p in params)

    def test_no_filter_uses_select_all(self, cosmos_case, monkeypatch):
        monkeypatch.setenv("CASE_STORE", "cosmos")
        with patch("cosmos_client.query_disputes", return_value=[cosmos_case]) as mock_qd:
            list_cases()

        call_args = mock_qd.call_args
        query: str = call_args[0][0]
        assert "WHERE" not in query.upper()

    def test_empty_cosmos_returns_empty_list(self, monkeypatch):
        monkeypatch.setenv("CASE_STORE", "cosmos")
        with patch("cosmos_client.query_disputes", return_value=[]):
            results = list_cases()

        assert results == []

    def test_sorted_by_due_date_ascending(self, cosmos_case_list, monkeypatch):
        monkeypatch.setenv("CASE_STORE", "cosmos")
        with patch("cosmos_client.query_disputes", return_value=cosmos_case_list):
            results = list_cases()

        due_dates = [s["deadline"]["dueDate"] for s in results]
        assert due_dates == sorted(due_dates)

    def test_skips_malformed_doc_and_logs_warning(self, cosmos_case, monkeypatch, caplog):
        monkeypatch.setenv("CASE_STORE", "cosmos")
        malformed = {
            "id": "9a307795-2a0d-40c0-9767-4b7b4362a441",
            "_ts": 1720540800,
            "status": "pending_review",
            "disputeId": "9a307795-2a0d-40c0-9767-4b7b4362a441",
            "deadline": {"dueDate": cosmos_case["deadline"]["dueDate"]},
        }
        with (
            patch("cosmos_client.query_disputes", return_value=[cosmos_case, malformed]),
            caplog.at_level(logging.WARNING),
        ):
            results = list_cases()

        assert [r["caseId"] for r in results] == [cosmos_case["caseId"]]
        assert "missing required field 'caseId'" in caplog.text
        assert "id=9a307795-2a0d-40c0-9767-4b7b4362a441" in caplog.text
        assert "_ts=1720540800" in caplog.text


# ---------------------------------------------------------------------------
# 4–5: get_case in cosmos mode
# ---------------------------------------------------------------------------

class TestCosmosGetCase:
    def test_returns_full_case_dict(self, cosmos_case, monkeypatch):
        monkeypatch.setenv("CASE_STORE", "cosmos")
        with patch("cosmos_client.query_disputes", return_value=[cosmos_case]):
            result = get_case(cosmos_case["caseId"])

        assert result is not None
        assert result["caseId"] == cosmos_case["caseId"]
        # Full case must include evidence and rebuttalDraft
        assert "evidence" in result
        assert "rebuttalDraft" in result

    def test_days_remaining_recomputed_live(self, cosmos_case, monkeypatch):
        monkeypatch.setenv("CASE_STORE", "cosmos")
        with patch("cosmos_client.query_disputes", return_value=[cosmos_case]):
            result = get_case(cosmos_case["caseId"])

        due_date = result["deadline"]["dueDate"]
        expected = _compute_days_remaining(due_date)
        assert result["deadline"]["daysRemaining"] == expected
        assert result["deadline"]["daysRemaining"] != 999

    def test_missing_case_returns_none(self, monkeypatch):
        monkeypatch.setenv("CASE_STORE", "cosmos")
        with patch("cosmos_client.query_disputes", return_value=[]):
            result = get_case("00000000-0000-0000-0000-000000000000")

        assert result is None

    def test_query_uses_id_param(self, cosmos_case, monkeypatch):
        monkeypatch.setenv("CASE_STORE", "cosmos")
        target_id = cosmos_case["caseId"]
        with patch("cosmos_client.query_disputes", return_value=[cosmos_case]) as mock_qd:
            get_case(target_id)

        call_args = mock_qd.call_args
        params: list = call_args[0][1]
        assert any(p.get("value") == target_id for p in params)

    def test_malformed_case_returns_none_and_logs_warning(self, monkeypatch, caplog):
        monkeypatch.setenv("CASE_STORE", "cosmos")
        malformed = {
            "id": "9a307795-2a0d-40c0-9767-4b7b4362a441",
            "_ts": 1720540800,
            "status": "pending_review",
            "deadline": {"dueDate": (date.today() + timedelta(days=3)).isoformat()},
        }
        with (
            patch("cosmos_client.query_disputes", return_value=[malformed]),
            caplog.at_level(logging.WARNING),
        ):
            result = get_case("9a307795-2a0d-40c0-9767-4b7b4362a441")

        assert result is None
        assert "missing required field 'caseId'" in caplog.text
        assert "id=9a307795-2a0d-40c0-9767-4b7b4362a441" in caplog.text


# ---------------------------------------------------------------------------
# 6–7: update_case_status in cosmos mode
# ---------------------------------------------------------------------------

class TestCosmosUpdateCaseStatus:
    def test_status_updated_in_document(self, cosmos_case, monkeypatch):
        monkeypatch.setenv("CASE_STORE", "cosmos")
        with (
            patch("cosmos_client.query_disputes", return_value=[cosmos_case]),
            patch("cosmos_client.update_dispute") as mock_upd,
        ):
            update_case_status(cosmos_case["caseId"], "approved")

        mock_upd.assert_called_once()
        saved_doc = mock_upd.call_args[0][0]
        assert saved_doc["status"] == "approved"

    def test_updated_at_is_stamped(self, cosmos_case, monkeypatch):
        monkeypatch.setenv("CASE_STORE", "cosmos")
        with (
            patch("cosmos_client.query_disputes", return_value=[cosmos_case]),
            patch("cosmos_client.update_dispute") as mock_upd,
        ):
            update_case_status(cosmos_case["caseId"], "approved")

        saved_doc = mock_upd.call_args[0][0]
        assert saved_doc["updatedAt"] != cosmos_case["updatedAt"]

    def test_unknown_case_raises_key_error(self, monkeypatch):
        monkeypatch.setenv("CASE_STORE", "cosmos")
        with (
            patch("cosmos_client.query_disputes", return_value=[]),
            pytest.raises(KeyError, match="not found"),
        ):
            update_case_status("00000000-0000-0000-0000-000000000000", "approved")


# ---------------------------------------------------------------------------
# 8–9: Synthetic mode guardrail — cosmos_client must never be called
# ---------------------------------------------------------------------------

class TestSyntheticModeNoCosmos:
    def test_list_cases_does_not_call_cosmos(self, monkeypatch):
        monkeypatch.delenv("CASE_STORE", raising=False)
        with patch("cosmos_client.query_disputes") as mock_qd:
            results = list_cases()

        mock_qd.assert_not_called()
        assert isinstance(results, list)

    def test_get_case_does_not_call_cosmos(self, monkeypatch, known_case_id):
        monkeypatch.delenv("CASE_STORE", raising=False)
        with patch("cosmos_client.query_disputes") as mock_qd:
            result = get_case(known_case_id)

        mock_qd.assert_not_called()
        assert result is not None

    def test_synthetic_explicit_does_not_call_cosmos(self, monkeypatch, known_case_id):
        monkeypatch.setenv("CASE_STORE", "synthetic")
        with patch("cosmos_client.query_disputes") as mock_qd:
            list_cases()
            get_case(known_case_id)

        mock_qd.assert_not_called()

    def test_update_case_status_is_noop_in_synthetic(self, monkeypatch, known_case_id):
        monkeypatch.setenv("CASE_STORE", "synthetic")
        with patch("cosmos_client.update_dispute") as mock_upd:
            # Must not raise; must not call Cosmos
            update_case_status(known_case_id, "approved")

        mock_upd.assert_not_called()
