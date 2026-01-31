from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_
from .base import BaseRepository
from ..models import Enrollment, EnrollmentStatus


class EnrollmentRepository(BaseRepository[Enrollment]):
    def __init__(self, session: Session):
        super().__init__(session, Enrollment)
    
    def get_student_enrollments(self, student_id: int, status: Optional[EnrollmentStatus] = None) -> List[Enrollment]:
        """Get all enrollments for a student, optionally filtered by status"""
        query = self.session.query(Enrollment).filter(Enrollment.student_id == student_id)
        if status:
            query = query.filter(Enrollment.status == status)
        return query.all()
    
    def get_section_enrollments(self, section_id: int, status: Optional[EnrollmentStatus] = None) -> List[Enrollment]:
        """Get all enrollments for a section, optionally filtered by status"""
        query = self.session.query(Enrollment).filter(Enrollment.section_id == section_id)
        if status:
            query = query.filter(Enrollment.status == status)
        return query.all()
    
    def get_enrollment(self, student_id: int, section_id: int) -> Optional[Enrollment]:
        """Get specific student enrollment in a section"""
        return (
            self.session.query(Enrollment)
            .filter(
                and_(
                    Enrollment.student_id == student_id,
                    Enrollment.section_id == section_id
                )
            )
            .first()
        )
    
    def update_grade(self, enrollment_id: int, grade_numeric: float, grade_letter: str) -> Optional[Enrollment]:
        """Update final grade for enrollment"""
        return self.update(
            enrollment_id,
            final_grade_numeric=grade_numeric,
            final_grade_letter=grade_letter
        )
    
    def drop_enrollment(self, enrollment_id: int) -> Optional[Enrollment]:
        """Change enrollment status to dropped"""
        return self.update(enrollment_id, status=EnrollmentStatus.DROPPED)
