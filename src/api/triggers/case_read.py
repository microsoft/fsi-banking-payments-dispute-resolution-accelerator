"""
HTTP read triggers for the dispute case queue and detail views.

Routes:
  GET /api/cases                  — queue list (CaseSummary[])
  GET /api/cases?status=<value>   — filtered by status
  GET /api/cases/{caseId}         — full Case detail

Data is served from the case_store module (synthetic fixtures for demo;
swap case_store._load_* to point at blob storage / OneLake in production).
"""
from __future__ import annotations

import json
import logging

import azure.functions as func

from services.case_store import get_case, list_cases

bp = func.Blueprint()


def _json_response(body, status_code: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(body),
        status_code=status_code,
        mimetype="application/json",
    )


def _inject_case_number_visibility(summary: dict) -> dict:
    """Expose caseNumber without mutating merchantName display text."""
    case_id = str(summary.get("caseId") or "").strip()
    if not case_id:
        return summary

    enriched = dict(summary)
    enriched["caseNumber"] = case_id
    return enriched


# ── GET /api/cases ────────────────────────────────────────────────────────────

@bp.route(route="cases", methods=["GET"])
def list_cases_http(req: func.HttpRequest) -> func.HttpResponse:
    """
    GET /api/cases[?status=<CaseStatus>]

    Returns the queue-list view as { "cases": CaseSummary[], "total": int }.
    Each CaseSummary includes: caseId, status, cardNetwork, merchantName,
    transactionAmount, reasonCode, reasonCodeLabel, winProbability, riskLevel,
    deadline (dueDate + live daysRemaining), createdAt, updatedAt.

    Query params:
      status  — optional; filter to a single CaseStatus value
                e.g. ?status=pending_review
    """
    status_filter: str | None = req.params.get("status") or None
    summaries = [_inject_case_number_visibility(item) for item in list_cases(status_filter)]

    logging.info(
        "[case_read] GET /cases — filter=%s returned %d cases",
        status_filter, len(summaries),
    )
    return _json_response({"cases": summaries, "total": len(summaries)})


# ── GET /api/cases/{caseId} ───────────────────────────────────────────────────

@bp.route(route="cases/{caseId}", methods=["GET"])
def get_case_http(req: func.HttpRequest) -> func.HttpResponse:
    """
    GET /api/cases/{caseId}

    Returns the full Case object for the given caseId.
    deadline.daysRemaining is recomputed live from dueDate.

    Response 200: full Case JSON
    Response 404: { "error": "Case '<id>' not found." }
    """
    case_id: str = req.route_params.get("caseId", "").strip()
    if not case_id:
        return _json_response({"error": "caseId path parameter is required."}, status_code=400)

    case = get_case(case_id)
    if case is None:
        logging.info("[case_read] GET /cases/%s — not found", case_id)
        return _json_response({"error": f"Case '{case_id}' not found."}, status_code=404)

    logging.info("[case_read] GET /cases/%s — status=%s", case_id, case.get("status"))
    return _json_response(case)
