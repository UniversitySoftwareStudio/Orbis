# Orbis Event And Regulation System

This document describes the current repository state as of 2026-06-03. It also
marks where the report uses historical evaluation artifacts that are preserved
in the database and JSONL files.

## What The Current Event API Does

The wired `/api/events/*` API runs an orchestrator-led extraction pipeline over
`knowledge_base` rows whose category is `regulation` or `regulation_document`.
It creates traceable rows in `regulatory_events` and logs every major decision.

```text
POST /api/events/trigger
        |
        v
EventPipelineOrchestrator.start_run
        |
        v
SearchAgent.fetch_regulation_sources
        |
        v
ReasoningAgent.extract
  deterministic sentence / clause scan for assignable obligations
        |
        v
EventCreator.persist_candidates
  deterministic quality checks, dedup, optional ReasoningReviewer
        |
        v
regulatory_events + event_candidate_logs + event_agent_logs
```

The orchestrator owns run state. `SearchAgent`, `ReasoningAgent`, and
`EventCreator` are stateless workers. `ReasoningReviewer` is optional and is
controlled by `EVENTS_ENABLE_REASONING_REVIEW`; when enabled, it calls the LLM
provider configured by `api/llm/service.py`.

## Current Event API Surface

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /api/events/trigger` | admin | Start a background extraction run |
| `GET /api/events/runs/{run_id}` | admin | Poll run counters and status |
| `GET /api/events/runs/{run_id}/telemetry` | admin | Read agent/run telemetry |
| `GET /api/events/runs/{run_id}/candidates` | admin | Read candidate decisions |

There is no currently wired `/api/events/assign/me` endpoint. Student-facing
regulation assignments are exposed through `/api/regulations/me`, which reads
precomputed `user_rule_assignments` joined to `regulation_rules`.

## Report Evaluation Boundary

The report's quantitative regulation-assignment results are based on the
historical action-object pipeline preserved in the database and artifacts:

- `regulation_rules`: accepted action objects used for user assignment.
- `user_rule_assignments`: precomputed per-user rule assignments.
- `event_candidate_logs`: candidate decisions used for silver-label scoring.
- `api/data/ground_truth/events/*.jsonl`: LLM-judge labels.
- `api/scripts/experiments/eval_event_extraction.py`
- `api/scripts/experiments/eval_assignment_matching.py`

Those artifacts reproduce these report metrics:

| Metric | Value |
|---|---:|
| Source documents processed | 80 |
| KB chunks consumed | 935 |
| Candidate rules evaluated | 323 |
| Accepted active rules | 178 |
| Rejected candidates | 145 |
| Event extraction precision / recall / F1 | 0.978 / 0.574 / 0.723 |
| Assignment matching precision / recall / F1 | 0.608 / 0.446 / 0.514 |
| Active user-rule assignments in evaluated DB snapshot | 176 |

## Student-Facing Regulation Route

`/api/regulations/me` returns active/precomputed regulation assignments for the
authenticated user. Each row includes urgency, status, reason, rule text,
trigger, deadline, consequence, authority, and blocking flag. Users can mark an
assignment `active`, `actioned`, or `dismissed` through:

```text
PATCH /api/regulations/assignments/{assignment_id}
```

## Why The Distinction Matters

The repository contains both live runtime code and research/evaluation evidence.
For the demo, the UI can show existing regulation assignments. For the report,
the historical extraction and matching data provide measured precision/recall
and error analysis. Future work is to reconnect the extraction route, assignment
matcher, and student regulation UI into one live end-to-end workflow.

## Key Files

- `api/events/orchestrator.py`
- `api/events/search_agent.py`
- `api/events/reasoning_agent.py`
- `api/events/event_creator.py`
- `api/events/reasoning_reviewer.py`
- `api/routes/events.py`
- `api/routes/regulations.py`
- `api/database/models/events.py`
- `api/scripts/experiments/eval_event_extraction.py`
- `api/scripts/experiments/eval_assignment_matching.py`
