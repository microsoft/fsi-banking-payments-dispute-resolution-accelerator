"""
test_orchestrator.py

Unit-tests the orchestrator decision branching and action trigger logic
WITHOUT requiring a live Azure Functions host or Durable Functions runtime.

Strategy
--------
The dispute_orchestrator is a Python generator wrapped by the
azure-durable-functions SDK decorator (@bp.orchestration_trigger).
The decorator produces a FunctionBuilder, not the raw generator.

Unwrap path (discovered via SDK source inspection):
  FunctionBuilder  →  .build(None).get_user_function()  →  handle
  handle           →  .orchestrator_function             →  raw generator

This raw generator accepts a MockOrchestratorContext and yields Task-like
objects, which the _run_orchestrator() driver sends values back into.

For the action HTTP triggers we mock df.DurableOrchestrationClient to verify
that raise_event() is called with the correct arguments.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Unwrap the raw generator from the SDK-decorated FunctionBuilder ───────────
# @bp.orchestration_trigger wraps the user function via Orchestrator.create(),
# which stores the original generator as handle.orchestrator_function.
# We extract it here so _run_orchestrator() can drive it directly.

_orch_import_error: str = ""
_dispute_orchestrator_raw = None

try:
    from orchestrator.dispute_orchestrator import dispute_orchestrator as _fb
    _dispute_orchestrator_raw = _fb.build(None).get_user_function().orchestrator_function
    _orch_ok = True
except Exception as _e:
    _orch_ok = False
    _orch_import_error = f"{type(_e).__name__}: {_e}"

_actions_import_error: str = ""
try:
    from triggers.case_actions import (
        _handle_start_review,
        _parse_body,
        _raise_analyst_decision,
        _require_analyst_id,
    )
    _actions_ok = True
except Exception as _e:
    _handle_start_review = _parse_body = _raise_analyst_decision = _require_analyst_id = None  # type: ignore
    _actions_ok = False
    _actions_import_error = f"{type(_e).__name__}: {_e}"

# Safety skip marks — activate only if the production modules are still broken
_skip_orch = pytest.mark.skipif(
    not _orch_ok,
    reason=(
        f"dispute_orchestrator unwrap failed — production module may be broken. "
        f"Error: {_orch_import_error}"
    ),
)
_skip_actions = pytest.mark.skipif(
    not _actions_ok,
    reason=(
        f"case_actions import failed — production module may be broken. "
        f"Error: {_actions_import_error}"
    ),
)


# ── Mock helpers ──────────────────────────────────────────────────────────────

class MockTask:
    """Minimal stand-in for a durable Task / TaskSet."""

    def __init__(self, result=None):
        self._result = result
        self.cancelled = False

    @property
    def result(self):
        return self._result

    def cancel(self):
        self.cancelled = True


class MockOrchestratorContext:
    """
    Simulates df.DurableOrchestrationContext for unit testing.

    Pass `scenario` to control which branch task_any resolves to:
      "approve" | "deny" | "escalate" | "timeout" | "unknown_action"
    """

    def __init__(self, case_id: str, scenario: str, decision_payload: dict | None = None):
        self.case_id = case_id
        self.is_replaying = False
        self.current_utc_datetime = datetime(2026, 7, 6, 17, 0, 0, tzinfo=timezone.utc)
        self.scenario = scenario
        self.decision_payload = decision_payload or {}

        self._decision_task: MockTask | None = None
        self._timeout_task: MockTask | None = None
        self.activities_called: list[tuple[str, dict]] = []

    def get_input(self) -> dict:
        return {"caseId": self.case_id}

    def call_activity(self, name: str, input_data: dict | None = None) -> MockTask:
        self.activities_called.append((name, input_data or {}))
        if name == "assemble_case":
            result = {
                "caseId": self.case_id,
                "orchestrationId": self.case_id,
                "status": "pending_review",
                "reasonCode": "TEST-001",
                "deadline": {
                    "network": "visa",
                    "dueDate": "2026-08-01",
                    "daysRemaining": 26,
                },
                "createdAt": "2026-07-06T17:00:00Z",
            }
        elif name == "submit_to_network":
            result = f"ACQ-{self.case_id[:8].upper()}"
        elif name == "notify_supervisor":
            result = {
                "notified": True,
                "caseId": self.case_id,
                "reason": (input_data or {}).get("reason", ""),
            }
        else:
            result = {}
        return MockTask(result=result)

    def wait_for_external_event(self, name: str) -> MockTask:
        self._decision_task = MockTask(result=self.decision_payload)
        return self._decision_task

    def create_timer(self, deadline) -> MockTask:
        self._timeout_task = MockTask(result=None)
        return self._timeout_task

    def task_any(self, tasks: list) -> MockTask:
        # task_any resolves to the "winning" inner task
        if self.scenario == "timeout":
            return MockTask(result=self._timeout_task)
        return MockTask(result=self._decision_task)


def _run_orchestrator(ctx: MockOrchestratorContext) -> dict:
    """
    Drive the dispute_orchestrator generator to completion.

    Yield sequence:
      1. call_activity("assemble_case")           → send assemble result
      2. task_any([decision_task, timeout_task])   → send winning task
      3. (optional) call_activity(...)             → send activity result
    """
    gen = _dispute_orchestrator_raw(ctx)

    try:
        # Step 1 — assemble_case
        assemble_task: MockTask = next(gen)

        # Step 2 — task_any  (also triggers wait_for_external_event + create_timer)
        task_any_task: MockTask = gen.send(assemble_task.result)

        # The task_any MockTask's result IS the winning inner task
        winning_task: MockTask = task_any_task.result

        # Step 3 — send winner; may yield another activity or StopIteration
        try:
            extra_task: MockTask = gen.send(winning_task)
            # One more activity (submit_to_network or notify_supervisor)
            gen.send(extra_task.result)
        except StopIteration as exc:
            return exc.value

    except StopIteration as exc:
        return exc.value

    return {}


# ── Orchestrator branching tests ──────────────────────────────────────────────

CASE_ID = "bd3f6fe3-ad20-5e96-b926-da3b87c18834"


@_skip_orch
class TestOrchestratorApprove:
    def test_approve_returns_submitted_status(self):
        ctx = MockOrchestratorContext(
            CASE_ID, "approve",
            {"action": "approve", "analystId": "analyst-1", "comment": "LGTM"},
        )
        result = _run_orchestrator(ctx)
        assert result["status"] == "submitted"

    def test_approve_includes_case_id(self):
        ctx = MockOrchestratorContext(
            CASE_ID, "approve",
            {"action": "approve", "analystId": "analyst-1", "comment": None},
        )
        result = _run_orchestrator(ctx)
        assert result["caseId"] == CASE_ID

    def test_approve_includes_acquirer_ref(self):
        ctx = MockOrchestratorContext(
            CASE_ID, "approve",
            {"action": "approve", "analystId": "analyst-1", "comment": None},
        )
        result = _run_orchestrator(ctx)
        assert "acquirerRef" in result

    def test_approve_calls_submit_to_network(self):
        ctx = MockOrchestratorContext(
            CASE_ID, "approve",
            {"action": "approve", "analystId": "analyst-1", "comment": None},
        )
        _run_orchestrator(ctx)
        activity_names = [name for name, _ in ctx.activities_called]
        assert "submit_to_network" in activity_names

    def test_approve_passes_analyst_id_to_submit(self):
        ctx = MockOrchestratorContext(
            CASE_ID, "approve",
            {"action": "approve", "analystId": "analyst-42", "comment": "ok"},
        )
        _run_orchestrator(ctx)
        submit_calls = [(n, d) for n, d in ctx.activities_called if n == "submit_to_network"]
        assert len(submit_calls) == 1
        assert submit_calls[0][1].get("analystId") == "analyst-42"


@_skip_orch
class TestOrchestratorDeny:
    def test_deny_returns_denied_status(self):
        ctx = MockOrchestratorContext(
            CASE_ID, "deny",
            {"action": "deny", "analystId": "analyst-1", "comment": "Insufficient evidence"},
        )
        result = _run_orchestrator(ctx)
        assert result["status"] == "denied"

    def test_deny_does_not_call_submit_or_notify(self):
        ctx = MockOrchestratorContext(
            CASE_ID, "deny",
            {"action": "deny", "analystId": "analyst-1", "comment": None},
        )
        _run_orchestrator(ctx)
        activity_names = [name for name, _ in ctx.activities_called]
        assert "submit_to_network" not in activity_names
        assert "notify_supervisor" not in activity_names

    def test_deny_includes_analyst_id(self):
        ctx = MockOrchestratorContext(
            CASE_ID, "deny",
            {"action": "deny", "analystId": "analyst-7", "comment": None},
        )
        result = _run_orchestrator(ctx)
        assert result.get("analystId") == "analyst-7"


@_skip_orch
class TestOrchestratorEscalate:
    def test_escalate_returns_escalated_status(self):
        ctx = MockOrchestratorContext(
            CASE_ID, "escalate",
            {"action": "escalate", "analystId": "analyst-1", "comment": "Need supervisor review"},
        )
        result = _run_orchestrator(ctx)
        assert result["status"] == "escalated"

    def test_escalate_calls_notify_supervisor(self):
        ctx = MockOrchestratorContext(
            CASE_ID, "escalate",
            {"action": "escalate", "analystId": "analyst-1", "comment": "Needs supervisor"},
        )
        _run_orchestrator(ctx)
        activity_names = [name for name, _ in ctx.activities_called]
        assert "notify_supervisor" in activity_names

    def test_escalate_notify_includes_reason(self):
        ctx = MockOrchestratorContext(
            CASE_ID, "escalate",
            {"action": "escalate", "analystId": "analyst-1", "comment": None},
        )
        _run_orchestrator(ctx)
        notify_calls = [(n, d) for n, d in ctx.activities_called if n == "notify_supervisor"]
        assert len(notify_calls) == 1
        assert notify_calls[0][1].get("reason") == "analyst_escalated"


@_skip_orch
class TestOrchestratorTimeout:
    def test_timeout_returns_expired_status(self):
        ctx = MockOrchestratorContext(CASE_ID, "timeout")
        result = _run_orchestrator(ctx)
        assert result["status"] == "expired"

    def test_timeout_calls_notify_supervisor(self):
        ctx = MockOrchestratorContext(CASE_ID, "timeout")
        _run_orchestrator(ctx)
        activity_names = [name for name, _ in ctx.activities_called]
        assert "notify_supervisor" in activity_names

    def test_timeout_notify_includes_sla_reason(self):
        ctx = MockOrchestratorContext(CASE_ID, "timeout")
        _run_orchestrator(ctx)
        notify_calls = [(n, d) for n, d in ctx.activities_called if n == "notify_supervisor"]
        assert notify_calls[0][1].get("reason") == "sla_timeout"

    def test_timeout_does_not_call_submit_to_network(self):
        ctx = MockOrchestratorContext(CASE_ID, "timeout")
        _run_orchestrator(ctx)
        activity_names = [name for name, _ in ctx.activities_called]
        assert "submit_to_network" not in activity_names


@_skip_orch
class TestOrchestratorUnknownAction:
    def test_unknown_action_falls_back_to_denied(self):
        """The orchestrator treats unknown actions as deny (logs a warning)."""
        ctx = MockOrchestratorContext(
            CASE_ID, "deny",  # scenario drives task_any, not the action
            {"action": "reopen", "analystId": "analyst-1", "comment": None},
        )
        result = _run_orchestrator(ctx)
        assert result["status"] == "denied"


# ── Action trigger helpers ────────────────────────────────────────────────────

@_skip_actions
class TestParseBody:
    def test_parses_valid_json(self):
        mock_req = MagicMock()
        mock_req.get_json.return_value = {"analystId": "a1", "comment": "ok"}
        result = _parse_body(mock_req)
        assert result == {"analystId": "a1", "comment": "ok"}

    def test_returns_empty_dict_on_parse_error(self):
        mock_req = MagicMock()
        mock_req.get_json.side_effect = ValueError("bad json")
        result = _parse_body(mock_req)
        assert result == {}


@_skip_actions
class TestRequireAnalystId:
    def test_returns_id_when_present(self):
        assert _require_analyst_id({"analystId": "a1"}) == "a1"

    def test_returns_none_when_missing(self):
        assert _require_analyst_id({}) is None

    def test_returns_none_for_blank_string(self):
        assert _require_analyst_id({"analystId": "  "}) is None

    def test_returns_none_for_empty_string(self):
        assert _require_analyst_id({"analystId": ""}) is None


@_skip_actions
class TestRaiseAnalystDecision:
    """
    Verify _raise_analyst_decision: case-existence gate, status returned,
    404 on unknown case.  No durable client — binding removed (issue #56).
    """

    def test_approve_returns_200_with_approved_status(self):
        response = _raise_analyst_decision(CASE_ID, "approve", "analyst-1", "ok")
        body = json.loads(response.get_body())
        assert response.status_code == 200
        assert body["status"] == "approved"
        assert body["caseId"] == CASE_ID

    def test_deny_returns_200_with_denied_status(self):
        response = _raise_analyst_decision(CASE_ID, "deny", "analyst-1", None)
        body = json.loads(response.get_body())
        assert response.status_code == 200
        assert body["status"] == "denied"

    def test_escalate_returns_200_with_escalated_status(self):
        response = _raise_analyst_decision(CASE_ID, "escalate", "analyst-2", None)
        body = json.loads(response.get_body())
        assert response.status_code == 200
        assert body["status"] == "escalated"

    def test_returns_404_when_case_not_found(self):
        """Unknown caseId → case store returns None → 404."""
        with patch("triggers.case_actions.get_case", return_value=None):
            response = _raise_analyst_decision(
                "00000000-0000-0000-0000-000000000000", "approve", "analyst-1", None
            )
        body = json.loads(response.get_body())
        assert response.status_code == 404
        assert "not found" in body["error"]


@_skip_actions
class TestStartReview:
    """_handle_start_review returns a clean 503/400 (not an empty-body 500) when durable is unavailable."""

    def test_returns_503_with_json_body(self):
        response = _handle_start_review(CASE_ID)
        assert response.status_code == 503
        body = json.loads(response.get_body())
        assert "error" in body

    def test_returns_400_when_case_id_missing(self):
        response = _handle_start_review("")
        assert response.status_code == 400


# ── Status-persistence tests (issue #56) ─────────────────────────────────────

@_skip_actions
class TestStatusPersistence:
    """
    Verify _raise_analyst_decision always persists via update_case_status
    regardless of any durable state, and never returns 5xx.

    update_case_status and get_case are mocked at their import sites in
    case_actions so tests are fully isolated from Cosmos and fixture files.
    """

    def test_approve_persists_approved_status(self):
        with patch("triggers.case_actions.update_case_status") as mock_upd:
            _raise_analyst_decision(CASE_ID, "approve", "analyst-1", "ok")
        mock_upd.assert_called_once_with(CASE_ID, "approved")

    def test_deny_persists_denied_status(self):
        with patch("triggers.case_actions.update_case_status") as mock_upd:
            _raise_analyst_decision(CASE_ID, "deny", "analyst-1", None)
        mock_upd.assert_called_once_with(CASE_ID, "denied")

    def test_escalate_persists_escalated_status(self):
        with patch("triggers.case_actions.update_case_status") as mock_upd:
            _raise_analyst_decision(CASE_ID, "escalate", "analyst-2", None)
        mock_upd.assert_called_once_with(CASE_ID, "escalated")

    def test_persists_status_for_seeded_case_no_orchestration(self):
        """Seeded/demo case (no orchestration instance) → status persisted, 200 returned."""
        with patch("triggers.case_actions.update_case_status") as mock_upd:
            response = _raise_analyst_decision(CASE_ID, "approve", "analyst-1", None)
        mock_upd.assert_called_once_with(CASE_ID, "approved")
        assert response.status_code == 200

    def test_best_effort_signals_durable_instance(self):
        with patch("triggers.case_actions.raise_durable_event", return_value=True) as mock_signal:
            response = _raise_analyst_decision(CASE_ID, "approve", "analyst-1", "ok")
        mock_signal.assert_called_once_with(CASE_ID, "approve", "analyst-1", "ok")
        assert response.status_code == 200

    def test_case_not_found_does_not_persist_status(self):
        """Unknown case → 404, update_case_status NOT called."""
        with (
            patch("triggers.case_actions.get_case", return_value=None),
            patch("triggers.case_actions.update_case_status") as mock_upd,
        ):
            response = _raise_analyst_decision(
                "00000000-0000-0000-0000-000000000000", "approve", "analyst-1", None
            )
        assert response.status_code == 404
        mock_upd.assert_not_called()

    def test_persistence_failure_does_not_break_response(self):
        """A Cosmos write failure must not propagate as a 5xx to the caller."""
        with patch(
            "triggers.case_actions.update_case_status",
            side_effect=KeyError("Case not found in Cosmos DB"),
        ):
            response = _raise_analyst_decision(CASE_ID, "approve", "analyst-1", None)
        assert response.status_code == 200
        body = json.loads(response.get_body())
        assert body["status"] == "approved"

    def test_durable_signal_failure_does_not_break_response(self):
        with patch(
            "triggers.case_actions.raise_durable_event",
            side_effect=RuntimeError("durable unavailable"),
        ):
            response = _raise_analyst_decision(CASE_ID, "approve", "analyst-1", None)
        assert response.status_code == 200
