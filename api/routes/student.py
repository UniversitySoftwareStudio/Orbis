"""Student-facing SIS read endpoints.

Thin projections over existing repositories that back the web app's
Dashboard, Profile, Transcript and Courses pages. All endpoints are
student-scoped: data is resolved from the authenticated user — a client
never supplies a student_id.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.logging import get_logger
from database.models import EnrollmentStatus, User, UserProfile
from database.repositories.academic_calendar_repository import AcademicCalendarRepository
from database.repositories.assignment_repository import AssignmentRepository
from database.repositories.enrollment_repository import EnrollmentRepository
from database.repositories.student_repository import StudentRepository
from database.repositories.user_repository import UserRepository
from database.repositories.user_rule_assignment_repository import UserRuleAssignmentRepository
from database.session import get_db
from dependencies import get_current_active_user
from schemas.student import (
    DashboardCalendarItem,
    DashboardDeadline,
    DashboardResponse,
    DashboardStats,
    EnrolledCourseResponse,
    EnrolledCourseSlot,
    ProfileResponse,
    TranscriptEntry,
    TranscriptResponse,
)

router = APIRouter()
logger = get_logger(__name__)


def _get_profile(db: Session, user_id: int) -> UserProfile | None:
    return db.scalars(select(UserProfile).where(UserProfile.user_id == user_id)).first()


def _resolve_student_id(db: Session, user: User) -> int | None:
    role_info = UserRepository(db).resolve_user_role(user.id)
    if not role_info or role_info.get("role") != "student":
        return None
    return role_info.get("entity_id")


@router.get("/sis/profile/me", response_model=ProfileResponse)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ProfileResponse:
    profile = _get_profile(db, current_user.id)
    student = StudentRepository(db).get_by_user_id(current_user.id)

    return ProfileResponse(
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        email=current_user.email,
        user_type=current_user.user_type.value,
        student_id=student.student_id if student else None,
        gpa=float(student.gpa) if student and student.gpa is not None else None,
        department=profile.department if profile else None,
        faculty=profile.faculty if profile else None,
        program_level=profile.program_level if profile else None,
        academic_year=profile.academic_year if profile else None,
        semester_number=profile.semester_number if profile else None,
        total_credits_completed=profile.total_credits_completed if profile else None,
        total_credits_enrolled=profile.total_credits_enrolled if profile else None,
        is_on_probation=bool(profile.is_on_probation) if profile else False,
        has_advisor_hold=bool(profile.has_advisor_hold) if profile else False,
        has_financial_hold=bool(profile.has_financial_hold) if profile else False,
        is_exchange_student=bool(profile.is_exchange_student) if profile else False,
        is_double_major=bool(profile.is_double_major) if profile else False,
        is_minor=bool(profile.is_minor) if profile else False,
    )


@router.get("/sis/transcript/me", response_model=TranscriptResponse)
def get_my_transcript(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> TranscriptResponse:
    student_id = _resolve_student_id(db, current_user)
    if student_id is None:
        return TranscriptResponse(entries=[], cumulative_gpa=None, total_credits=0)

    repo = StudentRepository(db)
    rows = repo.get_transcript(student_id)
    entries = [TranscriptEntry(**row) for row in rows]
    total_credits = sum(e.credits for e in entries)
    return TranscriptResponse(
        entries=entries,
        cumulative_gpa=repo.calculate_gpa(student_id),
        total_credits=total_credits,
    )


@router.get("/sis/courses/me", response_model=list[EnrolledCourseResponse])
def get_my_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[EnrolledCourseResponse]:
    student_id = _resolve_student_id(db, current_user)
    if student_id is None:
        return []

    rows = EnrollmentRepository(db).get_enrolled_with_details(student_id)

    # Collapse the per-slot rows into one course card with a list of slots.
    by_course: dict[tuple, EnrolledCourseResponse] = {}
    for row in rows:
        key = (row["course_code"], row["section_number"])
        course = by_course.get(key)
        if course is None:
            course = EnrolledCourseResponse(
                course_code=row["course_code"],
                course_name=row["course_name"],
                section_number=row["section_number"],
                section_type=row["section_type"],
                instructor_name=row.get("instructor_name"),
                status=str(row["status"]).lower(),
                slots=[],
            )
            by_course[key] = course
        if row.get("day_of_week") is not None:
            course.slots.append(
                EnrolledCourseSlot(
                    day_of_week=row.get("day_of_week"),
                    start_time=row.get("start_time"),
                    end_time=row.get("end_time"),
                    location=row.get("location"),
                    is_online=row.get("is_online"),
                )
            )
    return list(by_course.values())


@router.get("/sis/dashboard", response_model=DashboardResponse)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DashboardResponse:
    profile = _get_profile(db, current_user.id)
    student_id = _resolve_student_id(db, current_user)
    is_student = student_id is not None

    stats = DashboardStats(
        total_credits_completed=profile.total_credits_completed if profile else None,
        total_credits_enrolled=profile.total_credits_enrolled if profile else None,
        active_regulation_count=UserRuleAssignmentRepository(db).count_active_for_user(current_user.id),
    )
    upcoming_deadlines: list[DashboardDeadline] = []

    if is_student:
        student = StudentRepository(db).get_by_id(student_id)
        stats.gpa = float(student.gpa) if student and student.gpa is not None else None

        enrolled = EnrollmentRepository(db).get_student_enrollments(
            student_id, EnrollmentStatus.ENROLLED
        )
        stats.enrolled_course_count = len(enrolled)

        pending = AssignmentRepository(db).get_pending_assignments(student_id)
        stats.pending_assignment_count = len(pending)
        upcoming_deadlines = [
            DashboardDeadline(title=a.title, due_date=a.due_date, kind="assignment")
            for a in pending[:5]
        ]

    cal_repo = AcademicCalendarRepository(db)
    cal_entries = cal_repo.get_by_year_and_applies_to("2025-2026", "undergraduate")
    upcoming_calendar = [
        DashboardCalendarItem(
            title=e.title_en or e.title_tr,
            start_date=e.start_date,
            entry_type=e.entry_type,
        )
        for e in cal_entries[:5]
    ]

    return DashboardResponse(
        first_name=current_user.first_name,
        is_student=is_student,
        stats=stats,
        upcoming_deadlines=upcoming_deadlines,
        upcoming_calendar=upcoming_calendar,
    )
