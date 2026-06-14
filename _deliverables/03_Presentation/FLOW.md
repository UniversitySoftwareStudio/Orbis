# Orbis Presentation Flow

Follows the advisor's mandated 10-slide structure. 10 min total, all bullets,
no paragraphs, font ≥ 20 pt, clean template. Speaker in each header.

---

## Slide 1 — Title  (Atakan + Arda, ~30s)

- **Orbis** — An Intelligent Academic Support System with AI and RAG
- Team: Atakan Gül (121200152), Arda Kaan Yıldız (122200045)
- Supervisor: Özgür Özdemir
- Istanbul Bilgi University — Faculty of Engineering and Natural Sciences — CMPE 492 — June 2026
- One line: *Turning scattered university information into actionable, traceable guidance.*

Visual: logo + small ribbon `University sources → Orbis → Student action`.

---

## Slide 2 — Problem Statement  (Atakan, ~55s)

- University information exists but is **scattered, passive, hard to apply**.
- Rules live across SIS, catalogs, regulation PDFs, announcements.
- Students don't always know **what to ask** or **when to act**.
- Portals store records; they don't interpret the student's situation.
- → Need: proactive, personalized, **evidence-backed** support.

Visual: fragmented source map → student in the middle with two gaps.

---

## Slide 3 — Methodology / Approach  (Arda, ~70s)

- Three connected support paths:
  - **Pull** — grounded RAG search (ask a question).
  - **Push** — regulation obligations extracted & assigned before asking.
  - **Review** — submission screening against requirements.
- **Dataset:** 80 official URLs → 60,649 chunks → 125 taxonomy leaves → 935 regulatory chunks → 178 obligations → 176 assignments.
- **Taxonomy method:** Shannon-entropy URL classification + MiniBatchKMeans + Ward HAC → clean rule/non-rule split before any AI runs.
- **Models:** MiniLM embeddings + Jina cross-encoder reranker (RAG); two-pass LLM extraction & two-call submission reviewer.
- **Setup:** PostgreSQL + pgvector store; FastAPI backend; React/Vite frontend.
- **Process:** iterative/Agile — incremental sprints, GitHub PR review, build subsystem → evaluate → refine.
- **Split:** Arda — data scraping & RAG chatbot; Atakan — event pipeline, matching, submission agent, evaluation.

Visual: FULL end-to-end system map (whole canvas) — data collection → ingestion
→ 4-step taxonomy guardrail → shared PostgreSQL+pgvector → three runtime paths
(pull/push/review) → student. This is the detailed showcase slide.

---

## Slide 4 — System Design / Architecture  (Arda, ~65s)

Component & technology view (distinct from Slide 3's data-flow showcase), 4 tiers:

- **Client:** React/Vite student shell (chatbot, dashboard, My Regulations, submission review); SSE token streaming.
- **API:** FastAPI (Python 3.10, Uvicorn); routes `/chat`, `/search`, `/events/trigger`, `/regulations/me`, `/assignments/.../submit/stream`, `/sis/*`; JWT auth.
- **Services/AI:** RAG (Groq llama-3.3-70b router + Jina reranker), Event (orchestrator + agents + matcher), Submission (file gate + two-call reviewer); providers Groq/Gemini/OpenAI-compatible.
- **Data/Infra:** PostgreSQL + pgvector — HNSW (384-dim L2) + GIN (TSVECTOR) indexes; tables knowledge_base, regulation_rules, user_rule_assignments, assignment_submissions, event/agent logs; MiniLM via TEI container + HF fallback.

Visual: 4-tier layered stack (Client → API → Services → Data/Infra), request-down / SSE-response-up, tech chip under every component.

---

## Slide 5 — Implementation & Challenges  (Atakan, ~70s)

- **SDP II progress:** backend+API completed, taxonomy (125 leaves), RAG end-to-end, event pipeline+matching, submission agent, gold-label eval harness — built on S1 foundation (scraping, embedding choice, DB).
- **C1 rules vs noise** → 4-step taxonomy guardrail (935/60,649 regulatory chunks isolated before any AI).
- **C2 vague obligations** → two-pass adversarial review (55% accept / 45% reject by design).
- **C3 65% temporal news/events** → keyword-first hybrid + 2-stage Jina rerank + Smart Context Expansion (0 temporal contamination).
- **C4 fragmented multi-article rules** → Smart Context Expansion rebuilds full doc (8-step appeal procedure from 4 chunks).
- **C5 prompt injection in uploads** → two-call reviewer, document = evidence not instruction (injection 1/4 → 4/4).
- Every decision logged / auditable (event_candidate_logs · event_agent_logs).

Visual: top SDP-II progress checklist + 5-row challenge → resolution → evidence matrix.

---

## Slide 6 — Results & Testing (1/2): RAG + extraction + matching  (Atakan, ~70s)

- **RAG chatbot** (100-query bilingual benchmark, 7 routing categories):
  routing 92.3% · context recall 94.7% · MRR 0.94 · semantic accuracy 97.6%.
- **Embedding benchmark** (justifies model/chunk choice): best top-3 70.8% (TEI MiniLM, 100-word) · MRR 0.571.
- **Pipeline funnel:** 80 sources in 59 min → 323 candidates → 178 accepted (55%) / 145 rejected (45%).
- **Event extraction** (323 candidates, gold): P 0.978 · R 0.574 · F1 0.723 · Acc 0.588. Confusion: 174 TP · 4 FP · 129 FN · 16 TN.
- **Assignment matching** (712 pairs = 4 profiles × 178): P 0.608 · R 0.446 · F1 0.514. Overall 107 TP · 69 FP · 133 FN · 403 TN. Weakest layer.

Visual: RAG card + extraction card (+confusion) + matching card (+per-profile mini-table), red only on matching weakness.

---

## Slide 7 — Results & Testing (2/2): submission review + safety  (Atakan, ~65s)

- **Submission review** (32 cases = 4 assignments × 8 strata): Acc 93.8% · Precision 0.800 · Recall 1.000 · F1 0.889.
- **Confusion:** 8 TP · 0 FN (no genuine work rejected) · 2 FP · 22 TN. The 2 FP are over-approved partial drafts.
- **Strata:** 7 of 8 case types perfect (4/4); only flag_partial imperfect (2/4).
- **Ablation:** single-call → two-call agentic: Acc 0.781 → 0.938; injection 1/4 → 4/4.
- **Prompt injection:** 4/4 tested cases rejected (directional — not a general guarantee).

Visual: metric card + confusion + 8-strata bar + ablation before/after + injection.

---

## Slide 8 — Conclusion & Acknowledgments  (Arda, ~50s)

- Orbis moves academic support from **static lookup → proactive, inspectable, measurable** guidance.
- Boundaries honored: advisory, not authoritative; screening, not grading.
- Every subsystem is measurable — results show exactly where to work next.
- Thanks: supervisor Özgür Özdemir, course coordinator Doç. Dr. Tuğba Dalyan, Istanbul Bilgi University.

---

## Slide 9 — Future Work & Recommendations  (Arda, ~45s)

- Improve assignment-matching recall (the weakest layer).
- Live SIS integration for real student state.
- Human review queue + explicit "flag for review" class.
- Broader injection / safety testing beyond tested cases.

---

## Slide 10 — Demo  (Atakan + Arda, ~60s)

- **Embedded YouTube demo video** (left) + 3-step storyboard strip (right): **Ask → Obligation → Submit**.
- Present from live Google Slides (not PDF); needs venue internet; local MP4 fallback ready.
- Closing line: *Proactive, inspectable, measurable academic support.*

---

## Timing (~10 min)

| Slide | s | Speaker |
|---|---|---|
| 1 | 30 | both |
| 2 | 55 | Atakan |
| 3 | 70 | Arda |
| 4 | 65 | Arda |
| 5 | 70 | Atakan |
| 6 | 70 | Atakan |
| 7 | 65 | Atakan |
| 8 | 50 | Arda |
| 9 | 45 | Arda |
| 10 | 60 | both |

## Wording caveats

- Don't say Orbis replaces advisors or grades student work.
- Say "tested injection cases", not general injection security.
- Don't hide that matching is the weakest layer.
