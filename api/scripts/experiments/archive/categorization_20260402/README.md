# Categorization Experiments

## Local Jina v3 Embedding (No Container)

Script:
- `api/scripts/experiments/categorization/jina_v3_embed_kb.py`

What it does:
- Loads `jinaai/jina-embeddings-v3` locally via `sentence-transformers` (`trust_remote_code=True`).
- Uses task adapter `separation` by default (good for clustering).
- Samples random rows from `knowledge_base` for quick experiments.
- Registers/updates model metadata in `embedding_models`.
- Upserts vectors into `knowledge_base_embeddings`.
- Saves experiment artifacts (`.manifest.json`, `.embeddings.npy`, `.ids.json`).

### Quick Start
```bash
python3 api/scripts/experiments/categorization/jina_v3_embed_kb.py \
  --sample-size 500 \
  --seed 42 \
  --task separation \
  --truncate-dim 512 \
  --batch-size 16
```

### Useful Options
- `--language tr,en` filter by `knowledge_base.language`
- `--type pdf,web_page` filter by `knowledge_base.type`
- `--content-chars 2400` truncate per-row content before embedding
- `--truncate-dim 32|64|128|256|512|1024` Matryoshka dimension cut
- `--set-active` marks this model active in `embedding_models`
- `--register-only` only register model, skip embedding writes

### Notes
- The model is large (570M). First run downloads weights and can take time.
- Use small subsets first (`--sample-size 100..1000`) for quality checks.

## Hierarchical Clustering Run

Script:
- `api/scripts/experiments/categorization/jina_v3_cluster_kb.py`

Example:
```bash
python3 api/scripts/experiments/categorization/jina_v3_cluster_kb.py \
  --model-id 6 \
  --sample-size 4000 \
  --levels 8,24,64 \
  --pacmap-dim 30 \
  --seed 42
```

Output:
- `*.assignments.jsonl` document-level cluster assignments for each depth.
- `*.summary.json` run metadata + silhouette scores.
