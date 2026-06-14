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
    source_url: str | None = None
    evidence_quote: str | None = None
    blocking: bool = False
    valid_until: date | None = None


class RuleAssignmentStatusUpdate(BaseModel):
    status: str  # one of: active | dismissed | actioned


class RegulationRunSnapshot(BaseModel):
    run_id: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    sources_processed: int
    chunks_processed: int
    events_created: int
    error_message: str | None = None


class RegulationDiagnosticsResponse(BaseModel):
    user: dict[str, str | int]
    assignments: dict[str, int]
    rules: dict[str, int]
    events: dict[str, int]
    sources: dict[str, int]
    last_run: RegulationRunSnapshot | None = None
    last_run_events: dict[str, int]
    last_run_candidate_decisions: dict[str, int]
    last_run_candidate_reasons: dict[str, int]
    observations: list[str]
