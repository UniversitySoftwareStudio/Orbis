import time
import os
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session
from database.repositories import get_course_repository
from services.embedding_service import get_embedding_service
import google.generativeai as genai
import threading

class RAGService:
    """
    Simple RAG for course search using vector similarity.
    Service layer that orchestrates between embedding and repository.
    """
    
    def __init__(self):
        self.embedding_service = get_embedding_service()
        self.course_repository = get_course_repository()
        # Initialize Gemini
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self.intent_model = genai.GenerativeModel(model_name=os.getenv("INTENT_MODEL", "gemini-1.5-flash-002"))

    
    def _extract_keywords(self, user_query: str) -> str:
        """
        Uses Gemini Flash to extract technical keywords from the query.
        """
        prompt = (
            f"You are a search query optimizer for a university course database. "
            f"Analyze this user query: '{user_query}'. "
            f"Identify the user's intent and extract 5-10 core technical keywords, "
            f"concepts, or subject names relevant to this query. "
            f"Output ONLY the keywords separated by spaces. Do not include any introductory text."
        )
        
        try:
            response = self.intent_model.generate_content(prompt)
            # Clean the output just in case
            return response.text.strip()
        except Exception as e:
            # Fallback to original query if LLM fails to ensure system stability
            print(f"Keyword extraction failed: {e}")
            #throw error
            raise Exception("Keyword extraction failed")
            #return user_query
        

    def search_courses(self, query: str, db: Session, limit: int = 5) -> Tuple[List[Dict], Dict[str, float]]:
        """
        Semantic search for courses using embeddings with timing information
        
        Args:
            query: User's search query
            db: Database session
            limit: Number of results to return 
            
        Returns:
            Tuple of (list of courses with similarity scores, timing dict)
        """
        timings = {}

        # Intent detection & keyword extraction
        intent_start = time.perf_counter()
        optimized_query = self._extract_keywords(query)
        timings["intent_extraction"] = round((time.perf_counter() - intent_start) * 1000, 2)

        # Generate query embedding
        embed_start = time.perf_counter()
        query_embedding = self.embedding_service.embed_text(optimized_query)
        timings["embedding_generation"] = round((time.perf_counter() - embed_start) * 1000, 2)
        
        # Use repository for database access
        db_start = time.perf_counter()
        courses = self.course_repository.vector_search(db, query_embedding, limit)
        timings["vector_search"] = round((time.perf_counter() - db_start) * 1000, 2)
        
        # Format results
        format_start = time.perf_counter()
        results = []
        for course in courses:
            results.append({
                "id": course.id,
                "code": course.code,
                "name": course.name,
                "description": course.description,
                "keywords": course.keywords,
                "similarity": round(1 - course.distance, 4)  # Convert distance to similarity
            })
        timings["result_formatting"] = round((time.perf_counter() - format_start) * 1000, 2)

        
        return results, timings


# Singleton with thread-safe initialization
_rag_service = None
_rag_service_lock = threading.Lock()

def get_rag_service() -> RAGService:
    """Get or create RAG service (thread-safe)"""
    global _rag_service
    if _rag_service is None:
        with _rag_service_lock:
            # Double-check locking pattern
            if _rag_service is None:
                _rag_service = RAGService()
    return _rag_service
