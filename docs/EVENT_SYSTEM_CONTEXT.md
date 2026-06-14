# Event System Context

Updated: 2026-06-03

This note is the short technical context for the regulation/event system. The
root `EVENT_SYSTEM.md` is the canonical overview; this file keeps the report
and demo boundaries explicit.

## Current Runtime Path

The active FastAPI route is:

```text
POST /api/events/trigger
```

It creates an `event_runs` row, runs `EventPipelineOrchestrator` in the
background, reads regulation sources from `knowledge_base`, extracts obligation
candidates, validates/deduplicates them, and writes accepted rows to
`regulatory_events`.

Core runtime tables:

- `event_runs`
- `event_source_logs`
- `event_source_checkpoints`
- `event_agent_logs`
- `event_candidate_logs`
- `regulatory_events`

Core runtime files:

- `api/routes/events.py`
- `api/events/orchestrator.py`
- `api/events/search_agent.py`
- `api/events/reasoning_agent.py`
- `api/events/event_creator.py`
- `api/events/reasoning_reviewer.py`

## Current Student Regulation Path

The student-facing regulations page reads precomputed assignments:

```text
GET /api/regulations/me
PATCH /api/regulations/assignments/{assignment_id}
```

These endpoints read/write `user_rule_assignments`, joined to
`regulation_rules`.

A live per-user matcher is also exposed:

```text
POST /api/regulations/check/stream
```

It runs the user agent (`events/user_agent.py`) over the current user, reasons
rule-by-rule, and writes `user_rule_assignments` (SSE trace). The trigger
pipeline now feeds this path: accepted `regulatory_events` are promoted into
`regulation_rules` (see `api/events/promotion.py`) so the agent matches against
what the pipeline found. The canonical end-to-end flow is in the root
[`EVENT_SYSTEM.md`](../EVENT_SYSTEM.md).

## Report Evidence Path

The report uses measured artifacts from the historical action-object pipeline:

- 80 regulation sources.
- 935 regulation chunks.
- 323 candidate rules.
- 178 accepted obligations.
- 145 rejected candidates.
- 176 precomputed user-rule assignments over 4 test profiles.
- Silver event labels in `api/data/ground_truth/events/candidates_gt.jsonl`.
- Silver assignment labels in
  `api/data/ground_truth/events/assignment_matching_gt.jsonl`.

Reproduction commands:

```bash
python3 api/scripts/experiments/eval_event_extraction.py
python3 api/scripts/experiments/eval_assignment_matching.py
```

The first command only needs JSONL artifacts. The second command also queries
the historical PostgreSQL database to recover the system's positive
profile-rule pairs.

## Known Gaps

- The extraction route writes `regulatory_events`; those accepted events are now
  promoted into `regulation_rules` (`api/events/promotion.py`), which is what the
  per-user matcher and the regulations UI consume. Promotion adds rules but does
  not yet retire ones whose source regulation disappeared.
- Promoted rules are thin (obligation sentence + role); they do not carry
  structured deadline/consequence/blocking fields. Enriching the extractor is
  future work.
- The event extraction labels are silver LLM labels, not human gold labels.
- Inter-judge agreement is 0.529 on a 51-candidate sample, so recall should be
  interpreted conservatively.
- Admin review of `NEEDS_REVIEW` events has no dedicated UI yet; promotion takes
  `PENDING` events only.
