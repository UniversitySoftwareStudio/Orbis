from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, and_, func
from datetime import datetime
from .base import BaseRepository
from ..models import Student, Enrollment, EnrollmentStatus


class StudentRepository(BaseRepository[Student]):
    """Repository for Student entity with academic operations"""
    
    def __init__(self, session: Session):
        super().__init__(session, Student)
    
    def get_by_student_id(self, student_id: str) -> Optional[Student]:
        """Get student by student ID (e.g., 'STU12345')"""
        return self.get_one_by(student_id=student_id)
    
    def get_by_user_id(self, user_id: int) -> Optional[Student]:
        """Get student by linked user ID"""
        return self.get_one_by(user_id=user_id)
    
    def get_with_enrollments(self, student_id: int) -> Optional[Student]:
        """Get student with all enrollments loaded"""
        stmt = (
            select(Student)
            .options(joinedload(Student.enrollments))
            .where(Student.id == student_id)
        )
        return self.session.scalars(stmt).first()
    
    def get_active_students(self) -> List[Student]:
        """Get all active students"""
        return self.filter_by(is_active=True)
    
    def calculate_gpa(self, student_id: int) -> Optional[float]:
        """
        Calculate GPA from completed courses with numeric grades.
        Returns None if no completed courses.
        """
        stmt = (
            select(func.avg(Enrollment.final_grade_numeric))
            .where(
                and_(
                    Enrollment.student_id == student_id,
                    Enrollment.status == EnrollmentStatus.COMPLETED,
                    Enrollment.final_grade_numeric.isnot(None)
                )
            )
        )
        result = self.session.scalar(stmt)
        
        if result:
            return round(float(result), 2)
        return None
    
    def update_gpa(self, student_id: int) -> Optional[Student]:
        """Calculate and update student's GPA"""
        gpa = self.calculate_gpa(student_id)
        if gpa is not None:
            return self.update(student_id, gpa=gpa)
        return None
    
    def get_transcript(self, student_id: int) -> List[dict]:
        """
        Generate transcript: all completed enrollments with grades.
        Returns list of dicts with course info and grades.
        """
        from ..models import CourseSection, Course, AcademicTerm
        
        stmt = (
            select(Enrollment)
            .join(CourseSection)
            .join(Course)
            .join(AcademicTerm)
            .where(
                and_(
                    Enrollment.student_id == student_id,
                    Enrollment.status == EnrollmentStatus.COMPLETED
                )
            )
            .order_by(AcademicTerm.year.desc(), AcademicTerm.term_type.desc())
        )
        enrollments = list(self.session.scalars(stmt).all())
        
        transcript = []
        for enrollment in enrollments:
            section = enrollment.section
            transcript.append({
                'course_code': section.course.code,
                'course_name': section.course.name,
                'term': f"{section.term.term_type.value} {section.term.year}",
                'credits': 3,  # You may want to add this to Course model
                'grade_letter': enrollment.final_grade_letter,
                'grade_numeric': float(enrollment.final_grade_numeric) if enrollment.final_grade_numeric else None
            })
        
        return transcript
    
    def check_academic_standing(self, student_id: int) -> dict:
        """
        Check student's eligibility for registration based on GPA and active status.
        Returns dict with eligible flag and reason.
        """
        student = self.get_by_id(student_id)
        if not student:
            return {'eligible': False, 'reason': 'Student not found'}
        
        if not student.is_active:
            return {'eligible': False, 'reason': 'Student account is inactive'}
        
        if student.gpa is not None and student.gpa < 2.0:
            return {'eligible': False, 'reason': f'GPA ({student.gpa}) below minimum 2.0 requirement'}
        
        return {'eligible': True, 'reason': 'Student in good standing'}
    
    def check_already_enrolled(self, student_id: int, section_id: int) -> bool:
        """
        Check if student is already enrolled in this section.
        Prevents duplicate enrollments (enforces unique constraint).
        """
        stmt = (
            select(Enrollment)
            .where(
                and_(
                    Enrollment.student_id == student_id,
                    Enrollment.section_id == section_id
                )
            )
        )
        enrollment = self.session.scalars(stmt).first()
        return enrollment is not None
    
    def get_current_enrollments(self, student_id: int) -> List[Enrollment]:
        """Get all active (enrolled) enrollments for current term"""
        stmt = (
            select(Enrollment)
            .where(
                and_(
                    Enrollment.student_id == student_id,
                    Enrollment.status == EnrollmentStatus.ENROLLED
                )
            )
        )
        return list(self.session.scalars(stmt).all())
