"""Enroll the kitchen-sink probe student into real course sections.

Scoped to a single user (kitchensink.probe@bilgiedu.net) so it does NOT touch
any other student's enrollments. Idempotent: clears only this student's
enrollments, then enrolls them into a handful of active lecture sections from
the active term (plus one lab per lecture if the lecture has lab children).

Run:
    python3 scripts/seed_kitchen_sink_courses.py
"""

from __future__ import annotations

import os
import random
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from database.session import SessionLocal  # noqa: E402

TARGET_EMAIL = "kitchensink.probe@bilgiedu.net"
NUM_LECTURES = 6


def run() -> None:
    db = SessionLocal()
    try:
        student_id = db.execute(text("""
            SELECT s.id FROM students s
            JOIN users u ON u.id = s.user_id
            WHERE u.email = :email
        """), {"email": TARGET_EMAIL}).scalar()
        if student_id is None:
            raise RuntimeError(f"No student found for {TARGET_EMAIL}")

        term_id = db.execute(text(
            "SELECT id FROM academic_terms WHERE is_active = TRUE ORDER BY id DESC LIMIT 1"
        )).scalar()
        if term_id is None:
            raise RuntimeError("No active academic term")

        lecture_ids = [r[0] for r in db.execute(text("""
            SELECT id FROM course_sections
            WHERE term_id = :tid
              AND section_type = 'LECTURE'
              AND parent_section_id IS NULL
              AND status = 'ACTIVE'
        """), {"tid": term_id}).fetchall()]
        if not lecture_ids:
            raise RuntimeError("No active lecture sections in the active term")

        labs_by_lecture: dict[int, list[int]] = {}
        for parent_id, lab_id in db.execute(text("""
            SELECT parent_section_id, id FROM course_sections
            WHERE term_id = :tid AND section_type = 'LAB' AND status = 'ACTIVE'
        """), {"tid": term_id}).fetchall():
            labs_by_lecture.setdefault(parent_id, []).append(lab_id)

        # Only clear THIS student's enrollments — leave everyone else alone.
        cleared = db.execute(text(
            "DELETE FROM enrollments WHERE student_id = :sid"
        ), {"sid": student_id}).rowcount

        chosen = random.sample(lecture_ids, k=min(NUM_LECTURES, len(lecture_ids)))
        enrolled = 0
        for lecture_id in chosen:
            db.execute(text("""
                INSERT INTO enrollments (student_id, section_id, status, enrolled_at)
                VALUES (:sid, :secid, 'ENROLLED', NOW())
                ON CONFLICT (student_id, section_id) DO NOTHING
            """), {"sid": student_id, "secid": lecture_id})
            enrolled += 1
            if lecture_id in labs_by_lecture:
                lab_id = random.choice(labs_by_lecture[lecture_id])
                db.execute(text("""
                    INSERT INTO enrollments (student_id, section_id, status, enrolled_at)
                    VALUES (:sid, :secid, 'ENROLLED', NOW())
                    ON CONFLICT (student_id, section_id) DO NOTHING
                """), {"sid": student_id, "secid": lab_id})
                enrolled += 1

        db.commit()

        rows = db.execute(text("""
            SELECT c.code, c.name, cs.section_type
            FROM enrollments e
            JOIN course_sections cs ON cs.id = e.section_id
            JOIN courses c ON c.id = cs.course_id
            WHERE e.student_id = :sid AND e.status = 'ENROLLED'
            ORDER BY c.code
        """), {"sid": student_id}).all()

        print(f"Cleared {cleared} old enrollment(s) for {TARGET_EMAIL}")
        print(f"Enrolled into {enrolled} section(s):")
        for code, name, stype in rows:
            print(f"  - {code} ({stype}): {name}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
