from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..models import CourseSection, SectionStatus
from .base import BaseRepository


class SectionRepository(BaseRepository[CourseSection]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, CourseSection)

    def get_by_crn(self, crn: str) -> CourseSection | None:
        return self.get_one_by(crn=crn)

    def get_by_course_and_term(self, course_id: int, term_id: int) -> list[CourseSection]:
        stmt = select(CourseSection).where(CourseSection.course_id == course_id, CourseSection.term_id == term_id)
        return list(self.session.scalars(stmt).all())

    def get_with_enrollments(self, section_id: int) -> CourseSection | None:
        stmt = (
            select(CourseSection)
            .options(joinedload(CourseSection.enrollments))
            .where(CourseSection.id == section_id)
        )
        return self.session.scalars(stmt).first()

    def get_by_instructor(self, instructor_id: int, term_id: int | None = None) -> list[CourseSection]:
        stmt = select(CourseSection).where(CourseSection.instructor_id == instructor_id)
        if term_id is not None:
            stmt = stmt.where(CourseSection.term_id == term_id)
        return list(self.session.scalars(stmt).all())

    def increment_enrollment(self, section_id: int) -> bool:
        section = self.get_by_id(section_id)
        if section is None or section.current_enrollment >= section.max_enrollment:
            return False
        section.current_enrollment += 1
        self.session.commit()
        return True

    def decrement_enrollment(self, section_id: int) -> bool:
        section = self.get_by_id(section_id)
        if section is None or section.current_enrollment <= 0:
            return False
        section.current_enrollment -= 1
        self.session.commit()
        return True

    def check_capacity(self, section_id: int) -> bool:
        section = self.get_by_id(section_id)
        return section is not None and section.current_enrollment < section.max_enrollment

    def get_section_roster(self, section_id: int) -> list:
        from ..models import Enrollment, EnrollmentStatus, Student

        stmt = (
            select(Student)
            .join(Enrollment)
            .where(
                Enrollment.section_id == section_id,
                Enrollment.status == EnrollmentStatus.ENROLLED,
                Student.is_active.is_(True),
            )
        )
        return list(self.session.scalars(stmt).all())

    def validate_section_status(
        self,
        section_id: int,
        required_status: SectionStatus = SectionStatus.ACTIVE,
    ) -> bool:
        section = self.get_by_id(section_id)
        return section is not None and section.status == required_status

    def is_section_active(self, section_id: int) -> bool:
        return self.validate_section_status(section_id, SectionStatus.ACTIVE)

    def get_sections_by_status(self, status: SectionStatus, term_id: int | None = None) -> list[CourseSection]:
        stmt = select(CourseSection).where(CourseSection.status == status)
        if term_id is not None:
            stmt = stmt.where(CourseSection.term_id == term_id)
        return list(self.session.scalars(stmt).all())
