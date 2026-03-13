# Events Pipeline Flow

## Architecture Flow
This is the high-level agent flow only. The orchestrator is the hub, and every other agent talks through it.

```text
+---------------------------+
| Admin / Trigger API       |
| Starts an event run       |
+-------------+-------------+
              |
              v
+---------------------------+
| EventPipelineOrchestrator |
| Central coordinator       |
+------+------+-------------+
       |      |
       |      +-----------------------------------+
       |                                          |
       v                                          v
+---------------------------+     +-------------------------------+
| SearchAgent               |     | Pipeline State + Telemetry    |
| Finds regulation sources  |     | event_runs                    |
| to inspect                |     | event_source_logs             |
+-------------+-------------+     | event_agent_logs              |
              |                   | event_source_checkpoints      |
              +------------------>|                               |
              | source list       +-------------------------------+
              v
+---------------------------+
| EventPipelineOrchestrator |
| Selects one source        |
+-------------+-------------+
              |
              v
+---------------------------+
| ReasoningAgent            |
| Extracts obligation       |
| candidates from source    |
+-------------+-------------+
              | candidates
              v
+---------------------------+
| EventPipelineOrchestrator |
| Forwards candidates       |
+-------------+-------------+
              |
              v
+---------------------------+
| EventCreator              |
| Validates candidates      |
| Creates final events      |
+-------------+-------------+
              |
              | ambiguous only
              v
+---------------------------+
| ReasoningReviewer         |
| Optional extra review     |
+-------------+-------------+
              |
              | reviewed decision
              v
+---------------------------+
| EventCreator              |
| Final accept / reject     |
+------+------+-------------+
       |      |
       |      +------------------------------+
       |                                     |
       v                                     v
+---------------------------+   +-------------------------------+
| regulatory_events         |   | EventPipelineOrchestrator     |
| Final accepted events     |   | Updates counters, logs,       |
|                           |   | and moves to next source      |
+---------------------------+   +-------------------------------+
```

## Agent Communication Summary
- `EventPipelineOrchestrator` starts the run and controls the full flow.
- `SearchAgent` finds regulation sources worth processing.
- `ReasoningAgent` reads one source at a time and extracts obligation candidates.
- `EventCreator` decides which candidates become real events.
- `ReasoningReviewer` is only used when `EventCreator` wants extra review for ambiguous candidates.
- Final accepted output is written as events, while the orchestrator also writes logs and checkpoints.

## Agent Flow At The Top
This pipeline is **orchestrator-led**. The agents do not talk to each other directly and there is no event bus yet.

Communication happens in two simple ways:
- **In memory:** the orchestrator calls each agent and passes plain Python objects.
- **In the database:** the orchestrator writes run/source/agent logs and checkpoints so the flow is traceable and repeatable.

### Who owns state
- `EventPipelineOrchestrator` is the **only state owner**.
- `SearchAgent`, `ReasoningAgent`, and `EventCreator` are **stateless workers**.
- `ReasoningReviewer` is an optional LLM review step used **inside** `EventCreator`, not a top-level pipeline agent.

### What each agent sends to the next one
- `SearchAgent.fetch_regulation_sources(db)`
  - Reads `knowledge_base`
  - Returns `list[SourceDocument]`
  - Each `SourceDocument` contains the canonical URL, `source_key`, `content_hash`, chunk ids, merged text, and skip metadata
- `ReasoningAgent.extract(source)`
  - Receives one `SourceDocument`
  - Returns `list[ObligationCandidate]`
  - Each candidate contains the obligation text, evidence excerpt, target role, and source metadata
- `EventCreator.persist_candidates(db, run_id, candidates)`
  - Receives candidates for one source
  - Runs deterministic quality checks, optional LLM review, and dedup
  - Writes accepted rows into `regulatory_events`
  - Returns `PersistStats` to the orchestrator

### Simple communication model
1. API trigger creates a run.
2. The orchestrator asks `SearchAgent` for processable regulation sources.
3. For each source, the orchestrator decides whether to skip or process it.
4. If processing continues, the orchestrator sends the source text to `ReasoningAgent`.
5. `ReasoningAgent` returns obligation candidates to the orchestrator.
6. The orchestrator sends those candidates to `EventCreator`.
7. `EventCreator` validates, deduplicates, optionally asks `ReasoningReviewer`, then writes final events.
8. `EventCreator` returns summary counts to the orchestrator.
9. The orchestrator writes checkpoints/logs and moves to the next source.

### How they communicate in practice
- `SearchAgent` does not insert events or update run status.
- `ReasoningAgent` does not read or write database state.
- `EventCreator` does not choose which sources to process.
- The orchestrator is the layer that:
  - starts the run
  - loops through sources
  - checks `event_source_checkpoints`
  - updates `event_runs`
  - writes `event_source_logs`
  - writes `event_agent_logs`
  - handles failures

### End-to-end sequence
```mermaid
sequenceDiagram
    participant Client
    participant Route as POST /api/events/trigger
    participant Orch as EventPipelineOrchestrator
    participant Search as SearchAgent
    participant Reason as ReasoningAgent
    participant Create as EventCreator
    participant Review as ReasoningReviewer (optional)
    participant DB as PostgreSQL

    Client->>Route: trigger pipeline
    Route->>Orch: start_run(db)
    Orch->>DB: insert event_runs(status=RUNNING)
    Orch->>DB: insert event_agent_logs(orchestrator, run_started)
    Route-->>Client: { run_id, status }

    Route->>Orch: run_existing(db) in background
    Orch->>Search: fetch_regulation_sources(db)
    Search->>DB: read knowledge_base rows
    Search-->>Orch: list[SourceDocument]
    Orch->>DB: insert event_agent_logs(search, sources_loaded)

    loop each source
        Orch->>DB: check event_source_checkpoints by source_key
        alt skipped
            Orch->>DB: update event_source_logs(status=SKIPPED)
            Orch->>DB: insert event_agent_logs(search, skip)
        else processed
            Orch->>DB: upsert event_source_logs(status=PENDING)
            Orch->>DB: insert event_agent_logs(orchestrator, source_selected)
            Orch->>Reason: extract(source)
            Reason-->>Orch: list[ObligationCandidate]
            Orch->>DB: insert event_agent_logs(reasoning, obligations_extracted)
            Orch->>Create: persist_candidates(db, run_id, candidates)
            opt reviewer enabled
                Create->>Review: review_batch(candidates)
                Review-->>Create: reviewed decisions
            end
            Create->>DB: insert regulatory_events
            Create->>DB: insert event_candidate_logs
            Create-->>Orch: PersistStats
            Orch->>DB: insert event_agent_logs(event_creator, persist_summary)
            Orch->>DB: insert event_source_checkpoints
            Orch->>DB: update event_source_logs(status=DONE)
            Orch->>DB: update event_runs counters
        end
    end

    Orch->>DB: update event_runs(status=COMPLETED)
    Orch->>DB: insert event_agent_logs(orchestrator, run_completed)
```

### Why this design matters
- It keeps agent responsibilities narrow.
- It makes the pipeline deterministic except for the optional LLM review step.
- It makes reruns safe because processed sources are guarded by `event_source_checkpoints`.
- It makes debugging easy because every important decision is written to telemetry tables.

## Purpose
Extract strict, assignable obligations from `knowledge_base` rows in:
- `category = regulation`
- `category = regulation_document`

Create normalized events in `regulatory_events`.

## Trigger
- `POST /api/events/trigger` (admin)
- Returns `{ run_id, status }`
- Runs in background.

## Core Flow
1. `EventPipelineOrchestrator.start_run`
   - Creates `event_runs` row (`RUNNING`).
   - Writes the first orchestrator telemetry record.
2. `SearchAgent.fetch_regulation_sources`
   - Loads `knowledge_base` rows for `regulation` and `regulation_document`.
   - Canonicalizes URLs so `http/https` variants collapse into one source.
   - Groups rows into source documents and scores whether each one should be processed.
3. For each source:
   - Skip if it was already seen in memory during the run.
   - Skip if `should_process` is false.
   - Skip if `event_source_checkpoints` already has the same `source_key`.
   - Otherwise send the source to `ReasoningAgent.extract`.
4. `ReasoningAgent.extract`
   - Splits the merged text into atomic segments.
   - Keeps only segments that look like strict, assignable obligations.
   - Returns obligation candidates.
5. `EventCreator.persist_candidates`
   - Applies deterministic quality checks.
   - Optionally asks `ReasoningReviewer` for stricter normalization/decisioning.
   - Rejects weak candidates and duplicates.
   - Writes accepted rows to `regulatory_events`.
   - Writes all candidate decisions to `event_candidate_logs`.
6. Orchestrator finalization for that source
   - Writes `event_source_checkpoints`.
   - Marks the source `DONE` in `event_source_logs`.
   - Updates counters on `event_runs`.
7. End of run
   - Mark run `COMPLETED`
   - Or mark `FAILED` with `error_message` if any step raises

## State Ownership
- Stateful: `EventPipelineOrchestrator`
- Stateless workers:
  - `SearchAgent`
  - `ReasoningAgent`
  - `EventCreator`

## Telemetry
- Source-level logs: `event_source_logs`
- Agent-level logs: `event_agent_logs`
  - fields include `agent`, `state`, `decision`, `reason`, `payload`
- Candidate-level logs: `event_candidate_logs`
- Run summary: `event_runs`

## Read APIs
- `GET /api/events/runs/{run_id}`
  - run status + counters
- `GET /api/events/runs/{run_id}/telemetry?limit=200`
  - ordered agent trace for the run
- `GET /api/events/runs/{run_id}/candidates?limit=200`
  - ordered candidate decisions for the run

## Main Tables
- `event_runs`
- `event_source_logs`
- `event_source_checkpoints`
- `event_agent_logs`
- `event_candidate_logs`
- `regulatory_events`

## Current Quality Controls
- Reject weak or non-actionable candidates.
- Require actor + strict obligation markers.
- Reject noisy fragments and non-assignable governance text.
- Dedup inside the batch and against existing events by normalized text + role fingerprint.
- Route ambiguous but plausible obligations into `NEEDS_REVIEW`.
