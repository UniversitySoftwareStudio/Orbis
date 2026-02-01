from typing import List, Optional, Set
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select
from database.models import Course, CourseContent


class CourseRepository:
    """
    Repository for Course entity.
    Handles all database operations related to courses.
    """
    
    def __init__(self):
        pass
    
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
        # Note: Vector distance queries still use legacy API as pgvector integration
        # with SQLAlchemy 2.0 select() is limited
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
        stmt = select(Course).where(Course.code == code)
        return db.scalars(stmt).first()
    
    def search_by_keyword(self, db: Session, keyword: str, limit: int = 10) -> List[Course]:
        """Search courses by keyword (traditional text search)"""
        stmt = select(Course).where(Course.keywords.contains(keyword)).limit(limit)
        return list(db.scalars(stmt).all())
    
    def get_courses_with_embeddings(self, db: Session) -> List[Course]:
        """Get all courses that have embeddings"""
        stmt = select(Course).where(Course.embedding.isnot(None))
        return list(db.scalars(stmt).all())
    
    def get_syllabus(self, db: Session, course_id: int) -> List[CourseContent]:
        """
        Get structured weekly topics (CourseContent) for a course.
        Returns the learning roadmap ordered by week.
        """
        stmt = (
            select(CourseContent)
            .where(CourseContent.course_id == course_id)
            .order_by(CourseContent.week_number)
        )
        return list(db.scalars(stmt).all())
    
    def get_with_prerequisites(self, db: Session, course_id: int) -> Optional[Course]:
        """Get course with all prerequisite courses loaded"""
        stmt = (
            select(Course)
            .options(joinedload(Course.prerequisites))
            .where(Course.id == course_id)
        )
        return db.scalars(stmt).first()
    
    def check_prerequisites(self, db: Session, course_id: int, completed_course_ids: Set[int]) -> dict:
        """
        Recursively validate if all prerequisites are completed.
        
        Args:
            db: Database session
            course_id: Course to check prerequisites for
            completed_course_ids: Set of course IDs the student has completed
            
        Returns:
            dict with 'satisfied' bool and 'missing' list of course codes
        """
        course = self.get_with_prerequisites(db, course_id)
        if not course:
            return {'satisfied': False, 'missing': ['Course not found']}
        
        missing_prerequisites = []
        
        def check_recursive(prereq_course):
            # Check if this prerequisite is completed
            if prereq_course.id not in completed_course_ids:
                missing_prerequisites.append(prereq_course.code)
            
            # Recursively check prerequisites of prerequisites
            for nested_prereq in prereq_course.prerequisites:
                check_recursive(nested_prereq)
        
        # Check all direct prerequisites
        for prereq in course.prerequisites:
            check_recursive(prereq)
        
        return {
            'satisfied': len(missing_prerequisites) == 0,
            'missing': missing_prerequisites
        }
    
    def search_by_code_or_keyword(self, db: Session, search_term: str, limit: int = 10) -> List[Course]:
        """
        Search courses by code or keywords (traditional text search).
        Checks both Course.code and Course.keywords fields.
        """
        search_term_lower = search_term.lower()
        stmt = (
            select(Course)
            .where(
                (Course.code.ilike(f"%{search_term}%")) |
                (Course.keywords.ilike(f"%{search_term}%")) |
                (Course.name.ilike(f"%{search_term}%"))
            )
            .limit(limit)
        )
        return list(db.scalars(stmt).all())


def get_course_repository() -> CourseRepository:
    """Factory function to get course repository instance"""
    return CourseRepository()
