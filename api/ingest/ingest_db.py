"""
ingest_db.py — Ingest courses.jsonl and unidata.jsonl into Postgres.

Usage:
    python -m ingest.ingest_db                          # ingest only
    python -m ingest.ingest_db --reset                  # drop+recreate tables first
    python -m ingest.ingest_db --reset --seed-sis       # + real instructors/sections from JSONL

Run from the api/ directory.
"""

import argparse
import json
import os
import sys
import hashlib
import random
import textwrap
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

# Force unbuffered output so logs show immediately
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from dotenv import load_dotenv

# Load .env BEFORE any database imports so DATABASE_URL is picked up
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from sqlalchemy import text
from sqlalchemy.orm import Session

# ── Project imports ─────────────────────────────────────────────────────────
from database.session import engine, SessionLocal, init_db, reset_db
from database.models import (
    Base,
    Course,
    CourseContent,
    UniversityDocument,
    DocumentChunk,
    # SIS models (used by --seed-demo)
    User,
    Student,
    Instructor,
    AcademicTerm,
    CourseSection,
    Enrollment,
    Assignment,
    UserType,
    TermType,
    SectionStatus,
    EnrollmentStatus,
)

# ── Paths ───────────────────────────────────────────────────────────────────
INGEST_DIR = Path(__file__).parent
COURSES_FILE = INGEST_DIR / "courses.jsonl"
UNIDATA_FILE = INGEST_DIR / "unidata.jsonl"

# ── Chunking config ─────────────────────────────────────────────────────────
MAX_CHUNK_WORDS = 200  # safe for 256-token models


# ============================================================================
# Helpers
# ============================================================================

def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Read a .jsonl file, yielding parsed dicts."""
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                print(f"  ⚠  Skipping {path.name}:{lineno} — {exc}")
    return rows


def _chunk_text(text_content: str, max_words: int = MAX_CHUNK_WORDS) -> List[str]:
    """
    Split text into chunks of roughly `max_words` words,
    splitting at paragraph or sentence boundaries when possible.
    """
    if not text_content or not text_content.strip():
        return []

    paragraphs = [p.strip() for p in text_content.split("\n") if p.strip()]
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for para in paragraphs:
        para_words = len(para.split())
        if current_len + para_words > max_words and current:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(para)
        current_len += para_words

    if current:
        chunks.append("\n".join(current))

    return chunks


def _extract_keywords_from_course(meta: dict) -> str:
    """Build a keyword string for a course from its metadata."""
    parts = []
    if meta.get("course_code"):
        parts.append(meta["course_code"])
    if meta.get("course_name"):
        parts.append(meta["course_name"])
    if meta.get("department"):
        parts.append(meta["department"])
    if meta.get("level_of_course_unit"):
        parts.append(meta["level_of_course_unit"])
    if meta.get("offered_semester"):
        parts.append(meta["offered_semester"])
    if meta.get("language_of_instruction"):
        parts.append(meta["language_of_instruction"])
    return " | ".join(parts)


def _extract_keywords_from_page(row: dict) -> str:
    """Build a keyword string from a university web page."""
    parts = []
    if row.get("title"):
        parts.append(row["title"])
    meta = row.get("metadata", {})
    if meta.get("breadcrumbs"):
        parts.append(" > ".join(meta["breadcrumbs"]))
    if meta.get("source_domain"):
        parts.append(meta["source_domain"])
    return " | ".join(parts)


def _build_course_description(row: dict) -> str:
    """Build a full-text description for a course."""
    meta = row.get("metadata", {})
    parts = [row.get("content", "")]

    if meta.get("learning_outcomes_of_the_course_unit"):
        parts.append(f"Learning outcomes: {meta['learning_outcomes_of_the_course_unit']}")
    if meta.get("mode_of_delivery"):
        parts.append(f"Mode of delivery: {meta['mode_of_delivery']}")
    if meta.get("prerequisites_and_corequisites"):
        parts.append(f"Prerequisites: {meta['prerequisites_and_corequisites']}")
    if meta.get("ects"):
        parts.append(f"ECTS: {meta['ects']}")
    if meta.get("theorypractice_hour"):
        parts.append(f"Hours (theory+practice): {meta['theorypractice_hour']}")
    if meta.get("year_of_study"):
        parts.append(f"Year of study: {meta['year_of_study']}")

    return "\n".join(parts)


# ============================================================================
# Ingest: Courses
# ============================================================================

def ingest_courses(session: Session) -> int:
    """Load courses.jsonl → courses + course_content tables. Returns count."""
    if not COURSES_FILE.exists():
        print(f"  ⚠  {COURSES_FILE} not found — skipping course ingestion.")
        return 0

    rows = _read_jsonl(COURSES_FILE)
    total = len(rows)
    print(f"  📖 Read {total} course records from {COURSES_FILE.name}")

    inserted = 0
    skipped = 0

    for i, row in enumerate(rows, 1):
        if i % 500 == 0 or i == total:
            print(f"    ... processing course {i}/{total}", flush=True)
        meta = row.get("metadata", {})
        code = meta.get("course_code", "").strip()
        name = (meta.get("course_name") or row.get("title", "")).strip()

        if not code or not name:
            skipped += 1
            continue

        # Upsert-like: skip if code already exists
        existing = session.query(Course).filter_by(code=code).first()
        if existing:
            skipped += 1
            continue

        description = _build_course_description(row)
        keywords = _extract_keywords_from_course(meta)

        course = Course(
            code=code,
            name=name,
            description=description[:500] if description else None,
            keywords=keywords,
            # embedding left NULL — backfill later
        )
        session.add(course)
        session.flush()  # get course.id

        # Weekly topics → course_content
        weekly_topics = meta.get("weekly_topics", [])
        for week_num, topic in enumerate(weekly_topics, 1):
            if topic and topic.strip():
                cc = CourseContent(
                    course_id=course.id,
                    week_number=week_num,
                    topic=topic.strip(),
                )
                session.add(cc)

        inserted += 1

    session.commit()
    print(f"  ✅ Courses: {inserted} inserted, {skipped} skipped")
    return inserted


# ============================================================================
# Ingest: University Documents (web pages)
# ============================================================================

def ingest_unidata(session: Session) -> int:
    """Load unidata.jsonl → university_documents + document_chunks. Returns count."""
    if not UNIDATA_FILE.exists():
        print(f"  ⚠  {UNIDATA_FILE} not found — skipping unidata ingestion.")
        return 0

    rows = _read_jsonl(UNIDATA_FILE)
    total = len(rows)
    print(f"  📖 Read {total} document records from {UNIDATA_FILE.name}")

    inserted = 0
    skipped = 0
    total_chunks = 0

    for i, row in enumerate(rows, 1):
        if i % 1000 == 0 or i == total:
            print(f"    ... processing doc {i}/{total} ({total_chunks} chunks so far)", flush=True)
        url = (row.get("url") or "").strip()
        title = (row.get("title") or "").strip()
        content = (row.get("content") or "").strip()

        if not url or not title or not content:
            skipped += 1
            continue

        # Skip duplicates
        existing = session.query(UniversityDocument).filter_by(source_url=url).first()
        if existing:
            skipped += 1
            continue

        keywords = _extract_keywords_from_page(row)

        doc = UniversityDocument(
            source_url=url,
            title=title,
            raw_content=content,
            summary=content[:500] if content else None,
            keywords=keywords,
            # keyword_embedding left NULL — backfill later
        )
        session.add(doc)
        session.flush()

        # Chunk the content
        chunks = _chunk_text(content)
        for idx, chunk_text in enumerate(chunks):
            dc = DocumentChunk(
                document_id=doc.id,
                chunk_index=idx,
                content=chunk_text,
                # embedding left NULL — backfill later
            )
            session.add(dc)
            total_chunks += 1

        inserted += 1

    session.commit()
    print(f"  ✅ Documents: {inserted} inserted, {skipped} skipped ({total_chunks} chunks)")
    return inserted


# ============================================================================
# Seed REAL SIS data from JSONL (instructors, terms, sections)
# ============================================================================

import re as _re


def _hash_password(plain: str) -> str:
    """Simple hash — NOT for production."""
    return hashlib.sha256(plain.encode()).hexdigest()


def _parse_lecturers(raw: str) -> List[tuple]:
    """Parse 'Name, Title (Semester) Name2, Title2 (Semester)' into [(name, title), ...]"""
    results = []
    parts = _re.split(r'\)\s*', raw)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        match = _re.match(r'^(.+?),\s*(.+?)(?:\s*\(.*)?$', part)
        if match:
            name = match.group(1).strip()
            title = match.group(2).strip().rstrip('(').strip()
            if name.lower() not in ('instr staff', 'staff', ''):
                results.append((name, title))
    return results


def _semester_to_term_type(offered: str) -> List[str]:
    """Map offered_semester string to list of term types."""
    offered_lower = offered.lower()
    types = []
    if 'fall' in offered_lower or 'güz' in offered_lower:
        types.append('fall')
    if 'spring' in offered_lower or 'bahar' in offered_lower:
        types.append('spring')
    if 'summer' in offered_lower or 'yaz' in offered_lower:
        types.append('summer')
    return types or ['fall']


def seed_sis_data(session: Session):
    """
    Extract REAL instructors, academic terms, and course sections
    from courses.jsonl metadata.
    """
    if not COURSES_FILE.exists():
        print("  ⚠  courses.jsonl not found — cannot seed SIS data.")
        return

    rows = _read_jsonl(COURSES_FILE)
    print(f"  📖 Parsing {len(rows)} course records for SIS data ...")

    # ── 1) Academic Terms ───────────────────────────────────────────────
    terms_data = [
        ("2025-FALL",   TermType.FALL,   2025, date(2025, 9, 15), date(2026, 1, 15), True),
        ("2025-SPRING", TermType.SPRING, 2025, date(2026, 2, 10), date(2026, 6, 15), False),
        ("2025-SUMMER", TermType.SUMMER, 2025, date(2026, 7,  1), date(2026, 8, 31), False),
    ]
    term_map = {}  # 'fall' -> AcademicTerm object
    for code, ttype, year, start, end, active in terms_data:
        t = AcademicTerm(
            code=code, term_type=ttype, year=year,
            start_date=start, end_date=end, is_active=active,
        )
        session.add(t)
        term_map[ttype.value] = t
    session.flush()
    print(f"  ✅ {len(terms_data)} academic terms created")

    # ── 2) Parse unique instructors from JSONL ──────────────────────────
    # { "Full Name": "title" }
    instructor_dict: Dict[str, str] = {}
    # { course_code: [(instructor_name, semester_types)] }
    course_instructor_map: Dict[str, List[tuple]] = {}

    for row in rows:
        meta = row.get("metadata", {})
        code = (meta.get("course_code") or "").strip()
        raw_lecturers = meta.get("name_of_lecturers") or meta.get("retim_elemanlar") or ""
        offered = meta.get("offered_semester") or meta.get("verildii_dnem") or "Fall"

        if not raw_lecturers.strip() or not code:
            continue

        parsed = _parse_lecturers(raw_lecturers)
        sem_types = _semester_to_term_type(offered)

        for name, title in parsed:
            if name not in instructor_dict or (not instructor_dict[name] and title):
                instructor_dict[name] = title
            if code not in course_instructor_map:
                course_instructor_map[code] = []
            course_instructor_map[code].append((name, sem_types))

    print(f"  📐 Found {len(instructor_dict)} unique instructors in data")

    # ── 3) Create Instructor users + records ────────────────────────────
    instructor_db: Dict[str, Instructor] = {}  # name -> Instructor object
    for i, (name, title) in enumerate(sorted(instructor_dict.items()), 1):
        parts = name.split()
        first_name = parts[0] if parts else name
        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

        # Build a unique email
        email_base = _re.sub(r'[^a-z0-9]', '', name.lower())
        email = f"{email_base}@bilgi.edu.tr"

        user = User(
            email=email,
            password_hash=_hash_password("instructor1234"),
            first_name=first_name,
            last_name=last_name,
            user_type=UserType.INSTRUCTOR,
        )
        session.add(user)
        session.flush()

        inst = Instructor(
            user_id=user.id,
            employee_id=f"EMP{i:05d}",
            title=title or "Lecturer",
        )
        session.add(inst)
        instructor_db[name] = inst

        if i % 200 == 0:
            print(f"    ... created {i}/{len(instructor_dict)} instructors")

    session.flush()
    print(f"  ✅ {len(instructor_db)} instructors created")

    # ── 4) Create Sections (link courses ↔ instructors ↔ terms) ────────
    courses_in_db = {c.code: c for c in session.query(Course).all()}
    section_count = 0
    seen_crns = set()

    for code, instructor_entries in course_instructor_map.items():
        course = courses_in_db.get(code)
        if not course:
            continue

        # Deduplicate: one section per (instructor, term)
        seen_pairs = set()
        for instructor_name, sem_types in instructor_entries:
            inst = instructor_db.get(instructor_name)
            if not inst:
                continue

            for sem in sem_types:
                pair = (instructor_name, sem)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)

                term = term_map.get(sem, term_map['fall'])
                crn = f"{term.code}-{code}-{inst.employee_id}"
                if crn in seen_crns:
                    continue
                seen_crns.add(crn)

                sec_num = str(len([p for p in seen_pairs if p[1] == sem]))
                sec = CourseSection(
                    course_id=course.id,
                    term_id=term.id,
                    instructor_id=inst.id,
                    section_number=f"S{sec_num}",
                    crn=crn,
                    max_enrollment=40,
                    current_enrollment=0,
                    status=SectionStatus.ACTIVE if term.is_active else SectionStatus.SCHEDULED,
                )
                session.add(sec)
                section_count += 1

        if section_count % 500 == 0 and section_count > 0:
            session.flush()

    session.commit()
    print(f"  ✅ {section_count} course sections created")

    # ── Summary ─────────────────────────────────────────────────────────
    print(
        f"\n  ✅ SIS data seeded from real JSONL data:\n"
        f"     {len(terms_data)} academic terms\n"
        f"     {len(instructor_db)} instructors (real names from ECTS)\n"
        f"     {section_count} course sections"
    )


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Ingest JSONL data into PostgreSQL")
    parser.add_argument("--reset", action="store_true", help="Drop & recreate all tables before ingesting")
    parser.add_argument("--seed-sis", action="store_true", help="Seed real instructors, terms & sections from JSONL")
    args = parser.parse_args()

    print("=" * 60)
    print("  UniChatBot — Data Ingestion")
    print("=" * 60)

    # ── DB setup ────────────────────────────────────────────────────────
    if args.reset:
        print("\n🔄 Resetting database ...")
        reset_db()
        init_db()
    else:
        init_db()

    session = SessionLocal()

    try:
        # ── Ingest course data ──────────────────────────────────────────
        print("\n📥 Ingesting courses ...")
        n_courses = ingest_courses(session)

        # ── Ingest university documents ─────────────────────────────────
        print("\n📥 Ingesting university documents ...")
        n_docs = ingest_unidata(session)

        # ── Seed real SIS data from JSONL ───────────────────────────────
        if args.seed_sis:
            print("\n📥 Seeding SIS data from JSONL (real instructors & sections) ...")
            seed_sis_data(session)

        # ── Summary ─────────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("  Summary")
        print("=" * 60)
        print(f"  Courses ingested:    {n_courses}")
        print(f"  Documents ingested:  {n_docs}")
        total_chunks = session.query(DocumentChunk).count()
        print(f"  Total chunks:        {total_chunks}")
        total_weekly = session.query(CourseContent).count()
        print(f"  Total weekly topics: {total_weekly}")
        if args.seed_sis:
            n_inst = session.query(Instructor).count()
            n_sect = session.query(CourseSection).count()
            n_terms = session.query(AcademicTerm).count()
            print(f"  Instructors:         {n_inst}")
            print(f"  Course sections:     {n_sect}")
            print(f"  Academic terms:      {n_terms}")
        print("=" * 60)
        print("✅ Ingestion complete!")
        print(
            "\n💡 Next: backfill embeddings with:\n"
            "   python -m ingest.embed_backfill --only all --batch-size 32"
        )

    except Exception as exc:
        session.rollback()
        print(f"\n❌ Error during ingestion: {exc}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
