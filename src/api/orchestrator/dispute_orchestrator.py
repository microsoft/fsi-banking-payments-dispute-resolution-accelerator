"""
Durable Functions orchestrator for the dispute case HITL approval loop.

Shape (per Story #21 design brief):
    start
      → assemble_case (activity)   — loads case, sets status=pending_review
      → WaitForExternalEvent("analyst_decision", timeout=SLA_HOURS)
      → Branch:
            approve  → submit_to_network (activity) → status=submitted
            deny     → status=denied
            escalate → notify_supervisor (activity) → status=escalated
            timeout  → notify_supervisor (activity) → status=expired

Instance ID convention: orchestrationId == caseId (1:1, per ADR).
External event name   : "analyst_decision"
Event payload         : { "action": "approve"|"deny"|"escalate",
                          "analystId": str, "comment": str|None }
"""
from __future__ import annotations

import logging
from datetime import timedelta

import azure.durable_functions as df
import azure.functions as func

bp = df.Blueprint()

# SLA before the case expires and a supervisor is notified.
# Adjust via an app setting in production; hard-coded for demo.
SLA_HOURS: int = 72


@bp.orchestration_trigger(context_name="context")
def dispute_orchestrator(context: df.DurableOrchestrationContext):
    """
    Orchestrator: assemble → pending_review → wait for analyst → branch.

    Input : { "caseId": "<uuid>" }
    Output: { "status": "<final-status>", "caseId": "<uuid>", ... }
    """
    input_data: dict = context.get_input()
    case_id: str = input_data["caseId"]

    if not context.is_replaying:
        logging.info("[orchestrator] started — caseId=%s", case_id)

    # ── Step 1: assemble the case (loads from synthetic store / stub) ────────
    case: dict = yield context.call_activity("assemble_case", {"caseId": case_id})

    if not context.is_replaying:
        logging.info("[orchestrator] case assembled, status=pending_review — caseId=%s", case_id)

    # ── Step 2: await analyst decision with SLA timeout ──────────────────────
    sla_deadline = context.current_utc_datetime + timedelta(hours=SLA_HOURS)
    decision_task = context.wait_for_external_event("analyst_decision")
    timeout_task = context.create_timer(sla_deadline)

    winner = yield context.task_any([decision_task, timeout_task])

    # ── Branch: analyst responded before SLA ─────────────────────────────────
    if winner == decision_task:
        timeout_task.cancel()

        decision: dict = decision_task.result
        action: str = decision.get("action", "")
        analyst_id: str = decision.get("analystId", "")
        comment: str = decision.get("comment") or ""

        if not context.is_replaying:
            logging.info(
                "[orchestrator] analyst_decision received — action=%s analystId=%s caseId=%s",
                action, analyst_id, case_id,
            )

        if action == "approve":
            acquirer_ref: str = yield context.call_activity(
                "submit_to_network",
                {"caseId": case_id, "analystId": analyst_id, "comment": comment},
            )
            return {
                "status": "submitted",
                "caseId": case_id,
                "acquirerRef": acquirer_ref,
                "analystId": analyst_id,
            }

        if action == "deny":
            return {"status": "denied", "caseId": case_id, "analystId": analyst_id}

        if action == "escalate":
            yield context.call_activity(
                "notify_supervisor",
                {
                    "caseId": case_id,
                    "reason": "analyst_escalated",
                    "analystId": analyst_id,
                    "comment": comment,
                },
            )
            return {"status": "escalated", "caseId": case_id, "analystId": analyst_id}

        # Unknown action — treat as deny, log a warning
        logging.warning(
            "[orchestrator] unknown action '%s' for caseId=%s — treating as deny",
            action, case_id,
        )
        return {"status": "denied", "caseId": case_id, "analystId": analyst_id}

    # ── Branch: SLA timeout ──────────────────────────────────────────────────
    decision_task.cancel()
    if not context.is_replaying:
        logging.warning("[orchestrator] SLA timeout — notifying supervisor, caseId=%s", case_id)

    yield context.call_activity(
        "notify_supervisor",
        {"caseId": case_id, "reason": "sla_timeout"},
    )
    return {"status": "expired", "caseId": case_id}
