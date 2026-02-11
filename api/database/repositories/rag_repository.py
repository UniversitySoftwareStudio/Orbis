from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text, select, or_
from database.models import KnowledgeBase

class RagRepository:
    def vector_search(self, db: Session, query_embedding: List[float], limit: int = 5):
        """Standard Vector Search using pgvector"""
        # We use the <=> operator for Cosine Distance (lower is better)
        stmt = select(KnowledgeBase).order_by(
            KnowledgeBase.embedding.l2_distance(query_embedding)
        ).limit(limit)
        
        return db.scalars(stmt).all()

    def sql_filter(self, db: Session, filters: Dict[str, Any], limit: int = 20):
        """
        The 'Admin' Tool: Strict filtering based on metadata
        """
        query = select(KnowledgeBase)
        
        # Dynamic Filtering based on the Router's JSON output
        if filters.get("type"):
            safe_type = filters["type"].lower()
            query = query.where(KnowledgeBase.type == safe_type)
            
        if filters.get("faculty"):
            # Fuzzy match for faculty inside the JSONB metadata
            query = query.where(text("metadata->>'faculty' ILIKE :fac")).params(fac=f"%{filters['faculty']}%")
            
        if filters.get("year"):
            query = query.where(text("metadata->>'mentioned_years' LIKE :year")).params(year=f"%{filters['year']}%")

        if filters.get("code"):
            # For Course Codes (e.g., CMPE 101)
            code_input = filters["code"]
            if "," in code_input:
                # Split "CMPE 351, CMPE 321" -> ["CMPE 351", " CMPE 321"]
                codes = [c.strip() for c in code_input.split(",")]
                # Create OR logic: (title LIKE %351% OR title LIKE %321%)
                conditions = [KnowledgeBase.title.ilike(f"%{c}%") for c in codes]
                query = query.where(or_(*conditions))
            else:
                # Single code
                query = query.where(KnowledgeBase.title.ilike(f"%{code_input}%"))

        if filters.get("title_like"):
            # Partial title match (e.g., "Computer")
            title_input = filters["title_like"]
            if "," in title_input:
                titles = [t.strip() for t in title_input.split(",")]
                conditions = [KnowledgeBase.title.ilike(f"%{t}%") for t in titles]
                query = query.where(or_(*conditions))
            else:
                query = query.where(KnowledgeBase.title.ilike(f"%{title_input}%"))

        return db.scalars(query.limit(limit)).all()

# Singleton getter
_repo = RagRepository()
def get_rag_repository():
    return _repo