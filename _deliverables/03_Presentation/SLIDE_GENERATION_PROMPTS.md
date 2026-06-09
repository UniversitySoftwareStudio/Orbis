# Orbis Detailed Slide Generation Prompts

Use this file with `PRESENTATION_DESIGN_SYSTEM.md`. Every slide-specific prompt
must inherit the master prompt prefix and color/schema rules from that file.

Goal: create a detailed 10-minute CMPE 492 presentation that tells a strong
engineering story. The deck should not feel like a shallow result showcase. Each
slide must answer one narrative question and show a precise diagram, system
detail, data flow, or evidence boundary.

Global requirements:

- 16:9 widescreen.
- 10-11 slides maximum.
- Minimum body font 20 pt.
- Use exact Orbis module/table/route names where possible.
- Avoid generic boxes like "AI", "database", "backend" unless paired with exact
  names.
- Use the same color meaning across all slides.
- Keep slide text short, but make diagrams detailed.
- Use "labeled evaluation set" unless the team chooses to defend "gold ground
  truth" in Q&A.

## Slide 1: Title And Thesis

Narrative job:

- Establish that Orbis is not just a chatbot; it is a support system with pull,
  push, and review paths.

Final slide text:

- **Orbis**
- Intelligent Academic Support System with AI and RAG
- Pull search + push obligations + submission screening
- Atakan Gul, Arda Kaan Yildiz
- CMPE 492, June 2026

Precise visual:

- Right side: product/dashboard mockup with three labeled cards:
  - `Ask official sources`
  - `My regulation obligations`
  - `Submission review result`
- Bottom ribbon:
  - `University sources` -> `Orbis` -> `Student action`
- Use the Orbis color schema:
  - sources gray, Orbis core blue, AI/RAG teal, student action gold.

Generator prompt:

> [Use the Orbis master prompt prefix.] Create Slide 1, "Title And Thesis". Show "Orbis" as the dominant title and "Intelligent Academic Support System with AI and RAG" as subtitle. Include the line "Pull search + push obligations + submission screening". On the right, show a realistic product dashboard mockup with three cards: "Ask official sources", "My regulation obligations", and "Submission review result". Add a bottom ribbon "University sources -> Orbis -> Student action". Keep it polished but implementation-focused, not abstract.

## Slide 2: Problem: Information Exists, Guidance Does Not

Narrative job:

- Show why a normal university portal or ordinary chatbot is insufficient.

Final slide text:

- Rules are scattered.
- Students may not know what to ask.
- Static portals store records.
- They rarely interpret context.

Precise visual:

- Center: student profile card:
  - `CSE student`
  - `year / semester`
  - `GPA / standing`
  - `internship / graduation status`
- Around it: fragmented source blocks:
  - `SIS`
  - `course catalog`
  - `regulations`
  - `PDF directives`
  - `announcements`
- Two missing-question callouts:
  - `What applies to me?`
  - `When should I act?`
- Show static arrows from sources to storage, but missing arrows to student
  action.

Generator prompt:

> [Use the Orbis master prompt prefix.] Create Slide 2, "Information Exists, Guidance Does Not". Build a precise problem map. Place a student profile card in the center with fields "program", "year/semester", "GPA/standing", "internship/graduation status". Surround it with source blocks labeled SIS, course catalog, regulations, PDF directives, and announcements. Add two missing bridges labeled "What applies to me?" and "When should I act?". Use short slide text: "Rules are scattered.", "Students may not know what to ask.", "Static portals store records.", "They rarely interpret context." Make the problem operational, not emotional.

## Slide 3: Design Requirements And Safety Boundaries

Narrative job:

- Explain what the system must guarantee before showing architecture.

Final slide text:

- Grounded in official sources.
- Binding rules separated from noise.
- Obligations matched to profile state.
- Decisions logged and inspectable.
- Advisory, not authoritative.
- Screening, not grading.

Precise visual:

- Center: `Orbis design contract`.
- Four requirement nodes connected to the center:
  - `source evidence`
  - `taxonomy filter`
  - `profile-aware matching`
  - `audit trail`
- Two boundary rails at bottom:
  - `advisor remains final authority`
  - `submission agent checks requirements, not grades`
- Add small traceability path:
  - `source URL` -> `evidence quote` -> `reasoning` -> `student output`.

Generator prompt:

> [Use the Orbis master prompt prefix.] Create Slide 3, "Design Requirements And Boundaries". Show a central block "Orbis design contract" connected to four exact requirements: source evidence, taxonomy filter, profile-aware matching, audit trail. At the bottom, draw two boundary rails: "advisor remains final authority" and "submission agent checks requirements, not grades". Include a mini traceability path: source URL -> evidence quote -> reasoning -> student output. Keep text short and make this look like an engineering contract.

## Slide 4: Data Foundation And Taxonomy

Narrative job:

- Show the real data processing depth behind the RAG/event system.

Final slide text:

- 80 official source URLs.
- 60,649 chunks.
- 125 taxonomy leaves.
- 935 regulatory chunks.
- Taxonomy decides what can become an obligation.

Precise visual:

- Detailed funnel with exact stages:
  - `80 official source URLs`
  - `semantic chunking: ~800 tokens, 100 overlap`
  - `MiniLM embeddings`
  - `knowledge_base + knowledge_base_embeddings`
  - `URL rule engine`
  - `tail entropy classification`
  - `MiniBatchKMeans + Ward HAC`
  - `LLM taxonomy mapping`
  - `regex regulation overlay`
- Split outputs:
  - `RAG index: broad institutional search`
  - `event input: 935 regulatory chunks`
- Include side badge:
  - `125 leaves / 29 regulatory leaves`

Generator prompt:

> [Use the Orbis master prompt prefix.] Create Slide 4, "Data Foundation And Taxonomy". Do not draw a generic funnel. Draw the exact processing chain: 80 official source URLs -> semantic chunking (~800 tokens, 100 overlap) -> MiniLM embeddings -> knowledge_base + knowledge_base_embeddings -> URL rule engine -> tail entropy classification -> MiniBatchKMeans + Ward HAC -> LLM taxonomy mapping -> regex regulation overlay. Split the final output into "RAG index: broad institutional search" and "Event input: 935 regulatory chunks". Add large metric badges for 60,649 chunks, 125 taxonomy leaves, 29 regulatory leaves, and 935 regulatory chunks.

## Slide 5: System Architecture

Narrative job:

- Show Orbis as a real full-stack system with exact routes, services, and
  persistent tables.

Final slide text:

- React/Vite frontend.
- FastAPI service layer.
- PostgreSQL + pgvector.
- Three support paths share one evidence store.

Precise visual:

- Left input column:
  - `student profile`
  - `course/SIS data`
  - `university documents`
  - `assignment files`
- Top/frontend:
  - `React/Vite student shell`
- Center/FastAPI routes:
  - `/chat`
  - `/events/trigger`
  - `/regulations/me`
  - `/assignments/{id}/submit/stream`
- Service modules:
  - `RAGService`
  - `EventPipelineOrchestrator`
  - `SubmissionAgent`
- Storage layer:
  - `knowledge_base`
  - `knowledge_base_embeddings`
  - `event_candidate_logs`
  - `regulation_rules`
  - `user_rule_assignments`
  - `assignment_submissions`
- Output column:
  - `grounded answer`
  - `regulation assignment`
  - `submission decision + appeal`

Generator prompt:

> [Use the Orbis master prompt prefix.] Create Slide 5, "System Architecture". Build a precise architecture diagram with four columns: inputs, React/Vite frontend, FastAPI services, PostgreSQL + pgvector storage, outputs. Include exact routes: /chat, /events/trigger, /regulations/me, /assignments/{id}/submit/stream. Include exact service boxes: RAGService, EventPipelineOrchestrator, SubmissionAgent. Include exact tables: knowledge_base, knowledge_base_embeddings, event_candidate_logs, regulation_rules, user_rule_assignments, assignment_submissions. Outputs must be "grounded answer", "regulation assignment", and "submission decision + appeal". Use detailed labeled arrows and the shared color schema.

## Slide 6: Pull Path: Grounded RAG Search

Narrative job:

- Explain the RAG path as a grounded retrieval workflow and make clear why it is
  still reactive.

Final slide text:

- Useful when the student asks.
- Retrieval is grounded in stored chunks.
- Sources remain visible.
- Pull mode cannot discover unknown obligations.

Precise visual:

- Sequence diagram:
  - `POST /chat`
  - `RAGService.process_query`
  - `route_query`
  - branch A: `execute_sql_intent`
  - branch B: `execute_vector_intent`
  - `VectorSearchRepository.search_knowledge_base`
  - `pgvector similarity search`
  - `rerank_docs`
  - `build_context`
  - `stream_answer`
- Show answer card with:
  - `answer`
  - `source URL`
  - `evidence snippet`
- Add a gold note:
  - `student must know the question`.

Generator prompt:

> [Use the Orbis master prompt prefix.] Create Slide 6, "Pull Path: Grounded RAG Search". Make a sequence diagram with exact labels: POST /chat -> RAGService.process_query -> route_query -> execute_sql_intent OR execute_vector_intent -> VectorSearchRepository.search_knowledge_base -> pgvector similarity search -> rerank_docs -> build_context -> stream_answer. End with an answer card containing "answer", "source URL", and "evidence snippet". Add a clear note "student must know the question". This diagram should show why RAG is grounded but reactive.

## Slide 7: Push Path: Extracting Actionable Obligations

Narrative job:

- Show how regulation prose becomes strict obligations, and why rejection is a
  quality mechanism.

Final slide text:

- 935 regulatory chunks processed.
- 323 candidate rules evaluated.
- Two-pass adversarial review.
- 178 accepted obligations.
- 145 rejected quality candidates.

Precise visual:

- Pipeline diagram:
  - `POST /events/trigger`
  - `EventPipelineOrchestrator.start_run`
  - `event_runs`
  - `SearchAgent.fetch_regulation_sources`
  - `ReasoningAgent.extract`
  - `EventCreator.persist_candidates`
  - `ReasoningReviewer` for ambiguous candidates
  - `event_candidate_logs`
  - accepted obligation store
- Include metrics in the flow:
  - `935 chunks`
  - `323 candidates`
  - `178 accepted`
  - `145 rejected`
- Include example obligation record fields:
  - `audience`
  - `trigger`
  - `deadline`
  - `evidence URL`
  - `reason code`
- Visualize accepted in green and rejected in red.

Generator prompt:

> [Use the Orbis master prompt prefix.] Create Slide 7, "Push Path: Extracting Actionable Obligations". Draw the exact event extraction pipeline: POST /events/trigger -> EventPipelineOrchestrator.start_run -> event_runs -> SearchAgent.fetch_regulation_sources -> ReasoningAgent.extract -> EventCreator.persist_candidates -> optional ReasoningReviewer for ambiguous candidates -> event_candidate_logs -> accepted obligation store. Place the measured counts directly on the arrows: 935 regulatory chunks, 323 candidate rules, 178 accepted obligations, 145 rejected candidates. Add an example obligation record card with fields audience, trigger, deadline, evidence URL, and reason code. Make accepted green and rejected red.

## Slide 8: Personalization: Matching Obligations To Profiles

Narrative job:

- Explain the hardest part: applying accepted obligations to individual student
  state.

Final slide text:

- 4 profile states tested.
- SQL path handles objective thresholds.
- Contextual path handles situation-specific rules.
- 176 assignments generated.
- Main weakness: F1 0.514.

Precise visual:

- Left: four student profile cards:
  - `P1 CSE Y2, probation`
  - `P2 Business Y3, double major`
  - `P3 CSE senior, graduation project`
  - `P4 CSE internship required`
- Middle: two matching paths:
  - `match_sql_rules`
  - `match_contextual_rules`
- Data stores:
  - read from `regulation_rules`
  - write to `user_rule_assignments`
- Output assignment card fields:
  - `rule title`
  - `urgency`
  - `match_type: SQL/CTX`
  - `reason`
  - `source evidence`
- Add a small failure-mode panel:
  - `false positives: broad rules`
  - `false negatives: situational rules`.

Generator prompt:

> [Use the Orbis master prompt prefix.] Create Slide 8, "Personalization: Matching Obligations To Profiles". Draw four profile cards: P1 CSE Y2 probation, P2 Business Y3 double major, P3 CSE senior graduation project, P4 CSE internship required. Feed them into two exact paths: match_sql_rules and match_contextual_rules. Show both paths reading from regulation_rules and writing to user_rule_assignments. Show an output assignment card with fields rule title, urgency, match_type SQL/CTX, reason, source evidence. Include metrics: 176 assignments generated and F1 0.514. Add a small failure-mode panel: false positives from broad rules, false negatives from situational rules.

## Slide 9: Submission Review Agent

Narrative job:

- Show the submission agent as a two-step requirement checker with file safety
  gates and appeal path.

Final slide text:

- File gate before AI.
- Requirements decomposed first.
- Verdict checks evidence, not instructions.
- Approve/reject with appeal.
- Screening, not grading.

Precise visual:

- Workflow:
  - `/assignments/{id}/submit/stream`
  - `stream_submission_evaluation`
  - deterministic file gate:
    - extension
    - empty file
    - corrupt PDF/DOCX/ZIP
    - text extraction
  - `requirement decomposition`
  - `verdict prompt`
  - `fallback_decision`
  - `assignment_submissions`
  - `flag_submission_rejection` appeal path
- Prompt-injection detail:
  - submitted content box contains malicious instruction;
  - arrow blocked before verdict;
  - verdict reads assignment requirements and extracted evidence.

Generator prompt:

> [Use the Orbis master prompt prefix.] Create Slide 9, "Submission Review Agent". Draw the exact submission workflow: /assignments/{id}/submit/stream -> stream_submission_evaluation -> deterministic file gate with checks for extension, empty file, corrupt PDF/DOCX/ZIP, and text extraction -> requirement decomposition -> verdict prompt -> fallback_decision if needed -> assignment_submissions. Add an appeal branch labeled flag_submission_rejection. Show a submitted-content box containing a prompt injection instruction, blocked from controlling the verdict; show the verdict reading assignment requirements and extracted evidence instead. Highlight "Screening, not grading."

## Slide 10: Evaluation: What The Evidence Says

Narrative job:

- Present metrics as answers to engineering questions, not as isolated numbers.

Final slide text:

- Can we avoid bad obligations? P 0.978, F1 0.723.
- Can we assign them correctly? F1 0.514.
- Can we screen safely? Acc 93.8%, Recall 1.000.
- Injection cases rejected: 4/4 tested.
- Next work is dictated by the weakest layer.

Precise visual:

- Three evaluation cards:
  - Event extraction:
    - `N=323`
    - `TP=174, FP=4, FN=129, TN=16`
    - `P=0.978, R=0.574, F1=0.723`
  - Assignment matching:
    - `N=712`
    - `TP=107, FP=69, FN=133, TN=403`
    - `P=0.608, R=0.446, F1=0.514`
  - Submission review:
    - `N=32`
    - `TP=8, FP=2, FN=0, TN=22`
    - `Acc=93.8%, P=0.800, R=1.000, F1=0.889`
- Add caveat badge:
  - `4/4 tested injection cases, not a general guarantee`.

Generator prompt:

> [Use the Orbis master prompt prefix.] Create Slide 10, "Evaluation: What The Evidence Says". Use three detailed metric cards tied to design questions. Card 1: "Can we avoid bad obligations?" Event extraction, N=323, TP=174, FP=4, FN=129, TN=16, P=0.978, R=0.574, F1=0.723. Card 2: "Can we assign them correctly?" Assignment matching, N=712, TP=107, FP=69, FN=133, TN=403, P=0.608, R=0.446, F1=0.514, mark as weakest layer. Card 3: "Can we screen safely?" Submission review, N=32, TP=8, FP=2, FN=0, TN=22, Acc=93.8%, P=0.800, R=1.000, F1=0.889. Add badge "4/4 tested injection cases, not a general guarantee." Keep it readable with mini confusion matrices, not a dense table.

## Slide 11: Risks, Roadmap, And Demo

Narrative job:

- Close by showing that the system is inspectable, limited, and ready to demo.

Final slide text:

- Risks: wrong advice, missed obligations, stale regulations, privacy,
  injection.
- Mitigations: evidence, logs, dismiss/action states, appeal path.
- Roadmap: SIS integration, human review queue, stronger matching recall,
  flag-for-review.
- Demo: ask -> obligation -> submit.

Precise visual:

- Left: risk matrix:
  - `wrong advice` -> `source evidence + status controls` -> `human review`
  - `missed obligation` -> `RAG fallback` -> `recall-oriented pass`
  - `stale regulation` -> `content hashes/checkpoints` -> `scheduled re-crawl`
  - `privacy` -> `minimal profile fields + logs` -> `SIS-safe integration`
  - `prompt injection` -> `requirement-grounded verdict` -> `flag_for_review`
- Right: demo storyboard:
  - `/chat` question
  - `/regulations/me` assignment
  - `/assignments/{id}/submit/stream` decision
- Closing line:
  - `Proactive, inspectable, measurable academic support.`

Generator prompt:

> [Use the Orbis master prompt prefix.] Create Slide 11, "Risks, Roadmap, And Demo". On the left, create a risk-to-mitigation-to-roadmap matrix with rows: wrong advice -> source evidence + status controls -> human review; missed obligation -> RAG fallback -> recall-oriented pass; stale regulation -> content hashes/checkpoints -> scheduled re-crawl; privacy -> minimal profile fields + logs -> SIS-safe integration; prompt injection -> requirement-grounded verdict -> flag_for_review. On the right, create a three-step demo storyboard with exact routes: /chat question, /regulations/me assignment, /assignments/{id}/submit/stream decision. End with the large closing line "Proactive, inspectable, measurable academic support."

## Optional Backup Slide: Metric Provenance

Use only for Q&A.

Final slide text:

- Event extraction: 323 labeled candidates.
- Assignment matching: 712 profile-obligation pairs.
- Submission review: 32 deterministic cases.
- Injection: 4 tested injection cases.
- Caveat: matching uses 4 profiles; submission set is small.

Precise visual:

- Table columns:
  - `metric family`
  - `evaluation set`
  - `artifact/script`
  - `limitation`
- Artifact/script labels:
  - `candidates_gt.jsonl`
  - `assignment_matching_gt.jsonl`
  - `submissions/results.jsonl`
  - `eval_event_extraction.py`
  - `eval_assignment_matching.py`
  - `eval_submission_agent.py`

Generator prompt:

> [Use the Orbis master prompt prefix.] Create a backup slide titled "Metric Provenance". Make a precise provenance table with columns metric family, evaluation set, artifact/script, limitation. Include event extraction: 323 labeled candidates, candidates_gt.jsonl, eval_event_extraction.py; assignment matching: 712 profile-obligation pairs, assignment_matching_gt.jsonl, eval_assignment_matching.py; submission review: 32 deterministic cases, submissions/results.jsonl, eval_submission_agent.py; injection: 4 tested injection cases. Add caveat: matching uses 4 profiles; submission set is small. Design as a Q&A slide.
