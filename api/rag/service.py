import time
from collections.abc import Iterator
from typing import Any
import json
import re
from types import SimpleNamespace

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
from services.embedding_service import get_embedding_service
from sqlalchemy import select, text
from sqlalchemy.orm import Session

logger = get_logger(__name__)


CHAT_RETRIEVAL_LIMIT = 4
CHAT_CANDIDATE_LIMIT = 80
CHAT_REASONING_CANDIDATE_LIMIT = 8
SAME_DOCUMENT_CHUNK_LIMIT = 5
FULL_DOCUMENT_CHAR_LIMIT = 9000

CHAT_STOPWORDS = {
    "a", "about", "again", "all", "already", "am", "an", "and", "any", "are", "as", "at",
    "be", "been", "being", "by", "can", "could", "did", "do", "does", "doing", "done",
    "for", "from", "get", "give", "had", "has", "have", "having", "how", "i", "if", "in",
    "instead", "is", "it", "me", "my", "next", "of", "on", "or", "our", "please", "show",
    "so", "take", "tell", "than", "that", "the", "their", "this", "to", "want", "was",
    "we", "were", "what", "when", "where", "whether", "which", "who", "why", "will",
    "with", "work", "would", "year", "you", "your",
    "bir", "bu", "da", "de", "diye", "icin", "için", "ile", "mi", "mı", "mu", "mü",
    "ne", "nasil", "nasıl", "ve", "veya",
}

CHAT_GENERIC_TERMS = {"course", "courses", "semester", "semesters", "class", "classes", "student", "students"}

CHAT_DOMAIN_TERMS = {
    "internship": {
        "anchors": {"internship", "internships", "staj"},
        "boost_terms": {
            "internship", "internships", "staj", "mandatory", "summer", "working", "days",
            "committee", "employer", "evaluation", "report", "completion", "completed",
            "following", "semester",
        },
        "negative_categories": {"registration", "calendar", "academic", "programs", "financial", "international"},
    },
    "registration": {
        "anchors": {"add", "drop", "registration", "withdraw", "withdrawal", "advisor"},
        "boost_terms": {"registration", "add", "drop", "withdraw", "deadline", "advisor", "section", "capacity"},
        "negative_categories": {"internship", "international", "financial"},
    },
    "erasmus": {
        "anchors": {"erasmus", "exchange", "mobility"},
        "boost_terms": {"erasmus", "exchange", "mobility", "learning", "agreement", "international", "application"},
        "negative_categories": {"internship", "registration", "financial"},
    },
    "calendar": {
        "anchors": {"calendar", "deadline", "date", "dates", "exam", "exams", "holiday"},
        "boost_terms": {"calendar", "deadline", "date", "dates", "exam", "exams", "registration", "semester"},
        "negative_categories": {"internship", "financial"},
    },
}


def _tokenize_query(query: str) -> list[str]:
    return re.findall(r"[0-9a-zA-ZçğıöşüÇĞİÖŞÜ]+", (query or "").lower())


def _term_variants(term: str) -> set[str]:
    variants = {term}
    if len(term) > 4 and term.endswith("ies"):
        variants.add(f"{term[:-3]}y")
    if len(term) > 3 and term.endswith("s"):
        variants.add(term[:-1])
    return variants


def _query_domains(tokens: list[str]) -> set[str]:
    token_set = set(tokens)
    domains: set[str] = set()
    for domain, config in CHAT_DOMAIN_TERMS.items():
        if token_set & config["anchors"]:
            domains.add(domain)
    return domains


def _expanded_query_terms(tokens: list[str]) -> list[str]:
    domains = _query_domains(tokens)
    terms: set[str] = set()

    for token in tokens:
        if len(token) <= 2 or token in CHAT_STOPWORDS:
            continue
        if token in CHAT_GENERIC_TERMS and domains:
            continue
        terms.update(_term_variants(token))

    for domain in domains:
        terms.update(CHAT_DOMAIN_TERMS[domain]["boost_terms"])

    token_set = set(tokens)
    if "internship" in domains and ({"done", "completed", "complete"} & token_set):
        terms.update({"completion", "completed", "after", "following", "report"})
    if "internship" in domains and "semester" in token_set:
        terms.update({"following", "semester", "report"})

    return sorted(terms)


def _doc_text(doc: Any) -> tuple[str, str, str, str]:
    title = (getattr(doc, "title", "") or "").lower()
    content = (getattr(doc, "content", "") or "").lower()
    category = (getattr(doc, "category", "") or "").lower()
    url = (getattr(doc, "url", "") or "").lower()
    return title, content, category, url


def _focused_source_doc(focused_source: dict[str, Any] | None) -> Any | None:
    if not focused_source:
        return None
    title = str(focused_source.get("title") or "").strip()
    url = str(focused_source.get("url") or "").strip()
    content = str(focused_source.get("content") or focused_source.get("snippet") or "").strip()
    if not title and not url and not content:
        return None
    return SimpleNamespace(
        title=title or url or "Selected source",
        url=url,
        content=content,
        type=focused_source.get("doc_type") or focused_source.get("type"),
        category=focused_source.get("category"),
        language=focused_source.get("language"),
    )


def _chunk_doc_wrapper(chunk: Any) -> Any:
    document = getattr(chunk, "document", None)
    return SimpleNamespace(
        id=f"chunk:{getattr(chunk, 'id', '')}",
        title=getattr(document, "title", None) or "University document",
        url=getattr(document, "source_url", None) or "",
        content=getattr(chunk, "content", "") or "",
        type="web_page",
        category="document",
        language=None,
        document_id=getattr(chunk, "document_id", None),
        chunk_id=getattr(chunk, "id", None),
        chunk_index=getattr(chunk, "chunk_index", None),
        _source_table="document_chunks",
    )


def _doc_key(doc: Any) -> tuple[str, str]:
    document_id = getattr(doc, "document_id", None)
    if document_id is not None:
        return ("document", str(document_id))
    url = getattr(doc, "url", None)
    if url:
        return ("url", str(url))
    return ("doc", str(getattr(doc, "id", id(doc))))


def _merge_relevant_chunks(doc: Any, chunks: list[Any], use_full_content: str | None = None) -> Any:
    if use_full_content is not None:
        content = use_full_content
    elif len(chunks) == 1:
        content = getattr(chunks[0], "content", "") or ""
    else:
        parts = []
        for index, chunk in enumerate(chunks, start=1):
            chunk_index = getattr(chunk, "chunk_index", None)
            label = f"Relevant chunk {index}" if chunk_index is None else f"Relevant chunk {index} (file chunk {chunk_index})"
            parts.append(f"--- {label} ---\n{getattr(chunk, 'content', '') or ''}")
        content = "\n\n".join(parts)

    return SimpleNamespace(
        id=getattr(doc, "id", None),
        title=getattr(doc, "title", "") or "University document",
        url=getattr(doc, "url", "") or "",
        content=content,
        type=getattr(doc, "type", None),
        category=getattr(doc, "category", None),
        language=getattr(doc, "language", None),
        document_id=getattr(doc, "document_id", None),
        expanded_chunk_count=len(chunks),
    )


def _score_chat_doc(doc: Any, query: str, terms: list[str], domains: set[str]) -> float:
    title, content, category, url = _doc_text(doc)
    combined = f"{title} {category} {url} {content}"
    score = 0.0

    for term in terms:
        if not term:
            continue
        if term in title:
            score += 8.0
        if term == category:
            score += 7.0
        elif term in category:
            score += 5.0
        if term in url:
            score += 3.0
        count = combined.count(term)
        if count:
            score += min(count, 4) * 1.4

    query_phrases = re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ]+ [a-zA-ZçğıöşüÇĞİÖŞÜ]+", query.lower())
    for phrase in query_phrases:
        if phrase in combined:
            score += 5.0

    for domain in domains:
        config = CHAT_DOMAIN_TERMS[domain]
        anchors = config["anchors"]
        anchor_hits = sum(1 for anchor in anchors if anchor in combined)
        if anchor_hits:
            score += 18.0 + (anchor_hits * 2.0)
        elif domains:
            score -= 20.0
        if category == domain:
            score += 14.0
        elif category in config["negative_categories"]:
            score -= 8.0

    return score


def _rank_chat_candidates(candidates: list[Any], query: str, terms: list[str], domains: set[str]) -> list[tuple[Any, float]]:
    scored = [
        (doc, _score_chat_doc(doc, query, terms, domains))
        for doc in candidates
    ]
    scored = [(doc, score) for doc, score in scored if score > 0]
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored


def _select_relevant_chat_docs(candidates: list[Any], query: str, terms: list[str], domains: set[str]) -> list[Any]:
    scored = _rank_chat_candidates(candidates, query, terms, domains)
    if not scored:
        return []

    best = scored[0][1]
    threshold = max(8.0, best * 0.42)
    selected = [doc for doc, score in scored if score >= threshold]
    return selected[:CHAT_RETRIEVAL_LIMIT]


class RAGService:
    def __init__(self) -> None:
        # The embedding service connects to TEI; defer it so chat still works
        # (LLM-only fallback) when the vector stack isn't running.
        self._embedding_service = None
        self._retrieval = None
        self.repository = get_rag_repository()
        self.llm_service = get_llm_service()

    @property
    def embedding_service(self):
        if self._embedding_service is None:
            self._embedding_service = get_embedding_service()
        return self._embedding_service

    @property
    def retrieval(self):
        if self._retrieval is None:
            self._retrieval = RetrievalEngine(self.embedding_service, self.repository)
        return self._retrieval

    def _reasoned_doc_selection(
        self,
        query: str,
        candidates: list[Any],
        terms: list[str],
        domains: set[str],
    ) -> list[Any]:
        ranked = _rank_chat_candidates(candidates, query, terms, domains)
        if not ranked:
            return []

        shortlist = ranked[:CHAT_REASONING_CANDIDATE_LIMIT]
        candidate_blocks = []
        for index, (doc, score) in enumerate(shortlist, start=1):
            title = getattr(doc, "title", "") or "Untitled"
            category = getattr(doc, "category", "") or "uncategorized"
            url = getattr(doc, "url", "") or ""
            content = (getattr(doc, "content", "") or "").replace("\n", " ").strip()
            candidate_blocks.append(
                f"[{index}] score={score:.1f}\n"
                f"Title: {title}\n"
                f"Category: {category}\n"
                f"URL: {url}\n"
                f"Excerpt: {content[:900]}"
            )

        prompt = (
            "You are the source-selection step of a university RAG agent. "
            "Read the user question and candidate official documents. Select ONLY documents "
            "that directly answer the question or provide necessary evidence for the answer. "
            "Reject documents that merely share generic words like course, semester, student, "
            "calendar, registration, or transfer. Prefer one precise source over several weak ones. "
            "Return strict JSON only, with this shape: "
            '{"selected":[{"index":1,"reason":"directly answers ..."}]}. '
            f"Select at most {CHAT_RETRIEVAL_LIMIT} documents. If none directly apply, use an empty list.\n\n"
            f"User question: {query}\n\n"
            "Candidates:\n"
            + "\n\n".join(candidate_blocks)
        )

        raw = self.llm_service.complete(prompt)
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not match:
            logger.warning("Document selector returned non-JSON: %.160s", raw)
            return _select_relevant_chat_docs(candidates, query, terms, domains)

        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            logger.warning("Document selector JSON parse failed: %.160s", raw)
            return _select_relevant_chat_docs(candidates, query, terms, domains)

        selected_indexes = payload.get("selected", [])
        selected_docs: list[Any] = []
        seen_indexes: set[int] = set()
        if isinstance(selected_indexes, list):
            for item in selected_indexes:
                index = item.get("index") if isinstance(item, dict) else item
                if not isinstance(index, int) or index < 1 or index > len(shortlist) or index in seen_indexes:
                    continue
                seen_indexes.add(index)
                selected_docs.append(shortlist[index - 1][0])
                if len(selected_docs) >= CHAT_RETRIEVAL_LIMIT:
                    break

        return selected_docs or _select_relevant_chat_docs(candidates, query, terms, domains)

    def _fetch_chunk_candidates(self, session: Session, terms: list[str]) -> list[Any]:
        if not terms:
            return []
        try:
            from database.models import DocumentChunk, UniversityDocument

            stmt = (
                select(DocumentChunk)
                .join(UniversityDocument)
                .where(text("to_tsvector('simple', coalesce(document_chunks.content,'') || ' ' || coalesce(university_documents.title,'')) @@ to_tsquery('simple', :q)"))
                .order_by(text("ts_rank(to_tsvector('simple', coalesce(document_chunks.content,'') || ' ' || coalesce(university_documents.title,'')), to_tsquery('simple', :q)) DESC"))
                .limit(CHAT_CANDIDATE_LIMIT)
            )
            chunks = list(session.scalars(stmt.params(q=" | ".join(terms))).all())
            return [_chunk_doc_wrapper(chunk) for chunk in chunks]
        except Exception as exc:
            logger.warning("Document chunk candidate search failed: %s", exc)
            return []

    def _expand_selected_documents(
        self,
        selected_docs: list[Any],
        query: str,
        session: Session,
        terms: list[str],
        domains: set[str],
    ) -> list[Any]:
        expanded: list[Any] = []
        seen: set[tuple[str, str]] = set()

        for selected in selected_docs:
            key = _doc_key(selected)
            if key in seen:
                continue
            seen.add(key)

            document_id = getattr(selected, "document_id", None)
            if document_id is not None:
                try:
                    from database.models import DocumentChunk, UniversityDocument

                    document = session.get(UniversityDocument, document_id)
                    if document and document.raw_content and len(document.raw_content) <= FULL_DOCUMENT_CHAR_LIMIT:
                        expanded.append(_merge_relevant_chunks(selected, [selected], use_full_content=document.raw_content))
                        continue

                    chunks = list(
                        session.scalars(
                            select(DocumentChunk)
                            .where(DocumentChunk.document_id == document_id)
                            .order_by(DocumentChunk.chunk_index)
                        ).all()
                    )
                    wrappers = [_chunk_doc_wrapper(chunk) for chunk in chunks]
                    ranked = _rank_chat_candidates(wrappers, query, terms, domains)
                    top_chunks = [doc for doc, _score in ranked[:SAME_DOCUMENT_CHUNK_LIMIT]]
                    if not top_chunks and wrappers:
                        top_chunks = wrappers[:SAME_DOCUMENT_CHUNK_LIMIT]
                    expanded.append(_merge_relevant_chunks(selected, top_chunks or [selected]))
                    continue
                except Exception as exc:
                    logger.warning("Same-document chunk expansion failed: %s", exc)

            url = getattr(selected, "url", None)
            if url:
                try:
                    from database.models import KnowledgeBase

                    siblings = list(session.scalars(select(KnowledgeBase).where(KnowledgeBase.url == url)).all())
                    if len(siblings) > 1:
                        total_content = "\n\n".join((sibling.content or "") for sibling in siblings)
                        if len(total_content) <= FULL_DOCUMENT_CHAR_LIMIT:
                            expanded.append(_merge_relevant_chunks(selected, siblings, use_full_content=total_content))
                        else:
                            ranked = _rank_chat_candidates(siblings, query, terms, domains)
                            top_chunks = [doc for doc, _score in ranked[:SAME_DOCUMENT_CHUNK_LIMIT]] or siblings[:SAME_DOCUMENT_CHUNK_LIMIT]
                            expanded.append(_merge_relevant_chunks(selected, top_chunks))
                        continue
                except Exception as exc:
                    logger.warning("Same-URL source expansion failed: %s", exc)

            expanded.append(selected)

        return expanded or selected_docs

    def process_query_events(
        self,
        query: str,
        session: Session,
        current_user: User | None = None,
        focused_source: dict[str, Any] | None = None,
    ):
        """Agentic RAG that streams its work as structured events:
          {"type": "step", ...} narration   {"type": "source", ...} a cited doc
          {"type": "chunk", "text": ...}     {"type": "done", "sources": [...]}
        Uses full-text keyword search (no embedding stack needed) so it works in
        the demo and cites REAL documents from knowledge_base with their URLs.
        """
        from database.models import KnowledgeBase

        yield {"type": "step", "message": "Understanding your question"}

        focused_doc = _focused_source_doc(focused_source)
        if focused_doc is not None:
            yield {
                "type": "step",
                "message": "Using the selected official source",
                "detail": getattr(focused_doc, "title", None),
            }
            docs = [focused_doc]
            sources = []
            for d in docs:
                src = {"title": d.title, "url": d.url, "doc_type": d.type,
                       "category": d.category, "language": d.language,
                       "snippet": (d.content or "")[:160].strip(),
                       "content": d.content or ""}
                sources.append(src)
                yield {"type": "source", **src}
            yield {"type": "step", "message": "Reasoning within the selected document"}

            prompt = (
                "You are Orbis, the academic assistant for Istanbul Bilgi University. "
                "The student is asking while viewing the selected official source below. "
                "Answer using this source first and do not pull in unrelated documents. "
                "If the source does not explicitly answer the question, say exactly what it does say, "
                "what remains unclear, and who the student should contact. Cite the selected source as [1].\n\n"
                f"[Source 1] {focused_doc.title} ({focused_doc.url})\n{focused_doc.content}\n\n"
                f"Student question: {query}"
            )
            for chunk in self.llm_service.generate(prompt):
                yield {"type": "chunk", "text": chunk}
            yield {"type": "done", "sources": sources}
            return

        tokens = _tokenize_query(query)
        domains = _query_domains(tokens)
        terms = _expanded_query_terms(tokens)
        yield {"type": "step", "message": "Selecting the official source scope",
               "detail": "focused global retrieval" if not domains else " · ".join(sorted(domains))}

        docs: list[Any] = []
        candidates: list[Any] = []
        if terms:
            try:
                stmt = (
                    select(KnowledgeBase)
                    .where(text("search_vector @@ to_tsquery('simple', :q)"))
                    .order_by(text("ts_rank(search_vector, to_tsquery('simple', :q)) DESC"))
                    .limit(CHAT_CANDIDATE_LIMIT)
                )
                candidates = list(session.scalars(stmt.params(q=" | ".join(terms))).all())
            except Exception as exc:
                logger.warning("Keyword search failed: %s", exc)
            candidates.extend(self._fetch_chunk_candidates(session, terms))
        if not candidates:
            candidates = list(session.scalars(select(KnowledgeBase).limit(CHAT_CANDIDATE_LIMIT)).all())
        deduped_candidates: list[Any] = []
        seen_candidate_keys: set[tuple[str, str]] = set()
        for candidate in candidates:
            key = (str(getattr(candidate, "id", "")), str(getattr(candidate, "url", "")))
            if key in seen_candidate_keys:
                continue
            seen_candidate_keys.add(key)
            deduped_candidates.append(candidate)
        candidates = deduped_candidates
        if candidates:
            yield {"type": "step", "message": "Reasoning over candidate documents",
                   "detail": f"{min(len(candidates), CHAT_REASONING_CANDIDATE_LIMIT)} candidates"}
            docs = self._reasoned_doc_selection(query, candidates, terms, domains)
            expanded_docs = self._expand_selected_documents(docs, query, session, terms, domains)
            if expanded_docs and expanded_docs != docs:
                docs = expanded_docs
                yield {"type": "step", "message": "Expanding selected document context",
                       "detail": f"top {SAME_DOCUMENT_CHUNK_LIMIT} same-file chunks or full document"}

        # Add SIS (calendar/schedule) structured context if relevant.
        intents = route_query(self.llm_service, query)
        sis_context, _ = build_sis_context(intents, current_user, session)

        sources = []
        if docs:
            yield {"type": "step", "message": f"Found {len(docs)} highly relevant official source{'s' if len(docs) != 1 else ''}"}
            for d in docs:
                src = {"title": d.title, "url": d.url, "doc_type": d.type,
                       "category": d.category, "language": d.language,
                       "snippet": (d.content or "")[:160].strip(),
                       "content": d.content or ""}
                sources.append(src)
                yield {"type": "source", **src}
            yield {"type": "step", "message": "Reading the sources and composing a grounded answer"}
        else:
            yield {"type": "step", "message": "No exact source match — answering from general guidance"}

        # Build a grounded prompt from the real document content.
        if docs:
            context = "\n\n".join(
                f"[Source {i+1}] {d.title} ({d.url})\n{d.content}" for i, d in enumerate(docs)
            )
            if sis_context:
                context = sis_context + "\n\n" + context
            prompt = (
                "You are Orbis, the academic assistant for Istanbul Bilgi University. "
                "Answer the student's question using ONLY the sources below. Be concise and "
                "practical, answer in the student's language, and cite sources inline as "
                "[1], [2] matching their order. If the sources don't fully cover it, say so.\n\n"
                f"Sources:\n{context}\n\nStudent question: {query}"
            )
        else:
            ctx = (sis_context + "\n\n") if sis_context else ""
            prompt = (
                "You are Orbis, the academic assistant for Istanbul Bilgi University. "
                "Answer helpfully and concisely in the student's language. Give practical "
                "guidance and point to the relevant office for exact current rules. Do not "
                "invent specific dates, names, or numbers.\n\n"
                f"{ctx}Student question: {query}"
            )

        for chunk in self.llm_service.generate(prompt):
            yield {"type": "chunk", "text": chunk}
        yield {"type": "done", "sources": sources}

    def process_query(self, query: str, session: Session, current_user: User | None = None) -> Iterator[str]:
        t_start = time.perf_counter()

        intents = route_query(self.llm_service, query)
        sis_context, intents = build_sis_context(intents, current_user, session)
        t_routed = time.perf_counter()

        parallel_mode = RAG_PARALLEL_MODE and len(intents) > 1
        docs: list[Any] = []
        # Vector retrieval needs the TEI embedding stack. If it's unavailable,
        # fall back to answering directly from the question + any SIS context.
        try:
            for intent in intents:
                docs.extend(self.retrieval.execute_intent(session, intent, parallel_mode=parallel_mode))
        except Exception as exc:
            logger.warning("Retrieval unavailable, answering LLM-only: %s", exc)
            docs = []
        t_retrieved = time.perf_counter()

        context_docs = deduplicate_docs(docs)
        render_debug_table(intents, context_docs)

        if not context_docs and not sis_context:
            # No retrieval and no structured context — answer from the model
            # directly so the assistant still responds in a demo setting.
            prompt = (
                "You are Orbis, the academic assistant for Istanbul Bilgi University. "
                "Answer the student's question helpfully and concisely in their language. "
                "Give practical, general guidance about university procedures (Erasmus, "
                "internships, registration, regulations, calendar). If something depends on "
                "the exact current regulation, say so and point them to the relevant office "
                "or official page. Do not invent specific dates, names, or numbers.\n\n"
                f"Student question: {query}"
            )
            yield from self.llm_service.generate(prompt)
            return

        context = build_context(intents, context_docs)
        if sis_context:
            context = sis_context + "\n\n" + context if context else sis_context

        prompt = ANSWER_PROMPT_TEMPLATE.format(query=query, context=context)

        if RAG_STREAM_ENABLED:
            yield from self.llm_service.generate(prompt)
        else:
            full_response = "".join(self.llm_service.generate(prompt))
            yield full_response

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
