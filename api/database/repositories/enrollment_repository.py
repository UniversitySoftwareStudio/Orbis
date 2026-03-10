from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..models import CourseSection, Enrollment, EnrollmentStatus
from .base import BaseRepository


class EnrollmentRepository(BaseRepository[Enrollment]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Enrollment)

    def get_student_enrollments(self, student_id: int, status: EnrollmentStatus | None = None) -> list[Enrollment]:
        stmt = select(Enrollment).where(Enrollment.student_id == student_id)
        if status is not None:
            stmt = stmt.where(Enrollment.status == status)
        return list(self.session.scalars(stmt).all())

    def get_section_enrollments(self, section_id: int, status: EnrollmentStatus | None = None) -> list[Enrollment]:
        stmt = select(Enrollment).where(Enrollment.section_id == section_id)
        if status is not None:
            stmt = stmt.where(Enrollment.status == status)
        return list(self.session.scalars(stmt).all())

    def get_enrollment(self, student_id: int, section_id: int) -> Enrollment | None:
        stmt = select(Enrollment).where(Enrollment.student_id == student_id, Enrollment.section_id == section_id)
        return self.session.scalars(stmt).first()

    def update_grade(self, enrollment_id: int, grade_numeric: float, grade_letter: str) -> Enrollment | None:
        return self.update(enrollment_id, final_grade_numeric=grade_numeric, final_grade_letter=grade_letter)

    def drop_enrollment(self, enrollment_id: int) -> Enrollment | None:
        return self.update(enrollment_id, status=EnrollmentStatus.DROPPED)

    def register_student(self, student_id: int, section_id: int) -> Enrollment | None:
        if self.get_enrollment(student_id, section_id) is not None:
            return None

        section = self._get_section(section_id)
        if section is None or section.current_enrollment >= section.max_enrollment:
            return None

        try:
            enrollment = Enrollment(
                student_id=student_id,
                section_id=section_id,
                enrolled_at=datetime.utcnow(),
                status=EnrollmentStatus.ENROLLED,
            )
            self.session.add(enrollment)
            section.current_enrollment += 1
            self.session.flush()
            self.session.refresh(enrollment)
            return enrollment
        except SQLAlchemyError:
            self.session.rollback()
            return None

    def withdraw_student(self, student_id: int, section_id: int) -> bool:
        enrollment = self.get_enrollment(student_id, section_id)
        section = self._get_section(section_id)
        if enrollment is None or section is None or enrollment.status != EnrollmentStatus.ENROLLED:
            return False

        try:
            enrollment.status = EnrollmentStatus.DROPPED
            section.current_enrollment = max(0, section.current_enrollment - 1)
            self.session.flush()
            return True
        except SQLAlchemyError:
            self.session.rollback()
            return False

    def is_student_enrolled(self, student_id: int, section_id: int) -> bool:
        enrollment = self.get_enrollment(student_id, section_id)
        return enrollment is not None and enrollment.status == EnrollmentStatus.ENROLLED

    def get_completed_courses(self, student_id: int) -> list[int]:
        stmt = (
            select(CourseSection.course_id)
            .join(Enrollment)
            .where(Enrollment.student_id == student_id, Enrollment.status == EnrollmentStatus.COMPLETED)
            .distinct()
        )
        return list(self.session.scalars(stmt).all())

    def _get_section(self, section_id: int) -> CourseSection | None:
        return self.session.scalars(select(CourseSection).where(CourseSection.id == section_id)).first()
