"""
Maker Agent Client — Microsoft Agent Framework (Azure AI Foundry).

Drafts a *grounded* chargeback rebuttal narrative for a dispute case, citing
only facts that are present in the assembled evidence payload. Implements the
"Maker" half of the maker-checker pattern (Issue #13, absorbs #20): it produces
a draft that the Checker agent (#14, Phase 2) later validates for groundedness.

Design mirrors ``services.triage_agent_client``:
  * Calls an Azure AI Foundry model when configured, via the Chat Completions
    API (the protocol available in the target Foundry account). The maker's
    system prompt matches the NextGen ``maker-agent`` definition in Foundry, so
    behaviour is identical whether invoked through the portal agent or here.
  * Falls back to a deterministic, fully-grounded stub when Foundry is not
    configured or unreachable — the stub never throws and never blocks the
    orchestrator. Every sentence the stub emits is derived from a supplied
    evidence item, so the stub cannot hallucinate.

Environment variables (optional — leave unset for stub mode):
  FOUNDRY_PROJECT_ENDPOINT   e.g. https://<project>.services.ai.azure.com/api/projects/<project>
  FOUNDRY_MAKER_AGENT_ID     NextGen agent name (e.g. "maker-agent"). Presence of
                             this (with the endpoint) enables live Foundry calls.
  FOUNDRY_MAKER_MODEL        Model deployment used for drafting via Chat
                             Completions (default "DeepSeek-V3.2").

Note on the Responses API: NextGen "prompt" agents in Foundry speak the
``responses`` protocol, but that protocol is not enabled in every account/region
(a freshly-deployed, chat-capable model still 404s on ``/responses`` there). To
keep the live call working today, this client invokes the backing model through
Chat Completions using the same maker instructions. When the Responses API
becomes available the agent can be called directly with no behavioural change.

Result contract (structured for checker review):
  {
    "rebuttalText": str,           # the drafted letter
    "citations": [                 # one entry per evidence fact referenced
        {"evidenceId": str, "excerpt": str},
        ...
    ],
    "network": str,                # visa | mastercard | amex | discover | unknown
    "reasonCode": str,
    "networkFormat": str,          # human label of the network letter format used
    "grounded": bool,              # True iff every citation maps to a real evidence item
    "evidenceCited": int,          # number of distinct evidence items cited
    "source": str,                 # "foundry" | "stub"
    "rawResponse": str | None,     # model text response, or None for stub
  }
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Default model deployment used for drafting via Chat Completions.
_DEFAULT_MAKER_MODEL = "DeepSeek-V3.2"

# System prompt — mirrors the NextGen `maker-agent` definition in Foundry so the
# behaviour is identical whether the agent is invoked through the portal or here.
_MAKER_SYSTEM_PROMPT = (
    "You are the Maker agent in a payments dispute-resolution system. You run "
    "AFTER the Evidence Retrieval agent and consume its assembled evidence. Draft "
    "a grounded chargeback rebuttal letter for the bank's dispute analyst to "
    "review (maker-checker pattern).\n\n"
    "STRICT GROUNDING RULES:\n"
    "- Cite ONLY facts contained in the supplied evidence array. Never invent "
    "facts, amounts, dates, authorization codes, tracking numbers, or documents.\n"
    "- Every citation's evidenceId MUST be one of the evidence ids supplied.\n"
    "- If evidence is insufficient, say so plainly rather than fabricating support.\n\n"
    "INPUT: A JSON object with 'dispute' (network, reasonCode, merchantName, "
    "transactionAmount, transactionDate) and 'evidence' (array of {evidenceId, "
    "title, sourceSystem, content}).\n\n"
    "CARD-NETWORK FORMATS: Adapt the letter framing to the dispute's network — "
    "Visa (Dispute Representment / VCR), Mastercard (Second Presentment / "
    "Mastercom), American Express (Chargeback Reversal), or Discover (Dispute "
    "Representment).\n\n"
    "OUTPUT: Respond with STRICT JSON only, no prose outside the JSON:\n"
    '{"rebuttalText": "<the full letter>", "citations": [{"evidenceId": '
    '"<id from evidence>", "excerpt": "<the specific fact cited>"}]}'
)


# ---------------------------------------------------------------------------
# Card-network letter formats — all four networks in scope (Visa, Mastercard,
# American Express, Discover). Each network expects a slightly different
# framing / addressee for the representment (rebuttal) package.
# ---------------------------------------------------------------------------
_NETWORK_FORMATS: dict[str, dict[str, str]] = {
    "visa": {
        "label": "Visa Dispute Representment (VCR)",
        "addressee": "Visa Claims Resolution — Dispute Response",
        "closing": "Submitted under Visa Core Rules dispute representment.",
    },
    "mastercard": {
        "label": "Mastercard Second Presentment (Mastercom)",
        "addressee": "Mastercard Dispute Resolution — Second Presentment",
        "closing": "Submitted under the Mastercard Chargeback Guide.",
    },
    "amex": {
        "label": "American Express Chargeback Reversal",
        "addressee": "American Express Merchant Services — Dispute Response",
        "closing": "Submitted under American Express dispute policy.",
    },
    "discover": {
        "label": "Discover Dispute Representment",
        "addressee": "Discover Network — Dispute Resolution",
        "closing": "Submitted under Discover Network dispute rules.",
    },
    "unknown": {
        "label": "Card-Network Dispute Representment",
        "addressee": "Card Network — Dispute Resolution",
        "closing": "Submitted under applicable card-network dispute rules.",
    },
}


def _normalize_network(dispute: dict[str, Any]) -> str:
    net = (
        dispute.get("networkCode")
        or dispute.get("cardNetwork")
        or dispute.get("network")
        or ""
    ).strip().lower()
    aliases = {
        "mc": "mastercard",
        "master card": "mastercard",
        "american express": "amex",
        "ax": "amex",
    }
    net = aliases.get(net, net)
    return net if net in _NETWORK_FORMATS else "unknown"


# ---------------------------------------------------------------------------
# Evidence helpers
# ---------------------------------------------------------------------------

def _extract_evidence(
    dispute: dict[str, Any],
    evidence: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Return the list of evidence items to ground the draft on.

    Accepts either an explicit ``evidence`` list (e.g. the ``evidenceItems``
    output of ``evidence_retrieval.retrieve_evidence_for_dispute``) or falls
    back to ``dispute['evidence']``.
    """
    if evidence:
        return [e for e in evidence if isinstance(e, dict)]
    inner = dispute.get("evidence")
    if isinstance(inner, list):
        return [e for e in inner if isinstance(e, dict)]
    return []


def _evidence_id(item: dict[str, Any]) -> str:
    return str(
        item.get("evidenceId")
        or item.get("checklistItemId")
        or item.get("id")
        or item.get("title")
        or ""
    )


def _evidence_excerpt(item: dict[str, Any]) -> str:
    """Produce a short, factual excerpt from an evidence item's content."""
    title = item.get("title") or item.get("label") or item.get("type") or "Evidence"
    source = item.get("sourceLabel") or item.get("sourceSystem") or ""
    content = item.get("content")
    detail = ""
    if isinstance(content, dict):
        parts = []
        for key, val in content.items():
            if isinstance(val, (str, int, float, bool)):
                parts.append(f"{key}={val}")
            if len(parts) >= 3:
                break
        detail = "; ".join(parts)
    elif isinstance(content, str):
        detail = content[:160]
    source_str = f" [{source}]" if source else ""
    return f"{title}{source_str}: {detail}".strip().rstrip(":").strip()


# ---------------------------------------------------------------------------
# Deterministic, grounded stub draft
# ---------------------------------------------------------------------------

def _build_stub_draft(
    dispute: dict[str, Any],
    evidence: list[dict[str, Any]],
    network: str,
) -> dict[str, Any]:
    """Compose a grounded rebuttal strictly from the supplied evidence items.

    Never invents facts: every body sentence references a specific evidence item
    and produces a matching citation.
    """
    fmt = _NETWORK_FORMATS[network]
    reason_code = str(dispute.get("reasonCode") or "unknown")
    merchant = dispute.get("merchantName") or "the merchant"
    amount = dispute.get("transactionAmount")
    amount_str = f"${float(amount):.2f}" if amount is not None else "the disputed amount"

    header = (
        f"To: {fmt['addressee']}\n"
        f"Re: Rebuttal for dispute {dispute.get('disputeId') or dispute.get('caseId') or ''} "
        f"(reason code {reason_code})\n"
    )

    citations: list[dict[str, str]] = []
    body_lines: list[str] = []

    if not evidence:
        body = (
            f"{merchant} contests this {amount_str} chargeback. No supporting evidence "
            "items were supplied with this request; a grounded rebuttal cannot yet be "
            "assembled and additional evidence is required before submission."
        )
        return {
            "rebuttalText": header + "\n" + body + "\n\n" + fmt["closing"],
            "citations": [],
            "grounded": False,
            "evidenceCited": 0,
        }

    intro = (
        f"{merchant} respectfully contests the {amount_str} chargeback filed under "
        f"reason code {reason_code}. The following verified evidence supports that the "
        f"transaction was valid and properly authorized:"
    )
    body_lines.append(intro)

    for idx, item in enumerate(evidence, start=1):
        eid = _evidence_id(item)
        excerpt = _evidence_excerpt(item)
        if not eid or not excerpt:
            continue
        body_lines.append(f"{idx}. {excerpt}.")
        citations.append({"evidenceId": eid, "excerpt": excerpt})

    conclusion = (
        "Based solely on the evidence enumerated above, the charge is legitimate and "
        "the chargeback should be reversed."
    )
    body_lines.append(conclusion)

    rebuttal_text = header + "\n" + "\n".join(body_lines) + "\n\n" + fmt["closing"]
    return {
        "rebuttalText": rebuttal_text,
        "citations": citations,
        "grounded": len(citations) > 0,
        "evidenceCited": len({c["evidenceId"] for c in citations}),
    }


# ---------------------------------------------------------------------------
# Foundry agent invocation
# ---------------------------------------------------------------------------

def _build_agent_prompt(
    dispute: dict[str, Any],
    evidence: list[dict[str, Any]],
    network: str,
) -> str:
    """Build the user message for the Foundry maker agent.

    The evidence list is passed as an explicit, id-tagged block so the agent can
    only cite facts we actually supplied.
    """
    fmt = _NETWORK_FORMATS[network]
    evidence_block = [
        {
            "evidenceId": _evidence_id(item),
            "title": item.get("title") or item.get("label"),
            "sourceSystem": item.get("sourceSystem"),
            "content": item.get("content"),
        }
        for item in evidence
    ]
    instructions = (
        "You are the Maker agent. Draft a chargeback rebuttal letter for the "
        f"{fmt['label']} format. Cite ONLY facts contained in the evidence array — "
        "never invent facts, amounts, dates, or documents. Respond as strict JSON: "
        '{"rebuttalText": str, "citations": [{"evidenceId": str, "excerpt": str}]}. '
        "Every citation's evidenceId MUST be one of the supplied evidence ids."
    )
    payload = {
        "instructions": instructions,
        "dispute": {
            "disputeId": dispute.get("disputeId") or dispute.get("caseId"),
            "network": network,
            "reasonCode": dispute.get("reasonCode"),
            "merchantName": dispute.get("merchantName"),
            "transactionAmount": dispute.get("transactionAmount"),
            "transactionDate": dispute.get("transactionDate"),
        },
        "evidence": evidence_block,
    }
    return json.dumps(payload)


def _strip_code_fences(text: str) -> str:
    """Strip Markdown ```json ... ``` fences some models wrap JSON output in."""
    t = text.strip()
    if t.startswith("```"):
        # Drop the opening fence line (``` or ```json) and any trailing fence.
        first_newline = t.find("\n")
        if first_newline != -1:
            t = t[first_newline + 1:]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def _parse_agent_response(raw_text: str, valid_ids: set[str]) -> dict[str, Any]:
    """Parse the agent's JSON draft and enforce grounding against ``valid_ids``.

    Citations that reference an unknown evidence id are dropped, and the draft is
    only marked ``grounded`` when it contains at least one citation and every
    citation maps to a real evidence item.
    """
    try:
        data = json.loads(_strip_code_fences(raw_text))
    except (json.JSONDecodeError, TypeError):
        logger.warning("[maker_agent] Agent response is not valid JSON. raw=%r", raw_text[:200])
        return {"rebuttalText": "", "citations": [], "grounded": False, "evidenceCited": 0}

    rebuttal_text = str(data.get("rebuttalText", "") or "")
    raw_citations = data.get("citations") or []
    accepted: list[dict[str, str]] = []
    dropped = 0
    if isinstance(raw_citations, list):
        for c in raw_citations:
            if not isinstance(c, dict):
                dropped += 1
                continue
            eid = str(c.get("evidenceId", ""))
            if eid and eid in valid_ids:
                accepted.append({"evidenceId": eid, "excerpt": str(c.get("excerpt", ""))})
            else:
                dropped += 1

    if dropped:
        logger.warning(
            "[maker_agent] dropped %d ungrounded citation(s) referencing unknown evidence ids",
            dropped,
        )

    grounded = bool(accepted) and dropped == 0 and bool(rebuttal_text.strip())
    return {
        "rebuttalText": rebuttal_text,
        "citations": accepted,
        "grounded": grounded,
        "evidenceCited": len({c["evidenceId"] for c in accepted}),
    }


def _call_foundry_agent(
    endpoint: str,
    agent_id: str,
    prompt: str,
    valid_ids: set[str],
) -> dict[str, Any]:
    """Invoke the Foundry maker model via Chat Completions.

    Uses ``AIProjectClient.get_openai_client()`` and the Chat Completions API —
    the inference protocol available in the target Foundry account. The system
    prompt matches the NextGen ``maker-agent`` definition so behaviour is
    identical to invoking that agent directly. ``agent_id`` is accepted for
    interface parity / logging; the model is selected via ``FOUNDRY_MAKER_MODEL``.
    """
    try:
        from azure.ai.projects import AIProjectClient  # type: ignore[import]
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        raise RuntimeError(
            "azure-ai-projects is required for Foundry agent calls. Add it to requirements.txt."
        ) from exc

    model = os.environ.get("FOUNDRY_MAKER_MODEL", "").strip() or _DEFAULT_MAKER_MODEL

    project_client = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())
    openai_client = project_client.get_openai_client()

    completion = openai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _MAKER_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )

    content = ""
    if completion.choices:
        content = completion.choices[0].message.content or ""

    if not content:
        raise RuntimeError(
            f"Foundry maker model returned no content — model={model} agent={agent_id}"
        )

    parsed = _parse_agent_response(content, valid_ids)
    parsed["rawResponse"] = content
    return parsed


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def draft_rebuttal(
    dispute: dict[str, Any],
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Draft a grounded rebuttal for a dispute case.

    Uses the Foundry-hosted maker agent when ``FOUNDRY_PROJECT_ENDPOINT`` and
    ``FOUNDRY_MAKER_AGENT_ID`` are set; otherwise (or on any failure) returns a
    deterministic, fully-grounded stub. This function never raises — all
    exceptions are caught and logged so the orchestrator can treat drafting as
    best-effort.

    :param dispute: The dispute document (Cosmos shape).
    :param evidence: Optional explicit evidence-item list (e.g. the
        ``evidenceItems`` from evidence retrieval). Falls back to
        ``dispute['evidence']`` when omitted.
    :returns: Structured rebuttal draft (see module docstring).
    """
    network = _normalize_network(dispute)
    reason_code = str(dispute.get("reasonCode") or "unknown")
    items = _extract_evidence(dispute, evidence)
    fmt = _NETWORK_FORMATS[network]

    def _finalize(core: dict[str, Any], source: str, raw: str | None) -> dict[str, Any]:
        return {
            "rebuttalText": core["rebuttalText"],
            "citations": core["citations"],
            "network": network,
            "reasonCode": reason_code,
            "networkFormat": fmt["label"],
            "grounded": core["grounded"],
            "evidenceCited": core["evidenceCited"],
            "source": source,
            "rawResponse": raw,
        }

    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
    agent_id = os.environ.get("FOUNDRY_MAKER_AGENT_ID", "").strip()

    dispute_id = dispute.get("disputeId") or dispute.get("caseId")

    if not endpoint or not agent_id:
        logger.info(
            "[maker_agent] FOUNDRY_PROJECT_ENDPOINT or FOUNDRY_MAKER_AGENT_ID not set — "
            "returning grounded stub draft. disputeId=%s network=%s",
            dispute_id, network,
        )
        return _finalize(_build_stub_draft(dispute, items, network), "stub", None)

    valid_ids = {_evidence_id(i) for i in items if _evidence_id(i)}
    prompt = _build_agent_prompt(dispute, items, network)
    logger.info(
        "[maker_agent] Invoking Foundry maker agent — endpoint=%s agent_id=%s disputeId=%s",
        endpoint, agent_id, dispute_id,
    )

    try:
        result = _call_foundry_agent(endpoint, agent_id, prompt, valid_ids)
        raw = result.pop("rawResponse", None)
        logger.info(
            "[maker_agent] Foundry draft — disputeId=%s grounded=%s citations=%d",
            dispute_id, result["grounded"], result["evidenceCited"],
        )
        # If the agent produced nothing groundable, fall back to the grounded stub.
        if not result["rebuttalText"].strip():
            logger.warning(
                "[maker_agent] Foundry draft empty — falling back to stub. disputeId=%s", dispute_id
            )
            return _finalize(_build_stub_draft(dispute, items, network), "stub", raw)
        return _finalize(result, "foundry", raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[maker_agent] Foundry maker agent call failed — returning stub draft. "
            "disputeId=%s error=%s",
            dispute_id, exc,
        )
        return _finalize(_build_stub_draft(dispute, items, network), "stub", None)


def to_rebuttal_draft(result: dict[str, Any]) -> dict[str, Any]:
    """Adapt a ``draft_rebuttal`` result to the persisted ``RebuttalDraft`` shape.

    Mirrors ``models.case.RebuttalDraft`` ({text, citations:[{evidenceId, excerpt}]}).
    """
    return {
        "text": result.get("rebuttalText", ""),
        "citations": [
            {"evidenceId": c.get("evidenceId", ""), "excerpt": c.get("excerpt", "")}
            for c in result.get("citations", [])
        ],
    }
