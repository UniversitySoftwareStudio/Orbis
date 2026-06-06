"""Response/request schemas for the student-facing 'My Regulations' page.

Surfaces the regulation-extraction pipeline's per-user rule assignments
(UserRuleAssignment joined to RegulationRule) to the end user.
"""

from datetime import date, datetime

from pydantic import BaseModel


class RuleAssignmentResponse(BaseModel):
    id: str
    urgency: str            # high | medium | low
    status: str             # active | dismissed | actioned
    reason: str
    assigned_at: datetime

    # Projected from the linked RegulationRule
    rule_text: str
    applies_to: str | None = None
    trigger: str | None = None
    deadline: str | None = None
    consequence: str | None = None
    authority: str | None = None
    blocking: bool = False
    valid_until: date | None = None


class RuleAssignmentStatusUpdate(BaseModel):
    status: str  # one of: active | dismissed | actioned
