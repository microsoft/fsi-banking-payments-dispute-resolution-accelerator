"""
Build / refresh the ``dispute-knowledge`` Azure AI Search index and upload the
knowledge corpus (card-network rules + evidence requirements + precedents).

Keyword + semantic (L2) index — no vector field (embedding models are
unavailable on this subscription). Idempotent: creates-or-updates the index,
then uploads the corpus documents.

Corpus: data/knowledge/dispute-knowledge.jsonl (one JSON object per line).

Usage (run from src/api):
    # admin key auth (recommended for index creation):
    $env:AZURE_SEARCH_ENDPOINT = "https://rgdevaisearch.search.windows.net"
    $env:AZURE_SEARCH_KEY      = "<admin-key>"
    python scripts/build_search_index.py --recreate

    # or AAD (needs Search Service Contributor + Search Index Data Contributor):
    python scripts/build_search_index.py

Flags:
    --recreate   Delete the index first (use when the schema changed).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

DEFAULT_ENDPOINT = "https://rgdevaisearch.search.windows.net"
DEFAULT_INDEX = "dispute-knowledge"
SEMANTIC_CONFIG = "dispute-semantic"
VECTOR_PROFILE = "dispute-vector-profile"
VECTOR_ALGORITHM = "dispute-hnsw"

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_SCRIPT_DIR)))
_CORPUS_PATH = os.path.join(_REPO_ROOT, "data", "knowledge", "dispute-knowledge.jsonl")

# Allow `import services.*` when run as `python scripts/build_search_index.py` from src/api.
_API_DIR = os.path.dirname(_SCRIPT_DIR)
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)


def _credential():
    key = os.environ.get("AZURE_SEARCH_KEY", "").strip()
    if key:
        from azure.core.credentials import AzureKeyCredential
        return AzureKeyCredential(key)
    from azure.identity import DefaultAzureCredential
    print("AZURE_SEARCH_KEY not set — using DefaultAzureCredential (AAD).")
    return DefaultAzureCredential()


def _build_index(index_name: str, vector_dimensions: int):
    from azure.search.documents.indexes.models import (
        HnswAlgorithmConfiguration,
        SearchableField,
        SearchField,
        SearchFieldDataType,
        SearchIndex,
        SemanticConfiguration,
        SemanticField,
        SemanticPrioritizedFields,
        SemanticSearch,
        SimpleField,
        VectorSearch,
        VectorSearchProfile,
    )

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
        SearchableField(name="title", type=SearchFieldDataType.String),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SimpleField(name="source_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="card_network", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="reason_code", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="dispute_category", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="effective_date", type=SearchFieldDataType.String, filterable=True, sortable=True),
        SimpleField(name="source_url", type=SearchFieldDataType.String),
        SearchableField(name="citation_label", type=SearchFieldDataType.String),
        SimpleField(name="merchant_category", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="region", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchField(
            name="tags",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            searchable=True, filterable=True, facetable=True,
        ),
        SimpleField(name="chunk_id", type=SearchFieldDataType.String),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=vector_dimensions,
            vector_search_profile_name=VECTOR_PROFILE,
        ),
    ]

    semantic = SemanticConfiguration(
        name=SEMANTIC_CONFIG,
        prioritized_fields=SemanticPrioritizedFields(
            title_field=SemanticField(field_name="title"),
            content_fields=[
                SemanticField(field_name="content"),
                SemanticField(field_name="citation_label"),
            ],
            keywords_fields=[SemanticField(field_name="tags")],
        ),
    )

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name=VECTOR_ALGORITHM)],
        profiles=[
            VectorSearchProfile(
                name=VECTOR_PROFILE,
                algorithm_configuration_name=VECTOR_ALGORITHM,
            )
        ],
    )

    return SearchIndex(
        name=index_name,
        fields=fields,
        semantic_search=SemanticSearch(configurations=[semantic]),
        vector_search=vector_search,
    )


def _load_corpus() -> list[dict]:
    if not os.path.exists(_CORPUS_PATH):
        raise FileNotFoundError(f"Corpus not found: {_CORPUS_PATH}")
    docs = []
    with open(_CORPUS_PATH, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                docs.append(json.loads(line))
    return docs


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the dispute-knowledge search index.")
    parser.add_argument("--recreate", action="store_true", help="Delete the index before creating.")
    args = parser.parse_args()

    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT", DEFAULT_ENDPOINT).strip()
    index_name = os.environ.get("AZURE_SEARCH_INDEX", DEFAULT_INDEX).strip()

    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    from services.embeddings_client import (
        INPUT_TYPE_DOCUMENT,
        embed_dimensions,
        embed_texts,
        is_configured,
    )

    credential = _credential()
    index_client = SearchIndexClient(endpoint=endpoint, credential=credential)

    if args.recreate:
        try:
            index_client.delete_index(index_name)
            print(f"Deleted existing index '{index_name}'.")
        except Exception as exc:  # noqa: BLE001
            print(f"(No existing index to delete, or delete failed: {exc})")

    dims = embed_dimensions()
    index = _build_index(index_name, dims)
    index_client.create_or_update_index(index)
    print(f"Index '{index_name}' created/updated on {endpoint} (vector dims={dims}).")

    docs = _load_corpus()
    print(f"Loaded {len(docs)} corpus document(s) from {_CORPUS_PATH}.")

    # Embed each document's content for vector search (Cohere embed-v-4-0).
    if is_configured():
        vectors = embed_texts([d.get("content", "") for d in docs], INPUT_TYPE_DOCUMENT)
        if vectors and len(vectors) == len(docs):
            for doc, vec in zip(docs, vectors):
                doc["content_vector"] = vec
            print(f"Embedded {len(vectors)} document(s) for vector search.")
        else:
            print("WARNING: embedding failed — uploading without vectors (keyword+semantic only).")
    else:
        print("AZURE_EMBED_KEY not set — uploading without vectors (keyword+semantic only).")

    search_client = SearchClient(endpoint=endpoint, index_name=index_name, credential=credential)
    results = search_client.upload_documents(documents=docs)
    succeeded = sum(1 for r in results if r.succeeded)
    print(f"Uploaded {succeeded}/{len(docs)} document(s).")

    if succeeded != len(docs):
        for r in results:
            if not r.succeeded:
                print(f"  FAILED key={r.key} status={r.status_code} error={r.error_message}")
        return 1

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
