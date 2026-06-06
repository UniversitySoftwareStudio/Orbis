"""'My Regulations' endpoints.

Surface the regulation-extraction pipeline's per-user rule assignments to the
authenticated user, and let the user mark an assignment actioned or dismissed.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.logging import get_logger
from database.models import AssignmentStatus, User, UserRuleAssignment
from database.repositories.user_rule_assignment_repository import UserRuleAssignmentRepository
from database.session import get_db
from dependencies import get_current_active_user
from schemas.regulations import RuleAssignmentResponse, RuleAssignmentStatusUpdate

router = APIRouter()
logger = get_logger(__name__)


def _to_response(assignment: UserRuleAssignment) -> RuleAssignmentResponse:
    rule = assignment.rule
    return RuleAssignmentResponse(
        id=str(assignment.id),
        urgency=assignment.urgency.value,
        status=assignment.status.value,
        reason=assignment.reason,
        assigned_at=assignment.assigned_at,
        rule_text=rule.rule_text if rule else "",
        applies_to=rule.applies_to if rule else None,
        trigger=rule.trigger if rule else None,
        deadline=rule.deadline if rule else None,
        consequence=rule.consequence if rule else None,
        authority=rule.authority if rule else None,
        blocking=bool(rule.blocking) if rule else False,
        valid_until=rule.valid_until if rule else None,
    )


@router.get("/regulations/me", response_model=list[RuleAssignmentResponse])
def get_my_regulations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[RuleAssignmentResponse]:
    assignments = UserRuleAssignmentRepository(db).get_for_user(current_user.id)
    return [_to_response(a) for a in assignments]


@router.patch("/regulations/assignments/{assignment_id}", response_model=RuleAssignmentResponse)
def update_my_regulation_status(
    assignment_id: str,
    payload: RuleAssignmentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> RuleAssignmentResponse:
    try:
        new_status = AssignmentStatus(payload.status.lower())
    except ValueError:
        allowed = ", ".join(s.value for s in AssignmentStatus)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Allowed: {allowed}",
        )

    try:
        assignment_uuid = uuid.UUID(assignment_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    repo = UserRuleAssignmentRepository(db)
    updated = repo.update_status(current_user.id, assignment_uuid, new_status)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    db.commit()
    return _to_response(updated)
