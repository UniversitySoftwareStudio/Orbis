# Orbis

Orbis is a student-built academic support system for Istanbul Bilgi University.
It combines a conventional SIS-style backend, a retrieval-augmented chat/search
interface, a regulation-event extraction pipeline, and an agentic assignment
submission reviewer.

The project is a prototype, but the report artifacts are evidence-backed:
the repository contains the LaTeX report, evaluation scripts, silver ground
truth data, and archived categorization experiments used to support the
reported metrics.

## Current Capabilities

- Authenticated React student shell with dashboard, chat, academic calendar,
  weekly schedule, courses, assignments, transcript, regulations, profile, and
  settings pages.
- FastAPI backend with cookie-based auth, PostgreSQL/SQLAlchemy models,
  student/SIS projections, course/regulation search, and assignment submission
  endpoints.
- RAG pipeline that routes between SQL-like course lookup and vector retrieval,
  expands source context, reranks results, and streams LLM answers.
- Regulation-event pipeline exposed through `/api/events/*` for admin-triggered
  extraction runs over categorized regulation knowledge-base rows.
- Student-facing regulation assignments exposed through `/api/regulations/me`
  from precomputed `user_rule_assignments`.
- Assignment submission reviewer that performs deterministic file inspection,
  extracts text from PDF/DOCX/ZIP/text-like files, decomposes requirements, and
  streams per-requirement evaluation over Server-Sent Events.

## Evidence Used By The Report

- Main report: `report/report.tex`
- Bibliography: `report/references.bib`
- Report samples and writing notes: `report/reports/`, `report/notes/`
- Event/assignment ground truth: `api/data/ground_truth/events/`
- Submission-review ground truth: `api/data/ground_truth/submissions/`
- Evaluation scripts: `api/scripts/experiments/eval_*.py`
- Final taxonomy artifacts:
  - `api/scripts/experiments/results/categorization/runs/20260404_130324_taxonomy_clean/`
  - `api/scripts/experiments/results/categorization/flow/12_cluster_regulations/`
  - `api/scripts/experiments/results/categorization/flow/14_final_tree/`

## Important Implementation Boundary

There are two related regulation pipelines in the repository:

- The currently wired `/api/events/trigger` path creates rows in
  `regulatory_events` using `SearchAgent`, deterministic `ReasoningAgent`,
  `EventCreator`, and optional `ReasoningReviewer`.
- The report's assignment-matching metrics use historical database/evaluation
  artifacts around `regulation_rules`, `user_rule_assignments`, and
  `event_candidate_logs`. Those artifacts are preserved for reproducibility,
  but there is no currently exposed `/api/events/assign/me` route.

This boundary is intentional to document honestly: the demo UI reads existing
regulation assignments through `/api/regulations/me`, while event extraction
telemetry is exposed separately through `/api/events/*`.

## Tech Stack

- Backend: Python 3.10, FastAPI, SQLAlchemy, PostgreSQL, pgvector
- Frontend: React, Vite, TypeScript, lucide-react
- Runtime / infra: Uvicorn for the API; Docker Compose currently defines the
  optional TEI embedding load balancer, not a full application stack
- LLMs: Gemini by default through `api/llm/service.py`, Groq/OpenAI-compatible
  providers through environment configuration; evaluation scripts use
  OpenRouter directly through `api/scripts/experiments/_llm_judge.py`
- Embeddings: local/TEI providers under `api/embedding/`

## Run Locally

Backend:

```bash
cd api
python main.py
```

Frontend:

```bash
cd web
npm install
npm run dev
```

LaTeX report:

```bash
cd report
./render.sh
```

## Repository Map

- `api/`: FastAPI backend, RAG, SIS routes, event pipeline, submission agent,
  database models/repositories, seed/migration/evaluation scripts.
- `web/`: React/Vite frontend.
- `report/`: LaTeX report, references, sample reports, report notes.
- `docs/`: short engineering notes and audits.
- `archive/`: old experiment runs moved out of the active path but preserved.

## Main Verification Commands

```bash
python3 api/scripts/experiments/eval_event_extraction.py
python3 api/scripts/experiments/eval_assignment_matching.py
python3 api/scripts/experiments/eval_submission_agent.py
cd report && latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build report.tex
```

Some commands depend on a live PostgreSQL database with the historical Orbis
evaluation data. The report PDF can be rebuilt from source without running the
database-backed experiments.
