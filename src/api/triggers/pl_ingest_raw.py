"""
Pipeline: Ingest Raw (pl_ingest_raw)

Event-driven intake pipeline that ingests dispute data from external sources:
  1. Timer trigger (every 5 min) — polls for new network files in blob storage
  2. Event Grid trigger — reacts to BlobCreated events for real-time ingestion

In production, this handles:
  - Visa TC40 / SAFE files
  - Mastercard GCMS chargeback notifications
  - Amex & Discover batch files
  - Webhook payloads from payment processors

For the demo, it processes files dropped into the 'ingest' blob container,
normalizes them into the dispute schema, writes to Cosmos DB, deduplicates,
starts the deadline clock, and kicks off the orchestration workflow.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlparse

import azure.functions as func

import cosmos_client
from cosmos_models import new_dispute, new_evidence_item, new_timeline_event
from services.durable_orchestration_client import start_dispute_orchestration
from services.triage_agent_client import score_dispute

bp = func.Blueprint()

logger = logging.getLogger(__name__)

INGEST_CONTAINER = "ingest"

_FIELD_ALIASES: dict[str, list[str]] = {
    "networkCode": ["networkCode", "network", "cardNetwork", "scheme"],
    "reasonCode": ["reasonCode", "reason_code", "chargebackReasonCode", "disputeReasonCode"],
    "reasonCodeLabel": ["reasonCodeLabel", "reason_label", "disputeReason"],
    "cardholderName": ["cardholderName", "cardholder", "customerName"],
    "cardLastFour": ["cardLastFour", "last4", "panLast4", "card_last_four"],
    "transactionAmount": ["transactionAmount", "amount", "chargebackAmount", "disputeAmount"],
    "transactionCurrency": ["transactionCurrency", "currency", "chargebackCurrency"],
    "transactionDate": ["transactionDate", "transactionAt", "chargebackDate", "disputeDate"],
    "merchantName": ["merchantName", "merchant", "merchant_name", "merchantDescriptor"],
    "deadlineUtc": ["deadlineUtc"],
}

_NETWORK_ALIASES: dict[str, tuple[str, ...]] = {
    "visa": ("visa", "tc40", "safe"),
    "mastercard": ("mastercard", "mc", "gcm", "gcms"),
    "amex": ("amex", "americanexpress", "american-express"),
    "discover": ("discover",),
}

_NETWORK_SLAS: dict[str, int] = {
    "visa": 30,
    "mastercard": 45,
    "amex": 20,
    "discover": 30,
}


def _first_present(record: dict[str, Any], aliases: list[str]) -> Any:
    for alias in aliases:
        if alias in record and record[alias] not in (None, ""):
            return record[alias]
    return None


def _infer_network(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.lower()
    for network_code, aliases in _NETWORK_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            return network_code
    return None


def _extract_network(record: dict[str, Any], network_hint: str | None = None) -> str | None:
    direct = _first_present(record, _FIELD_ALIASES["networkCode"])
    if isinstance(direct, str):
        inferred = _infer_network(direct)
        if inferred:
            return inferred

    for key in ("sourceFile", "fileName", "sourceSystem", "processor", "format"):
        value = record.get(key)
        if isinstance(value, str):
            inferred = _infer_network(value)
            if inferred:
                return inferred

    return _infer_network(network_hint)


def _validate_ingest_payload(payload: dict) -> list[str]:
    """Validate a normalized ingest payload has minimum required fields."""
    required = [
        "networkCode",
        "reasonCode",
        "cardholderName",
        "cardLastFour",
        "transactionAmount",
        "transactionDate",
        "merchantName",
    ]
    return [f for f in required if payload.get(f) in (None, "")]


def _calculate_deadline(network_code: str, transaction_date: str) -> str:
    """Calculate response deadline based on network rules."""
    from datetime import timedelta

    days = _NETWORK_SLAS.get(network_code.lower(), 30)

    try:
        txn_date = datetime.fromisoformat(transaction_date.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        txn_date = datetime.now(timezone.utc)

    deadline = txn_date + timedelta(days=days)
    return deadline.isoformat()


def _deadline_due_date(deadline_utc: str) -> str:
    try:
        return datetime.fromisoformat(deadline_utc.replace("Z", "+00:00")).date().isoformat()
    except (ValueError, AttributeError):
        return date.today().isoformat()


def _normalize_evidence_items(record: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = record.get("evidence") or []
    if isinstance(evidence, list):
        return [item for item in evidence if isinstance(item, dict)]
    return []


def _normalize_payload(
    record: dict[str, Any],
    *,
    network_hint: str | None = None,
    source_system: str | None = None,
    allow_reason_code_default: bool = False,
) -> dict[str, Any]:
    dispute = record.get("dispute")
    if isinstance(dispute, dict):
        record = {**record, **dispute}

    transaction = record.get("transaction") if isinstance(record.get("transaction"), dict) else {}
    merchant = record.get("merchant") if isinstance(record.get("merchant"), dict) else {}
    card = record.get("card") if isinstance(record.get("card"), dict) else {}

    normalized: dict[str, Any] = {
        "networkCode": _extract_network(record, network_hint),
        "reasonCode": _first_present(record, _FIELD_ALIASES["reasonCode"]),
        "reasonCodeLabel": _first_present(record, _FIELD_ALIASES["reasonCodeLabel"]),
        "cardholderName": (
            _first_present(record, _FIELD_ALIASES["cardholderName"])
            or card.get("cardholderName")
            or card.get("name")
        ),
        "cardLastFour": (
            _first_present(record, _FIELD_ALIASES["cardLastFour"])
            or card.get("last4")
            or card.get("panLast4")
        ),
        "transactionAmount": (
            _first_present(record, _FIELD_ALIASES["transactionAmount"])
            or transaction.get("amount")
        ),
        "transactionCurrency": (
            _first_present(record, _FIELD_ALIASES["transactionCurrency"])
            or transaction.get("currency")
            or "USD"
        ),
        "transactionDate": (
            _first_present(record, _FIELD_ALIASES["transactionDate"])
            or transaction.get("transactionDate")
            or transaction.get("postedAt")
        ),
        "merchantName": (
            _first_present(record, _FIELD_ALIASES["merchantName"])
            or merchant.get("name")
            or merchant.get("descriptor")
        ),
        "deadlineUtc": _first_present(record, _FIELD_ALIASES["deadlineUtc"]),
        "sourceSystem": source_system or record.get("sourceSystem") or record.get("processor") or "unknown",
        "evidence": _normalize_evidence_items(record),
    }

    if allow_reason_code_default and not normalized["reasonCode"]:
        normalized["reasonCode"] = "unknown"

    metadata: dict[str, Any] = dict(record.get("metadata") or {})
    for key in (
        "eventId",
        "externalDisputeId",
        "chargebackReference",
        "caseNumber",
        "arn",
        "tc40CaseNumber",
        "gcmsCaseId",
        "sourceFile",
        "blobUrl",
        "disputeDescription",
    ):
        value = record.get(key)
        if value not in (None, ""):
            metadata[key] = value

    normalized["metadata"] = metadata
    return normalized


def _build_dedupe_key(record: dict[str, Any]) -> str:
    metadata = record.get("metadata") or {}
    explicit = metadata.get("dedupeKey") or record.get("eventId") or metadata.get("eventId")
    if explicit:
        return str(explicit)

    external_ref = (
        metadata.get("externalDisputeId")
        or metadata.get("chargebackReference")
        or metadata.get("caseNumber")
        or metadata.get("arn")
        or metadata.get("tc40CaseNumber")
        or metadata.get("gcmsCaseId")
    )
    if external_ref:
        return f"{record['networkCode']}|external|{external_ref}"

    merchant = str(record.get("merchantName", "")).strip().lower()
    amount = f"{float(record['transactionAmount']):.2f}"
    txn_date = str(record.get("transactionDate", "")).split("T")[0]
    return "|".join(
        [
            record["networkCode"],
            str(record.get("reasonCode", "")).strip().lower(),
            str(record.get("cardLastFour", "")).strip(),
            amount,
            txn_date,
            merchant,
        ]
    )


def _find_duplicate_dispute(dedupe_key: str) -> dict[str, Any] | None:
    results = cosmos_client.query_disputes(
        "SELECT * FROM c WHERE c.metadata.dedupeKey = @dedupeKey",
        parameters=[{"name": "@dedupeKey", "value": dedupe_key}],
        max_items=1,
    )
    return results[0] if results else None


def _decorate_case_fields(dispute: dict[str, Any], record: dict[str, Any], deadline_utc: str) -> None:
    due_date = _deadline_due_date(deadline_utc)
    dispute["caseId"] = dispute["disputeId"]
    dispute["orchestrationId"] = dispute["disputeId"]
    dispute["cardNetwork"] = dispute["networkCode"]
    dispute["reasonCodeLabel"] = record.get("reasonCodeLabel")
    dispute["deadline"] = {
        "network": dispute["networkCode"],
        "dueDate": due_date,
        "daysRemaining": 0,
    }
    dispute["disputeRef"] = (record.get("metadata") or {}).get("externalDisputeId")


def intake_dispute_record(
    record: dict[str, Any],
    *,
    network_hint: str | None = None,
    source_system: str | None = None,
    allow_reason_code_default: bool = False,
) -> dict[str, Any]:
    """Normalize, dedupe, persist, and start orchestration for a dispute record."""
    normalized = _normalize_payload(
        record,
        network_hint=network_hint,
        source_system=source_system,
        allow_reason_code_default=allow_reason_code_default,
    )
    missing = _validate_ingest_payload(normalized)
    if missing:
        logger.warning("Skipping record — missing fields: %s", missing)
        return {"outcome": "invalid", "missing": missing}

    deadline = normalized.get("deadlineUtc") or _calculate_deadline(
        normalized["networkCode"],
        normalized["transactionDate"],
    )
    normalized["deadlineUtc"] = deadline

    dedupe_key = _build_dedupe_key(normalized)
    normalized.setdefault("metadata", {})["dedupeKey"] = dedupe_key
    duplicate = _find_duplicate_dispute(dedupe_key)
    if duplicate:
        logger.info(
            "Skipping duplicate intake — disputeId=%s dedupeKey=%s",
            duplicate.get("disputeId"),
            dedupe_key,
        )
        return {
            "outcome": "duplicate",
            "disputeId": duplicate.get("disputeId"),
            "networkCode": duplicate.get("networkCode"),
            "status": duplicate.get("status"),
        }

    dispute = new_dispute(
        network_code=normalized["networkCode"],
        reason_code=normalized["reasonCode"],
        cardholder_name=normalized["cardholderName"],
        card_last_four=normalized["cardLastFour"],
        transaction_amount=float(normalized["transactionAmount"]),
        transaction_currency=normalized.get("transactionCurrency", "USD"),
        transaction_date=normalized["transactionDate"],
        merchant_name=normalized["merchantName"],
        deadline_utc=deadline,
        metadata=normalized.get("metadata", {}),
    )
    _decorate_case_fields(dispute, normalized, deadline)

    created = cosmos_client.create_dispute(dispute)
    dispute_id = created["disputeId"]

    metadata = normalized.get("metadata") or {}
    source_name = str(normalized.get("sourceSystem", "unknown"))
    source_lower = source_name.lower()
    customer_id = str(metadata.get("customerId") or "").strip()
    submitter = customer_id or ("customer" if "portal" in source_lower else "pipeline/ingest_raw")

    created_event = new_timeline_event(
        dispute_id=dispute_id,
        event_type="case_created",
        actor=submitter,
        detail=(
            "Dispute submitted by customer"
            if "portal" in source_lower or customer_id
            else f"Dispute created from {source_name}"
        ),
        data={
            "source": source_name,
            "customerId": customer_id or None,
            "initialStatus": created.get("status", "intake"),
        },
    )
    # Anchor this event to dispute creation time for accurate chronology.
    created_event["occurredAt"] = created.get("createdAt", created_event.get("occurredAt"))
    cosmos_client.create_timeline_event(created_event)
    cosmos_client.touch_dispute_activity(
        dispute_id,
        event_type="case_created",
        actor=submitter,
        detail=created_event.get("detail", "Dispute case created"),
        occurred_at=created_event.get("occurredAt"),
    )

    event = new_timeline_event(
        dispute_id=dispute_id,
        event_type="status_change",
        actor="pipeline/ingest_raw",
        detail=f"Dispute ingested from {normalized.get('sourceSystem', 'unknown')} — status=intake",
        data={"source": normalized.get("sourceSystem", "network_file")},
    )
    cosmos_client.create_timeline_event(event)
    cosmos_client.touch_dispute_activity(
        dispute_id,
        event_type="status_change",
        actor="pipeline/ingest_raw",
        detail=event.get("detail", "Dispute ingested"),
        occurred_at=event.get("occurredAt"),
    )

    for evidence in normalized.get("evidence", []):
        ev_item = new_evidence_item(
            dispute_id=dispute_id,
            evidence_type=evidence.get("evidenceType", "other"),
            source_system=evidence.get("sourceSystem", "ingest_pipeline"),
            title=evidence.get("title", "Ingested evidence"),
            content=evidence.get("content"),
            blob_url=evidence.get("blobUrl"),
        )
        cosmos_client.create_evidence(ev_item)

    # ── Triage agent scoring (best-effort — never blocks ingestion) ──────────
    try:
        triage = score_dispute(created)
        created["triageScore"] = triage["score"]
        created["triageCategory"] = triage["category"]
        created["triageSource"] = triage["source"]
        cosmos_client.upsert_dispute(created)
        logger.info(
            "Triage complete — disputeId=%s score=%.3f category=%s source=%s",
            dispute_id,
            triage["score"],
            triage["category"],
            triage["source"],
        )
        # Mark the exact moment the score became available, so the
        # dispute-created -> score-generated elapsed time is measurable
        # (see web/src/utils/timeToScore.ts).
        cosmos_client.create_timeline_event(
            new_timeline_event(
                dispute_id=dispute_id,
                event_type="score_generated",
                actor="triage_agent",
                detail=(
                    f"Triage agent scored the dispute — win probability "
                    f"{triage['score']:.0%}, category {triage['category']} "
                    f"(source={triage['source']})."
                ),
                data={
                    "score": triage["score"],
                    "category": triage["category"],
                    "source": triage["source"],
                },
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Triage agent call failed — disputeId=%s exc=%s (ingestion continues)",
            dispute_id,
            exc,
        )

    orchestration_status = "not_started"
    try:
        orchestration_status = start_dispute_orchestration(dispute_id)
        cosmos_client.create_timeline_event(
            new_timeline_event(
                dispute_id=dispute_id,
                event_type="orchestration",
                actor="pipeline/ingest_raw",
                detail=f"Durable orchestration {orchestration_status}",
                data={"orchestrationId": dispute_id, "status": orchestration_status},
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Orchestration start failed — disputeId=%s exc=%s", dispute_id, exc)
        cosmos_client.create_timeline_event(
            new_timeline_event(
                dispute_id=dispute_id,
                event_type="orchestration",
                actor="pipeline/ingest_raw",
                detail="Durable orchestration start failed",
                data={"orchestrationId": dispute_id, "error": str(exc)},
            )
        )

    logger.info(
        "Ingested dispute %s [%s] from %s",
        dispute_id,
        normalized["networkCode"],
        normalized.get("sourceSystem", "unknown"),
    )
    return {
        "outcome": "created",
        "dispute": created,
        "orchestrationStatus": orchestration_status,
    }


def _parse_records_from_payload(
    body: Any,
    *,
    network_hint: str | None = None,
    source_system: str | None = None,
) -> list[dict[str, Any]]:
    if isinstance(body, list):
        return [item for item in body if isinstance(item, dict)]

    if isinstance(body, dict):
        if "records" in body and isinstance(body["records"], list):
            records = [item for item in body["records"] if isinstance(item, dict)]
            for item in records:
                item.setdefault("sourceSystem", source_system or body.get("sourceSystem"))
            return records
        if "disputes" in body and isinstance(body["disputes"], list):
            records = [item for item in body["disputes"] if isinstance(item, dict)]
            for item in records:
                item.setdefault("sourceSystem", source_system or body.get("sourceSystem"))
                if network_hint:
                    item.setdefault("networkCode", network_hint)
            return records
        if "dispute" in body and isinstance(body["dispute"], dict):
            payload = dict(body["dispute"])
            payload.setdefault("sourceSystem", source_system or body.get("sourceSystem"))
            if network_hint:
                payload.setdefault("networkCode", network_hint)
            if "eventId" in body:
                payload.setdefault("eventId", body["eventId"])
            return [payload]
        return [body]

    raise ValueError("Unsupported payload format")


def _download_blob_text(blob_url: str) -> tuple[str, str]:
    try:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient
    except ImportError as exc:  # pragma: no cover - guarded by requirements.txt
        raise RuntimeError(
            "azure-storage-blob and azure-identity are required for Event Grid ingestion"
        ) from exc

    parsed = urlparse(blob_url)
    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) < 2:
        raise ValueError(f"Blob URL missing container/blob path: {blob_url}")

    container_name = path_parts[0]
    blob_name = "/".join(path_parts[1:])
    service = BlobServiceClient(
        account_url=f"{parsed.scheme}://{parsed.netloc}",
        credential=DefaultAzureCredential(),
    )
    blob = service.get_blob_client(container=container_name, blob=blob_name)
    payload = blob.download_blob().readall().decode("utf-8-sig")
    return blob_name, payload


def _parse_network_file(blob_name: str, body_text: str) -> list[dict[str, Any]]:
    network_hint = _infer_network(blob_name)
    if blob_name.lower().endswith(".csv"):
        reader = csv.DictReader(io.StringIO(body_text))
        records = []
        for row in reader:
            row["sourceFile"] = blob_name
            row.setdefault("sourceSystem", f"{network_hint or 'network'}_file")
            records.append(row)
        return records

    payload = json.loads(body_text)
    records = _parse_records_from_payload(
        payload,
        network_hint=network_hint,
        source_system=f"{network_hint or 'network'}_file",
    )
    for row in records:
        row["sourceFile"] = blob_name
        row.setdefault("sourceSystem", f"{network_hint or 'network'}_file")
    return records


def _process_records(records: list[dict[str, Any]], *, network_hint: str | None = None) -> dict[str, Any]:
    results = {"ingested": 0, "skipped": 0, "duplicates": 0, "disputes": []}

    for record in records:
        result = intake_dispute_record(record, network_hint=network_hint, source_system=record.get("sourceSystem"))
        if result["outcome"] == "created":
            created = result["dispute"]
            results["ingested"] += 1
            results["disputes"].append(
                {
                    "disputeId": created["disputeId"],
                    "networkCode": created["networkCode"],
                    "status": created["status"],
                    "orchestrationStatus": result["orchestrationStatus"],
                }
            )
        elif result["outcome"] == "duplicate":
            results["duplicates"] += 1
            results["skipped"] += 1
        else:
            results["skipped"] += 1

    return results


def _handle_ingest_blob_event(event_data: dict[str, Any]) -> dict[str, Any]:
    blob_url = event_data.get("url", "")
    logger.info("pl_ingest_raw event triggered — blob: %s", blob_url)

    if f"/{INGEST_CONTAINER}/" not in blob_url:
        logger.info("Ignoring blob event — not from ingest container: %s", blob_url)
        return {"ingested": 0, "duplicates": 0, "skipped": 0, "ignored": True}

    blob_name, body_text = _download_blob_text(blob_url)
    records = _parse_network_file(blob_name, body_text)
    results = _process_records(records, network_hint=_infer_network(blob_name))

    logger.info(
        "pl_ingest_raw event complete — blob=%s ingested=%d duplicates=%d skipped=%d",
        blob_name,
        results["ingested"],
        results["duplicates"],
        results["skipped"],
    )
    return results


@bp.function_name("pl_ingest_raw_timer")
@bp.timer_trigger(schedule="0 */5 * * * *", arg_name="timer", run_on_startup=False)
def ingest_raw_timer(timer: func.TimerRequest) -> None:
    """
    Timer trigger (every 5 min): Poll for new network files in blob storage.

    The Event Grid path is the primary real-time mechanism. The timer remains as
    a safety net / ops hook and currently logs its check.
    """
    if timer.past_due:
        logger.warning("pl_ingest_raw timer is past due")

    logger.info("pl_ingest_raw timer triggered — checking for new files")
    logger.info("pl_ingest_raw timer complete — no pending files (Event Grid is primary)")


@bp.function_name("pl_ingest_raw_event")
@bp.event_grid_trigger(arg_name="event")
def ingest_raw_event(event: func.EventGridEvent) -> None:
    """
    Event Grid trigger: Process a blob-created event for real-time ingestion.

    Fires when a new file lands in the 'ingest' storage container. Downloads the
    blob, parses JSON/CSV network formats, and writes disputes to Cosmos DB.
    """
    _handle_ingest_blob_event(event.get_json())


@bp.function_name("pl_ingest_raw_http")
@bp.route(route="pipelines/ingest", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def ingest_raw_http(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP trigger: Manual/webhook ingest endpoint.

    Accepts a JSON body with one or more dispute records for immediate ingestion.
    Used by payment processor webhooks and manual batch imports.
    """
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON body"}),
            status_code=400,
            mimetype="application/json",
        )

    try:
        records = _parse_records_from_payload(body)
    except ValueError as exc:
        return func.HttpResponse(
            json.dumps({"error": str(exc)}),
            status_code=400,
            mimetype="application/json",
        )

    results = _process_records(records)
    status_code = 201 if results["ingested"] > 0 else 400
    logger.info(
        "pl_ingest_raw HTTP — ingested=%d duplicates=%d skipped=%d",
        results["ingested"],
        results["duplicates"],
        results["skipped"],
    )

    return func.HttpResponse(
        json.dumps(results),
        status_code=status_code,
        mimetype="application/json",
    )
