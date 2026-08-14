"""
Document upload, storage, and AI analysis service.

Supports two modes (controlled by AZURE_STORAGE_MODE env var):
  - "local" (default): Stores files in src/api/uploads/ directory
  - "azure": Stores in Azure Blob Storage using DefaultAzureCredential

AI analysis uses Azure Document Intelligence when AZURE_DOC_INTELLIGENCE_ENDPOINT is set.
Falls back to keyword-based heuristic analysis in local mode.

Environment Variables:
  AZURE_STORAGE_MODE          - "local" | "azure" (default: "local")
  AZURE_STORAGE_ACCOUNT_NAME  - e.g. "stdisputesdocs"
  AZURE_STORAGE_CONTAINER     - e.g. "documents" (default: "documents")
  AZURE_DOC_INTELLIGENCE_ENDPOINT - e.g. "https://<AI_SERVICES_NAME>.cognitiveservices.azure.com/"
  AZURE_DOC_INTELLIGENCE_KEY  - optional; if blank, uses DefaultAzureCredential

Team Azure Resources (rg-dev, West US 2):
  - AI Services: <AI_SERVICES_NAME> (S0, supports Document Intelligence)
  - Storage: create via portal with private endpoint (policy requires publicNetworkAccess=Disabled)
  - Subscription: <AZURE_SUBSCRIPTION_ID>
  - Tenant: <AZURE_TENANT_DOMAIN>
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, unquote

try:
    import cosmos_client
    from cosmos_models import new_evidence_item, new_timeline_event
except Exception:  # noqa: BLE001
    cosmos_client = None  # type: ignore[assignment]
    new_evidence_item = None  # type: ignore[assignment]
    new_timeline_event = None  # type: ignore[assignment]

# ── Configuration ─────────────────────────────────────────────────────────────

RUNNING_IN_AZURE = bool(os.getenv("WEBSITE_INSTANCE_ID"))
STORAGE_MODE = os.getenv("AZURE_STORAGE_MODE") or ("azure" if RUNNING_IN_AZURE else "local")
STORAGE_ACCOUNT = (
    os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
    or os.getenv("AzureWebJobsStorage__accountName")
    or "stdisputesdocs"
)
STORAGE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER", "documents")
DOC_INTEL_ENDPOINT = os.getenv("AZURE_DOC_INTELLIGENCE_ENDPOINT", "")
DOC_INTEL_KEY = os.getenv("AZURE_DOC_INTELLIGENCE_KEY", "")

LOCAL_UPLOAD_DIR = Path(__file__).parent.parent / "uploads"

# ── In-memory document store (per case) ──────────────────────────────────────

_documents: dict[str, list[dict[str, Any]]] = {}


def _safe_filename(name: str) -> str:
    return ''.join(ch if ch.isalnum() or ch in {'.', '-', '_'} else '_' for ch in name)


def _guess_content_type(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith('.json'):
        return 'application/json'
    if lower.endswith('.txt'):
        return 'text/plain; charset=utf-8'
    if lower.endswith('.pdf'):
        return 'application/pdf'
    if lower.endswith('.svg'):
        return 'image/svg+xml'
    return 'application/octet-stream'


def _coerce_float(value: Any, default: float = 0.0) -> float:
    """Parse numbers from ints/floats or common currency-formatted strings."""
    if isinstance(value, (int, float)):
        try:
            return float(value)
        except Exception:
            return default

    text = str(value or '').strip()
    if not text:
        return default
    normalized = text.replace('$', '').replace(',', '')
    try:
        return float(normalized)
    except Exception:
        return default


def _build_pdf_bytes(title: str, lines: list[str]) -> bytes:
    def esc(value: str) -> str:
        return value.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')

    content_lines = [f'({esc(title)}) Tj']
    for line in lines:
        content_lines.append('T*')
        content_lines.append(f'({esc(line[:110])}) Tj')
    stream = 'BT /F1 12 Tf 50 780 Td 14 TL ' + ' '.join(content_lines) + ' ET'
    objects = [
        '1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj',
        '2 0 obj << /Type /Pages /Count 1 /Kids [3 0 R] >> endobj',
        '3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj',
        f'4 0 obj << /Length {len(stream.encode("utf-8"))} >> stream\n{stream}\nendstream endobj',
        '5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj',
    ]

    pdf = '%PDF-1.4\n'
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf.encode('utf-8')))
        pdf += obj + '\n'
    xref_offset = len(pdf.encode('utf-8'))
    pdf += f'xref\n0 {len(objects) + 1}\n'
    pdf += '0000000000 65535 f \n'
    for offset in offsets[1:]:
        pdf += f'{offset:010d} 00000 n \n'
    pdf += f'trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF'
    return pdf.encode('utf-8')


def _build_text_lines(case: dict[str, Any], evidence: dict[str, Any]) -> list[str]:
    amount = _coerce_float(case.get('transactionAmount'), 0.0)
    return [
        f'Case ID: {case.get("caseId")}',
        f'Merchant: {case.get("merchantName")}',
        f'Cardholder: {case.get("cardholderName")}',
        f'Reason Code: {case.get("reasonCode")} {case.get("reasonCodeLabel") or ""}'.strip(),
        f'Amount: ${amount:,.2f}',
        f'Evidence Type: {evidence.get("type")}',
        f'Source System: {evidence.get("sourceSystem")}',
        f'Retrieved At: {evidence.get("retrievedAt")}',
        f'Completeness: {evidence.get("completeness")}',
        f'Original Reference: {evidence.get("contentRef")}',
    ]


def _build_json_artifact(case: dict[str, Any], evidence: dict[str, Any]) -> bytes:
    related_citations = []
    rebuttal = case.get('rebuttalDraft') or {}
    for citation in rebuttal.get('citations', []) if isinstance(rebuttal, dict) else []:
        if citation.get('evidenceId') == evidence.get('evidenceId'):
            related_citations.append(citation)

    ev_type = str(evidence.get('type') or '').lower()
    amount = _coerce_float(case.get('transactionAmount'), 0.0)
    txn_date = case.get('transactionDate')
    merchant = case.get('merchantName')

    typed_details: dict[str, Any]
    if ev_type in {'transaction'}:
        typed_details = {
            'recordType': 'processor_transaction_extract',
            'authorizationCode': f"A{str(case.get('caseId') or '')[:6].upper()}",
            'avsResult': 'Y',
            'cvvResult': 'M',
            'settlementStatus': 'captured',
        }
    elif ev_type in {'receipt', 'order'}:
        typed_details = {
            'recordType': 'merchant_order_packet',
            'orderNumber': f"ORD-{str(case.get('caseId') or '')[:8].upper()}",
            'lineItems': [
                {'sku': 'SKU-001', 'description': 'Primary purchase item', 'quantity': 1, 'amount': round(amount, 2)}
            ],
            'billingZipMatch': True,
        }
    elif ev_type in {'shipping', 'photo'}:
        typed_details = {
            'recordType': 'fulfillment_delivery_proof',
            'carrier': 'UPS',
            'trackingNumber': f"1Z{str(case.get('caseId') or '').replace('-', '')[:14].upper()}",
            'deliveryStatus': 'delivered',
            'deliveryWindow': 'front door photo captured',
        }
    elif ev_type in {'communication', 'contract'}:
        typed_details = {
            'recordType': 'customer_communication_log',
            'channel': 'email',
            'threadId': f"THR-{str(case.get('caseId') or '')[:10].upper()}",
            'lastResponseSummary': 'Customer acknowledged receipt and merchant response timeline.',
        }
    elif ev_type in {'fraud_signal', 'fraud_screening', 'device_fingerprint'}:
        typed_details = {
            'recordType': 'fraud_risk_assessment',
            'riskScore': int(round((_coerce_float(case.get('winProbability'), 0.5)) * 100)),
            'ipVelocityBucket': 'normal',
            'deviceTrust': 'known',
            'geoDistanceKm': 12,
        }
    else:
        typed_details = {
            'recordType': 'general_evidence_record',
            'notes': 'Synthetic demo evidence payload generated for analyst review.',
        }

    payload = {
        'artifactType': 'synthetic_evidence',
        'caseId': case.get('caseId'),
        'merchantName': case.get('merchantName'),
        'cardholderName': case.get('cardholderName'),
        'caseDescription': case.get('caseDescription'),
        'reasonCode': case.get('reasonCode'),
        'reasonCodeLabel': case.get('reasonCodeLabel'),
        'transactionAmount': case.get('transactionAmount'),
        'transactionDate': case.get('transactionDate'),
        'evidence': evidence,
        'evidenceDetails': typed_details,
        'network': case.get('cardNetwork'),
        'disputeReason': {
            'code': case.get('reasonCode'),
            'label': case.get('reasonCodeLabel'),
        },
        'timelineContext': {
            'disputedAt': txn_date,
            'merchantResponseWindow': case.get('deadline', {}).get('dueDate') if isinstance(case.get('deadline'), dict) else None,
            'merchantAmount': amount,
            'merchantName': merchant,
        },
        'relatedCitations': related_citations,
        'generatedAt': datetime.now(timezone.utc).isoformat(),
    }
    return json.dumps(payload, indent=2).encode('utf-8')


def _build_pdf_artifact(case: dict[str, Any], evidence: dict[str, Any], filename: str) -> bytes:
    title = f'Synthetic Evidence Artifact - {filename}'
    lines = _build_text_lines(case, evidence)
    ev_type = str(evidence.get('type') or '').lower()
    if ev_type == 'shipping':
        lines.extend([
            '',
            'Shipping Verification:',
            'Carrier: UPS',
            'Tracking Status: Delivered',
            'Delivery Timestamp: 2026-07-20T16:44:00Z',
        ])
    elif ev_type in {'receipt', 'order'}:
        lines.extend([
            '',
            'Order Packet Summary:',
            'POS Match: Verified',
            'Tax Calculation: Within expected range',
            'Signature/Capture: Present',
        ])
    elif ev_type in {'fraud_signal', 'fraud_screening', 'device_fingerprint'}:
        lines.extend([
            '',
            'Fraud Screening Snapshot:',
            'Device Trust: Known device in prior successful orders',
            'Velocity Rule: No spike in 24h window',
            'Risk Decision: Manual review recommended',
        ])
    note = case.get('caseDescription')
    if isinstance(note, str) and note.strip():
        lines.append('')
        lines.append('Customer Submission Summary:')
        lines.append(note)
    return _build_pdf_bytes(title, lines)


def _build_text_artifact(case: dict[str, Any], evidence: dict[str, Any]) -> bytes:
    lines = _build_text_lines(case, evidence)
    lines.append('')
    lines.append('Analyst Notes:')
    lines.append('Synthetic artifact generated for demo preview and downloadable evidence workflow validation.')
    return ('\n'.join(lines) + '\n').encode('utf-8')


def _resolve_synthetic_filename(evidence_id: str, evidence: dict[str, Any]) -> tuple[str, str]:
    raw_ref = str(evidence.get('contentRef') or '')
    filename = raw_ref.rsplit('/', 1)[-1] if '/' in raw_ref else ''
    if not filename:
        ev_type = str(evidence.get('type') or 'evidence').lower()
        preferred_ext = 'json' if ev_type in {'transaction', 'communication', 'fraud_signal', 'fraud_screening', 'device_fingerprint'} else 'pdf'
        filename = f'{ev_type}_{evidence_id}.{preferred_ext}'
    filename = _safe_filename(filename)
    content_type = _guess_content_type(filename)
    return filename, content_type


def _materialize_synthetic_artifact(case: dict[str, Any], evidence_id: str, evidence: dict[str, Any]) -> tuple[bytes, str, str]:
    filename, content_type = _resolve_synthetic_filename(evidence_id, evidence)
    case_id = str(case.get('caseId') or '')
    synthetic_dir = LOCAL_UPLOAD_DIR / 'synthetic' / case_id
    synthetic_dir.mkdir(parents=True, exist_ok=True)
    file_path = synthetic_dir / f'{evidence_id}_{filename}'

    if file_path.exists() and file_path.is_file():
        return file_path.read_bytes(), content_type, filename

    if content_type == 'application/json':
        data = _build_json_artifact(case, evidence)
    elif content_type == 'application/pdf':
        data = _build_pdf_artifact(case, evidence, filename)
    else:
        data = _build_text_artifact(case, evidence)

    file_path.write_bytes(data)
    return data, content_type, filename


def get_synthetic_evidence_artifact(case_id: str, evidence_id: str) -> tuple[bytes, str, str] | None:
    """Materialize a synthetic artifact for a seeded evidence item and return its bytes."""
    from services.case_store import get_case  # deferred to avoid import cycles

    case = get_case(case_id)
    if not case:
        return None
    evidence_items = case.get('evidence') or []
    evidence = next((ev for ev in evidence_items if str(ev.get('evidenceId')) == evidence_id), None)
    if not evidence:
        return None

    return _materialize_synthetic_artifact(case, evidence_id, evidence)


def ensure_case_synthetic_artifacts(case_id: str) -> dict[str, int]:
    """Pre-generate synthetic artifacts for all seeded evidence in a case."""
    from services.case_store import get_case  # deferred to avoid import cycles

    case = get_case(case_id)
    if not case:
        return {'generated': 0, 'total': 0}

    evidence_items = case.get('evidence') or []
    generated = 0
    for ev in evidence_items:
        evidence_id = str(ev.get('evidenceId') or '')
        if not evidence_id:
            continue
        try:
            _materialize_synthetic_artifact(case, evidence_id, ev)
            generated += 1
        except Exception:
            continue

    return {'generated': generated, 'total': len(evidence_items)}


def list_case_synthetic_artifacts(case_id: str) -> list[tuple[str, bytes, str, str]]:
    """Return all synthetic artifact payloads for seeded evidence in a case."""
    from services.case_store import get_case  # deferred to avoid import cycles

    case = get_case(case_id)
    if not case:
        return []

    artifacts: list[tuple[str, bytes, str, str]] = []
    evidence_items = case.get('evidence') or []
    for ev in evidence_items:
        evidence_id = str(ev.get('evidenceId') or '')
        if not evidence_id:
            continue
        try:
            data, content_type, filename = _materialize_synthetic_artifact(case, evidence_id, ev)
            artifacts.append((evidence_id, data, content_type, filename))
        except Exception:
            continue
    return artifacts


def get_documents(case_id: str) -> list[dict[str, Any]]:
    """Get all documents for a case."""
    if cosmos_client is not None:
        try:
            evidence = cosmos_client.get_evidence_for_dispute(case_id)
            docs = [
                ev for ev in evidence
                if ev.get("evidenceType") in {"document", "closure_document"} and ev.get("content") is not None
            ]
            if docs:
                return [ev["content"] for ev in docs]
        except Exception:
            pass
    return _documents.get(case_id, [])


def upload_document(
    case_id: str,
    filename: str,
    content_type: str,
    file_bytes: bytes,
    submitted_by: str = "unknown",
    submitted_from: str = "unknown",
    note: str | None = None,
) -> dict[str, Any]:
    """
    Upload a document for a case:
    1. Store the file (local or Azure Blob)
    2. Run AI analysis (Document Intelligence or heuristic)
    3. Return document metadata + analysis results
    """
    doc_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    # 1. Store the file
    blob_url = _store_file(case_id, doc_id, filename, content_type, file_bytes)

    # 2. Analyze the document
    analysis = _analyze_document(filename, content_type, file_bytes)

    # 3. Build document record
    doc_record: dict[str, Any] = {
        "documentId": doc_id,
        "caseId": case_id,
        "filename": filename,
        "contentType": content_type,
        "sizeBytes": len(file_bytes),
        "uploadedAt": timestamp,
        "submittedBy": submitted_by,
        "submittedFrom": submitted_from,
        "note": note,
        "blobUrl": blob_url,
        "analysis": analysis,
    }

    # 4. Persist in memory
    _documents.setdefault(case_id, []).append(doc_record)

    # 5. Persist evidence metadata + timeline in Cosmos for audit/AI retrieval
    if cosmos_client is not None and new_evidence_item is not None:
        try:
            evidence = new_evidence_item(
                dispute_id=case_id,
                evidence_type="document",
                source_system=submitted_from or "portal_upload",
                title=f"Uploaded document: {filename}",
                content=doc_record,
                blob_url=blob_url,
            )
            cosmos_client.create_evidence(evidence)
        except Exception:
            pass

    if cosmos_client is not None and new_timeline_event is not None:
        try:
            timeline_event = new_timeline_event(
                    dispute_id=case_id,
                    event_type="document_uploaded",
                    actor=submitted_by,
                    detail=f"Document uploaded: {filename}",
                    data={
                        "documentId": doc_id,
                        "filename": filename,
                        "sizeBytes": len(file_bytes),
                        "submittedBy": submitted_by,
                        "submittedFrom": submitted_from,
                        "note": note,
                        "blobUrl": blob_url,
                    },
                )
            cosmos_client.create_timeline_event(timeline_event)
            cosmos_client.touch_dispute_activity(
                case_id,
                event_type="document_uploaded",
                actor=submitted_by,
                detail=f"Document uploaded: {filename}",
                occurred_at=timeline_event.get("occurredAt"),
            )
        except Exception:
            pass

    return doc_record


def create_case_closure_document(
    *,
    case_id: str,
    case_data: dict[str, Any],
    disposition: str,
    analyst_id: str,
    reason: str | None,
) -> dict[str, Any]:
    """
    Create and persist a closure artifact for approved/denied disputes.

    Artifact is saved to blob under a closed/ folder and metadata is stored in
    Cosmos evidence container so it is discoverable in both portals.
    """
    if disposition not in {"approved", "denied"}:
        raise ValueError("closure artifact supported only for approved/denied dispositions")

    timestamp = datetime.now(timezone.utc).isoformat()
    doc_id = str(uuid.uuid4())
    payload = {
        "artifactType": "closure_decision",
        "caseId": case_id,
        "disposition": disposition,
        "analystId": analyst_id,
        "reason": reason or "",
        "createdAt": timestamp,
        "details": {
            "networkCode": case_data.get("networkCode") or case_data.get("cardNetwork"),
            "reasonCode": case_data.get("reasonCode"),
            "merchantName": case_data.get("merchantName"),
            "transactionAmount": case_data.get("transactionAmount"),
            "transactionDate": case_data.get("transactionDate"),
            "cardLastFour": case_data.get("cardLastFour"),
            "deadlineUtc": case_data.get("deadlineUtc"),
        },
    }

    filename = f"closure-{disposition}-{case_id}.json"
    file_bytes = json.dumps(payload, indent=2).encode("utf-8")
    blob_url = _store_file_closed(case_id, doc_id, filename, "application/json", file_bytes)

    closure_record: dict[str, Any] = {
        "documentId": doc_id,
        "caseId": case_id,
        "filename": filename,
        "contentType": "application/json",
        "sizeBytes": len(file_bytes),
        "uploadedAt": timestamp,
        "submittedBy": analyst_id,
        "submittedFrom": "analyst_portal",
        "note": f"Case {disposition} closure artifact",
        "blobUrl": blob_url,
        "analysis": {
            "method": "system_generated",
            "documentType": "closure_decision",
            "evidenceScore": 1.0,
            "recommendation": "System closure artifact for audit and customer communication.",
        },
        "closure": payload,
    }

    _documents.setdefault(case_id, []).append(closure_record)

    if cosmos_client is not None and new_evidence_item is not None:
        try:
            evidence = new_evidence_item(
                dispute_id=case_id,
                evidence_type="closure_document",
                source_system="analyst_decision",
                title=f"Closure decision artifact ({disposition})",
                content=closure_record,
                blob_url=blob_url,
            )
            cosmos_client.create_evidence(evidence)
        except Exception:
            pass

    if cosmos_client is not None and new_timeline_event is not None:
        try:
            timeline_event = new_timeline_event(
                    dispute_id=case_id,
                    event_type="case_closed_artifact_created",
                    actor=analyst_id,
                    detail=f"Closure artifact created for {disposition} decision",
                    data={
                        "documentId": doc_id,
                        "filename": filename,
                        "disposition": disposition,
                        "reason": reason or "",
                        "blobUrl": blob_url,
                    },
                )
            cosmos_client.create_timeline_event(timeline_event)
            cosmos_client.touch_dispute_activity(
                case_id,
                event_type="case_closed_artifact_created",
                actor=analyst_id,
                detail=f"Closure artifact created for {disposition} decision",
                occurred_at=timeline_event.get("occurredAt"),
            )
        except Exception:
            pass

    return closure_record


def get_document_bytes(case_id: str, document_id: str) -> tuple[bytes, str, str] | None:
    """Return document bytes, content type, and filename for a stored case document."""
    docs = get_documents(case_id)
    doc = next((d for d in docs if d.get("documentId") == document_id), None)
    if not doc:
        return None

    filename = str(doc.get("filename") or document_id)
    content_type = str(doc.get("contentType") or "application/octet-stream")
    blob_url = str(doc.get("blobUrl") or "")
    if not blob_url:
        return None

    # Local storage path (uploads/...)
    if blob_url.startswith("/uploads/"):
        rel = blob_url.removeprefix("/uploads/")
        file_path = LOCAL_UPLOAD_DIR / rel
        if not file_path.exists() or not file_path.is_file():
            return None
        return file_path.read_bytes(), content_type, filename

    # Azure blob URL (private container): download server-side with MI.
    try:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobClient
    except ImportError:
        return None

    try:
        parsed = urlparse(blob_url)
        path_parts = [p for p in parsed.path.split("/") if p]
        if len(path_parts) < 2:
            return None
        container_name = path_parts[0]
        blob_name = unquote("/".join(path_parts[1:]))
        account_url = f"{parsed.scheme}://{parsed.netloc}"

        blob_client = BlobClient(
            account_url=account_url,
            container_name=container_name,
            blob_name=blob_name,
            credential=DefaultAzureCredential(),
        )
        data = blob_client.download_blob().readall()
        return data, content_type, filename
    except Exception:
        return None


# ── Storage backends ──────────────────────────────────────────────────────────


def _store_file(
    case_id: str, doc_id: str, filename: str, content_type: str, file_bytes: bytes
) -> str:
    """Store file and return URL/path."""
    if STORAGE_MODE == "azure":
        return _store_azure_blob(case_id, doc_id, filename, content_type, file_bytes)
    else:
        return _store_local(case_id, doc_id, filename, file_bytes)


def _store_file_closed(
    case_id: str, doc_id: str, filename: str, content_type: str, file_bytes: bytes
) -> str:
    """Store closure artifacts under a dedicated closed/ path."""
    if STORAGE_MODE == "azure":
        return _store_azure_blob_closed(case_id, doc_id, filename, content_type, file_bytes)
    else:
        return _store_local_closed(case_id, doc_id, filename, file_bytes)


def _store_local(case_id: str, doc_id: str, filename: str, file_bytes: bytes) -> str:
    """Store file locally in src/api/uploads/{case_id}/.
    Falls back to in-memory-only storage if the filesystem is read-only
    (e.g. Azure Functions Flex Consumption).
    """
    safe_name = f"{doc_id}_{filename}"
    try:
        case_dir = LOCAL_UPLOAD_DIR / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        file_path = case_dir / safe_name
        file_path.write_bytes(file_bytes)
    except OSError:
        # Read-only filesystem (Azure Functions) — skip disk write,
        # metadata is still persisted in-memory by upload_document().
        pass

    return f"/uploads/{case_id}/{safe_name}"


def _store_local_closed(case_id: str, doc_id: str, filename: str, file_bytes: bytes) -> str:
    """Store closure artifacts locally in uploads/closed/{case_id}/."""
    safe_name = f"{doc_id}_{filename}"
    try:
        case_dir = LOCAL_UPLOAD_DIR / "closed" / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        file_path = case_dir / safe_name
        file_path.write_bytes(file_bytes)
    except OSError:
        pass
    return f"/uploads/closed/{case_id}/{safe_name}"


def _store_azure_blob(
    case_id: str,
    doc_id: str,
    filename: str,
    content_type: str,
    file_bytes: bytes,
) -> str:
    """
    Store file in Azure Blob Storage using DefaultAzureCredential.
    Requires: pip install azure-storage-blob azure-identity
    """
    try:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient
    except ImportError:
        raise RuntimeError(
            "azure-storage-blob and azure-identity packages required. "
            "Install with: pip install azure-storage-blob azure-identity"
        )

    credential = DefaultAzureCredential()
    account_url = f"https://{STORAGE_ACCOUNT}.blob.core.windows.net"
    blob_service = BlobServiceClient(account_url=account_url, credential=credential)
    container_client = blob_service.get_container_client(STORAGE_CONTAINER)
    try:
        container_client.create_container()
    except Exception:
        # Container likely already exists
        pass

    blob_name = f"{case_id}/{doc_id}_{filename}"
    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(file_bytes, content_type=content_type, overwrite=True)

    return blob_client.url


def _store_azure_blob_closed(
    case_id: str,
    doc_id: str,
    filename: str,
    content_type: str,
    file_bytes: bytes,
) -> str:
    """Store closure artifacts in Azure Blob under closed/{case_id}/."""
    try:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient
    except ImportError:
        raise RuntimeError(
            "azure-storage-blob and azure-identity packages required. "
            "Install with: pip install azure-storage-blob azure-identity"
        )

    credential = DefaultAzureCredential()
    account_url = f"https://{STORAGE_ACCOUNT}.blob.core.windows.net"
    blob_service = BlobServiceClient(account_url=account_url, credential=credential)
    container_client = blob_service.get_container_client(STORAGE_CONTAINER)
    try:
        container_client.create_container()
    except Exception:
        pass

    blob_name = f"closed/{case_id}/{doc_id}_{filename}"
    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(file_bytes, content_type=content_type, overwrite=True)
    return blob_client.url


# ── AI Document Analysis ──────────────────────────────────────────────────────


def _analyze_document(filename: str, content_type: str, file_bytes: bytes) -> dict[str, Any]:
    """
    Analyze document content. Uses Azure Document Intelligence if configured,
    otherwise falls back to heuristic keyword analysis.
    """
    if DOC_INTEL_ENDPOINT:
        return _analyze_with_azure_di(file_bytes, content_type)
    else:
        return _analyze_heuristic(filename, content_type, file_bytes)


def _analyze_with_azure_di(file_bytes: bytes, content_type: str) -> dict[str, Any]:
    """
    Azure Document Intelligence analysis.
    Requires: pip install azure-ai-documentintelligence azure-identity
    """
    try:
        from azure.identity import DefaultAzureCredential
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
    except ImportError:
        return _analyze_heuristic("", content_type, file_bytes)

    credential = DefaultAzureCredential()
    if DOC_INTEL_KEY:
        from azure.core.credentials import AzureKeyCredential
        credential = AzureKeyCredential(DOC_INTEL_KEY)

    client = DocumentIntelligenceClient(endpoint=DOC_INTEL_ENDPOINT, credential=credential)

    # Use prebuilt-document model for general document analysis
    poller = client.begin_analyze_document(
        "prebuilt-document",
        AnalyzeDocumentRequest(bytes_source=file_bytes),
    )
    result = poller.result()

    # Extract key-value pairs and content
    extracted_text = result.content or ""
    key_values = {}
    if result.key_value_pairs:
        for kvp in result.key_value_pairs:
            key = kvp.key.content if kvp.key else ""
            value = kvp.value.content if kvp.value else ""
            if key:
                key_values[key] = value

    # Determine document type and evidence value
    doc_type, evidence_score = _classify_document(extracted_text, key_values)

    return {
        "method": "azure_document_intelligence",
        "documentType": doc_type,
        "evidenceScore": evidence_score,
        "extractedText": extracted_text[:500],
        "keyValuePairs": key_values,
        "recommendation": _generate_recommendation(doc_type, evidence_score, key_values),
    }


def _analyze_heuristic(filename: str, content_type: str, file_bytes: bytes) -> dict[str, Any]:
    """
    Heuristic analysis based on filename and file properties.
    Used in local dev when Azure Document Intelligence is not available.
    """
    fname_lower = filename.lower()

    # Classify by filename patterns
    if any(kw in fname_lower for kw in ["receipt", "invoice", "transaction"]):
        doc_type = "transaction_receipt"
        evidence_score = 0.8
        checklist_items = ["transaction_evidence"]
    elif any(kw in fname_lower for kw in ["terminal", "log", "pos"]):
        doc_type = "terminal_log"
        evidence_score = 0.9
        checklist_items = ["terminal_transaction_log"]
    elif any(kw in fname_lower for kw in ["delivery", "tracking", "shipping", "signed"]):
        doc_type = "delivery_proof"
        evidence_score = 0.85
        checklist_items = ["delivery_confirmation"]
    elif any(kw in fname_lower for kw in ["refund", "credit", "reversal"]):
        doc_type = "refund_evidence"
        evidence_score = 0.75
        checklist_items = ["refund_documentation"]
    elif any(kw in fname_lower for kw in ["auth", "signature", "consent", "agreement"]):
        doc_type = "authorization_proof"
        evidence_score = 0.85
        checklist_items = ["cardholder_authorization"]
    elif any(kw in fname_lower for kw in ["duplicate", "dup"]):
        doc_type = "duplicate_transaction_evidence"
        evidence_score = 0.9
        checklist_items = ["duplicate_transaction_evidence"]
    elif "image" in content_type:
        doc_type = "photo_evidence"
        evidence_score = 0.6
        checklist_items = ["supplemental_evidence"]
    else:
        doc_type = "general_document"
        evidence_score = 0.5
        checklist_items = ["supplemental_evidence"]

    # Adjust score based on file size (very small files are likely not useful)
    if len(file_bytes) < 1024:
        evidence_score *= 0.5

    return {
        "method": "heuristic",
        "documentType": doc_type,
        "evidenceScore": round(evidence_score, 2),
        "checklistItemsSatisfied": checklist_items,
        "recommendation": _generate_recommendation(doc_type, evidence_score, {}),
        "note": "Analyzed using filename heuristics. Connect Azure Document Intelligence for OCR-based analysis.",
    }


# ── Helpers ───────────────────────────────────────────────────────────────────


def _classify_document(text: str, key_values: dict) -> tuple[str, float]:
    """Classify document type and assign evidence score from extracted content."""
    text_lower = text.lower()

    if any(kw in text_lower for kw in ["terminal", "pos", "transaction log", "batch"]):
        return "terminal_log", 0.9
    elif any(kw in text_lower for kw in ["delivery", "tracking", "shipped", "signed"]):
        return "delivery_proof", 0.85
    elif any(kw in text_lower for kw in ["receipt", "invoice", "total", "subtotal"]):
        return "transaction_receipt", 0.8
    elif any(kw in text_lower for kw in ["refund", "credit", "reversal"]):
        return "refund_evidence", 0.75
    elif any(kw in text_lower for kw in ["authorize", "signature", "consent"]):
        return "authorization_proof", 0.85
    else:
        return "general_document", 0.5


def _generate_recommendation(doc_type: str, score: float, key_values: dict) -> str:
    """Generate human-readable recommendation based on analysis."""
    recommendations = {
        "terminal_log": "Strong evidence. Terminal transaction log supports the merchant's case. Recommend updating win probability upward.",
        "delivery_proof": "Delivery confirmation found. This directly addresses 'merchandise not received' claims. Recommend approval.",
        "transaction_receipt": "Transaction receipt validates the disputed charge. Supports case resolution.",
        "refund_evidence": "Refund/credit documentation found. Verify the refund was processed and update case status.",
        "authorization_proof": "Cardholder authorization evidence found. Strongly supports merchant position.",
        "duplicate_transaction_evidence": "Duplicate transaction evidence supports the dispute claim. Recommend reviewing for credit.",
        "photo_evidence": "Photo evidence uploaded. Manual review recommended to assess relevance.",
        "general_document": "Document type unclear. Manual review recommended to determine evidentiary value.",
    }
    base = recommendations.get(doc_type, "Review document manually.")

    if score >= 0.8:
        return f"✅ HIGH VALUE — {base}"
    elif score >= 0.6:
        return f"⚠️ MODERATE VALUE — {base}"
    else:
        return f"📋 LOW VALUE — {base}"


def compute_updated_score(case_id: str, current_win_prob: float) -> dict[str, Any]:
    """
    Compute updated win probability based on all documents for a case.
    Called after upload to recommend score adjustments.
    """
    docs = get_documents(case_id)
    if not docs:
        return {"adjustedWinProbability": current_win_prob, "adjustment": 0, "reason": "No documents"}

    # Average evidence scores, weighted by recency
    total_boost = 0.0
    for doc in docs:
        analysis = doc.get("analysis", {})
        score = analysis.get("evidenceScore", 0.5)
        # Each strong document boosts win probability by up to 5%
        boost = (score - 0.5) * 0.10  # range: -5% to +4%
        total_boost += boost

    # Cap total boost at ±15%
    total_boost = max(-0.15, min(0.15, total_boost))
    new_prob = max(0.05, min(0.95, current_win_prob + total_boost))

    return {
        "adjustedWinProbability": round(new_prob, 2),
        "adjustment": round(total_boost, 3),
        "reason": f"Based on {len(docs)} document(s) with avg evidence quality",
        "documentsAnalyzed": len(docs),
    }
