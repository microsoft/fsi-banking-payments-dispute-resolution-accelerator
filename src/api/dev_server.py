"""
Local development API server — Flask replacement for Azure Functions Core Tools.

Serves the same routes as the Function App (case_read + case_actions blueprints)
using the synthetic data store. Use when func CLI is unavailable (e.g. ARM64).

Usage:
    cd src/api
    python dev_server.py

Runs on http://localhost:7071 with CORS enabled (matches Vite proxy target).
"""
from __future__ import annotations

import sys
import os

# Ensure src/api is on the path so services/ imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, request
from flask_cors import CORS

from services.case_store import get_case, list_cases, update_case_status
from services.case_store import _load_all as _load_all_cases  # dev-only: in-memory demo persistence
from services.document_service import get_documents, upload_document, compute_updated_score
from services.evidence_retrieval import retrieve_evidence_for_dispute
from services.evidence_search import retrieve_precedents_for_dispute
from services.gaps_service import detect_gaps
from services.scoring_service import score_case
from services.maker_agent_client import draft_rebuttal, to_rebuttal_draft

app = Flask(__name__)
CORS(app)


# ── Timeline data (synthetic) ─────────────────────────────────────────────────

import json
from datetime import date, datetime, timezone

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
_REPO_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")


def _load_timeline_data() -> dict[str, list[dict]]:
    """Load timeline events from seed data files, grouped by disputeId/caseId."""
    timeline: dict[str, list[dict]] = {}

    # Try seed data timeline file (both src/data and repo-root data/)
    for path in [
        os.path.join(_DATA_DIR, "seed", "timeline.json"),
        os.path.join(_DATA_DIR, "seed", "demo_timeline.json"),
        os.path.join(_REPO_DATA_DIR, "seed", "timeline.json"),
        os.path.join(_REPO_DATA_DIR, "seed", "demo_timeline.json"),
    ]:
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                events = json.load(f)
            for ev in events:
                case_id = ev.get("disputeId") or ev.get("caseId", "")
                timeline.setdefault(case_id, []).append(ev)

    return timeline


_TIMELINE_STORE: dict[str, list[dict]] | None = None


# Phase progression with typical relative timing (as fraction of total elapsed)
_PHASE_PROGRESSION = {
    "intake": [],
    "evidence_gathering": [("evidence_gathering", 0.02)],
    "ai_drafting": [("evidence_gathering", 0.02), ("ai_drafting", 0.55)],
    "pending_review": [("evidence_gathering", 0.02), ("ai_drafting", 0.45), ("pending_review", 0.50)],
    "escalated": [("evidence_gathering", 0.02), ("ai_drafting", 0.35), ("pending_review", 0.40), ("escalated", 0.70)],
    "approved": [("evidence_gathering", 0.02), ("ai_drafting", 0.40), ("pending_review", 0.50), ("approved", 0.90)],
    "denied": [("evidence_gathering", 0.02), ("ai_drafting", 0.40), ("pending_review", 0.50), ("denied", 0.90)],
    "submitted": [("evidence_gathering", 0.02), ("ai_drafting", 0.35), ("pending_review", 0.45), ("approved", 0.85), ("submitted", 0.92)],
}


def _generate_synthetic_timeline(case: dict) -> list[dict]:
    """Generate synthetic timeline events from case status + createdAt for cases with no seed data."""
    status = case.get("status", "intake")
    created_str = case.get("createdAt")
    if not created_str:
        return []

    created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    total_elapsed = (now - created).total_seconds()

    phases = _PHASE_PROGRESSION.get(status, [])
    events: list[dict] = [
        {
            "eventId": f"synth-{case.get('caseId', 'x')[:8]}-000",
            "disputeId": case.get("caseId", ""),
            "eventType": "status_change",
            "actor": "system",
            "detail": "Dispute created — intake initiated",
            "data": {"fromStatus": None, "toStatus": "intake"},
            "occurredAt": created_str,
        }
    ]

    for i, (to_status, fraction) in enumerate(phases):
        ts = created + __import__("datetime").timedelta(seconds=total_elapsed * fraction)
        events.append({
            "eventId": f"synth-{case.get('caseId', 'x')[:8]}-{i+1:03d}",
            "disputeId": case.get("caseId", ""),
            "eventType": "status_change",
            "actor": "system",
            "detail": f"Status changed to {to_status}",
            "data": {"fromStatus": phases[i-1][0] if i > 0 else "intake", "toStatus": to_status},
            "occurredAt": ts.isoformat(),
        })

    return events


def _get_timeline(case_id: str) -> list[dict]:
    global _TIMELINE_STORE
    if _TIMELINE_STORE is None:
        _TIMELINE_STORE = _load_timeline_data()
    events = _TIMELINE_STORE.get(case_id, [])
    # If no seed data events, generate synthetic ones from the case record
    if not events:
        case = get_case(case_id)
        if case:
            events = _generate_synthetic_timeline(case)
            _TIMELINE_STORE[case_id] = events
    return events


# ── Health ────────────────────────────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "store": "synthetic", "server": "dev_server"})


# ── POST /api/disputes (Customer Portal submission) ───────────────────────────

@app.route("/api/disputes", methods=["POST"])
def api_create_dispute():
    """Accept a dispute from the customer portal and add it to the in-memory case store."""
    body = request.get_json(silent=True) or {}

    required_fields = [
        "networkCode", "cardholderName", "cardLastFour",
        "transactionAmount", "transactionDate", "merchantName",
    ]
    missing = [f for f in required_fields if f not in body]
    if missing:
        return jsonify({"error": f"Missing required fields: {missing}"}), 400

    import uuid
    dispute_id = f"DSP-{uuid.uuid4().hex[:8].upper()}"
    now_iso = datetime.now(timezone.utc).isoformat()

    # Compute deadline (network SLA days)
    sla_days = {"visa": 30, "mastercard": 45, "amex": 20, "discover": 30}
    network = body["networkCode"].lower()
    deadline_days = sla_days.get(network, 45)
    from datetime import timedelta
    deadline_date = (datetime.now(timezone.utc) + timedelta(days=deadline_days)).strftime("%Y-%m-%d")

    metadata = body.get("metadata") or {}

    # Build a full case record compatible with the analyst portal
    case = {
        "id": dispute_id,
        "caseId": dispute_id,
        "disputeId": dispute_id,
        "networkCode": network,
        "cardNetwork": network,
        "reasonCode": body.get("reasonCode", "unknown"),
        "status": "intake",
        "cardholderName": body["cardholderName"],
        "cardLastFour": body["cardLastFour"],
        "transactionAmount": body["transactionAmount"],
        "transactionCurrency": body.get("transactionCurrency", "USD"),
        "transactionDate": body["transactionDate"],
        "merchantName": body["merchantName"],
        "merchantCategory": metadata.get("merchantCategory", ""),
        "description": metadata.get("description", ""),
        "deadline": {
            "dueDate": deadline_date,
            "daysRemaining": deadline_days,
        },
        "deadlineUtc": deadline_date + "T23:59:59Z",
        "createdAt": now_iso,
        "updatedAt": now_iso,
        "winProbability": 0.65,
        "riskLevel": "medium",
        "sourceSystem": "portal_api",
    }

    # Insert into the in-memory store so it appears in the analyst queue
    store = _load_all_cases()
    store[dispute_id] = case

    # Persist to disk so it survives server restarts
    cases_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "synthetic", "cases")
    os.makedirs(cases_dir, exist_ok=True)
    with open(os.path.join(cases_dir, f"{dispute_id}.json"), "w", encoding="utf-8") as f:
        json.dump(case, f, indent=2, default=str)

    # Clear the case_store LRU cache so GET endpoints see the new case
    from services.case_store import _load_all
    _load_all.cache_clear()

    # Return the response expected by the customer portal
    response = {
        "id": dispute_id,
        "disputeId": dispute_id,
        "networkCode": network,
        "reasonCode": body.get("reasonCode", "unknown"),
        "status": "intake",
        "cardholderName": body["cardholderName"],
        "cardLastFour": body["cardLastFour"],
        "transactionAmount": body["transactionAmount"],
        "transactionCurrency": body.get("transactionCurrency", "USD"),
        "transactionDate": body["transactionDate"],
        "merchantName": body["merchantName"],
        "deadlineUtc": deadline_date + "T23:59:59Z",
        "createdAt": now_iso,
    }
    return jsonify(response), 201


# ── GET /api/disputes/<disputeId> (Customer Portal status check) ──────────────

@app.route("/api/disputes/<dispute_id>", methods=["GET"])
def api_get_dispute(dispute_id: str):
    """Return dispute/case detail by ID — used by the customer portal to check status."""
    case = get_case(dispute_id)
    if not case:
        return jsonify({"error": f"Dispute '{dispute_id}' not found."}), 404
    return jsonify(case)


# ── POST /api/disputes/<disputeId>/retrieve-precedents (#12) ──────────────────

@app.route("/api/disputes/<dispute_id>/retrieve-precedents", methods=["POST"])
def api_retrieve_precedents(dispute_id: str):
    body = request.get_json(silent=True) or {}
    try:
        top_k = int(body.get("topK") or 5)
    except (TypeError, ValueError):
        top_k = 5

    if body.get("reasonCode"):
        dispute = {"disputeId": dispute_id, "id": dispute_id, **body}
    else:
        case = get_case(dispute_id)
        dispute = case or {"disputeId": dispute_id, "id": dispute_id}

    result = retrieve_precedents_for_dispute(dispute, top_k=top_k)

    try:
        from services.evidence_search_agent_client import ground_evidence
        result = ground_evidence(dispute, result)
    except Exception:
        pass

    return jsonify(result)


# ── GET /api/cases ────────────────────────────────────────────────────────────

@app.route("/api/cases", methods=["GET"])
def api_list_cases():
    status_filter = request.args.get("status")
    summaries = list_cases(status_filter)
    return jsonify({"cases": summaries, "total": len(summaries)})


# ── GET /api/cases/<caseId> ───────────────────────────────────────────────────

@app.route("/api/cases/<case_id>", methods=["GET"])
def api_get_case(case_id: str):
    case = get_case(case_id)
    if case is None:
        return jsonify({"error": f"Case '{case_id}' not found."}), 404
    return jsonify(case)


# ── GET /api/cases/<caseId>/timeline ──────────────────────────────────────────

def _normalize_timeline_event(ev: dict) -> dict:
    """Normalize seed data events to match the frontend TimelineEvent interface."""
    normalized = dict(ev)
    # Map occurredAt -> timestamp if timestamp not present
    if "timestamp" not in normalized and "occurredAt" in normalized:
        normalized["timestamp"] = normalized.pop("occurredAt")
    # Map detail -> description if description not present
    if "description" not in normalized and "detail" in normalized:
        normalized["description"] = normalized.pop("detail")
    # Map data -> metadata if metadata not present
    if "metadata" not in normalized and "data" in normalized:
        normalized["metadata"] = normalized.pop("data")
    # Normalize eventType: status_change -> status_changed (frontend convention)
    if normalized.get("eventType") == "status_change":
        normalized["eventType"] = "status_changed"
    return normalized


@app.route("/api/cases/<case_id>/timeline", methods=["GET"])
def api_get_timeline(case_id: str):
    case = get_case(case_id)
    if case is None:
        return jsonify({"error": f"Case '{case_id}' not found."}), 404
    events = [_normalize_timeline_event(ev) for ev in _get_timeline(case_id)]
    return jsonify({"caseId": case_id, "events": events, "total": len(events)})


# ── POST /api/cases/<caseId>/<action> ─────────────────────────────────────────

@app.route("/api/cases/<case_id>/<action>", methods=["POST"])
def api_case_action(case_id: str, action: str):
    valid_actions = ("approve", "deny", "escalate", "reroute", "reopen")
    if action not in valid_actions:
        return jsonify({"error": f"Unknown action '{action}'"}), 400

    case = get_case(case_id)
    if case is None:
        return jsonify({"error": f"Case '{case_id}' not found."}), 404

    body = request.get_json(silent=True) or {}
    analyst_id = body.get("analystId", "")

    status_map = {
        "approve": "approved",
        "deny": "denied",
        "escalate": "escalated",
        "reroute": "pending_review",
        "reopen": "pending_review",
    }
    new_status = status_map[action]

    # Update in-memory store directly
    store = _load_all_cases()
    if case_id in store:
        store[case_id]["status"] = new_status
        store[case_id]["updatedAt"] = datetime.now(timezone.utc).isoformat()

        # Persist to disk if it's a portal-created case
        cases_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "synthetic", "cases")
        case_file = os.path.join(cases_dir, f"{case_id}.json")
        if os.path.isfile(case_file):
            with open(case_file, "w", encoding="utf-8") as f:
                json.dump(store[case_id], f, indent=2, default=str)

    # Clear cache so subsequent reads see the update
    from services.case_store import _load_all
    _load_all.cache_clear()

    return jsonify({"status": new_status, "caseId": case_id})


# ── POST /api/cases/<caseId>/documents ────────────────────────────────────────

@app.route("/api/cases/<case_id>/documents", methods=["POST"])
def api_upload_document(case_id: str):
    """Upload evidence document(s) for a case. Returns analysis + score update."""
    case = get_case(case_id)
    if case is None:
        return jsonify({"error": f"Case '{case_id}' not found."}), 404

    if "file" not in request.files:
        return jsonify({"error": "No file provided. Use multipart/form-data with field name 'file'."}), 400

    uploaded_file = request.files["file"]
    if not uploaded_file.filename:
        return jsonify({"error": "Empty filename."}), 400

    file_bytes = uploaded_file.read()
    if len(file_bytes) == 0:
        return jsonify({"error": "Empty file."}), 400

    if len(file_bytes) > 10 * 1024 * 1024:  # 10MB limit
        return jsonify({"error": "File exceeds 10MB limit."}), 413

    doc_record = upload_document(
        case_id=case_id,
        filename=uploaded_file.filename,
        content_type=uploaded_file.content_type or "application/octet-stream",
        file_bytes=file_bytes,
    )

    # Compute updated win probability
    current_win_prob = case.get("winProbability") or 0.5
    score_update = compute_updated_score(case_id, current_win_prob)

    return jsonify({
        "document": doc_record,
        "scoreUpdate": score_update,
        "message": f"Document '{uploaded_file.filename}' uploaded and analyzed.",
    }), 201


# ── GET /api/cases/<caseId>/documents ─────────────────────────────────────────

@app.route("/api/cases/<case_id>/documents", methods=["GET"])
def api_list_documents(case_id: str):
    """List all uploaded documents for a case."""
    case = get_case(case_id)
    if case is None:
        return jsonify({"error": f"Case '{case_id}' not found."}), 404

    docs = get_documents(case_id)
    return jsonify({"caseId": case_id, "documents": docs, "total": len(docs)})


# ── POST /api/disputes/<disputeId>/reprocess ──────────────────────────────────

@app.route("/api/disputes/<dispute_id>/reprocess", methods=["POST"])
def api_reprocess_dispute(dispute_id: str):
    """
    Re-run the full AI pipeline for a case on demand: evidence retrieval ->
    gaps detection -> win-probability/risk scoring -> maker-agent rebuttal
    drafting. Dev-server equivalent of the production
    /api/disputes/{id}/reprocess endpoint — mutates the in-memory synthetic
    store (best-effort, session-only) instead of writing to Cosmos, and
    appends a matching event to the in-memory timeline store so the
    Processing Timeline reflects the retrigger immediately.
    """
    case = get_case(dispute_id)
    if case is None:
        return jsonify({"error": f"Case '{dispute_id}' not found."}), 404

    body = request.get_json(silent=True) or {}
    alert_threshold = body.get("alertThreshold")

    dispute = {
        **case,
        "disputeId": case.get("caseId"),
        "networkCode": case.get("cardNetwork"),
    }

    retrieval = retrieve_evidence_for_dispute(dispute)
    evidence = retrieval.get("evidenceItems", [])

    gaps = detect_gaps(dispute, evidence=evidence, alert_threshold=alert_threshold)
    score = score_case(dispute, evidence=evidence)
    rebuttal = draft_rebuttal(dispute, evidence)

    reprocessed_at = datetime.now(timezone.utc).isoformat()

    # Best-effort in-memory update so the local demo reflects fresh results
    # for the remainder of this dev-server session (synthetic mode has no
    # durable write path — see services.case_store module docstring).
    store = _load_all_cases()
    stored = store.get(dispute_id)
    if stored is not None:
        stored["reasonCodeChecklist"] = gaps["reasonCodeChecklist"]
        stored["evidenceGaps"] = gaps["evidenceGaps"]
        stored["winProbability"] = score["winProbability"]
        stored["riskLevel"] = score["riskLevel"]
        stored["rebuttalDraft"] = to_rebuttal_draft(rebuttal)
        stored["updatedAt"] = reprocessed_at

    score_event = {
        "eventId": f"tl-score-{dispute_id[:8]}-{int(datetime.now(timezone.utc).timestamp())}",
        "disputeId": dispute_id,
        "eventType": "score_generated",
        "timestamp": reprocessed_at,
        "actor": "scoring_service",
        "description": (
            f"Win-probability score recomputed — {score['winProbability']:.0%} "
            f"({score['riskLevel']} risk, {score['category']})."
        ),
    }
    event = {
        "eventId": f"tl-reprocess-{dispute_id[:8]}-{int(datetime.now(timezone.utc).timestamp())}",
        "disputeId": dispute_id,
        "eventType": "ai_draft_generated",
        "timestamp": reprocessed_at,
        "actor": "system",
        "description": (
            f"Dispute reprocessed on demand — evidence re-retrieved "
            f"({retrieval.get('totalRetrieved', 0)}/{retrieval.get('totalRequired', 0)}), "
            f"win probability {score['winProbability']:.0%}, risk {score['riskLevel']}, "
            f"rebuttal redrafted ({rebuttal['source']})."
        ),
    }
    _get_timeline(dispute_id)  # ensure the store is initialized
    if _TIMELINE_STORE is not None:
        _TIMELINE_STORE.setdefault(dispute_id, []).extend([score_event, event])

    return jsonify({
        "disputeId": dispute_id,
        "reprocessedAt": reprocessed_at,
        "evidence": {
            "totalRetrieved": retrieval.get("totalRetrieved"),
            "totalRequired": retrieval.get("totalRequired"),
        },
        "gaps": gaps,
        "score": score,
        "rebuttal": {k: v for k, v in rebuttal.items() if k != "rawResponse"},
    })


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n  Dispute API dev server")
    print(f"  Listening on http://localhost:7071")
    print(f"  Store: synthetic (src/data/synthetic/)")
    print(f"  Routes:")
    print(f"    GET  /api/health")
    print(f"    GET  /api/cases")
    print(f"    GET  /api/cases/<caseId>")
    print(f"    GET  /api/cases/<caseId>/timeline")
    print(f"    POST /api/cases/<caseId>/approve")
    print(f"    POST /api/cases/<caseId>/deny")
    print(f"    POST /api/cases/<caseId>/escalate")
    print(f"    POST /api/disputes/<disputeId>/reprocess")
    print()

    app.run(host="0.0.0.0", port=7071, debug=True)
