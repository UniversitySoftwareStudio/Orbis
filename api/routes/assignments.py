import io
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from core.logging import get_logger
from database.models import AssignmentSubmission, User
from database.repositories.assignment_repository import AssignmentRepository
from database.repositories.assignment_submission_repository import AssignmentSubmissionRepository
from database.repositories.user_repository import UserRepository
from database.session import get_db
from dependencies import get_current_active_user, require_student
from llm.service import get_llm_service

router = APIRouter()
logger = get_logger(__name__)

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads/assignments"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _extract_text(content: bytes, content_type: str) -> str:
    if content_type == "application/pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if "wordprocessingml" in content_type:
        from docx import Document
        doc = Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs)
    return content.decode("utf-8", errors="ignore")


def _validate_with_ai(text: str, title: str, description: str) -> tuple[bool, str]:
    llm = get_llm_service()
    prompt = f"""You are a university assignment validator.

Assignment title: {title}
Assignment description: {description or 'No description provided.'}

Student submitted document (first 3000 chars):
{text[:3000]}

Decide if this document is genuinely related to the assignment above.
Respond with exactly one of:
APPROVED: <one sentence reason>
REJECTED: <one sentence reason>
"""
    response = llm.complete(prompt).strip()
    approved = response.upper().startswith("APPROVED")
    return approved, response


@router.get("/assignments/me")
def get_my_assignments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
) -> list[dict]:
    role_info = UserRepository(db).resolve_user_role(current_user.id)
    if not role_info:
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
    if not role_info:
        raise HTTPException(status_code=404, detail="Student profile not found")
    student_id = role_info["entity_id"]

    assignment_repo = AssignmentRepository(db)
    assignment = assignment_repo.get_by_id(assignment_id)
    if not assignment or not assignment.is_published:
        raise HTTPException(status_code=404, detail="Assignment not found")

    window = assignment_repo.validate_submission_window(assignment_id)
    if not window["open"]:
        raise HTTPException(status_code=400, detail="Submission deadline has passed")

    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail="Only PDF, DOCX, and TXT files are allowed")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")

    text = _extract_text(content, file.content_type)
    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from file")

    approved, feedback = _validate_with_ai(text, assignment.title, assignment.description or "")

    ext = Path(file.filename or "file").suffix
    saved_name = f"{uuid.uuid4()}{ext}"
    file_path = UPLOAD_DIR / saved_name
    file_path.write_bytes(content)

    sub_repo = AssignmentSubmissionRepository(db)
    existing = sub_repo.get_by_student_and_assignment(student_id, assignment_id)

    final_status = "approved" if approved else "rejected"

    if existing:
        sub_repo.update(existing.id, status=final_status, ai_feedback=feedback, file_path=str(file_path), original_filename=file.filename or saved_name)
        submission = sub_repo.get_by_id(existing.id)
    else:
        submission = sub_repo.create(
            assignment_id=assignment_id,
            student_id=student_id,
            file_path=str(file_path),
            original_filename=file.filename or saved_name,
            status=final_status,
            ai_feedback=feedback,
        )

    db.commit()

    return {
        "submission_id": submission.id,
        "status": final_status,
        "ai_feedback": feedback,
    }
