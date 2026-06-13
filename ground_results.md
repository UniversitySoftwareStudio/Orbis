# Ground Truth Results

Compact view of the three evaluated Orbis systems: event extraction, assignment matching, and RAG chatbot retrieval/generation.

Label caveat: event and assignment labels are treated as project ground truth for reporting, but they are silver labels created with LLM judge support and author review. RAG results come from the later `origin/rag_evaluation` / `origin/report` branch work, not the older chunking-quality experiment on this branch.

## Model Metadata

| Area | Model / provider | Role | Source |
|---|---|---|---|
| Event GT labels | `google/gemini-2.5-flash-lite` via OpenRouter | Primary LLM judge for candidate labels | `_llm_judge.py`, `build_event_gt.py` |
| Assignment GT labels | `google/gemini-2.5-flash-lite` via OpenRouter | Primary LLM judge for profile-obligation applicability | `_llm_judge.py`, `build_event_gt.py` |
| Second-judge validation | `deepseek/deepseek-v3.2` via OpenRouter | Independent validation sample / noise-floor estimate | `human_validate.py` |
| Reported cross-check model | `qwen/qwen3-235b-a22b-2507` via OpenRouter | Secondary judge artifacts and cross-check noted in report | `report/report.tex`, `*.qwen.jsonl` |
| Event extraction pipeline | `google/gemini-2.5-flash-lite` + `deepseek/deepseek-v3.2` | Bulk extraction/review plus adversarial Pass 2 | `report/report.tex` |
| RAG embeddings | TEI embedding service, default `EMBEDDING_PROVIDER=tei` | Vector retrieval over KB chunks | `origin/rag_evaluation:api/embedding/config.py` |
| RAG reranker | `jina-reranker-v2-base-multilingual` | Two-stage neural reranking | `origin/rag_evaluation:api/rag/config.py` |
| RAG answer LLM | Groq `llama-3.3-70b-versatile` observed in runtime log / env example | Final answer generation and router LLM backend | `origin/rag_evaluation:api/.env.example`, eval log Q078 |

Shared judge settings: `_llm_judge.py` defaults to `JUDGE_MODEL=google/gemini-2.5-flash-lite`, `temperature=0.0`, and OpenRouter chat completions.

## 1. Event System

**What was tested:** whether extracted regulation candidates are real student obligations.

**Ground truth:** `api/data/ground_truth/events/candidates_gt.jsonl`

**Set:** 323 event candidates from `event_candidate_logs`

**Metadata:** primary GT judge `google/gemini-2.5-flash-lite`; system decisions came from the event extraction run, with adversarial review reported as `deepseek/deepseek-v3.2`.

| Metric | Value |
|---|---:|
| Accepted by system | 178 |
| Rejected by system | 145 |
| True positives | 174 |
| False positives | 4 |
| False negatives | 129 |
| True negatives | 16 |
| Accuracy | 0.588 |
| Precision | 0.978 |
| Recall | 0.574 |
| F1 | 0.723 |

**Good example:** correct accept

> "Find a project advisor within the first two weeks of the first semester of the Graduation Design Project."

Gold label: true obligation.  
System decision: accepted.  
Why good: clear student action plus a deadline.

**Bad example:** missed obligation

> "Respond to Graduation Design Project topic announcements within the first two weeks of Semester 1. Form your project team and finalize your topic selection with an advisor during this window."

Gold label: true obligation.  
System decision: rejected as `not_imperative_enough`.  
What it shows: the filter is precise but too conservative, so recall suffers.

## 2. Assignment Matching System

**What was tested:** whether each accepted obligation should be assigned to each student profile.

**Ground truth:** `api/data/ground_truth/events/assignment_matching_gt.jsonl`

**Set:** 712 profile-obligation pairs, built as 4 profiles x 178 accepted obligations

**Metadata:** primary GT judge `google/gemini-2.5-flash-lite`; assignment output came from archived `regulation_rules` + `user_rule_assignments` rows. Matching used hybrid deterministic SQL plus contextual LLM matching.

| Metric | Value |
|---|---:|
| True positives | 107 |
| False positives | 69 |
| False negatives | 133 |
| True negatives | 403 |
| Precision | 0.608 |
| Recall | 0.446 |
| F1 | 0.514 |

| Profile | Precision | Recall | F1 |
|---|---:|---:|---:|
| P1: Computer Engineering, year 2, probation | 0.548 | 0.469 | 0.505 |
| P2: Business, double major | 0.667 | 0.358 | 0.466 |
| P3: senior/graduation-project profile | 0.650 | 0.500 | 0.565 |
| P4: internship-required profile | 0.553 | 0.457 | 0.500 |

**Good example:** correct assignment

Profile: P1, Computer Engineering, undergraduate year 2, on probation.  
Assigned obligation:

> "Contact your Academic Advisor at least once every semester to discuss your academic progress and course plans."

Gold label: applies.  
System decision: assigned.  
Why good: probation context makes advisor contact clearly relevant.

**Bad example:** false positive assignment

Profile: P1, Computer Engineering, undergraduate year 2, internship not started.  
Assigned obligation:

> "Submit the Istanbul Bilgi University Compulsory/Voluntary Internship Contract Cover Form ... at least 10 working days before your internship start date."

Gold label: does not apply.  
System decision: assigned.  
What it shows: broad internship rules can be over-assigned before the profile is actually at the internship stage.

## 3. RAG System

**What was tested:** whether the live chatbot routes, retrieves context, reranks, expands PDFs, and generates correct answers for real Bilgi-style questions.

**Ground truth:** 100-query bilingual benchmark with author-validated expected answers, reported in `origin/report:_deliverables/01_Report1/report/report1.tex`.

**Runtime log:** `origin/rag_evaluation:api/data/rag_evaluation_logs.jsonl`

**Set:** 100 Turkish/English queries across direct course lookup, bulk course lookup, schedule, academic calendar, regulations, campus life, and multi-hop comparison.

**Metadata:** router + answer generation used the configured RAG LLM service; the branch env example and runtime error identify Groq `llama-3.3-70b-versatile`. Retrieval used hybrid SQL/vector tools, TEI embeddings, Jina `jina-reranker-v2-base-multilingual`, and Smart Context Expansion for PDFs.

| Metric | Value |
|---|---:|
| Questions | 100 |
| Routing accuracy | ~92% |
| Context recall | ~95% |
| MRR | ~0.94 |
| Semantic accuracy | ~98% |
| Answer F1, token overlap | ~78% |

Runtime-log shape:

| Logged item | Value |
|---|---:|
| JSONL records | 100 |
| SQL route uses | 36 |
| Vector route uses | 78 |
| Calendar route uses | 8 |
| Student schedule route uses | 6 |
| Smart Context Expansion triggered | 57 queries |
| Expanded PDFs | 169 |
| Newly added expanded chunks | 7,785 |
| Average context tokens | ~2,182 |

**Good example:** correct SQL route and grounded answer

Question:

> "What is the ECTS credit for YZG 411?"

Route: `sql`, filter `code=YZG 411`  
Final context: 1 course row, 212 context tokens  
Answer: YZG 411 has **6 ECTS**.  
Why good: exact course-code lookup went directly through SQL and returned the concise fact.

**Bad example:** generation failure after retrieval

Question:

> "What are the psychological counseling center's hours?"

Route: `vector` + `sql`, Smart Context Expansion triggered  
Final context: 80 chunk IDs, 3,005 context tokens  
Failure: Groq returned a `429` rate-limit error for `llama-3.3-70b-versatile`, so the final user-visible response was an error rather than an answer.  
What it shows: the retrieval pipeline can prepare context, but generation availability is still an operational dependency.

**Known softer failure mode:** the report notes routing deviations such as "Who is the target audience for ACC 516?" going to `vector` instead of `sql`. The answer still succeeded because vector retrieval found the ACC 516 course chunk, which is why context recall stayed higher than routing accuracy.

## Reading

- Event extraction is precise: accepted rules are almost always real obligations.
- Assignment matching is the weak layer: too many relevant obligations are missed, and broad rules are sometimes over-assigned.
- RAG is strong overall on the later 100-query benchmark: high context recall and semantic accuracy, with failures concentrated in routing deviations and runtime/model availability.
