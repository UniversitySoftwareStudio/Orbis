import re
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from database.models import EmbeddingModel, KnowledgeBase, KnowledgeBaseEmbedding


class VectorSearchRepository:
    def search_legacy_l2(
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

    def _get_active_model(self, db: Session) -> EmbeddingModel | None:
        return db.scalars(
            select(EmbeddingModel).where(EmbeddingModel.is_active.is_(True)).limit(1)
        ).first()

    def _versioned_vector_rows(
        self,
        db: Session,
        query_embedding: list[float],
        model_id: int,
        filters: dict[str, Any] | None,
        limit: int,
    ) -> list[KnowledgeBase]:
        stmt = (
            select(KnowledgeBase)
            .join(KnowledgeBaseEmbedding, KnowledgeBaseEmbedding.kb_id == KnowledgeBase.id)
            .where(KnowledgeBaseEmbedding.model_id == model_id)
            .order_by(KnowledgeBaseEmbedding.embedding.cosine_distance(query_embedding))
        )
        if filters and filters.get("type"):
            stmt = stmt.where(KnowledgeBase.type == filters["type"])
        if filters and filters.get("code"):
            stmt = stmt.where(KnowledgeBase.title.ilike(f"{filters['code']}%"))
        return list(db.scalars(stmt.limit(limit)).all())

    def _legacy_vector_rows(
        self,
        db: Session,
        query_embedding: list[float],
        filters: dict[str, Any] | None,
        limit: int,
    ) -> list[KnowledgeBase]:
        stmt = select(KnowledgeBase).order_by(KnowledgeBase.embedding.cosine_distance(query_embedding))
        if filters and filters.get("type"):
            stmt = stmt.where(KnowledgeBase.type == filters["type"])
        if filters and filters.get("code"):
            stmt = stmt.where(KnowledgeBase.title.ilike(f"{filters['code']}%"))
        return list(db.scalars(stmt.limit(limit)).all())

    def search_knowledge_base(
        self,
        db: Session,
        query_embedding: list[float],
        query_text: str = "",
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> list[KnowledgeBase]:
        active_model = self._get_active_model(db)
        if active_model is not None:
            vector_rows = self._versioned_vector_rows(
                db=db,
                query_embedding=query_embedding,
                model_id=active_model.id,
                filters=filters,
                limit=limit,
            )
            if not vector_rows:
                vector_rows = self._legacy_vector_rows(db, query_embedding, filters, limit)
        else:
            vector_rows = self._legacy_vector_rows(db, query_embedding, filters, limit)
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
