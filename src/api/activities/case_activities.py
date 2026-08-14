"""
Activity functions for the dispute case orchestrator.

Activities:
  assemble_case      — loads a case by caseId via case_store, sets
                       status=pending_review, falls back to a minimal stub for
                       demo/testing.
  submit_to_network  — stub: logs approval, persists "submitted" to case store,
                       and returns a fake acquirer ref.
  notify_supervisor  — stub: logs escalation / SLA-timeout alert.
                       (production: Teams / email / Event Grid)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import azure.durable_functions as df

bp = df.Blueprint()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@bp.activity_trigger(input_name="inputData")
def assemble_case(inputData: dict) -> dict:
    """
    Load a dispute case by caseId and set status to pending_review.

    Lookup order:
      1. data/synthetic/output/<caseId>.json  (Hockney's generator output)
      2. Minimal stub case (for demo / unit testing)
    """
    case_id: str = inputData["caseId"]
    logging.info("[assemble_case] loading caseId=%s", case_id)

    try:
        from services.case_store import get_case, update_case_status

        case = get_case(case_id)
        if case is not None:
            update_case_status(case_id, "pending_review")
            case = dict(case)
            case["status"] = "pending_review"
            case["orchestrationId"] = case_id
            case["updatedAt"] = _now_iso()
            logging.info("[assemble_case] loaded from case store — caseId=%s", case_id)
            return case
    except Exception as exc:  # noqa: BLE001
        logging.warning("[assemble_case] case-store load failed — caseId=%s exc=%s", case_id, exc)

    # Synthetic file not found — return a stub so the orchestrator can still run
    logging.warning(
        "[assemble_case] case not found for caseId=%s — using stub", case_id
    )
    now = _now_iso()
    return {
        "caseId": case_id,
        "orchestrationId": case_id,
        "status": "pending_review",
        "reasonCode": "STUB-001",
        "reasonCodeLabel": "Stub — synthetic data not found",
        "cardNetwork": "visa",
        "merchantName": "Demo Merchant",
        "transactionAmount": 0.0,
        "deadline": {
            "network": "visa",
            "dueDate": "2026-07-20",
            "daysRemaining": 14,
        },
        "createdAt": now,
        "updatedAt": now,
    }


@bp.activity_trigger(input_name="inputData")
def submit_to_network(inputData: dict) -> str:
    """
    Stub: simulate submitting an approved dispute to the card network.

    Input : { "caseId": str, "analystId": str, "comment": str }
    Output: fake acquirer reference number (str)
    """
    case_id: str = inputData["caseId"]
    analyst_id: str = inputData.get("analystId", "unknown")
    acquirer_ref = f"ACQ-{case_id[:8].upper()}-{uuid.uuid4().hex[:6].upper()}"

    logging.info(
        "[submit_to_network] case approved — caseId=%s analystId=%s acquirerRef=%s",
        case_id, analyst_id, acquirer_ref,
    )

    # Persist the terminal "submitted" status to the case store.
    try:
        from services.case_store import update_case_status
        update_case_status(case_id, "submitted")
    except Exception as exc:  # noqa: BLE001
        logging.warning(
            "[submit_to_network] status persistence failed — caseId=%s exc=%s", case_id, exc
        )

    return acquirer_ref


@bp.activity_trigger(input_name="inputData")
def notify_supervisor(inputData: dict) -> dict:
    """
    Stub: alert a supervisor on escalation or SLA timeout.

    Input : { "caseId": str, "reason": "analyst_escalated"|"sla_timeout",
               "analystId"?: str, "comment"?: str }
    Output: { "notified": True, "caseId": str, "reason": str }

    Production implementation would send a Teams adaptive card or
    trigger an Event Grid topic.
    """
    case_id: str = inputData["caseId"]
    reason: str = inputData.get("reason", "unknown")
    analyst_id: str = inputData.get("analystId", "")
    comment: str = inputData.get("comment", "")

    logging.warning(
        "[notify_supervisor] ALERT — caseId=%s reason=%s analystId=%s comment=%s",
        case_id, reason, analyst_id, comment,
    )
    return {"notified": True, "caseId": case_id, "reason": reason}
