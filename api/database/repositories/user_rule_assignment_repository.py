from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..models import AssignmentStatus, UserRuleAssignment
from .base import BaseRepository


# Urgency ordering for stable "most important first" sorting.
_URGENCY_RANK = {"high": 0, "medium": 1, "low": 2}


class UserRuleAssignmentRepository(BaseRepository[UserRuleAssignment]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, UserRuleAssignment)

    def get_for_user(self, user_id: int) -> list[UserRuleAssignment]:
        """All rule assignments for a user, linked rule eagerly loaded,
        sorted by urgency (high first) then most-recently assigned."""
        rows = list(
            self.session.scalars(
                select(UserRuleAssignment)
                .options(joinedload(UserRuleAssignment.rule))
                .where(UserRuleAssignment.user_id == user_id)
            ).all()
        )
        rows.sort(
            key=lambda a: (
                _URGENCY_RANK.get(a.urgency.value, 99),
                -(a.assigned_at.timestamp() if a.assigned_at else 0),
            )
        )
        return rows

    def get_for_user_by_id(self, user_id: int, assignment_id) -> UserRuleAssignment | None:
        return self.session.scalars(
            select(UserRuleAssignment).where(
                UserRuleAssignment.id == assignment_id,
                UserRuleAssignment.user_id == user_id,
            )
        ).first()

    def count_active_for_user(self, user_id: int) -> int:
        return len(
            list(
                self.session.scalars(
                    select(UserRuleAssignment.id).where(
                        UserRuleAssignment.user_id == user_id,
                        UserRuleAssignment.status == AssignmentStatus.ACTIVE,
                    )
                ).all()
            )
        )

    def update_status(
        self, user_id: int, assignment_id, new_status: AssignmentStatus
    ) -> UserRuleAssignment | None:
        assignment = self.get_for_user_by_id(user_id, assignment_id)
        if assignment is None:
            return None
        assignment.status = new_status
        self.session.flush()
        self.session.refresh(assignment)
        return assignment
