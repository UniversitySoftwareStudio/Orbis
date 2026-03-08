# Orbis — Project Context Index

This file is the entry point for AI assistants reading this repo.
Read this file first, then read the specific concern file(s) relevant to what you're working on.

## What Is This Project?

Orbis is a RAG (Retrieval-Augmented Generation) system built for Istanbul Bilgi University.
It allows students and staff to query university data (course catalog, regulations, handbooks, announcements)
in natural language, in both Turkish and English.

It is a student project, built by two undergraduate students.

## File Map

| File | What it covers |
|------|----------------|
| `.github/copilot-instructions.md` | Global: tech stack, repo structure, conventions, known bugs, what NOT to do |
| `.github/instructions/rag-pipeline.instructions.md` | The full RAG pipeline: router, hybrid search, double-rerank, expansion, context building. **Read this if touching anything in `api/services/rag_service.py` or `api/database/repositories/rag_repository.py`** |
| `.github/instructions/data-pipeline.instructions.md` | Data sources, JSONL schemas, KnowledgeBase table design, embedding pipeline, language detection, title cleaning. **Read this if touching anything in `api/scripts/` or `api/ingest/`** |
| `.github/instructions/sis.instructions.md` | SIS models and repositories. **Read this before touching anything in `api/database/`** — the SIS is under active development and many things are incomplete or will be refactored |
| `.github/instructions/frontend.instructions.md` | React frontend: current state, auth flow, streaming. **Read this if touching anything in `web/`** |

## Quick orientation

- The production RAG lives in `api/services/rag_service.py` and `api/database/repositories/rag_repository.py`
- `api/services/regulation_service.py` is an **older, simpler** search used only for experiments — not production
- `docker-compose.yml` at the root is **not in active use** — ignore it
- Real data files (`*.jsonl`) are gitignored. `api/data/*_example.jsonl` files show their schemas
- The SIS (Student Information System) backend is partially built and will undergo significant changes