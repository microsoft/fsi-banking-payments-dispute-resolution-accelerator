"""
Evidence Retrieval Agent (#12) — precedents & rules retrieval over Azure AI Search.

Given a dispute, retrieves the most relevant card-network RULES, EVIDENCE
REQUIREMENTS, and case PRECEDENTS from the ``dispute-knowledge`` index on Azure
AI Search, grounded to source citations. Output feeds the Maker agent (#13).

Retrieval = keyword + semantic (L2) ranking (no vectors — embedding models are
unavailable on this subscription). Filters by card network + reason code, with
graceful relaxation (network + category, then semantic-only) when an exact match
returns nothing.

This module is ADDITIVE — it does NOT replace ``services.evidence_retrieval``
(the source-system evidence mock, #17). Different corpus, different job.

Environment variables (retrieval falls back to a stub if search is unconfigured
or unreachable — it never raises, so callers can treat it as best-effort):
  AZURE_SEARCH_ENDPOINT         e.g. https://rgdevaisearch.search.windows.net
  AZURE_SEARCH_INDEX            default "dispute-knowledge"
  AZURE_SEARCH_KEY             admin/query key (optional; DefaultAzureCredential used if unset)
  AZURE_SEARCH_SEMANTIC_CONFIG  default "dispute-semantic"

Result contract:
  {
    "disputeId", "network", "reasonCode",
    "results": [ {id, sourceType, title, snippet, score, rerankerScore,
                  citationLabel, sourceUrl, cardNetwork, reasonCode, tags} ],
    "rules": [...], "evidenceRequirements": [...], "precedents": [...],
    "citations": [ {label, url} ],
    "topK", "matchMode": "exact"|"network_category"|"semantic"|"none",
    "retrievedAt", "source": "search"|"stub"
  }
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "https://rgdevaisearch.search.windows.net"
DEFAULT_INDEX = "dispute-knowledge"
DEFAULT_SEMANTIC_CONFIG = "dispute-semantic"

_SELECT_FIELDS = [
    "id", "title", "content", "source_type", "card_network", "reason_code",
    "dispute_category", "effective_date", "source_url", "citation_label",
    "merchant_category", "region", "tags", "chunk_id",
]

_SNIPPET_MAX = 400

# Cached SearchClient — reset via reset_search_client() (used by tests).
_client: Any = None


def reset_search_client() -> None:
    """Drop the cached SearchClient (test hook / config change)."""
    global _client
    _client = None


def _get_search_client() -> Any:
    """Build (and cache) a SearchClient from environment configuration."""
    global _client
    if _client is not None:
        return _client
    try:
        from azure.core.credentials import AzureKeyCredential
        from azure.search.documents import SearchClient
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "azure-search-documents is required for evidence search."
        ) from exc

    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT", DEFAULT_ENDPOINT).strip()
    index = os.environ.get("AZURE_SEARCH_INDEX", DEFAULT_INDEX).strip()
    key = os.environ.get("AZURE_SEARCH_KEY", "").strip()

    if key:
        credential: Any = AzureKeyCredential(key)
    else:
        from azure.identity import DefaultAzureCredential
        credential = DefaultAzureCredential()

    _client = SearchClient(endpoint=endpoint, index_name=index, credential=credential)
    return _client


# ---------------------------------------------------------------------------
# Pure helpers (unit-testable without Azure)
# ---------------------------------------------------------------------------

def _resolve_network_and_code(dispute: dict[str, Any]) -> tuple[str, str]:
    """Determine (network, reason_code) from a dispute document."""
    raw = str(dispute.get("reasonCode") or "").strip()
    network = str(dispute.get("networkCode") or dispute.get("network") or "").lower().strip()

    parsed_net, parsed_code = "", raw
    try:
        from services.reason_code_engine import parse_reason_code_string
        parsed_net, parsed_code = parse_reason_code_string(raw)
    except Exception:  # noqa: BLE001 — parsing is best-effort
        pass

    if not network or network == "unknown":
        network = (parsed_net or "").lower().strip()
    code = (parsed_code or raw).strip()
    return network, code


def _dispute_category(dispute: dict[str, Any], network: str, code: str) -> str:
    """Best-effort dispute category (fraud / consumer_dispute / ...)."""
    cat = str(dispute.get("reasonCategory") or dispute.get("dispute_category") or "").strip()
    if cat:
        return cat
    try:
        from services.reason_code_engine import get_reason_code_detail
        detail = get_reason_code_detail(network, code)
        if detail:
            return str(detail.get("category") or "")
    except Exception:  # noqa: BLE001
        pass
    return ""


def _build_query_text(dispute: dict[str, Any], network: str, code: str) -> str:
    """Compose a natural-language query string to drive semantic ranking."""
    desc = str(dispute.get("reasonDescription") or "").strip()
    category = str(dispute.get("reasonCategory") or "").strip()
    if not desc or not category:
        try:
            from services.reason_code_engine import get_reason_code_detail
            detail = get_reason_code_detail(network, code)
            if detail:
                desc = desc or str(detail.get("description") or "")
                category = category or str(detail.get("category") or "")
        except Exception:  # noqa: BLE001
            pass

    merchant = str(dispute.get("merchantName") or "").strip()
    merchant_cat = str(dispute.get("merchantCategory") or "").strip()
    merchant_bit = f"merchant {merchant} {merchant_cat}".strip() if (merchant or merchant_cat) else ""

    bits = [network, code, desc, category.replace("_", " "), merchant_bit]
    text = " ".join(b for b in bits if b).strip()
    return text or f"{network} {code} dispute".strip()


def _odata_escape(value: str) -> str:
    return str(value).replace("'", "''")


def _build_filter(network: str, code: str, category: str, mode: str) -> str | None:
    """Build the OData filter for a given match mode. None => no filter."""
    net = _odata_escape(network)
    if mode == "exact":
        return f"card_network eq '{net}' and reason_code eq '{_odata_escape(code)}'"
    if mode == "network_category" and category:
        return f"card_network eq '{net}' and dispute_category eq '{_odata_escape(category)}'"
    return None


def _map_result(doc: dict[str, Any]) -> dict[str, Any]:
    """Map a raw search document to the response contract shape."""
    content = str(doc.get("content") or "")
    snippet = content if len(content) <= _SNIPPET_MAX else content[: _SNIPPET_MAX - 3] + "..."
    return {
        "id": doc.get("id"),
        "sourceType": doc.get("source_type"),
        "title": doc.get("title"),
        "snippet": snippet,
        "score": doc.get("@search.score"),
        "rerankerScore": doc.get("@search.reranker_score"),
        "citationLabel": doc.get("citation_label"),
        "sourceUrl": doc.get("source_url"),
        "cardNetwork": doc.get("card_network"),
        "reasonCode": doc.get("reason_code"),
        "tags": doc.get("tags") or [],
    }


def _assemble(
    dispute_id: str,
    network: str,
    code: str,
    results: list[dict[str, Any]],
    top_k: int,
    match_mode: str,
    now: datetime,
    source: str,
) -> dict[str, Any]:
    rules = [r for r in results if r.get("sourceType") == "network_rule"]
    reqs = [r for r in results if r.get("sourceType") == "evidence_requirement"]
    precedents = [r for r in results if r.get("sourceType") == "precedent"]

    citations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in results:
        label = r.get("citationLabel")
        if label and label not in seen:
            seen.add(label)
            citations.append({"label": label, "url": r.get("sourceUrl")})

    return {
        "disputeId": dispute_id,
        "network": network,
        "reasonCode": code,
        "results": results,
        "rules": rules,
        "evidenceRequirements": reqs,
        "precedents": precedents,
        "citations": citations,
        "topK": top_k,
        "matchMode": match_mode,
        "retrievedAt": now.isoformat(),
        "source": source,
    }


def _stub(dispute_id: str, network: str, code: str, top_k: int, now: datetime) -> dict[str, Any]:
    result = _assemble(dispute_id, network, code, [], top_k, "none", now, "stub")
    result["retrievalMode"] = "none"
    result["usedVector"] = False
    return result


def _execute_search(
    client: Any,
    query_text: str,
    filter_expr: str | None,
    top_k: int,
    semantic_config: str,
    query_vector: list[float] | None = None,
) -> list[dict[str, Any]]:
    """
    Run one search. When a query vector is supplied, runs HYBRID (vector +
    keyword) with semantic (L2) reranking; otherwise keyword + semantic. Falls
    back to plain keyword (+ vector if present) on any semantic failure.
    """
    vector_queries = None
    if query_vector is not None:
        from azure.search.documents.models import VectorizedQuery
        vector_queries = [
            VectorizedQuery(
                vector=query_vector,
                k_nearest_neighbors=top_k,
                fields="content_vector",
            )
        ]

    try:
        return list(
            client.search(
                search_text=query_text,
                filter=filter_expr,
                vector_queries=vector_queries,
                query_type="semantic",
                semantic_configuration_name=semantic_config,
                top=top_k,
                select=_SELECT_FIELDS,
            )
        )
    except Exception as exc:  # noqa: BLE001 — semantic may be unavailable / throttled
        logger.warning(
            "[evidence_search] semantic query failed (%s) — retrying without semantic reranking.",
            exc,
        )
        return list(
            client.search(
                search_text=query_text,
                filter=filter_expr,
                vector_queries=vector_queries,
                top=top_k,
                select=_SELECT_FIELDS,
            )
        )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def retrieve_precedents_for_dispute(dispute: dict[str, Any], top_k: int = 5) -> dict[str, Any]:
    """
    Retrieve relevant rules, evidence requirements, and precedents for a dispute.

    Tries progressively broader matches: exact (network + reason code) ->
    network + category -> semantic-only. Never raises: on any failure or
    misconfiguration it returns a well-formed stub result (source="stub").
    """
    now = datetime.now(timezone.utc)
    dispute_id = str(dispute.get("disputeId") or dispute.get("id") or "")
    network, code = "", ""

    try:
        network, code = _resolve_network_and_code(dispute)
        category = _dispute_category(dispute, network, code)
        query_text = _build_query_text(dispute, network, code)
        semantic_config = os.environ.get(
            "AZURE_SEARCH_SEMANTIC_CONFIG", DEFAULT_SEMANTIC_CONFIG
        ).strip()

        # Embed the query for hybrid search (None => keyword + semantic only).
        query_vector: list[float] | None = None
        try:
            from services.embeddings_client import embed_query
            query_vector = embed_query(query_text)
        except Exception as exc:  # noqa: BLE001 — embeddings are best-effort
            logger.warning("[evidence_search] query embedding failed (%s).", exc)

        client = _get_search_client()

        attempts: list[tuple[str, str | None]] = [
            ("exact", _build_filter(network, code, category, "exact")),
            ("network_category", _build_filter(network, code, category, "network_category")),
            ("semantic", None),
        ]

        docs: list[dict[str, Any]] = []
        match_mode = "semantic"
        for mode, filter_expr in attempts:
            if mode == "network_category" and not category:
                continue
            docs = _execute_search(
                client, query_text, filter_expr, top_k, semantic_config, query_vector
            )
            if docs:
                match_mode = mode
                break

        results = [_map_result(d) for d in docs]
        retrieval_mode = "hybrid" if query_vector is not None else "keyword_semantic"
        logger.info(
            "[evidence_search] disputeId=%s network=%s code=%s -> %d result(s) (mode=%s, retrieval=%s)",
            dispute_id, network, code, len(results), match_mode, retrieval_mode,
        )
        result = _assemble(dispute_id, network, code, results, top_k, match_mode, now, "search")
        result["retrievalMode"] = retrieval_mode
        result["usedVector"] = query_vector is not None
        return result

    except Exception as exc:  # noqa: BLE001 — best-effort, never block caller
        logger.warning(
            "[evidence_search] retrieval failed for disputeId=%s — returning stub. error=%s",
            dispute_id, exc,
        )
        return _stub(dispute_id, network, code, top_k, now)
