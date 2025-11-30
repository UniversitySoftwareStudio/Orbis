from typing import List, Optional
from sqlalchemy.orm import Session
from database.models import Course
from database.repositories.base import BaseRepository


class CourseRepository(BaseRepository[Course]):
    """
    Repository for Course entity.
    Handles all database operations related to courses.
    """
    
    def __init__(self):
        super().__init__(Course)
    
    def vector_search(self, db: Session, query_embedding: List[float], limit: int = 5) -> List[Course]:
        """
        Search courses by vector similarity using pgvector
        
        Args:
            db: Database session
            query_embedding: Query vector for semantic search
            limit: Maximum number of results
            
        Returns:
            List of courses ordered by similarity with distance attribute
        """
        results = db.query(
            Course,
            Course.embedding.cosine_distance(query_embedding).label('distance')
        ).filter(
            Course.embedding.isnot(None)
        ).order_by(
            'distance'
        ).limit(limit).all()
        
        # Add distance as attribute to each course
        courses_with_distance = []
        for course, distance in results:
            course.distance = distance
            courses_with_distance.append(course)
        
        return courses_with_distance
    
    def get_by_code(self, db: Session, code: str) -> Optional[Course]:
        """Get course by course code (e.g., 'CS101')"""
        return db.query(Course).filter(Course.code == code).first()
    
    def search_by_keyword(self, db: Session, keyword: str, limit: int = 10) -> List[Course]:
        """Search courses by keyword (traditional text search)"""
        return db.query(Course).filter(
            Course.keywords.contains(keyword)
        ).limit(limit).all()
    
    def get_courses_with_embeddings(self, db: Session) -> List[Course]:
        """Get all courses that have embeddings"""
        return db.query(Course).filter(Course.embedding.isnot(None)).all()


def get_course_repository() -> CourseRepository:
    """Factory function to get course repository instance"""
    return CourseRepository()
