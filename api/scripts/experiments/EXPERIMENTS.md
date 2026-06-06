# Experiment Scripts

This folder contains two kinds of scripts:

- report-facing evaluation scripts that are still useful for the current paper;
- older RAG retrieval experiments kept as historical scaffolding.

Run paths are relative to the repository root unless noted.

## Current Report Checks

These scripts back the report metrics and can be rerun against the current
database/artifacts:

```bash
python3 api/scripts/experiments/eval_event_extraction.py
python3 api/scripts/experiments/eval_assignment_matching.py
python3 api/scripts/experiments/eval_submission_agent.py
```

Ground-truth builders and review helpers live beside them:

- `build_event_gt.py`
- `build_submission_gt.py`
- `human_validate.py`
- `_llm_judge.py`

`eval_submission_agent.py` may call an external judge depending on environment
configuration. For a no-network sanity check, compute metrics from
`api/data/ground_truth/submissions/results.jsonl`.

## Historical RAG Experiment 1: Chunking Quality Check

Test whether retrieval can find the right regulation rules under different
chunk sizes.

### What We're Testing
Different chunk sizes for university regulation documents: 100 words vs 200 words vs 300 words.

### How to Run
```bash
python3 api/scripts/experiments/experiment_chunk_quality.py
```

### What It Does
1. Re-chunks regulation documents with each size.
2. Asks questions where we know the correct answer (ground truth).
3. Checks if the retrieved chunks contain the correct answer.

### Success
Did we find the right chunk? Yes or No.

---

## Historical RAG Experiment 2: Embedding Quality / Factuality

Test whether course recommendation retrieval/generation invents courses that do
not exist.

### What We're Testing
Does the course recommendation system invent courses that don't exist?

### How to Run
```bash
python3 api/scripts/experiments/experiment_embedding_quality.py
```

### What It Does
1. Ask for course recommendations with known correct answers.
2. Compare AI's answer to ground truth.
3. Flag any hallucinations (invented course codes).

## Categorization Subfolder

`categorization/` contains the staged taxonomy experiments used to derive the
clean category tree referenced by the report. The latest clean run is indexed
under `api/scripts/experiments/results/categorization/`.
