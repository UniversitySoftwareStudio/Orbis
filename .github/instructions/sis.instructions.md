# SIS (Student Information System) — Instructions

Applies to: `api/database/models.py` (SIS models), `api/database/repositories/` (non-RAG repos)

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

It currently has **models, repositories, and tests** but very few connected routes.
Most SIS functionality is scaffolded and not yet exposed via the API.

---

## Models (in `database/models.py`)

All models share the same `Base` from `DeclarativeBase`. Key relationships:

```
User (1) ──── (1) Student ──── (N) Enrollment ──── (N) CourseSection
                                                            │
User (1) ──── (1) Instructor ──────────────────────── (N) CourseSection
                                                            │
                                        Course ────────── (N) CourseSection
                                          │
                                   CoursePrerequisites (self-referential M2M)
                                          │
                                   CourseContent (weekly topics)
                                          │
                                   AcademicTerm ──────── (N) CourseSection
                                                                │
                                                         Assignment (N)
```

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

---

## Known Incomplete / Missing Things

1. **`UserRepository.resolve_user_role()`** — now implemented in `user_repository.py`.
   Returns a dict with `role`, `entity_id`, and `user_type` keys. Checks Student first, then Instructor.

2. **No SIS routes beyond auth** — there are no active FastAPI endpoints for enrollment,
   sections, terms, or assignments yet. The repositories exist but are not wired up.

3. **`CourseRepository` uses legacy `.query()` style** — intentionally, because pgvector's
   `cosine_distance` ordering with SQLAlchemy 2.0 `select()` requires workarounds. Do not
   "fix" this without testing that vector search still works.

4. **The `KnowledgeBase` model and the `Course`/`UniversityDocument` models co-exist** —
   `KnowledgeBase` is the production RAG table (one unified table for all content types).
   `Course` and `UniversityDocument`/`DocumentChunk` are older models from an earlier architecture
   that the experiments still reference. They may be deprecated or removed in future refactoring.

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

## Planned SIS–RAG Integration

The roadmap includes connecting SIS relational data into the RAG pipeline via Text-to-SQL.
This would allow queries like "When is my next assignment due?" to be answered by translating
the question into SQL against the SIS tables and then formatting the result.

This integration does not exist yet. When it is built, the router agent will need a new intent
type (e.g., `tool: "sis_sql"`) and the RAG service will need a new execution path.
Do not design around this yet — wait for the integration to be scoped.