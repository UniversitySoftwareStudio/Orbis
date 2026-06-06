"""Response schemas for the student-facing SIS pages.

These back the read-only endpoints used by the web app's Dashboard, Profile,
Transcript and Courses pages. They are thin projections over existing models
and repositories — no new tables.
"""

from datetime import date, datetime, time

from pydantic import BaseModel


class ProfileResponse(BaseModel):
    # Identity (User + Student)
    first_name: str
    last_name: str
    email: str
    user_type: str
    student_id: str | None = None
    gpa: float | None = None

    # Academic context (UserProfile)
    department: str | None = None
    faculty: str | None = None
    program_level: str | None = None
    academic_year: int | None = None
    semester_number: int | None = None
    total_credits_completed: int | None = None
    total_credits_enrolled: int | None = None

    # Status flags
    is_on_probation: bool = False
    has_advisor_hold: bool = False
    has_financial_hold: bool = False
    is_exchange_student: bool = False
    is_double_major: bool = False
    is_minor: bool = False


class TranscriptEntry(BaseModel):
    course_code: str
    course_name: str
    term: str
    credits: int
    grade_letter: str | None = None
    grade_numeric: float | None = None


class TranscriptResponse(BaseModel):
    entries: list[TranscriptEntry]
    cumulative_gpa: float | None = None
    total_credits: int = 0


class EnrolledCourseSlot(BaseModel):
    day_of_week: str | None = None
    start_time: time | None = None
    end_time: time | None = None
    location: str | None = None
    is_online: bool | None = None


class EnrolledCourseResponse(BaseModel):
    course_code: str
    course_name: str
    section_number: str
    section_type: str
    instructor_name: str | None = None
    status: str
    slots: list[EnrolledCourseSlot] = []


class DashboardStats(BaseModel):
    gpa: float | None = None
    total_credits_completed: int | None = None
    total_credits_enrolled: int | None = None
    enrolled_course_count: int = 0
    pending_assignment_count: int = 0
    active_regulation_count: int = 0


class DashboardDeadline(BaseModel):
    title: str
    due_date: datetime
    kind: str  # "assignment" | "calendar"


class DashboardCalendarItem(BaseModel):
    title: str
    start_date: date
    entry_type: str


class DashboardResponse(BaseModel):
    first_name: str
    is_student: bool
    stats: DashboardStats
    upcoming_deadlines: list[DashboardDeadline] = []
    upcoming_calendar: list[DashboardCalendarItem] = []
