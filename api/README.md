# `api/`

FastAPI backend for Orbis. It owns authentication, SIS read projections, RAG
chat/search, regulation-event extraction, student regulation assignments, and
assignment submission review.

## Active Modules

- `main.py`: FastAPI bootstrap, CORS, DB initialization, router wiring.
- `routes/`: HTTP endpoints. Keep route files thin.
- `services/`: app-level service wrappers and auth/RAG entry points.
- `rag/`: query routing, SQL/vector retrieval, reranking, context building.
- `llm/`: Gemini/Groq/OpenAI-compatible provider selection.
- `embedding/`: local/TEI embedding runtime and backfill helpers.
- `events/`: regulation-source loader, candidate extraction, validation,
  optional review, telemetry, and checkpointing.
- `agents/submission_agent.py`: agentic assignment submission evaluator.
- `database/`: SQLAlchemy sessions, repositories, and the `models/` **package** (`identity`, `academic`, `knowledge`, `events`, `enums`). Note: the standalone `database/models.py` *file* is dead, shadowed code — Python imports the package; edit the package, not the file.
- `scripts/`: migrations, seed scripts, ingestion utilities, and evaluation
  scripts used by the report.
- `data/ground_truth/`: event, assignment-matching, and submission-review
  evaluation artifacts.

## Router Surface

- `/api/auth/*`: register, login, refresh, current user.
- `/api/chat`, `/api/search`, `/api/ask`: RAG chat/search endpoints.
- `/api/sis/calendar`, `/api/sis/schedule/me`: calendar and schedule.
- `/api/sis/dashboard`, `/api/sis/profile/me`, `/api/sis/transcript/me`,
  `/api/sis/courses/me`: student-facing SIS projections.
- `/api/events/*`: admin-triggered regulation event extraction and telemetry.
- `/api/regulations/me`: current user's precomputed regulation assignments.
- `/api/assignments/*`: pending assignments, upload, streaming submission
  review, and student rejection flagging.

## Run

```bash
python main.py
```

The app expects a PostgreSQL database configured through environment variables
loaded from `api/.env`. LLM-backed paths also require the provider-specific key
for `LLM_PROVIDER` (`gemini` by default).

## Report Verification

These scripts reproduce the report's quantitative tables when the historical
evaluation database/artifacts are present:

```bash
python3 api/scripts/experiments/eval_event_extraction.py
python3 api/scripts/experiments/eval_assignment_matching.py
python3 api/scripts/experiments/eval_submission_agent.py
```
