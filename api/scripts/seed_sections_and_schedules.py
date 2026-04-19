"""
Generates demo section schedules for all existing courses.
Creates 1-2 lecture sections per course, optionally 1-2 lab sections per lecture section.
Assigns random but non-overlapping time slots (within the same course).
Run: python scripts/seed_sections_and_schedules.py

Assumptions:
- A spring term with is_active=TRUE already exists in academic_terms.
- Courses exist in the courses table.
- No instructor FK is set — instructor_name is used instead for simplicity.
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

DAYS = ["MON", "TUE", "WED", "THU", "FRI"]

# Possible time slots (start, end) in 1h and 2h blocks between 09:00-19:00
TIME_SLOTS = [
    ("09:00", "10:00"), ("09:00", "11:00"), ("09:00", "12:00"),
    ("10:00", "11:00"), ("10:00", "12:00"), ("10:00", "13:00"),
    ("11:00", "12:00"), ("11:00", "13:00"),
    ("13:00", "14:00"), ("13:00", "15:00"), ("13:00", "16:00"),
    ("14:00", "15:00"), ("14:00", "16:00"),
    ("15:00", "16:00"), ("15:00", "17:00"),
    ("16:00", "17:00"), ("16:00", "18:00"),
    ("17:00", "18:00"), ("17:00", "19:00"),
    ("18:00", "19:00"),
]

LOCATIONS = [
    "Santral E1-101", "Santral E1-102", "Santral E1-103", "Santral E1-201",
    "Santral E1-202", "Santral E1-301", "Santral E2-101", "Santral E2-102",
    "Santral E3-101", "Santral E3-204", "Santral ÇSM-101", "Santral ÇSM-302",
    "Dolapdere B1-101", "Dolapdere B1-201", "Dolapdere B2-104",
    "Kuştepe A1-101", "Kuştepe A1-201",
]

INSTRUCTORS = [
    "Ahmet Yılmaz", "Elif Kaya", "Mehmet Demir", "Ayşe Çelik", "Mustafa Şahin",
    "Zeynep Arslan", "Ali Öztürk", "Fatma Koç", "Hüseyin Aydın", "Selin Doğan",
    "Emre Çetin", "Deniz Erdoğan", "Can Korkmaz", "İpek Güneş", "Burak Aksoy",
]

LAB_INSTRUCTORS = [
    "Arş. Gör. Tuba Polat", "Arş. Gör. Onur Acar", "Arş. Gör. Simge Yurt",
    "Arş. Gör. Berkay Işık", "Arş. Gör. Merve Kaplan", "Arş. Gör. Tarık Sezer",
]


def slots_overlap(s1_start, s1_end, s1_day, s2_start, s2_end, s2_day):
    if s1_day != s2_day:
        return False
    return not (s1_end <= s2_start or s2_end <= s1_start)


def pick_non_overlapping_slot(used_slots, duration_hours=None):
    """Pick a (day, start, end) tuple that doesn't overlap with used_slots."""
    candidates = list(TIME_SLOTS)
    random.shuffle(candidates)
    for start, end in candidates:
        day = random.choice(DAYS)
        overlaps = any(
            slots_overlap(start, end, day, u[1], u[2], u[0])
            for u in used_slots
        )
        if not overlaps:
            return day, start, end
    return None  # exhausted — shouldn't happen in practice


def run():
    print("Connecting to DB...")
    db = SessionLocal()
    print("Connected. Fetching term...")
    try:
        # Get active term
        print("Fetching active term...")
        term = db.execute(text(
            "SELECT id FROM academic_terms WHERE is_active = TRUE ORDER BY id DESC LIMIT 1"
        ), execution_options={"timeout": 5}).fetchone()
        if not term:
            print("No active term found — creating 2025-2026 Spring term...")
            result = db.execute(text("""
                INSERT INTO academic_terms (code, term_type, year, start_date, end_date, is_active)
                VALUES ('2025-2026-SPRING', 'SPRING', 2026, '2026-02-23', '2026-06-05', TRUE)
                ON CONFLICT (code) DO UPDATE SET is_active = TRUE
                RETURNING id
            """))
            db.commit()
            term_id = result.fetchone()[0]
            print(f"Created term with id={term_id}")
        else:
            term_id = term[0]
            print(f"Using term id={term_id}")

        # Get all courses
        print("Fetching courses...")
        courses = db.execute(text("SELECT id, code FROM courses ORDER BY id")).fetchall()
        print(f"Got {len(courses)} courses.")

        if not courses:
            print("❌  No courses found.")
            return

        section_count = 0
        schedule_count = 0

        print(f"Got {len(courses)} courses. Starting section generation...")
        section_count = 0
        schedule_count = 0
        BATCH_SIZE = 50

        for idx, (course_id, course_code) in enumerate(courses):
            # Progress indicator every 50 courses
            if idx % BATCH_SIZE == 0:
                print(f"  Processing course {idx+1}/{len(courses)}...")
                db.commit()  # commit in batches instead of one giant transaction

            num_sections = random.choices([1, 2], weights=[40, 60])[0]
            course_used_slots = []

            for sec_idx in range(num_sections):
                section_number = f"{sec_idx + 1:02d}"
                instructor = random.choice(INSTRUCTORS)
                is_online = random.random() < 0.15

                result = db.execute(text("""
                    INSERT INTO course_sections
                        (course_id, term_id, section_number, section_type, instructor_name,
                         max_enrollment, current_enrollment, status)
                    VALUES
                        (:course_id, :term_id, :section_number, 'LECTURE', :instructor_name,
                         :max_enroll, :cur_enroll, 'ACTIVE')
                    RETURNING id
                """), {
                    "course_id": course_id, "term_id": term_id,
                    "section_number": section_number, "instructor_name": instructor,
                    "max_enroll": random.randint(25, 60),
                    "cur_enroll": random.randint(10, 24),
                })
                lecture_section_id = result.fetchone()[0]
                section_count += 1

                num_lecture_slots = random.choices([1, 2], weights=[50, 50])[0]
                for _ in range(num_lecture_slots):
                    slot = pick_non_overlapping_slot(course_used_slots)
                    if slot is None:
                        break
                    day, start, end = slot
                    course_used_slots.append((day, start, end))
                    location = None if is_online else random.choice(LOCATIONS)
                    db.execute(text("""
                        INSERT INTO section_schedules
                            (section_id, day_of_week, start_time, end_time, location, is_online)
                        VALUES (:sid, :day, :start, :end, :loc, :online)
                    """), {
                        "sid": lecture_section_id, "day": day,
                        "start": start, "end": end,
                        "loc": location, "online": is_online,
                    })
                    schedule_count += 1

                has_labs = random.random() < 0.4
                if not has_labs:
                    continue

                num_lab_sections = random.choices([1, 2], weights=[60, 40])[0]
                for lab_idx in range(num_lab_sections):
                    lab_number = f"{section_number}{lab_idx + 1:02d}"
                    lab_instructor = random.choice(LAB_INSTRUCTORS)
                    lab_is_online = random.random() < 0.1

                    result = db.execute(text("""
                        INSERT INTO course_sections
                            (course_id, term_id, section_number, section_type,
                             parent_section_id, instructor_name,
                             max_enrollment, current_enrollment, status)
                        VALUES
                            (:course_id, :term_id, :section_number, 'LAB',
                             :parent_id, :instructor_name,
                             :max_enroll, :cur_enroll, 'ACTIVE')
                        RETURNING id
                    """), {
                        "course_id": course_id, "term_id": term_id,
                        "section_number": lab_number, "parent_id": lecture_section_id,
                        "instructor_name": lab_instructor,
                        "max_enroll": random.randint(15, 30),
                        "cur_enroll": random.randint(5, 14),
                    })
                    lab_section_id = result.fetchone()[0]
                    section_count += 1

                    slot = pick_non_overlapping_slot(course_used_slots)
                    if slot:
                        day, start, end = slot
                        course_used_slots.append((day, start, end))
                        location = None if lab_is_online else random.choice(LOCATIONS)
                        db.execute(text("""
                            INSERT INTO section_schedules
                                (section_id, day_of_week, start_time, end_time, location, is_online)
                            VALUES (:sid, :day, :start, :end, :loc, :online)
                        """), {
                            "sid": lab_section_id, "day": day,
                            "start": start, "end": end,
                            "loc": location, "online": lab_is_online,
                        })
                        schedule_count += 1

        db.commit()
        print(f"✅  Created {section_count} sections and {schedule_count} schedule slots across {len(courses)} courses.")
        print("    Next: run seed_enrollments.py to assign students to sections.")

    finally:
        db.close()


if __name__ == "__main__":
    run()