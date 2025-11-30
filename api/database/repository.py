from typing import List
from sqlalchemy.orm import Session
from database.models import Course


class CourseRepository:
    """
    Data access layer for courses
    """
    
    def vector_search(self, db: Session, query_embedding: List[float], limit: int = 5) -> List[Course]:
        """
        Search courses by vector similarity
        
        Args:
            db: Database session
            query_embedding: Query vector
            limit: Max results
            
        Returns:
            List of courses with distance scores
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
    
    def get_by_id(self, db: Session, course_id: int) -> Course:
        """Get course by ID"""
        return db.query(Course).filter(Course.id == course_id).first()
    
    def get_all(self, db: Session, skip: int = 0, limit: int = 100) -> List[Course]:
        """Get all courses"""
        return db.query(Course).offset(skip).limit(limit).all()


def get_course_repository() -> CourseRepository:
    """Get course repository"""
    return CourseRepository()
