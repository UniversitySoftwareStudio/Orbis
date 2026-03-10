import time
from collections.abc import Iterator
from typing import Any

from rich import box
from rich.panel import Panel
from rich.table import Table

from core.logging import get_logger
from database.repositories.rag_repository import get_rag_repository
from llm.service import get_llm_service
from rag.console import RAG_DEBUG, console
from rag.constants import ANSWER_PROMPT_TEMPLATE
from rag.context import build_context, deduplicate_docs, render_debug_table
from rag.helpers import doc_meta
from rag.retrieval import RetrievalEngine
from rag.router import route_query
from services.embedding_service import get_embedding_service
from sqlalchemy.orm import Session

logger = get_logger(__name__)


class RAGService:
    def __init__(self) -> None:
        self.embedding_service = get_embedding_service()
        self.repository = get_rag_repository()
        self.llm_service = get_llm_service()
        self.retrieval = RetrievalEngine(self.embedding_service, self.repository)

    def process_query(self, query: str, session: Session) -> Iterator[str]:
        t_start = time.perf_counter()

        intents = route_query(self.llm_service, query)
        t_routed = time.perf_counter()

        parallel_mode = len(intents) > 1
        docs: list[Any] = []
        for intent in intents:
            docs.extend(self.retrieval.execute_intent(session, intent, parallel_mode=parallel_mode))
        t_retrieved = time.perf_counter()

        context_docs = deduplicate_docs(docs)
        render_debug_table(intents, context_docs)

        if not context_docs:
            logger.warning("No docs found for query: %.80s", query)
            yield "I'm sorry, but I couldn't find any specific information."
            return

        prompt = ANSWER_PROMPT_TEMPLATE.format(query=query, context=build_context(intents, context_docs))

        yield from self.llm_service.generate(prompt)

        t_end = time.perf_counter()

        if RAG_DEBUG:
            table = Table(box=box.SIMPLE, show_header=False)
            table.add_column("Stage", style="dim")
            table.add_column("Duration", style="bold green", justify="right")
            table.add_row("Routing", f"{(t_routed - t_start) * 1000:.0f}ms")
            table.add_row("Retrieval", f"{(t_retrieved - t_routed) * 1000:.0f}ms")
            table.add_row("LLM stream", f"{(t_end - t_retrieved) * 1000:.0f}ms")
            table.add_row("Total", f"{(t_end - t_start) * 1000:.0f}ms")
            console.print(Panel(
                table,
                title="[dim]Query complete[/dim]",
                border_style="dim",
                box=box.SIMPLE,
            ))

    def search_courses(
        self,
        query: str,
        session: Session,
        limit: int = 5,
    ) -> tuple[list[dict[str, Any]], dict[str, float]]:
        start = time.perf_counter()
        query_embedding = self.embedding_service.embed_text(query)
        docs = self.repository.vector_search(
            session,
            query_embedding=query_embedding,
            query_text=query,
            filters={"type": "course"},
            limit=max(1, limit),
        )

        results: list[dict[str, Any]] = []
        for doc in docs:
            meta = doc_meta(doc)
            results.append(
                {
                    "id": str(doc.id),
                    "title": doc.title,
                    "url": getattr(doc, "url", None),
                    "code": meta.get("course_code"),
                    "type": doc.type,
                    "score": float(getattr(doc, "score", 0.0)),
                    "snippet": (doc.content or "")[:240],
                }
            )

        timings = {"total": round((time.perf_counter() - start) * 1000, 2)}
        return results, timings

    def stream_answer(
        self,
        query: str,
        session: Session,
        limit: int = 5,
    ) -> tuple[Iterator[str], list[dict[str, Any]]]:
        courses, _ = self.search_courses(query=query, session=session, limit=limit)

        if courses:
            context = "\n\n".join(
                f"Source: {course['title']}\nURL: {course.get('url') or 'N/A'}\nContent: {course.get('snippet') or ''}"
                for course in courses
            )
            prompt = ANSWER_PROMPT_TEMPLATE.format(query=query, context=context)
        else:
            prompt = f"The user asked: {query}. No matching courses were found. Respond helpfully and suggest refining the query."

        return self.llm_service.generate(prompt), courses