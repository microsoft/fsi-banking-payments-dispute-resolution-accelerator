"""
Pipeline: Master Refresh (pl_master_refresh)

Periodic pipeline that maintains data freshness and consistency:
  1. Deadline enforcement — flags disputes approaching/past SLA deadlines
  2. Status reconciliation — syncs dispute status with network responses
  3. Metrics refresh — updates aggregate counters for dashboards
  4. Stale record detection — identifies stuck disputes needing attention

Runs every 15 minutes on a timer trigger. Also exposes an HTTP endpoint
for on-demand refresh (e.g., after bulk imports or system recovery).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta

import azure.functions as func

import cosmos_client
from cosmos_models import DisputeStatus, new_timeline_event

bp = func.Blueprint()

logger = logging.getLogger(__name__)

# Disputes approaching deadline within this window get flagged
DEADLINE_WARNING_HOURS = 48

# Disputes stuck in a non-terminal status longer than this get flagged
STALE_THRESHOLD_HOURS = 72

# Terminal statuses — disputes in these states don't need refresh
TERMINAL_STATUSES = {
    DisputeStatus.CLOSED.value,
    DisputeStatus.SUBMITTED.value,
    DisputeStatus.REJECTED.value,
}


def _check_deadlines() -> dict:
    """Flag disputes approaching or past their SLA deadlines."""
    now = datetime.now(timezone.utc)
    warning_cutoff = (now + timedelta(hours=DEADLINE_WARNING_HOURS)).isoformat()

    # Query disputes approaching deadline that aren't in terminal state
    query = """
        SELECT c.id, c.disputeId, c.networkCode, c.status, c.deadlineUtc,
               c.cardholderName, c.merchantName, c.transactionAmount
        FROM c
        WHERE c.deadlineUtc <= @warningCutoff
          AND c.status NOT IN ('closed', 'submitted', 'rejected')
    """
    params = [{"name": "@warningCutoff", "value": warning_cutoff}]

    at_risk = cosmos_client.query_disputes(query, params, max_items=200)

    expired = []
    approaching = []

    for dispute in at_risk:
        deadline_str = dispute.get("deadlineUtc", "")
        try:
            deadline = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue

        if deadline <= now:
            expired.append(dispute)
            # Update status to escalated if not already
            if dispute.get("status") not in (DisputeStatus.ESCALATED.value, *TERMINAL_STATUSES):
                _escalate_expired_dispute(dispute)
        else:
            approaching.append(dispute)

    logger.info("Deadline check — expired=%d approaching=%d", len(expired), len(approaching))
    return {"expired": len(expired), "approaching": len(approaching)}


def _escalate_expired_dispute(dispute: dict) -> None:
    """Escalate a dispute that has passed its SLA deadline."""
    dispute_id = dispute["disputeId"]
    network_code = dispute["networkCode"]

    # Fetch full document for update
    full_dispute = cosmos_client.get_dispute(dispute_id, network_code)
    if not full_dispute:
        logger.warning("Cannot escalate %s — not found", dispute_id)
        return

    full_dispute["status"] = DisputeStatus.ESCALATED.value
    now_iso = datetime.now(timezone.utc).isoformat()
    full_dispute["updatedAt"] = now_iso

    cosmos_client.update_dispute(full_dispute)

    # Record timeline event
    event = new_timeline_event(
        dispute_id=dispute_id,
        event_type="status_change",
        actor="pipeline/master_refresh",
        detail=f"Auto-escalated — SLA deadline passed ({dispute.get('deadlineUtc', 'unknown')})",
        data={"previousStatus": dispute.get("status"), "reason": "deadline_expired"},
    )
    cosmos_client.create_timeline_event(event)

    logger.info("Escalated dispute %s — deadline passed", dispute_id)


def _check_stale_disputes() -> dict:
    """Identify disputes stuck in non-terminal states beyond threshold."""
    stale_cutoff = (
        datetime.now(timezone.utc) - timedelta(hours=STALE_THRESHOLD_HOURS)
    ).isoformat()

    query = """
        SELECT c.id, c.disputeId, c.networkCode, c.status, c.updatedAt
        FROM c
        WHERE c.updatedAt <= @staleCutoff
          AND c.status NOT IN ('closed', 'submitted', 'rejected', 'escalated')
    """
    params = [{"name": "@staleCutoff", "value": stale_cutoff}]

    stale = cosmos_client.query_disputes(query, params, max_items=200)

    for dispute in stale:
        # Record a warning event (don't change status — let analysts handle it)
        event = new_timeline_event(
            dispute_id=dispute["disputeId"],
            event_type="system_alert",
            actor="pipeline/master_refresh",
            detail=f"Dispute stale — no update for {STALE_THRESHOLD_HOURS}h (status={dispute.get('status')})",
            data={"lastUpdated": dispute.get("updatedAt")},
        )
        cosmos_client.create_timeline_event(event)

    logger.info("Stale check — %d disputes flagged", len(stale))
    return {"stale_flagged": len(stale)}


def _compute_metrics() -> dict:
    """Compute aggregate metrics for dashboard refresh."""
    # Count disputes by status
    query = """
        SELECT c.status, COUNT(1) as count
        FROM c
        GROUP BY c.status
    """
    status_counts = cosmos_client.query_disputes(query, max_items=20)

    # Count disputes by network
    query_network = """
        SELECT c.networkCode, COUNT(1) as count
        FROM c
        GROUP BY c.networkCode
    """
    network_counts = cosmos_client.query_disputes(query_network, max_items=10)

    metrics = {
        "byStatus": {r["status"]: r["count"] for r in status_counts},
        "byNetwork": {r["networkCode"]: r["count"] for r in network_counts},
        "refreshedAt": datetime.now(timezone.utc).isoformat(),
    }

    logger.info("Metrics computed — statuses=%d networks=%d",
                len(metrics["byStatus"]), len(metrics["byNetwork"]))
    return metrics


def _run_refresh() -> dict:
    """Execute the full master refresh pipeline."""
    results = {
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "deadlines": {},
        "stale": {},
        "metrics": {},
    }

    # Step 1: Check deadlines and auto-escalate
    results["deadlines"] = _check_deadlines()

    # Step 2: Flag stale disputes
    results["stale"] = _check_stale_disputes()

    # Step 3: Compute dashboard metrics
    results["metrics"] = _compute_metrics()

    results["completedAt"] = datetime.now(timezone.utc).isoformat()
    logger.info("Master refresh complete — %s", json.dumps(results, default=str))
    return results


@bp.function_name("pl_master_refresh_timer")
@bp.timer_trigger(schedule="0 */15 * * * *", arg_name="timer", run_on_startup=False)
def master_refresh_timer(timer: func.TimerRequest) -> None:
    """
    Timer trigger (every 15 min): Run the full master refresh pipeline.

    Checks deadlines, flags stale disputes, and refreshes dashboard metrics.
    """
    if timer.past_due:
        logger.warning("pl_master_refresh timer is past due")

    logger.info("pl_master_refresh timer triggered")
    _run_refresh()


@bp.function_name("pl_master_refresh_http")
@bp.route(route="pipelines/refresh", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def master_refresh_http(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP trigger: On-demand master refresh.

    Runs the full refresh pipeline and returns the results.
    Useful after bulk imports, system recovery, or manual testing.
    """
    logger.info("pl_master_refresh HTTP triggered")
    results = _run_refresh()

    return func.HttpResponse(
        json.dumps(results, default=str),
        status_code=200,
        mimetype="application/json",
    )
