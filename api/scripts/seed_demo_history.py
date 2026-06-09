"""
Demo seeder — fills the two empty student-facing surfaces so the portal looks
real for a walkthrough:

  1. Transcript: past academic terms with COMPLETED, graded enrollments.
  2. Regulations (Push path): realistic regulation_rules + user_rule_assignments.

Idempotent-ish: skips a student who already has completed enrollments.
Run: python scripts/seed_demo_history.py
"""
import os
import sys
import random
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from sqlalchemy import text
from database.session import SessionLocal

# A believable CS history: (code, name, typical grade pool)
PAST_COURSES = [
    ("COMP 101", "Introduction to Programming"),
    ("MATH 101", "Calculus I"),
    ("ENG 101", "Academic English I"),
    ("COMP 102", "Object-Oriented Programming"),
    ("MATH 211", "Linear Algebra"),
    ("COMP 201", "Data Structures and Algorithms"),
    ("MATH 220", "Probability and Statistics"),
    ("COMP 204", "Database Systems"),
]
GRADES = [("AA", 4.0), ("BA", 3.5), ("BB", 3.0), ("CB", 2.5), ("CC", 2.0)]

PAST_TERMS = [("FALL", 2024), ("SPRING", 2025)]

# Regulation obligations (Push) — written like extracted directives.
RULES = [
    dict(rule_text="Students must complete the mandatory summer internship (min. 20 working days) before graduation and submit the internship report through the SIS.",
         applies_to="Undergraduate students who have completed 4 semesters",
         trigger="Reaching 60+ completed ECTS credits", deadline="Before final-year registration",
         consequence="Graduation is blocked until the internship requirement is fulfilled.",
         authority="Faculty of Engineering Internship Committee", blocking=True, urgency="HIGH",
         reason="You have completed enough credits to be eligible; the internship is still pending."),
    dict(rule_text="Students whose cumulative GPA falls below 2.00 are placed on academic probation and must meet their academic advisor before the add/drop period.",
         applies_to="Students with CGPA < 2.50", trigger="CGPA below threshold at term end",
         deadline="Before add/drop deadline", consequence="Course load may be restricted for the following term.",
         authority="Office of the Registrar", blocking=False, urgency="MEDIUM",
         reason="Your current CGPA is close to the advisory threshold."),
    dict(rule_text="Double Major / Minor / Department Change applications must be submitted online during the announced application window for the Fall semester.",
         applies_to="Students with CGPA ≥ 3.00 and no failing grades", trigger="Application window open",
         deadline="July 21, 2025", consequence="Late applications are not accepted for this cycle.",
         authority="Academic Affairs", blocking=False, urgency="LOW",
         reason="You are eligible and the application window is approaching."),
]


def run():
    db = SessionLocal()
    try:
        students = db.execute(text("SELECT id, user_id FROM students ORDER BY id")).fetchall()
        # Map course code -> course_id (create missing past courses)
        def course_id(code, name):
            row = db.execute(text("SELECT id FROM courses WHERE code = :c"), {"c": code}).fetchone()
            if row:
                return row[0]
            db.execute(text("INSERT INTO courses (code, name) VALUES (:c, :n)"), {"c": code, "n": name})
            return db.execute(text("SELECT id FROM courses WHERE code = :c"), {"c": code}).fetchone()[0]

        # Ensure past terms exist; map (type,year)->term_id
        term_ids = {}
        for ttype, year in PAST_TERMS:
            row = db.execute(text("SELECT id FROM academic_terms WHERE term_type = :t AND year = :y"),
                             {"t": ttype, "y": year}).fetchone()
            if not row:
                sd, ed = (date(year, 9, 15), date(year, 12, 30)) if ttype == "FALL" else (date(year, 2, 10), date(year, 5, 30))
                db.execute(text(
                    "INSERT INTO academic_terms (code, term_type, year, is_active, start_date, end_date) "
                    "VALUES (:code, :t, :y, false, :sd, :ed)"
                ), {"code": f"{year}-{ttype}", "t": ttype, "y": year, "sd": sd, "ed": ed})
                row = db.execute(text("SELECT id FROM academic_terms WHERE term_type = :t AND year = :y"),
                                 {"t": ttype, "y": year}).fetchone()
            term_ids[(ttype, year)] = row[0]

        # One past LECTURE section per (course, term), reused across students.
        def section_for(cid, term_id):
            row = db.execute(text(
                "SELECT id FROM course_sections WHERE course_id = :c AND term_id = :t AND section_type = 'LECTURE' LIMIT 1"
            ), {"c": cid, "t": term_id}).fetchone()
            if row:
                return row[0]
            db.execute(text(
                "INSERT INTO course_sections (course_id, term_id, section_number, section_type, instructor_name, max_enrollment, current_enrollment) "
                "VALUES (:c, :t, '01', 'LECTURE', 'Staff', 60, 0)"
            ), {"c": cid, "t": term_id})
            return db.execute(text(
                "SELECT id FROM course_sections WHERE course_id = :c AND term_id = :t AND section_type = 'LECTURE' LIMIT 1"
            ), {"c": cid, "t": term_id}).fetchone()[0]

        cids = [(c, n, course_id(c, n)) for c, n in PAST_COURSES]

        transcript_count = 0
        for student_id, _user_id in students:
            already = db.execute(text(
                "SELECT 1 FROM enrollments WHERE student_id = :s AND status = 'COMPLETED' LIMIT 1"
            ), {"s": student_id}).fetchone()
            if already:
                continue
            # split the 8 courses across the two past terms
            for idx, (code, name, cid) in enumerate(cids):
                ttype, year = PAST_TERMS[idx % len(PAST_TERMS)]
                sec = section_for(cid, term_ids[(ttype, year)])
                letter, num = random.choices(GRADES, weights=[3, 4, 4, 2, 2])[0]
                db.execute(text(
                    "INSERT INTO enrollments (student_id, section_id, status, final_grade_letter, final_grade_numeric, enrolled_at) "
                    "VALUES (:s, :sec, 'COMPLETED', :gl, :gn, now()) "
                    "ON CONFLICT (student_id, section_id) DO NOTHING"
                ), {"s": student_id, "sec": sec, "gl": letter, "gn": num})
                transcript_count += 1
        db.commit()
        print(f"✅  Transcript: created {transcript_count} completed graded enrollments.")

        # --- Regulations (Push) ---
        rule_ids = []
        for i, r in enumerate(RULES):
            fp = f"demo-rule-{i}"
            row = db.execute(text("SELECT id FROM regulation_rules WHERE fingerprint = :f"), {"f": fp}).fetchone()
            if row:
                rule_ids.append(row[0]); continue
            db.execute(text(
                "INSERT INTO regulation_rules "
                "(source_doc_url, source_chunk_ids, evidence_quote, rule_text, applies_to, trigger, deadline, "
                " blocking, consequence, authority, target_role, match_type, status, fingerprint) "
                "VALUES (:url, '[]'::jsonb, :ev, :rt, :ap, :tr, :dl, :bl, :cn, :au, 'STUDENT', 'CONTEXTUAL', 'ACTIVE', :fp)"
            ), {
                "url": "https://www.bilgi.edu.tr/regulations/demo", "ev": r["rule_text"][:120],
                "rt": r["rule_text"], "ap": r["applies_to"], "tr": r["trigger"], "dl": r["deadline"],
                "bl": r["blocking"], "cn": r["consequence"], "au": r["authority"], "fp": fp,
            })
            rule_ids.append(db.execute(text("SELECT id FROM regulation_rules WHERE fingerprint = :f"), {"f": fp}).fetchone()[0])
        db.commit()

        # Assign all three to every student (demo: everyone has obligations).
        assign_count = 0
        for student_id, user_id in students:
            for r, rid in zip(RULES, rule_ids):
                exists = db.execute(text(
                    "SELECT 1 FROM user_rule_assignments WHERE user_id = :u AND rule_id = :r"
                ), {"u": user_id, "r": rid}).fetchone()
                if exists:
                    continue
                db.execute(text(
                    "INSERT INTO user_rule_assignments (user_id, rule_id, match_type, urgency, status, reason) "
                    "VALUES (:u, :r, 'CONTEXTUAL', :ur, 'ACTIVE', :rs)"
                ), {"u": user_id, "r": rid, "ur": r["urgency"], "rs": r["reason"]})
                assign_count += 1
        db.commit()
        print(f"✅  Regulations: {len(rule_ids)} rules, {assign_count} user assignments.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
