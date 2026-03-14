from __future__ import annotations

from core.logging import get_logger
from database.models import User
from database.repositories.academic_calendar_repository import AcademicCalendarRepository
from database.repositories.section_schedule_repository import SectionScheduleRepository
from database.repositories.user_repository import UserRepository
from sqlalchemy.orm import Session

logger = get_logger(__name__)

SIS_TOOLS = {"calendar", "student_schedule"}


def build_sis_context(
    intents: list[dict],
    current_user: User | None,
    db: Session,
) -> tuple[str, list[dict]]:
    """
    Extract calendar / student_schedule intents, fetch structured data from
    the SIS tables, and return a formatted context block to prepend to the
    RAG context.  The remaining (non-SIS) intents are returned for the normal
    retrieval pipeline.
    """
    sis_intents = [i for i in intents if str(i.get("tool", "")).lower() in SIS_TOOLS]
    remaining = [i for i in intents if str(i.get("tool", "")).lower() not in SIS_TOOLS]

    if not sis_intents:
        return "", intents

    blocks: list[str] = []

    for intent in sis_intents:
        tool = str(intent.get("tool", "")).lower()

        if tool == "calendar":
            block = _fetch_calendar(db)
            if block:
                blocks.append(block)

        elif tool == "student_schedule":
            block = _fetch_student_schedule(current_user, db)
            if block:
                blocks.append(block)

    context_str = "\n\n".join(blocks)
    return context_str, remaining


def _fetch_calendar(db: Session) -> str:
    try:
        repo = AcademicCalendarRepository(db)
        entries = repo.get_active_year_entries()
        if not entries:
            return ""
        return repo.format_for_rag(entries)
    except Exception:
        logger.exception("Failed to fetch academic calendar for RAG context")
        return ""


def _fetch_student_schedule(current_user: User | None, db: Session) -> str:
    if current_user is None:
        return ""
    if current_user.user_type.value != "student":
        return ""

    try:
        role_info = UserRepository(db).resolve_user_role(current_user.id)
        if role_info is None or role_info["role"] != "student":
            return ""

        student_id = role_info["entity_id"]
        repo = SectionScheduleRepository(db)
        rows = repo.get_student_schedule(student_id)
        if not rows:
            return ""
        return repo.format_for_rag(rows)
    except Exception:
        logger.exception("Failed to fetch student schedule for RAG context")
        return ""
