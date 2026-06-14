"""'My Regulations' endpoints.

Surface the regulation-extraction pipeline's per-user rule assignments to the
authenticated user, and let the user mark an assignment actioned or dismissed.
"""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.logging import get_logger
from database.models import (
    AssignmentStatus,
    Event,
    EventCandidateLog,
    EventRun,
    EventSourceCheckpoint,
    EventStatus,
    KnowledgeBase,
    RegulationRule,
    RuleMatchType,
    RuleStatus,
    User,
    UserRuleAssignment,
)
from database.repositories.user_repository import UserRepository
from database.repositories.user_rule_assignment_repository import UserRuleAssignmentRepository
from database.session import SessionLocal, get_db
from dependencies import get_current_active_user
from events.search_agent import SearchAgent
from events.user_agent import run_for_user_trace
from schemas.regulations import (
    RegulationDiagnosticsResponse,
    RegulationRunSnapshot,
    RuleAssignmentResponse,
    RuleAssignmentStatusUpdate,
)

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
        source_url=rule.source_doc_url if rule else None,
        evidence_quote=rule.evidence_quote if rule else None,
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


@router.get("/regulations/assignments/{assignment_id}", response_model=RuleAssignmentResponse)
def get_my_regulation_assignment(
    assignment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> RuleAssignmentResponse:
    try:
        assignment_uuid = uuid.UUID(assignment_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    assignment = UserRuleAssignmentRepository(db).get_for_user_by_id(current_user.id, assignment_uuid)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    return _to_response(assignment)


def _enum_counts(db: Session, model, column, *filters) -> dict[str, int]:
    query = db.query(column, func.count()).select_from(model)
    for condition in filters:
        query = query.filter(condition)
    rows = query.group_by(column).all()
    return {
        (key.value if hasattr(key, "value") else str(key)): int(count)
        for key, count in rows
    }


def _pipeline_observations(
    *,
    assignments: dict[str, int],
    rules: dict[str, int],
    events: dict[str, int],
    sources: dict[str, int],
    last_run: EventRun | None,
) -> list[str]:
    notes: list[str] = []
    if sources.get("processable", 0) == 0:
        notes.append("No processable regulation sources were found in knowledge_base.")
    if last_run is None:
        notes.append("No event extraction run has been recorded yet.")
    elif last_run.status.value == "failed":
        notes.append(f"The latest event run failed: {last_run.error_message or 'no error message recorded'}.")
    elif last_run.events_created == 0:
        notes.append("The latest event run completed but created 0 regulatory_events.")
    if events.get("total", 0) == 0:
        notes.append("regulatory_events is empty, so the trigger pipeline has not produced accepted obligations.")
    elif events.get("pending", 0) == 0:
        notes.append("There are regulatory_events, but none are pending/high-confidence for promotion.")
    if rules.get("active", 0) == 0:
        notes.append("No active regulation_rules exist for the user matcher to evaluate.")
    elif rules.get("promoted_from_events", 0) == 0:
        notes.append("Active historical rules exist, but no rules are traceably promoted from regulatory_events yet.")
    if assignments.get("total", 0) == 0 and rules.get("active", 0) > 0:
        notes.append("Rules exist, but this user has no persisted user_rule_assignments; run the self-check.")
    if assignments.get("active", 0) > 0:
        notes.append("This user has active persisted assignments; the assignment list should render them.")
    return notes


@router.get("/regulations/debug/me", response_model=RegulationDiagnosticsResponse)
def get_my_regulation_diagnostics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> RegulationDiagnosticsResponse:
    assignment_status = _enum_counts(
        db,
        UserRuleAssignment,
        UserRuleAssignment.status,
        UserRuleAssignment.user_id == current_user.id,
    )
    assignments = {
        "total": db.query(UserRuleAssignment.id).filter(UserRuleAssignment.user_id == current_user.id).count(),
        "active": assignment_status.get(AssignmentStatus.ACTIVE.value, 0),
        "dismissed": assignment_status.get(AssignmentStatus.DISMISSED.value, 0),
        "actioned": assignment_status.get(AssignmentStatus.ACTIONED.value, 0),
    }

    rule_status = _enum_counts(db, RegulationRule, RegulationRule.status)
    rule_match_types = _enum_counts(
        db,
        RegulationRule,
        RegulationRule.match_type,
        RegulationRule.status == RuleStatus.ACTIVE,
    )
    promoted_from_events = (
        db.query(RegulationRule.id)
        .join(Event, RegulationRule.fingerprint == Event.fingerprint)
        .filter(RegulationRule.status == RuleStatus.ACTIVE)
        .count()
    )
    rules = {
        "total": db.query(RegulationRule.id).count(),
        "active": rule_status.get(RuleStatus.ACTIVE.value, 0),
        "needs_review": rule_status.get(RuleStatus.NEEDS_REVIEW.value, 0),
        "rejected": rule_status.get(RuleStatus.REJECTED.value, 0),
        "sql": rule_match_types.get(RuleMatchType.SQL.value, 0),
        "contextual": rule_match_types.get(RuleMatchType.CONTEXTUAL.value, 0),
        "promoted_from_events": promoted_from_events,
    }

    event_status = _enum_counts(db, Event, Event.status)
    events = {
        "total": db.query(Event.id).count(),
        "pending": event_status.get(EventStatus.PENDING.value, 0),
        "needs_review": event_status.get(EventStatus.NEEDS_REVIEW.value, 0),
        "assigned": event_status.get(EventStatus.ASSIGNED.value, 0),
    }

    source_rows = (
        db.query(KnowledgeBase.category, func.count())
        .filter(KnowledgeBase.category.in_(["regulation", "regulation_document"]))
        .group_by(KnowledgeBase.category)
        .all()
    )
    source_counts = {str(category): int(count) for category, count in source_rows}
    try:
        loaded_sources = SearchAgent().fetch_regulation_sources(db)
        processable_sources = sum(1 for source in loaded_sources if source.should_process)
        source_count = len(loaded_sources)
    except Exception as exc:  # pragma: no cover - diagnostics must not break page load
        logger.warning("Could not compute regulation source diagnostics: %s", exc)
        processable_sources = 0
        source_count = 0
    sources = {
        "knowledge_base_rows": sum(source_counts.values()),
        "regulation_rows": source_counts.get("regulation", 0),
        "regulation_document_rows": source_counts.get("regulation_document", 0),
        "sources": source_count,
        "processable": processable_sources,
        "checkpoints": db.query(EventSourceCheckpoint.source_key).count(),
    }

    last_run = db.query(EventRun).order_by(EventRun.started_at.desc()).first()
    last_run_snapshot = None
    last_run_events: dict[str, int] = {}
    candidate_decisions: dict[str, int] = {}
    candidate_reasons: dict[str, int] = {}
    if last_run is not None:
        last_run_snapshot = RegulationRunSnapshot(
            run_id=str(last_run.id),
            status=last_run.status.value,
            started_at=last_run.started_at,
            completed_at=last_run.completed_at,
            sources_processed=last_run.sources_processed,
            chunks_processed=last_run.chunks_processed,
            events_created=last_run.events_created,
            error_message=last_run.error_message,
        )
        last_run_events = _enum_counts(db, Event, Event.status, Event.run_id == last_run.id)
        candidate_decisions = _enum_counts(
            db,
            EventCandidateLog,
            EventCandidateLog.decision,
            EventCandidateLog.run_id == last_run.id,
        )
        candidate_reasons = {
            str(reason): int(count)
            for reason, count in (
                db.query(EventCandidateLog.reason_code, func.count())
                .filter(EventCandidateLog.run_id == last_run.id)
                .group_by(EventCandidateLog.reason_code)
                .order_by(func.count().desc())
                .limit(8)
                .all()
            )
        }

    return RegulationDiagnosticsResponse(
        user={
            "id": current_user.id,
            "email": current_user.email,
            "name": f"{current_user.first_name} {current_user.last_name}",
            "type": current_user.user_type.value,
        },
        assignments=assignments,
        rules=rules,
        events=events,
        sources=sources,
        last_run=last_run_snapshot,
        last_run_events=last_run_events,
        last_run_candidate_decisions=candidate_decisions,
        last_run_candidate_reasons=candidate_reasons,
        observations=_pipeline_observations(
            assignments=assignments,
            rules=rules,
            events=events,
            sources=sources,
            last_run=last_run,
        ),
    )


@router.post("/regulations/check/stream")
def run_my_regulation_check(
    current_user: User = Depends(get_current_active_user),
) -> StreamingResponse:
    def sse(event_type: str, data: dict) -> str:
        return f"event: {event_type}\ndata: {json.dumps(jsonable_encoder(data), ensure_ascii=False)}\n\n"

    # StreamingResponse drives this generator *after* the request handler returns,
    # by which point FastAPI's request-scoped `db` session is already closed. Any
    # lazy-load (e.g. user.profile) on the request-scoped `current_user` would then
    # raise DetachedInstanceError. So open a dedicated session for the whole stream
    # and re-fetch the user inside it, keeping every ORM access in a live session.
    user_email = current_user.email

    def event_stream():
        stream_db = SessionLocal()
        try:
            user = UserRepository(stream_db).get_by_email(user_email)
            if user is None:
                yield sse("error", {"detail": "User not found"})
                return

            for event in run_for_user_trace(stream_db, user):
                event_type = event.pop("type", "message")
                yield sse(event_type, event)

            assignments = UserRuleAssignmentRepository(stream_db).get_for_user(user.id)
            yield sse("done", {"assignments": [_to_response(item) for item in assignments]})
        except Exception as exc:  # pragma: no cover - defensive stream guard
            logger.exception("Regulation self-check failed")
            yield sse("error", {"detail": str(exc)})
        finally:
            stream_db.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
