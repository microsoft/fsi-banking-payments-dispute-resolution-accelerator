"""
Triage Agent Client — Microsoft Agent Framework (Azure AI Foundry) placeholder.

Calls an Azure AI Foundry-hosted triage agent immediately after dispute intake
to score and categorize the case. Falls back to a deterministic stub if the
Foundry agent is not configured or reachable — stub never throws, never blocks
ingestion, and is always logged clearly so it cannot be mistaken for a real
agent response.

Environment variables (optional — leave unset for stub mode):
  FOUNDRY_PROJECT_ENDPOINT   e.g. https://<project>.services.ai.azure.com/api/projects/<project>
  FOUNDRY_TRIAGE_AGENT_ID    e.g. asst_XXXXXXXXXXXXXXXXXXXX

Result contract:
  {
    "score": float,          # win-probability [0.0, 1.0]
    "category": str,         # "auto_approve" | "review" | "escalate"
    "source": str,           # "foundry" | "stub"
    "rawResponse": str|None  # agent text response, or None for stub
  }
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stub fallback — returned whenever Foundry is not configured or unreachable
# ---------------------------------------------------------------------------
_STUB_RESPONSE: dict[str, Any] = {
    "score": 0.5,
    "category": "review",
    "source": "stub",
    "rawResponse": None,
}


def _build_case_summary(case_doc: dict[str, Any]) -> str:
    """Produce a compact natural-language summary of the case for the agent."""
    network = case_doc.get("networkCode") or case_doc.get("cardNetwork") or "unknown"
    reason = case_doc.get("reasonCode") or "unknown"
    amount = case_doc.get("transactionAmount")
    merchant = case_doc.get("merchantName") or "unknown merchant"
    evidence = case_doc.get("evidence") or []
    evidence_count = len(evidence) if isinstance(evidence, list) else 0

    amount_str = f"${float(amount):.2f}" if amount is not None else "unknown amount"
    completeness = "complete" if evidence_count >= 2 else "partial" if evidence_count == 1 else "no evidence"

    return (
        f"Network: {network}. Reason code: {reason}. Amount: {amount_str}. "
        f"Merchant: {merchant}. Evidence completeness: {completeness} ({evidence_count} item(s))."
    )


def _parse_agent_response(raw_text: str) -> dict[str, Any]:
    """
    Parse structured JSON from the agent's text response.

    Expects the agent to return JSON with 'score' and 'category'. If parsing
    fails or required fields are missing, the stub values are used as defaults
    so the caller always gets a well-formed result.
    """
    try:
        data = json.loads(raw_text)
        score = float(data.get("score", _STUB_RESPONSE["score"]))
        category = str(data.get("category", _STUB_RESPONSE["category"]))
        score = max(0.0, min(1.0, score))
        return {"score": score, "category": category, "source": "foundry", "rawResponse": raw_text}
    except (json.JSONDecodeError, ValueError, TypeError):
        logger.warning(
            "[triage_agent] Agent response is not valid JSON — using stub defaults. raw=%r",
            raw_text[:200],
        )
        return {**_STUB_RESPONSE, "source": "foundry", "rawResponse": raw_text}


def _call_foundry_agent(endpoint: str, agent_id: str, case_summary: str) -> dict[str, Any]:
    """Invoke the Foundry-hosted triage agent via azure-ai-projects."""
    try:
        from azure.ai.projects import AIProjectClient  # type: ignore[import]
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        raise RuntimeError(
            "azure-ai-projects is required for Foundry agent calls. "
            "Add it to requirements.txt."
        ) from exc

    client = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())

    thread = client.agents.threads.create()
    client.agents.messages.create(
        thread_id=thread.id,
        role="user",
        content=case_summary,
    )
    run = client.agents.runs.create_and_poll(
        thread_id=thread.id,
        agent_id=agent_id,
        timeout=30,
    )

    if run.status != "completed":
        raise RuntimeError(
            f"Foundry agent run did not complete — status={run.status} agent_id={agent_id}"
        )

    messages = client.agents.messages.list(thread_id=thread.id)
    # The last assistant message is the agent's answer
    for msg in messages:
        if msg.role == "assistant":
            content = msg.content[0].text.value if msg.content else ""
            return _parse_agent_response(content)

    raise RuntimeError(f"Foundry agent returned no assistant messages — agent_id={agent_id}")


def score_dispute(case_doc: dict[str, Any]) -> dict[str, Any]:
    """
    Score and categorize a dispute case using the triage agent.

    Returns the stub response if FOUNDRY_PROJECT_ENDPOINT or
    FOUNDRY_TRIAGE_AGENT_ID are unset, or if the Foundry agent call fails for
    any reason. This function never raises — all exceptions are caught and
    logged so that callers (ingestion pipeline) can treat this as best-effort.

    :param case_doc: The full dispute document as stored/returned by Cosmos.
    :returns: Triage result dict with keys: score, category, source, rawResponse.
    """
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
    agent_id = os.environ.get("FOUNDRY_TRIAGE_AGENT_ID", "").strip()

    if not endpoint or not agent_id:
        logger.info(
            "[triage_agent] FOUNDRY_PROJECT_ENDPOINT or FOUNDRY_TRIAGE_AGENT_ID not set — "
            "returning stub response (source=stub). disputeId=%s",
            case_doc.get("disputeId"),
        )
        return dict(_STUB_RESPONSE)

    case_summary = _build_case_summary(case_doc)
    logger.info(
        "[triage_agent] Invoking Foundry agent — endpoint=%s agent_id=%s disputeId=%s",
        endpoint,
        agent_id,
        case_doc.get("disputeId"),
    )

    try:
        result = _call_foundry_agent(endpoint, agent_id, case_summary)
        logger.info(
            "[triage_agent] Foundry agent result — disputeId=%s score=%.3f category=%s",
            case_doc.get("disputeId"),
            result["score"],
            result["category"],
        )
        return result
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[triage_agent] Foundry agent call failed — returning stub response. "
            "disputeId=%s error=%s",
            case_doc.get("disputeId"),
            exc,
        )
        return dict(_STUB_RESPONSE)
