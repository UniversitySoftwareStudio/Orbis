# Presentation

Moodle artifact: `CMPE492-Presentation`

Required filenames:

- `121200152_Atakan_Gul_presentation.pdf`
- `122200045_Arda_Kaan_Yildiz_presentation.pdf`

Accepted format:

- PDF or PowerPoint (`.pptx`), but PDF is safest for venue compatibility.

Presentation constraints:

- 10 minutes maximum.
- 5 minutes Q&A.
- 10-11 slides maximum.
- Font size at least 20 pt.
- All team members must participate.

Deck planning files:

- `PRESENTATION_FLOW.md`: detailed 11-slide narrative arc.
- `PRESENTATION_DESIGN_SYSTEM.md`: shared colors, typography, layout, and
  diagram precision rules.
- `USE_CASE_NARRATIVE_SPINE.md`: clean problem/objective/flow/theory/findings
  structure for RAG, regulation events, and assignment submission review.
- `SLIDE_GENERATION_PROMPTS.md`: generator-ready prompts with exact visuals,
  routes, services, tables, metrics, and diagram content.

Current state:

- Generated PPTX/PDF attempts, preview images, rendered slide assets, and build
  scripts were removed.
- Only the planning/reference documents are kept here for reuse.
- A new final presentation should be built from the narrative, design system,
  use-case spine, and slide prompts listed above.

Recommended narrative:

1. Title and thesis
2. Problem: information exists, guidance does not
3. Design requirements and safety boundaries
4. Data foundation and taxonomy
5. System architecture
6. Pull path: grounded RAG search
7. Push path: extracting actionable obligations
8. Personalization: matching obligations to profiles
9. Submission review agent
10. Evaluation: what the evidence says
11. Risks, roadmap, and demo

Diagram rule:

- Do not use generic architecture diagrams. Use implementation-aware diagrams
  with exact Orbis routes, modules, tables, data flow, evidence flow, and
  logged/auditable outputs.
