# Orbis Detailed Presentation Flow

Base design system: `PRESENTATION_DESIGN_SYSTEM.md`.
Use-case narrative spine: `USE_CASE_NARRATIVE_SPINE.md`.
Slide-generation prompts: `SLIDE_GENERATION_PROMPTS.md`.

Presentation constraint: 10 minutes, 10-11 slides, all team members speak.

## Core Narrative

Orbis is not just a RAG chatbot. The project starts from a real academic support
failure: university information exists, but it is scattered, passive, and hard
to apply to an individual student's state. Orbis turns that passive information
into three connected support paths:

1. pull support: grounded RAG search when the student asks;
2. push support: regulation obligations extracted and assigned before the
   student asks;
3. review support: submission screening that checks files against requirements
   without pretending to grade academic quality.

The deck should therefore move from problem pressure to design choices, then to
mechanics, then to evidence and limitations. Results should appear as proof of
design tradeoffs, not as a detached scoreboard.

## 11-Slide Flow

### 1. Title And Thesis

Claim: Orbis moves academic support from static lookup to proactive,
evidence-backed guidance.

On slide:

- Orbis
- Intelligent Academic Support System with AI and RAG
- Pull search + push obligations + submission screening
- Team, advisor, institution, date

Visual:

- Product/dashboard mockup with three visible paths: Ask, Obligations,
  Submission Review.
- Small ribbon: University sources -> Orbis -> Student action.

Speaker point:

- "Our project is about making university information actionable, not just
  searchable."

### 2. Problem: Information Exists, Guidance Does Not

Claim: The student's problem is not absence of data; it is fragmentation,
timing, and applicability.

On slide:

- Rules are scattered across systems.
- Students do not always know what to ask.
- Static portals store records.
- They rarely interpret the student's situation.

Visual:

- Fragmented source map: SIS, course catalog, regulations, PDFs,
  announcements.
- Student in the center with two missing bridges: "What applies to me?" and
  "When should I act?"

Speaker point:

- "A chatbot alone only helps after the student asks a good question. The
  hardest obligations are often the ones the student never knows to ask about."

### 3. Design Requirements And Boundaries

Claim: Orbis was designed around four requirements and two safety boundaries.

On slide:

- Ground answers in official sources.
- Separate binding rules from noisy pages.
- Match obligations to student profiles.
- Keep every decision inspectable.
- Boundary: advisory, not authoritative.
- Boundary: screening, not grading.

Visual:

- Requirement compass or checklist around the Orbis core.
- Two boundary rails at the bottom: "Not replacing advisors" and "Not grading
  academic quality."

Speaker point:

- "The system is useful only if students can trace why something was shown and
  staff can audit what the AI did."

### 4. Data Foundation And Taxonomy

Claim: The main data-engineering problem is separating formal regulation from
the rest of the university web.

On slide:

- 80 official source URLs.
- 60,649 chunks.
- 125 taxonomy leaves.
- 935 regulatory chunks.
- Taxonomy decides what can become an obligation.

Visual:

- Funnel/sorter: raw bilingual university content -> taxonomy -> RAG index and
  regulatory subset.
- Highlight the 935 regulatory chunks as the event-pipeline input.

Speaker point:

- "If formal rules and casual announcements are mixed together, a RAG system can
  retrieve text, but an event system can create bad obligations. Taxonomy is the
  guardrail before intelligence."

### 5. System Architecture

Claim: Orbis is a connected system, not a single prompt.

On slide:

- React/Vite frontend.
- FastAPI backend.
- PostgreSQL + pgvector.
- RAG path.
- Event extraction path.
- Submission review path.

Visual:

- Architecture diagram: inputs left, backend center, storage bottom, outputs
  right.
- Use the same color schema from the design system.

Speaker point:

- "The database is not just storage. It is the shared memory for evidence,
  embeddings, rules, assignments, logs, and submission decisions."

### 6. Pull Path: Grounded RAG Search

Claim: RAG is the safety net for questions, but it is intentionally not the
whole product.

On slide:

- Query -> retrieval -> reranking -> grounded answer.
- Sources are shown with evidence.
- Works when the student knows the question.
- Limitation: pull mode cannot discover unknown obligations.

Visual:

- Query card connected to pgvector retrieval, source snippets, and answer card.
- A small warning label: "Helpful, but reactive."

Speaker point:

- "RAG solves the lookup problem. It does not solve timing or personalization by
  itself, so Orbis adds the event pipeline."

### 7. Push Path: Extracting Actionable Obligations

Claim: The event pipeline converts regulation prose into strict, assignable
obligations.

On slide:

- 935 regulatory chunks processed.
- 323 candidate rules evaluated.
- Two-pass adversarial review.
- 178 accepted obligations.
- 145 rejected quality candidates.

Visual:

- Horizontal pipeline: regulatory chunks -> candidates -> adversarial review ->
  accepted obligations.
- Quality gate showing accepted versus rejected.
- "Strict obligation" example card with trigger, audience, deadline, evidence.

Speaker point:

- "The 45 percent rejection rate is not failure. It is the specificity filter
  doing its job: avoid notifying students about vague awareness-only text."

### 8. Personalization: Matching Obligations To Profiles

Claim: The hardest layer is deciding which accepted obligations apply to which
student.

On slide:

- 4 student profiles.
- SQL path for deterministic thresholds.
- Contextual path for situation-aware rules.
- 176 assignments generated.
- Weakest evaluated layer: F1 0.514.

Visual:

- Four profile cards feeding into two matching paths: SQL and contextual LLM.
- Output assignment cards with urgency labels.
- Show one concrete example: internship form obligation for an internship
  profile.

Speaker point:

- "Extraction asks: is this a real obligation? Matching asks: is this obligation
  for this student? That second question is more context-sensitive and produced
  our clearest improvement target."

### 9. Submission Review Agent

Claim: Submission review uses AI as a requirement checker, not as a grader.

On slide:

- Deterministic file gate.
- Requirement decomposition.
- Evidence-based judgment.
- Approve/reject with appeal path.
- Prompt-injection tested.

Visual:

- Uploaded file -> file checks -> requirements -> evidence match -> decision.
- Show prompt-injection text blocked by requirement checking.
- Highlight "Screening, not grading."

Speaker point:

- "The submitted document is treated as evidence, not instruction. Approval
  depends on assignment requirements, not on what the file tells the model to
  do."

### 10. Evaluation: What The Evidence Says

Claim: The results validate parts of the design and expose the weakest layer.

On slide:

- Event extraction: P 0.978, R 0.574, F1 0.723.
- Assignment matching: P 0.608, R 0.446, F1 0.514.
- Submission review: Acc 93.8%, Recall 1.000, F1 0.889.
- Injection cases rejected: 4/4 tested cases.
- Design conclusion: precise extraction, weak matching, strong screening.

Visual:

- Three metric cards, each tied to a design question:
  - "Can we avoid bad obligations?"
  - "Can we assign them correctly?"
  - "Can we screen submissions safely?"
- Use a small caveat badge: "tested cases only" for injection resistance.

Speaker point:

- "The point is not that every number is perfect. The point is that every
  subsystem is measurable, and the measurements tell us exactly where the next
  engineering work should go."

### 11. Risks, Roadmap, And Demo

Claim: Orbis is useful because it is inspectable, and future work follows
directly from measured risks.

On slide:

- Risks: wrong advice, missed obligations, stale regulations, privacy, prompt
  injection.
- Mitigations: source evidence, audit logs, dismiss/action states, appeal path.
- Roadmap: SIS integration, human review queue, stronger matching recall,
  explicit flag-for-review class.
- Demo path: ask -> obligation -> submit.

Visual:

- Left: compact risk-to-mitigation matrix.
- Right: three-step demo storyboard.
- Closing sentence large: "Proactive, inspectable, measurable academic support."

Speaker point:

- "The final system is not a black box oracle. It is a measured support layer
  whose outputs can be traced, challenged, and improved."

## Suggested Speaker Split

Arda:

- Slide 1 opening sentence with Atakan.
- Slide 4 Data Foundation And Taxonomy.
- Slide 5 System Architecture, especially PostgreSQL/pgvector and data layout.
- Slide 6 Pull Path: Grounded RAG Search.

Atakan:

- Slide 2 Problem.
- Slide 3 Design Requirements And Boundaries.
- Slide 7 Push Path: Event Extraction.
- Slide 8 Personalization.
- Slide 9 Submission Review Agent.
- Slide 10 Evaluation.
- Slide 11 Risks, Roadmap, Demo close.

If time feels tight, combine Slide 6 and Slide 7 into one "Pull vs Push" slide
and keep the same narrative.

## Timing Guide

- Slide 1: 35 seconds
- Slide 2: 55 seconds
- Slide 3: 55 seconds
- Slide 4: 70 seconds
- Slide 5: 65 seconds
- Slide 6: 55 seconds
- Slide 7: 75 seconds
- Slide 8: 70 seconds
- Slide 9: 65 seconds
- Slide 10: 80 seconds
- Slide 11: 80 seconds

Total: about 10 minutes.

## Wording Caveats

Avoid overclaiming:

- Do not say Orbis replaces academic advisors.
- Do not say submission review grades student work.
- Do not claim general prompt-injection security; say tested injection cases.
- Do not hide that assignment matching is the weakest evaluated layer.

Ground-truth wording:

- Use "labeled evaluation set" or "validated evaluation set" unless the team is
  fully comfortable defending "human-validated gold ground truth" in Q&A.

## One-Sentence Ending

Orbis shows that academic advising can move from static lookup to proactive,
inspectable, and measurable support by combining RAG, regulation extraction,
profile-aware matching, and auditable submission review.
