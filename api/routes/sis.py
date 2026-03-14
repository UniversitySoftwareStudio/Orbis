from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.logging import get_logger
from database.models import User
from database.repositories.academic_calendar_repository import AcademicCalendarRepository
from database.repositories.section_schedule_repository import SectionScheduleRepository
from database.repositories.user_repository import UserRepository
from database.session import get_db
from dependencies import get_current_active_user
from schemas.sis import CalendarEntryResponse, ScheduleSlotResponse

router = APIRouter()
logger = get_logger(__name__)


@router.get("/sis/calendar", response_model=list[CalendarEntryResponse])
def get_calendar(
    academic_year: str = "2025-2026",
    applies_to: str = "undergraduate",
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
) -> list[CalendarEntryResponse]:
    repo = AcademicCalendarRepository(db)
    entries = repo.get_by_year_and_applies_to(academic_year, applies_to)
    return [CalendarEntryResponse.from_orm(e) for e in entries]


@router.get("/sis/schedule/me")
def get_my_schedule(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    role_info = UserRepository(db).resolve_user_role(current_user.id)
    if role_info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )

    if role_info["role"] != "student":
        return {"slots": [], "message": "Not a student account"}

    student_id = role_info["entity_id"]
    repo = SectionScheduleRepository(db)
    rows = repo.get_student_schedule(student_id)
    return {"slots": [ScheduleSlotResponse(**row) for row in rows]}
