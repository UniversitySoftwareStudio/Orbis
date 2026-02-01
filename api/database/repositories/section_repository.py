from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, and_
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
        stmt = (
            select(CourseSection)
            .where(
                and_(
                    CourseSection.course_id == course_id,
                    CourseSection.term_id == term_id
                )
            )
        )
        return list(self.session.scalars(stmt).all())
    
    def get_with_enrollments(self, section_id: int) -> Optional[CourseSection]:
        """Get section with all enrollments"""
        stmt = (
            select(CourseSection)
            .options(joinedload(CourseSection.enrollments))
            .where(CourseSection.id == section_id)
        )
        return self.session.scalars(stmt).first()
    
    def get_by_instructor(self, instructor_id: int, term_id: Optional[int] = None) -> List[CourseSection]:
        """Get all sections taught by instructor, optionally filtered by term"""
        stmt = select(CourseSection).where(CourseSection.instructor_id == instructor_id)
        if term_id:
            stmt = stmt.where(CourseSection.term_id == term_id)
        return list(self.session.scalars(stmt).all())
    
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
    
    def check_capacity(self, section_id: int) -> bool:
        """
        Check if section has available seats.
        Returns True if current_enrollment < max_enrollment.
        """
        section = self.get_by_id(section_id)
        if not section:
            return False
        return section.current_enrollment < section.max_enrollment
    
    def get_section_roster(self, section_id: int) -> List:
        """
        Get all active students enrolled in this section.
        Returns list of Student objects for instructor dashboards.
        """
        from ..models import Student, Enrollment, EnrollmentStatus
        
        stmt = (
            select(Student)
            .join(Enrollment)
            .where(
                Enrollment.section_id == section_id,
                Enrollment.status == EnrollmentStatus.ENROLLED,
                Student.is_active == True
            )
        )
        return list(self.session.scalars(stmt).all())
    
    def validate_section_status(self, section_id: int, required_status: SectionStatus = SectionStatus.ACTIVE) -> bool:
        """
        Validate that section is in required status.
        Default checks for ACTIVE (not CANCELLED or SCHEDULED).
        """
        section = self.get_by_id(section_id)
        if not section:
            return False
        return section.status == required_status
    
    def is_section_active(self, section_id: int) -> bool:
        """Check if section status is ACTIVE"""
        return self.validate_section_status(section_id, SectionStatus.ACTIVE)
    
    def get_sections_by_status(self, status: SectionStatus, term_id: Optional[int] = None) -> List[CourseSection]:
        """Get all sections with specific status, optionally filtered by term"""
        stmt = select(CourseSection).where(CourseSection.status == status)
        if term_id:
            stmt = stmt.where(CourseSection.term_id == term_id)
        return list(self.session.scalars(stmt).all())
