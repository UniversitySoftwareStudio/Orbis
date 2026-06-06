import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agents.submission_agent import evaluate_submission, stream_submission_evaluation
from core.logging import get_logger
from database.models import User
from database.repositories.assignment_repository import AssignmentRepository
from database.repositories.assignment_submission_repository import AssignmentSubmissionRepository
from database.repositories.user_repository import UserRepository
from database.session import get_db
from dependencies import require_student

router = APIRouter()
logger = get_logger(__name__)

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads/assignments"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class SubmissionFlagRequest(BaseModel):
    reason: str | None = None


@router.get("/assignments/me")
def get_my_assignments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
) -> list[dict]:
    role_info = UserRepository(db).resolve_user_role(current_user.id)
    if not role_info or role_info.get("role") != "student" or role_info.get("entity_id") is None:
        raise HTTPException(status_code=404, detail="Student profile not found")
    student_id = role_info["entity_id"]

    assignments = AssignmentRepository(db).get_pending_assignments(student_id)
    sub_repo = AssignmentSubmissionRepository(db)

    result = []
    for a in assignments:
        existing = sub_repo.get_by_student_and_assignment(student_id, a.id)
        result.append({
            "id": a.id,
            "title": a.title,
            "description": a.description,
            "due_date": a.due_date.isoformat(),
            "max_points": float(a.max_points),
            "section_id": a.section_id,
            "submission": {
                "id": existing.id,
                "status": existing.status,
                "ai_feedback": existing.ai_feedback,
                "submitted_at": existing.submitted_at.isoformat(),
                "original_filename": existing.original_filename,
                "evaluation_report": existing.evaluation_report,
                "flagged_by_student": existing.flagged_by_student,
                "student_flag_reason": existing.student_flag_reason,
                "flagged_at": existing.flagged_at.isoformat() if existing.flagged_at else None,
            } if existing else None,
        })
    return result


@router.post("/assignments/{assignment_id}/submit")
async def submit_assignment(
    assignment_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
) -> dict:
    role_info = UserRepository(db).resolve_user_role(current_user.id)
    if not role_info or role_info.get("role") != "student" or role_info.get("entity_id") is None:
        raise HTTPException(status_code=404, detail="Student profile not found")
    student_id = role_info["entity_id"]

    assignment_repo = AssignmentRepository(db)
    assignment = assignment_repo.get_by_id(assignment_id)
    if not assignment or not assignment.is_published:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if not assignment_repo.student_is_enrolled_for_assignment(student_id, assignment_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not enrolled in this assignment's section")

    window = assignment_repo.validate_submission_window(assignment_id)
    if not window["open"]:
        raise HTTPException(status_code=400, detail="Submission deadline has passed")

    content = await file.read()
    evaluation = evaluate_submission(
        assignment_title=assignment.title,
        assignment_description=assignment.description,
        content=content,
        filename=file.filename,
        content_type=file.content_type,
    )
    file_errors = ((evaluation.report.get("file") or {}).get("blocking_errors") or [])
    if any("too large" in error for error in file_errors):
        raise HTTPException(status_code=400, detail=file_errors[0])

    return _persist_submission(
        db=db,
        assignment_id=assignment_id,
        student_id=student_id,
        evaluation=evaluation,
        content=content,
        original_filename=file.filename or "",
    )


def _persist_submission(
    *,
    db: Session,
    assignment_id: int,
    student_id: int,
    evaluation,
    content: bytes,
    original_filename: str,
) -> dict:
    """Save the uploaded file and upsert the submission row, returning the API payload."""
    ext = Path(original_filename or "file").suffix
    saved_name = f"{uuid.uuid4()}{ext}"
    file_path = UPLOAD_DIR / saved_name
    file_path.write_bytes(content)

    sub_repo = AssignmentSubmissionRepository(db)
    existing = sub_repo.get_by_student_and_assignment(student_id, assignment_id)
    final_status = evaluation.decision

    if existing:
        sub_repo.update(
            existing.id,
            status=final_status,
            ai_feedback=evaluation.feedback,
            evaluation_report=evaluation.report,
            file_path=str(file_path),
            original_filename=original_filename or saved_name,
            submitted_at=datetime.utcnow(),
            flagged_by_student=False,
            student_flag_reason=None,
            flagged_at=None,
        )
        submission = sub_repo.get_by_id(existing.id)
    else:
        submission = sub_repo.create(
            assignment_id=assignment_id,
            student_id=student_id,
            file_path=str(file_path),
            original_filename=original_filename or saved_name,
            status=final_status,
            ai_feedback=evaluation.feedback,
            evaluation_report=evaluation.report,
        )
    db.commit()

    return {
        "submission_id": submission.id,
        "status": final_status,
        "ai_feedback": evaluation.feedback,
        "evaluation_report": evaluation.report,
        "can_flag_rejection": final_status == "rejected",
    }


@router.post("/assignments/{assignment_id}/submit/stream")
async def submit_assignment_stream(
    assignment_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
) -> StreamingResponse:
    """Same as /submit, but streams the agent's reasoning steps as SSE events.

    Emits one `data:` line per step (file inspection, requirement decomposition,
    each requirement finding, the verdict) and finally a `result` event carrying
    the persisted submission payload — identical in shape to the blocking endpoint.
    """
    role_info = UserRepository(db).resolve_user_role(current_user.id)
    if not role_info or role_info.get("role") != "student" or role_info.get("entity_id") is None:
        raise HTTPException(status_code=404, detail="Student profile not found")
    student_id = role_info["entity_id"]

    assignment_repo = AssignmentRepository(db)
    assignment = assignment_repo.get_by_id(assignment_id)
    if not assignment or not assignment.is_published:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if not assignment_repo.student_is_enrolled_for_assignment(student_id, assignment_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not enrolled in this assignment's section")

    window = assignment_repo.validate_submission_window(assignment_id)
    if not window["open"]:
        raise HTTPException(status_code=400, detail="Submission deadline has passed")

    content = await file.read()
    original_filename = file.filename or ""
    content_type = file.content_type

    def event_stream():
        def sse(event_type: str, data: dict) -> str:
            return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        try:
            from llm.service import get_llm_service

            llm = get_llm_service()
            evaluation = None
            for event in stream_submission_evaluation(
                assignment_title=assignment.title,
                assignment_description=assignment.description,
                content=content,
                filename=original_filename,
                content_type=content_type,
                llm_complete=llm.complete,
                llm_stream=llm.generate,
            ):
                if event.type == "complete":
                    evaluation = event.data["evaluation"]
                    continue
                yield sse(event.type, event.data)

            file_errors = ((evaluation.report.get("file") or {}).get("blocking_errors") or [])
            if any("too large" in error for error in file_errors):
                yield sse("error", {"detail": file_errors[0]})
                return

            payload = _persist_submission(
                db=db,
                assignment_id=assignment_id,
                student_id=student_id,
                evaluation=evaluation,
                content=content,
                original_filename=original_filename,
            )
            yield sse("result", payload)
        except Exception as exc:  # pragma: no cover - defensive guard for the stream
            logger.exception("Streaming submission failed")
            yield sse("error", {"detail": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/assignments/submissions/{submission_id}/flag")
def flag_submission_rejection(
    submission_id: int,
    payload: SubmissionFlagRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
) -> dict:
    role_info = UserRepository(db).resolve_user_role(current_user.id)
    if not role_info or role_info.get("role") != "student" or role_info.get("entity_id") is None:
        raise HTTPException(status_code=404, detail="Student profile not found")
    student_id = role_info["entity_id"]

    sub_repo = AssignmentSubmissionRepository(db)
    submission = sub_repo.get_by_id(submission_id)
    if not submission or submission.student_id != student_id:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.status != "rejected":
        raise HTTPException(status_code=400, detail="Only rejected submissions can be flagged")

    reason = (payload.reason or "").strip() or None
    sub_repo.update(
        submission_id,
        status="flagged",
        flagged_by_student=True,
        student_flag_reason=reason,
        flagged_at=datetime.utcnow(),
    )
    db.commit()
    updated = sub_repo.get_by_id(submission_id)
    return {
        "submission_id": updated.id,
        "status": updated.status,
        "flagged_by_student": updated.flagged_by_student,
        "student_flag_reason": updated.student_flag_reason,
        "flagged_at": updated.flagged_at.isoformat() if updated.flagged_at else None,
    }
