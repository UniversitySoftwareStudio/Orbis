# RAG System Experiments

## Experiment 1: Chunking Quality Check
**Test if we can find the right regulation rules.**

### What We're Testing
Different chunk sizes for university regulation documents: 100 words vs 200 words vs 300 words.

### How to Run
```bash
python3 api/experiments/run_experiment_1_chunking_quality.py
```

### What It Does
1. Re-chunks regulation documents with each size.
2. Asks questions where we know the correct answer (ground truth).
3. Checks if the retrieved chunks contain the correct answer.

### Success
Did we find the right chunk? Yes or No.

---

## Experiment 2: Factuality Check
**Test if the AI makes up fake courses in recommendations.**

### What We're Testing
Does the course recommendation system invent courses that don't exist?

### How to Run
```bash
python3 api/experiments/run_experiment_2_factuality_check.py
```

### What It Does
1. Ask for course recommendations with known correct answers.
2. Compare AI's answer to ground truth.
3. Flag any hallucinations (invented course codes).

---

## Experiment 3: Local Jina v3 Categorization Embeddings
**Generate multilingual embeddings without containerized embedding service.**

### What We're Testing
- `jinaai/jina-embeddings-v3` with task adapter `separation` for clustering/categorization quality.
- Fast random subset runs to iterate quickly.
- Optional Matryoshka dimension truncation (`--truncate-dim`).

### How to Run
```bash
python3 api/scripts/experiments/categorization/jina_v3_embed_kb.py \
  --sample-size 500 \
  --seed 42 \
  --task separation \
  --truncate-dim 512
```

### What It Does
1. Randomly samples documents from `knowledge_base`.
2. Embeds them locally with Jina v3.
3. Upserts vectors into `knowledge_base_embeddings`.
4. Registers model metadata in `embedding_models`.
5. Saves `.manifest.json`, `.embeddings.npy`, and `.ids.json` artifacts.
