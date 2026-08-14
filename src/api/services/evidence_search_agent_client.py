"""
Optional grounding layer for the Evidence Retrieval Agent (#12).

Wraps the deterministic search result from ``services.evidence_search`` with a
short, grounded "relevance rationale" produced by a Foundry-hosted chat model
(DeepSeek-V3.2 by default). Strictly ADDITIVE and env-gated: if the model is not
configured or the call fails, the original search result is returned unchanged
(``source`` stays "search"). Never raises.

Environment variables (leave FOUNDRY_INFERENCE_KEY unset to disable grounding):
  FOUNDRY_INFERENCE_ENDPOINT  e.g. https://<AI_SERVICES_NAME>.services.ai.azure.com/models
  FOUNDRY_INFERENCE_KEY       AIServices key (required to enable grounding)
  FOUNDRY_SYNTH_MODEL         deployment name, default "DeepSeek-V3.2"
  FOUNDRY_SYNTH_API_VERSION   default "2024-05-01-preview"

On success the returned dict gains ``rationale`` and ``source`` becomes "agent".
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "https://<AI_SERVICES_NAME>.services.ai.azure.com/models"  # override via FOUNDRY_INFERENCE_ENDPOINT env var
DEFAULT_MODEL = "DeepSeek-V3.2"
DEFAULT_API_VERSION = "2024-05-01-preview"

_SYSTEM_PROMPT = (
    "You are an evidence-retrieval assistant for card-dispute analysts. "
    "You are given a dispute summary and a set of retrieved knowledge snippets "
    "(card-network rules, evidence requirements, and case precedents). In 2-3 "
    "sentences, explain which snippets are most relevant to winning this dispute "
    "and why. Cite snippets only by their citation label. Do not invent facts or "
    "cite anything not in the provided snippets."
)


def _build_grounding_prompt(dispute: dict[str, Any], search_result: dict[str, Any]) -> str:
    network = search_result.get("network") or dispute.get("networkCode") or "unknown"
    code = search_result.get("reasonCode") or dispute.get("reasonCode") or "unknown"
    merchant = dispute.get("merchantName") or "unknown merchant"
    lines = [
        f"Dispute: network={network}, reason_code={code}, merchant={merchant}.",
        "",
        "Retrieved snippets:",
    ]
    for r in search_result.get("results", []):
        label = r.get("citationLabel") or r.get("id") or "unlabeled"
        stype = r.get("sourceType") or "unknown"
        snippet = (r.get("snippet") or "").strip()
        lines.append(f"- [{label}] ({stype}) {snippet}")
    return "\n".join(lines)


def _call_model(prompt: str, endpoint: str, api_key: str, model: str, api_version: str) -> str:
    """Invoke the Foundry chat model via the OpenAI-compatible inference route."""
    from openai import OpenAI

    client = OpenAI(
        base_url=endpoint,
        api_key=api_key,
        default_query={"api-version": api_version},
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=300,
    )
    return (resp.choices[0].message.content or "").strip()


def ground_evidence(dispute: dict[str, Any], search_result: dict[str, Any]) -> dict[str, Any]:
    """
    Add a grounded relevance rationale to a search result, if configured.

    Returns ``search_result`` unchanged when grounding is disabled (no
    FOUNDRY_INFERENCE_KEY), when there are no results to ground, or when the
    model call fails. Never raises.
    """
    api_key = os.environ.get("FOUNDRY_INFERENCE_KEY", "").strip()
    if not api_key:
        logger.info("[evidence_agent] FOUNDRY_INFERENCE_KEY unset — skipping grounding.")
        return search_result

    if not search_result.get("results"):
        return search_result

    endpoint = os.environ.get("FOUNDRY_INFERENCE_ENDPOINT", DEFAULT_ENDPOINT).strip()
    model = os.environ.get("FOUNDRY_SYNTH_MODEL", DEFAULT_MODEL).strip()
    api_version = os.environ.get("FOUNDRY_SYNTH_API_VERSION", DEFAULT_API_VERSION).strip()

    try:
        prompt = _build_grounding_prompt(dispute, search_result)
        rationale = _call_model(prompt, endpoint, api_key, model, api_version)
        if not rationale:
            return search_result
        grounded = dict(search_result)
        grounded["rationale"] = rationale
        grounded["source"] = "agent"
        return grounded
    except Exception as exc:  # noqa: BLE001 — grounding is best-effort
        logger.warning(
            "[evidence_agent] grounding failed — returning ungrounded result. error=%s",
            exc,
        )
        return search_result
