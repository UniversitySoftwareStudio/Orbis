from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from .base import BaseRepository
from ..models import Enrollment, EnrollmentStatus


class EnrollmentRepository(BaseRepository[Enrollment]):
    def __init__(self, session: Session):
        super().__init__(session, Enrollment)
    
    def get_student_enrollments(self, student_id: int, status: Optional[EnrollmentStatus] = None) -> List[Enrollment]:
        """Get all enrollments for a student, optionally filtered by status"""
        stmt = select(Enrollment).where(Enrollment.student_id == student_id)
        if status:
            stmt = stmt.where(Enrollment.status == status)
        return list(self.session.scalars(stmt).all())
    
    def get_section_enrollments(self, section_id: int, status: Optional[EnrollmentStatus] = None) -> List[Enrollment]:
        """Get all enrollments for a section, optionally filtered by status"""
        stmt = select(Enrollment).where(Enrollment.section_id == section_id)
        if status:
            stmt = stmt.where(Enrollment.status == status)
        return list(self.session.scalars(stmt).all())
    
    def get_enrollment(self, student_id: int, section_id: int) -> Optional[Enrollment]:
        """Get specific student enrollment in a section"""
        stmt = (
            select(Enrollment)
            .where(
                and_(
                    Enrollment.student_id == student_id,
                    Enrollment.section_id == section_id
                )
            )
        )
        return self.session.scalars(stmt).first()
    
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
    
    def register_student(self, student_id: int, section_id: int) -> Optional[Enrollment]:
        """
        Transactional operation to enroll a student in a section.
        Creates Enrollment record and increments CourseSection.current_enrollment.
        
        Returns:
            Enrollment object if successful, None if validation fails
        """
        from ..models import CourseSection
        from datetime import datetime
        
        # Check if already enrolled
        existing = self.get_enrollment(student_id, section_id)
        if existing:
            return None
        
        # Check section capacity
        stmt = select(CourseSection).where(CourseSection.id == section_id)
        section = self.session.scalars(stmt).first()
        if not section or section.current_enrollment >= section.max_enrollment:
            return None
        
        try:
            # Create enrollment
            enrollment = Enrollment(
                student_id=student_id,
                section_id=section_id,
                enrolled_at=datetime.utcnow(),
                status=EnrollmentStatus.ENROLLED
            )
            self.session.add(enrollment)
            
            # Increment section enrollment count
            section.current_enrollment += 1
            
            self.session.flush()
            self.session.refresh(enrollment)
            return enrollment
        except Exception as e:
            self.session.rollback()
            return None
    
    def withdraw_student(self, student_id: int, section_id: int) -> bool:
        """
        Transactional operation to withdraw a student from a section.
        Updates Enrollment.status to DROPPED and decrements CourseSection.current_enrollment.
        
        Returns:
            True if successful, False otherwise
        """
        from ..models import CourseSection
        
        enrollment = self.get_enrollment(student_id, section_id)
        if not enrollment or enrollment.status != EnrollmentStatus.ENROLLED:
            return False
        
        stmt = select(CourseSection).where(CourseSection.id == section_id)
        section = self.session.scalars(stmt).first()
        if not section:
            return False
        
        try:
            # Update enrollment status
            enrollment.status = EnrollmentStatus.DROPPED
            
            # Decrement section enrollment count
            if section.current_enrollment > 0:
                section.current_enrollment -= 1
            
            self.session.flush()
            return True
        except Exception as e:
            self.session.rollback()
            return False
    
    def is_student_enrolled(self, student_id: int, section_id: int) -> bool:
        """
        Check if student is currently enrolled in section.
        Validates enrollment exists and status is ENROLLED.
        """
        enrollment = self.get_enrollment(student_id, section_id)
        return enrollment is not None and enrollment.status == EnrollmentStatus.ENROLLED
    
    def get_completed_courses(self, student_id: int) -> List[int]:
        """
        Get list of course IDs that student has completed.
        Used for prerequisite checking.
        """
        from ..models import CourseSection
        
        stmt = (
            select(CourseSection.course_id)
            .join(Enrollment)
            .where(
                Enrollment.student_id == student_id,
                Enrollment.status == EnrollmentStatus.COMPLETED
            )
            .distinct()
        )
        completed = self.session.scalars(stmt).all()
        
        return list(completed)
