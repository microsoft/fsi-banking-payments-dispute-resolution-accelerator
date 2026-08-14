"""
Completeness & Gaps Detection Service (Issue #18).

Compares the reason code's required evidence checklist against what has
actually been retrieved for a dispute, and produces the case-facing
``reasonCodeChecklist`` / ``evidenceGaps`` artifacts (matching the Case model
contract — see models/case.py and src/shared/schemas/case.schema.json) so the
analyst review UI's existing EvidenceGapsPanel / ReasonCodeChecklist
components can render them directly, whether the case came from the
synthetic fixtures or a live pipeline run.

Adds a configurable alert threshold: a case is flagged for early analyst
attention when more than N *required* checklist items are missing (default 2,
per the Issue #18 acceptance criteria example). Configurable via the
``EVIDENCE_GAP_ALERT_THRESHOLD`` environment variable.

Usage:
    from services.gaps_service import detect_gaps
"""

from __future__ import annotations

import logging
import os
from typing import Any

from services.reason_code_engine import (
    get_evidence_checklist,
    identify_evidence_gaps,
    parse_reason_code_string,
)

logger = logging.getLogger(__name__)

_DEFAULT_ALERT_THRESHOLD = 2


def _get_alert_threshold() -> int:
    """Read the configurable missing-required-items alert threshold."""
    raw = os.environ.get("EVIDENCE_GAP_ALERT_THRESHOLD", "").strip()
    if not raw:
        return _DEFAULT_ALERT_THRESHOLD
    try:
        value = int(raw)
        return value if value >= 0 else _DEFAULT_ALERT_THRESHOLD
    except ValueError:
        logger.warning(
            "[gaps_service] invalid EVIDENCE_GAP_ALERT_THRESHOLD=%r — using default %d",
            raw, _DEFAULT_ALERT_THRESHOLD,
        )
        return _DEFAULT_ALERT_THRESHOLD


def _extract_network_and_code(dispute: dict[str, Any]) -> tuple[str, str]:
    network = (dispute.get("networkCode") or dispute.get("cardNetwork") or "").strip().lower()
    reason_code_raw = str(dispute.get("reasonCode") or "")
    if not network or network == "unknown":
        return parse_reason_code_string(reason_code_raw)
    _, code = parse_reason_code_string(reason_code_raw)
    if code == reason_code_raw:
        code = reason_code_raw
    return network, code


def _gathered_ids_from_evidence(evidence: list[dict[str, Any]]) -> set[str]:
    return {
        str(e.get("checklistItemId") or e.get("evidenceId") or "")
        for e in evidence
        if e.get("checklistItemId") or e.get("evidenceId")
    }


def _missing_item_reason(item: dict[str, Any]) -> str:
    """Produce a human-readable reason for a missing checklist item."""
    priority = "required" if item.get("priority") == "required" else "recommended"
    return (
        f"No {item.get('type', 'evidence')} evidence retrieved for "
        f"'{item.get('label', item.get('id', 'this item'))}' ({priority})."
    )


def detect_gaps(
    dispute: dict[str, Any],
    gathered_evidence_ids: list[str] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    alert_threshold: int | None = None,
) -> dict[str, Any]:
    """
    Detect evidence gaps for a dispute and build the case-facing artifacts.

    :param dispute: Dispute document with ``networkCode``/``cardNetwork`` and
        ``reasonCode``.
    :param gathered_evidence_ids: Explicit list of gathered checklist item ids.
        Falls back to deriving them from ``evidence`` when omitted.
    :param evidence: Retrieved evidence items (e.g. ``evidenceItems`` from
        evidence retrieval) — used to derive gathered ids when
        ``gathered_evidence_ids`` is not supplied.
    :param alert_threshold: Override for the missing-required-items alert
        threshold. Defaults to ``EVIDENCE_GAP_ALERT_THRESHOLD`` env var (or 2).
    :returns: {
        "reasonCodeChecklist": [{"item", "required", "satisfied"}, ...],
        "evidenceGaps": [{"missingItem", "reason", "impact"}, ...],
        "missingRequiredCount": int,
        "alertThreshold": int,
        "alertTriggered": bool,
        "completionPct": float,
        "readyForRebuttal": bool,
        "network": str,
        "reasonCode": str,
    }
    """
    network, code = _extract_network_and_code(dispute)

    if gathered_evidence_ids is not None:
        gathered_ids = set(gathered_evidence_ids)
    elif evidence:
        gathered_ids = _gathered_ids_from_evidence(evidence)
    else:
        gathered_ids = set()

    checklist = get_evidence_checklist(network, code)
    threshold = alert_threshold if alert_threshold is not None else _get_alert_threshold()

    reason_code_checklist: list[dict[str, Any]] = []
    evidence_gaps: list[dict[str, Any]] = []
    missing_required_count = 0

    for item in checklist:
        satisfied = item["id"] in gathered_ids
        reason_code_checklist.append({
            "item": item["label"],
            "required": item["priority"] == "required",
            "satisfied": satisfied,
        })
        if not satisfied:
            is_required = item["priority"] == "required"
            if is_required:
                missing_required_count += 1
            evidence_gaps.append({
                "missingItem": item["label"],
                "reason": _missing_item_reason(item),
                "impact": "critical" if is_required else "medium",
            })

    gap_analysis = identify_evidence_gaps(network, code, list(gathered_ids))
    alert_triggered = missing_required_count > threshold

    if alert_triggered:
        logger.warning(
            "[gaps_service] ALERT — caseId=%s missingRequired=%d > threshold=%d",
            dispute.get("disputeId") or dispute.get("caseId"),
            missing_required_count, threshold,
        )

    return {
        "reasonCodeChecklist": reason_code_checklist,
        "evidenceGaps": evidence_gaps,
        "missingRequiredCount": missing_required_count,
        "alertThreshold": threshold,
        "alertTriggered": alert_triggered,
        "completionPct": gap_analysis["completionPct"],
        "readyForRebuttal": gap_analysis["readyForRebuttal"],
        "network": network,
        "reasonCode": code,
    }
