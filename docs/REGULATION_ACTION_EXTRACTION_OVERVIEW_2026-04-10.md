# Regulation Action Extraction Overview - 2026-04-10 Run

This is the historical DB run used by the report's regulation-assignment
metrics. It is evidence, not necessarily the exact behavior of the currently
wired `/api/events/trigger` route.

## Historical Flow

```text
Categorized regulation document set
  -> 80 regulation documents
  -> 935 KB chunks
  -> candidate action extraction
  -> review / fix / remove
  -> timing + specificity + dedup quality gates
  -> regulation_rules
  -> user_rule_assignments
```

## Final Run Result

| Quantity | Value |
|---|---:|
| Documents total | 80 |
| Done | 59 |
| Skipped | 21 |
| Failed | 0 |
| Candidate rules evaluated | 323 |
| Accepted actions | 178 |
| Rejected candidates | 145 |
| Blocking actions | 108 |
| Non-blocking actions | 70 |
| Contextual actions | 167 |
| SQL actions | 11 |
| Student-targeted actions | 153 |
| Staff-targeted actions | 11 |
| Admin-targeted actions | 9 |
| All-role actions | 5 |

## Action Object Shape

- `rule_text`
- `applies_to`
- `trigger`
- `deadline`
- `valid_from`
- `valid_until`
- `blocking`
- `consequence`
- `authority`
- `exceptions`
- `target_role`
- `match_type`
- `sql_condition`
- `confidence`
- `evidence_quote`

## Sample Actions

- Internship timing: do not begin a compulsory internship before the summer
  following the end of the fourth semester.
- Internship documents: submit internship contract forms at least 10 working
  days before the internship start date.
- Graduation project: find a project advisor within the first two weeks of the
  first semester.
- Exams: bring university identification card to every examination.

## Filtered Out

- Expired announcements.
- Blank forms.
- Committee workflow or internal governance text.
- Purpose/definition text.
- Generic awareness items.

## Reproduction And Current Boundary

Report-facing evaluation:

```bash
python3 api/scripts/experiments/eval_event_extraction.py
python3 api/scripts/experiments/eval_assignment_matching.py
```

Current runtime extraction code:

- `api/events/orchestrator.py`
- `api/events/reasoning_agent.py`
- `api/events/event_creator.py`

Current student-facing regulation API:

- `api/routes/regulations.py`

The current runtime route writes `regulatory_events`; this historical run's
assignment metrics use `regulation_rules` and `user_rule_assignments`.
