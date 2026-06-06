"""E2E tests for the student-facing SIS read endpoints (routes/student.py).

These exercise the real repositories against the test Postgres database
(via the db_session fixture), with get_db / get_current_active_user overridden
to the seeded session and user.
"""

from datetime import date, datetime, time, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database import models
from database.session import get_db
from dependencies import get_current_active_user
from routes.student import router as student_router


def _seed_student(db):
    """Create a user+student+profile with one completed and one enrolled course,
    plus a published future assignment. Returns the User."""
    user = models.User(
        email="student@bilgiedu.net",
        password_hash="x",
        first_name="Ada",
        last_name="Lovelace",
        user_type=models.UserType.STUDENT,
        is_active=True,
    )
    db.add(user)
    db.flush()

    student = models.Student(user_id=user.id, student_id="2025001", gpa=3.50, is_active=True)
    db.add(student)
    db.flush()

    profile = models.UserProfile(
        user_id=user.id,
        department="Computer Engineering",
        faculty="Faculty of Engineering",
        program_level="undergraduate",
        academic_year=2,
        semester_number=3,
        total_credits_completed=30,
        total_credits_enrolled=15,
        is_on_probation=False,
        has_advisor_hold=True,
    )
    db.add(profile)

    term = models.AcademicTerm(
        code="2025F", term_type=models.TermType.FALL, year=2025,
        start_date=date(2025, 9, 1), end_date=date(2026, 1, 15), is_active=True,
    )
    db.add(term)
    course1 = models.Course(code="CS101", name="Intro to CS", description="d")
    course2 = models.Course(code="CS102", name="Data Structures", description="d")
    db.add_all([course1, course2])
    db.flush()

    sec_completed = models.CourseSection(
        course_id=course1.id, term_id=term.id, section_number="01",
        section_type="LECTURE", instructor_name="Dr. Turing",
    )
    sec_enrolled = models.CourseSection(
        course_id=course2.id, term_id=term.id, section_number="02",
        section_type="LECTURE", instructor_name="Dr. Hopper",
    )
    db.add_all([sec_completed, sec_enrolled])
    db.flush()

    db.add(models.SectionSchedule(
        section_id=sec_enrolled.id, day_of_week="MON",
        start_time=time(9, 0), end_time=time(11, 0), location="B-201", is_online=False,
    ))

    db.add(models.Enrollment(
        student_id=student.id, section_id=sec_completed.id,
        status=models.EnrollmentStatus.COMPLETED,
        final_grade_numeric=3.70, final_grade_letter="A-",
    ))
    db.add(models.Enrollment(
        student_id=student.id, section_id=sec_enrolled.id,
        status=models.EnrollmentStatus.ENROLLED,
    ))

    db.add(models.Assignment(
        section_id=sec_enrolled.id, title="Project 1", description="build it",
        due_date=datetime.utcnow() + timedelta(days=7), max_points=100, is_published=True,
    ))
    db.commit()
    return user


def _authed_app(db, user):
    app = FastAPI()
    app.include_router(student_router, prefix="/api")

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_active_user] = lambda: user
    return app


def test_profile_me_returns_identity_and_flags(db_session):
    user = _seed_student(db_session)
    client = TestClient(_authed_app(db_session, user))
    res = client.get("/api/sis/profile/me")
    assert res.status_code == 200
    body = res.json()
    assert body["first_name"] == "Ada"
    assert body["student_id"] == "2025001"
    assert body["gpa"] == 3.5
    assert body["department"] == "Computer Engineering"
    assert body["has_advisor_hold"] is True
    assert body["is_on_probation"] is False


def test_transcript_me_lists_completed_with_gpa(db_session):
    user = _seed_student(db_session)
    client = TestClient(_authed_app(db_session, user))
    res = client.get("/api/sis/transcript/me")
    assert res.status_code == 200
    body = res.json()
    assert len(body["entries"]) == 1
    assert body["entries"][0]["course_code"] == "CS101"
    assert body["entries"][0]["grade_letter"] == "A-"
    assert body["cumulative_gpa"] == 3.7
    assert body["total_credits"] == 3


def test_courses_me_returns_enrolled_with_slots(db_session):
    user = _seed_student(db_session)
    client = TestClient(_authed_app(db_session, user))
    res = client.get("/api/sis/courses/me")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    course = body[0]
    assert course["course_code"] == "CS102"
    assert course["status"] == "enrolled"
    assert len(course["slots"]) == 1
    assert course["slots"][0]["day_of_week"] == "MON"
    assert course["slots"][0]["location"] == "B-201"


def test_dashboard_aggregates_stats(db_session):
    user = _seed_student(db_session)
    client = TestClient(_authed_app(db_session, user))
    res = client.get("/api/sis/dashboard")
    assert res.status_code == 200
    body = res.json()
    assert body["first_name"] == "Ada"
    assert body["is_student"] is True
    assert body["stats"]["enrolled_course_count"] == 1
    assert body["stats"]["pending_assignment_count"] == 1
    assert body["stats"]["gpa"] == 3.5
    assert len(body["upcoming_deadlines"]) == 1
    assert body["upcoming_deadlines"][0]["title"] == "Project 1"


def test_student_endpoints_require_auth(db_session):
    app = FastAPI()
    app.include_router(student_router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: iter([db_session])
    client = TestClient(app)
    for path in ("/api/sis/profile/me", "/api/sis/transcript/me",
                 "/api/sis/courses/me", "/api/sis/dashboard"):
        assert client.get(path).status_code in {401, 403}
