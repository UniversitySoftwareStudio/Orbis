"""Create a deterministic demo student loaded with many problem conditions.

This "kitchen sink" student is designed to maximize the number of regulation
rules that could apply, so a *manual* regulation check surfaces a lot:

  * Low GPA (1.62) satisfies every "gpa < X" SQL rule (< 1.75, < 2.00,
    < 2.70, < 2.80) — the academic-standing problems.
  * Every contextual status flag is set (probation, advisor hold, financial
    hold, exchange student, double major, minor) so the LLM matcher has many
    hooks.
  * extra_context lists concrete problems for the contextual matcher to read.

Unlike the other probe scripts, this DOES NOT persist any assignments — run the
regulation check yourself to see what gets matched.

Run:
    python3 scripts/seed_kitchen_sink_probe_user.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from database.session import SessionLocal  # noqa: E402
from services.auth_service import AuthService  # noqa: E402


PROBE_USER = {
    "email": "kitchensink.probe@bilgiedu.net",
    "password": "demo1234",
    "first_name": "Mira",
    "last_name": "Troublewell",
    "student_id": "20257777",
    "gpa": 1.62,  # trips every "gpa < X" SQL rule
    "department": "Computer Engineering",
    "faculty": "Faculty of Engineering and Natural Sciences",
    "program_level": "undergraduate",
    "academic_year": 4,
    "semester_number": 8,
    "total_credits_completed": 132,
    "total_credits_enrolled": 21,  # overload
    "extra_context": {
        "probe_case": "kitchen_sink_many_problems",
        "specific_problem": (
            "Senior on academic probation with very low GPA, both an advisor "
            "hold and a financial hold, an incoming exchange student, a double "
            "major, and a minor — many overlapping obligations expected."
        ),
        "academic_standing": "probation",
        "credit_overload": True,
        "expected_graduation_term": "2026 Spring",
        "scholarship": "OSYS scholarship (at risk due to GPA)",
        "exchange_program": "Erasmus+",
        "home_university": "Politecnico di Milano",
        "entered_turkey": True,
        "preferred_language": "en",
    },
}


def seed_probe_user() -> None:
    db = SessionLocal()
    try:
        password_hash = AuthService.hash_password(PROBE_USER["password"])

        user_id = db.execute(text("""
            INSERT INTO users (email, password_hash, first_name, last_name, user_type, is_active, created_at)
            VALUES (:email, :password_hash, :first_name, :last_name, 'STUDENT', TRUE, NOW())
            ON CONFLICT (email) DO UPDATE
            SET password_hash = EXCLUDED.password_hash,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                user_type = 'STUDENT',
                is_active = TRUE
            RETURNING id
        """), {
            "email": PROBE_USER["email"],
            "password_hash": password_hash,
            "first_name": PROBE_USER["first_name"],
            "last_name": PROBE_USER["last_name"],
        }).scalar_one()

        db.execute(text("""
            INSERT INTO students (user_id, student_id, gpa, is_active)
            VALUES (:user_id, :student_id, :gpa, TRUE)
            ON CONFLICT (student_id) DO UPDATE
            SET user_id = EXCLUDED.user_id,
                gpa = EXCLUDED.gpa,
                is_active = TRUE
        """), {
            "user_id": user_id,
            "student_id": PROBE_USER["student_id"],
            "gpa": PROBE_USER["gpa"],
        })

        db.execute(text("""
            INSERT INTO user_profiles (
                user_id, department, faculty, program_level, academic_year,
                semester_number, total_credits_completed, total_credits_enrolled,
                is_on_probation, has_advisor_hold, has_financial_hold,
                is_exchange_student, is_double_major, is_minor, extra_context,
                created_at, updated_at
            )
            VALUES (
                :user_id, :department, :faculty, :program_level, :academic_year,
                :semester_number, :total_credits_completed, :total_credits_enrolled,
                TRUE, TRUE, TRUE,
                TRUE, TRUE, TRUE, CAST(:extra_context AS jsonb),
                NOW(), NOW()
            )
            ON CONFLICT (user_id) DO UPDATE
            SET department = EXCLUDED.department,
                faculty = EXCLUDED.faculty,
                program_level = EXCLUDED.program_level,
                academic_year = EXCLUDED.academic_year,
                semester_number = EXCLUDED.semester_number,
                total_credits_completed = EXCLUDED.total_credits_completed,
                total_credits_enrolled = EXCLUDED.total_credits_enrolled,
                is_on_probation = EXCLUDED.is_on_probation,
                has_advisor_hold = EXCLUDED.has_advisor_hold,
                has_financial_hold = EXCLUDED.has_financial_hold,
                is_exchange_student = EXCLUDED.is_exchange_student,
                is_double_major = EXCLUDED.is_double_major,
                is_minor = EXCLUDED.is_minor,
                extra_context = EXCLUDED.extra_context,
                updated_at = NOW()
        """), {
            "user_id": user_id,
            "department": PROBE_USER["department"],
            "faculty": PROBE_USER["faculty"],
            "program_level": PROBE_USER["program_level"],
            "academic_year": PROBE_USER["academic_year"],
            "semester_number": PROBE_USER["semester_number"],
            "total_credits_completed": PROBE_USER["total_credits_completed"],
            "total_credits_enrolled": PROBE_USER["total_credits_enrolled"],
            "extra_context": json.dumps(PROBE_USER["extra_context"]),
        })

        db.commit()

        print(f"Kitchen-sink probe user ready: {PROBE_USER['email']} / {PROBE_USER['password']}")
        print(f"Profile: GPA {PROBE_USER['gpa']} | senior | probation + advisor hold + financial hold")
        print("Flags: exchange student, double major, minor — all ON")
        print("NOTE: no assignments persisted. Run the regulation check yourself to see matches.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_probe_user()
