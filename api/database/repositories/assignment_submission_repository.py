from sqlalchemy import select
from sqlalchemy.orm import Session

from .base import BaseRepository
from ..models import AssignmentSubmission


class AssignmentSubmissionRepository(BaseRepository[AssignmentSubmission]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, AssignmentSubmission)

    def get_by_student_and_assignment(self, student_id: int, assignment_id: int) -> AssignmentSubmission | None:
        return self.session.scalars(
            select(AssignmentSubmission).where(
                AssignmentSubmission.student_id == student_id,
                AssignmentSubmission.assignment_id == assignment_id,
            )
        ).first()

    def get_by_student(self, student_id: int) -> list[AssignmentSubmission]:
        return list(
            self.session.scalars(
                select(AssignmentSubmission)
                .where(AssignmentSubmission.student_id == student_id)
                .order_by(AssignmentSubmission.submitted_at.desc())
            ).all()
        )

