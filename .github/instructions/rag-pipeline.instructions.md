# RAG Pipeline — Detailed Instructions

Applies to: `api/services/rag_service.py`, `api/database/repositories/rag_repository.py`

This file documents how the production RAG pipeline works, why it is structured the way it is,
and what must not be changed without understanding the consequences.

---

## Pipeline Overview (End to End)

```
User Query
    │
    ▼
[1] Router Agent (LLM call)
    → Produces a list of "intents", each with tool=vector or tool=sql
    │
    ▼
[2] For each intent → _process_single_intent()
    │
    ├─ SQL path → rag_repository.sql_filter() → exact course/code lookup
    │
    └─ Vector path:
           │
           ▼
        [2a] Hybrid Search (vector_search in rag_repository)
             → Vector similarity (semantic) + TSVector keyword search
             → Merge: keyword results first, then vector results (deduplicated)
           │
           ▼
        [2b] Pre-Expansion Rerank
             → Jina AI reranks the full hybrid pool
             → Identifies "True Top 3" most relevant documents
           │
           ▼
        [2c] Smart Context Expansion
             → For each of the True Top 3: fetch ALL chunks from the same source URL
             → Reconstructs the full document context around the best hits
           │
           ▼
        [2d] Final Rerank
             → Jina AI reranks the expanded candidate pool
             → Returns top 10 (or top 5 if parallel intent)
    │
    ▼
[3] Deduplicate across all intents
    │
    ▼
[4] Context Building
    → If SQL list or >40 docs: compact to CSV format
    → Otherwise: detailed text blocks with Title, URL, Content, Metadata
    │
    ▼
[5] LLM Generation (streaming)
    → System prompt enforces citation protocol and administrative safety rules
    → Response streams back to frontend via SSE
```

---

## Why Two Rerank Steps (Not One)

This is the most important architectural decision in the pipeline.

**The problem with single reranking:** If you rerank after expansion, you're reranking a large pool
of chunks that includes many irrelevant neighbors. The reranker has no way to tell which source
documents were actually relevant before expansion.

**The solution — two stages:**

- **Stage 1 (Pre-Expansion Rerank):** Takes the raw hybrid search results (e.g. 30 docs) and reranks
  them to find the "True Top 3" — the documents that are actually most relevant to the query.
  This is a quality filter *before* we spend time expanding.

- **Stage 2 (Final Rerank):** After expansion, we have a large pool of chunks from the expanded sources
  plus the top 10 from the initial results. The final rerank finds the best chunks within this
  enriched context to feed to the LLM.

**Do not collapse these into one rerank.** If you expand first and then rerank, you lose the ability
to identify which source documents are truly relevant — the expansion noise will suppress them.

---

## Router Agent Rules

The router is an LLM call that converts the user query into a list of "intents".
The rules are enforced via the system prompt but must be understood here too.

### When to use SQL
- User asks for a **specific course code**: `"CMPE 351"`, `"ACC"`, `"SOC"`
- User asks to **list courses in a department**: `"List all engineering courses"`
- SQL filters: `{ "code": "CMPE" }` or `{ "type": "course" }`

### When to use Vector (everything else)
- Questions about regulations, rules, procedures: `"How do I apply for Erasmus?"`
- Conceptual queries: `"What is the internship policy?"` (Staj)
- Factual questions about the university: `"Where is the student affairs office?"`
- Even if the answer might be in a course-related document — use Vector, not SQL

**Critical rule:** Generic topic searches must go to Vector, not SQL.
The word "Staj" (internship) is a perfect example — SQL title search would return
hundreds of irrelevant results, while vector search finds the actual regulation documents.

### Auto-repair logic (in `_process_single_intent`)
The router sometimes makes mistakes. The code contains auto-repair logic:
- If the router picks SQL with `type='course'` but provides no `code` filter and the query is short
  (< 10 chars), move the query string into the `code` filter
- If SQL has no filters at all, fall back to Vector to avoid a full DB dump
- If SQL returns 0 results, fall back to Vector
- If `code` is present in filters, force `type='course'` to prevent irrelevant type matches

---

## Hybrid Search (rag_repository.py)

The `vector_search` method performs true hybrid retrieval and merges results.

### Vector path
Uses `l2_distance` (L2/Euclidean distance), not cosine distance.
This is intentional — L2 works well for the MiniLM model used and was the working implementation.
Do not switch to cosine without re-evaluating retrieval quality.

### Keyword path (TSVector)
Uses `to_tsquery` with OR logic (`|` operator).
Words shorter than 3 characters are filtered out.
This handles long sentences by catching any key term (e.g., "Staj" in a long Turkish sentence).

### Merge order
**Keyword results go first, then vector results.**
This is intentional: keyword matches are high-precision (exact term found), so they get priority.
Vector results fill in the remaining slots for semantic coverage.
Deduplication is by `id` — a document that appears in both lists only appears once (in the keyword position).

---

## Smart Context Expansion

After the pre-expansion rerank identifies the True Top 3:

1. Collect the unique source URLs from those 3 documents (only for `type='web_page'` and `type='pdf'`)
2. For each URL, call `rag_repository.get_by_url()` to fetch ALL chunks from that source
3. Add them to the candidate pool alongside the top 10 from the initial reranked results

**Why this matters:** The `KnowledgeBase` table stores chunks (~150 words each), not full documents.
A relevant regulation article might span 5–10 chunks. If only chunk 3 is retrieved by search,
the LLM lacks the article's beginning and conclusion. Expansion reconstructs the full document.

**The `RERANK_INPUT_CAP = 75` limit:**
If expansion produces more than 75 candidates, we cap it.
Priority slots are given to the 3 expansion-trigger documents first, then remaining slots fill from others.
This prevents the final reranker from being overwhelmed by a very long document.

---

## Context Building

Two modes depending on result shape:

### CSV mode (activated when)
- The primary intent was SQL-based AND there are more than 5 results, OR
- There are more than 40 documents total (vector result overflow)

CSV format is used because feeding 40+ full text blocks to the LLM would exceed the context window
and cause the LLM to hallucinate summaries. The LLM prompt instructs it to present CSV data as
a formatted list.

### Detailed mode (default)
Each document becomes a text block:
```
Source: {title}
URL: {url}
Content: {content}
Attributes: {metadata key-value pairs}
```

The URL is explicitly labeled so the LLM can generate proper Markdown citation links.

---

## LLM Prompt and Citation Rules

The final prompt enforces these rules (do not soften them when modifying the prompt):

1. **Bold for entities** (offices, roles, departments): `**Erasmus Office**` — never linked
2. **Markdown link on the document title** (not on the entity): `[Study Mobility Guide](url)`
3. **No invented citations** — if a URL is not in context, do not fabricate one
4. **Administrative safety** — when the answer involves a procedure, identify the responsible
   office from the context and advise contacting them
5. **Answer only from context** — no hallucination beyond what the retrieved documents say

---

## Parallel Intents

When the router returns multiple intents (e.g., comparing two departments), they are processed
sequentially in a loop. Each intent runs `_process_single_intent()` with `is_parallel=True`,
which reduces the search limit (15 instead of 30) and the final rerank top-k (5 instead of 10)
to conserve context window space across the merged result.

---

## What This Pipeline Is NOT

- **Not stateful** — no conversation history is kept. Each query is independent. This is intentional
  to prevent context bloat and token overflow. Do not add history.
- **Not a simple RAG** — "just embed, search, generate" is not how this works. The double rerank
  and expansion are load-bearing components, not optional optimizations.
- **Not using `regulation_service.py`** — that service is a simpler, older search used only for
  the experiments in `api/experiments/`. The production `/api/chat` endpoint uses `rag_service.py`.

---

## Key File References

| File | Role |
|------|------|
| `api/services/rag_service.py` | Full pipeline: router, intent processing, context building, generation |
| `api/database/repositories/rag_repository.py` | DB queries: hybrid search, SQL filter, URL fetch |
| `api/services/reranker_service.py` | Jina AI reranker wrapper with fallback |
| `api/services/embedding_service.py` | TEI / Ollama provider with round-robin and 413 backoff |
| `api/services/llm_service.py` | Groq / Gemini streaming wrapper |
| `api/routes/search.py` | `/api/chat` and `/api/search` endpoints |