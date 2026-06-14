"""Create a deterministic demo user for My Regulations testing — Erasmus case.

This user is an incoming exchange (Erasmus) student. Erasmus obligations are
CONTEXTUAL rules, normally matched via the LLM path. To keep the demo
deterministic (no LLM endpoint required), this script also persists the active
Erasmus regulation rules as ACTIVE assignments directly, mirroring how
``seed_regulation_probe_user.py`` persists its SQL matches.

Run:
    python scripts/seed_erasmus_probe_user.py
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
    "email": "erasmus.probe@bilgiedu.net",
    "password": "demo1234",
    "first_name": "Luca",
    "last_name": "Bianchi",
    "student_id": "20259999",
    "gpa": 3.10,
    "department": "Computer Engineering",
    "faculty": "Faculty of Engineering and Natural Sciences",
    "program_level": "undergraduate",
    "academic_year": 2,
    "semester_number": 3,
    "total_credits_completed": 36,
    "total_credits_enrolled": 15,
    "extra_context": {
        "probe_case": "incoming_erasmus_exchange",
        "specific_problem": "Incoming Erasmus exchange student — residence permit and exchange obligations apply",
        "home_university": "Politecnico di Milano",
        "exchange_program": "Erasmus+",
        "nationality": "Italian",
        "entered_turkey": True,
        "preferred_language": "en",
    },
}

# Active Erasmus / exchange obligations are matched contextually. We select them
# by their text so the script stays correct even if rule IDs change.
ERASMUS_RULE_FILTER = """
    status = 'ACTIVE'
    AND (
        rule_text ILIKE '%erasmus%'
        OR rule_text ILIKE '%exchange%'
        OR rule_text ILIKE '%residence permit%'
        OR rule_text ILIKE '%mobility%'
        OR rule_text ILIKE '%incoming student%'
    )
"""


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
                FALSE, FALSE, FALSE,
                TRUE, FALSE, FALSE, CAST(:extra_context AS jsonb),
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

        rules = db.execute(text(f"""
            SELECT id, rule_text
            FROM regulation_rules
            WHERE {ERASMUS_RULE_FILTER}
            ORDER BY rule_text
        """)).mappings().all()

        if not rules:
            raise RuntimeError("No active Erasmus/exchange regulation rules found to assign")

        # Persist each Erasmus rule as an ACTIVE contextual assignment. Idempotent
        # via the (user_id, rule_id) unique pair; re-running re-activates them.
        for rule in rules:
            urgency = "HIGH" if "residence permit" in rule["rule_text"].lower() else "MEDIUM"
            db.execute(text("""
                INSERT INTO user_rule_assignments (
                    id, user_id, rule_id, match_type, urgency, status, reason,
                    assigned_at, updated_at
                )
                VALUES (
                    gen_random_uuid(), :user_id, :rule_id, 'CONTEXTUAL', :urgency, 'ACTIVE',
                    :reason, NOW(), NOW()
                )
                ON CONFLICT (user_id, rule_id) DO UPDATE
                SET status = 'ACTIVE',
                    match_type = 'CONTEXTUAL',
                    urgency = EXCLUDED.urgency,
                    reason = EXCLUDED.reason,
                    updated_at = NOW()
            """), {
                "user_id": user_id,
                "rule_id": rule["id"],
                "urgency": urgency,
                "reason": "Incoming Erasmus exchange student — obligation applies",
            })

        db.commit()

        active = db.execute(text("""
            SELECT a.urgency, a.reason, r.rule_text, r.source_doc_url
            FROM user_rule_assignments a
            JOIN regulation_rules r ON r.id = a.rule_id
            WHERE a.user_id = :user_id AND a.status = 'ACTIVE'
            ORDER BY a.urgency, a.assigned_at DESC
        """), {"user_id": user_id}).mappings().all()

        print(f"Erasmus probe user ready: {PROBE_USER['email']} / {PROBE_USER['password']}")
        print(f"Profile: exchange student | {PROBE_USER['extra_context']['home_university']}")
        print(f"Active Erasmus assignments: {len(active)}")
        for row in active:
            print(f"- [{row['urgency']}] {row['reason']} :: {row['rule_text'][:90]}")
            print(f"  source: {row['source_doc_url']}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_probe_user()
