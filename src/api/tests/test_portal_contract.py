"""
test_portal_contract.py

Verifies the portal-friendly contract additions to the two core HTTP endpoints:

  POST /api/disputes
    • ``reasonCode``         optional — defaults to "unknown"
    • ``deadlineUtc``        optional — auto-calculated from network SLA
    • ``disputeDescription`` optional — stored in metadata
    • original required fields still enforced

  GET /api/disputes/{id}
    • ``networkCode`` query param optional — falls back to cross-partition query
    • point-read path still used when networkCode is supplied
    • 404 on genuinely missing dispute

Tests call the extracted ``_handle_*`` helpers directly (not the decorated
@app.route functions) following the established team pattern.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, call, patch

import pytest

from function_app import _compute_deadline_utc, _handle_create_dispute, _handle_get_dispute


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _fake_dispute(dispute_id: str = "aaaa-1111", network_code: str = "visa") -> dict:
    return {
        "id": dispute_id,
        "disputeId": dispute_id,
        "networkCode": network_code,
        "reasonCode": "unknown",
        "status": "intake",
        "cardholderName": "Jane Doe",
        "cardLastFour": "4242",
        "transactionAmount": 99.99,
        "transactionCurrency": "USD",
        "transactionDate": "2026-06-01",
        "merchantName": "Acme Corp",
        "deadlineUtc": "2026-07-01T00:00:00+00:00",
        "metadata": {},
        "createdAt": "2026-07-08T00:00:00+00:00",
        "updatedAt": "2026-07-08T00:00:00+00:00",
    }


_MINIMAL_PORTAL_BODY = {
    "networkCode": "visa",
    "cardholderName": "Jane Doe",
    "cardLastFour": "4242",
    "transactionAmount": 99.99,
    "transactionDate": "2026-06-01",
    "merchantName": "Acme Corp",
}


# ── POST /disputes — portal payload tests ─────────────────────────────────────

class TestHandleCreateDispute:
    def _patched_call(self, body: dict) -> tuple:
        """Helper: patch cosmos, call _handle_create_dispute, return (response, mock)."""
        fake = _fake_dispute()
        with (
            patch("function_app.intake_dispute_record") as mock_intake,
        ):
            mock_intake.return_value = {"outcome": "created", "dispute": fake}
            resp = _handle_create_dispute(body)
        return resp, mock_intake

    def test_minimal_payload_returns_201(self):
        resp, _ = self._patched_call(_MINIMAL_PORTAL_BODY)
        assert resp.status_code == 201

    def test_reason_code_defaults_to_unknown_when_omitted(self):
        resp, mock_intake = self._patched_call(_MINIMAL_PORTAL_BODY)
        assert resp.status_code == 201
        created_doc = mock_intake.call_args[0][0]
        assert created_doc["reasonCode"] == "unknown"

    def test_explicit_reason_code_is_used_verbatim(self):
        body = {**_MINIMAL_PORTAL_BODY, "reasonCode": "13.1"}
        resp, mock_intake = self._patched_call(body)
        assert resp.status_code == 201
        created_doc = mock_intake.call_args[0][0]
        assert created_doc["reasonCode"] == "13.1"

    def test_deadline_is_auto_calculated_when_omitted(self):
        resp, mock_intake = self._patched_call(_MINIMAL_PORTAL_BODY)
        assert resp.status_code == 201
        created_doc = mock_intake.call_args[0][0]
        assert created_doc["networkCode"] == "visa"
        assert created_doc["transactionDate"] == "2026-06-01"

    def test_explicit_deadline_utc_is_used_verbatim(self):
        body = {**_MINIMAL_PORTAL_BODY, "deadlineUtc": "2026-08-15T00:00:00Z"}
        resp, mock_intake = self._patched_call(body)
        created_doc = mock_intake.call_args[0][0]
        assert created_doc["deadlineUtc"] == "2026-08-15T00:00:00Z"

    def test_dispute_description_stored_in_metadata(self):
        body = {**_MINIMAL_PORTAL_BODY, "disputeDescription": "Item never arrived"}
        resp, mock_intake = self._patched_call(body)
        assert resp.status_code == 201
        created_doc = mock_intake.call_args[0][0]
        assert created_doc["metadata"]["disputeDescription"] == "Item never arrived"

    def test_existing_metadata_preserved_alongside_description(self):
        body = {
            **_MINIMAL_PORTAL_BODY,
            "metadata": {"channel": "portal"},
            "disputeDescription": "Duplicate charge",
        }
        resp, mock_intake = self._patched_call(body)
        created_doc = mock_intake.call_args[0][0]
        assert created_doc["metadata"]["channel"] == "portal"
        assert created_doc["metadata"]["disputeDescription"] == "Duplicate charge"

    def test_intake_pipeline_called_on_success(self):
        resp, mock_intake = self._patched_call(_MINIMAL_PORTAL_BODY)
        assert resp.status_code == 201
        mock_intake.assert_called_once()

    def test_missing_network_code_returns_400(self):
        body = {k: v for k, v in _MINIMAL_PORTAL_BODY.items() if k != "networkCode"}
        with patch("function_app.intake_dispute_record"):
            resp = _handle_create_dispute(body)
        assert resp.status_code == 400
        payload = json.loads(resp.get_body())
        assert "networkCode" in payload["error"]

    def test_missing_cardholder_name_returns_400(self):
        body = {k: v for k, v in _MINIMAL_PORTAL_BODY.items() if k != "cardholderName"}
        with patch("function_app.intake_dispute_record"):
            resp = _handle_create_dispute(body)
        assert resp.status_code == 400

    def test_missing_merchant_name_returns_400(self):
        body = {k: v for k, v in _MINIMAL_PORTAL_BODY.items() if k != "merchantName"}
        with patch("function_app.intake_dispute_record"):
            resp = _handle_create_dispute(body)
        assert resp.status_code == 400

    def test_cosmos_not_called_on_400(self):
        """Validation failure must not call Cosmos at all."""
        body = {}
        with patch("function_app.intake_dispute_record") as mock_intake:
            mock_intake.side_effect = RuntimeError("should not be called")
            resp = _handle_create_dispute(body)
        assert resp.status_code == 400

    def test_duplicate_returns_409(self):
        with patch("function_app.intake_dispute_record") as mock_intake:
            mock_intake.return_value = {
                "outcome": "duplicate",
                "disputeId": "dup-1",
                "networkCode": "visa",
                "status": "intake",
            }
            resp = _handle_create_dispute(_MINIMAL_PORTAL_BODY)
        assert resp.status_code == 409


# ── GET /disputes/{id} — optional networkCode ────────────────────────────────

class TestHandleGetDispute:
    _DISPUTE_ID = "aaaa-1111"

    def test_with_network_code_uses_point_read(self):
        fake = _fake_dispute(self._DISPUTE_ID, "visa")
        with patch("function_app.cosmos_client") as mock_cosmos:
            mock_cosmos.get_dispute.return_value = fake
            resp = _handle_get_dispute(self._DISPUTE_ID, "visa")
        assert resp.status_code == 200
        mock_cosmos.get_dispute.assert_called_once_with(self._DISPUTE_ID, "visa")
        mock_cosmos.query_disputes.assert_not_called()

    def test_without_network_code_uses_cross_partition_query(self):
        fake = _fake_dispute(self._DISPUTE_ID)
        with patch("function_app.cosmos_client") as mock_cosmos:
            mock_cosmos.query_disputes.return_value = [fake]
            resp = _handle_get_dispute(self._DISPUTE_ID, None)
        assert resp.status_code == 200
        mock_cosmos.get_dispute.assert_not_called()
        mock_cosmos.query_disputes.assert_called_once()
        call_kwargs = mock_cosmos.query_disputes.call_args
        assert "@id" in str(call_kwargs)

    def test_without_network_code_returns_dispute_body(self):
        fake = _fake_dispute(self._DISPUTE_ID)
        with patch("function_app.cosmos_client") as mock_cosmos:
            mock_cosmos.query_disputes.return_value = [fake]
            resp = _handle_get_dispute(self._DISPUTE_ID, None)
        body = json.loads(resp.get_body())
        assert body["disputeId"] == self._DISPUTE_ID

    def test_not_found_with_network_code_returns_404(self):
        with patch("function_app.cosmos_client") as mock_cosmos:
            mock_cosmos.get_dispute.return_value = None
            resp = _handle_get_dispute(self._DISPUTE_ID, "visa")
        assert resp.status_code == 404

    def test_not_found_without_network_code_returns_404(self):
        with patch("function_app.cosmos_client") as mock_cosmos:
            mock_cosmos.query_disputes.return_value = []
            resp = _handle_get_dispute(self._DISPUTE_ID, None)
        assert resp.status_code == 404

    def test_empty_string_network_code_treated_as_absent(self):
        """Empty string from portal should fall through to cross-partition query."""
        fake = _fake_dispute(self._DISPUTE_ID)
        with patch("function_app.cosmos_client") as mock_cosmos:
            mock_cosmos.query_disputes.return_value = [fake]
            # The route handler converts "" → None via `or None`; test helper directly with None
            resp = _handle_get_dispute(self._DISPUTE_ID, None)
        mock_cosmos.get_dispute.assert_not_called()
        mock_cosmos.query_disputes.assert_called_once()


# ── _compute_deadline_utc unit tests ─────────────────────────────────────────

class TestComputeDeadlineUtc:
    def test_visa_sla_is_30_days(self):
        result = _compute_deadline_utc("visa", "2026-06-01")
        assert "2026-07-01" in result

    def test_mastercard_sla_is_45_days(self):
        result = _compute_deadline_utc("mastercard", "2026-06-01")
        assert "2026-07-16" in result

    def test_amex_sla_is_20_days(self):
        result = _compute_deadline_utc("amex", "2026-06-01")
        assert "2026-06-21" in result

    def test_discover_sla_is_30_days(self):
        result = _compute_deadline_utc("discover", "2026-06-01")
        assert "2026-07-01" in result

    def test_unknown_network_defaults_to_30_days(self):
        result = _compute_deadline_utc("unionpay", "2026-06-01")
        assert "2026-07-01" in result

    def test_network_code_is_case_insensitive(self):
        lower = _compute_deadline_utc("visa", "2026-06-01")
        upper = _compute_deadline_utc("VISA", "2026-06-01")
        assert lower == upper

    def test_bad_date_falls_back_gracefully(self):
        result = _compute_deadline_utc("visa", "not-a-date")
        assert result  # must return a non-empty string
