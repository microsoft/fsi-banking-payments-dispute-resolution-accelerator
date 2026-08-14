"""
test_blueprint_types.py

Guard tests: assert that the three durable-function modules expose blueprints
built from azure.durable_functions.Blueprint (df.Blueprint) and that the
decorator kwargs match the actual df.Blueprint API.

These tests would have caught:
  • Bug 1: using func.Blueprint() instead of df.Blueprint() — the durable
    decorator methods (orchestration_trigger, activity_trigger,
    durable_client_input) do not exist on azure.functions.Blueprint.
  • Bug 2: using wrong keyword argument names for the df.Blueprint decorators
    (context_parameter vs context_name, client_parameter vs client_name) — the
    module raises TypeError at import time, which would fail at Functions host
    startup before any request is served.

Expected decorator signatures (df.Blueprint):
  orchestration_trigger(context_name: str, ...)
  activity_trigger(input_name: str, ...)
  durable_client_input(client_name: str, ...)
"""
from __future__ import annotations

import importlib

import pytest
import azure.durable_functions as df


# ── 1. Blueprint class identity ────────────────────────────────────────────────
# These tests verify the bp objects are df.Blueprint instances.
# If a module is broken (wrong kwarg), the import raises TypeError and the
# test fails with a clear error showing exactly which module and kwarg is wrong.

class TestBlueprintTypes:
    def test_dispute_orchestrator_bp_is_df_blueprint(self):
        """
        dispute_orchestrator.py must use df.Blueprint().
        Wrong kwargs: @bp.orchestration_trigger(context_parameter=...) should be
        @bp.orchestration_trigger(context_name=...).
        """
        from orchestrator.dispute_orchestrator import bp as orch_bp
        assert isinstance(orch_bp, df.Blueprint), (
            f"dispute_orchestrator.bp must be df.Blueprint, got {type(orch_bp)!r}"
        )

    def test_case_activities_bp_is_df_blueprint(self):
        """case_activities.py must use df.Blueprint()."""
        from activities.case_activities import bp as act_bp
        assert isinstance(act_bp, df.Blueprint), (
            f"case_activities.bp must be df.Blueprint, got {type(act_bp)!r}"
        )

    def test_case_actions_bp_is_func_blueprint(self):
        """
        case_actions.py uses func.Blueprint() (not df.Blueprint) because the
        @bp.durable_client_input binding was removed (issue #56 — it caused
        a host-level crash on Flex Consumption).  Plain HTTP triggers do not
        need df.Blueprint.
        """
        import azure.functions as func
        from triggers.case_actions import bp as actions_bp
        assert isinstance(actions_bp, func.Blueprint), (
            f"case_actions.bp must be func.Blueprint, got {type(actions_bp)!r}"
        )


# ── 2. Decorator kwarg validation ─────────────────────────────────────────────
# These tests probe the decorator signatures directly so a regression to the
# wrong kwarg name is caught before any module import is attempted.

class TestDecoratorSignatures:
    def test_orchestration_trigger_uses_context_name(self):
        """df.Blueprint.orchestration_trigger first param must be 'context_name'."""
        import inspect
        bp = df.Blueprint()
        sig = inspect.signature(bp.orchestration_trigger)
        params = list(sig.parameters.keys())
        assert "context_name" in params, (
            f"orchestration_trigger must accept 'context_name', got params={params}. "
            "Production code must use @bp.orchestration_trigger(context_name=...)"
        )
        assert "context_parameter" not in params, (
            "'context_parameter' is NOT a valid kwarg for orchestration_trigger. "
            "Use 'context_name' instead."
        )

    def test_activity_trigger_uses_input_name(self):
        """df.Blueprint.activity_trigger first param must be 'input_name'."""
        import inspect
        bp = df.Blueprint()
        sig = inspect.signature(bp.activity_trigger)
        params = list(sig.parameters.keys())
        assert "input_name" in params, (
            f"activity_trigger must accept 'input_name', got params={params}"
        )

    def test_durable_client_input_uses_client_name(self):
        """df.Blueprint.durable_client_input first param must be 'client_name'."""
        import inspect
        bp = df.Blueprint()
        sig = inspect.signature(bp.durable_client_input)
        params = list(sig.parameters.keys())
        assert "client_name" in params, (
            f"durable_client_input must accept 'client_name', got params={params}. "
            "Production code must use @bp.durable_client_input(client_name=...)"
        )
        assert "client_parameter" not in params, (
            "'client_parameter' is NOT a valid kwarg for durable_client_input. "
            "Use 'client_name' instead."
        )


# ── 3. Module-level import smoke tests ────────────────────────────────────────
# These confirm the modules load cleanly end-to-end as the Functions host would.

class TestModuleImports:
    def test_dispute_orchestrator_importable(self):
        """Full import of dispute_orchestrator module must succeed."""
        mod = importlib.import_module("orchestrator.dispute_orchestrator")
        assert hasattr(mod, "dispute_orchestrator"), "Function 'dispute_orchestrator' must be defined"
        assert hasattr(mod, "bp"), "Blueprint 'bp' must be exported"

    def test_case_activities_importable(self):
        """Full import of case_activities module must succeed."""
        mod = importlib.import_module("activities.case_activities")
        assert hasattr(mod, "assemble_case")
        assert hasattr(mod, "submit_to_network")
        assert hasattr(mod, "notify_supervisor")

    def test_case_actions_importable(self):
        """Full import of case_actions module must succeed."""
        mod = importlib.import_module("triggers.case_actions")
        assert hasattr(mod, "_raise_analyst_decision")
        assert hasattr(mod, "_require_analyst_id")
        assert hasattr(mod, "_parse_body")
