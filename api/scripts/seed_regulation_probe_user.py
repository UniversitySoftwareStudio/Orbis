"""Create a deterministic demo user for My Regulations testing.

The user has a deliberately low GPA so the SQL-backed regulation rules
match without needing an LLM call.

Run:
    python scripts/seed_regulation_probe_user.py
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

from database.models import User  # noqa: E402
from database.session import SessionLocal  # noqa: E402
from events.user_agent import _persist_assignments_detailed, _sql_rule_decisions  # noqa: E402
from services.auth_service import AuthService  # noqa: E402


PROBE_USER = {
    "email": "regulation.probe@bilgiedu.net",
    "password": "demo1234",
    "first_name": "Deniz",
    "last_name": "Probation",
    "student_id": "20258888",
    "gpa": 1.62,
    "department": "Computer Engineering",
    "faculty": "Faculty of Engineering and Natural Sciences",
    "program_level": "undergraduate",
    "academic_year": 2,
    "semester_number": 4,
    "total_credits_completed": 54,
    "total_credits_enrolled": 18,
    "extra_context": {
        "probe_case": "low_gpa_academic_probation",
        "specific_problem": "GPA below academic probation threshold",
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
                TRUE, TRUE, FALSE,
                FALSE, FALSE, FALSE, CAST(:extra_context AS jsonb),
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

        db.flush()
        user = db.get(User, user_id)
        if user is None:
            raise RuntimeError("Probe user was not created")

        decisions = _sql_rule_decisions(db, user)
        _persist_assignments_detailed(db, user, decisions)
        active = db.execute(text("""
            SELECT
                a.reason,
                r.rule_text,
                r.source_doc_url,
                r.evidence_quote
            FROM user_rule_assignments a
            JOIN regulation_rules r ON r.id = a.rule_id
            WHERE a.user_id = :user_id
              AND a.status = 'ACTIVE'
            ORDER BY a.assigned_at DESC
        """), {"user_id": user_id}).mappings().all()
        missing_source = [
            row for row in active
            if not row["source_doc_url"] or not row["evidence_quote"]
        ]

        print(f"Probe user ready: {PROBE_USER['email']} / {PROBE_USER['password']}")
        print(f"Profile: GPA {PROBE_USER['gpa']} | probation + advisor hold")
        print(f"SQL rules checked: {len(decisions)}")
        print(f"Active matching assignments: {len(active)}")
        print(f"Source-backed assignments: {len(active) - len(missing_source)}/{len(active)}")
        for row in active:
            print(f"- {row['reason']} :: {row['rule_text'][:90]}")
            print(f"  source: {row['source_doc_url']}")
            print(f"  quote: {(row['evidence_quote'] or '')[:140]}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_probe_user()
