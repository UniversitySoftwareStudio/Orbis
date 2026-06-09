# Orbis URL Categorization — Experiment History

Istanbul Bilgi University · Orbis RAG Platform  
Student project by two undergraduate students.

Updated context: the final report uses the April 4-5 taxonomy-clean run and the
regulation overlay that identifies 935 regulation chunks. Older runs are
historical design evidence and should stay archived rather than be treated as
runtime code.

---

## The Starting Point

```
knowledge_base table
60,649 document chunks
from 80+ source URLs
─────────────────────
url  │ title │ content
─────────────────────
bilgi.edu.tr/en/academics/...
bilgi.edu.tr/tr/ogrenci/...
bilgi.edu.tr/mevzuat/...
...all flat, no category, no topic
```

The RAG pipeline had no way to restrict retrieval by topic. Regulation queries would surface event
announcements. Student-life content would pollute regulation search. The goal: assign every URL to a
leaf node in a taxonomy, and specifically surface the 935 regulation-document chunks for the event
extraction pipeline.

---

## Epoch 1 — April 2, 2026

### The Plan

```
60,649 docs
    │
    ▼
Parse every URL into (host, path_segments)
Sweep depths 1, 2, 3 — find parent prefixes
    │
    ├─ strong signal  → ACCEPT as parent group
    ├─ weak signal    → REJECT
    └─ ambiguous      → ask LLM (Ollama qwen:4b)
    │
    ▼
250 parent groups
143 URL-obvious → go straight to AI labeling
 65 need AI classification
 42 need embedding clustering  ← problem lives here
    │
    ▼
MiniBatchKMeans on 42 opaque groups
Map each subcluster to nearest Pass 1 centroid
    │
    ▼
302 categories, 60,649 docs covered
```

What "strong" and "weak" meant in the rule engine:

```
For each candidate parent prefix at depth d:

  semantic_ratio = (child segments with letters, not {tr,en,www}, not IDs)
                   ─────────────────────────────────────────────────────
                   total child segments

  dynamic_ratio  = (child segments matching: all-digits │ date │ hex │ UUID │ 60%+ digit density)
                   ─────────────────────────────────────────────────────────────────────────────
                   total child segments

  STRONG  →  doc_count ≥ 25
         AND distinct_children ≥ 3
         AND semantic_ratio ≥ 0.40
         AND dynamic_ratio ≤ 0.55
         → ACCEPT immediately, no LLM needed

  WEAK    →  doc_count < 5
         OR  distinct_children < 2
         OR  (semantic_ratio ≤ 0.15 AND dynamic_ratio ≥ 0.80)
         → REJECT immediately

  MIDDLE  →  everything else
         → call LLM, ask: PARENT or NOT_PARENT?
```

Parent connectivity constraint: a depth-3 prefix was only considered if its depth-2 parent was already accepted.

### What Broke

```
42 opaque groups (21,129 docs) → MiniBatchKMeans
                                        │
                        centroids built from Pass 1 clusters
                                        │
                    ┌───────────────────┴──────────────────────┐
                    │                                          │
             4,013 docs used                          35,507 docs MISSING
          to build centroids                       (not embedded at this point)
                    │
                    ▼
         centroids unrepresentative of
         the actual opaque documents
                    │
                    ▼
         94 subclusters mapped by
         "nearest-seen-doc" not true similarity
                    │
                    ▼
      302 flat categories — no depth structure
      no quality check, no deduplication
      /en/academics/ and /tr/akademik/ = 2 separate leaves
```

**Decision: full reset April 4. Archive everything. Rebuild with a different architecture.**

---

## Epoch 2 — April 4–5, 2026

### The New Architecture

The core idea was to split the problem. Some URL groups are *interpretable by URL structure* — the path
segments tell you what the content is. Others have opaque URLs (IDs, hashes, repetitive slugs) — for
those, you have to look at the content itself. Route them differently from the start.

```
60,649 docs in knowledge_base
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 01 · 01_group_parent_urls.py                          │
│  Scan all URLs at depths 1, 2, 3                            │
│  Rule engine: strong → accept, weak → reject, middle → LLM  │
│  New: large-group override (≥1000 docs + semantic path)      │
│  Result: 105 parent groups                                   │
│          1,993 candidates evaluated · 0 AI calls needed      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
                    105 parent groups
            (each group = set of doc IDs under
             one accepted URL prefix)
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 02 · 02_classify_unknowns.py                          │
│  For each group, analyze the URL "tail" beyond parent depth  │
│  Compute 5 tail metrics per group                            │
│  Decision: is this group's structure already interpretable?  │
└──────────────────────────┬──────────────────────────────────┘
                           │
               ┌───────────┴───────────┐
               │                       │
               ▼                       ▼
         74 KNOWN groups          31 UNKNOWN groups
         39,325 docs              21,324 docs
         (URL tells the story)    (URL is opaque)
               │                       │
               │                       ▼
               │        ┌──────────────────────────────────────┐
               │        │  STEP 03 · 03_discover_categories.py  │
               │        │  Fetch embeddings for all 21,324 docs │
               │        │  L2-normalize vectors                  │
               │        │  MiniBatchKMeans → 52 leaf clusters   │
               │        │  Ward HAC on centroids → 3 cut levels │
               │        │  Label each cluster: TF-IDF + URLs     │
               │        └──────────────────┬───────────────────┘
               │                           │
               │                    52 discovered clusters
               │                    (fine level, labeled by content)
               │                           │
               └───────────┬───────────────┘
                           │
                           ▼ 74 known + 52 discovered = 126 inputs
┌─────────────────────────────────────────────────────────────┐
│  STEP 04 · 04_build_taxonomy_tree.py                        │
│  A) Bilingual dedup: merge /en/ and /tr/ twins → 71 groups   │
│  B) Reclassify /upload/ paths by content not location        │
│  C) AI taxonomy: claude-opus-4-6, 12 calls, 0 errors        │
│     Closed vocab: 12 top-category terms                      │
│  D) Quality score every leaf: specificity + coverage + size  │
│  Result: 96 leaves, avg quality 0.873, 100% AI-mapped        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
                    Refined taxonomy tree
                    (05_refactor_tree.py cleans edges)
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 12 · 12_cluster_regulations.py                        │
│  SQL regex selects regulation-domain URLs                    │
│  935 regulation chunks → separate clustering pass            │
│  TF-IDF labels → 29 regulation leaf nodes                   │
│  Overlay onto taxonomy under `regulations` top category      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
             tree_with_regulations.json
      ┌──────────────────────────────────────┐
      │ 11 top categories                    │
      │ 96 taxonomy leaves                   │
      │ 29 regulation leaves                 │
      │ 60,649 total docs covered            │
      │ 935 regulation chunks identified     │
      └──────────────────────────────────────┘
                           │
                           ▼
             Event extraction pipeline reads this
             → 178 active regulation rules
             → assigned to users via user agent
```

---

## Inside Each Step

### Step 01 — The Rule Engine

```
For every URL in the corpus, at depths 1, 2, 3:

  Parse → (host, [seg₁, seg₂, seg₃, ...])

  Is a segment DYNAMIC?
    ├─ all digits                      "12345"          → YES
    ├─ date pattern \d{4}[-_]\d{1,2}  "2024-01"        → YES
    ├─ hex ≥ 8 chars                   "a3f8c291..."    → YES
    ├─ UUID pattern                    "a3f8c291-..."   → YES
    └─ ≥ 60% digit density, len ≥ 5   "AB12345"        → YES

  Is a segment SEMANTIC?
    └─ has [a-z] AND not {tr,en,www} AND not dynamic    → YES

  For candidate prefix at depth d:
    dynamic_ratio  = dynamic child tokens / total child tokens
    semantic_ratio = semantic child tokens / total child tokens

         ┌─ last segment IS dynamic?
         │       → REJECT always (IDs can never be stable category names)
         │
         ├─ doc_count ≥ 25
         │  distinct_children ≥ 3         → ACCEPT (strong)
         │  semantic_ratio ≥ 0.40
         │  dynamic_ratio ≤ 0.55
         │
         ├─ doc_count < 5                 → REJECT (weak)
         │  OR distinct_children < 2
         │  OR semantic ≤ 0.15 & dynamic ≥ 0.80
         │
         ├─ doc_count ≥ 1000              → ACCEPT (large-group override)
         │  AND ≥ 1 semantic segment      prevents over-splitting huge semantic trees
         │  AND last segment not dynamic
         │
         └─ everything else              → LLM decides: PARENT or NOT_PARENT

  Tree constraint: depth-d prefix only considered if depth-(d-1) parent was accepted.

Result
──────
  1,993 candidates evaluated
    105 accepted (depth 1: 5, depth 2: 24, depth 3: 76)
      8 via large-group override
      0 AI calls (rules resolved everything)
     26 docs fell to root fallback
```

### Step 02 — The Tail Signal Test

```
Each accepted group has a "chosen depth" — the level of the URL where the parent boundary sits.
Everything in the URL AFTER that depth is the "tail".

  bilgi.edu.tr / en / academics / undergraduate / ...
  ───────────────────────────────
  parent prefix (depth 3)        ^─────────────── tail

For each group, scan all tails and compute:

  no_tail_ratio           = docs with NO tail / total docs
  dynamic_tail_ratio      = dynamic tail tokens / total tail tokens
  semantic_tail_ratio     = semantic tail tokens / total tail tokens
  unique_tail_patterns    = distinct normalized tails  ("<id>" replaces IDs, "<n>" replaces numbers)
  tail_pattern_entropy    = Shannon (1948):  H = -∑ pᵢ · log₂(pᵢ)

Why entropy? A group with 200 docs and 180 distinct tail patterns has HIGH entropy — every page
is named differently, URL structure is informative. A group with 200 docs and 2 tail patterns
has LOW entropy — all docs are instances of one template, URL tells you nothing.

Decision cascade:

  no_tail_ratio ≥ 0.85?
  └─ YES → KNOWN (parent_explains_group_no_tail)
           Most docs end at the parent depth. The parent prefix IS the category.

  semantic_tail_ratio ≥ 0.45
  AND unique_tail_patterns ≥ 4
  AND tail_pattern_entropy ≥ 1.50 bits     ← ~8 distinct patterns, evenly spread
  AND dominant_pattern_share ≤ 0.55?
  └─ YES → KNOWN (semantic_tail_signal)
           Tails are diverse and semantic. URL structure tells the full story.

  dynamic_tail_ratio ≥ 0.70
  AND semantic_tail_ratio ≤ 0.30?
  └─ YES → UNKNOWN (dynamic_tail_low_signal)
           Tails are mostly IDs. URL tells us nothing about content.

  dominant_pattern_share ≥ 0.60
  OR tail_pattern_entropy ≤ 1.20 bits?
  └─ YES → UNKNOWN (repetitive_tail_low_signal)
           Tails repeat one template. No diversity, no information.

  Else → UNKNOWN (mixed_or_weak_signal)

Result
──────
  105 groups → 74 KNOWN (39,325 docs, 64.8%)
             → 31 UNKNOWN (21,324 docs, 35.2%)
```

### Step 03 — Semantic Discovery for the 31 Unknown Groups

```
31 unknown groups
21,324 documents
URL structure: useless
Need to find categories from document content.

Fetch embeddings from DB for all 21,324 docs
            │
            ▼
L2-normalize every vector:
  v̂ = v / ‖v‖
  (converts cosine distance → Euclidean on unit sphere,
   makes K-Means equivalent to maximizing cosine similarity)
            │
            ▼
Auto-k formula (scales sublinearly with n):

  leaf_k = clip(round(√(n/8)),   20, 300)   → 52
  coarse = clip(round(n/2500),    6,  20)   →  9
  mid    = clip(round(n/1000),   12,  45)   → 21
  fine   = clip(round(n/400),    20,  80)   → 52

            │
            ▼
STAGE 1 — MiniBatchKMeans (Sculley 2010, web-scale K-Means)

  MiniBatchKMeans(n_clusters=52, batch_size=4096,
                  max_iter=300, reassignment_ratio=0.01)

  Processes random mini-batches instead of full dataset.
  Linear time complexity: O(n) not O(n·k·iter).
  reassignment_ratio=0.01 → 1% of clusters eligible for
  reassignment each step, preventing cluster death in
  sparse regions while allowing convergence.

  Output: 52 leaf clusters + 52 centroids

            │
            ▼
STAGE 2 — Ward HAC on the 52 centroids (Ward 1963)

  Z = linkage(centroids, method='ward', metric='euclidean')

  Ward merges the pair of clusters whose union minimizes
  total within-cluster variance (minimum-variance criterion).
  Running on centroids not documents: O(k²) not O(n²).

  Cut dendrogram at 3 levels:
    coarse → 9 clusters   (broad topic areas)
    mid    → 21 clusters  (usable categories)
    fine   → 52 clusters  (same as leaf, used in Step 04)

            │
            ▼
Label each cluster from 3 signals:

  ① TF-IDF on document titles
    top 6 terms by mean TF-IDF score across cluster,
    after removing bilingual stopwords (TR + EN)
    → discriminative content terms

  ② Top URL path segments by frequency
    (after stripping dynamic tokens and locale prefixes)
    → structural hints even for dynamically-named URLs

  ③ Representative titles
    5 docs closest to centroid by cosine similarity
    → concrete examples of cluster content

Result
──────
  21,324 docs → 52 labeled clusters ready for taxonomy
```

### Step 04 — Unifying into One Tree

```
74 URL-known groups   +   52 discovered clusters
(Step 02 output)          (Step 03 fine level)
       │                          │
       ▼                          │
BILINGUAL DEDUP                   │
  Strip /en/ and /tr/ from paths  │
  Compute fingerprint per group   │
  Groups with same fingerprint    │
  → keep larger, sum doc_counts   │
  74 → 71 groups (3 twins merged) │
       │                          │
       ▼                          │
UPLOAD RECLASSIFICATION           │
  Groups under /upload/ paths     │
  → classify by DOCUMENT CONTENT  │
  not by file-system location     │
  "Erasmus Guides" not "Uploads"  │
  71 groups: 1 upload, 70 normal  │
       │                          │
       └────────────┬─────────────┘
                    │
                    ▼ 71 + 52 = 123 groups
         AI TAXONOMY MAPPING
         claude-opus-4-6
         batches of 12 · 12 calls · 0 errors

         Each group → { top_category, sub_category, category_label }

         Closed top-category vocabulary (12 terms):
           academics  admissions  administration  events
           international  library  news  people
           quality  regulations  research  student_life

         For URL-known groups: prompt uses parent_key + sample_urls + semantic_tokens
         For discovered clusters: prompt uses TF-IDF tokens + representative_titles
         Bad labels (generic words: "Files", "Content", "Documents") → retry pass
                    │
                    ▼
         QUALITY SCORE per leaf node:

           generic_ratio = words in label that are generic / total words
           locale_ratio  = words in label that are locale suffixes / total words
           specificity   = 1 - generic_ratio - locale_ratio       weight: 0.45
           coverage      = fraction of groups in leaf mapped by AI weight: 0.35
           size_health   = penalizes leaves too small or too large  weight: 0.20

           quality_score = 0.45·specificity + 0.35·coverage + 0.20·size_health

Result
──────
  11 top-level categories
  90 sub-levels
  96 leaf nodes
  avg quality_score: 0.873
  high-quality leaves (≥ 0.70): 95 / 96
  low-quality leaves (< 0.40): 0
  AI-mapped: 123 / 123 (100%)
```

### Step 12 — Regulation Overlay

```
Refined taxonomy tree (Step 05 output)
            │
            ▼
SQL regex identifies regulation-domain URLs:

  url ~* '/(mevzuat|yonetmelik|yonerge|regulation|regulations|
            directive|policy|policies|handbook|internship|
            dual-major|double-major|thesis|discipline)/'

            │
            ▼
935 regulation chunks · 80 source URLs

Cluster count: round(935 / 50) = 19  (1 cluster per ~50 docs)
clamped to [15, 35]

Repeat MiniBatchKMeans → Ward HAC on regulation embeddings only

            │
            ▼
Label each cluster:
  Top TF-IDF term per cluster (length ≥ 3, not in stopwords)
  → most discriminative content word in that cluster

            │
            ▼
Overlay 29 labeled leaves onto taxonomy
under the `regulations` top category:

  regulations/
  ├── academic_regulations/
  │     Undergraduate Education And Examination Regulation   (63 docs)
  │     Higher Education Law Implementation Procedures       (60 docs)
  │     Credit System Education Regulation                   (18 docs)
  ├── student_handbooks/
  │     Student Handbooks 2022-2023                          (56 docs)
  │     Student Handbooks And Financial Procedures           (54 docs)
  ├── double_major_minor_regulations/
  │     Double Major Minor Honors Programs                   (56 docs)
  ├── internship_student_work_regulations/
  │     Internship And Student Work Procedures               (47 docs)
  │     Internship Directive And Guide                       (30 docs)
  ├── disciplinary_regulations/
  │     Student Discipline Regulations                       (44 docs)
  ├── disability_accessibility_policy/
  │     Disability Unit Procedures And Policy                (40 docs)
  └── ... 19 more leaves

            │
            ▼
  tree_with_regulations.json
  ← this is what the event pipeline reads
```

---

## The Full River: From Raw URLs to 178 Active Rules

```
knowledge_base · 60,649 chunks
            │
            ▼
STEP 01 — URL group detection
  1,993 candidate prefixes evaluated
  rule engine (strong/weak/override) resolves all 0 AI calls
            │
            ▼
  105 parent groups
            │
            ▼
STEP 02 — Tail signal classification
  Shannon entropy + 4 threshold rules
            │
       ┌────┴────┐
       ▼         ▼
  74 KNOWN    31 UNKNOWN
  39,325 docs  21,324 docs
       │         │
       │         ▼
       │    STEP 03 — Semantic discovery
       │    L2-normalize → MiniBatchKMeans (k=52)
       │    → Ward HAC (cut at coarse/mid/fine)
       │    → 52 labeled clusters
       │         │
       └────┬────┘
            ▼
  126 groups total
            │
            ▼
STEP 04 — Unified taxonomy
  Bilingual dedup (74→71) + upload reclassification
  AI mapping: 12 calls · 0 errors · 100% coverage
  Quality scoring per leaf
            │
            ▼
  96 leaves · avg quality 0.873
            │
            ▼
STEP 05 — Tree refinement
  Clean degenerate sub-levels
            │
            ▼
STEP 12 — Regulation overlay
  SQL regex → 935 chunks isolated
  MiniBatchKMeans → Ward HAC → TF-IDF labels
  29 regulation leaves grafted onto tree
            │
            ▼
  tree_with_regulations.json
  11 top categories · 96 + 29 leaves · 60,649 docs
            │
            ▼
Event extraction pipeline
  Two-pass LLM extracts rules from 935 regulation chunks
            │
            ▼
  178 active regulation rules
            │
            ▼
User agent assigns relevant rules to each person
  SQL-matched: 11 rules (deterministic, GPA/credits)
  Contextual-matched: 167 rules (LLM reasoning per user)
            │
            ▼
  GET /api/events/assignments/me
```

---

## Why Epoch 1 Failed, What Epoch 2 Fixed

```
PROBLEM 1: Centroids built on wrong data
─────────────────────────────────────────
Epoch 1 built cluster centroids from 4,013 docs
while 35,507 docs were missing embeddings.
Centroids did not represent the actual opaque documents.

Epoch 2 fix: run Step 03 only on the 21,324 unknown docs,
all of which have embeddings. Centroids are representative.

PROBLEM 2: No signal test before clustering
────────────────────────────────────────────
Epoch 1 routed groups to embedding clustering based only
on whether the URL had weak semantic signal. Groups with
repetitive or dynamic tails went to clustering without
any check on whether clustering would even help.

Epoch 2 fix: Step 02 measures tail entropy and routes groups
to clustering only when URL structure has genuinely failed.

PROBLEM 3: /en/ and /tr/ counted twice
────────────────────────────────────────
Epoch 1: bilgi.edu.tr/en/academics/ and bilgi.edu.tr/tr/akademik/
were treated as two separate categories.

Epoch 2 fix: locale-stripped fingerprint deduplication in Step 04,
merging twins before any labeling happens.

PROBLEM 4: No quality measurement
───────────────────────────────────
Epoch 1: 302 categories with no way to tell which labels were
generic ("Content", "Documents") vs. specific.

Epoch 2 fix: quality_score per leaf = 0.45·specificity + 0.35·coverage
+ 0.20·size_health. 95/96 leaves score ≥ 0.70.

FINAL NUMBERS
─────────────
Epoch 1: 302 flat categories · unknown quality · 35,507 docs misrouted
Epoch 2:  96 taxonomy leaves + 29 regulation leaves
          avg quality 0.873 · 100% AI-mapped · 0 low-quality leaves
```
