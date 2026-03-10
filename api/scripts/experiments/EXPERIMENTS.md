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