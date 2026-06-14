# Orbis — Work Packages (CMPE 491 → CMPE 492)

Two-semester plan for a two-person team. Semester 1 (CMPE 491) established the
data and infrastructure foundation; Semester 2 (CMPE 492) built the three
intelligent subsystems and the evaluation on top of it.

**Team:** Atakan Gül (121200152), Arda Kaan Yıldız (122200045)
**Ownership model:** shared infrastructure (backend, DB, taxonomy), split
features (Arda → retrieval/RAG, Atakan → events/matching/submission).

---

## Semester 1 — CMPE 491 (foundation)

| WP | Work package | Owner | Deliverable | Status at S1 end |
|----|--------------|-------|-------------|------------------|
| WP1.1 | Data scraping & collection | Arda | ~12,600 web pages + ~2,245 PDFs from 80 bilgi.edu.tr sources | Done |
| WP1.2 | PDF filtering & language detection | Arda | filter_pdfs.py (1,595 kept), stopword-race language tagging (65% TR / 35% EN) | Done |
| WP1.3 | Embedding model selection | Arda | Benchmark MiniLM vs nomic, 100w vs 150w chunks → MiniLM 384-dim chosen (70.8% top-3) | **Done (decision locked)** |
| WP1.4 | Backend + DB scaffolding | Shared | FastAPI app, PostgreSQL + pgvector schema, HNSW + GIN indexes | Started |
| WP1.5 | Core API implementation | Shared | Ingestion/embedding endpoints, knowledge_base load pipeline | Started |

**Semester 1 outcome (midterm):** scraping complete, embedding model selected,
backend + database + initial API in place — the data foundation the second
semester builds on.

---

## Semester 2 — CMPE 492 (intelligent subsystems + evaluation)

| WP | Work package | Owner | Deliverable | Status |
|----|--------------|-------|-------------|--------|
| WP2.1 | Backend + API completion | Shared | All routes finished (/search, /events/*, /regulations/me, /assignments/*) | Done |
| WP2.2 | Taxonomy guardrail pipeline | Shared | 4-step pipeline (Shannon entropy + MiniBatchKMeans + Ward HAC + LLM mapping) → 125 leaves, 935 regulatory chunks | Done |
| WP2.3 | RAG chatbot pipeline | Arda | Router (4 tools) + hybrid search + 2-stage Jina rerank + Smart Context Expansion + streaming | Done |
| WP2.4 | Proactive event pipeline | Atakan | Orchestrator + agents, two-pass adversarial review → 178 obligations | Done |
| WP2.5 | Assignment matching | Atakan | SQL + contextual matching → 176 personalized assignments | Done |
| WP2.6 | Submission review agent | Atakan | File gate + two-call evidence-based reviewer + appeal path | Done |
| WP2.7 | Evaluation & gold ground truth | Atakan | Manual labels (323 candidates + 712 pairs), 32 submission cases, RAG 100-query benchmark | Done |
| WP2.8 | Frontend (student shell) | Shared | React/Vite UI: chatbot, dashboard, My Regulations, submission review | Done |
| WP2.9 | Reports, presentation, demo | Shared | Report 1, Report 2, deck, poster, video | In progress |

**Semester 2 outcome:** all three paths (pull/push/review) shipped end-to-end and
every subsystem evaluated against measured ground truth.

---

## Two-semester timeline (compact)

```
                 CMPE 491 (Semester 1)          CMPE 492 (Semester 2)
Data/Scraping    ████████████ done
Embedding sel.   ███████ done
Backend + DB     ██████ started ──────────────► ████ completed (WP2.1)
Taxonomy                                          ████████
RAG chatbot                                       ██████████ (Arda)
Event pipeline                                    ████████ (Atakan)
Matching                                          ██████ (Atakan)
Submission agent                                  ███████ (Atakan)
Evaluation                                        ██████████
Reports/Deck/Video                                       ████ (now)
```

---

## Notes

- This document is a **report / planning artifact**, not a presentation slide.
  The advisor's 10-slide list has no work-package slide; the two-semester split
  is surfaced in the presentation only as the Slide 3 process + contributions
  line, and Slide 5 ("Progress in SDP II") narrates the S1 → S2 handoff.
- If a work-packages or Gantt figure is needed in **Report 2** (risk/standards/
  contributions), this table is the source; render the timeline block as a
  proper Gantt there.
