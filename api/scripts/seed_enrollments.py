"""
Seed enrollments for demo purposes.
Assigns each student 4-8 randomly chosen LECTURE sections from the active term.
If a lecture section has lab children, also enrolls the student in one random lab.
Run: python scripts/seed_enrollments.py
"""

import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from sqlalchemy import text
from database.session import SessionLocal


def run():
    print("Connecting...")
    db = SessionLocal()
    db.execute(text("SET statement_timeout = '30s'"))

    try:
        # Get active term
        term = db.execute(text(
            "SELECT id FROM academic_terms WHERE is_active = TRUE ORDER BY id DESC LIMIT 1"
        )).fetchone()
        if not term:
            print("❌  No active term.")
            return
        term_id = term[0]
        print(f"Term id={term_id}")

        # Get all students
        students = db.execute(text("SELECT id FROM students WHERE is_active = TRUE")).fetchall()
        if not students:
            print("❌  No active students found.")
            return
        print(f"Found {len(students)} students.")

        # Get all LECTURE sections for active term, with their lab children
        lecture_sections = db.execute(text("""
            SELECT id FROM course_sections
            WHERE term_id = :tid
              AND section_type = 'LECTURE'
              AND parent_section_id IS NULL
              AND status = 'ACTIVE'
        """), {"tid": term_id}).fetchall()
        lecture_ids = [r[0] for r in lecture_sections]
        print(f"Found {len(lecture_ids)} lecture sections.")

        # Build lab lookup: lecture_id -> [lab_section_id, ...]
        lab_rows = db.execute(text("""
            SELECT parent_section_id, id FROM course_sections
            WHERE term_id = :tid
              AND section_type = 'LAB'
              AND status = 'ACTIVE'
        """), {"tid": term_id}).fetchall()
        labs_by_lecture: dict[int, list[int]] = {}
        for parent_id, lab_id in lab_rows:
            labs_by_lecture.setdefault(parent_id, []).append(lab_id)

        # Clear existing enrollments to allow safe re-runs
        deleted = db.execute(text("DELETE FROM enrollments")).rowcount
        db.commit()
        print(f"Cleared {deleted} existing enrollments.")

        enrollment_count = 0
        BATCH_SIZE = 20

        for idx, (student_id,) in enumerate(students):
            if idx % BATCH_SIZE == 0:
                db.commit()
                print(f"  Enrolling student {idx+1}/{len(students)}...")

            # Pick 4-8 random lecture sections (no course duplicates)
            chosen_lectures = random.sample(lecture_ids, k=min(random.randint(4, 8), len(lecture_ids)))

            for lecture_id in chosen_lectures:
                db.execute(text("""
                    INSERT INTO enrollments (student_id, section_id, status, enrolled_at)
                    VALUES (:sid, :secid, 'ENROLLED', NOW())
                    ON CONFLICT (student_id, section_id) DO NOTHING
                """), {"sid": student_id, "secid": lecture_id})
                enrollment_count += 1

                # If this lecture has labs, enroll in one random lab
                if lecture_id in labs_by_lecture:
                    lab_id = random.choice(labs_by_lecture[lecture_id])
                    db.execute(text("""
                        INSERT INTO enrollments (student_id, section_id, status, enrolled_at)
                        VALUES (:sid, :secid, 'ENROLLED', NOW())
                        ON CONFLICT (student_id, section_id) DO NOTHING
                    """), {"sid": student_id, "secid": lab_id})
                    enrollment_count += 1

        db.commit()
        print(f"✅  Done. {enrollment_count} enrollments across {len(students)} students.")

    finally:
        db.close()


if __name__ == "__main__":
    run()