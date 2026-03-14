"""
Seed script — generates demo student accounts.
~80% Turkish names, ~20% international.
All students get password: "demo1234"
Run: python scripts/seed_students.py
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


def run():
    print("Connecting...")
    db = SessionLocal()
    db.execute(text("SET statement_timeout = '30s'"))

    try:
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