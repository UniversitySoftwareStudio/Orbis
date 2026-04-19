from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.logging import get_logger
from database.models import (
    AssignmentStatus,
    Event,
    EventAgentLog,
    EventCandidateLog,
    EventRun,
    EventRunStatus,
    EventStatus,
    User,
    UserRuleAssignment,
)
from database.session import SessionLocal, get_db
from dependencies import get_current_active_user, require_admin
from events.orchestrator import RuleExtractionOrchestrator
from events.user_agent import run_for_all_users, run_for_user

router = APIRouter()
logger = get_logger(__name__)


class TriggerResponse(BaseModel):
    run_id: str
    status: str


class RunStatusResponse(BaseModel):
    run_id: str
    status: str
    sources_processed: int
    chunks_processed: int
    events_created: int
    events_pending: int = 0
    events_needs_review: int = 0
    last_category: str | None = None
    error_message: str | None = None


class AgentLogResponse(BaseModel):
    id: str
    run_id: str
    source_key: str | None
    agent: str
    state: str
    decision: str
    reason: str | None
    payload: dict[str, object]
    created_at: str


class CandidateLogResponse(BaseModel):
    id: str
    run_id: str
    source_key: str | None
    source_url: str
    category: str
    parent_category: str
    target_role: str
    candidate_hash: str
    decision: str
    reason_code: str
    metrics: dict[str, object]
    created_at: str
    candidate_text: str


def _run_pipeline_background(run_id: str) -> None:
    db = SessionLocal()
    try:
        RuleExtractionOrchestrator().run(db)
    finally:
        db.close()


@router.post("/events/trigger", response_model=TriggerResponse)
def trigger_events(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> TriggerResponse:
    run = EventRun(status=EventRunStatus.RUNNING)
    db.add(run)
    db.commit()
    db.refresh(run)
    background_tasks.add_task(_run_pipeline_background, str(run.id))
    return TriggerResponse(run_id=str(run.id), status=run.status.value)


@router.get("/events/runs/{run_id}", response_model=RunStatusResponse)
def get_run_status(
    run_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> RunStatusResponse:
    run = db.get(EventRun, run_id)
    if run is None:
        return RunStatusResponse(
            run_id=run_id,
            status="not_found",
            sources_processed=0,
            chunks_processed=0,
            events_created=0,
            events_pending=0,
            events_needs_review=0,
            error_message="run not found",
        )

    pending_count = (
        db.query(Event.id)
        .filter(Event.run_id == run.id, Event.status == EventStatus.PENDING)
        .count()
    )
    review_count = (
        db.query(Event.id)
        .filter(Event.run_id == run.id, Event.status == EventStatus.NEEDS_REVIEW)
        .count()
    )

    return RunStatusResponse(
        run_id=str(run.id),
        status=run.status.value,
        sources_processed=run.sources_processed,
        chunks_processed=run.chunks_processed,
        events_created=run.events_created,
        events_pending=pending_count,
        events_needs_review=review_count,
        last_category=run.last_category,
        error_message=run.error_message,
    )


@router.get("/events/runs/{run_id}/telemetry", response_model=list[AgentLogResponse])
def get_run_telemetry(
    run_id: str,
    limit: int = 200,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> list[AgentLogResponse]:
    safe_limit = min(max(limit, 1), 2000)
    logs = (
        db.query(EventAgentLog)
        .filter(EventAgentLog.run_id == run_id)
        .order_by(EventAgentLog.created_at.asc())
        .limit(safe_limit)
        .all()
    )
    return [
        AgentLogResponse(
            id=str(item.id),
            run_id=str(item.run_id),
            source_key=item.source_key,
            agent=item.agent.value,
            state=item.state,
            decision=item.decision,
            reason=item.reason,
            payload=item.payload or {},
            created_at=item.created_at.isoformat(),
        )
        for item in logs
    ]


class AssignmentResponse(BaseModel):
    id: str
    rule_id: str
    rule_text: str
    applies_to: str
    trigger: str | None
    deadline: str | None
    valid_from: str | None
    valid_until: str | None
    blocking: bool
    consequence: str | None
    authority: str | None
    exceptions: str | None
    match_type: str
    urgency: str
    status: str
    reason: str
    source_url: str
    assigned_at: str


class AssignRunResponse(BaseModel):
    users_processed: int
    total_matched: int
    new_assignments: int
    errors: int


def _assignment_to_response(a: UserRuleAssignment) -> AssignmentResponse:
    rule = a.rule
    return AssignmentResponse(
        id=str(a.id),
        rule_id=str(a.rule_id),
        rule_text=rule.rule_text,
        applies_to=rule.applies_to,
        trigger=rule.trigger,
        deadline=rule.deadline,
        valid_from=rule.valid_from.isoformat() if rule.valid_from else None,
        valid_until=rule.valid_until.isoformat() if rule.valid_until else None,
        blocking=bool(rule.blocking),
        consequence=rule.consequence,
        authority=rule.authority,
        exceptions=rule.exceptions,
        match_type=a.match_type.value,
        urgency=a.urgency.value,
        status=a.status.value,
        reason=a.reason,
        source_url=rule.source_doc_url,
        assigned_at=a.assigned_at.isoformat(),
    )


def _run_assign_background() -> None:
    db = SessionLocal()
    try:
        run_for_all_users(db)
    finally:
        db.close()


@router.post("/events/assign", response_model=AssignRunResponse)
def trigger_assign(
    background_tasks: BackgroundTasks,
    _admin=Depends(require_admin),
) -> AssignRunResponse:
    """Trigger the user agent to match and persist rules for all active users."""
    background_tasks.add_task(_run_assign_background)
    return AssignRunResponse(users_processed=0, total_matched=0, new_assignments=0, errors=0)


@router.post("/events/assign/me", response_model=dict)
def assign_for_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Run the user agent for the current user and return matched rules."""
    result = run_for_user(db, current_user, persist=True)
    result.pop("user_context", None)
    return result


@router.get("/events/assignments/me", response_model=list[AssignmentResponse])
def get_my_assignments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[AssignmentResponse]:
    """Return all active rule assignments for the current user."""
    assignments = (
        db.query(UserRuleAssignment)
        .filter(
            UserRuleAssignment.user_id == current_user.id,
            UserRuleAssignment.status == AssignmentStatus.ACTIVE,
        )
        .order_by(UserRuleAssignment.assigned_at.desc())
        .all()
    )
    return [_assignment_to_response(a) for a in assignments]


@router.get("/events/runs/{run_id}/candidates", response_model=list[CandidateLogResponse])
def get_run_candidates(
    run_id: str,
    limit: int = 200,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> list[CandidateLogResponse]:
    safe_limit = min(max(limit, 1), 5000)
    logs = (
        db.query(EventCandidateLog)
        .filter(EventCandidateLog.run_id == run_id)
        .order_by(EventCandidateLog.created_at.asc())
        .limit(safe_limit)
        .all()
    )
    return [
        CandidateLogResponse(
            id=str(item.id),
            run_id=str(item.run_id),
            source_key=item.source_key,
            source_url=item.source_url,
            category=item.category,
            parent_category=item.parent_category,
            target_role=item.target_role,
            candidate_hash=item.candidate_hash,
            decision=item.decision.value,
            reason_code=item.reason_code,
            metrics=item.metrics or {},
            created_at=item.created_at.isoformat(),
            candidate_text=item.candidate_text,
        )
        for item in logs
    ]
