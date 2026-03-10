from typing import Any

from sqlalchemy.orm import Session

from rag.helpers import build_rerank_text
from rag.rerank import rerank, rerank_docs


def _expand_top_sources(
    repository: Any, session: Session, docs: list[Any], top_n: int = 3
) -> list[Any]:
    if not docs:
        return []

    expanded: dict[Any, Any] = {doc.id: doc for doc in docs[:10]}
    seen_urls: set[str] = set()
    for doc in docs[:top_n]:
        url = getattr(doc, "url", None)
        if getattr(doc, "type", "") not in {"web_page", "pdf"}:
            continue
        if not isinstance(url, str) or url in seen_urls:
            continue
        seen_urls.add(url)
        for chunk in repository.get_by_url(session, url):
            if chunk.id not in expanded:
                expanded[chunk.id] = chunk
    return list(expanded.values())


def execute_vector_intent(
    embedding_service: Any,
    repository: Any,
    session: Session,
    query: str,
    filters: dict[str, Any],
    parallel_mode: bool,
) -> list[Any]:
    if not query.strip():
        return []

    initial_docs = repository.vector_search(
        session,
        query_embedding=embedding_service.embed_text(query),
        query_text=query,
        filters=filters,
        limit=15 if parallel_mode else 30,
    )
    if not initial_docs:
        return []

    pre_rank = rerank(query, [build_rerank_text(doc) for doc in initial_docs], len(initial_docs))
    ranked_initial: list[Any] = [
        initial_docs[item["index"]]
        for item in pre_rank
        if isinstance(item.get("index"), int) and 0 <= item["index"] < len(initial_docs)
    ]
    if not ranked_initial:
        ranked_initial = initial_docs

    candidates = _expand_top_sources(repository, session, ranked_initial, top_n=3)
    if len(candidates) > 75:
        priority_ids = {doc.id for doc in ranked_initial[:3]}
        priority = [doc for doc in candidates if doc.id in priority_ids]
        rest = [doc for doc in candidates if doc.id not in priority_ids]
        candidates = priority + rest[: max(0, 75 - len(priority))]

    return rerank_docs(query, candidates, top_k=(5 if parallel_mode else 10), include_language=True)
