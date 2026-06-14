# Q&A Backup — facts NOT on slides but ready to defend

The email gives only two Results slides (~135s total), so not every measured
experiment fits. These are kept here to answer "depth" questions live without
crowding the deck.

## Embedding / chunking benchmark (why MiniLM, why this chunk size)

- Isolated the dense-retrieval layer on Orbis regulation Q&A pairs.
- Metric: is the expected chunk in the top-3 retrieved? + MRR.

| Runtime | Chunk | Top-3 acc. | MRR |
|---|---|---|---|
| TEI all-MiniLM | 100w | **70.8%** | 0.565 |
| Ollama nomic-embed-text | 100w | 68.9% | **0.571** |
| TEI all-MiniLM | 150w | 68.0% | 0.552 |
| Ollama nomic-embed-text | 150w | 67.8% | 0.560 |

- **Takeaway to say out loud:** 100-word chunks beat 150-word for exact-rule
  retrieval; longer chunks keep topic vocabulary but dilute the specific rule
  signal. This justified the local MiniLM default and motivated hybrid search +
  rerank + Smart Context Expansion (embeddings alone top out ~71%).

## Submission ablation (if asked "did your design actually help?")

- V1 single-call reviewer → V2 two-call agentic reviewer.
- Accuracy 0.781 → 0.938; in-document injection resistance 1/4 → 4/4.
- Why: the two-call agent explicitly verifies each requirement, so embedded
  "approve me" instructions are bypassed instead of obeyed.

## Other likely Q&A facts

- Full pipeline ran 80 sources in **59 minutes**.
- Matching weakness root causes: broad-scope obligations assigned to everyone
  (false positives); situational rules under-matched (false negatives).
- Submission residual weakness: 2/4 partial drafts over-approved → motivates an
  explicit flag-for-review output class.
- Ground truth: authors manually labeled 323 candidates + 712 profile-obligation
  pairs; submission cases deterministically generated (N=32, synthetic).
