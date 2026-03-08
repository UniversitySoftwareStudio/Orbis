# Orbis — Global Project Instructions

## Project Summary

Orbis is a RAG-based academic assistant for Istanbul Bilgi University, built by two undergraduate students.
Users (students and staff) query course data, university regulations, handbooks, and announcements
in natural language across two languages: Turkish and English.

The system has two major components in active development:
1. **RAG Chatbot** — the core feature, largely complete
2. **SIS (Student Information System)** — a relational backend for students, courses, instructors, enrollments. Partially built, subject to significant refactoring

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+, FastAPI, SQLAlchemy 2.0 |
| Database | PostgreSQL 16 with `pgvector` extension |
| Embeddings | HuggingFace TEI server (primary) or Ollama (alternative) — model: `paraphrase-multilingual-MiniLM-L12-v2` (384-dim) or `all-MiniLM-L6-v2` (384-dim) |
| Reranker | Jina AI (`jina-reranker-v2-base-multilingual`) via external API |
| LLM | Groq (`llama-3.3-70b-versatile`) or Gemini (`gemini-1.5-flash`) — switchable via `LLM_PROVIDER` env var |
| Frontend | React 19 + TypeScript + Vite (NOT Angular — the developers know Angular but this project uses React) |
| Auth | JWT stored in httpOnly cookies |

---

## Repository Structure

```
orbis/
├── CLAUDE.md                        # AI context index (read this first)
├── docker-compose.yml               # NOT IN USE — ignore this file
├── api/
│   ├── main.py                      # FastAPI app entry point
│   ├── dependencies.py              # Auth dependencies (JWT cookie validation)
│   ├── requirements.txt
│   ├── .env.example                 # Reference for required env vars
│   ├── database/
│   │   ├── models.py                # ALL SQLAlchemy models (single source of truth)
│   │   ├── session.py               # DB engine, SessionLocal, get_db()
│   │   └── repositories/            # Data access layer
│   ├── routes/                      # FastAPI routers
│   ├── services/                    # Business logic and AI
│   │   ├── rag_service.py           # PRODUCTION RAG pipeline
│   │   ├── regulation_service.py    # LEGACY — used only by experiments, not production
│   │   ├── embedding_service.py     # Embedding provider abstraction (TEI / Ollama)
│   │   ├── llm_service.py           # LLM provider abstraction (Groq / Gemini)
│   │   └── reranker_service.py      # Jina AI reranker
│   ├── schemas/                     # Pydantic request/response schemas
│   ├── scripts/                     # ACTIVE: data processing scripts (see below)
│   ├── ingest/                      # LEGACY — old ingestion pipeline, kept but not in use
│   ├── experiments/                 # LEGACY — old RAG experiments, kept but not in use
│   └── data/                        # JSONL data files (gitignored except *_example.jsonl)
└── web/
    └── src/
        ├── App.tsx                  # Entire frontend UI (single component for now)
        ├── services/api.ts          # HTTP + SSE streaming calls to backend
        └── index.css
```

---

## Conventions

### Python (Backend)
- SQLAlchemy 2.0 style: use `select()` statements, not `session.query()` — exception: vector distance queries still use legacy `.query()` because pgvector's SQLAlchemy 2.0 integration for ordering by distance is limited
- Repository pattern for all DB access — routes call services, services call repositories
- Repositories take `Session` as a parameter (dependency injected via FastAPI `Depends`)
- Pydantic models live in `schemas/`, SQLAlchemy models live in `database/models.py`
- Environment config via `python-dotenv`, always loaded in `main.py` before other imports

### Naming
- Database columns: `snake_case`
- Python classes: `PascalCase`
- Python methods/variables: `snake_case`
- The `KnowledgeBase.metadata` column is aliased as `metadata_` in SQLAlchemy because SQLAlchemy uses `metadata` internally — always access it as `doc.metadata_` in Python, but the actual DB column is named `metadata`

### Environment Variables
- Never hardcode credentials — always use `os.getenv()`
- See `.env.example` for the full list of required variables
- `LLM_PROVIDER` switches between `groq` and `gemini`
- `EMBEDDING_PROVIDER` switches between `tei`, `ollama`, and `local`

---

## Known Bugs and Incomplete Things

These are real issues in the current codebase. Do not silently work around them — flag them.

1. **`UserRepository.resolve_user_role()` does not exist** — it is tested in `api/tests/test_repository_features.py` but the method is missing from `api/database/repositories/user_repository.py`. Tests for it will fail.

2. **Duplicate logout route** — `main.py` registers both `auth_router` (which includes a logout endpoint) and a separate `logout_router`. This causes a route conflict.

3. **Frontend cookie sentinel** — `App.tsx` stores the string `'cookie'` in localStorage as a workaround to indicate an authenticated session when using httpOnly cookies. This is intentional for now but is a known hack.

4. **`docker-compose.yml` is not part of the active setup** — TEI and Ollama are run separately outside Docker. The compose file may be removed in the future.

5. **`api/experiments/` and `api/ingest/` are entirely legacy** — these folders belong to an earlier RAG prototype, kept only at a contributor's request. They may not function correctly against the current codebase. Do not reference or modify them. The active data pipeline is in `api/scripts/`.

6. **SIS repositories are partially complete** — several repositories have methods that are scaffolded but not yet connected to routes. See `sis.instructions.md` for details.

---

## What NOT To Do

- **Do not add session history to the RAG chat** — the system is intentionally stateless. Adding history causes context bloat and 413 token overflow errors. This was a deliberate architectural decision.
- **Do not replace the two-stage rerank with a single rerank** — the pre-expansion rerank and the final rerank serve different purposes. See `rag-pipeline.instructions.md`.
- **Do not use SQL search for generic topic queries** — SQL is only for exact course code lookups. Vector search handles everything else. The router enforces this.
- **Do not use `session.query()` style in new code** — use SQLAlchemy 2.0 `select()` style.
- **Do not add new columns to `knowledge_base` without regenerating `search_vector`** — the `search_vector` column is a `GENERATED ALWAYS AS` computed column. Schema changes require a full `ALTER TABLE`.
- **Do not put business logic in routes** — routes call services, services call repositories.
- **Do not use Angular patterns in the frontend** — the frontend is React with hooks.

---

## Running the Project

### Backend
```bash
cd api
uvicorn main:app --reload
# → http://localhost:8000
```

### Frontend
```bash
cd web
npm run dev
# → http://localhost:5173
```

### Data Pipeline (order matters)

The scraping scripts are not in the repo. Assume scraped JSONL files already exist in `api/data/`.

```bash
cd api

# Step 1 (optional): Fix PDF titles and detect languages
python scripts/fix_pdf_language_and_titles.py

# Step 2: Load JSONL data into PostgreSQL (creates knowledge_base rows, embedding = NULL)
python scripts/load_data.py

# Step 3: Generate and backfill embeddings (slow — safe to pause with CTRL+C and resume)
python scripts/embed_database.py
```

The TEI embedding server must be running before Step 3 if `EMBEDDING_PROVIDER=tei`.
Steps 2 and 3 are separate so ingestion can run quickly and embedding can be done incrementally.

---

## Concern-Specific Files

For detailed context on specific parts of the system, read:
- `.github/instructions/rag-pipeline.instructions.md` — RAG pipeline decisions
- `.github/instructions/data-pipeline.instructions.md` — Data sources and ingestion
- `.github/instructions/sis.instructions.md` — SIS models and repositories
- `.github/instructions/frontend.instructions.md` — React frontend