# Full Pipeline Flow (Current)

This document is the canonical end-to-end flow for the categorization system in this directory.
It reflects the current production-style approach:
- freeze pass-1 taxonomy
- process only `needs_algorithm` in pass-2
- merge without rerunning pass-1 AI

## 1) Purpose

Build a stable, directional taxonomy for source documents:
- use URL structure first where reliable
- use vector clustering only where URL tails are low-signal/repetitive
- keep all outputs auditable as tree artifacts

## 2) Core Decisions

Each URL cluster is assigned one of:
- `url_only_parent`
- `url_only_categorize`
- `needs_algorithm`

Interpretation:
- `url_only_parent`: parent URL branch itself is enough as a stable leaf.
- `url_only_categorize`: tail text diverges enough to categorize with URL evidence.
- `needs_algorithm`: URL signal is low/repetitive; use embedding-based clustering.

## 3) Stage-by-Stage Flow

1. URL umbrella clustering
- Script: `01_build_url_groups.py`
- Output: umbrella clusters with `cluster_id`, `representative_parent`, `doc_ids`, `chosen_depth`.

2. Tail-depth diversity scoring
- Script: `02_classify_url_groups.py`
- Output: per-cluster metrics and final `decision`.
- Key low-signal triggers:
  - numeric-heavy tails
  - repetitive tail patterns
  - low entropy / low unique tail patterns

3. Shortlist view
- Script: `03_build_shortlist.py`
- Output: human-readable candidate view with priorities.

4. Pass-1 AI input preparation (URL-resolved only)
- Script: `04_build_ai_input.py`
- Includes only:
  - `url_only_parent`
  - `url_only_categorize`
- Excludes:
  - `needs_algorithm`

5. Pass-1 AI taxonomy refinement
- Script: `05_run_ai_mapping.py`
- Provider: `outlier` or `ollama`
- Safety:
  - count gate (`--dry-run-count`)
  - full-run confirmation (`--confirm-count`)
- Current stable usage:
  - rule-first mapping for directional consistency
  - unresolved fallback for weak outputs

6. Pass-1 directional tree
- Script: `06_build_tree.py`
- Output tree shape:
  - `top_level -> sub_level -> canonical_label`

7. Pass-2 algorithm merge (no pass-1 rerun)
- Script: `07_merge_algorithm_groups.py`
- Inputs:
  - depth decisions JSON
  - umbrella JSON
  - pass-1 AI JSON
  - pass-1 tree JSON
  - embeddings from `knowledge_base_embeddings`
- Method:
  - build reference leaf centroids from pass-1 mapped groups
  - cluster only `needs_algorithm` groups
  - map subcluster centroid to nearest pass-1 leaf (cosine)
  - merge mapped subclusters into existing tree

8. Full tree and visual outputs
- Full tree markdown/text (complete parent-child view)
- Interactive final tree:
  - sunburst HTML
  - icicle HTML
- Pipeline visuals:
  - `08_build_visuals.py`

## 4) Commands (Clean Run)

```bash
find api/scripts/experiments/results/categorization -mindepth 1 -maxdepth 1 -type f -delete

python3 -u api/scripts/experiments/categorization/01_build_url_groups.py \
  --sample-size 0 --dynamic-depth --min-depth 2 --max-depth 3 \
  --min-parent-docs 6 --similarity-threshold 0.85 \
  --run-name clean_url_umbrella_parents_dynamic_d23

python3 -u api/scripts/experiments/categorization/02_classify_url_groups.py \
  --input-json api/scripts/experiments/results/categorization/clean_url_umbrella_parents_dynamic_d23_*.json \
  --run-name clean_url_parent_depth_diversity_d23_fulltail

python3 -u api/scripts/experiments/categorization/04_build_ai_input.py \
  --depth-json api/scripts/experiments/results/categorization/clean_url_parent_depth_diversity_d23_fulltail_*.json \
  --umbrella-json api/scripts/experiments/results/categorization/clean_url_umbrella_parents_dynamic_d23_*.json \
  --include-decisions url_only_parent,url_only_categorize \
  --sample-urls-per-category 3 \
  --run-name clean_ai_taxonomy_pass1_input

python3 -u api/scripts/experiments/categorization/05_run_ai_mapping.py \
  --llm-provider outlier \
  --outlier-url http://127.0.0.1:8080 \
  --input-json api/scripts/experiments/results/categorization/clean_ai_taxonomy_pass1_input_*.json \
  --ollama-model claude-opus-4-6 \
  --confirm-count <COUNT_FROM_DRY_RUN> \
  --run-name clean_ai_taxonomy_pass1_ollama_full

python3 -u api/scripts/experiments/categorization/06_build_tree.py \
  --input-json api/scripts/experiments/results/categorization/clean_ai_taxonomy_pass1_ollama_full_*.json \
  --run-name clean_taxonomy_tree_directional

python3 -u api/scripts/experiments/categorization/07_merge_algorithm_groups.py \
  --depth-json api/scripts/experiments/results/categorization/clean_url_parent_depth_diversity_d23_fulltail_*.json \
  --umbrella-json api/scripts/experiments/results/categorization/clean_url_umbrella_parents_dynamic_d23_*.json \
  --pass1-ai-json api/scripts/experiments/results/categorization/clean_ai_taxonomy_pass1_ollama_full_*.json \
  --pass1-tree-json api/scripts/experiments/results/categorization/clean_taxonomy_tree_directional_*.json \
  --model-id 6 \
  --reference-docs-per-pass1-cluster 20 \
  --max-subclusters 12 \
  --min-docs-to-split 24 \
  --min-subcluster-size 8 \
  --min-similarity 0.20 \
  --db-chunk-size 2000 \
  --run-name clean_pass2_algorithm_merge
```

## 5) Merge Script Knobs (Important)

- `--reference-docs-per-pass1-cluster`
  - Reference sample size for pass-1 leaf centroids.
  - `0` means use all pass-1 docs.
- `--max-subclusters`
  - Max local k per `needs_algorithm` source cluster.
- `--min-docs-to-split`
  - If group docs are below this, keep k=1.
- `--min-subcluster-size`
  - Prevents over-fragmentation in local k selection.
- `--min-similarity`
  - Similarity threshold for attaching subcluster to a taxonomy leaf.
- `--db-chunk-size`
  - ID fetch batch size for embeddings.
- `--fetch-all-model-if-ids-ge`
  - Optional full-model scan threshold (default `0`, disabled).

## 6) Quality Gates

Pass-1:
- `unresolved_count == 0` in pass-1 tree summary.
- Top/sub/leaf direction remains coherent.

Pass-2:
- Check `mapped_algorithm_subcluster_count` and `unresolved_algorithm_subcluster_count`.
- Verify `merged_tree_doc_count = pass1_tree_doc_count + mapped_algorithm_doc_count`.
- Inspect top-level additions and random leaf assignments.

## 7) Current Reference Run (April 2, 2026 UTC)

Reference artifacts:
- `pass1_ai_taxonomy_outlier_full_sota_v4_20260402_181846.json`
- `pass1_taxonomy_tree_directional_sota_v4_20260402_181852.json`
- `pass2_algorithm_merge_sota_v1_20260402_210324.json`
- `pass2_taxonomy_tree_full_view_20260402_210357.md`
- `pass2_taxonomy_tree_everything_20260402_211232.md`
- `pass2_taxonomy_sunburst_docs_20260402_210414.html`
- `pass2_taxonomy_icicle_docs_20260402_210414.html`

Key numbers from this run:
- pass-1 mapped categories: `208`
- pass-1 docs: `39,520`
- `needs_algorithm` groups: `42`
- `needs_algorithm` docs: `21,129`
- algorithm subclusters created: `65`
- mapped algorithm subclusters: `65`
- unresolved algorithm subclusters: `0`
- merged docs total: `60,649`
- merged leaf entries: `273`

## 8) What Must Not Change in This Flow

- Do not rerun pass-1 AI after pass-1 tree is accepted, unless explicitly requested.
- Do not mix unrelated new categories into pass-1 base before merge.
- Do not collapse parent-child direction in final tree.
- Do not drop algorithm assignment evidence (`source_cluster_id`, similarity, sample URLs).
