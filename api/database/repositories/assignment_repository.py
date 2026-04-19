from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .base import BaseRepository
from ..models import Assignment


class AssignmentRepository(BaseRepository[Assignment]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Assignment)

    def get_by_section(self, section_id: int, published_only: bool = True) -> list[Assignment]:
        stmt = select(Assignment).where(Assignment.section_id == section_id)
        if published_only:
            stmt = stmt.where(Assignment.is_published.is_(True))
        return list(self.session.scalars(stmt).all())

    def get_upcoming(self, section_id: int, days: int = 7) -> list[Assignment]:
        now = datetime.utcnow()
        cutoff = now + timedelta(days=days)
        stmt = (
            select(Assignment)
            .where(
                Assignment.section_id == section_id,
                Assignment.is_published.is_(True),
                Assignment.due_date <= cutoff,
                Assignment.due_date >= now,
            )
            .order_by(Assignment.due_date)
        )
        return list(self.session.scalars(stmt).all())

    def publish(self, assignment_id: int) -> Assignment | None:
        return self.update(assignment_id, is_published=True)

    def unpublish(self, assignment_id: int) -> Assignment | None:
        return self.update(assignment_id, is_published=False)

    def get_pending_assignments(self, student_id: int) -> list[Assignment]:
        from ..models import Enrollment, EnrollmentStatus

        now = datetime.utcnow()
        stmt = (
            select(Assignment)
            .join(Enrollment, Enrollment.section_id == Assignment.section_id)
            .where(
                Enrollment.student_id == student_id,
                Enrollment.status == EnrollmentStatus.ENROLLED,
                Assignment.is_published.is_(True),
                Assignment.due_date > now,
            )
            .order_by(Assignment.due_date)
        )
        return list(self.session.scalars(stmt).all())

    def validate_submission_window(self, assignment_id: int) -> dict[str, object]:
        assignment = self.get_by_id(assignment_id)
        if assignment is None:
            return {"open": False, "due_date": None, "message": "Assignment not found"}

        is_open = datetime.utcnow() <= assignment.due_date
        return {
            "open": is_open,
            "due_date": assignment.due_date,
            "message": "Submission window open" if is_open else "Submission deadline has passed",
        }

    def get_assignment_rubric(self, assignment_id: int) -> dict[str, object] | None:
        assignment = self.get_by_id(assignment_id)
        if assignment is None:
            return None

        return {
            "id": assignment.id,
            "title": assignment.title,
            "description": assignment.description,
            "max_points": float(assignment.max_points),
            "due_date": assignment.due_date,
            "is_published": assignment.is_published,
        }

    def get_overdue_assignments(self, section_id: int) -> list[Assignment]:
        stmt = (
            select(Assignment)
            .where(
                Assignment.section_id == section_id,
                Assignment.is_published.is_(True),
                Assignment.due_date < datetime.utcnow(),
            )
            .order_by(Assignment.due_date.desc())
        )
        return list(self.session.scalars(stmt).all())
