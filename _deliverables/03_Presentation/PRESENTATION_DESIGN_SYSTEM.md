# Orbis Presentation Design System

Use this design system as the inherited base for every slide. The goal is for
the presentation to feel like one coherent engineering artifact, not ten
separate generated images.

## Master Prompt Prefix

Prepend this to every slide-generation prompt:

> Create a 16:9 CMPE 492 engineering presentation slide for the Orbis project. Use the shared Orbis visual system: warm white background, dark ink text, Orbis blue for system structure, teal for AI/RAG modules, gold for student-facing actions, green for success/accepted states, red for risk/error states, and light gray for neutral source/data blocks. Use a consistent top title bar, subtle slide number in the bottom right, thin line dividers, 8px-radius cards, and simple line icons. Keep typography clean and readable: title 34-40 pt, section labels 22-26 pt, body labels at least 20 pt. Avoid dense paragraphs, decorative gradients, abstract blobs, heavy shadows, and inconsistent colors. All diagrams should use the same meaning for the same color across slides.

## Color Tokens

| Token | Hex | Meaning |
| --- | --- | --- |
| Background | `#F8FAFC` | Slide background |
| Panel | `#FFFFFF` | Cards, metric tiles, diagram panels |
| Ink | `#1F2933` | Main text |
| Muted Text | `#64748B` | Secondary labels |
| Line | `#CBD5E1` | Connectors, dividers, borders |
| Orbis Blue | `#2563A9` | Core system, backend, architecture frame |
| RAG Teal | `#0F766E` | AI/RAG/LLM components |
| Action Gold | `#B7791F` | Student-facing actions and notifications |
| Success Green | `#2F855A` | Accepted, correct, approved, completed |
| Risk Red | `#B42318` | Risks, failures, blocked/rejected states |
| Neutral Gray | `#E2E8F0` | Raw sources, inactive paths, background structure |

Do not let the deck become a single-hue blue/teal deck. Use gold, green, red,
and neutral gray meaningfully.

## Layout System

- Canvas: 16:9 widescreen.
- Safe margins: 48 px left/right, 36 px top/bottom.
- Header: slide title on the top left; optional short section tag on the top right.
- Footer: small `Orbis | CMPE 492` on the bottom left and slide number on the bottom right.
- Body grid: prefer either a 2-column layout or a 3-card row; keep alignment consistent.
- Card radius: 8 px maximum.
- Stroke width: 1.5-2 px for diagrams and cards.
- Use whitespace as structure; do not fill every corner.

## Typography

- Use a modern sans-serif such as Inter, Aptos, Calibri, or Arial.
- Title: 34-40 pt, semibold.
- Main metric numbers: 34-44 pt, bold.
- Body labels: 20-24 pt.
- Captions/footnotes: 14-16 pt only when necessary.
- No negative letter spacing.
- Use sentence case for slide titles and labels.

## Diagram Color Schema

Use the same color meanings everywhere:

- University sources, PDFs, announcements: neutral gray.
- Database/storage/PostgreSQL/pgvector: Orbis Blue.
- RAG, retrieval, LLM, extraction, reviewer agents: RAG Teal.
- Student profile, notifications, assignments, demo actions: Action Gold.
- Approved/accepted/correct: Success Green.
- Rejected/risk/error/prompt injection: Risk Red.
- Connectors and secondary structure: Line.

## Diagram Precision Rules

The presentation diagrams must be implementation-aware. Avoid generic boxes
such as "AI engine", "database", "backend", or "LLM" when a real Orbis module,
route, table, or stage is known.

Use precise labels where they fit:

- Frontend: `React/Vite student shell`
- Backend routes: `/chat`, `/search`, `/events/trigger`, `/events/runs/{id}`,
  `/regulations/me`, `/regulations/assignments/{id}`,
  `/assignments/{id}/submit/stream`
- RAG modules: `RAGService`, `route_query`, `execute_sql_intent`,
  `execute_vector_intent`, `VectorSearchRepository`, `rerank_docs`,
  `build_context`, `stream_answer`
- Event modules: `EventPipelineOrchestrator`, `SearchAgent`,
  `ReasoningAgent`, `EventCreator`, `ReasoningReviewer`
- Submission modules: `evaluate_submission`, `stream_submission_evaluation`,
  deterministic file gate, requirement decomposition, verdict prompt,
  fallback decision
- Tables/stores: `knowledge_base`, `knowledge_base_embeddings`,
  `event_runs`, `event_agent_logs`, `event_candidate_logs`,
  `regulation_rules`, `user_rule_assignments`, `assignment_submissions`

Every detailed system diagram should show:

- exact direction of data flow;
- at least one route or function/module name;
- at least one persistent table or artifact name;
- where evidence/source text enters the decision;
- where the student sees the output;
- what is logged or auditable.

Do not use vague cloud icons, unlabeled arrows, or decorative "AI brain"
diagrams without data flow. If an AI component appears, label what it receives,
what it returns, and where the result is stored or shown.

## Component Rules

- Metric tiles: white card, thin line border, large number, tiny metric label.
- Architecture blocks: rounded rectangles with icons and short labels.
- Pipeline stages: left-to-right arrows with numbered checkpoints.
- Risk rows: compact matrix, red risk label, blue/teal mitigation, gold future action.
- Screenshots/mockups: place inside a light frame with a title strip; do not overdecorate.
- Use icons sparingly and consistently: database, document, search, brain/AI, bell, shield, check, warning.

## Slide Type Templates

Title slide:

- Large project name on left.
- Product/dashboard mockup on right.
- Small pipeline ribbon under the subtitle.

Problem slide:

- Fragmented source map.
- Student/action gap in the center.
- Minimal text.

Architecture slide:

- Inputs left, backend center, storage bottom, outputs right.
- Follow the diagram color schema.

Data/taxonomy slide:

- Funnel or sorter.
- Large numbers as metric tiles.
- Highlight the regulatory subset.

Pipeline slide:

- Horizontal process.
- Quality gate visually distinct.
- End with a student notification/action.

Evaluation slide:

- Three metric cards.
- Explicitly mark strongest and weakest subsystem.
- Use the risk color only for the weakness, not for every low value.

Risk/future slide:

- Matrix with risk, current mitigation, future work.
- Keep it calm and engineering-focused.

Demo slide:

- Three-step storyboard.
- Use actual screenshots when possible.

## Consistency Checks

Before finalizing the deck, check:

- Same title placement across all slides.
- Same colors mean the same thing across all diagrams.
- Every slide can be read from the back of a classroom.
- No slide contains report-style paragraphs.
- Report2-only risks/constraints appear in the risk slide, not scattered everywhere.
- Metrics use the same labels and decimal precision across the deck.
