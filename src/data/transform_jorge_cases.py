"""
Transform Jorge's 10 curated demo cases (develop branch) into our 3-container Cosmos DB format.

Input:  origin/develop:src/data/synthetic/cases.json (flat case documents)
Output: data/seed/jorge_disputes.json, jorge_evidence.json, jorge_timeline.json

Mapping:
  - Case → disputes container doc (partition: /networkCode, /disputeId)
  - Case.evidence[] → evidence container docs (partition: /disputeId)
  - Generated timeline events → timeline container (partition: /disputeId)
"""

import json
import subprocess
import uuid
from datetime import datetime

def load_cases_from_git():
    """Load Jorge's cases.json from origin/develop branch."""
    result = subprocess.run(
        ["git", "show", "origin/develop:src/data/synthetic/cases.json"],
        capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to read from git: {result.stderr}")
    return json.loads(result.stdout)


def transform_case_to_dispute(case: dict) -> dict:
    """Extract dispute container document from a flat case."""
    dispute_id = case["caseId"]
    return {
        "id": dispute_id,
        "disputeId": dispute_id,
        "caseId": case["caseId"],
        "orchestrationId": case["orchestrationId"],
        "disputeRef": case["disputeRef"],
        "networkCode": case["cardNetwork"],
        "cardNetwork": case["cardNetwork"],
        "reasonCode": case["reasonCode"],
        "reasonCodeLabel": case["reasonCodeLabel"],
        "reasonDescription": case["reasonCodeLabel"],  # alias for backward compat
        "reasonCategory": _infer_category(case["reasonCode"], case["cardNetwork"]),
        "reasonCodeChecklist": case.get("reasonCodeChecklist", []),
        "status": case["status"],
        "cardholderName": case["cardholderName"],
        "merchantName": case["merchantName"],
        "transactionAmount": case["transactionAmount"],
        "transactionCurrency": "USD",
        "transactionDate": case["transactionDate"],
        "deadline": case.get("deadline", {}),
        "deadlineUtc": case.get("deadline", {}).get("dueDate"),
        "daysUntilDeadline": case.get("deadline", {}).get("daysRemaining"),
        "winProbability": case.get("winProbability"),
        "riskLevel": case.get("riskLevel", "medium"),
        "riskScore": _risk_level_to_score(case.get("riskLevel", "medium")),
        "evidenceCollected": len(case.get("evidence", [])),
        "evidenceGaps": case.get("evidenceGaps", []),
        "rebuttalDraft": case.get("rebuttalDraft"),
        "metadata": {"source": "jorge_curated", "version": "1.0"},
        "createdAt": case.get("createdAt"),
        "updatedAt": case.get("updatedAt"),
    }


def transform_case_to_evidence(case: dict) -> list[dict]:
    """Extract evidence container documents from a flat case."""
    dispute_id = case["caseId"]
    docs = []
    for ev in case.get("evidence", []):
        docs.append({
            "id": ev["evidenceId"],
            "evidenceId": ev["evidenceId"],
            "disputeId": dispute_id,
            "type": ev["type"],
            "evidenceType": ev["type"],  # backward compat alias
            "sourceSystem": ev["sourceSystem"],
            "retrievedAt": ev.get("retrievedAt"),
            "contentRef": ev.get("contentRef"),
            "completeness": ev.get("completeness", "complete"),
            "title": f"{ev['sourceSystem']} — {ev['type'].title()} Record",
            "content": {},  # Jorge's cases use contentRef (blob pointer) instead of inline content
            "extractedAt": ev.get("retrievedAt"),
            "metadata": {"source": "jorge_curated"},
        })
    return docs


def generate_timeline_for_case(case: dict) -> list[dict]:
    """Generate synthetic timeline events based on the case status and timestamps."""
    dispute_id = case["caseId"]
    created = case.get("createdAt", "2026-06-01T00:00:00Z")
    events = []

    # Intake event
    events.append(_timeline_event(dispute_id, "status_change", "system",
        f"Dispute created — {case['cardNetwork'].title()} {case['reasonCode']}",
        {"fromStatus": None, "toStatus": "intake"}, created))

    # Evidence gathering
    events.append(_timeline_event(dispute_id, "status_change", "orchestrator_agent",
        "Evidence gathering initiated",
        {"fromStatus": "intake", "toStatus": "evidence_gathering"}, _offset(created, minutes=5)))

    # Evidence items retrieved
    for ev in case.get("evidence", []):
        events.append(_timeline_event(dispute_id, "evidence_retrieved", "evidence_agent",
            f"Retrieved {ev['type']} from {ev['sourceSystem']}",
            {"sourceSystem": ev["sourceSystem"], "completeness": ev.get("completeness")},
            ev.get("retrievedAt", _offset(created, minutes=10))))

    # Evidence gaps
    for gap in case.get("evidenceGaps", []):
        events.append(_timeline_event(dispute_id, "evidence_gap", "evidence_agent",
            f"⚠️ EVIDENCE GAP: {gap['missingItem']}",
            {"missingItem": gap["missingItem"], "impact": gap.get("impact")},
            _offset(created, minutes=15)))

    # Status progression based on current status
    status = case["status"]
    status_order = ["intake", "evidence_gathering", "ai_drafting", "pending_review",
                    "approved", "submitted", "denied", "escalated", "expired", "closed"]

    # ai_drafting
    if status in status_order[status_order.index("ai_drafting"):]:
        events.append(_timeline_event(dispute_id, "status_change", "maker_agent",
            "Rebuttal draft generated",
            {"fromStatus": "evidence_gathering", "toStatus": "ai_drafting"},
            _offset(created, hours=2)))

    # pending_review
    if status in status_order[status_order.index("pending_review"):]:
        events.append(_timeline_event(dispute_id, "status_change", "system",
            "Assigned for analyst review",
            {"fromStatus": "ai_drafting", "toStatus": "pending_review"},
            _offset(created, hours=3)))

    # approved
    if status == "approved":
        events.append(_timeline_event(dispute_id, "status_change", "analyst",
            "Approved by analyst",
            {"fromStatus": "pending_review", "toStatus": "approved"},
            case.get("updatedAt", _offset(created, hours=24))))

    # submitted
    if status == "submitted":
        events.append(_timeline_event(dispute_id, "status_change", "analyst",
            "Approved by analyst",
            {"fromStatus": "pending_review", "toStatus": "approved"},
            _offset(created, hours=24)))
        events.append(_timeline_event(dispute_id, "status_change", "system",
            f"Evidence package submitted to {case['cardNetwork'].title()}",
            {"fromStatus": "approved", "toStatus": "submitted"},
            case.get("updatedAt", _offset(created, hours=25))))

    # denied
    if status == "denied":
        events.append(_timeline_event(dispute_id, "status_change", "analyst",
            "Denied — insufficient evidence",
            {"fromStatus": "pending_review", "toStatus": "denied"},
            case.get("updatedAt", _offset(created, hours=24))))

    # escalated
    if status == "escalated":
        events.append(_timeline_event(dispute_id, "status_change", "system",
            "Escalated to supervisor",
            {"fromStatus": "pending_review", "toStatus": "escalated"},
            case.get("updatedAt", _offset(created, hours=24))))

    return events


def _timeline_event(dispute_id, event_type, actor, detail, data, occurred_at):
    return {
        "id": str(uuid.uuid4()),
        "eventId": str(uuid.uuid4()),
        "disputeId": dispute_id,
        "eventType": event_type,
        "actor": actor,
        "detail": detail,
        "data": data,
        "occurredAt": occurred_at,
    }


def _offset(iso_str, minutes=0, hours=0):
    """Offset an ISO timestamp by given minutes/hours. Simple string-based."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        from datetime import timedelta
        dt = dt + timedelta(minutes=minutes, hours=hours)
        return dt.isoformat().replace("+00:00", "Z")
    except (ValueError, AttributeError):
        return iso_str


def _infer_category(reason_code: str, network: str) -> str:
    """Infer dispute category from reason code."""
    fraud_codes = {"10.4", "10.5", "4863", "F10", "F14", "UA01", "UA02"}
    if reason_code in fraud_codes:
        return "fraud"
    processing_codes = {"12.1", "12.2", "4831", "4834", "P01", "P05", "IN"}
    if reason_code in processing_codes:
        return "processing_error"
    auth_codes = {"11.1", "11.2", "4808", "4812", "F24"}
    if reason_code in auth_codes:
        return "authorization"
    return "consumer_dispute"


def _risk_level_to_score(level: str) -> int:
    """Map risk level to numeric score."""
    return {"low": 25, "medium": 50, "high": 75, "critical": 90}.get(level, 50)


def main():
    from pathlib import Path

    print("Loading Jorge's 10 curated cases from origin/develop...")
    cases = load_cases_from_git()
    print(f"  Loaded {len(cases)} cases")

    disputes = []
    evidence = []
    timeline = []

    for case in cases:
        disputes.append(transform_case_to_dispute(case))
        evidence.extend(transform_case_to_evidence(case))
        timeline.extend(generate_timeline_for_case(case))

    output_dir = Path("data/seed")
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "jorge_disputes.json", "w", encoding="utf-8") as f:
        json.dump(disputes, f, indent=2, default=str)

    with open(output_dir / "jorge_evidence.json", "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2, default=str)

    with open(output_dir / "jorge_timeline.json", "w", encoding="utf-8") as f:
        json.dump(timeline, f, indent=2, default=str)

    print(f"\nJorge's Cases Transformed to 3-Container Format:")
    print(f"  Disputes:  {len(disputes)}")
    print(f"  Evidence:  {len(evidence)}")
    print(f"  Timeline:  {len(timeline)}")
    print(f"\n  Output: data/seed/jorge_disputes.json")
    print(f"          data/seed/jorge_evidence.json")
    print(f"          data/seed/jorge_timeline.json")

    # Show status distribution
    statuses = {}
    for d in disputes:
        statuses[d["status"]] = statuses.get(d["status"], 0) + 1
    print(f"\n  Status distribution:")
    for s, c in sorted(statuses.items(), key=lambda x: -x[1]):
        print(f"    {s:20s} {c}")


if __name__ == "__main__":
    main()
