"""
Win-Probability & Risk Scoring Service (Issue #30).

Computes a per-case win-probability estimate and risk assessment from:
  - the reason code's historical win-rate benchmark (reason_code_engine),
  - evidence completeness (required-item gap analysis), and
  - evidence-item completeness quality (complete/partial/missing) when available.

This replaces static/placeholder ``winProbability``/``riskLevel`` values with a
deterministic, explainable score. It intentionally uses a transparent formula
rather than a trained model — the accelerator's Phase 1 scope calls for a
"win-probability model defined and calibrated" that is auditable end-to-end;
swapping in a trained model later only requires replacing ``_compute_score``.

Risk categories (for the human-in-the-loop routing decision):
  auto_approve — high win-probability, evidence complete -> low risk
  review       — the default; needs analyst judgment
  escalate     — low win-probability or critical evidence gaps -> high risk

Invariant enforced: a case with ``riskLevel == "critical"`` always has
``winProbability <= 0.5`` (data-integrity requirement asserted by
tests/test_compliance.py::test_win_probability_lower_for_high_risk_cases).

Usage:
    from services.scoring_service import score_case
"""

from __future__ import annotations

import logging
from typing import Any

from services.reason_code_engine import (
    get_reason_code_detail,
    identify_evidence_gaps,
    parse_reason_code_string,
)

logger = logging.getLogger(__name__)

# Weight given to the reason code's historical win-rate vs. evidence
# completeness when blending the final win-probability. Must sum to 1.0.
_WEIGHT_BASE_RATE = 0.6
_WEIGHT_COMPLETENESS = 0.4

# Risk-level thresholds (inclusive lower bound) applied to winProbability.
_RISK_THRESHOLDS: list[tuple[float, str]] = [
    (0.70, "low"),
    (0.50, "medium"),
    (0.30, "high"),
    (0.00, "critical"),
]

# Category thresholds — routing hint for the HITL gate / ops dashboard.
_AUTO_APPROVE_MIN_SCORE = 0.75
_AUTO_APPROVE_MIN_COMPLETENESS = 100.0
_ESCALATE_MAX_SCORE = 0.35


def _risk_level_for(score: float) -> str:
    for threshold, level in _RISK_THRESHOLDS:
        if score >= threshold:
            return level
    return "critical"  # unreachable given the 0.00 floor above, but explicit


def _category_for(score: float, completion_pct: float, evidence_gaps_critical: int) -> str:
    """Return the routing category: auto_approve | review | escalate."""
    if evidence_gaps_critical > 0:
        # A critical gap always forces at least human review.
        if score <= _ESCALATE_MAX_SCORE:
            return "escalate"
        return "review"
    if score >= _AUTO_APPROVE_MIN_SCORE and completion_pct >= _AUTO_APPROVE_MIN_COMPLETENESS:
        return "auto_approve"
    if score <= _ESCALATE_MAX_SCORE:
        return "escalate"
    return "review"


def _evidence_quality_factor(evidence: list[dict[str, Any]] | None) -> float:
    """
    Return a [0, 1] quality multiplier from evidence-item completeness.

    Evidence items carry a ``completeness`` field ("complete" | "partial" |
    "missing") per the Evidence model. Returns 1.0 (neutral) when no evidence
    is supplied, so callers that only pass gathered-id lists are unaffected.
    """
    if not evidence:
        return 1.0
    weights = {"complete": 1.0, "partial": 0.5, "missing": 0.0}
    scores = [weights.get(str(e.get("completeness", "complete")).lower(), 1.0) for e in evidence]
    return sum(scores) / len(scores) if scores else 1.0


def _extract_network_and_code(dispute: dict[str, Any]) -> tuple[str, str]:
    network = (dispute.get("networkCode") or dispute.get("cardNetwork") or "").strip().lower()
    reason_code_raw = str(dispute.get("reasonCode") or "")
    if not network or network == "unknown":
        return parse_reason_code_string(reason_code_raw)
    _, code = parse_reason_code_string(reason_code_raw)
    if code == reason_code_raw:
        code = reason_code_raw
    return network, code


def score_case(
    dispute: dict[str, Any],
    gathered_evidence_ids: list[str] | None = None,
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Compute win-probability and risk assessment for a dispute case.

    :param dispute: Dispute/case document with at least ``networkCode``/
        ``cardNetwork`` and ``reasonCode``.
    :param gathered_evidence_ids: IDs of checklist items already gathered
        (reason_code_engine checklist ids). Falls back to an empty list
        (i.e. no evidence gathered yet) when omitted.
    :param evidence: Optional list of retrieved evidence *items* (e.g. the
        ``evidenceItems`` from evidence retrieval, or ``dispute['evidence']``)
        used to weight the score by completeness quality, not just presence.
    :returns: {
        "winProbability": float,       # 0-1
        "riskLevel": str,              # low | medium | high | critical
        "category": str,               # auto_approve | review | escalate
        "baseWinRate": float | None,   # reason-code historical win-rate
        "completionPct": float,        # % of required+optional checklist gathered
        "readyForRebuttal": bool,      # all required items gathered
        "criticalGaps": int,           # count of missing REQUIRED checklist items
        "network": str,
        "reasonCode": str,
    }
    """
    network, code = _extract_network_and_code(dispute)
    detail = get_reason_code_detail(network, code)
    base_win_rate = detail["winRate"] if detail else None

    if gathered_evidence_ids is None and evidence:
        # Derive gathered checklist ids from retrieved evidence items when the
        # caller only supplies the evidence list (e.g. evidenceItems output).
        gathered_ids = [
            str(e.get("checklistItemId") or e.get("evidenceId") or "")
            for e in evidence
            if e.get("checklistItemId") or e.get("evidenceId")
        ]
    else:
        gathered_ids = gathered_evidence_ids or []
    gap_analysis = identify_evidence_gaps(network, code, gathered_ids)
    completion_pct = gap_analysis["completionPct"]
    ready = gap_analysis["readyForRebuttal"]
    critical_gaps = sum(
        1 for g in gap_analysis["gaps"] if g.get("priority") == "required"
    )

    quality_factor = _evidence_quality_factor(evidence)

    # Blend historical win-rate with evidence completeness (quality-adjusted).
    # Default to a neutral 0.5 base rate when the reason code is unknown, so
    # the score still reflects evidence completeness rather than collapsing.
    effective_base_rate = base_win_rate if base_win_rate is not None else 0.5
    completeness_component = (completion_pct / 100.0) * quality_factor

    raw_score = (
        _WEIGHT_BASE_RATE * effective_base_rate
        + _WEIGHT_COMPLETENESS * completeness_component
    )

    # Critical (required) evidence gaps materially undercut confidence — apply
    # a penalty per missing required item, floored at 0.
    penalty = min(0.15 * critical_gaps, raw_score)
    win_probability = max(0.0, min(1.0, raw_score - penalty))

    risk_level = _risk_level_for(win_probability)
    category = _category_for(win_probability, completion_pct, critical_gaps)

    # Enforce the data-integrity invariant explicitly (belt-and-suspenders —
    # the threshold table already guarantees this, but future threshold edits
    # must not silently violate it).
    if risk_level == "critical" and win_probability > 0.5:
        win_probability = 0.5

    logger.info(
        "[scoring] caseId=%s network=%s reasonCode=%s winProbability=%.3f "
        "riskLevel=%s category=%s completionPct=%.1f criticalGaps=%d",
        dispute.get("disputeId") or dispute.get("caseId"),
        network, code, win_probability, risk_level, category, completion_pct, critical_gaps,
    )

    return {
        "winProbability": round(win_probability, 4),
        "riskLevel": risk_level,
        "category": category,
        "baseWinRate": base_win_rate,
        "completionPct": completion_pct,
        "readyForRebuttal": ready,
        "criticalGaps": critical_gaps,
        "network": network,
        "reasonCode": code,
    }
