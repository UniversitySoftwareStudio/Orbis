# SIS (Student Information System) — Instructions

Applies to: `api/database/models.py` (SIS models), `api/database/repositories/` (non-RAG repos), `api/routes/sis.py`, `api/schemas/sis.py`

> ⚠️ **The SIS is under active development and will undergo significant refactoring.**
> Do not treat the current structure as a stable reference architecture.
> When in doubt about a SIS-related design decision, ask before implementing.

---

## Current State

The SIS backend provides a relational data layer for:
- Users (Students, Instructors, Admins)
- Courses and their weekly content
- Academic Terms
- Course Sections (a course offered in a specific term by a specific instructor)
- Enrollments (student ↔ section registration)
- Assignments
- **Section Schedules** (weekly time slots for course sections)
- **Academic Calendar** (university-wide calendar entries: holidays, exam periods, registration windows)

It has **models, repositories, routes, schemas, seed scripts, and SQL migrations**.
Two SIS routes are currently exposed via `/api/sis/`.
The SIS is also integrated into the RAG pipeline via `rag/context_injectors.py`.

---

## Models (in `database/models.py`)

All models share the same `Base` from `DeclarativeBase`. Key relationships:

```
User (1) ──── (1) Student ──── (N) Enrollment ──── (N) CourseSection
                                                          │
User (1) ──── (1) Instructor ──────────────────────── (N) CourseSection
                                                          │
                                      Course ────────── (N) CourseSection
                                        │                  │
                                 CoursePrerequisites       ├── SectionSchedule (N) ← weekly time slots
                                        │                  │
                                 CourseContent             ├── parent_section ← self-ref for lab/lecture hierarchy
                                        │                  │
                                 AcademicTerm ──────── (N) CourseSection
                                                              │
                                                       Assignment (N)

AcademicCalendarEntry (standalone — no FK relationships)
EmbeddingModel (1) ──── (N) KnowledgeBaseEmbedding ──── (1) KnowledgeBase
```

### New Models (added in this branch)

**`SectionSchedule`** — Weekly time slots for course sections:
- `section_id` (FK to `course_sections`), `day_of_week` (MON-FRI), `start_time`, `end_time`, `location`, `is_online`
- Back-references `CourseSection.schedules` with cascade delete

**`AcademicCalendarEntry`** — University-wide calendar events:
- `title_tr`, `title_en`, `start_date`, `end_date` (nullable for single-day events)
- `entry_type` — constrained to: `holiday`, `exam_period`, `registration`, `add_drop`, `section_change`, `withdrawal_deadline`, `semester_start`, `semester_end`, `makeup_exam`, `graduation`, `orientation`, `grade_announcement`, `freeze_period`, `summer_school`, `other`
- `applies_to` — constrained to: `undergraduate`, `graduate`, `prep`, `all`
- `academic_year`, `notes`

**`EmbeddingModel` / `KnowledgeBaseEmbedding`** — Scaffolded for future versioned embedding support. These models have no migration, no repository, and no usage yet.

### New Columns on `CourseSection`

- `section_type` (VARCHAR(10), default `LECTURE`, constrained to `LECTURE`/`LAB`)
- `parent_section_id` (FK to self, for lab-lecture hierarchy, with cascade delete)
- `instructor_name` (VARCHAR(200), for cases where the instructor is not a registered system user)

### Enums
- `UserType`: STUDENT, INSTRUCTOR, ADMIN
- `EnrollmentStatus`: ENROLLED, DROPPED, COMPLETED
- `SectionStatus`: SCHEDULED, ACTIVE, COMPLETED, CANCELLED
- `TermType`: FALL, SPRING, SUMMER

All enum columns use `validate_strings=True` to reject invalid string inputs at the SQLAlchemy level.

---

## Repository Pattern

Each entity has a repository in `api/database/repositories/`.
Most extend `BaseRepository` which provides generic CRUD (`create`, `get_by_id`, `get_all`, `update`, `delete`, `count`, `filter_by`, `get_one_by`).

`CourseRepository` is an exception — it does not extend `BaseRepository` and takes `db: Session`
as a parameter on each method rather than in `__init__`. This is a legacy pattern that predates
the standardized repository structure and may be refactored.

### New Repositories

**`AcademicCalendarRepository`** — extends `BaseRepository[AcademicCalendarEntry]`:
- `get_by_year(academic_year)` — all entries for a given year, ordered by `start_date`
- `get_by_year_and_applies_to(academic_year, applies_to)` — filtered by both year and audience
- `get_active_year_entries()` — entries for the latest academic year
- `format_for_rag(entries)` — formats entries into structured text with Turkish headers, split by Fall (GÜZ YARIYILI) and Spring (BAHAR YARIYILI) semesters

**`SectionScheduleRepository`** — extends `BaseRepository[SectionSchedule]`:
- `get_by_section_id(section_id)` — schedule rows for a section
- `get_student_schedule(student_id)` — raw SQL joining enrollments, sections, courses, and schedules to get a student's full weekly timetable (only `ENROLLED` status)
- `format_for_rag(schedule_rows)` — formats into structured text with Turkish day names, pipe-separated fields

---

## API Routes (`api/routes/sis.py`)

Two endpoints under `/api/sis/`:

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/sis/calendar` | GET | Required | Returns academic calendar entries. Query params: `academic_year` (default `2025-2026`), `applies_to` (default `undergraduate`) |
| `/api/sis/schedule/me` | GET | Required | Returns the current student's weekly schedule. Non-student accounts get `{"slots": [], "message": "Not a student account"}` |

### Response Schemas (`api/schemas/sis.py`)

- `CalendarEntryResponse` — `id`, `title_tr`, `title_en`, `start_date`, `end_date`, `entry_type`, `applies_to`, `academic_year`, `notes`
- `ScheduleSlotResponse` — `course_code`, `course_name`, `section_number`, `section_type`, `instructor_name`, `day_of_week`, `start_time`, `end_time`, `location`, `is_online`

---

## SIS–RAG Integration

The SIS is now integrated into the RAG pipeline. This is handled by `api/rag/context_injectors.py`.

The router agent recognizes two SIS-specific tools:
- `calendar` — triggers when the user asks about academic dates/deadlines/holidays
- `student_schedule` — triggers when the user asks about their own personal schedule

**How it works:**
1. After routing, `build_sis_context()` separates SIS intents from RAG intents
2. For `calendar`: fetches entries from `academic_calendar_entries` via `AcademicCalendarRepository.get_active_year_entries()` and formats them as a `=== AKADEMİK TAKVİM ===` block
3. For `student_schedule`: resolves the student ID, fetches their enrolled courses' schedules via `SectionScheduleRepository.get_student_schedule()`, and formats as a `=== ÖĞRENCİ HAFTALIK PROGRAMI ===` block
4. The SIS context is prepended to the RAG document context
5. Both fetchers are wrapped in try/except to prevent SIS failures from crashing the RAG pipeline
6. The remaining non-SIS intents continue through the normal retrieval pipeline

---

## SQL Migrations

Located in `api/scripts/migrations/`:
- `001_academic_calendar.sql` — creates `academic_calendar_entries` table with CHECK constraints and indexes
- `002_section_schedule.sql` — alters `course_sections` (adds `section_type`, `parent_section_id`, `instructor_name`), creates `section_schedules` table

---

## Seed Scripts

Located in `api/scripts/`:

| Script | Purpose |
|--------|---------|
| `seed_academic_calendar.py` | Seeds 49 calendar entries for 2025-2026 (undergraduate). Idempotent — deletes and reinserts. |
| `seed_students.py` | Creates 150 demo student accounts (80% Turkish names, 20% international). Password: `demo1234` |
| `seed_sections_and_schedules.py` | Generates demo course sections (1-2 lectures, optional labs) with schedule slots for all courses |
| `seed_enrollments.py` | Assigns each student 4-8 random lecture sections, auto-enrolls in lab sections. Idempotent. |

Run order: `seed_students.py` → `seed_sections_and_schedules.py` → `seed_enrollments.py` → `seed_academic_calendar.py`

---

## Auth System

JWT authentication uses httpOnly cookies (not Authorization headers).

- Tokens are set on login/register via `response.set_cookie(key="access_token", ...)`
- `dependencies.py` reads the cookie via `request.cookies.get("access_token")`
- `AuthService` handles hashing (bcrypt_sha256 with bcrypt fallback), JWT encode/decode
- Passwords over 72 bytes are truncated before hashing — this is a known bcrypt limitation workaround
- `ACCESS_TOKEN_EXPIRE_MINUTES` defaults to 30 (configurable via env var)

### Role-based access
- `require_admin` — ADMIN only
- `require_instructor` — INSTRUCTOR or ADMIN
- `require_student` — any authenticated user
- `require_user_types([UserType.X, UserType.Y])` — factory for custom combinations

---

## Email Generation Convention

On registration, emails are auto-generated from first name initial + last name:
- Students: `{first_initial}.{last_name}@bilgiedu.net`
- Instructors/Admins: `{first_initial}.{last_name}@bilgi.edu.tr`

Example: John Doe (student) → `j.doe@bilgiedu.net`

---

## Known Incomplete / Missing Things

1. **`EmbeddingModel` / `KnowledgeBaseEmbedding` models** — defined in `models.py` but have no migration, no repository, and no usage. Scaffolded for future versioned embedding support.

2. **`CourseRepository` uses legacy `.query()` style** — intentionally, because pgvector's
   `cosine_distance` ordering with SQLAlchemy 2.0 `select()` requires workarounds. Do not
   "fix" this without testing that vector search still works.

3. **The `KnowledgeBase` model and the `Course`/`UniversityDocument` models co-exist** —
   `KnowledgeBase` is the production RAG table (one unified table for all content types).
   `Course` and `UniversityDocument`/`DocumentChunk` are older models from an earlier architecture
   that the experiments still reference. They may be deprecated or removed in future refactoring.
