import azure.functions as func
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from orchestrator.dispute_orchestrator import bp as orchestrator_bp
from activities.case_activities import bp as activities_bp
from triggers.case_actions import bp as actions_bp
from triggers.case_read import bp as read_bp
from triggers.pl_ingest_raw import bp as ingest_bp
from triggers.pl_ingest_raw import _calculate_deadline, intake_dispute_record
from triggers.pl_master_refresh import bp as refresh_bp

import cosmos_client
from services.reason_code_engine import (
    get_supported_networks,
    get_reason_codes_for_network,
    get_reason_code_detail,
    get_evidence_checklist,
    identify_evidence_gaps,
)
from services.evidence_retrieval import retrieve_evidence_for_dispute
from services.maker_agent_client import draft_rebuttal, to_rebuttal_draft
from services.scoring_service import score_case
from services.gaps_service import detect_gaps
from services.evidence_search import retrieve_precedents_for_dispute
from services.document_service import upload_document
from services.runtime_case_store import (
    register_case as register_runtime_case,
    get_case as get_runtime_case,
    list_for_customer as list_runtime_cases_for_customer,
)

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

app.register_blueprint(orchestrator_bp)
app.register_blueprint(activities_bp)
app.register_blueprint(actions_bp)
app.register_blueprint(read_bp)
app.register_blueprint(ingest_bp)
app.register_blueprint(refresh_bp)

RUNNING_IN_AZURE = bool(os.getenv("WEBSITE_INSTANCE_ID"))
ALLOW_DEMO_FALLBACK = os.getenv("ALLOW_DEMO_FALLBACK", "false" if RUNNING_IN_AZURE else "true").strip().lower() == "true"


def _to_lower_token(value: Any) -> str:
    return str(value or "").strip().lower()


def _build_case_document_proxy_url(case_id: str, document_id: str) -> str:
    return f"/api/cases/{case_id}/documents/{document_id}/download"


def _rewrite_timeline_document_links(case_id: str, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rewritten: list[dict[str, Any]] = []
    for ev in events:
        ev_copy = dict(ev)
        data = ev_copy.get("data")
        if isinstance(data, dict):
            document_id = str(data.get("documentId") or "").strip()
            if document_id:
                proxy_url = _build_case_document_proxy_url(case_id, document_id)
                data_copy = dict(data)
                if "blobUrl" in data_copy:
                    data_copy["storageBlobUrl"] = data_copy.get("blobUrl")
                data_copy["blobUrl"] = proxy_url
                data_copy["downloadUrl"] = proxy_url
                ev_copy["data"] = data_copy
        rewritten.append(ev_copy)
    return rewritten


def _normalize_timeline_event(ev: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize a Cosmos timeline document to the portal API contract.

    Cosmos documents store ``occurredAt`` / ``detail`` / ``data``; the portal
    TimelineEvent interface expects ``timestamp`` / ``description`` / ``metadata``.
    Both field names are preserved for backwards-compatible consumers.
    """
    normalized = dict(ev)
    if "timestamp" not in normalized and "occurredAt" in normalized:
        normalized["timestamp"] = normalized["occurredAt"]
    if "description" not in normalized and "detail" in normalized:
        normalized["description"] = normalized["detail"]
    if "metadata" not in normalized and "data" in normalized:
        normalized["metadata"] = normalized["data"]
    if normalized.get("eventType") == "status_change":
        normalized["eventType"] = "status_changed"
    return normalized


def _rewrite_evidence_document_links(case_id: str, evidence_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rewritten: list[dict[str, Any]] = []
    for item in evidence_items:
        item_copy = dict(item)
        content = item_copy.get("content")
        if isinstance(content, dict):
            document_id = str(content.get("documentId") or "").strip()
            if document_id:
                proxy_url = _build_case_document_proxy_url(case_id, document_id)
                content_copy = dict(content)
                if "blobUrl" in content_copy:
                    content_copy["storageBlobUrl"] = content_copy.get("blobUrl")
                content_copy["blobUrl"] = proxy_url
                content_copy["downloadUrl"] = proxy_url
                item_copy["content"] = content_copy
        rewritten.append(item_copy)
    return rewritten


def _ensure_foundational_timeline(dispute_id: str, events: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """
    Ensure a dispute has foundational audit events so analyst-side audit logs
    include customer/lifecycle origins.

    Backfills are persisted once and then returned with the timeline.
    """
    try:
        timeline = list(events or cosmos_client.get_timeline_for_dispute(dispute_id) or [])
    except Exception as exc:  # noqa: BLE001
        logging.warning("Timeline lookup failed for %s: %s", dispute_id, exc)
        return list(events or [])
    normalized_types = {_to_lower_token(ev.get("eventType")) for ev in timeline}

    try:
        results = cosmos_client.query_disputes(
            "SELECT * FROM c WHERE c.id = @id",
            parameters=[{"name": "@id", "value": dispute_id}],
            max_items=1,
        )
    except Exception as exc:  # noqa: BLE001
        logging.warning("Timeline dispute lookup failed for %s: %s", dispute_id, exc)
        return _rewrite_timeline_document_links(dispute_id, timeline)

    dispute = results[0] if results else None
    if not dispute:
        return timeline

    metadata = dispute.get("metadata") or {}
    customer_id = str(metadata.get("customerId") or "").strip()
    source_system = str(dispute.get("sourceSystem") or metadata.get("sourceSystem") or "").strip().lower()
    created_at = dispute.get("createdAt") or datetime.now(timezone.utc).isoformat()
    initial_status = dispute.get("status") or "intake"

    has_creation_marker = any(
        event_type in normalized_types
        for event_type in ("case_created", "status_change", "status_changed")
    )
    if not has_creation_marker:
        from cosmos_models import new_timeline_event

        actor = customer_id or ("customer" if "portal" in source_system else "pipeline/ingest_raw")
        detail = "Dispute submitted by customer" if "portal" in source_system or customer_id else "Dispute case created"
        event = new_timeline_event(
            dispute_id=dispute_id,
            event_type="case_created",
            actor=actor,
            detail=detail,
            data={
                "customerId": customer_id or None,
                "sourceSystem": source_system or "unknown",
                "initialStatus": initial_status,
            },
        )
        event["occurredAt"] = created_at
        cosmos_client.create_timeline_event(event)
        timeline.append(event)

    sorted_timeline = sorted(
        timeline,
        key=lambda ev: str(ev.get("occurredAt") or ev.get("timestamp") or ""),
    )
    return _rewrite_timeline_document_links(dispute_id, sorted_timeline)



@app.route(route="health")
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Health check called.")
    return func.HttpResponse("OK", status_code=200)


# ── Portal-friendly helpers ───────────────────────────────────────────────────

def _compute_deadline_utc(network_code: str, transaction_date: str) -> str:
    """Auto-calculate response deadline from network SLA rules."""
    return _calculate_deadline(network_code, transaction_date)


def _build_degraded_dispute_response(body: dict[str, Any]) -> dict[str, Any]:
    """Return a demo-safe created dispute payload when persistent storage is unavailable."""
    dispute_id = f"demo-{uuid4()}"
    created_at = datetime.now(timezone.utc).isoformat()
    network_code = str(body.get("networkCode") or "unknown")
    transaction_date = str(body.get("transactionDate") or datetime.now(timezone.utc).date().isoformat())
    deadline_utc = body.get("deadlineUtc") or _compute_deadline_utc(network_code, transaction_date)

    return {
        "id": dispute_id,
        "disputeId": dispute_id,
        "caseId": dispute_id,
        "orchestrationId": dispute_id,
        "networkCode": network_code,
        "cardNetwork": network_code,
        "reasonCode": body.get("reasonCode", "unknown"),
        "reasonCodeLabel": body.get("reasonCode", "unknown"),
        "status": "intake",
        "cardholderName": body.get("cardholderName", ""),
        "cardLastFour": body.get("cardLastFour", ""),
        "transactionAmount": body.get("transactionAmount", 0),
        "transactionCurrency": body.get("transactionCurrency", "USD"),
        "transactionDate": transaction_date,
        "merchantName": body.get("merchantName", ""),
        "deadlineUtc": deadline_utc,
        "deadline": {
            "network": network_code,
            "dueDate": str(deadline_utc).split("T")[0],
            "daysRemaining": 0,
        },
        "createdAt": created_at,
        "updatedAt": created_at,
        "metadata": dict(body.get("metadata") or {}),
        "degradedMode": True,
    }


def _handle_create_dispute(body: dict[str, Any]) -> func.HttpResponse:
    """
    Core dispute-creation logic, extracted for testability.

    Portal-friendly relaxations vs. the raw pipeline endpoint:
      - ``reasonCode``        optional — defaults to ``"unknown"`` (AI agent maps it).
      - ``deadlineUtc``       optional — auto-calculated from network SLA rules.
      - ``disputeDescription`` optional — free-text customer reason; stored in metadata.
    """
    required_fields = [
        "networkCode", "cardholderName", "cardLastFour",
        "transactionAmount", "transactionDate", "merchantName",
    ]
    missing = [f for f in required_fields if f not in body]
    if missing:
        return func.HttpResponse(
            json.dumps({"error": f"Missing required fields: {missing}"}),
            status_code=400,
            mimetype="application/json",
        )

    metadata: dict[str, Any] = dict(body.get("metadata") or {})
    if "disputeDescription" in body:
        metadata["disputeDescription"] = body["disputeDescription"]
    result = intake_dispute_record(
        {
            **body,
            "reasonCode": body.get("reasonCode", "unknown"),
            "metadata": metadata,
            "sourceSystem": body.get("sourceSystem", "portal_api"),
        },
        source_system=body.get("sourceSystem", "portal_api"),
        allow_reason_code_default=True,
    )
    if result["outcome"] == "duplicate":
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Duplicate dispute intake",
                    "disputeId": result["disputeId"],
                    "networkCode": result["networkCode"],
                    "status": result["status"],
                }
            ),
            status_code=409,
            mimetype="application/json",
        )
    if result["outcome"] != "created":
        return func.HttpResponse(
            json.dumps({"error": f"Missing required fields: {result.get('missing', [])}"}),
            status_code=400,
            mimetype="application/json",
        )

    created = result["dispute"]
    logging.info("Dispute %s created for %s", created["disputeId"], created["networkCode"])

    # Attach evidence checklist from reason-code engine
    reason_code = created.get("reasonCode", "")
    network = created.get("networkCode", "")
    from services.reason_code_engine import parse_reason_code_string as _parse_rc
    parsed_net, parsed_code = _parse_rc(reason_code)
    effective_network = parsed_net if parsed_net != "unknown" else network
    detail = get_reason_code_detail(effective_network, parsed_code)
    if detail:
        created["reasonCodeDetail"] = {
            "description": detail["description"],
            "category": detail["category"],
            "categoryLabel": detail["categoryLabel"],
            "winRate": detail["winRate"],
            "timeLimitDays": detail["timeLimitDays"],
            "evidenceChecklist": detail["evidenceRequired"],
        }
        # Emit initial score_generated event so the portal timeline reflects the
        # reason-code win-rate as the first AI risk estimate for this dispute.
        try:
            from cosmos_models import new_timeline_event as _new_tl
            win_rate = detail["winRate"]
            cosmos_client.create_timeline_event(
                _new_tl(
                    dispute_id=created["disputeId"],
                    event_type="score_generated",
                    actor="reason_code_engine",
                    detail=(
                        f"Initial win-probability estimate from reason-code engine — "
                        f"{win_rate:.0%} ({detail['category']})."
                    ),
                    data={
                        "score": win_rate,
                        "category": detail["category"],
                        "source": "reason_code_engine",
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            logging.warning(
                "[create_dispute] score_generated timeline event failed — id=%s exc=%s",
                created.get("disputeId"), exc,
            )

    return func.HttpResponse(
        json.dumps(created, default=str),
        status_code=201,
        mimetype="application/json",
    )


def _handle_get_dispute(dispute_id: str, network_code: str | None) -> func.HttpResponse:
    """
    Core dispute-retrieval logic, extracted for testability.

    When ``network_code`` is supplied, uses a fast partition-key point-read.
    When omitted (portal confirmation flow), falls back to a cross-partition
    query — adequate for single-item lookups by the portal.
    """
    try:
        if network_code:
            dispute = cosmos_client.get_dispute(dispute_id, network_code)
        else:
            results = cosmos_client.query_disputes(
                "SELECT * FROM c WHERE c.id = @id",
                parameters=[{"name": "@id", "value": dispute_id}],
                max_items=1,
            )
            dispute = results[0] if results else None
    except Exception as exc:  # noqa: BLE001
        logging.warning("Dispute lookup failed for %s: %s", dispute_id, exc)
        dispute = get_runtime_case(dispute_id) if ALLOW_DEMO_FALLBACK else None

    if not dispute and ALLOW_DEMO_FALLBACK:
        dispute = get_runtime_case(dispute_id)

    if not dispute:
        return func.HttpResponse(
            json.dumps({"error": "Dispute not found"}),
            status_code=404,
            mimetype="application/json",
        )

    return func.HttpResponse(
        json.dumps(dispute, default=str),
        status_code=200,
        mimetype="application/json",
    )


@app.route(route="disputes/customer/{customer_id}", methods=["GET"])
def list_disputes_for_customer(req: func.HttpRequest) -> func.HttpResponse:
    """
    List disputes filed by a customer for the customer portal.

    Matches by either:
      1) metadata.customerId (preferred)
      2) cardholderName (fallback for older records)

    Query params:
      cardholderName  — optional fallback name filter
      cardLastFour    — optional fallback card suffix filter
      includeClosed   — optional boolean (default true)
    """
    customer_id = (req.route_params.get("customer_id") or "").strip()
    cardholder_name = (req.params.get("cardholderName") or "").strip()
    card_last_four = (req.params.get("cardLastFour") or "").strip()
    include_closed_raw = (req.params.get("includeClosed") or "true").strip().lower()
    include_closed = include_closed_raw not in {"false", "0", "no"}

    if not customer_id and not cardholder_name and not card_last_four:
        return func.HttpResponse(
            json.dumps({"error": "customer_id path parameter or cardholderName/cardLastFour query parameter is required"}),
            status_code=400,
            mimetype="application/json",
        )

    where_clauses = []
    parameters: list[dict[str, Any]] = []

    if customer_id:
        where_clauses.append("(IS_DEFINED(c.metadata.customerId) AND c.metadata.customerId = @customerId)")
        parameters.append({"name": "@customerId", "value": customer_id})

    if cardholder_name:
        where_clauses.append("(IS_DEFINED(c.cardholderName) AND LOWER(c.cardholderName) = LOWER(@cardholderName))")
        parameters.append({"name": "@cardholderName", "value": cardholder_name})

    if card_last_four:
        where_clauses.append("(IS_DEFINED(c.cardLastFour) AND c.cardLastFour = @cardLastFour)")
        parameters.append({"name": "@cardLastFour", "value": card_last_four})

    where_expr = " OR ".join(where_clauses)
    status_filter = ""
    if not include_closed:
        status_filter = " AND c.status NOT IN ('approved', 'denied', 'submitted', 'closed', 'expired')"

    query = f"""
        SELECT *
        FROM c
        WHERE ({where_expr}){status_filter}
        ORDER BY c.createdAt DESC
    """

    try:
        disputes = cosmos_client.query_disputes(query, parameters=parameters, max_items=500)
    except Exception as exc:  # noqa: BLE001
        logging.warning(
            "Customer disputes lookup failed for %s: %s",
            customer_id or cardholder_name or card_last_four,
            exc,
        )
        if not ALLOW_DEMO_FALLBACK:
            return func.HttpResponse(
                json.dumps({"error": "Persistent dispute lookup is currently unavailable."}),
                status_code=503,
                mimetype="application/json",
            )
        disputes = list_runtime_cases_for_customer(
            customer_id=customer_id,
            cardholder_name=cardholder_name,
            card_last_four=card_last_four,
            include_closed=include_closed,
        )
    return func.HttpResponse(
        json.dumps({"disputes": disputes, "total": len(disputes)}, default=str),
        status_code=200,
        mimetype="application/json",
    )


@app.route(route="disputes", methods=["POST"])
def create_dispute(req: func.HttpRequest) -> func.HttpResponse:
    """Intake a new dispute case — creates the dispute document and an intake timeline event."""
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON body"}),
            status_code=400,
            mimetype="application/json",
        )
    try:
        return _handle_create_dispute(body)
    except Exception as exc:  # noqa: BLE001
        logging.exception("Dispute creation failed: %s", exc)
        if not ALLOW_DEMO_FALLBACK:
            return func.HttpResponse(
                json.dumps({"error": "Persistent dispute creation failed. Please retry once storage connectivity is restored."}),
                status_code=503,
                mimetype="application/json",
            )
        degraded = _build_degraded_dispute_response(body)
        register_runtime_case(degraded)
        return func.HttpResponse(
            json.dumps(degraded, default=str),
            status_code=201,
            mimetype="application/json",
        )


@app.route(route="disputes/{dispute_id}", methods=["GET"])
def get_dispute(req: func.HttpRequest) -> func.HttpResponse:
    """
    Retrieve a dispute case by ID.

    ``networkCode`` query param is optional: if provided, uses a fast partition-key
    point-read; if omitted (e.g. portal confirmation page), falls back to a
    cross-partition query so the caller need not track it.
    """
    dispute_id = req.route_params.get("dispute_id")
    network_code = req.params.get("networkCode") or None
    return _handle_get_dispute(dispute_id, network_code)


@app.route(route="disputes/{dispute_id}/evidence", methods=["GET"])
def get_evidence(req: func.HttpRequest) -> func.HttpResponse:
    """Retrieve all evidence items for a dispute."""
    dispute_id = req.route_params.get("dispute_id")
    try:
        items = cosmos_client.get_evidence_for_dispute(dispute_id)
    except Exception as exc:  # noqa: BLE001
        logging.warning("Evidence lookup failed for %s: %s", dispute_id, exc)
        items = []
    items = _rewrite_evidence_document_links(dispute_id, items)

    return func.HttpResponse(
        json.dumps(items, default=str),
        status_code=200,
        mimetype="application/json",
    )


@app.route(route="disputes/{dispute_id}/timeline", methods=["GET"])
def get_timeline(req: func.HttpRequest) -> func.HttpResponse:
    """Retrieve the full timeline for a dispute."""
    dispute_id = req.route_params.get("dispute_id")
    raw_events = _ensure_foundational_timeline(dispute_id)
    events = [_normalize_timeline_event(ev) for ev in raw_events]

    return func.HttpResponse(
        json.dumps(events, default=str),
        status_code=200,
        mimetype="application/json",
    )


@app.route(route="cases/{case_id}/timeline", methods=["GET"])
def get_case_timeline(req: func.HttpRequest) -> func.HttpResponse:
    """Compatibility endpoint for analyst portal clients expecting /cases/{id}/timeline."""
    case_id = req.route_params.get("case_id")
    raw_events = _ensure_foundational_timeline(case_id)
    events = [_normalize_timeline_event(ev) for ev in raw_events]
    return func.HttpResponse(
        json.dumps({"caseId": case_id, "events": events}, default=str),
        status_code=200,
        mimetype="application/json",
    )


@app.route(route="disputes/{dispute_id}/customer-response", methods=["POST"])
def post_customer_response(req: func.HttpRequest) -> func.HttpResponse:
    """Persist a customer message/update for a dispute so analyst + AI can reference it."""
    dispute_id = req.route_params.get("dispute_id")

    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON body"}),
            status_code=400,
            mimetype="application/json",
        )

    comment = (body.get("comment") or "").strip()
    if not comment:
        return func.HttpResponse(
            json.dumps({"error": "comment is required"}),
            status_code=400,
            mimetype="application/json",
        )

    # Validate dispute exists via id lookup across partitions.
    results = cosmos_client.query_disputes(
        "SELECT * FROM c WHERE c.id = @id",
        parameters=[{"name": "@id", "value": dispute_id}],
        max_items=1,
    )
    if not results:
        return func.HttpResponse(
            json.dumps({"error": "Dispute not found"}),
            status_code=404,
            mimetype="application/json",
        )

    customer_id = (body.get("customerId") or "customer").strip() or "customer"
    attachment_document_ids = body.get("attachmentDocumentIds") or []
    if not isinstance(attachment_document_ids, list):
        attachment_document_ids = []

    # Persist the customer note as a text artifact so it is blob-backed and AI-analyzed.
    try:
        artifact_name = f"customer-response-{dispute_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.txt"
        upload_document(
            case_id=dispute_id,
            filename=artifact_name,
            content_type="text/plain",
            file_bytes=comment.encode("utf-8"),
            submitted_by=customer_id,
            submitted_from="customer_portal",
            note="Customer response note artifact",
        )
    except Exception as exc:  # noqa: BLE001
        logging.warning("Customer response artifact save failed for %s: %s", dispute_id, exc)

    from cosmos_models import new_timeline_event

    event = new_timeline_event(
        dispute_id=dispute_id,
        event_type="customer_response",
        actor="customer",
        detail=comment,
        data={
            "customerId": customer_id,
            "attachmentDocumentIds": attachment_document_ids,
        },
    )
    cosmos_client.create_timeline_event(event)
    cosmos_client.touch_dispute_activity(
        dispute_id,
        event_type="customer_response",
        actor="customer",
        detail=comment,
        occurred_at=event.get("occurredAt"),
    )

    return func.HttpResponse(
        json.dumps({"status": "recorded", "disputeId": dispute_id, "eventId": event.get("eventId")}),
        status_code=201,
        mimetype="application/json",
    )


@app.route(route="disputes/{dispute_id}/cancel", methods=["POST"])
def cancel_dispute(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/disputes/{dispute_id}/cancel

    Customer-initiated cancellation of an in-flight dispute.
    Only allowed for cases that have not yet been actioned by the network
    (i.e. status NOT IN approved/denied/submitted/closed/expired).

    Body: { "customerId": "<string>", "reason": "<string, optional>" }
    Response 200: { "disputeId": "...", "status": "closed" }
    Response 400: already in a terminal state
    Response 404: dispute not found
    """
    dispute_id = (req.route_params.get("dispute_id") or "").strip()
    if not dispute_id:
        return func.HttpResponse(
            json.dumps({"error": "dispute_id path parameter is required"}),
            status_code=400,
            mimetype="application/json",
        )

    try:
        body = req.get_json()
    except ValueError:
        body = {}

    customer_id = str(body.get("customerId") or "customer").strip() or "customer"
    reason = str(body.get("reason") or "Customer requested cancellation").strip()

    # Look up the dispute (cross-partition for customer portal)
    results = cosmos_client.query_disputes(
        "SELECT * FROM c WHERE c.id = @id",
        parameters=[{"name": "@id", "value": dispute_id}],
        max_items=1,
    )
    if not results:
        return func.HttpResponse(
            json.dumps({"error": "Dispute not found"}),
            status_code=404,
            mimetype="application/json",
        )

    dispute = results[0]
    terminal_statuses = {"approved", "denied", "submitted", "closed", "expired"}
    current_status = (dispute.get("status") or "").lower()
    if current_status in terminal_statuses:
        return func.HttpResponse(
            json.dumps({
                "error": f"Dispute cannot be cancelled — it is already in a terminal state: {current_status}",
                "status": current_status,
            }),
            status_code=400,
            mimetype="application/json",
        )

    network_code = dispute.get("networkCode") or dispute.get("network_code") or ""
    try:
        cosmos_client.update_dispute_status(dispute_id, network_code, "closed")
    except Exception as exc:  # noqa: BLE001
        logging.warning("[cancel_dispute] status update failed — id=%s exc=%s", dispute_id, exc)

    from cosmos_models import new_timeline_event as _new_tl

    event = _new_tl(
        dispute_id=dispute_id,
        event_type="customer_cancellation",
        actor=customer_id,
        detail=reason,
        data={"customerId": customer_id, "previousStatus": current_status},
    )
    try:
        cosmos_client.create_timeline_event(event)
        cosmos_client.touch_dispute_activity(
            dispute_id,
            event_type="customer_cancellation",
            actor=customer_id,
            detail=reason,
            occurred_at=event.get("occurredAt"),
        )
    except Exception as exc:  # noqa: BLE001
        logging.warning("[cancel_dispute] timeline persist failed — id=%s exc=%s", dispute_id, exc)

    logging.info("[cancel_dispute] dispute cancelled — id=%s by=%s", dispute_id, customer_id)
    return func.HttpResponse(
        json.dumps({"disputeId": dispute_id, "status": "closed"}),
        status_code=200,
        mimetype="application/json",
    )


# ── Reason Code Engine Endpoints ──────────────────────────────────────────────


@app.route(route="reason-codes", methods=["GET"])
def list_reason_codes(req: func.HttpRequest) -> func.HttpResponse:
    """
    GET /api/reason-codes[?network=<network>]

    Without network param: returns all networks with their code counts.
    With network param: returns all reason codes for that network.
    """
    network = req.params.get("network")
    if network:
        codes = get_reason_codes_for_network(network)
        if not codes:
            return func.HttpResponse(
                json.dumps({"error": f"Unknown network: {network}"}),
                status_code=404,
                mimetype="application/json",
            )
        return func.HttpResponse(
            json.dumps({"network": network.lower(), "reasonCodes": codes, "total": len(codes)}),
            status_code=200,
            mimetype="application/json",
        )

    # Return summary of all networks
    networks = []
    for net in get_supported_networks():
        codes = get_reason_codes_for_network(net)
        networks.append({"network": net, "codeCount": len(codes)})
    return func.HttpResponse(
        json.dumps({"networks": networks}),
        status_code=200,
        mimetype="application/json",
    )


@app.route(route="reason-codes/{network}/{code}", methods=["GET"])
def get_reason_code(req: func.HttpRequest) -> func.HttpResponse:
    """
    GET /api/reason-codes/{network}/{code}

    Returns full detail for a specific reason code including evidence requirements.
    """
    network = req.route_params.get("network", "")
    code = req.route_params.get("code", "")

    detail = get_reason_code_detail(network, code)
    if not detail:
        return func.HttpResponse(
            json.dumps({"error": f"Reason code '{code}' not found for network '{network}'"}),
            status_code=404,
            mimetype="application/json",
        )
    return func.HttpResponse(
        json.dumps(detail),
        status_code=200,
        mimetype="application/json",
    )


@app.route(route="reason-codes/{network}/{code}/checklist", methods=["GET"])
def get_reason_code_checklist(req: func.HttpRequest) -> func.HttpResponse:
    """
    GET /api/reason-codes/{network}/{code}/checklist

    Returns just the evidence checklist for a reason code.
    """
    network = req.route_params.get("network", "")
    code = req.route_params.get("code", "")

    checklist = get_evidence_checklist(network, code)
    if not checklist:
        return func.HttpResponse(
            json.dumps({"error": f"No checklist found for {network}/{code}"}),
            status_code=404,
            mimetype="application/json",
        )
    return func.HttpResponse(
        json.dumps({"network": network.lower(), "code": code, "checklist": checklist}),
        status_code=200,
        mimetype="application/json",
    )


@app.route(route="reason-codes/{network}/{code}/gaps", methods=["POST"])
def check_evidence_gaps(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/reason-codes/{network}/{code}/gaps

    Body: { "gatheredEvidenceIds": ["shipping_confirmation", "tracking_number"] }

    Returns gap analysis: what's gathered, what's missing, completion %.
    """
    network = req.route_params.get("network", "")
    code = req.route_params.get("code", "")

    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON body"}),
            status_code=400,
            mimetype="application/json",
        )

    gathered_ids = body.get("gatheredEvidenceIds", [])
    if not isinstance(gathered_ids, list):
        return func.HttpResponse(
            json.dumps({"error": "gatheredEvidenceIds must be an array"}),
            status_code=400,
            mimetype="application/json",
        )

    result = identify_evidence_gaps(network, code, gathered_ids)
    if result["totalRequired"] == 0:
        return func.HttpResponse(
            json.dumps({"error": f"No checklist found for {network}/{code}"}),
            status_code=404,
            mimetype="application/json",
        )
    return func.HttpResponse(
        json.dumps({"network": network.lower(), "code": code, **result}),
        status_code=200,
        mimetype="application/json",
    )


# ── Precedent / Rules Retrieval Endpoint (#12) ────────────────────────────────


@app.route(route="disputes/{dispute_id}/retrieve-precedents", methods=["POST"])
def retrieve_precedents(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/disputes/{dispute_id}/retrieve-precedents

    Evidence Retrieval Agent (#12): fetches relevant card-network rules,
    evidence requirements, and case precedents from Azure AI Search, grounded to
    source citations. Feeds the Maker agent (#13).

    Optional body: {"network": "visa", "reasonCode": "13.1", "topK": 5}
    When reasonCode is supplied it is used directly; otherwise the dispute is
    loaded from the case store by id.
    """
    dispute_id = req.route_params.get("dispute_id")
    try:
        body = req.get_json() if req.get_body() else {}
    except ValueError:
        body = {}

    try:
        top_k = int(body.get("topK") or 5)
    except (TypeError, ValueError):
        top_k = 5

    if body.get("reasonCode"):
        dispute = {"disputeId": dispute_id, "id": dispute_id, **body}
    else:
        network_code = body.get("networkCode") or body.get("network")
        if network_code:
            dispute = cosmos_client.get_dispute(dispute_id, network_code)
        else:
            results = cosmos_client.query_disputes(
                "SELECT * FROM c WHERE c.id = @id",
                parameters=[{"name": "@id", "value": dispute_id}],
                max_items=1,
            )
            dispute = results[0] if results else None
        if not dispute:
            return func.HttpResponse(
                json.dumps({"error": "Dispute not found"}),
                status_code=404,
                mimetype="application/json",
            )

    result = retrieve_precedents_for_dispute(dispute, top_k=top_k)

    try:
        from services.evidence_search_agent_client import ground_evidence
        result = ground_evidence(dispute, result)
    except Exception:  # noqa: BLE001 — grounding is best-effort, never block
        logging.warning("[retrieve_precedents] grounding failed", exc_info=True)

    logging.info(
        "Precedent retrieval for %s: %d result(s) (mode=%s, source=%s)",
        dispute_id,
        len(result.get("results", [])),
        result.get("matchMode"),
        result.get("source"),
    )

    return func.HttpResponse(
        json.dumps(result, default=str),
        status_code=200,
        mimetype="application/json",
    )


# ── Evidence Retrieval Endpoint ───────────────────────────────────────────────


@app.route(route="disputes/{dispute_id}/retrieve-evidence", methods=["POST"])
def retrieve_evidence(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/disputes/{dispute_id}/retrieve-evidence

    Triggers evidence retrieval for a dispute. Pulls from mock connectors
    (all 4 networks) based on the dispute's reason code.

    Optional body: { "networkCode": "visa" } to override network lookup.
    """
    dispute_id = req.route_params.get("dispute_id")
    network_code = req.params.get("networkCode") or None

    # Try body override
    try:
        body = req.get_json() if req.get_body() else {}
    except ValueError:
        body = {}

    if not network_code:
        network_code = body.get("networkCode")

    # Fetch the dispute document
    if network_code:
        dispute = cosmos_client.get_dispute(dispute_id, network_code)
    else:
        results = cosmos_client.query_disputes(
            "SELECT * FROM c WHERE c.id = @id",
            parameters=[{"name": "@id", "value": dispute_id}],
            max_items=1,
        )
        dispute = results[0] if results else None

    if not dispute:
        return func.HttpResponse(
            json.dumps({"error": "Dispute not found"}),
            status_code=404,
            mimetype="application/json",
        )

    # Run evidence retrieval
    result = retrieve_evidence_for_dispute(dispute)

    logging.info(
        "Evidence retrieval for %s: %d/%d items retrieved",
        dispute_id, result["totalRetrieved"], result["totalRequired"],
    )

    return func.HttpResponse(
        json.dumps(result, default=str),
        status_code=200,
        mimetype="application/json",
    )


# ── Maker Agent Endpoint (Issue #13) ──────────────────────────────────────────


@app.route(route="disputes/{dispute_id}/draft-rebuttal", methods=["POST"])
def draft_rebuttal_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/disputes/{dispute_id}/draft-rebuttal

    Runs the Maker agent to draft a grounded rebuttal narrative for a dispute.
    Evidence is taken from the request body when provided, otherwise it is
    auto-retrieved via the mock evidence-retrieval service. The resulting draft
    is persisted onto the dispute document as ``rebuttalDraft`` and the full
    structured maker result is returned for checker review.

    Optional query param: ``networkCode`` (fast partition-key point-read).
    Optional JSON body:
      { "networkCode": "visa", "evidence": [ ...evidenceItems... ] }
    """
    dispute_id = req.route_params.get("dispute_id")
    network_code = req.params.get("networkCode") or None

    try:
        body = req.get_json() if req.get_body() else {}
    except ValueError:
        body = {}

    if not network_code:
        network_code = body.get("networkCode")

    # Fetch the dispute document.
    if network_code:
        dispute = cosmos_client.get_dispute(dispute_id, network_code)
    else:
        results = cosmos_client.query_disputes(
            "SELECT * FROM c WHERE c.id = @id",
            parameters=[{"name": "@id", "value": dispute_id}],
            max_items=1,
        )
        dispute = results[0] if results else None

    if not dispute:
        return func.HttpResponse(
            json.dumps({"error": "Dispute not found"}),
            status_code=404,
            mimetype="application/json",
        )

    # Use supplied evidence, or auto-retrieve it via the mock connectors.
    evidence = body.get("evidence")
    if not evidence:
        retrieval = retrieve_evidence_for_dispute(dispute)
        evidence = retrieval.get("evidenceItems", [])

    result = draft_rebuttal(dispute, evidence)

    # Persist the draft onto the dispute document (best-effort).
    try:
        dispute["rebuttalDraft"] = to_rebuttal_draft(result)
        cosmos_client.upsert_dispute(dispute)
    except Exception as exc:  # noqa: BLE001
        logging.warning(
            "Rebuttal draft persistence failed for %s: %s", dispute_id, exc
        )

    logging.info(
        "Rebuttal drafted for %s: source=%s grounded=%s citations=%d",
        dispute_id, result["source"], result["grounded"], result["evidenceCited"],
    )

    return func.HttpResponse(
        json.dumps(result, default=str),
        status_code=200,
        mimetype="application/json",
    )


# ── Win-Probability & Risk Scoring Endpoint (Issue #30) ───────────────────────


@app.route(route="disputes/{dispute_id}/score", methods=["POST"])
def score_dispute_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/disputes/{dispute_id}/score

    Computes win-probability and risk assessment for a dispute from the
    reason code's historical win-rate and evidence completeness. Evidence is
    taken from the request body when provided, otherwise auto-retrieved via
    the mock evidence-retrieval service. Persists ``winProbability`` and
    ``riskLevel`` onto the dispute document.

    Optional query param: ``networkCode`` (fast partition-key point-read).
    Optional JSON body:
      { "networkCode": "visa", "evidence": [ ...evidenceItems... ] }
    """
    dispute_id = req.route_params.get("dispute_id")
    network_code = req.params.get("networkCode") or None

    try:
        body = req.get_json() if req.get_body() else {}
    except ValueError:
        body = {}

    if not network_code:
        network_code = body.get("networkCode")

    if network_code:
        dispute = cosmos_client.get_dispute(dispute_id, network_code)
    else:
        results = cosmos_client.query_disputes(
            "SELECT * FROM c WHERE c.id = @id",
            parameters=[{"name": "@id", "value": dispute_id}],
            max_items=1,
        )
        dispute = results[0] if results else None

    if not dispute:
        return func.HttpResponse(
            json.dumps({"error": "Dispute not found"}),
            status_code=404,
            mimetype="application/json",
        )

    evidence = body.get("evidence")
    if not evidence:
        retrieval = retrieve_evidence_for_dispute(dispute)
        evidence = retrieval.get("evidenceItems", [])

    result = score_case(dispute, evidence=evidence)

    try:
        dispute["winProbability"] = result["winProbability"]
        dispute["riskLevel"] = result["riskLevel"]
        cosmos_client.upsert_dispute(dispute)
    except Exception as exc:  # noqa: BLE001
        logging.warning("Score persistence failed for %s: %s", dispute_id, exc)

    try:
        from cosmos_models import new_timeline_event
        cosmos_client.create_timeline_event(
            new_timeline_event(
                dispute_id=dispute_id,
                event_type="score_generated",
                actor="scoring_service",
                detail=(
                    f"Win-probability score computed — {result['winProbability']:.0%} "
                    f"({result['riskLevel']} risk, {result['category']})."
                ),
                data={
                    "score": result["winProbability"],
                    "category": result["category"],
                    "source": "scoring_service",
                },
            )
        )
    except Exception as exc:  # noqa: BLE001
        logging.warning("Score timeline event failed for %s: %s", dispute_id, exc)

    logging.info(
        "Scored %s: winProbability=%.3f riskLevel=%s category=%s",
        dispute_id, result["winProbability"], result["riskLevel"], result["category"],
    )

    return func.HttpResponse(
        json.dumps(result, default=str),
        status_code=200,
        mimetype="application/json",
    )


# ── Completeness & Gaps Detection Endpoint (Issue #18) ────────────────────────


@app.route(route="disputes/{dispute_id}/detect-gaps", methods=["POST"])
def detect_gaps_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/disputes/{dispute_id}/detect-gaps

    Compares the reason code's required evidence checklist against retrieved
    evidence and flags gaps before the network deadline hits. Evidence is
    taken from the request body when provided, otherwise auto-retrieved via
    the mock evidence-retrieval service. Persists ``reasonCodeChecklist`` and
    ``evidenceGaps`` onto the dispute document — the shape the analyst review
    UI's EvidenceGapsPanel / ReasonCodeChecklist components already expect.

    Optional query param: ``networkCode`` (fast partition-key point-read).
    Optional JSON body:
      {
        "networkCode": "visa",
        "evidence": [ ...evidenceItems... ],
        "alertThreshold": 2   // override EVIDENCE_GAP_ALERT_THRESHOLD
      }
    """
    dispute_id = req.route_params.get("dispute_id")
    network_code = req.params.get("networkCode") or None

    try:
        body = req.get_json() if req.get_body() else {}
    except ValueError:
        body = {}

    if not network_code:
        network_code = body.get("networkCode")

    if network_code:
        dispute = cosmos_client.get_dispute(dispute_id, network_code)
    else:
        results = cosmos_client.query_disputes(
            "SELECT * FROM c WHERE c.id = @id",
            parameters=[{"name": "@id", "value": dispute_id}],
            max_items=1,
        )
        dispute = results[0] if results else None

    if not dispute:
        return func.HttpResponse(
            json.dumps({"error": "Dispute not found"}),
            status_code=404,
            mimetype="application/json",
        )

    evidence = body.get("evidence")
    if not evidence:
        retrieval = retrieve_evidence_for_dispute(dispute)
        evidence = retrieval.get("evidenceItems", [])

    alert_threshold = body.get("alertThreshold")

    result = detect_gaps(dispute, evidence=evidence, alert_threshold=alert_threshold)

    try:
        dispute["reasonCodeChecklist"] = result["reasonCodeChecklist"]
        dispute["evidenceGaps"] = result["evidenceGaps"]
        cosmos_client.upsert_dispute(dispute)
    except Exception as exc:  # noqa: BLE001
        logging.warning("Gap detection persistence failed for %s: %s", dispute_id, exc)

    logging.info(
        "Gaps detected for %s: missingRequired=%d/%d alertTriggered=%s",
        dispute_id, result["missingRequiredCount"], result["alertThreshold"], result["alertTriggered"],
    )

    return func.HttpResponse(
        json.dumps(result, default=str),
        status_code=200,
        mimetype="application/json",
    )


# ── Reprocess Endpoint — re-run the full AI pipeline on demand ───────────────


@app.route(route="disputes/{dispute_id}/reprocess", methods=["POST"])
def reprocess_dispute_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/disputes/{dispute_id}/reprocess

    Re-triggers the full AI pipeline for an existing dispute in one call:
    evidence retrieval -> gaps detection -> win-probability/risk scoring ->
    maker-agent rebuttal drafting. Useful when new evidence has arrived, a
    reason code was corrected, or an analyst simply wants fresh AI output
    without waiting for the next scheduled pipeline run.

    Persists the refreshed evidenceGaps, reasonCodeChecklist, winProbability,
    riskLevel, and rebuttalDraft onto the dispute document, and appends a
    best-effort timeline event so the reprocess shows up in the case history
    and the processing-timeline visualization.

    Optional query param: ``networkCode`` (fast partition-key point-read).
    Optional JSON body: { "networkCode": "visa", "alertThreshold": 2 }
    """
    dispute_id = req.route_params.get("dispute_id")
    network_code = req.params.get("networkCode") or None

    try:
        body = req.get_json() if req.get_body() else {}
    except ValueError:
        body = {}

    if not network_code:
        network_code = body.get("networkCode")

    if network_code:
        dispute = cosmos_client.get_dispute(dispute_id, network_code)
    else:
        results = cosmos_client.query_disputes(
            "SELECT * FROM c WHERE c.id = @id",
            parameters=[{"name": "@id", "value": dispute_id}],
            max_items=1,
        )
        dispute = results[0] if results else None

    if not dispute:
        return func.HttpResponse(
            json.dumps({"error": "Dispute not found"}),
            status_code=404,
            mimetype="application/json",
        )

    alert_threshold = body.get("alertThreshold")

    # ── Run the full pipeline ────────────────────────────────────────────────
    retrieval = retrieve_evidence_for_dispute(dispute)
    evidence = retrieval.get("evidenceItems", [])

    gaps = detect_gaps(dispute, evidence=evidence, alert_threshold=alert_threshold)
    score = score_case(dispute, evidence=evidence)
    rebuttal = draft_rebuttal(dispute, evidence)

    reprocessed_at = datetime.now(timezone.utc).isoformat()

    try:
        dispute["reasonCodeChecklist"] = gaps["reasonCodeChecklist"]
        dispute["evidenceGaps"] = gaps["evidenceGaps"]
        dispute["winProbability"] = score["winProbability"]
        dispute["riskLevel"] = score["riskLevel"]
        dispute["rebuttalDraft"] = to_rebuttal_draft(rebuttal)
        dispute["updatedAt"] = reprocessed_at
        cosmos_client.upsert_dispute(dispute)
    except Exception as exc:  # noqa: BLE001
        logging.warning("Reprocess persistence failed for %s: %s", dispute_id, exc)

    try:
        from cosmos_models import new_timeline_event
        cosmos_client.create_timeline_event(
            new_timeline_event(
                dispute_id=dispute_id,
                event_type="score_generated",
                actor="scoring_service",
                detail=(
                    f"Win-probability score recomputed — {score['winProbability']:.0%} "
                    f"({score['riskLevel']} risk, {score['category']})."
                ),
                data={"score": score["winProbability"], "category": score["category"], "source": "scoring_service"},
            )
        )
        event = new_timeline_event(
            dispute_id=dispute_id,
            event_type="ai_draft_generated",
            actor="system",
            detail=(
                f"Dispute reprocessed on demand — evidence re-retrieved "
                f"({retrieval.get('totalRetrieved', 0)}/{retrieval.get('totalRequired', 0)}), "
                f"win probability {score['winProbability']:.0%}, "
                f"risk {score['riskLevel']}, rebuttal redrafted ({rebuttal['source']})."
            ),
        )
        cosmos_client.create_timeline_event(event)
    except Exception as exc:  # noqa: BLE001
        logging.warning("Reprocess timeline event failed for %s: %s", dispute_id, exc)

    logging.info(
        "Reprocessed %s: evidence=%d/%d winProbability=%.3f riskLevel=%s rebuttalSource=%s",
        dispute_id, retrieval.get("totalRetrieved", 0), retrieval.get("totalRequired", 0),
        score["winProbability"], score["riskLevel"], rebuttal["source"],
    )

    result = {
        "disputeId": dispute_id,
        "reprocessedAt": reprocessed_at,
        "evidence": {
            "totalRetrieved": retrieval.get("totalRetrieved"),
            "totalRequired": retrieval.get("totalRequired"),
        },
        "gaps": gaps,
        "score": score,
        "rebuttal": {k: v for k, v in rebuttal.items() if k != "rawResponse"},
    }
    return func.HttpResponse(
        json.dumps(result, default=str),
        status_code=200,
        mimetype="application/json",
    )

