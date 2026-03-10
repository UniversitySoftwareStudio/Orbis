import re
from typing import Any

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from database.models import KnowledgeBase


class RAGRepository:
    def vector_search(
        self,
        db: Session,
        query_embedding: list[float],
        query_text: str = "",
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> list[KnowledgeBase]:
        stmt = select(KnowledgeBase).order_by(KnowledgeBase.embedding.l2_distance(query_embedding))
        if filters and filters.get("type"):
            stmt = stmt.where(KnowledgeBase.type == filters["type"])
        if filters and filters.get("code"):
            stmt = stmt.where(KnowledgeBase.title.ilike(f"{filters['code']}%"))

        vector_rows = list(db.scalars(stmt.limit(limit)).all())
        keyword_rows = self._keyword_search(db, query_text=query_text, filters=filters, limit=limit)

        seen: set[Any] = set()
        merged: list[KnowledgeBase] = []
        for doc in keyword_rows + vector_rows:
            if doc.id in seen:
                continue
            seen.add(doc.id)
            merged.append(doc)
        return merged

    def _keyword_search(
        self,
        db: Session,
        query_text: str,
        filters: dict[str, Any] | None,
        limit: int,
    ) -> list[KnowledgeBase]:
        clean = re.sub(r"[^\w\s]", " ", query_text or "")
        words = [word for word in clean.split() if len(word) > 2]
        if not words:
            return []

        stmt = (
            select(KnowledgeBase)
            .where(text("search_vector @@ to_tsquery('simple', :q)"))
            .order_by(text("ts_rank(search_vector, to_tsquery('simple', :q)) DESC"))
        )
        if filters and filters.get("type"):
            stmt = stmt.where(KnowledgeBase.type == filters["type"])
        return list(db.scalars(stmt.params(q=" | ".join(words)).limit(limit)).all())

    def get_by_url(self, db: Session, url: str) -> list[KnowledgeBase]:
        return list(db.scalars(select(KnowledgeBase).where(KnowledgeBase.url == url).order_by(KnowledgeBase.id)).all())

    def sql_filter(self, db: Session, filters: dict[str, Any] | None, limit: int = 20) -> list[KnowledgeBase]:
        if not filters:
            return []

        stmt = select(KnowledgeBase)
        if filters.get("type"):
            stmt = stmt.where(KnowledgeBase.type == str(filters["type"]).lower())

        if filters.get("code"):
            value = str(filters["code"])
            if "," in value:
                stmt = stmt.where(or_(*[KnowledgeBase.title.ilike(f"{code.strip()}%") for code in value.split(",")]))
            else:
                stmt = stmt.where(KnowledgeBase.title.ilike(f"{value}%"))

        is_course = filters.get("type") == "course" or "code" in filters
        rows = list(db.scalars(stmt.limit(limit * 3 if is_course else limit)).all())
        return self._dedupe_by_course_code(rows, limit) if is_course else rows

    @staticmethod
    def _dedupe_by_course_code(rows: list[KnowledgeBase], limit: int) -> list[KnowledgeBase]:
        seen_codes: set[str] = set()
        output: list[KnowledgeBase] = []
        for doc in rows:
            meta = getattr(doc, "metadata_", getattr(doc, "metadata", {})) or {}
            code = meta.get("course_code")
            if code and code in seen_codes:
                continue
            if code:
                seen_codes.add(code)
            output.append(doc)
        return output[:limit]


_repo = RAGRepository()


def get_rag_repository() -> RAGRepository:
    return _repo
