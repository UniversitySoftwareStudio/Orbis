# Clean Categorization Run

- created_at_utc: `2026-04-04T13:03:24.594720+00:00`
- source_results_dir: `/home/zperson/Orbis/api/scripts/experiments/results/categorization`
- run_dir: `/home/zperson/Orbis/api/scripts/experiments/results/categorization/runs/20260404_130324_taxonomy_clean`

## Stage Files

| Stage | Status | File | Notes |
|---|---|---|---|
| 01_url_umbrella | ok | `01_url_umbrella__docs-60649__clusters-250.json` | docs=60649, clusters=250 |
| 02_depth_diversity | ok | `02_depth_diversity__parent-143__categorize-65__needs-42.json` | url_only_parent=143, url_only_categorize=65, needs_algorithm=42 |
| 03_shortlist | ok | `03_shortlist__candidates-185__top-10.json` | candidate_groups=185, top_n=10 |
| 04_ai_input | ok | `04_ai_input__categories-208__excluded-needs-42.json` | categories_for_ai=208, excluded_needs=42 |
| 05_ai_taxonomy | ok | `05_ai_taxonomy__mapped-208__unresolved-0__provider-outlier.json` | mapped=208, unresolved=0, provider=outlier |
| 06_taxonomy_tree | ok | `06_taxonomy_tree__top-13__mapped-208__unresolved-0.json` | top_levels=13, mapped_categories=208, unresolved=0 |
| 07_algorithm_merge | ok | `07_algorithm_merge__mapped-sub-94__unresolved-sub-0__docs-60649.json` | mapped_subclusters=94, unresolved_subclusters=0, merged_docs=60649 |

## Status

- copied_stage_files: `7`
- required_stages: `complete`
