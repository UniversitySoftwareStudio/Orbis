# Algorithm Specification

This file documents the exact current algorithm used in `api/scripts/experiments/categorization`.

## Scope
The active pipeline has four parts:
1. URL-first decisioning (fast, structure-based).
2. Pass-1 AI taxonomy for URL-resolved groups only.
3. Pass-2 algorithm merge for `needs_algorithm` groups only.
4. Tree/visual artifacts for full inspection.

Goal: classify source groups into:
- `url_only_parent`
- `url_only_categorize`
- `needs_algorithm`

## Data Sources
- URL-first stage reads `knowledge_base.id` and `knowledge_base.url`.
- Diversity stage also reads URLs from `knowledge_base`.
- Embedding stage writes to `embedding_models` and `knowledge_base_embeddings`.
- Clustering stage reads from `knowledge_base_embeddings` joined to `knowledge_base`.

---

## Stage 1: Umbrella Parent Builder
Script: `01_build_url_groups.py`

### 1.1 URL normalization and segmenting
For each URL:
- Extract host (`lowercase`).
- Split path into segments.
- Candidate parent key is `host/segment1/.../segmentD`.

### 1.2 Dynamic-segment detector
A segment is treated as dynamic if one of these is true:
- all digits
- date-like pattern (`YYYY-MM-DD` variants)
- long hex-like token
- UUID-like token
- length >= 5 and digit ratio >= 0.6

### 1.3 Dynamic depth selection (default mode)
For each URL, depth is chosen between `min_depth` and `max_depth`.

Depth selection logic:
1. Start from deepest allowed depth.
2. Back off while last segment is dynamic.
3. Back off until parent at that depth has at least `min_parent_docs` support.
4. Optional decider pass (`heuristic` or `ollama`) can stop earlier.

Heuristic deepen rule (`_decide_deepen`) at prefix depth `d`:
- `unique_semantic >= 2`
- `semantic_ratio >= 0.40`
- `dynamic_ratio <= 0.50`
- `dominant_share <= 0.80`
If all true -> `DEEPEN`, else `STOP`.

Ollama mode:
- Calls local Ollama for `DEEPEN` vs `STOP`.
- If model output fails, falls back to heuristic decision.

### 1.4 Parent clustering (URL-char similarity)
After parent keys are selected:
- Vectorize parent strings using character TF-IDF (`3-5` grams).
- Build radius neighbor graph with cosine distance radius `1 - similarity_threshold`.
- Connected components become parent clusters.

### 1.5 Output
JSON contains:
- `depth_results.dynamic.clusters[]`
- each cluster has `cluster_id`, `doc_count`, `representative_parent`, `parents[]`
- each parent has `parent_key`, `doc_count`, `doc_ids`, `chosen_depth`

---

## Stage 2: Tail-Diversity Classifier
Script: `02_classify_url_groups.py`

Input: Stage-1 dynamic output.

For each cluster, for each doc URL:
- Compute tail = segments after `chosen_depth`.
- Build counters and metrics from tail tokens.

### 2.1 Metrics used
- `no_tail_ratio`
- `dynamic_first_ratio`
- `semantic_first_ratio`
- `dynamic_tail_ratio`
- `semantic_tail_ratio`
- `numeric_only_tail_ratio`
- `all_dynamic_tail_doc_ratio`
- `semantic_tail_doc_ratio`
- `unique_tail_patterns`
- `tail_pattern_entropy`
- `dominant_tail_pattern_share`

Tail pattern normalization:
- dynamic token -> `<id>`
- embedded digits inside token -> `<n>` replacement

### 2.2 Exact decision rules (current)
Rule order is strict:

1. If `no_tail_ratio >= 0.90`:
- `decision = url_only_parent`
- `depth_signal = shallow_only`

2. Else if all of:
- `all_dynamic_tail_doc_ratio >= 0.80`
- `semantic_tail_doc_ratio <= 0.20`
Then:
- `decision = needs_algorithm`
- `depth_signal = numeric_only_tail_low_signal`

3. Else if all of:
- `dynamic_tail_ratio >= 0.70`
- `semantic_tail_ratio <= 0.30`
Then:
- `decision = needs_algorithm`
- `depth_signal = numeric_dominant_tail_low_signal`

4. Else if any of:
- `dominant_tail_pattern_share >= 0.60`
- `tail_pattern_entropy <= 1.20`
- `unique_tail_patterns <= 2`
Then:
- `decision = needs_algorithm`
- `depth_signal = too_similar_repetitive`

5. Else if all of:
- `semantic_tail_ratio >= 0.45`
- `semantic_tail_doc_ratio >= 0.45`
- `unique_tail_patterns >= 4`
- `tail_pattern_entropy >= 1.50`
- `dominant_tail_pattern_share <= 0.55`
Then:
- `decision = url_only_categorize`
- `depth_signal = diversified_semantic`

6. Else:
- `decision = needs_algorithm`
- `depth_signal = mixed`

### 2.3 Output
JSON contains:
- `summary` with counts per decision
- `groups[]` with metrics and final decision per cluster

---

## Stage 3: Shortlist View
Script: `03_build_shortlist.py`

Input: Stage-2 JSON.

Current behavior:
- Excludes only `url_only_categorize`.
- Keeps `needs_algorithm` and `url_only_parent` as candidates.

Priority assignment:
- `P1` if `doc_count >= p1_min_docs`
- `P2` otherwise

Sorting:
- P1 first, then P2
- inside priority: larger `doc_count` first

Top-N behavior:
- `top_n_groups` = first `N` rows from `P1` only
- no P2 backfill when P1 count < N

Optional:
- `--include-all-candidates` adds full candidate list to JSON.

---

## Stage 3.5: AI Taxonomy Refinement (URL-Resolved Only)
Scripts:
- `04_build_ai_input.py`
- `05_run_ai_mapping.py`

Purpose:
- Build stable taxonomy labels for URL-resolved groups before algorithm-only groups are attached.
- Keep structure intact; do not rewrite group identity.

### 3.5.1 Input selection
`04_build_ai_input.py` includes only:
- `url_only_parent`
- `url_only_categorize`

It excludes:
- `needs_algorithm`

### 3.5.2 Count gate
Before model calls:
- print `categories_for_ai_count`
- print excluded decisions (must include `needs_algorithm` at pass-1)

### 3.5.3 Ollama pass behavior
`05_run_ai_mapping.py`:
- Uses category evidence:
  - `representative_parent`
  - `path_hint`
  - `sample_urls`
  - host-level and global segment context from pass-1 set
- Requires one of fixed `top_level` options.
- Validates model output and grounding evidence terms.
- On weak/invalid output, forces `status = unresolved`.
- Supports `outlier` or `ollama` provider (`--llm-provider`).
- In current production flow, Outlier proxy + stronger model is preferred.
- Applies deterministic rule-first mapping for strongly signaled URL groups.

Safety:
- Full run requires explicit `--confirm-count`.
- Prevents accidental large run with wrong input.
- Prevents low-grounding labels from entering taxonomy.

### 3.5.4 Directional taxonomy tree artifact
Script: `06_build_tree.py`

Builds:
- `top_level -> sub_level -> canonical_label` tree
- per-leaf examples and doc counts

Pass-1 expectation:
- `unresolved_count = 0`
- no orphan category outside parent-child direction

---

## Stage 3.6: Algorithm Merge (Needs-Only, No Pass-1 Rerun)
Script:
- `07_merge_algorithm_groups.py`

Purpose:
- Keep pass-1 taxonomy tree as stable base.
- Process only `needs_algorithm` groups.
- Attach algorithm-produced subclusters into existing tree leaves.

### 3.6.1 Inputs
- Depth decisions JSON (`02_classify_url_groups.py` output)
- Umbrella cluster JSON (`01_build_url_groups.py` output)
- Pass-1 AI taxonomy JSON (`05_run_ai_mapping.py` output)
- Pass-1 taxonomy tree JSON (`06_build_tree.py` output)
- Embeddings from `knowledge_base_embeddings` (selected model id)

### 3.6.2 Reference centroid build
From pass-1 mapped groups:
1. Map each pass-1 `cluster_id` to taxonomy leaf (`top_level/sub_level/canonical_label`).
2. Expand cluster to document ids from umbrella output (optionally capped per cluster with `--reference-docs-per-pass1-cluster`).
3. Compute normalized centroid per taxonomy leaf in embedding space.

### 3.6.3 Needs-group clustering
For each `needs_algorithm` source group:
1. Read doc embeddings for that group.
2. Choose local `k` adaptively (bounded by `max_subclusters`, `min_docs_to_split`, `min_subcluster_size`).
3. Optional PaCMAP reduction (`--pacmap-dim`) before MiniBatchKMeans.
4. Produce subclusters + centroid per subcluster.

### 3.6.4 Merge mapping
For each algorithm subcluster:
1. Compute cosine similarity to all pass-1 leaf centroids.
2. If best similarity >= `min_similarity`:
- map subcluster under that existing taxonomy leaf
- increment leaf/top/sub counts
- store algorithm metadata (`source_cluster_id`, local subcluster id, doc count, similarity, sample URLs)
3. Else:
- mark unresolved
- optionally attach under `unknown/algorithm_unresolved`

### 3.6.5 Embedding fetch strategy
The merge script supports two DB fetch paths:
1. Chunked ID fetch (default):
- fetch only requested UUID ids in chunks (`--db-chunk-size`, default `2000`)
- uses UUID typed predicate (`kbe.kb_id IN :ids`) for index use
2. Optional full-model scan:
- enabled only if `--fetch-all-model-if-ids-ge > 0` and id count crosses threshold
- reads all model rows once and filters in-memory

### 3.6.6 Outputs
- Merged taxonomy JSON (tree + assignment details)
- Markdown summary:
  - mapped vs unresolved algorithm subclusters
  - added docs per top-level taxonomy

Output structure includes:
- `summary`
- `algorithm_assignments[]`
- `unresolved_algorithm_assignments[]`
- `tree` (same directional structure, enriched with `algorithm_clusters[]` under leaves)

---

## Stage 3.7: Full Tree Exports (Everything View)
Source: pass-2 merged JSON from Stage 3.6.

Purpose:
- Provide a full parent-child tree view for manual audit and presentation.
- Include every level and all algorithm children under leaves.

Typical exported files:
- `pass2_taxonomy_tree_full_view_*.md`
- `pass2_taxonomy_tree_everything_*.md`
- `pass2_taxonomy_tree_everything_*.txt`

The “everything” tree includes:
- top/sub/leaf node counts
- pass-1 cluster children
- algorithm children (`source_cluster_id`, `subcluster_local_id`, `doc_count`, `similarity`, `sample_urls`)

---

## Stage 3.8: Visual Artifacts
Script:
- `08_build_visuals.py`

Also for final merged tree:
- interactive sunburst (`pass2_taxonomy_sunburst_docs_*.html`)
- interactive icicle (`pass2_taxonomy_icicle_docs_*.html`)

## Stage 4A: Embedding Generator
Script: `20_build_embeddings_optional.py`

### 4A.1 Sampling
- Random sample from `knowledge_base` with non-empty content.
- Optional language/type filters.

### 4A.2 Text built for embedding
Per row text is assembled from:
- title
- filtered metadata (excluding configurable keys; default excludes `category,parent_category,breadcrumbs`)
- type
- language
- content (optionally truncated)

### 4A.3 Embedding model
- `jinaai/jina-embeddings-v3`
- configurable task adapter (default `separation`)
- optional truncation dimension (Matryoshka)
- optional L2 normalization (default enabled)

### 4A.4 Writes
- Upserts model info into `embedding_models`.
- Upserts vectors into `knowledge_base_embeddings (kb_id, model_id)`.
- Optional local artifacts: manifest, `.npy`, ids.

---

## Stage 4B: PaCMAP Hierarchical Clustering (Subset)
Script: `21_cluster_subset_optional.py`

Algorithm:
1. Load sampled embeddings for selected model.
2. Optional cleaning:
- drop exact duplicate vectors
- cap repeated normalized titles
3. Reduce vectors with PaCMAP.
4. Build Ward hierarchical linkage on reduced vectors.
5. Cut tree at requested levels (`k` list).
6. Compute silhouette per level.

Outputs:
- `*.assignments.jsonl` with `cluster_k{level}` labels per document
- `*.summary.json` with run metadata and silhouette scores

---

## Stage 4C: Scalable Hierarchical Clustering (All Data)
Script: `22_cluster_all_optional.py`

Approximation strategy:
1. Fit MiniBatchKMeans on document vectors (`leaf_k`, default 64).
2. Run Ward hierarchy on leaf centroids (optionally PaCMAP-reduced centroids).
3. Cut centroid tree at requested levels.
4. Project centroid labels back to documents.

Optional strict URL-first mode:
- Partition rows by URL bucket first (`host`, `host_path1`, or `full`).
- Cluster inside each bucket independently.
- Prevents cross-bucket mixing by design.

Outputs:
- `*.assignments.jsonl`
- `*.summary.json` (centroid-level and sampled doc-level silhouette metrics)

---

## How Decisions Connect to Regulatory Extraction
For regulation extraction workflow:
- `url_only_parent`: treat as fixed leaf group.
- `url_only_categorize`: URL path is enough for semantic grouping.
- `needs_algorithm`: send to embedding/clustering stage, then select regulation-relevant subclusters/docs.

This keeps URL rules as first-pass gate and uses vector methods only where URL structure is not semantically reliable.
