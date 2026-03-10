from typing import Any

from rich import box
from rich.panel import Panel
from rich.table import Table

from rag.console import RAG_DEBUG, console
from rag.helpers import build_rerank_text
from rag.rerank import rerank, rerank_docs


def _expand_top_sources(
    repository: Any, session: Any, docs: list[Any], top_n: int = 3
) -> list[Any]:
    if not docs:
        return []

    expanded: dict[Any, Any] = {doc.id: doc for doc in docs[:10]}
    seen_urls: set[str] = set()
    expansion_rows: list[tuple[str, int]] = []

    for doc in docs[:top_n]:
        url = getattr(doc, "url", None)
        if getattr(doc, "type", "") not in {"web_page", "pdf"}:
            continue
        if not isinstance(url, str) or url in seen_urls:
            continue
        seen_urls.add(url)
        before = len(expanded)
        for chunk in repository.get_by_url(session, url):
            if chunk.id not in expanded:
                expanded[chunk.id] = chunk
        expansion_rows.append((url, len(expanded) - before))

    result = list(expanded.values())

    if RAG_DEBUG and expansion_rows:
        table = Table(box=box.SIMPLE, show_header=True)
        table.add_column("Source URL", style="white")
        table.add_column("Chunks added", style="green", justify="right")
        for url, count in expansion_rows:
            table.add_row(url[-70:], f"+{count}")
        console.print(Panel(
            table,
            title=f"[green]Smart Expansion[/green] → pool now [bold]{len(result)}[/bold] doc(s)",
            border_style="green",
            box=box.SIMPLE,
        ))

    return result


def execute_vector_intent(
    embedding_service: Any,
    repository: Any,
    session: Any,
    query: str,
    filters: dict[str, Any],
    parallel_mode: bool,
) -> list[Any]:
    if not query.strip():
        return []

    fetch_limit = 15 if parallel_mode else 30
    initial_docs = repository.vector_search(
        session,
        query_embedding=embedding_service.embed_text(query),
        query_text=query,
        filters=filters,
        limit=fetch_limit,
    )

    if RAG_DEBUG:
        console.print(f"  [bold]Vector search[/bold]  limit=[cyan]{fetch_limit}[/cyan]  →  [green]{len(initial_docs)} doc(s)[/green] retrieved")

    if not initial_docs:
        return []

    # Stage 1 — pre-expansion rerank
    pre_rank = rerank(query, [build_rerank_text(doc) for doc in initial_docs], len(initial_docs))
    ranked_initial: list[Any] = [
        initial_docs[item["index"]]
        for item in pre_rank
        if isinstance(item.get("index"), int) and 0 <= item["index"] < len(initial_docs)
    ]
    if not ranked_initial:
        ranked_initial = initial_docs

    if RAG_DEBUG:
        table = Table(box=box.SIMPLE, show_header=True)
        table.add_column("Rank", style="dim", width=5)
        table.add_column("Title", style="white")
        table.add_column("Type", style="cyan", width=10)
        for i, doc in enumerate(ranked_initial[:5]):
            marker = "[bold yellow]★[/bold yellow] " if i < 3 else "  "
            table.add_row(
                f"{marker}{i + 1}",
                str(getattr(doc, "title", "?"))[:60],
                str(getattr(doc, "type", "")).upper(),
            )
        console.print(Panel(
            table,
            title=f"[yellow]Pre-Expansion Rerank[/yellow] — True Top 3 identified (showing top 5 of {len(ranked_initial)})",
            border_style="yellow",
            box=box.SIMPLE,
        ))

    # Smart context expansion
    candidates = _expand_top_sources(repository, session, ranked_initial, top_n=3)

    # RERANK_INPUT_CAP = 75
    if len(candidates) > 75:
        priority_ids = {doc.id for doc in ranked_initial[:3]}
        priority = [doc for doc in candidates if doc.id in priority_ids]
        rest = [doc for doc in candidates if doc.id not in priority_ids]
        candidates = priority + rest[: max(0, 75 - len(priority))]
        if RAG_DEBUG:
            console.print(f"  [bold]Cap (75)[/bold]  priority=[cyan]{len(priority)}[/cyan]  rest=[cyan]{len(rest[:max(0, 75 - len(priority))])}[/cyan]  →  pool trimmed to [bold]{len(candidates)}[/bold]")

    # Stage 2 — final rerank
    top_k = 5 if parallel_mode else 10
    final = rerank_docs(query, candidates, top_k=top_k, include_language=True)

    if RAG_DEBUG:
        table = Table(box=box.SIMPLE, show_header=True)
        table.add_column("Score", style="magenta", width=7)
        table.add_column("Type", style="cyan", width=10)
        table.add_column("Title", style="green")
        for doc in final:
            score = f"{getattr(doc, 'score', 0.0):.3f}"
            table.add_row(score, str(getattr(doc, "type", "")).upper(), str(getattr(doc, "title", ""))[:60])
        console.print(Panel(
            table,
            title=f"[magenta]Final Rerank[/magenta] — top_k=[bold]{top_k}[/bold]  parallel=[bold]{parallel_mode}[/bold]  →  [bold]{len(final)} doc(s)[/bold] to context builder",
            border_style="magenta",
            box=box.SIMPLE,
        ))

    return final