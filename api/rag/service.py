import time
from collections.abc import Iterator
from typing import Any

from rich import box
from rich.panel import Panel
from rich.table import Table

from core.logging import get_logger
from database.models import User
from database.repositories.rag_repository import get_rag_repository
from llm.service import get_llm_service
from rag.config import RAG_PARALLEL_MODE, RAG_STREAM_ENABLED
from rag.console import RAG_DEBUG, console
from rag.constants import ANSWER_PROMPT_TEMPLATE
from rag.context import build_context, deduplicate_docs, render_debug_table
from rag.context_injectors import build_sis_context
from rag.helpers import doc_meta
from rag.retrieval import RetrievalEngine
from rag.router import route_query
from rag.eval_logger import init_eval_state, get_eval_state, write_eval_log, register_chunks, append_search_log
from services.embedding_service import get_embedding_service
from sqlalchemy.orm import Session

logger = get_logger(__name__)


class RAGService:
    def __init__(self) -> None:
        self.embedding_service = get_embedding_service()
        self.repository = get_rag_repository()
        self.llm_service = get_llm_service()
        self.retrieval = RetrievalEngine(self.embedding_service, self.repository)

    def process_query(self, query: str, session: Session, current_user: User | None = None) -> Iterator[str]:
        t_start = time.perf_counter()
        init_eval_state(query) # Initialize evaluation logger

        intents = route_query(self.llm_service, query)
        sis_context, intents = build_sis_context(intents, current_user, session)
        t_routed = time.perf_counter()

        parallel_mode = RAG_PARALLEL_MODE and len(intents) > 1
        docs: list[Any] = []
        for i, intent in enumerate(intents):
            intent_docs = self.retrieval.execute_intent(session, intent, parallel_mode=parallel_mode)
            
            # Register documents and log SQL intents directly
            register_chunks(intent_docs)
            if str(intent.get("tool", "")).lower() == "sql":
                sql_ids = [str(d.id) for d in intent_docs]
                append_search_log(f"search_{i+1}_sql", sql_ids, sql_ids)
                
            docs.extend(intent_docs)
        t_retrieved = time.perf_counter()

        context_docs = deduplicate_docs(docs)
        
        # Log the final cross-search document order
        eval_state = get_eval_state()
        eval_state["retrieval_and_reranking_phase"]["second_reranking_final_order_ids"] = [str(d.id) for d in context_docs]

        render_debug_table(intents, context_docs)

        if not context_docs and not sis_context:
            logger.warning("No docs found for query: %.80s", query)
            yield "I'm sorry, but I couldn't find any specific information."
            return

        context = build_context(intents, context_docs)
        if sis_context:
            context = sis_context + "\n\n" + context if context else sis_context

        prompt = ANSWER_PROMPT_TEMPLATE.format(query=query, context=context)

        # Capture the state reference locally before crossing the yield thread boundary
        current_eval_state = get_eval_state()
        current_eval_state["generation_phase"]["context_token_count"] = len(context) // 4

        full_response_chunks = []
        try:
            if RAG_STREAM_ENABLED:
                for chunk in self.llm_service.generate(prompt):
                    full_response_chunks.append(chunk)
                    yield chunk
            else:
                full_response = "".join(self.llm_service.generate(prompt))
                full_response_chunks.append(full_response)
                yield full_response
        finally:
            t_end = time.perf_counter()
            
            # Use the preserved local state reference instead of querying the ContextVar
            current_eval_state["generation_phase"]["final_response"] = "".join(full_response_chunks)
            write_eval_log(current_eval_state)

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