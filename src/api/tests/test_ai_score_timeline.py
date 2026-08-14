"""
test_ai_score_timeline.py

Regression tests for two fixes introduced in fix/ai-score-timeline-display:

  1. Timeline normalization — Azure Function timeline endpoints must map Cosmos
     ``occurredAt``/``detail``/``data`` fields to the portal contract's
     ``timestamp``/``description``/``metadata`` before responding.

  2. score_generated on portal intake — when _handle_create_dispute resolves a
     reason-code win-rate (initial AI estimate), a ``score_generated`` timeline
     event must be persisted to Cosmos so the portal Processing Timeline shows
     the initial assessment immediately after submission.

These tests call the extracted helpers directly (``_normalize_timeline_event``,
``_handle_create_dispute``) following the established team pattern.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, call, patch

import pytest

from function_app import _normalize_timeline_event, _handle_create_dispute


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _cosmos_style_event(**overrides) -> dict:
    """Return a Cosmos-shaped timeline event (occurredAt / detail / data)."""
    ev = {
        "id": "evt-1",
        "eventId": "evt-1",
        "disputeId": "disp-1",
        "eventType": "case_created",
        "actor": "customer",
        "detail": "Dispute submitted by customer",
        "data": {"source": "portal_api"},
        "occurredAt": "2026-07-01T00:00:00+00:00",
    }
    ev.update(overrides)
    return ev


_MINIMAL_PORTAL_BODY = {
    "networkCode": "visa",
    "cardholderName": "Jane Doe",
    "cardLastFour": "4242",
    "transactionAmount": 99.99,
    "transactionDate": "2026-06-01",
    "merchantName": "Acme Corp",
}

_FAKE_DISPUTE = {
    "id": "test-disp-1",
    "disputeId": "test-disp-1",
    "networkCode": "visa",
    "reasonCode": "13.1",
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


# ── 1. Timeline normalization tests ───────────────────────────────────────────

class TestNormalizeTimelineEvent:
    def test_occurredat_mapped_to_timestamp(self):
        ev = _cosmos_style_event()
        result = _normalize_timeline_event(ev)
        assert "timestamp" in result
        assert result["timestamp"] == "2026-07-01T00:00:00+00:00"

    def test_detail_mapped_to_description(self):
        ev = _cosmos_style_event()
        result = _normalize_timeline_event(ev)
        assert "description" in result
        assert result["description"] == "Dispute submitted by customer"

    def test_data_mapped_to_metadata(self):
        ev = _cosmos_style_event()
        result = _normalize_timeline_event(ev)
        assert "metadata" in result
        assert result["metadata"] == {"source": "portal_api"}

    def test_status_change_normalized_to_status_changed(self):
        ev = _cosmos_style_event(eventType="status_change")
        result = _normalize_timeline_event(ev)
        assert result["eventType"] == "status_changed"

    def test_existing_timestamp_not_overwritten(self):
        """If ``timestamp`` already exists, ``occurredAt`` must not replace it."""
        ev = _cosmos_style_event(timestamp="2026-07-15T00:00:00+00:00")
        result = _normalize_timeline_event(ev)
        assert result["timestamp"] == "2026-07-15T00:00:00+00:00"

    def test_existing_description_not_overwritten(self):
        ev = _cosmos_style_event(description="Already set")
        result = _normalize_timeline_event(ev)
        assert result["description"] == "Already set"

    def test_event_without_occurredat_unchanged(self):
        ev = {"id": "x", "eventType": "case_created", "timestamp": "2026-07-01T00:00:00+00:00"}
        result = _normalize_timeline_event(ev)
        assert result["timestamp"] == "2026-07-01T00:00:00+00:00"
        assert "occurredAt" not in result

    def test_returns_copy_not_mutating_original(self):
        ev = _cosmos_style_event()
        result = _normalize_timeline_event(ev)
        assert "timestamp" in result
        assert "timestamp" not in ev  # original untouched

    def test_non_status_change_eventtype_unchanged(self):
        ev = _cosmos_style_event(eventType="score_generated")
        result = _normalize_timeline_event(ev)
        assert result["eventType"] == "score_generated"


# ── 2. score_generated emitted during portal intake ───────────────────────────

class TestPortalIntakeScoreGenerated:
    """
    _handle_create_dispute should emit a score_generated timeline event when
    the reason-code engine resolves a winRate for the created dispute.
    """

    _REASON_CODE_DETAIL = {
        "description": "Not as described",
        "category": "review",
        "categoryLabel": "Needs Review",
        "winRate": 0.62,
        "timeLimitDays": 30,
        "evidenceRequired": ["receipt", "communication"],
    }

    def _call_with_reason_code_detail(self, detail=None):
        """
        Helper: patch cosmos + intake + reason-code engine, call
        _handle_create_dispute, return (response, cosmos_mock).
        """
        detail = detail if detail is not None else self._REASON_CODE_DETAIL
        fake = dict(_FAKE_DISPUTE)
        with (
            patch("function_app.intake_dispute_record") as mock_intake,
            patch("function_app.cosmos_client") as mock_cosmos,
            patch("function_app.get_reason_code_detail") as mock_detail,
        ):
            mock_intake.return_value = {"outcome": "created", "dispute": fake}
            mock_detail.return_value = detail
            resp = _handle_create_dispute({**_MINIMAL_PORTAL_BODY, "reasonCode": "13.1"})
            return resp, mock_cosmos

    def test_score_generated_event_created_when_win_rate_available(self):
        _, mock_cosmos = self._call_with_reason_code_detail()
        assert mock_cosmos.create_timeline_event.called, (
            "create_timeline_event must be called for score_generated"
        )
        calls = mock_cosmos.create_timeline_event.call_args_list
        event_types = [c.args[0].get("eventType") for c in calls]
        assert "score_generated" in event_types, (
            f"No score_generated event found in timeline calls: {event_types}"
        )

    def test_score_generated_event_contains_win_rate(self):
        _, mock_cosmos = self._call_with_reason_code_detail()
        calls = mock_cosmos.create_timeline_event.call_args_list
        score_event = next(
            c.args[0] for c in calls if c.args[0].get("eventType") == "score_generated"
        )
        data = score_event.get("data", {})
        assert abs(data.get("score", 0) - 0.62) < 1e-6, (
            f"Expected score=0.62, got {data.get('score')}"
        )

    def test_score_generated_actor_is_reason_code_engine(self):
        _, mock_cosmos = self._call_with_reason_code_detail()
        calls = mock_cosmos.create_timeline_event.call_args_list
        score_event = next(
            c.args[0] for c in calls if c.args[0].get("eventType") == "score_generated"
        )
        assert score_event.get("actor") == "reason_code_engine"

    def test_score_generated_source_field_set(self):
        _, mock_cosmos = self._call_with_reason_code_detail()
        calls = mock_cosmos.create_timeline_event.call_args_list
        score_event = next(
            c.args[0] for c in calls if c.args[0].get("eventType") == "score_generated"
        )
        assert score_event.get("data", {}).get("source") == "reason_code_engine"

    def test_no_score_generated_when_reason_code_detail_absent(self):
        """When the reason-code engine returns None, no score_generated event is emitted."""
        fake = dict(_FAKE_DISPUTE)
        with (
            patch("function_app.intake_dispute_record") as mock_intake,
            patch("function_app.cosmos_client") as mock_cosmos,
            patch("function_app.get_reason_code_detail") as mock_detail,
        ):
            mock_intake.return_value = {"outcome": "created", "dispute": fake}
            mock_detail.return_value = None
            resp = _handle_create_dispute({**_MINIMAL_PORTAL_BODY, "reasonCode": "unknown"})

        score_calls = [
            c for c in mock_cosmos.create_timeline_event.call_args_list
            if c.args[0].get("eventType") == "score_generated"
        ]
        assert score_calls == [], (
            "score_generated must not be emitted when no reason-code detail is available"
        )

    def test_score_generated_failure_does_not_break_intake(self):
        """Even if Cosmos raises when persisting the score_generated event, the
        intake response must still be HTTP 201 and not propagate the exception."""
        fake = dict(_FAKE_DISPUTE)
        with (
            patch("function_app.intake_dispute_record") as mock_intake,
            patch("function_app.cosmos_client") as mock_cosmos,
            patch("function_app.get_reason_code_detail") as mock_detail,
        ):
            mock_intake.return_value = {"outcome": "created", "dispute": fake}
            mock_detail.return_value = self._REASON_CODE_DETAIL
            mock_cosmos.create_timeline_event.side_effect = RuntimeError("Cosmos unavailable")
            resp = _handle_create_dispute({**_MINIMAL_PORTAL_BODY, "reasonCode": "13.1"})

        assert resp.status_code == 201, (
            "Intake must succeed even when score_generated event persistence fails"
        )

    def test_intake_response_still_201_with_score_generated(self):
        resp, _ = self._call_with_reason_code_detail()
        assert resp.status_code == 201
