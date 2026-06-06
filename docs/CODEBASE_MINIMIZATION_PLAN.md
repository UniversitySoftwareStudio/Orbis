# Codebase Minimization Plan

Updated: 2026-06-03.

This is still a preservation-first cleanup plan. Do not delete evidence used by
the report just to make the tree look smaller.

## Purpose

Make the repo easy to understand for the report and video.

Not production cleanup. Not deleting evidence.

## What Must Stay

- Working backend and frontend.
- Demo path: auth, chat, calendar/schedule, assignments, submission review.
- Report source and render script.
- Evaluation scripts.
- Ground-truth data.
- Final experiment results used by the report.

## What Is Evidence

Keep these. They prove the report metrics.

- `api/data/ground_truth/events/`
- `api/data/ground_truth/submissions/`
- `api/scripts/experiments/eval_*.py`
- `api/scripts/experiments/results/categorization/runs/20260404_130324_taxonomy_clean/`
- `api/scripts/experiments/results/categorization/flow/12_cluster_regulations/`
- `api/scripts/experiments/results/categorization/flow/14_final_tree/`

## What Should Be Archived

Do not delete old experiments. Move or keep them under an obvious archive path.

- Old experiment archives.
- Huge intermediate JSON files.
- Old categorization attempts.
- Report sample PDFs.
- Generated visuals not used in the report.

## What Can Be Ignored Locally

These do not need to be committed. They can be regenerated.

- `web/node_modules/`
- `web/dist/`
- `report/build/`
- `report/report.pdf`
- `api/tests/reports/`
- `api/uploads/`
- LaTeX aux/log files.

## Current Documentation Boundary

- Active runtime docs: `README.md`, `api/README.md`, `web/README.md`,
  `EVENT_SYSTEM.md`, and the short notes in `docs/`.
- Report-facing evidence: `report/report.tex`,
  `api/data/ground_truth/events/`, `api/data/ground_truth/submissions/`, and
  `api/scripts/experiments/eval_*.py`.
- Historical categorization artifacts are evidence, not runtime code. Keep the
  final report inputs in place and move only obsolete attempts under
  `archive/old_experiment_runs/`.

## Code Smells To Fix

- Archive legacy `api/database/models.py` if tests pass.
- Decide whether event assignments are real or report-only:
  - current API exposes event extraction to `regulatory_events`,
  - current student UI reads precomputed `user_rule_assignments`,
  - old docs mentioned `/api/events/assign/me`; that route is not wired.
- Archive unused wrappers only after confirming imports.
- Keep one clear RAG path.

## Target Shape

```text
api/       runtime backend
web/       runtime frontend
report/    final report
docs/      short notes
archive/   old experiments
```

## Steps

1. Keep all old experiments.
2. Add clear ignores.
3. Move old experiment runs into `archive/old_experiment_runs/`.
4. Keep current/final report evidence in place.
5. Archive or mark confirmed dead code.
6. Keep demo path stable.

## Done When

- Reviewer can understand the repo in 5 minutes.
- Video can show the system working.
- Report metrics point to exact scripts/data.
- Evidence is preserved.
- Runtime code is not buried under experiment clutter.
