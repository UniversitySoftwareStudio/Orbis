from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..models import Enrollment, EnrollmentStatus, Student
from .base import BaseRepository


class StudentRepository(BaseRepository[Student]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Student)

    def get_by_student_id(self, student_id: str) -> Student | None:
        return self.get_one_by(student_id=student_id)

    def get_by_user_id(self, user_id: int) -> Student | None:
        return self.get_one_by(user_id=user_id)

    def get_with_enrollments(self, student_id: int) -> Student | None:
        return self.session.scalars(select(Student).options(joinedload(Student.enrollments)).where(Student.id == student_id)).first()

    def get_active_students(self) -> list[Student]:
        return self.filter_by(is_active=True)

    def calculate_gpa(self, student_id: int) -> float | None:
        stmt = select(func.avg(Enrollment.final_grade_numeric)).where(
            Enrollment.student_id == student_id,
            Enrollment.status == EnrollmentStatus.COMPLETED,
            Enrollment.final_grade_numeric.isnot(None),
        )
        result = self.session.scalar(stmt)
        return round(float(result), 2) if result is not None else None

    def update_gpa(self, student_id: int) -> Student | None:
        gpa = self.calculate_gpa(student_id)
        return self.update(student_id, gpa=gpa) if gpa is not None else None

    def get_transcript(self, student_id: int) -> list[dict[str, object]]:
        from ..models import AcademicTerm, Course, CourseSection

        rows = list(
            self.session.scalars(
                select(Enrollment)
                .join(CourseSection)
                .join(Course)
                .join(AcademicTerm)
                .where(Enrollment.student_id == student_id, Enrollment.status == EnrollmentStatus.COMPLETED)
                .order_by(AcademicTerm.year.desc(), AcademicTerm.term_type.desc())
            ).all()
        )

        return [
            {
                "course_code": row.section.course.code,
                "course_name": row.section.course.name,
                "term": f"{row.section.term.term_type.value} {row.section.term.year}",
                "credits": 3,
                "grade_letter": row.final_grade_letter,
                "grade_numeric": float(row.final_grade_numeric) if row.final_grade_numeric is not None else None,
            }
            for row in rows
        ]

    def check_academic_standing(self, student_id: int) -> dict[str, object]:
        student = self.get_by_id(student_id)
        if student is None:
            return {"eligible": False, "reason": "Student not found"}
        if not student.is_active:
            return {"eligible": False, "reason": "Student account is inactive"}
        if student.gpa is not None and student.gpa < 2.0:
            return {"eligible": False, "reason": f"GPA ({student.gpa}) below minimum 2.0 requirement"}
        return {"eligible": True, "reason": "Student in good standing"}

    def check_already_enrolled(self, student_id: int, section_id: int) -> bool:
        stmt = select(Enrollment).where(Enrollment.student_id == student_id, Enrollment.section_id == section_id)
        return self.session.scalars(stmt).first() is not None

    def get_current_enrollments(self, student_id: int) -> list[Enrollment]:
        stmt = select(Enrollment).where(
            Enrollment.student_id == student_id,
            Enrollment.status == EnrollmentStatus.ENROLLED,
        )
        return list(self.session.scalars(stmt).all())
