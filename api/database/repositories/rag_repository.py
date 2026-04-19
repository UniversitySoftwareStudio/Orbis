from typing import Any

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from database.models import KnowledgeBase
from database.repositories.vector_search_repository import VectorSearchRepository


class RAGRepository:
    def __init__(self, vector_search_repository: VectorSearchRepository) -> None:
        self.vector_search_repository = vector_search_repository

    def vector_search(
        self,
        db: Session,
        query_embedding: list[float],
        query_text: str = "",
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> list[KnowledgeBase]:
        return self.vector_search_repository.search_legacy_l2(
            db=db,
            query_embedding=query_embedding,
            query_text=query_text,
            filters=filters,
            limit=limit,
        )

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


_vector_repo = VectorSearchRepository()
_repo = RAGRepository(vector_search_repository=_vector_repo)


def get_rag_repository() -> RAGRepository:
    return _repo
