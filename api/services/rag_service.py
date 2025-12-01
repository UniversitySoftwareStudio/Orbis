import time
from typing import List, Dict, Tuple, Iterator
from sqlalchemy.orm import Session
from database.repositories import get_course_repository
from services.embedding_service import get_embedding_service
from services.llm_service import LLMService


class RAGService:
    """
    RAG service for course search and recommendations.
    Orchestrates between embedding, LLM, and repository services.
    """

    def __init__(self):
        self.embedding_service = get_embedding_service()
        self.course_repository = get_course_repository()
        self.llm_service = LLMService()

    def search_courses(
        self, query: str, db: Session, limit: int = 5
    ) -> Tuple[List[Dict], Dict[str, float]]:
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

        embed_start = time.perf_counter()
        query_embedding = self.embedding_service.embed_text(query)
        timings["embedding_generation"] = round(
            (time.perf_counter() - embed_start) * 1000, 2
        )

        # Use repository for database access
        db_start = time.perf_counter()
        courses = self.course_repository.vector_search(db, query_embedding, limit)
        timings["vector_search"] = round((time.perf_counter() - db_start) * 1000, 2)

        # Format results
        format_start = time.perf_counter()
        results = []
        for course in courses:
            results.append(
                {
                    "id": course.id,
                    "code": course.code,
                    "name": course.name,
                    "description": course.description,
                    "keywords": course.keywords,
                    "similarity": round(
                        1 - course.distance, 4
                    ),  # Convert distance to similarity
                }
            )
        timings["result_formatting"] = round(
            (time.perf_counter() - format_start) * 1000, 2
        )

        return results, timings

    def stream_answer(
        self, query: str, db: Session, limit: int = 5
    ) -> Tuple[Iterator[str], List[Dict]]:
        """
        Stream answer to user query in real-time

        Args:
            query: User's search query
            db: Database session
            limit: Number of results to return

        Returns:
            Tuple of (streaming recommendation iterator, list of courses)
        """
        courses, _ = self.search_courses(query, db, limit)

        stream = self.llm_service.stream_recommendation(query, courses)

        return stream, courses
