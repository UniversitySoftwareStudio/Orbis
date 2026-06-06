# Orbis — Project Context Index

This file is the entry point for AI assistants reading this repo.
Read this file first, then read the specific concern file(s) relevant to what you're working on.

## What Is This Project?

Orbis is a RAG (Retrieval-Augmented Generation) and academic-support system
built for Istanbul Bilgi University. It combines natural-language university
search with SIS-style student pages, regulation assignments, and an agentic
assignment submission reviewer.

It is a student project, built by two undergraduate students.

## File Map

| File | What it covers |
|------|----------------|
| `.github/copilot-instructions.md` | Global: tech stack, repo structure, conventions, known bugs, what NOT to do |
| `.github/instructions/rag-pipeline.instructions.md` | The full RAG pipeline: router (4 tools: vector, sql, calendar, student_schedule), SIS context injection, hybrid search, double-rerank, expansion, context building. **Read this if touching anything in `api/rag/` or `api/database/repositories/rag_repository.py`** |
| `.github/instructions/data-pipeline.instructions.md` | Data sources, JSONL schemas, KnowledgeBase table design, embedding pipeline, language detection, title cleaning. **Read this if touching anything in `api/scripts/` or `api/data/`** |
| `.github/instructions/sis.instructions.md` | SIS models, repositories, routes, schemas, seed scripts, and SIS–RAG integration. **Read this before touching anything in `api/database/`, `api/routes/sis.py`, `api/routes/student.py`, or `api/schemas/sis.py`** |
| `.github/instructions/frontend.instructions.md` | React frontend: current state, auth flow, streaming. **Read this if touching anything in `web/`** |
| `EVENT_SYSTEM.md` (root) + `docs/EVENT_SYSTEM_CONTEXT.md` | The regulation event system and its wired-vs-historical boundary: `/api/events/*` extraction writes `regulatory_events`; `/api/regulations/*` reads precomputed `user_rule_assignments`. **Read this before touching `api/events/`, `api/routes/events.py`, or `api/routes/regulations.py`** |

## Quick orientation

- The production RAG lives in `api/rag/service.py` (with the full pipeline in `api/rag/`) and `api/database/repositories/rag_repository.py`
- The RAG pipeline now includes SIS context injection via `api/rag/context_injectors.py` — the router recognizes `calendar` and `student_schedule` intents alongside `vector` and `sql`
- `api/services/rag_service.py` and `api/services/embedding_service.py` are thin re-export wrappers for backward compatibility
- `regulation_service.py`, `llm_service.py`, and `reranker_service.py` have been removed from `api/services/` — their functionality is now in `api/rag/`, `api/llm/`, and `api/embedding/`
- `docker-compose.yml` at the root defines a TEI load-balanced setup but uses a different embedding model than production — see Known Bugs
- Real data files (`*.jsonl`) are gitignored. `api/data/*_example.jsonl` files show their schemas
- The SIS (Student Information System) backend has models, repositories, routes, and schemas, and is integrated into the RAG pipeline for calendar and schedule queries. Calendar/schedule live under `/api/sis/`; student-facing read endpoints (dashboard, profile, transcript, enrolled courses) live in `api/routes/student.py`
- **SQLAlchemy models now live in a package: `api/database/models/`** (`identity.py`, `academic.py`, `knowledge.py`, `events.py`, `enums.py`, `base.py`). The old monolithic `api/database/models.py` file **still exists but is dead code** — Python imports the package, not the file. Import models from `database.models` (resolves to the package) and edit the package files; do not edit `database/models.py`. See Known Bugs in `copilot-instructions.md`.
- The **regulation event system** (`api/events/`) has an important wired-vs-historical boundary (documented in `EVENT_SYSTEM.md` and the root `README.md`):
  - **Wired now:** `POST /api/events/trigger` runs `EventPipelineOrchestrator` → `SearchAgent` (loads regulation sources from the categorization tree) → `ReasoningAgent.extract` (deterministic regex scan for actionable "must/shall/zorunlu" sentences) → `EventCreator.persist_candidates` (deterministic quality + dedup, with an **optional** LLM `ReasoningReviewer` gated by `EVENTS_ENABLE_REASONING_REVIEW`). This writes `Event` rows to `regulatory_events`, with telemetry in `event_candidate_logs` / `event_agent_logs`. Admin-only; read back via `/api/events/runs/*`.
  - **Historical / report artifacts (NOT wired to a live route):** the `RegulationRule` + `UserRuleAssignment` two-pass LLM extraction and per-user assignment flow (`events/user_agent.py`). There is **no** exposed `/api/events/assign/me`. The web app only *reads* precomputed `user_rule_assignments` via `GET /api/regulations/me` (and updates status via `PATCH /api/regulations/assignments/{id}`). User context for that historical matching came from `user_profiles` (`UserProfile` model).
- The **submission agent** (`api/agents/submission_agent.py`) validates uploaded documents against a ruleset; routes are in `api/routes/assignments.py` (including an SSE streaming variant)
- Full route surface (all under `/api`): `auth` (register, login, me, refresh), `search` (chat, search, ask), `logout`, `sis` (calendar, schedule/me), `student` (dashboard, profile/me, transcript/me, courses/me), `regulations` (me, assignments/{id}), `events` (trigger, runs/{id}, runs/{id}/telemetry, runs/{id}/candidates — admin only), `assignments` (me, submit, submit/stream, submissions/{id}/flag)
