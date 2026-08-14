"""
HTTP action triggers for the HITL analyst approval gate.

Routes (all under /api/):
  POST cases/{caseId}/start-review   — returns 503 (durable binding unavailable)
  POST cases/{caseId}/approve        — persists approved status to case store
  POST cases/{caseId}/deny           — persists denied  status to case store
  POST cases/{caseId}/escalate       — persists escalated status to case store

All action routes (approve/deny/escalate) expect:
  Body: { "analystId": "<string>", "comment": "<string>" (optional) }

Design note — durable client binding removed (issue #56):
  The @bp.durable_client_input binding causes a host-level empty-body 500 on
  Azure Functions Flex Consumption before Python code executes — the binding
  init fails at the worker layer and our try/except cannot intercept it.  The
  binding has been removed from ALL routes in this module.

  Status persistence (Cosmos write via update_case_status) is the primary
  requirement and works without any durable dependency.  The approve/deny/
  escalate routes are now plain HTTP triggers: validate case → persist → 200.

  Durable signaling is now best-effort via the Durable Task HTTP webhook API.
  Status persistence remains the primary success path: a signaling failure is
  logged but does not change the HTTP response.
"""
from __future__ import annotations

import logging
import json
import io
import zipfile

import azure.functions as func

from services.case_store import get_case, update_case_status
from services.document_service import (
    get_documents,
    get_document_bytes,
    get_synthetic_evidence_artifact,
    ensure_case_synthetic_artifacts,
    list_case_synthetic_artifacts,
    upload_document,
    compute_updated_score,
    create_case_closure_document,
)
from services.durable_orchestration_client import raise_analyst_decision as raise_durable_event

try:
    from cosmos_client import create_timeline_event
    from cosmos_models import new_timeline_event
except Exception:  # noqa: BLE001
    create_timeline_event = None  # type: ignore[assignment]
    new_timeline_event = None  # type: ignore[assignment]

bp = func.Blueprint()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _json_response(body: dict, status_code: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(body),
        status_code=status_code,
        mimetype="application/json",
    )


def _parse_body(req: func.HttpRequest) -> dict:
    """Parse JSON request body; return empty dict on any parse failure."""
    try:
        return req.get_json()
    except (ValueError, TypeError):
        return {}


def _require_analyst_id(body: dict) -> str | None:
    """Return analystId from body, or None if missing/blank."""
    value = body.get("analystId", "")
    return value if isinstance(value, str) and value.strip() else None


def _safe_bundle_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in value)


def _with_proxy_document_url(case_id: str, doc: dict) -> dict:
    """Return a document payload with blobUrl rewritten to the API proxy download endpoint."""
    document_id = str(doc.get("documentId") or "").strip()
    if not document_id:
        return doc

    proxy_url = (
        f"/api/cases/{case_id}/documents/"
        f"{document_id}/download"
    )
    rewritten = dict(doc)
    if "blobUrl" in rewritten:
        rewritten["storageBlobUrl"] = rewritten.get("blobUrl")
    rewritten["blobUrl"] = proxy_url
    rewritten["downloadUrl"] = proxy_url
    return rewritten


def _raise_analyst_decision(
    case_id: str,
    action: str,
    analyst_id: str,
    comment: str | None,
) -> func.HttpResponse:
    """
    Validates the case exists in the store, persists the analyst decision,
    and returns 200.

    Flow:
      1. Validate the case EXISTS via get_case → 404 if not found.
      2. Persist the new status via update_case_status.  Errors are caught and
         logged as WARNING; a persistence failure does NOT cause a 5xx.
      3. Return 200 {"status": new_status, "caseId": case_id}.

    Durable signaling is best-effort only; persistence remains primary.
    """
    case = get_case(case_id)
    if case is None:
        logging.warning("[case_actions] case not found — caseId=%s", case_id)
        return _json_response({"error": f"Case '{case_id}' not found."}, status_code=404)

    _status_map = {"approve": "approved", "deny": "denied", "escalate": "escalated"}
    new_status = _status_map.get(action, action)

    try:
        update_case_status(case_id, new_status)
    except Exception as exc:  # noqa: BLE001
        logging.warning(
            "[case_actions] status persistence failed — caseId=%s status=%s exc=%s",
            case_id, new_status, exc,
        )

    # For final analyst outcomes, persist a closure artifact in the closed folder.
    if new_status in {"approved", "denied"}:
        try:
            create_case_closure_document(
                case_id=case_id,
                case_data=case,
                disposition=new_status,
                analyst_id=analyst_id,
                reason=comment,
            )
        except Exception as exc:  # noqa: BLE001
            logging.warning(
                "[case_actions] closure artifact creation failed — caseId=%s status=%s exc=%s",
                case_id,
                new_status,
                exc,
            )

    if create_timeline_event and new_timeline_event:
        try:
            timeline_event = new_timeline_event(
                    dispute_id=case_id,
                    event_type="status_change",
                    actor=analyst_id,
                    detail=f"Analyst action '{action}' applied — status={new_status}",
                    data={
                        "action": action,
                        "status": new_status,
                        "comment": comment or "",
                    },
                )
            create_timeline_event(timeline_event)
            try:
                import cosmos_client

                cosmos_client.touch_dispute_activity(
                    case_id,
                    event_type="status_change",
                    actor=analyst_id,
                    detail=f"Analyst action '{action}' applied — status={new_status}",
                    occurred_at=timeline_event.get("occurredAt"),
                )
            except Exception:  # noqa: BLE001
                pass
        except Exception as exc:  # noqa: BLE001
            logging.warning(
                "[case_actions] timeline persist failed — caseId=%s action=%s exc=%s",
                case_id,
                action,
                exc,
            )

    try:
        raise_durable_event(case_id, action, analyst_id, comment)
    except Exception as exc:  # noqa: BLE001
        logging.warning(
            "[case_actions] durable signal failed — caseId=%s action=%s exc=%s",
            case_id,
            action,
            exc,
        )

    logging.info(
        "[case_actions] decision recorded — caseId=%s action=%s analystId=%s status=%s",
        case_id, action, analyst_id, new_status,
    )
    return _json_response({"status": new_status, "caseId": case_id})


def _handle_start_review(case_id: str) -> func.HttpResponse:
    """
    Inner logic for start_review — testable without the route decorator.
    Returns 400 for missing caseId, 503 for the (unavailable) durable binding.
    """
    if not case_id:
        return _json_response({"error": "caseId path parameter is required."}, status_code=400)
    logging.warning(
        "[start_review] durable binding not available on this plan — caseId=%s", case_id
    )
    return _json_response(
        {
            "error": "Orchestration start is not available in this environment.",
            "detail": (
                "The Durable Functions client binding is not supported on the current "
                "Flex Consumption plan.  Use the pipeline ingest endpoint for "
                "cases that require the full HITL orchestration flow."
            ),
        },
        status_code=503,
    )


# ── Start-review ──────────────────────────────────────────────────────────────

@bp.route(route="cases/{caseId}/start-review", methods=["POST"])
def start_review(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/cases/{caseId}/start-review

    Durable orchestration startup is NOT available in this environment.
    The @bp.durable_client_input binding causes a host-level crash on Flex
    Consumption, so this route returns 503 instead of an empty-body 500.

    Response 503: { "error": "...", "detail": "..." }
    Response 400: caseId missing
    """
    case_id: str = req.route_params.get("caseId", "").strip()
    return _handle_start_review(case_id)


# ── Approve ───────────────────────────────────────────────────────────────────

@bp.route(route="cases/{caseId}/approve", methods=["POST"])
def approve_case(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/cases/{caseId}/approve

    Body: { "analystId": "<string>", "comment": "<string>" (optional) }
    Response 200: { "status": "approved", "caseId": "<caseId>" }
    Response 400: analystId missing
    Response 404: case not found
    """
    case_id: str = req.route_params.get("caseId", "")
    body = _parse_body(req)
    analyst_id = _require_analyst_id(body)
    if not analyst_id:
        return _json_response({"error": "analystId is required in the request body."}, status_code=400)
    return _raise_analyst_decision(case_id, "approve", analyst_id, body.get("comment"))


# ── Deny ──────────────────────────────────────────────────────────────────────

@bp.route(route="cases/{caseId}/deny", methods=["POST"])
def deny_case(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/cases/{caseId}/deny

    Body: { "analystId": "<string>", "comment": "<string>" (optional) }
    Response 200: { "status": "denied", "caseId": "<caseId>" }
    Response 400: analystId missing
    Response 404: case not found
    """
    case_id: str = req.route_params.get("caseId", "")
    body = _parse_body(req)
    analyst_id = _require_analyst_id(body)
    if not analyst_id:
        return _json_response({"error": "analystId is required in the request body."}, status_code=400)
    return _raise_analyst_decision(case_id, "deny", analyst_id, body.get("comment"))


# ── Escalate ──────────────────────────────────────────────────────────────────

@bp.route(route="cases/{caseId}/escalate", methods=["POST"])
def escalate_case(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/cases/{caseId}/escalate

    Body: { "analystId": "<string>", "comment": "<string>" (optional) }
    Response 200: { "status": "escalated", "caseId": "<caseId>" }
    Response 400: analystId missing
    Response 404: case not found
    """
    case_id: str = req.route_params.get("caseId", "")
    body = _parse_body(req)
    analyst_id = _require_analyst_id(body)
    if not analyst_id:
        return _json_response({"error": "analystId is required in the request body."}, status_code=400)
    return _raise_analyst_decision(case_id, "escalate", analyst_id, body.get("comment"))


@bp.route(route="cases/{caseId}/recommendation-response", methods=["POST"])
def record_recommendation_response(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/cases/{caseId}/recommendation-response

    Persists analyst accept/reject/modify responses to AI recommendations,
    creates an auditable timeline event, writes a note artifact, and sends
    a best-effort signal back to the AI orchestration channel.

    Body:
      {
        "analystId": "<string>",
        "decision": "accept"|"reject"|"modify",
        "recommendationDisposition": "<string>",
        "recommendationConfidence": <number>,
        "reasoning": ["..."],
        "comment": "<string, optional>",
        "modifiedRecommendation": "<string, optional>"
      }
    """
    case_id: str = req.route_params.get("caseId", "").strip()
    if not case_id:
        return _json_response({"error": "caseId path parameter is required."}, status_code=400)

    case = get_case(case_id)
    if case is None:
        return _json_response({"error": f"Case '{case_id}' not found."}, status_code=404)

    body = _parse_body(req)
    analyst_id = _require_analyst_id(body)
    if not analyst_id:
        return _json_response({"error": "analystId is required in the request body."}, status_code=400)

    decision = (body.get("decision") or "").strip().lower()
    if decision not in {"accept", "reject", "modify"}:
        return _json_response({"error": "decision must be one of: accept, reject, modify."}, status_code=400)

    recommendation_disposition = (body.get("recommendationDisposition") or "").strip()
    recommendation_confidence = body.get("recommendationConfidence")
    reasoning = body.get("reasoning")
    if not isinstance(reasoning, list):
        reasoning = []

    comment = (body.get("comment") or "").strip() or None
    modified_recommendation = (body.get("modifiedRecommendation") or "").strip() or None

    from datetime import datetime, timezone

    timestamp = datetime.now(timezone.utc).isoformat()
    note_lines = [
        "AI recommendation response",
        f"Decision: {decision}",
        f"Disposition: {recommendation_disposition or 'n/a'}",
        f"Confidence: {recommendation_confidence if recommendation_confidence is not None else 'n/a'}",
    ]
    if reasoning:
        note_lines.append("Reasoning:")
        note_lines.extend([f"- {str(item)}" for item in reasoning])
    if comment:
        note_lines.append(f"Reject reason/comment: {comment}")
    if modified_recommendation:
        note_lines.append(f"Modified recommendation: {modified_recommendation}")
    note_text = "\n".join(note_lines)

    # Persist as a note artifact for auditability and downstream AI grounding.
    try:
        artifact_name = (
            f"ai-recommendation-response-{decision}-{case_id}-"
            f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.txt"
        )
        upload_document(
            case_id=case_id,
            filename=artifact_name,
            content_type="text/plain",
            file_bytes=note_text.encode("utf-8"),
            submitted_by=analyst_id,
            submitted_from="analyst_portal",
            note="Analyst AI recommendation response",
        )
    except Exception as exc:  # noqa: BLE001
        logging.warning(
            "[case_actions] ai recommendation note artifact save failed — caseId=%s exc=%s",
            case_id,
            exc,
        )

    # Persist timeline/audit event.
    if create_timeline_event and new_timeline_event:
        try:
            event = new_timeline_event(
                dispute_id=case_id,
                event_type="ai_recommendation_response",
                actor=analyst_id,
                detail=(
                    f"Analyst {decision}ed AI recommendation "
                    f"({recommendation_disposition or 'unspecified disposition'})"
                ),
                data={
                    "decision": decision,
                    "recommendationDisposition": recommendation_disposition,
                    "recommendationConfidence": recommendation_confidence,
                    "reasoning": reasoning,
                    "comment": comment,
                    "modifiedRecommendation": modified_recommendation,
                },
            )
            create_timeline_event(event)
            try:
                import cosmos_client

                cosmos_client.touch_dispute_activity(
                    case_id,
                    event_type="ai_recommendation_response",
                    actor=analyst_id,
                    detail=event.get("detail") or f"Analyst {decision}ed AI recommendation",
                    occurred_at=event.get("occurredAt"),
                )
            except Exception:  # noqa: BLE001
                pass
        except Exception as exc:  # noqa: BLE001
            logging.warning(
                "[case_actions] timeline persist failed for ai recommendation response — caseId=%s exc=%s",
                case_id,
                exc,
            )

    # Best-effort signal back to orchestration/AI channel.
    ai_signal_action = f"ai_recommendation_{decision}"
    signal_comment_parts = []
    if comment:
        signal_comment_parts.append(comment)
    if modified_recommendation:
        signal_comment_parts.append(f"modified={modified_recommendation}")
    signal_comment = " | ".join(signal_comment_parts) if signal_comment_parts else None
    try:
        raise_durable_event(case_id, ai_signal_action, analyst_id, signal_comment)
    except Exception as exc:  # noqa: BLE001
        logging.warning(
            "[case_actions] durable ai recommendation signal failed — caseId=%s action=%s exc=%s",
            case_id,
            ai_signal_action,
            exc,
        )

    logging.info(
        "[case_actions] ai recommendation response recorded — caseId=%s analystId=%s decision=%s",
        case_id,
        analyst_id,
        decision,
    )
    return _json_response(
        {
            "caseId": case_id,
            "analystId": analyst_id,
            "decision": decision,
            "status": "recorded",
            "timestamp": timestamp,
        },
        status_code=200,
    )


@bp.route(route="cases/{caseId}/evidence-gaps/request", methods=["POST"])
def request_evidence_gap(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/cases/{caseId}/evidence-gaps/request

    Persists an analyst evidence-gap retrieval request, creates a timeline/audit
    event, stores an artifact note, and sends a best-effort signal to the
    orchestration/AI channel.

    Body:
      {
        "analystId": "<string>",
        "missingItem": "<string>",
        "reason": "<string>",
        "impact": "critical"|"high"|"medium"|"low",
        "suggestedAction": "<string, optional>"
      }
    """
    case_id: str = req.route_params.get("caseId", "").strip()
    if not case_id:
        return _json_response({"error": "caseId path parameter is required."}, status_code=400)

    case = get_case(case_id)
    if case is None:
        return _json_response({"error": f"Case '{case_id}' not found."}, status_code=404)

    body = _parse_body(req)
    analyst_id = _require_analyst_id(body)
    if not analyst_id:
        return _json_response({"error": "analystId is required in the request body."}, status_code=400)

    missing_item = (body.get("missingItem") or "").strip()
    reason = (body.get("reason") or "").strip()
    impact = (body.get("impact") or "").strip().lower()
    suggested_action = (body.get("suggestedAction") or "").strip() or None

    if not missing_item:
        return _json_response({"error": "missingItem is required."}, status_code=400)
    if not reason:
        return _json_response({"error": "reason is required."}, status_code=400)
    if impact not in {"critical", "high", "medium", "low"}:
        return _json_response({"error": "impact must be one of: critical, high, medium, low."}, status_code=400)

    from datetime import datetime, timezone

    timestamp = datetime.now(timezone.utc).isoformat()
    note_lines = [
        "Evidence gap retrieval requested",
        f"Missing item: {missing_item}",
        f"Impact: {impact}",
        f"Reason: {reason}",
    ]
    if suggested_action:
        note_lines.append(f"Suggested action: {suggested_action}")
    note_text = "\n".join(note_lines)

    try:
        artifact_name = (
            f"evidence-gap-request-{case_id}-"
            f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.txt"
        )
        upload_document(
            case_id=case_id,
            filename=artifact_name,
            content_type="text/plain",
            file_bytes=note_text.encode("utf-8"),
            submitted_by=analyst_id,
            submitted_from="analyst_portal",
            note="Analyst evidence gap auto-request",
        )
    except Exception as exc:  # noqa: BLE001
        logging.warning(
            "[case_actions] evidence gap request artifact save failed — caseId=%s item=%s exc=%s",
            case_id,
            missing_item,
            exc,
        )

    if create_timeline_event and new_timeline_event:
        try:
            event = new_timeline_event(
                dispute_id=case_id,
                event_type="evidence_gap_requested",
                actor=analyst_id,
                detail=f"Evidence gap requested: {missing_item} ({impact})",
                data={
                    "missingItem": missing_item,
                    "reason": reason,
                    "impact": impact,
                    "suggestedAction": suggested_action,
                },
            )
            create_timeline_event(event)
            try:
                import cosmos_client

                cosmos_client.touch_dispute_activity(
                    case_id,
                    event_type="evidence_gap_requested",
                    actor=analyst_id,
                    detail=event.get("detail") or f"Evidence gap requested: {missing_item}",
                    occurred_at=event.get("occurredAt"),
                )
            except Exception:  # noqa: BLE001
                pass
        except Exception as exc:  # noqa: BLE001
            logging.warning(
                "[case_actions] timeline persist failed for evidence gap request — caseId=%s item=%s exc=%s",
                case_id,
                missing_item,
                exc,
            )

    try:
        raise_durable_event(case_id, "request_evidence_gap", analyst_id, note_text)
    except Exception as exc:  # noqa: BLE001
        logging.warning(
            "[case_actions] durable signal failed for evidence gap request — caseId=%s item=%s exc=%s",
            case_id,
            missing_item,
            exc,
        )

    logging.info(
        "[case_actions] evidence gap requested — caseId=%s analystId=%s item=%s impact=%s",
        case_id,
        analyst_id,
        missing_item,
        impact,
    )
    return _json_response(
        {
            "caseId": case_id,
            "analystId": analyst_id,
            "missingItem": missing_item,
            "status": "requested",
            "timestamp": timestamp,
        },
        status_code=200,
    )


# ── Add Note (no status change) ──────────────────────────────────────────────

@bp.route(route="cases/{caseId}/add-note", methods=["POST"])
def add_case_note(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/cases/{caseId}/add-note

    Adds an analyst note/comment to the case timeline without changing status.
    Body: { "analystId": "<string>", "comment": "<string>" }
    Response 200: { "caseId": "...", "note": "...", "analystId": "...", "timestamp": "..." }
    Response 400: analystId or comment missing
    """
    case_id: str = req.route_params.get("caseId", "").strip()
    if not case_id:
        return _json_response({"error": "caseId path parameter is required."}, status_code=400)

    body = _parse_body(req)
    analyst_id = _require_analyst_id(body)
    if not analyst_id:
        return _json_response({"error": "analystId is required in the request body."}, status_code=400)

    comment = (body.get("comment") or "").strip()
    if not comment:
        return _json_response({"error": "comment is required for a note."}, status_code=400)

    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).isoformat()

    # Save analyst note text as a blob-backed, AI-analyzed artifact.
    try:
        artifact_name = f"analyst-note-{case_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.txt"
        upload_document(
            case_id=case_id,
            filename=artifact_name,
            content_type="text/plain",
            file_bytes=comment.encode("utf-8"),
            submitted_by=analyst_id,
            submitted_from="analyst_portal",
            note="Analyst note artifact",
        )
    except Exception as exc:  # noqa: BLE001
        logging.warning("[case_actions] analyst note artifact save failed — caseId=%s exc=%s", case_id, exc)

    # Persist to timeline if Cosmos is available
    if create_timeline_event and new_timeline_event:
        try:
            event = new_timeline_event(
                dispute_id=case_id,
                event_type="analyst_note",
                actor=analyst_id,
                detail=comment,
            )
            create_timeline_event(event)
            try:
                import cosmos_client

                cosmos_client.touch_dispute_activity(
                    case_id,
                    event_type="analyst_note",
                    actor=analyst_id,
                    detail=comment,
                    occurred_at=event.get("occurredAt"),
                )
            except Exception:  # noqa: BLE001
                pass
        except Exception as exc:  # noqa: BLE001
            logging.warning("[case_actions] timeline persist failed for note — caseId=%s exc=%s", case_id, exc)

    logging.info("[case_actions] note added — caseId=%s analystId=%s", case_id, analyst_id)

    return _json_response({
        "caseId": case_id,
        "note": comment,
        "analystId": analyst_id,
        "timestamp": timestamp,
    })


# ── Document Upload ───────────────────────────────────────────────────────────

@bp.route(route="cases/{caseId}/documents", methods=["POST"])
def upload_case_document(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/cases/{caseId}/documents

    Accepts multipart/form-data with field name 'file'.
    Returns document metadata + AI analysis + updated win probability.

    Response 201: { "document": {...}, "scoreUpdate": {...}, "message": "..." }
    Response 400: no file or empty file
    Response 404: case not found
    Response 413: file exceeds 10MB
    """
    case_id: str = req.route_params.get("caseId", "").strip()
    if not case_id:
        return _json_response({"error": "caseId path parameter is required."}, status_code=400)

    case = get_case(case_id) or {"caseId": case_id, "winProbability": 0.5}

    # Azure Functions exposes uploaded files via get_body() for multipart
    # The file is accessible via the request files interface
    def _read_form_value(field_name: str) -> str | None:
        try:
            if req.form:
                value = req.form.get(field_name)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        except Exception:
            pass
        query_value = req.params.get(field_name)
        if isinstance(query_value, str) and query_value.strip():
            return query_value.strip()
        return None

    try:
        file = req.files.get("file")
    except Exception:
        file = None

    if file is None:
        return _json_response(
            {"error": "No file provided. Use multipart/form-data with field name 'file'."},
            status_code=400,
        )

    filename = file.filename or ""
    if not filename:
        return _json_response({"error": "Empty filename."}, status_code=400)

    file_bytes = file.read()
    if len(file_bytes) == 0:
        return _json_response({"error": "Empty file."}, status_code=400)

    if len(file_bytes) > 10 * 1024 * 1024:
        return _json_response({"error": "File exceeds 10MB limit."}, status_code=413)

    try:
        submitted_by = _read_form_value("submittedBy") or "unknown"
        submitted_from = _read_form_value("submittedFrom") or "analyst_portal"
        note = _read_form_value("note")

        doc_record = upload_document(
            case_id=case_id,
            filename=filename,
            content_type=file.content_type or "application/octet-stream",
            file_bytes=file_bytes,
            submitted_by=submitted_by,
            submitted_from=submitted_from,
            note=note,
        )

        current_win_prob = case.get("winProbability") or 0.5
        score_update = compute_updated_score(case_id, current_win_prob)
    except Exception as exc:
        logging.exception("[case_actions] document upload failed — caseId=%s filename=%s", case_id, filename)
        return _json_response({"error": f"Document processing failed: {exc}"}, status_code=500)

    logging.info(
        "[case_actions] document uploaded — caseId=%s filename=%s score=%.2f",
        case_id, filename, doc_record.get("analysis", {}).get("evidenceScore", 0),
    )

    return func.HttpResponse(
        json.dumps({
            "document": _with_proxy_document_url(case_id, doc_record),
            "scoreUpdate": score_update,
            "message": f"Document '{filename}' uploaded and analyzed.",
        }, default=str),
        status_code=201,
        mimetype="application/json",
    )


# ── Document List ─────────────────────────────────────────────────────────────

@bp.route(route="cases/{caseId}/documents", methods=["GET"])
def list_case_documents(req: func.HttpRequest) -> func.HttpResponse:
    """
    GET /api/cases/{caseId}/documents

    Returns all uploaded documents for a case.
    Response 200: { "caseId": "...", "documents": [...], "total": N }
    Response 404: case not found
    """
    case_id: str = req.route_params.get("caseId", "").strip()
    if not case_id:
        return _json_response({"error": "caseId path parameter is required."}, status_code=400)

    docs = get_documents(case_id)
    public_docs = [_with_proxy_document_url(case_id, doc) for doc in docs]
    return _json_response({"caseId": case_id, "documents": public_docs, "total": len(public_docs)})


@bp.route(route="cases/{caseId}/documents/{documentId}/download", methods=["GET"])
def download_case_document(req: func.HttpRequest) -> func.HttpResponse:
    """Download a specific case document by id for customer/analyst review."""
    case_id: str = req.route_params.get("caseId", "").strip()
    document_id: str = req.route_params.get("documentId", "").strip()
    if not case_id or not document_id:
        return _json_response({"error": "caseId and documentId path parameters are required."}, status_code=400)

    resolved = get_document_bytes(case_id, document_id)
    if not resolved:
        return _json_response({"error": "Document not found or unavailable for download."}, status_code=404)

    data, content_type, filename = resolved
    return func.HttpResponse(
        body=data,
        status_code=200,
        mimetype=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@bp.route(route="cases/{caseId}/evidence/{evidenceId}/download", methods=["GET"])
def download_synthetic_evidence(req: func.HttpRequest) -> func.HttpResponse:
    """Generate and download a seeded evidence artifact for demo review."""
    case_id: str = req.route_params.get("caseId", "").strip()
    evidence_id: str = req.route_params.get("evidenceId", "").strip()
    if not case_id or not evidence_id:
        return _json_response({"error": "caseId and evidenceId path parameters are required."}, status_code=400)

    try:
        resolved = get_synthetic_evidence_artifact(case_id, evidence_id)
    except Exception as exc:  # noqa: BLE001
        logging.exception(
            "[case_actions] synthetic evidence download failed — caseId=%s evidenceId=%s exc=%s",
            case_id,
            evidence_id,
            exc,
        )
        resolved = None

    # Compatibility fallback: some older records reuse documentId in the evidence URL.
    if not resolved:
        resolved = get_document_bytes(case_id, evidence_id)

    if not resolved:
        return _json_response({"error": "Evidence artifact not found."}, status_code=404)

    data, content_type, filename = resolved
    return func.HttpResponse(
        body=data,
        status_code=200,
        mimetype=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@bp.route(route="cases/{caseId}/evidence/preseed", methods=["POST"])
def preseed_case_evidence(req: func.HttpRequest) -> func.HttpResponse:
    """Pre-generate synthetic evidence artifacts for all seeded evidence in a case."""
    case_id: str = req.route_params.get("caseId", "").strip()
    if not case_id:
        return _json_response({"error": "caseId path parameter is required."}, status_code=400)

    try:
        result = ensure_case_synthetic_artifacts(case_id)
    except Exception as exc:  # noqa: BLE001
        logging.warning(
            "[case_actions] evidence preseed skipped — caseId=%s exc=%s",
            case_id,
            exc,
        )
        return _json_response(
            {
                "caseId": case_id,
                "generated": 0,
                "total": 0,
                "warning": "Evidence pre-seed skipped due to a transient backend dependency issue.",
            }
        )

    if result.get("total", 0) == 0:
        return _json_response(
            {
                "caseId": case_id,
                "generated": 0,
                "total": 0,
                "message": "No seeded synthetic evidence found for case.",
            }
        )

    return _json_response(
        {
            "caseId": case_id,
            "generated": result.get("generated", 0),
            "total": result.get("total", 0),
            "message": "Synthetic evidence artifacts are ready.",
        }
    )


@bp.route(route="cases/{caseId}/evidence/download-all", methods=["GET"])
def download_case_evidence_bundle(req: func.HttpRequest) -> func.HttpResponse:
    """Download a ZIP containing uploaded documents and synthetic evidence artifacts."""
    case_id: str = req.route_params.get("caseId", "").strip()
    if not case_id:
        return _json_response({"error": "caseId path parameter is required."}, status_code=400)

    archive = io.BytesIO()
    count = 0

    with zipfile.ZipFile(archive, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Include uploaded documents (if any).
        for doc in get_documents(case_id):
            doc_id = str(doc.get("documentId") or "")
            if not doc_id:
                continue
            resolved = get_document_bytes(case_id, doc_id)
            if not resolved:
                continue
            data, _content_type, filename = resolved
            safe_name = _safe_bundle_name(filename or f"document_{doc_id}")
            zf.writestr(f"uploaded/{safe_name}", data)
            count += 1

        # Include synthetic seeded evidence artifacts.
        for evidence_id, data, _content_type, filename in list_case_synthetic_artifacts(case_id):
            safe_name = _safe_bundle_name(filename or f"evidence_{evidence_id}.json")
            zf.writestr(f"synthetic/{safe_name}", data)
            count += 1

    if count == 0:
        return _json_response(
            {"error": "No evidence artifacts available for this case."},
            status_code=404,
        )

    bundle_name = _safe_bundle_name(f"evidence-bundle-{case_id}.zip")
    return func.HttpResponse(
        body=archive.getvalue(),
        status_code=200,
        mimetype="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{bundle_name}"',
            "Cache-Control": "no-store",
        },
    )
