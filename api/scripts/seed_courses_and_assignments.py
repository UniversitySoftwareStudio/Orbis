"""
Demo seeder — creates a realistic CS/Eng course catalog and, after sections
exist, a few assignments per section. Run AFTER seed_students and BEFORE
seed_sections_and_schedules for courses; assignments are created at the end
against existing sections.

Run: python scripts/seed_courses_and_assignments.py
"""
import os
import sys
import random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from sqlalchemy import text
from database.session import SessionLocal

COURSES = [
    ("COMP 101", "Introduction to Programming", "Fundamentals of programming using Python: variables, control flow, functions, and basic data structures."),
    ("COMP 102", "Object-Oriented Programming", "Classes, inheritance, polymorphism and design principles in Java."),
    ("COMP 201", "Data Structures and Algorithms", "Lists, trees, graphs, hashing, sorting and algorithmic complexity analysis."),
    ("COMP 204", "Database Systems", "Relational model, SQL, normalization, transactions and indexing."),
    ("COMP 301", "Operating Systems", "Processes, threads, scheduling, memory management and file systems."),
    ("COMP 305", "Computer Networks", "Layered architectures, TCP/IP, routing, and application protocols."),
    ("COMP 310", "Web Application Development", "Modern full-stack development with React, REST APIs and authentication."),
    ("COMP 320", "Machine Learning", "Supervised and unsupervised learning, model evaluation and neural networks."),
    ("MATH 101", "Calculus I", "Limits, derivatives, integrals and applications."),
    ("MATH 211", "Linear Algebra", "Vector spaces, matrices, eigenvalues and linear transformations."),
    ("MATH 220", "Probability and Statistics", "Random variables, distributions, estimation and hypothesis testing."),
    ("ENG 101", "Academic English I", "Academic reading, writing and presentation skills."),
]

ASSIGNMENT_TITLES = [
    ("Homework 1: {c} Fundamentals", "Complete the exercises covering the core concepts introduced in the first weeks."),
    ("Project: {c} Mini-System", "Design and implement a small system applying the techniques from this course."),
    ("Lab Report: {c}", "Document your experiment, methodology, results and conclusions."),
]


def run():
    db = SessionLocal()
    try:
        # --- Courses ---
        created = 0
        for code, name, desc in COURSES:
            exists = db.execute(text("SELECT 1 FROM courses WHERE code = :c"), {"c": code}).fetchone()
            if exists:
                continue
            db.execute(
                text("INSERT INTO courses (code, name, description) VALUES (:code, :name, :desc)"),
                {"code": code, "name": name, "desc": desc},
            )
            created += 1
        db.commit()
        print(f"✅  Courses: created {created} (total catalog: {len(COURSES)}).")
    finally:
        db.close()


def seed_assignments():
    db = SessionLocal()
    try:
        sections = db.execute(text(
            "SELECT cs.id, c.name FROM course_sections cs "
            "JOIN courses c ON c.id = cs.course_id WHERE cs.section_type = 'LECTURE'"
        )).fetchall()
        if not sections:
            print("⚠️  No lecture sections found — run seed_sections_and_schedules first.")
            return
        now = datetime.utcnow()
        total = 0
        for section_id, course_name in sections:
            n = random.randint(1, 3)
            for i in range(n):
                tmpl_title, tmpl_desc = ASSIGNMENT_TITLES[i % len(ASSIGNMENT_TITLES)]
                due = now + timedelta(days=random.randint(3, 45))
                db.execute(text(
                    "INSERT INTO assignments (section_id, title, description, due_date, max_points, is_published) "
                    "VALUES (:sid, :title, :desc, :due, :pts, true)"
                ), {
                    "sid": section_id,
                    "title": tmpl_title.format(c=course_name),
                    "desc": tmpl_desc,
                    "due": due,
                    "pts": random.choice([50, 100, 100, 100]),
                })
                total += 1
        db.commit()
        print(f"✅  Assignments: created {total} across {len(sections)} sections.")
    finally:
        db.close()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "courses"
    if mode == "assignments":
        seed_assignments()
    else:
        run()
