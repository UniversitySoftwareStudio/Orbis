from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text, select, or_
from database.models import KnowledgeBase

class RAGRepository:
    def vector_search(self, db: Session, query_embedding: List[float], limit: int = 5):
        """Standard Vector Search using pgvector"""
        stmt = select(KnowledgeBase).order_by(
            KnowledgeBase.embedding.l2_distance(query_embedding)
        ).limit(limit)
        return db.scalars(stmt).all()

    def get_by_url(self, db: Session, url: str):
        """Fetch ALL chunks for a specific URL to reconstruct the document"""
        # Uses .url column (fixed from previous source_url bug)
        return db.scalars(
            select(KnowledgeBase)
            .where(KnowledgeBase.url == url)
            .order_by(KnowledgeBase.id)
        ).all()

    def sql_filter(self, db: Session, filters: Dict[str, Any], limit: int = 20):
        """The 'Admin' Tool: Strict filtering based on metadata"""
        query = select(KnowledgeBase)
        
        if filters.get("type"):
            query = query.where(KnowledgeBase.type == filters["type"].lower())
            
        if filters.get("code"):
            code_input = filters["code"]
            if "," in code_input:
                codes = [c.strip() for c in code_input.split(",")]
                conditions = [KnowledgeBase.title.ilike(f"%{c}%") for c in codes]
                query = query.where(or_(*conditions))
            else:
                query = query.where(KnowledgeBase.title.ilike(f"%{code_input}%"))

        if filters.get("title_like"):
            title_input = filters["title_like"]
            if "," in title_input:
                titles = [t.strip() for t in title_input.split(",")]
                conditions = [KnowledgeBase.title.ilike(f"%{t}%") for t in titles]
                query = query.where(or_(*conditions))
            else:
                query = query.where(KnowledgeBase.title.ilike(f"%{title_input}%"))

        return db.scalars(query.limit(limit)).all()

_repo = RAGRepository()
def get_rag_repository():
    return _repo