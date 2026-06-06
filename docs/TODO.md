# Current TODO - 2026-06-03

This replaces the older March cleanup TODO. The old items around adding a
`category` column and embedding-model tables are historical; the report now
depends on the categorized regulation subset and evaluation artifacts already
present in the repo.

## Report / Documentation

- [ ] Keep `report/report.tex` aligned with the current implementation boundary:
  `/api/events/*` writes `regulatory_events`, while the reported assignment
  metrics use `regulation_rules` and `user_rule_assignments`.
- [ ] Add a short limitations paragraph anywhere the report mentions silver
  ground truth: the event labels are LLM-produced and inter-judge agreement is
  0.529 on 51 candidates.
- [ ] Keep the baseline-paper notes in `report/baseline_papers/README.md`
  synchronized with `report/references.bib`.

## Runtime / Demo

- [ ] Reconnect the live event extraction route to the per-user regulation
  assignment flow, or explicitly keep the current split as demo data.
- [ ] Decide whether to expose a new `/api/events/assign/me` route or keep
  `/api/regulations/me` as the only student-facing regulation endpoint.
- [ ] Add a reviewer/admin queue page for submissions flagged by students.
- [ ] Add a third submission-agent output class (`flagged`) so partial or
  suspicious work routes to human review instead of binary approve/reject.

## Evaluation

- [ ] Convert the 323 event-candidate silver labels into human-validated gold.
- [ ] Expand the submission-review set beyond 32 deterministic cases.
- [ ] Add more prompt-injection variants; current 4/4 result is directional,
  not a general security guarantee.
- [ ] Re-run assignment matching after matcher calibration and report confidence
  intervals or sensitivity over `maybe` labels.

## Cleanup

- [ ] Keep generated/local files out of commits: `web/node_modules/`,
  `report/build/`, `api/uploads/`, `api/tests/reports/`.
- [ ] Preserve archived experiment outputs under `archive/old_experiment_runs/`.
- [ ] Review whether legacy `api/database/models.py` can be archived after
  imports/tests are stable.
