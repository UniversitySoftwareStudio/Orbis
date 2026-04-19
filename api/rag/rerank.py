import os
from typing import Any

import requests

from core.logging import get_logger
from rag.config import RAG_RERANK_MODEL
from rag.helpers import build_rerank_text

RERANK_URL = "https://api.jina.ai/v1/rerank"
logger = get_logger(__name__)


def _fallback(documents: list[str], top_k: int) -> list[dict[str, float | int]]:
    logger.debug("Using rerank fallback for top_k=%s", top_k)
    return [{"index": i, "score": 0.0} for i, _ in enumerate(documents[:top_k])]


def rerank(query: str, documents: list[str], top_k: int) -> list[dict[str, float | int]]:
    api_key = os.getenv("JINA_API_KEY")
    if not api_key or api_key.startswith("jina_xxx"):
        return _fallback(documents, top_k)

    try:
        response = requests.post(
            RERANK_URL,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            json={"model": RAG_RERANK_MODEL, "query": query, "documents": documents, "top_n": top_k},
            timeout=10,
        )
        response.raise_for_status()
        rows = response.json().get("results", [])
    except (requests.RequestException, ValueError):
        logger.warning("Rerank request failed; falling back to index order")
        return _fallback(documents, top_k)

    output: list[dict[str, float | int]] = []
    for row in rows:
        index = int(row.get("index", -1))
        if 0 <= index < len(documents):
            output.append({"index": index, "score": float(row.get("relevance_score", 0.0))})
    return output


def rerank_docs(query: str, docs: list[Any], top_k: int, include_language: bool) -> list[Any]:
    if not docs:
        return []
    ranked = rerank(query, [build_rerank_text(doc, include_language=include_language) for doc in docs], top_k)
    output: list[Any] = []
    for item in ranked:
        index = item.get("index")
        if isinstance(index, int) and 0 <= index < len(docs):
            doc = docs[index]
            doc.score = float(item.get("score", 0.0))
            output.append(doc)
    return output
