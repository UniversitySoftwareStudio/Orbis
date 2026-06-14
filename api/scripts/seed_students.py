"""
Seed script — generates demo student accounts.
~80% Turkish names, ~20% international.
All students get password: "demo1234"
Run: python scripts/seed_students.py
"""

import random
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from sqlalchemy import text
from database.session import SessionLocal
from services.auth_service import AuthService

# ---------- Name pools ----------

TURKISH_FIRST_MALE = [
    "Ahmet", "Mehmet", "Mustafa", "Ali", "Hüseyin", "İbrahim", "Hasan", "Ömer",
    "Emre", "Burak", "Can", "Cem", "Deniz", "Erkan", "Fatih", "Gökhan",
    "Haluk", "İlker", "Kadir", "Levent", "Murat", "Oğuz", "Onur", "Selim",
    "Sercan", "Tarık", "Uğur", "Volkan", "Yusuf", "Berk", "Alp", "Ege",
]
TURKISH_FIRST_FEMALE = [
    "Ayşe", "Fatma", "Zeynep", "Elif", "Hatice", "Emine", "Selin", "Merve",
    "Özge", "Büşra", "Ceren", "Dilan", "Ebru", "Gizem", "İpek", "Kübra",
    "Lale", "Melis", "Nilüfer", "Pınar", "Rüya", "Simge", "Tuğçe", "Yasemin",
    "Aslı", "Beren", "Cansu", "Damla", "Esra", "Nazlı",
]
TURKISH_LAST = [
    "Yılmaz", "Kaya", "Demir", "Çelik", "Şahin", "Doğan", "Arslan", "Aydın",
    "Öztürk", "Acar", "Bulut", "Çetin", "Erdoğan", "Güneş", "Koç", "Korkmaz",
    "Kurt", "Özdemir", "Polat", "Sarı", "Şimşek", "Tekin", "Uçar", "Yıldız",
    "Aksoy", "Aktaş", "Aslan", "Avcı", "Aygün", "Bayram", "Bilgin", "Bozkurt",
    "Çakır", "Duman", "Erbaş", "Erdem", "Güler", "Işık", "Kaplan", "Kılıç",
    "Mutlu", "Özkan", "Soylu", "Taş", "Türk", "Uysal", "Ünal", "Yalçın", "Zengin",
]

INTL_FIRST = [
    "James", "Emma", "Lucas", "Sophie", "Liam", "Mia", "Noah", "Olivia",
    "Ethan", "Chloe", "Mason", "Isabella", "Logan", "Amelia", "Aiden", "Ava",
    "Carlos", "Maria", "Ahmed", "Fatima", "Wei", "Yuki", "Arjun", "Priya",
    "Ivan", "Natasha", "Pierre", "Claire", "Erik", "Ingrid",
]
INTL_LAST = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Martinez",
    "Anderson", "Taylor", "Thomas", "Hernandez", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Lewis",
    "Robinson", "Walker", "Young", "Kim", "Nguyen", "Patel", "Singh", "Kumar",
]

PASSWORD_HASH = AuthService.hash_password("demo1234")
TOTAL_STUDENTS = 150

DEMO_STUDENT = {
    "email": "a.acar@bilgiedu.net",
    "first_name": "Alp",
    "last_name": "Acar",
    "student_id": "20260001",
    "gpa": 3.24,
    "department": "Computer Engineering",
    "faculty": "Faculty of Engineering and Natural Sciences",
    "program_level": "undergraduate",
    "academic_year": 3,
    "semester_number": 6,
    "total_credits_completed": 142,
    "total_credits_enrolled": 28,
    "is_on_probation": False,
    "has_advisor_hold": False,
    "has_financial_hold": False,
    "is_exchange_student": False,
    "is_double_major": False,
    "is_minor": True,
    "extra_context": {
        "minor_program": "Data Science",
        "internship_status": "not_started",
        "internship_form_submitted": False,
        "graduation_project": "not_started",
        "scholarship": "merit",
        "advisor": "Dr. Demo Advisor",
        "preferred_language": "en",
    },
}

DEMO_TRANSCRIPT = [
    ("FALL", 2024, "COMP 101", "Introduction to Programming", "AA", 4.0),
    ("FALL", 2024, "MATH 101", "Calculus I", "BA", 3.5),
    ("FALL", 2024, "ENG 101", "Academic English I", "AA", 4.0),
    ("FALL", 2024, "MATH 211", "Linear Algebra", "BB", 3.0),
    ("SPRING", 2025, "COMP 102", "Object-Oriented Programming", "BA", 3.5),
    ("SPRING", 2025, "COMP 201", "Data Structures and Algorithms", "BB", 3.0),
    ("SPRING", 2025, "COMP 204", "Database Systems", "AA", 4.0),
    ("SPRING", 2025, "MATH 220", "Probability and Statistics", "CB", 2.5),
]


def _make_email(first: str, last: str, existing_emails: set) -> str:
    """Generate email, appending a number suffix if collision."""
    # Normalize: remove non-ASCII for email safety
    import unicodedata
    def norm(s):
        s = unicodedata.normalize("NFD", s)
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        return s.lower().replace(" ", "").replace("'", "")

    base = f"{norm(first)[0]}.{norm(last)}@bilgiedu.net"
    if base not in existing_emails:
        return base
    # collision — append numbers until unique
    for i in range(2, 99):
        candidate = f"{norm(first)[0]}.{norm(last)}{i}@bilgiedu.net"
        if candidate not in existing_emails:
            return candidate
    raise ValueError(f"Could not generate unique email for {first} {last}")


def _ensure_demo_student(db) -> None:
    """Create or refresh the named demo student used in walkthroughs."""
    user = db.execute(text("""
        SELECT id FROM users WHERE email = :email
    """), {"email": DEMO_STUDENT["email"]}).fetchone()

    if user:
        user_id = user[0]
        db.execute(text("""
            UPDATE users
            SET password_hash = :pw,
                first_name = :first,
                last_name = :last,
                user_type = 'STUDENT',
                is_active = TRUE
            WHERE id = :uid
        """), {
            "uid": user_id,
            "pw": PASSWORD_HASH,
            "first": DEMO_STUDENT["first_name"],
            "last": DEMO_STUDENT["last_name"],
        })
    else:
        user_id = db.execute(text("""
            INSERT INTO users (email, password_hash, first_name, last_name, user_type, is_active, created_at)
            VALUES (:email, :pw, :first, :last, 'STUDENT', TRUE, NOW())
            RETURNING id
        """), {
            "email": DEMO_STUDENT["email"],
            "pw": PASSWORD_HASH,
            "first": DEMO_STUDENT["first_name"],
            "last": DEMO_STUDENT["last_name"],
        }).fetchone()[0]

    existing_student = db.execute(text("""
        SELECT id FROM students WHERE user_id = :uid
    """), {"uid": user_id}).fetchone()

    if existing_student:
        db.execute(text("""
            UPDATE students
            SET student_id = :sid,
                gpa = :gpa,
                is_active = TRUE
            WHERE user_id = :uid
        """), {
            "uid": user_id,
            "sid": DEMO_STUDENT["student_id"],
            "gpa": DEMO_STUDENT["gpa"],
        })
    else:
        db.execute(text("""
            INSERT INTO students (user_id, student_id, gpa, is_active)
            VALUES (:uid, :sid, :gpa, TRUE)
            ON CONFLICT (student_id) DO UPDATE
            SET user_id = EXCLUDED.user_id,
                gpa = EXCLUDED.gpa,
                is_active = TRUE
        """), {
            "uid": user_id,
            "sid": DEMO_STUDENT["student_id"],
            "gpa": DEMO_STUDENT["gpa"],
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
            :uid, :department, :faculty, :program_level, :academic_year,
            :semester_number, :total_credits_completed, :total_credits_enrolled,
            :is_on_probation, :has_advisor_hold, :has_financial_hold,
            :is_exchange_student, :is_double_major, :is_minor, CAST(:extra_context AS jsonb),
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
        "uid": user_id,
        "department": DEMO_STUDENT["department"],
        "faculty": DEMO_STUDENT["faculty"],
        "program_level": DEMO_STUDENT["program_level"],
        "academic_year": DEMO_STUDENT["academic_year"],
        "semester_number": DEMO_STUDENT["semester_number"],
        "total_credits_completed": DEMO_STUDENT["total_credits_completed"],
        "total_credits_enrolled": DEMO_STUDENT["total_credits_enrolled"],
        "is_on_probation": DEMO_STUDENT["is_on_probation"],
        "has_advisor_hold": DEMO_STUDENT["has_advisor_hold"],
        "has_financial_hold": DEMO_STUDENT["has_financial_hold"],
        "is_exchange_student": DEMO_STUDENT["is_exchange_student"],
        "is_double_major": DEMO_STUDENT["is_double_major"],
        "is_minor": DEMO_STUDENT["is_minor"],
        "extra_context": json.dumps(DEMO_STUDENT["extra_context"]),
    })

    print(
        f"✅  Demo student ready: {DEMO_STUDENT['first_name']} {DEMO_STUDENT['last_name']} "
        f"({DEMO_STUDENT['email']} / demo1234)"
    )


def _ensure_demo_transcript(db) -> None:
    row = db.execute(text("""
        SELECT u.id AS user_id, s.id AS student_pk
        FROM users u
        JOIN students s ON s.user_id = u.id
        WHERE u.email = :email
    """), {"email": DEMO_STUDENT["email"]}).mappings().first()
    if not row:
        return

    student_pk = row["student_pk"]
    user_id = row["user_id"]

    for term_type, year, code, name, grade, numeric in DEMO_TRANSCRIPT:
        start_date = f"{year}-09-15" if term_type == "FALL" else f"{year}-02-10"
        end_date = f"{year}-12-30" if term_type == "FALL" else f"{year}-05-30"
        term_id = db.execute(text("""
            INSERT INTO academic_terms (code, term_type, year, start_date, end_date, is_active)
            VALUES (:code, :term_type, :year, :start_date, :end_date, FALSE)
            ON CONFLICT (code) DO UPDATE
            SET term_type = EXCLUDED.term_type,
                year = EXCLUDED.year,
                start_date = EXCLUDED.start_date,
                end_date = EXCLUDED.end_date
            RETURNING id
        """), {
            "code": f"{year}-{term_type}",
            "term_type": term_type,
            "year": year,
            "start_date": start_date,
            "end_date": end_date,
        }).scalar_one()

        course_id = db.execute(text("""
            INSERT INTO courses (code, name)
            VALUES (:code, :name)
            ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
        """), {"code": code, "name": name}).scalar_one()

        section = db.execute(text("""
            SELECT id FROM course_sections
            WHERE course_id = :course_id
              AND term_id = :term_id
              AND section_number = '01'
              AND section_type = 'LECTURE'
            LIMIT 1
        """), {"course_id": course_id, "term_id": term_id}).fetchone()
        if section:
            section_id = section[0]
        else:
            section_id = db.execute(text("""
                INSERT INTO course_sections (
                    course_id, term_id, section_number, section_type,
                    instructor_name, max_enrollment, current_enrollment, status
                )
                VALUES (:course_id, :term_id, '01', 'LECTURE', 'Demo Instructor', 60, 0, 'COMPLETED')
                RETURNING id
            """), {"course_id": course_id, "term_id": term_id}).scalar_one()

        db.execute(text("""
            INSERT INTO enrollments (
                student_id, section_id, status, final_grade_letter, final_grade_numeric, enrolled_at
            )
            VALUES (:student_id, :section_id, 'COMPLETED', :grade, :numeric, NOW())
            ON CONFLICT (student_id, section_id) DO UPDATE
            SET status = 'COMPLETED',
                final_grade_letter = EXCLUDED.final_grade_letter,
                final_grade_numeric = EXCLUDED.final_grade_numeric
        """), {
            "student_id": student_pk,
            "section_id": section_id,
            "grade": grade,
            "numeric": numeric,
        })

    gpa = db.execute(text("""
        SELECT ROUND(AVG(final_grade_numeric)::numeric, 2)
        FROM enrollments
        WHERE student_id = :student_id
          AND status = 'COMPLETED'
          AND final_grade_numeric IS NOT NULL
    """), {"student_id": student_pk}).scalar_one()

    db.execute(text("UPDATE students SET gpa = :gpa WHERE id = :student_id"), {
        "gpa": gpa,
        "student_id": student_pk,
    })
    db.execute(text("""
        UPDATE user_profiles
        SET total_credits_completed = GREATEST(COALESCE(total_credits_completed, 0), :credits),
            updated_at = NOW()
        WHERE user_id = :user_id
    """), {"credits": len(DEMO_TRANSCRIPT) * 3, "user_id": user_id})

    print(f"✅  Demo transcript ready: {len(DEMO_TRANSCRIPT)} completed courses, GPA {gpa}")


def _ensure_demo_active_enrollment(db) -> None:
    """Enroll the demo student (ACTIVE) in a section that has published
    assignments, so /assignments/me returns work to submit in the demo video.
    Idempotent."""
    row = db.execute(text("""
        SELECT s.id AS student_pk
        FROM users u JOIN students s ON s.user_id = u.id
        WHERE u.email = :email
    """), {"email": DEMO_STUDENT["email"]}).mappings().first()
    if not row:
        print("⚠️  Demo active enrollment skipped: no students row for demo user.")
        return
    student_pk = row["student_pk"]

    # Enroll the demo student (ACTIVE) in EVERY section that has published
    # assignments, so the assignments page shows several items for a richer demo.
    sections = [
        r[0] for r in db.execute(text("""
            SELECT DISTINCT section_id FROM assignments WHERE is_published = TRUE
        """)).fetchall()
    ]
    if not sections:
        print("⚠️  No published assignments exist — cannot create demo enrollment.")
        return

    for section in sections:
        db.execute(text("""
            INSERT INTO enrollments (student_id, section_id, status, enrolled_at)
            VALUES (:student_id, :section_id, 'ENROLLED', NOW())
            ON CONFLICT (student_id, section_id) DO UPDATE
            SET status = 'ENROLLED'
        """), {"student_id": student_pk, "section_id": section})

    n = db.execute(text("""
        SELECT count(*) FROM assignments a
        WHERE a.is_published = TRUE AND a.section_id = ANY(:sids)
    """), {"sids": sections}).scalar_one()
    print(f"✅  Demo active enrollment ready: {len(sections)} section(s), {n} published assignment(s).")


def run():
    print("Connecting...")
    db = SessionLocal()
    db.execute(text("SET statement_timeout = '30s'"))

    try:
        _ensure_demo_student(db)
        _ensure_demo_transcript(db)
        _ensure_demo_active_enrollment(db)
        db.commit()

        # Fetch existing student emails to avoid conflicts
        existing = db.execute(text(
            "SELECT email FROM users WHERE user_type = 'STUDENT'"
        )).fetchall()
        existing_emails: set = {r[0] for r in existing}
        print(f"Found {len(existing_emails)} existing student accounts.")

        # Get next student_id number
        max_sid = db.execute(text(
            "SELECT MAX(CAST(REGEXP_REPLACE(student_id, '[^0-9]', '', 'g') AS INTEGER)) "
            "FROM students"
        )).scalar()
        next_num = (max_sid or 20250000) + 1

        created = 0
        BATCH = 30

        for i in range(TOTAL_STUDENTS):
            if i % BATCH == 0 and i > 0:
                db.commit()
                print(f"  Created {created} students so far...")

            # 80% Turkish, 20% international
            is_turkish = random.random() < 0.80

            if is_turkish:
                is_female = random.random() < 0.50
                first = random.choice(TURKISH_FIRST_FEMALE if is_female else TURKISH_FIRST_MALE)
                last = random.choice(TURKISH_LAST)
            else:
                first = random.choice(INTL_FIRST)
                last = random.choice(INTL_LAST)

            try:
                email = _make_email(first, last, existing_emails)
            except ValueError:
                continue  # skip on rare collision exhaustion

            existing_emails.add(email)
            student_id_str = f"{next_num + i:08d}"

            # Insert user
            user_result = db.execute(text("""
                INSERT INTO users (email, password_hash, first_name, last_name, user_type, is_active, created_at)
                VALUES (:email, :pw, :first, :last, 'STUDENT', TRUE, NOW())
                RETURNING id
            """), {
                "email": email, "pw": PASSWORD_HASH,
                "first": first, "last": last,
            })
            user_id = user_result.fetchone()[0]

            # Insert student profile
            db.execute(text("""
                INSERT INTO students (user_id, student_id, gpa, is_active)
                VALUES (:uid, :sid, :gpa, TRUE)
            """), {
                "uid": user_id,
                "sid": student_id_str,
                "gpa": round(random.uniform(1.80, 4.00), 2),
            })
            created += 1

        db.commit()
        print(f"✅  Done. Created {created} student accounts.")
        print(f"    Login with any student email + password: demo1234")
        print(f"    Example: check 'SELECT email FROM users WHERE user_type = 'STUDENT' LIMIT 5'")

    finally:
        db.close()


if __name__ == "__main__":
    run()
