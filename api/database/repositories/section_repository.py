from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_
from .base import BaseRepository
from ..models import CourseSection, SectionStatus


class SectionRepository(BaseRepository[CourseSection]):
    def __init__(self, session: Session):
        super().__init__(session, CourseSection)
    
    def get_by_crn(self, crn: str) -> Optional[CourseSection]:
        """Get section by CRN"""
        return self.get_one_by(crn=crn)
    
    def get_by_course_and_term(self, course_id: int, term_id: int) -> List[CourseSection]:
        """Get all sections for a course in a term"""
        return (
            self.session.query(CourseSection)
            .filter(
                and_(
                    CourseSection.course_id == course_id,
                    CourseSection.term_id == term_id
                )
            )
            .all()
        )
    
    def get_with_enrollments(self, section_id: int) -> Optional[CourseSection]:
        """Get section with all enrollments"""
        return (
            self.session.query(CourseSection)
            .options(joinedload(CourseSection.enrollments))
            .filter(CourseSection.id == section_id)
            .first()
        )
    
    def get_by_instructor(self, instructor_id: int, term_id: Optional[int] = None) -> List[CourseSection]:
        """Get all sections taught by instructor, optionally filtered by term"""
        query = self.session.query(CourseSection).filter(CourseSection.instructor_id == instructor_id)
        if term_id:
            query = query.filter(CourseSection.term_id == term_id)
        return query.all()
    
    def increment_enrollment(self, section_id: int) -> bool:
        """Increment current enrollment count"""
        section = self.get_by_id(section_id)
        if not section or section.current_enrollment >= section.max_enrollment:
            return False
        
        section.current_enrollment += 1
        self.session.commit()
        return True
    
    def decrement_enrollment(self, section_id: int) -> bool:
        """Decrement current enrollment count"""
        section = self.get_by_id(section_id)
        if not section or section.current_enrollment <= 0:
            return False
        
        section.current_enrollment -= 1
        self.session.commit()
        return True
