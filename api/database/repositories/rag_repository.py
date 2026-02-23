import re
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text, select, or_, func
from database.models import KnowledgeBase

class RAGRepository:
    def vector_search(self, db: Session, query_embedding: List[float], query_text: str = "", filters: Dict[str, Any] = None, limit: int = 10):
        """
        True Hybrid Search: Merges Vector Similarity (Semantic) with Pre-computed Keyword Search (Lexical).
        """
        
        # --- 1. SEMANTIC SEARCH (Vector) ---
        vector_stmt = select(KnowledgeBase).order_by(
            KnowledgeBase.embedding.l2_distance(query_embedding)
        )
        
        if filters:
            if filters.get("type"):
                vector_stmt = vector_stmt.where(KnowledgeBase.type == filters["type"])
            if filters.get("code"): 
                 vector_stmt = vector_stmt.where(KnowledgeBase.title.ilike(f"{filters['code']}%"))

        vector_results = db.scalars(vector_stmt.limit(limit)).all()

        # --- 2. LEXICAL SEARCH (Keyword / TSVector) ---
        keyword_results = []
        if query_text:
            # FIX: Use "OR" logic for long sentences to catch key terms like "Staj" (Internship)
            
            # 1. Clean punctuation (keep only alphanumeric)
            clean_text = re.sub(r'[^\w\s]', ' ', query_text)
            
            # 2. Split into words (filter out short words < 3 chars)
            words = [w for w in clean_text.split() if len(w) > 2]
            
            if words:
                # 3. Join with OR operator (|)
                # Example: "Staj | çalışmamı | tamamladım"
                or_query = " | ".join(words)
                
                # 4. Use to_tsquery with the OR string
                # This ensures documents matching *any* of the words are returned.
                keyword_stmt = select(KnowledgeBase).where(
                    text("search_vector @@ to_tsquery('simple', :q)")
                ).order_by(
                    text("ts_rank(search_vector, to_tsquery('simple', :q)) DESC")
                )
                
                if filters and filters.get("type"):
                    keyword_stmt = keyword_stmt.where(KnowledgeBase.type == filters["type"])
                
                keyword_results = db.scalars(keyword_stmt.params(q=or_query).limit(limit)).all()

        # --- 3. HYBRID FUSION (Deduplicate & Merge) ---
        seen_ids = set()
        final_results = []
        
        # Add Keyword Results first (High Precision / Specific Terms)
        for doc in keyword_results:
            if doc.id not in seen_ids:
                final_results.append(doc)
                seen_ids.add(doc.id)
                
        # Add Vector Results (High Recall / Concepts)
        for doc in vector_results:
            if doc.id not in seen_ids:
                final_results.append(doc)
                seen_ids.add(doc.id)
                
        return final_results

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