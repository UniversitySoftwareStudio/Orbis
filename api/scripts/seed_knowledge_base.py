"""
Demo seeder — populates knowledge_base with realistic Istanbul Bilgi University
regulation/procedure documents so the RAG chat can retrieve and CITE real
sources (with URLs) via full-text keyword search (no embedding stack needed).

Run: python scripts/seed_knowledge_base.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from sqlalchemy import text
from database.session import SessionLocal

DOCS = [
    {
        "url": "https://www.bilgi.edu.tr/en/student-life/erasmus-exchange/",
        "title": "Erasmus+ Student Exchange — Application Guide",
        "category": "international", "type": "regulation", "language": "en",
        "content": (
            "Erasmus+ student exchange applications open twice a year, announced by the "
            "International Relations Office. To apply you must be a registered full-time "
            "student with a cumulative GPA of at least 2.20 (undergraduate) or 2.50 "
            "(graduate). Applications are submitted online through the Erasmus portal during "
            "the announced window. Selection is based on academic achievement (50%) and a "
            "foreign language exam score (50%). Selected students sign a Learning Agreement "
            "with their department coordinator before the mobility period. Contact: "
            "International Relations Office, erasmus@bilgi.edu.tr."
        ),
    },
    {
        "url": "https://www.bilgi.edu.tr/en/academic/regulations/add-drop/",
        "title": "Course Registration and Add/Drop Period",
        "category": "registration", "type": "regulation", "language": "en",
        "content": (
            "Course registration takes place at the beginning of each semester according to "
            "the academic calendar. The add/drop period runs during the first two weeks of "
            "classes. During add/drop, students may add new courses, drop existing ones, or "
            "change sections, subject to capacity and advisor approval. Courses dropped during "
            "the add/drop period do not appear on the transcript. After the add/drop deadline, "
            "withdrawing from a course results in a 'W' grade. Students on academic probation "
            "must meet their advisor before completing registration."
        ),
    },
    {
        "url": "https://www.bilgi.edu.tr/en/academic/regulations/internship/",
        "title": "Mandatory Internship Directive — Faculty of Engineering",
        "category": "internship", "type": "regulation", "language": "en",
        "content": (
            "Undergraduate engineering students must complete a mandatory summer internship of "
            "at least 20 working days before graduation. The internship must be approved in "
            "advance by the department internship committee. After completion, students submit "
            "an internship report and an employer evaluation form through the SIS within the "
            "first three weeks of the following semester. Internships may be completed after "
            "the student has earned at least 60 ECTS credits. Graduation is blocked until the "
            "internship requirement is fulfilled and the report is accepted."
        ),
    },
    {
        "url": "https://www.bilgi.edu.tr/en/academic/regulations/graduation/",
        "title": "Graduation Requirements and Honors",
        "category": "graduation", "type": "regulation", "language": "en",
        "content": (
            "To graduate, a student must complete all required courses in the curriculum, earn "
            "the minimum required ECTS credits, fulfill the mandatory internship, and reach a "
            "cumulative GPA of at least 2.00. Students who graduate with a CGPA between 3.00 "
            "and 3.49 graduate with Honor; those with a CGPA of 3.50 or above graduate with "
            "High Honor. Graduation applications are processed automatically by the Registrar "
            "once all requirements are met at the end of the final semester."
        ),
    },
    {
        "url": "https://www.bilgi.edu.tr/en/academic/regulations/double-major/",
        "title": "Double Major and Minor Program Regulations",
        "category": "programs", "type": "regulation", "language": "en",
        "content": (
            "Students may apply to a Double Major (ÇAP) or Minor program after completing at "
            "least two semesters. Double Major applicants must have a cumulative GPA of at "
            "least 3.00 and rank in the top 20% of their class, with no failing grades. Minor "
            "applicants need a CGPA of at least 2.50. Applications are submitted online during "
            "the announced window at the start of the Fall semester. Late applications are not "
            "accepted. Approved students follow both curricula and receive a separate diploma "
            "for the completed double major."
        ),
    },
    {
        "url": "https://www.bilgi.edu.tr/en/academic/regulations/grading/",
        "title": "Grading System and GPA Calculation",
        "category": "academic", "type": "regulation", "language": "en",
        "content": (
            "Istanbul Bilgi University uses a letter grading system: AA (4.00), BA (3.50), BB "
            "(3.00), CB (2.50), CC (2.00), DC (1.50), DD (1.00), FD (0.50), FF (0.00). The "
            "grade point average (GPA) is the credit-weighted average of grade points. A "
            "minimum CC is generally required to pass a course. Students whose cumulative GPA "
            "falls below 2.00 are placed on academic probation and may have their course load "
            "restricted until their GPA recovers."
        ),
    },
    {
        "url": "https://www.bilgi.edu.tr/en/academic/calendar/",
        "title": "Academic Calendar 2025-2026",
        "category": "calendar", "type": "calendar", "language": "en",
        "content": (
            "The 2025-2026 academic year consists of the Fall and Spring semesters. Fall "
            "semester classes begin in mid-September; the add/drop period is the first two "
            "weeks. Midterm exams are held in late October to November, and final exams in "
            "January. The Spring semester begins in February with its own add/drop period, "
            "midterms in March-April, and finals in May-June. Registration dates, holidays, "
            "and exam periods are published in the official academic calendar."
        ),
    },
    {
        "url": "https://www.bilgi.edu.tr/en/academic/regulations/attendance/",
        "title": "Attendance and Examination Regulations",
        "category": "academic", "type": "regulation", "language": "en",
        "content": (
            "Students are expected to attend at least 70% of lectures and 80% of laboratory or "
            "applied sessions. Instructors may bar students who fail to meet attendance "
            "requirements from the final exam. A make-up exam may be granted only with a valid, "
            "documented excuse submitted to the faculty within five working days. The final "
            "course grade combines midterm, assignment, and final exam components as stated in "
            "the course syllabus."
        ),
    },
    {
        "url": "https://www.bilgi.edu.tr/en/student-life/scholarships/",
        "title": "Scholarships and Financial Aid",
        "category": "financial", "type": "regulation", "language": "en",
        "content": (
            "Istanbul Bilgi University offers merit-based and need-based scholarships. "
            "Merit scholarships are awarded based on the university entrance exam ranking and "
            "are renewed each year provided the student maintains the required CGPA and passes "
            "their courses on time. Students who fail to meet the academic conditions may have "
            "their scholarship reduced or suspended. Financial aid applications are evaluated "
            "by the Scholarship and Financial Aid Office each academic year."
        ),
    },
    {
        "url": "https://www.bilgi.edu.tr/en/academic/regulations/transfer/",
        "title": "Course Transfer and Exemption (Muafiyet)",
        "category": "academic", "type": "regulation", "language": "en",
        "content": (
            "Students transferring from another institution or returning from an exchange may "
            "apply for course exemption (muafiyet). Exemption requests are submitted to the "
            "relevant department with official transcripts and course syllabi within the first "
            "two weeks of the semester. The department evaluates content equivalence and ECTS "
            "credits. Approved exempted courses are recorded as transfer credits and counted "
            "toward graduation but are not included in the GPA calculation."
        ),
    },
]


def run():
    db = SessionLocal()
    try:
        created = 0
        for d in DOCS:
            exists = db.execute(text("SELECT 1 FROM knowledge_base WHERE url = :u"), {"u": d["url"]}).fetchone()
            if exists:
                continue
            db.execute(text(
                "INSERT INTO knowledge_base (url, title, content, language, type, category, search_vector) "
                "VALUES (:url, :title, :content, :lang, :type, :cat, "
                "        to_tsvector('simple', coalesce(:title,'') || ' ' || coalesce(:content,'')))"
            ), {
                "url": d["url"], "title": d["title"], "content": d["content"],
                "lang": d["language"], "type": d["type"], "cat": d["category"],
            })
            created += 1
        db.commit()
        print(f"✅  Knowledge base: created {created} documents (total catalog: {len(DOCS)}).")
    finally:
        db.close()


if __name__ == "__main__":
    run()
