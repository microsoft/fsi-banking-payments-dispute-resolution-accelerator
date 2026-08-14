"""
Embeddings client for the Evidence Retrieval Agent (#12) — Cohere Embed v4
(`embed-v-4-0`) hosted on Azure AI Foundry.

Produces dense vectors for hybrid (vector + keyword) search over the
`dispute-knowledge` index. Cohere embeddings are ASYMMETRIC: documents are
embedded with input_type="document" and queries with input_type="query", which
improves retrieval quality.

Dependency-free (stdlib urllib) and env-gated: if not configured or the call
fails, every function returns None so callers degrade gracefully to keyword +
semantic search. Never raises.

Environment variables (leave AZURE_EMBED_KEY unset to disable vectors):
  AZURE_EMBED_ENDPOINT      default https://<AI_SERVICES_NAME>.services.ai.azure.com
  AZURE_EMBED_DEPLOYMENT    default "embed-v-4-0"
  AZURE_EMBED_KEY           AI Services key (required to enable embeddings)
  AZURE_EMBED_API_VERSION   default "2024-05-01-preview"
  AZURE_EMBED_DIMENSIONS    default "1536" (Cohere v4 also supports 256/512/1024)
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "https://<AI_SERVICES_NAME>.services.ai.azure.com"  # override via AZURE_EMBED_ENDPOINT env var
DEFAULT_DEPLOYMENT = "embed-v-4-0"
DEFAULT_API_VERSION = "2024-05-01-preview"
DEFAULT_DIMENSIONS = 1536

# Cohere-on-Azure input_type values (NOT Cohere's native search_document/search_query).
INPUT_TYPE_DOCUMENT = "document"
INPUT_TYPE_QUERY = "query"


def embed_dimensions() -> int:
    try:
        return int(os.environ.get("AZURE_EMBED_DIMENSIONS", str(DEFAULT_DIMENSIONS)).strip())
    except (TypeError, ValueError):
        return DEFAULT_DIMENSIONS


def is_configured() -> bool:
    """True when an embedding key is present (embeddings enabled)."""
    return bool(os.environ.get("AZURE_EMBED_KEY", "").strip())


def _endpoint() -> str:
    return os.environ.get("AZURE_EMBED_ENDPOINT", DEFAULT_ENDPOINT).strip().rstrip("/")


def embed_texts(texts: list[str], input_type: str) -> list[list[float]] | None:
    """
    Embed a batch of texts. Returns a list of vectors (one per input) or None if
    embeddings are unconfigured or the call fails. Never raises.

    :param input_type: INPUT_TYPE_DOCUMENT for corpus docs, INPUT_TYPE_QUERY for queries.
    """
    key = os.environ.get("AZURE_EMBED_KEY", "").strip()
    if not key:
        logger.info("[embeddings] AZURE_EMBED_KEY unset — embeddings disabled.")
        return None
    if not texts:
        return []

    deployment = os.environ.get("AZURE_EMBED_DEPLOYMENT", DEFAULT_DEPLOYMENT).strip()
    api_version = os.environ.get("AZURE_EMBED_API_VERSION", DEFAULT_API_VERSION).strip()
    url = f"{_endpoint()}/models/embeddings?api-version={api_version}"

    body: dict[str, Any] = {
        "input": texts,
        "model": deployment,
        "input_type": input_type,
        "dimensions": embed_dimensions(),
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "api-key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
        items = sorted(data.get("data", []), key=lambda d: d.get("index", 0))
        vectors = [item["embedding"] for item in items]
        if len(vectors) != len(texts):
            logger.warning(
                "[embeddings] expected %d vectors, got %d.", len(texts), len(vectors)
            )
            return None
        return vectors
    except urllib.error.HTTPError as exc:  # noqa: PERF203
        detail = ""
        try:
            detail = exc.read().decode()[:200]
        except Exception:  # noqa: BLE001
            pass
        logger.warning("[embeddings] HTTP %s calling %s — %s", exc.code, deployment, detail)
        return None
    except Exception as exc:  # noqa: BLE001 — network/parse errors, best-effort
        logger.warning("[embeddings] embed call failed (%s) — returning None.", exc)
        return None


def embed_query(text: str) -> list[float] | None:
    """Embed a single query string (input_type=query). None if unavailable."""
    vectors = embed_texts([text], INPUT_TYPE_QUERY)
    return vectors[0] if vectors else None
