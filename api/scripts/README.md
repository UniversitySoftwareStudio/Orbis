# `api/scripts/`

Operational and research scripts used to seed, ingest, migrate, and evaluate
Orbis data.

## Groups

- `migrations/`: SQL migrations for academic calendar, schedules, regulation
  rules, action fields, and assignment-submission review.
- `seed_*.py`: small seeders for calendar, enrollments, sections, schedules,
  and students.
- `scrape/` and `ingest/`: data ingestion utilities for scraped university
  pages, PDFs, and database backfill.
- `categorization/`: older URL categorization helpers.
- `experiments/`: report-facing experiment/evaluation scripts.

## Report-Facing Scripts

```bash
python3 api/scripts/experiments/eval_event_extraction.py
python3 api/scripts/experiments/eval_assignment_matching.py
python3 api/scripts/experiments/eval_submission_agent.py
```

The event and assignment matching evaluators expect access to the historical
Orbis PostgreSQL database or the JSONL artifacts under
`api/data/ground_truth/events/`. The submission evaluator can run from the
deterministic files under `api/data/ground_truth/submissions/`, assuming the
LLM judge configuration is available.
