# SIS (Student Information System) — Instructions

Applies to: `api/database/models/` (SIS models — a **package**, not the dead `models.py` file), `api/database/repositories/` (non-RAG repos), `api/routes/sis.py`, `api/routes/student.py`, `api/schemas/sis.py`, `api/schemas/student.py`

> ⚠️ **The SIS is under active development and will undergo significant refactoring.**
> Do not treat the current structure as a stable reference architecture.
> When in doubt about a SIS-related design decision, ask before implementing.

> 🛑 **Models live in the `api/database/models/` package, split by domain** (`identity.py`,
> `academic.py`, `knowledge.py`, `events.py`, `enums.py`, `base.py`). The old monolithic
> `api/database/models.py` *file* still exists but is **dead, shadowed code** — Python imports the
> package. Always import from `database.models` (the package re-exports everything) and edit the
> package files. Never edit `database/models.py`.

---

## Current State

The SIS backend provides a relational data layer for:
- Users (Students, Instructors, Admins) and **UserProfile** (enriched per-user context for any role)
- Courses and their weekly content
- Academic Terms
- Course Sections (a course offered in a specific term by a specific instructor)
- Enrollments (student ↔ section registration)
- Assignments and **AssignmentSubmission** (submission-check records)
- **Section Schedules** (weekly time slots for course sections)
- **Academic Calendar** (university-wide calendar entries: holidays, exam periods, registration windows)

It has **models, repositories, routes, schemas, seed scripts, and SQL migrations**.
The route surface has grown beyond `/api/sis/`:
- `api/routes/sis.py` — `/api/sis/calendar`, `/api/sis/schedule/me`
- `api/routes/student.py` — student-facing read projections: `/api/sis/dashboard`, `/api/sis/profile/me`, `/api/sis/transcript/me`, `/api/sis/courses/me`
- `api/routes/regulations.py` — `/api/regulations/me`, `/api/regulations/assignments/{id}` (reads precomputed rule assignments — see `EVENT_SYSTEM.md`)
- `api/routes/assignments.py` — `/api/assignments/me`, submit (+ streaming), and submission flagging

The SIS is also integrated into the RAG pipeline via `rag/context_injectors.py`.

---

## Models (in `database/models/`)

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

**`UserProfile`** (`database/models/identity.py`) — enriched per-user context for **any** role (student, instructor, admin), one-to-one with `User` (`User.profile`):
- Student fields: `department`, `faculty`, `program_level`, `academic_year`, `semester_number`, `total_credits_completed`, `total_credits_enrolled`
- Instructor/staff fields: `title`, `office`, `responsibilities`
- Status flags: `is_on_probation`, `has_advisor_hold`, `has_financial_hold`, `is_exchange_student`, `is_double_major`, `is_minor`
- `extra_context` (JSONB) — free-form key/value injection point for facts not in structured columns
- Read by the (historical) regulation assignment agent to build a per-user context blob, and projected by `/api/sis/profile/me` and `/api/sis/dashboard`

**`RegulationRule` / `UserRuleAssignment`** (`database/models/events.py`) — the regulation-extraction action objects and per-user assignments. See `EVENT_SYSTEM.md` for how they're populated (historical LLM pipeline) and surfaced (`/api/regulations/me`).

**`AssignmentSubmission`** (`database/models/academic.py`) — records produced by the submission-check agent.

**Event models** (`EventRun`, `EventSourceLog`, `EventSourceCheckpoint`, `Event` → `regulatory_events`, `EventAgentLog`, `EventCandidateLog`) — telemetry + output of the wired `/api/events/trigger` extraction pipeline.

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

**`UserRuleAssignmentRepository`** — extends `BaseRepository[UserRuleAssignment]`:
- `get_for_user(user_id)` — all assignments for a user, with the linked `RegulationRule` eagerly loaded (`joinedload`), sorted by urgency (high → low) then most-recent
- `get_for_user_by_id(user_id, assignment_id)` — single assignment scoped to the user
- `count_active_for_user(user_id)` — count of `ACTIVE` assignments (used by the dashboard)
- `update_status(user_id, assignment_id, new_status)` — flips status; returns `None` if not found/owned

**`AssignmentSubmissionRepository`** — backs the submission-check records written by the submission agent (`api/agents/submission_agent.py`) via `api/routes/assignments.py`.

`EnrollmentRepository`, `StudentRepository`, and `UserRepository` gained methods used by `routes/student.py`: `EnrollmentRepository.get_enrolled_with_details` / `get_student_enrollments`, `StudentRepository.get_transcript` / `calculate_gpa` / `get_by_user_id`, `UserRepository.resolve_user_role` (returns `{role, entity_id}`).

---

## API Routes

### `api/routes/sis.py` — under `/api/sis/`

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/sis/calendar` | GET | Required | Returns academic calendar entries. Query params: `academic_year` (default `2025-2026`), `applies_to` (default `undergraduate`) |
| `/api/sis/schedule/me` | GET | Required | Returns the current student's weekly schedule. Non-student accounts get `{"slots": [], "message": "Not a student account"}` |

### `api/routes/student.py` — student-facing read projections (also under `/api/sis/`)

All endpoints resolve the student from the authenticated user — a client never supplies a `student_id`. Non-student accounts get empty/zeroed payloads rather than errors.

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/sis/dashboard` | GET | Required | Aggregate for the Dashboard page: stats (gpa, credits, enrolled/pending counts, active regulation count), upcoming assignment deadlines, upcoming calendar items |
| `/api/sis/profile/me` | GET | Required | Identity (User + Student) merged with `UserProfile` academic context and status flags |
| `/api/sis/transcript/me` | GET | Required | Completed-course transcript entries + cumulative GPA + total credits |
| `/api/sis/courses/me` | GET | Required | Current enrolled courses, each collapsed into one card with a list of schedule slots |

### `api/routes/regulations.py` — under `/api/regulations/`

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/regulations/me` | GET | Required | Caller's `UserRuleAssignment` rows (joined to `RegulationRule`), sorted by urgency then recency. **Reads precomputed data** — there is no live assignment-trigger route (see `EVENT_SYSTEM.md`) |
| `/api/regulations/assignments/{assignment_id}` | PATCH | Required | Mark one assignment `active` / `actioned` / `dismissed` (status in body) |

### Response Schemas

- `api/schemas/sis.py` — `CalendarEntryResponse`, `ScheduleSlotResponse`
- `api/schemas/student.py` — `ProfileResponse`, `TranscriptResponse`/`TranscriptEntry`, `EnrolledCourseResponse`/`EnrolledCourseSlot`, `DashboardResponse`/`DashboardStats`/`DashboardDeadline`/`DashboardCalendarItem`
- `api/schemas/regulations.py` — `RuleAssignmentResponse`, `RuleAssignmentStatusUpdate`

`ScheduleSlotResponse` fields: `course_code`, `course_name`, `section_number`, `section_type`, `instructor_name`, `day_of_week`, `start_time`, `end_time`, `location`, `is_online`.
`CalendarEntryResponse` fields: `id`, `title_tr`, `title_en`, `start_date`, `end_date`, `entry_type`, `applies_to`, `academic_year`, `notes`.

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
- `003_regulation_rules.sql` — creates the `regulation_rules` table
- `004_regulation_rule_action_fields.sql` — renames `condition`→`trigger` and adds action-object fields to `regulation_rules` (`valid_from`, `valid_until`, `blocking`, `consequence`, …)
- `005_assignment_submission_agent.sql` — alters `assignment_submissions` (adds `evaluation_report` JSONB, `flagged_by_student`, `student_flag_reason`, `flagged_at`)

> Note: not every table has a hand-written migration here — there is no migration in this folder for
> `user_profiles`, `user_rule_assignments`, or the `event_runs`/`regulatory_events`/log tables.
> Verify the live schema before assuming one exists. `init_db()` (SQLAlchemy `create_all`) creates
> all model-defined tables on a fresh DB.

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

0. **`database/models.py` (file) is dead, shadowed code** — the `database/models/` package wins on import. Edit the package, never the file. It should eventually be deleted.

1. **`EmbeddingModel` / `KnowledgeBaseEmbedding` models** — defined in `database/models/knowledge.py` but have no migration, no repository, and no usage. Scaffolded for future versioned embedding support.

2. **`CourseRepository` uses legacy `.query()` style** — intentionally, because pgvector's
   `cosine_distance` ordering with SQLAlchemy 2.0 `select()` requires workarounds. Do not
   "fix" this without testing that vector search still works.

3. **The `KnowledgeBase` model and the `Course`/`UniversityDocument` models co-exist** —
   `KnowledgeBase` is the production RAG table (one unified table for all content types).
   `Course` and `UniversityDocument`/`DocumentChunk` are older models from an earlier architecture
   that the experiments still reference. They may be deprecated or removed in future refactoring.
