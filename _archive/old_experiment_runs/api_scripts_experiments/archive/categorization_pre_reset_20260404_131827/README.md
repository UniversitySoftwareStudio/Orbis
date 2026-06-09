# Categorization (Active Pipeline)

This directory uses a four-stage flow:
1) URL-first decisioning
2) AI taxonomy refinement for URL-resolved groups
3) Algorithm-only merge for `needs_algorithm` groups (no pass-1 rerun)
4) Tree + visualization artifacts for inspection/presentation

## Clean Entrypoint (Use This)
Use one script only:
```bash
python3 -u api/scripts/experiments/categorization/00_run_flow.py list
```

Run a stage by id or name:
```bash
python3 -u api/scripts/experiments/categorization/00_run_flow.py 01 -- --sample-size 0 --dynamic-depth
python3 -u api/scripts/experiments/categorization/00_run_flow.py classify-groups -- --input-json <umbrella_json>
python3 -u api/scripts/experiments/categorization/00_run_flow.py 90 -- --run-name taxonomy_clean --update-latest-link --archive-source-files
```

## Active scripts
- `01_build_url_groups.py`
- `02_classify_url_groups.py`
- `03_build_shortlist.py`
- `20_build_embeddings_optional.py`
- `21_cluster_subset_optional.py`
- `22_cluster_all_optional.py`
- `04_build_ai_input.py`
- `05_run_ai_mapping.py`
- `06_build_tree.py`
- `07_merge_algorithm_groups.py`
- `08_build_visuals.py`
- `URL_PARENT_PIPELINE_RUNBOOK.md`
- `FULL_FLOW.md`
- `00_run_flow.py` (clean stage router; preferred)

## Decision flow
1. Build umbrella URL parents (`01_build_url_groups.py`).
2. Score each parent with tail-depth diversity (`02_classify_url_groups.py`).
3. Interpret decisions:
   - `url_only_parent`: keep as a precise URL leaf.
   - `url_only_categorize`: URL path is semantically informative enough.
   - `needs_algorithm`: send to embedding/clustering stage.
4. Produce decision view / shortlist (`03_build_shortlist.py`).
5. Prepare AI input only from URL-resolved groups and check count before any AI run:
   - `04_build_ai_input.py`
   - includes only `url_only_parent` + `url_only_categorize`
   - excludes `needs_algorithm`
6. Run context-aware Ollama taxonomy refinement for URL-resolved groups:
   - `05_run_ai_mapping.py`
   - default mode is rule-first for directional stability
   - full run requires explicit `--confirm-count`
   - unresolved fallback prevents made-up categories when context is weak
   - optional `--ai-on-rule-matches` runs LLM even for rule-mapped groups
7. Build strict directional tree (`top_level -> sub_level -> leaf`) from taxonomy output:
   - `06_build_tree.py`
   - keep unresolved at `0` for pass-1
8. Merge algorithm-required groups into existing tree (no pass-1 rerun):
   - `07_merge_algorithm_groups.py`
   - builds reference leaf centroids from pass-1 mapped groups
   - clusters only `needs_algorithm` groups
   - attaches subclusters to nearest existing taxonomy leaves
9. Export full merged tree views:
   - produce full tree markdown/text from merged JSON
   - include full parent-child structure with algorithm children
10. Generate presentation visuals + literature mapping:
   - `08_build_visuals.py`
   - outputs per-step charts + report markdown
11. Run algorithm stage primitives when needed:
   - Create embeddings (`20_build_embeddings_optional.py`)
   - Cluster with PaCMAP hierarchy (`21_cluster_subset_optional.py`)
   - Or use scalable full-data clustering (`22_cluster_all_optional.py`)

## Runtime outputs
- Regenerate outputs under:
  `api/scripts/experiments/results/categorization/`
- Typical final artifacts:
  - `pass1_ai_taxonomy_*.json`
  - `pass1_taxonomy_tree_directional_*.json`
  - `pass2_algorithm_merge_*.json`
  - `pass2_taxonomy_tree_full_view_*.md`
  - `pass2_taxonomy_tree_everything_*.md`
  - `pass2_taxonomy_sunburst_docs_*.html`
  - `pass2_taxonomy_icicle_docs_*.html`

## Clean Working Style
- One run should read like a story from file names alone.
- Prefer one numbered stage file per step in a dedicated run folder.
- Avoid dumping many timestamped files at the same level.

Use:
```bash
python3 -u api/scripts/experiments/categorization/00_run_flow.py 90 -- \
  --run-name taxonomy_clean \
  --update-latest-link \
  --archive-source-files
```

This creates:
- `api/scripts/experiments/results/categorization/runs/<timestamp>_<run-name>/`
- numbered files like `01_url_umbrella__...json`, `02_depth_diversity__...json`, ...
- `FLOW.md` with stage status and key metrics
- optional symlink `latest_clean_run` for quick navigation
