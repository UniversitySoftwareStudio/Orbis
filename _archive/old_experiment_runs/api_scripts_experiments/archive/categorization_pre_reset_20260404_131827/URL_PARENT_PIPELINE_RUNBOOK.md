# URL + Algorithm Pipeline (Minimal)

## Micro Flow
1. Build umbrella parents (dynamic depth 2..3).
2. Score each parent with full-tail diversity.
3. Split decisions:
   - `url_only_parent`
   - `url_only_categorize`
   - `needs_algorithm`
4. Build AI taxonomy input from URL-resolved groups only and check count.
5. Run context-aware Ollama taxonomy pass for URL-resolved groups.
6. Build pass-1 directional tree.
7. Run pass-2 algorithm merge for `needs_algorithm` (no pass-1 AI rerun).
8. Export full tree views and visuals.

## Use One Entrypoint
```bash
python3 -u api/scripts/experiments/categorization/00_run_flow.py list
```
Use stage ids/names instead of memorizing many script files.

## Clean Directory Output (Recommended)
After any run, create a clean stage-ordered folder:
```bash
python3 -u api/scripts/experiments/categorization/00_run_flow.py 90 -- \
  --run-name url_parent_flow \
  --update-latest-link \
  --archive-source-files
```

Result:
- one run folder under `api/scripts/experiments/results/categorization/runs/`
- numbered stage files with key metrics in file names
- `FLOW.md` summary so directory intent is obvious without opening raw JSON

## One-Time Clean Run
```bash
find api/scripts/experiments/results/categorization -mindepth 1 -maxdepth 1 -type f -delete

python3 -u api/scripts/experiments/categorization/01_build_url_groups.py \
  --sample-size 0 --dynamic-depth --min-depth 2 --max-depth 3 \
  --min-parent-docs 6 --similarity-threshold 0.85 \
  --run-name clean_url_umbrella_parents_dynamic_d23

python3 -u api/scripts/experiments/categorization/02_classify_url_groups.py \
  --input-json api/scripts/experiments/results/categorization/clean_url_umbrella_parents_dynamic_d23_*.json \
  --run-name clean_url_parent_depth_diversity_d23_fulltail

python3 -u api/scripts/experiments/categorization/03_build_shortlist.py \
  --input-json api/scripts/experiments/results/categorization/clean_url_parent_depth_diversity_d23_fulltail_*.json \
  --top-n 3 --p1-min-docs 20 \
  --run-name clean_url_parent_shortlist_d23

python3 -u api/scripts/experiments/categorization/04_build_ai_input.py \
  --depth-json api/scripts/experiments/results/categorization/clean_url_parent_depth_diversity_d23_fulltail_*.json \
  --umbrella-json api/scripts/experiments/results/categorization/clean_url_umbrella_parents_dynamic_d23_*.json \
  --include-decisions url_only_parent,url_only_categorize \
  --sample-urls-per-category 3 \
  --run-name clean_ai_taxonomy_pass1_input
```

Before any AI call, check:
- `categories_for_ai_count`
- `excluded_by_decision.needs_algorithm` (must be excluded at pass-1)

## AI Taxonomy Pass (Context-Aware LLM)

Start Outlier proxy first (if you want Outlier models):
```bash
cd standard-ui
./outlier-up.sh
```

### 1) Count gate only (no model calls)
```bash
python3 -u api/scripts/experiments/categorization/05_run_ai_mapping.py \
  --llm-provider outlier \
  --outlier-url http://127.0.0.1:8080 \
  --input-json api/scripts/experiments/results/categorization/clean_ai_taxonomy_pass1_input_*.json \
  --ollama-model qwen:4b \
  --dry-run-count
```

### 2) Small sanity run
```bash
python3 -u api/scripts/experiments/categorization/05_run_ai_mapping.py \
  --llm-provider outlier \
  --outlier-url http://127.0.0.1:8080 \
  --input-json api/scripts/experiments/results/categorization/clean_ai_taxonomy_pass1_input_*.json \
  --ollama-model claude-opus-4-6 \
  --max-categories 8 \
  --run-name clean_ai_taxonomy_pass1_ollama_small
```

### 3) Full run (requires explicit count confirm)
```bash
python3 -u api/scripts/experiments/categorization/05_run_ai_mapping.py \
  --llm-provider outlier \
  --outlier-url http://127.0.0.1:8080 \
  --input-json api/scripts/experiments/results/categorization/clean_ai_taxonomy_pass1_input_*.json \
  --ollama-model claude-opus-4-6 \
  --confirm-count <COUNT_FROM_GATE> \
  --run-name clean_ai_taxonomy_pass1_ollama_full
```

Notes:
- Script preserves source structure and only labels existing URL-resolved groups.
- Default is rule-first directional mapping (stable parent-child).
- If model output is weak or ungrounded, row is forced to `status=unresolved`.
- `needs_algorithm` groups remain excluded in pass-1 by design.
- Use `--ai-on-rule-matches` only if you explicitly want model re-interpretation on already rule-mapped groups.

## Build Directional Taxonomy Tree

```bash
python3 -u api/scripts/experiments/categorization/06_build_tree.py \
  --input-json api/scripts/experiments/results/categorization/clean_ai_taxonomy_pass1_ollama_full_*.json \
  --run-name clean_taxonomy_tree_directional
```

Checks:
- `summary.unresolved_count` should be `0` for pass-1.
- Tree must be coherent as `top_level -> sub_level -> canonical_label`.

## Merge `needs_algorithm` Into Existing Taxonomy (No Pass-1 Rerun)

```bash
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

Notes:
- This script keeps pass-1 taxonomy fixed as the base.
- Only `needs_algorithm` groups are clustered and merged.
- Mapping is vector-based (nearest existing taxonomy leaf).
- No pass-1 AI rerun is required.
- Performance knobs for large runs:
  - `--reference-docs-per-pass1-cluster` (default `80`) controls centroid reference size.
  - `--db-chunk-size` (default `2000`) controls embedding fetch batch size.
  - `--fetch-all-model-if-ids-ge` (default `0`) disables full-model scan unless explicitly set.

## Full Tree Export (Everything)

Use merged JSON as source and render full tree with all parent-child relations:
```bash
python3 - <<'PY'
import json
from pathlib import Path
from datetime import datetime, timezone

base = Path("api/scripts/experiments/results/categorization")
src = sorted(base.glob("clean_pass2_algorithm_merge_*.json"))[-1]
payload = json.loads(src.read_text())
tree = payload["tree"]
summary = payload["summary"]

stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
out_md = base / f"clean_pass2_taxonomy_tree_everything_{stamp}.md"
out_txt = base / f"clean_pass2_taxonomy_tree_everything_{stamp}.txt"

lines = []
lines.append("# Full Taxonomy Tree (Everything)")
lines.append("")
lines.append(f"- source: `{src}`")
lines.append(f"- total_docs: `{sum(int(v.get('doc_count',0)) for v in tree.values())}`")
lines.append(f"- top_levels: `{len(tree)}`")
lines.append(f"- merged_leaf_entries: `{summary.get('merged_tree_category_count', 0)}`")
lines.append(f"- algorithm_subclusters: `{summary.get('algorithm_subcluster_count', 0)}`")
lines.append("")

for top, top_node in sorted(tree.items(), key=lambda kv: (-int(kv[1].get("doc_count",0)), kv[0])):
    lines.append(f"{top} (docs={int(top_node.get('doc_count',0))}, leaf_entries={int(top_node.get('category_count',0))})")
    for sub, sub_node in sorted(top_node.get("sub_levels", {}).items(), key=lambda kv: (-int(kv[1].get("doc_count",0)), kv[0])):
        lines.append(f"  ├─ {sub} (docs={int(sub_node.get('doc_count',0))}, leaf_entries={int(sub_node.get('category_count',0))})")
        for leaf, leaf_node in sorted(sub_node.get("leaves", {}).items(), key=lambda kv: (-int(kv[1].get("doc_count",0)), kv[0])):
            lines.append(
                "  │  ├─ "
                + f"{leaf} (docs={int(leaf_node.get('doc_count',0))}, "
                + f"leaf_entries={int(leaf_node.get('category_count',0))}, "
                + f"pass1_clusters={len(leaf_node.get('clusters',[]))}, "
                + f"algo_subclusters={len(leaf_node.get('algorithm_clusters',[]))})"
            )
    lines.append("")

text = "\n".join(lines)
out_md.write_text(text, encoding="utf-8")
out_txt.write_text(text, encoding="utf-8")
print(out_md)
print(out_txt)
PY
```

Optional detailed leaf audit:
- Read `algorithm_clusters` per leaf in merged JSON to inspect every algorithm child (`source_cluster_id`, `subcluster_local_id`, `doc_count`, `similarity`, `sample_urls`).

## Visualization Pack (Per Step + Literature Framing)

```bash
python3 -u api/scripts/experiments/categorization/08_build_visuals.py \
  --run-name clean_pipeline_visual_pack
```

Outputs:
- PNG charts for step-1 through step-5
- `visualization_metrics_*.json`
- `visualization_report_*.md` (includes method-to-literature mapping)
- For final merged tree, also generate:
  - `pass2_taxonomy_sunburst_docs_*.html`
  - `pass2_taxonomy_icicle_docs_*.html`

## Algorithm Stage (Bring Back PaCMAP)

### 1) Create/refresh embeddings (start small)
```bash
python3 -u api/scripts/experiments/categorization/20_build_embeddings_optional.py \
  --sample-size 4000 \
  --seed 42 \
  --task separation \
  --truncate-dim 512 \
  --batch-size 16 \
  --set-active \
  --run-name clean_jina_v3_embed_subset
```

### 2) PaCMAP hierarchical clustering (subset)
```bash
python3 -u api/scripts/experiments/categorization/21_cluster_subset_optional.py \
  --sample-size 4000 \
  --levels 8,24,64 \
  --pacmap-dim 30 \
  --seed 42 \
  --run-name clean_jina_v3_hierarchical
```

### 3) Scalable clustering (all rows for a model)
```bash
python3 -u api/scripts/experiments/categorization/22_cluster_all_optional.py \
  --model-id <MODEL_ID> \
  --sample-size 0 \
  --levels 8,24,64 \
  --leaf-k 64 \
  --run-name clean_jina_v3_hierarchical_all
```

## Scripts
- `01_build_url_groups.py`: dynamic parent extraction + URL-char clustering
- `02_classify_url_groups.py`: full-tail diversity scoring
- `03_build_shortlist.py`: decision view + shortlist
- `04_build_ai_input.py`: pass-1 AI input + category count gate
- `05_run_ai_mapping.py`: context-aware taxonomy refinement (Ollama)
- `06_build_tree.py`: directional tree artifact with examples
- `07_merge_algorithm_groups.py`: pass-2 algorithm subclustering + merge into pass-1 tree
- `08_build_visuals.py`: presentation visuals + method framing
- `20_build_embeddings_optional.py`: embedding generation + DB upsert
- `21_cluster_subset_optional.py`: PaCMAP + Ward hierarchical clustering
- `22_cluster_all_optional.py`: scalable all-data clustering
