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
| LLM | Groq (`llama-3.3-70b-versatile`), Gemini (`gemini-1.5-flash`), or any OpenAI-compatible endpoint — switchable via `LLM_PROVIDER` env var |
| Frontend | React 19 + TypeScript + Vite (NOT Angular — the developers know Angular but this project uses React) |
| Auth | JWT stored in httpOnly cookies |

---

## Repository Structure

```
orbis/
├── CLAUDE.md                        # AI context index (read this first)
├── docker-compose.yml               # TEI load-balanced setup — see note in Known Bugs
├── api/
│   ├── main.py                      # FastAPI app entry point
│   ├── dependencies.py              # Auth dependencies (JWT cookie validation)
│   ├── requirements.txt
│   ├── .env.example                 # Reference for required env vars
│   ├── core/                        # Shared infrastructure (logging)
│   ├── database/
│   │   ├── models.py                # ALL SQLAlchemy models (single source of truth)
│   │   ├── session.py               # DB engine, SessionLocal, get_db()
│   │   └── repositories/            # Data access layer
│   ├── embedding/                   # Embedding provider package (TEI / Ollama / Local)
│   ├── llm/                         # LLM provider package (Groq / Gemini / OpenAI)
│   ├── rag/                         # RAG pipeline package (router, retrieval, rerank, context)
│   ├── rag_service/                 # Optional standalone RAG microservice (port 8010)
│   ├── routes/                      # FastAPI routers
│   ├── services/                    # Thin re-export wrappers for backward compatibility
│   │   ├── rag_service.py           # Re-exports RAGService from rag.pipeline
│   │   ├── embedding_service.py     # Re-exports from embedding.runtime
│   │   └── auth_service.py          # Authentication and JWT logic
│   ├── schemas/                     # Pydantic request/response schemas
│   ├── scripts/                     # ACTIVE: data processing, scraping, and categorization
│   │   ├── experiments/             # LEGACY — old RAG experiments, kept but not in use
│   │   ├── ingest/                  # LEGACY — old ingestion pipeline, kept but not in use
│   │   ├── categorization/          # URL clustering and data categorization
│   │   └── scrape/                  # Web scraping scripts
│   ├── tests/                       # Pytest E2E and stress tests (PostgreSQL-backed)
│   └── data/                        # JSONL data files (gitignored except *_example.jsonl)
├── docs/                            # Project documentation and audits
├── nginx/                           # Nginx config for TEI load balancer
└── web/
    └── src/
        ├── App.tsx                  # Entire frontend UI (single component for now)
        ├── components/              # Placeholder — empty, prepared for future use
        ├── pages/                   # Placeholder — empty, prepared for future use
        ├── types/                   # Placeholder — empty, prepared for future use
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
- `LLM_PROVIDER` switches between `groq`, `gemini`, and `openai`
- `EMBEDDING_PROVIDER` switches between `tei`, `ollama`, and `local`

---

## Known Bugs and Incomplete Things

These are real issues in the current codebase. Do not silently work around them — flag them.

1. **Frontend cookie sentinel** — `App.tsx` stores the string `'cookie'` in localStorage as a workaround to indicate an authenticated session when using httpOnly cookies. This is intentional for now but is a known hack.

2. **`docker-compose.yml` embedding model mismatch** — The compose file now uses `intfloat/multilingual-e5-small` with 3 load-balanced TEI replicas, but the production system uses `paraphrase-multilingual-MiniLM-L12-v2` or `all-MiniLM-L6-v2` (384-dim). If someone deploys via compose, the embeddings will be incompatible with the existing database.

3. **`api/scripts/experiments/` and `api/scripts/ingest/` are entirely legacy** — these folders were moved from `api/experiments/` and `api/ingest/` into `api/scripts/` but still belong to an earlier RAG prototype. They may not function correctly against the current codebase. Do not reference or modify them. The active data pipeline is in `api/scripts/` (top-level scripts only).

4. **SIS repositories are partially complete** — several repositories have methods that are scaffolded but not yet connected to routes. See `sis.instructions.md` for details.

5. **Simplified LLM prompt** — The `ANSWER_PROMPT_TEMPLATE` in `rag/constants.py` has been simplified compared to the original. The detailed citation protocol (bold entities, Markdown links on document titles, administrative safety rules) has been reduced to briefer instructions. This may affect citation quality.

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

Scraping scripts are now in `api/scripts/scrape/`. Scraped JSONL files should be placed in `api/data/`.

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