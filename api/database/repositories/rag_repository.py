from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text, select, or_, func
from database.models import KnowledgeBase

class RAGRepository:
    def vector_search(self, db: Session, query_embedding: List[float], query_text: str = "", filters: Dict[str, Any] = None, limit: int = 35):
        """Hybrid Search: Vector Similarity + Exact Title Keyword Boosting"""
        
        # Base query
        stmt = select(KnowledgeBase)
        
        if filters:
            if filters.get("type"):
                stmt = stmt.where(KnowledgeBase.type == filters["type"].lower())
        
        # 1. Vector Distance Calculation
        vector_dist = KnowledgeBase.embedding.l2_distance(query_embedding)
        
        # 2. Lexical Boosting Logic (Requires PostgreSQL tsvector)
        # We clean the query text for basic keyword matching
        clean_keywords = " | ".join([word for word in query_text.split() if len(word) > 2])
        
        if clean_keywords:
            # Create a basic rank based on title matching
            # If the title contains the words, ts_rank increases
            lexical_rank = func.ts_rank(
                func.to_tsvector('english', KnowledgeBase.title), 
                func.to_tsquery('english', clean_keywords)
            )
            # Combine scores: lower distance is better, higher rank is better.
            # We subtract the rank from the distance to boost exact title matches.
            combined_score = vector_dist - (lexical_rank * 0.5) 
            stmt = stmt.order_by(combined_score)
        else:
            stmt = stmt.order_by(vector_dist)
            
        return db.scalars(stmt.limit(limit)).all()

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
        # Safety: Don't dump DB if no filters
        if not filters:
            return []
            
        stmt = select(KnowledgeBase)
        
        # Apply Filters
        if filters.get("type"):
            stmt = stmt.where(KnowledgeBase.type == filters["type"].lower())
        
        if filters.get("code"):
            # "Starts With" logic for Course Codes
            code_input = filters["code"]
            if "," in code_input:
                codes = [c.strip() for c in code_input.split(",")]
                conditions = [KnowledgeBase.title.ilike(f"{c}%") for c in codes]
                stmt = stmt.where(or_(*conditions))
            else:
                stmt = stmt.where(KnowledgeBase.title.ilike(f"{code_input}%"))

        # --- DEDUPLICATION LOGIC ---
        # If searching for courses, we expect EN/TR duplicates.
        # Strategy: Fetch 3x the limit, then filter by unique course_code in Python.
        is_course_search = filters.get("type") == "course" or "code" in filters
        
        effective_limit = limit * 3 if is_course_search else limit
        
        # Execute Query
        results = db.scalars(stmt.limit(effective_limit)).all()
        
        if is_course_search:
            unique_results = []
            seen_codes = set()
            
            for doc in results:
                # Safely access metadata
                meta = getattr(doc, "metadata_", getattr(doc, "metadata", {})) or {}
                c_code = meta.get("course_code")
                
                if c_code:
                    if c_code not in seen_codes:
                        unique_results.append(doc)
                        seen_codes.add(c_code)
                else:
                    # If no code exists (data issue), keep the doc to be safe
                    unique_results.append(doc)
            
            # Return only the requested amount of UNIQUE courses
            return unique_results[:limit]

        return results

_repo = RAGRepository()
def get_rag_repository():
    return _repo