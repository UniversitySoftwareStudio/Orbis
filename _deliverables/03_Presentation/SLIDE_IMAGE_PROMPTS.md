# Orbis — Full-Slide Image Prompts (Google Slides + Infographic)

Each slide below is generated as **one full 16:9 image**, then dropped into a
Google Slides page. Every prompt = the shared **BASE TEMPLATE PROMPT** (paste
first, every time) + the **PER-SLIDE PROMPT** (paste after).

Rules baked into every prompt: clean professional template, no distracting
background, all on-slide text ≥ 20 pt equivalent and readable from the back of a
room, bullet-style (no paragraphs), one consistent color meaning across slides.

**Every quoted string in `"..."` must appear on the slide EXACTLY, character for
character. Do not paraphrase numbers.**

---

## BASE TEMPLATE PROMPT  (prepend to EVERY slide)

> Create one 16:9 widescreen presentation slide, flat vector infographic style,
> clean and professional. This is a slide for the Orbis project (a university
> CMPE 492 senior-design system). IMPORTANT: the ONLY heading on the slide is the
> exact "Title bar text" given in the per-slide prompt — do NOT invent a title,
> do NOT use this description as a heading, do NOT write the words "university
> senior-design project" anywhere on the slide.
> Background: solid warm white #F8FAFC, no gradients, no photos, no decorative
> blobs, no drop shadows. Text color dark ink #1F2933; secondary labels gray
> #64748B; thin divider/borders #CBD5E1. Cards are white #FFFFFF rounded
> rectangles, 8px corners, 1.5px border. Use a modern sans-serif (Inter/Arial).
> Color meaning is FIXED across all slides: Orbis blue #2563A9 = system/backend/
> database; teal #0F766E = AI/RAG/LLM; gold #B7791F = student-facing action/
> notification; green #2F855A = accepted/correct/approved; red #B42318 = risk/
> rejected/error; neutral gray #E2E8F0 = raw sources/data. Layout: a thin top
> title bar with the slide title on the top-left, a small "Orbis | CMPE 492"
> tag bottom-left, and the slide number bottom-right. Generous whitespace.
> Title ~36pt, body labels ≥20pt, big metric numbers bold. Reproduce all
> provided text EXACTLY; do not invent extra text, do not translate, do not
> change any number. Use clean line icons next to stages where they aid meaning
> (database, funnel, document, web page, PDF, shield/guardrail, router, brain/AI,
> bell, check, warning); icons support the labels, they never replace required
> text. Where a slide marks itself a "detailed" or "showcase" slide, density is
> intended — fill the canvas and show every stage rather than simplifying.

---

## SLIDE 1 — Title

**Title bar text:** none (this is the cover; project name is the hero).
**Slide number:** 1

PER-SLIDE PROMPT:

> Title / cover slide. LEFT 55% of the canvas: very large product wordmark
> "Orbis" (≈80pt, Orbis blue), and directly under it the subtitle
> "An Intelligent Academic Support System with AI and RAG" (≈26pt, dark ink).
> Below the subtitle, a thin horizontal divider, then four stacked small lines
> (≈20pt): "Atakan Gül — 121200152", "Arda Kaan Yıldız — 122200045",
> "Supervisor: Özgür Özdemir",
> "Istanbul Bilgi University · Faculty of Engineering and Natural Sciences · CMPE 492 · June 2026".
> RIGHT 45%: a simple horizontal 3-step ribbon of three rounded cards connected
> by arrows: card 1 neutral-gray labeled "University sources", arrow, card 2
> blue labeled "Orbis", arrow, card 3 gold labeled "Student action". Under the
> ribbon, one italic tagline (≈22pt, gray):
> "Turning scattered information into actionable, traceable guidance."
> Keep it calm and uncluttered.

---

## SLIDE 2 — Problem Statement

**Title bar text:** "The problem: information exists, guidance does not"
**Slide number:** 2

PER-SLIDE PROMPT:

> Problem slide, two zones.
> LEFT: a "fragmented source map" — five small neutral-gray cards scattered (not
> aligned in a neat grid, slightly offset to feel fragmented), each with a tiny
> line icon and a label: "SIS", "Course catalog", "Regulation PDFs",
> "Announcements", "Student handbook".
> CENTER-RIGHT: a single gold circle labeled "Student", with TWO red dashed
> arrows pointing away from it toward empty space, each arrow labeled with a
> question in a red-bordered tag: arrow 1 = "What applies to me?",
> arrow 2 = "When should I act?".
> BOTTOM strip: four short bullet lines (≈20pt, dark ink), each with a small
> gray dot:
> "Rules are scattered across many systems",
> "Students don't always know what to ask",
> "Portals store records, they don't interpret them",
> "The hardest obligations are the ones you never think to ask about".
> Minimal text, lots of whitespace. The visual must communicate fragmentation +
> two missing bridges.

---

## SLIDE 3 — Methodology / Approach  (FULL END-TO-END SYSTEM SHOWCASE)

**Title bar text:** "Methodology — from data collection to student action"
**Slide number:** 3

> NOTE: This is the SHOWCASE slide. Use the ENTIRE canvas, edge to edge, every
> pixel. It is a single connected pipeline read LEFT → RIGHT in four bands:
> (A) Data collection & ingestion, (B) Taxonomy guardrail, (C) Shared store,
> (D) Three runtime paths → student outputs. Dense is GOOD here. The infographic
> engine is capable of complex multi-stage flow diagrams — produce a rich,
> detailed, professional system map, not a simple 3-card layout. Connect every
> stage with directional arrows so data visibly flows through the whole system.
> Reproduce every quoted number and label EXACTLY.

PER-SLIDE PROMPT:

> One large, detailed left-to-right system pipeline infographic filling the whole
> 16:9 canvas. Four vertical bands separated by thin dividers, data flowing left
> to right with arrows crossing every boundary. Use line icons on stages. CRUCIAL:
> this slide must show not only WHAT each stage is but the KEY DESIGN DECISION
> behind it — render each decision as a tiny italic gray "why" annotation tag
> attached under its stage. Reproduce every quoted string exactly.
>
> BAND A — "1 · Data collection & ingestion" (neutral gray, far left, with a
> web-page icon and a PDF icon on the sources):
> source chips "80 official bilgi.edu.tr URLs", "~12,600 web pages", "~2,245 PDFs".
> Stage "Crawl + filter (filter_pdfs.py)" note "1,595 kept · 315 discarded · 335 archived"
> why-tag "tenders & result lists look like rules — excluded by URL + keyword".
> Stage "Stopword-race language detect (≈65% TR / 35% EN)"
> why-tag "char-frequency failed on local addresses → count stopwords instead".
> Stage "Semantic chunking — 150-word chunks, 30-word overlap"
> why-tag "overlap preserves cross-sentence rules".
> Stage "MiniLM embed → 384-dim vectors (enriched: title + breadcrumb prepended)"
> why-tag "encode topic + category in one vector".
> Output arrow labeled "60,649 raw chunks".
>
> BAND B — "2 · Taxonomy guardrail (4 steps)" (teal accents, shield icon on the
> band header): a vertical numbered 4-step flow, each with a why-tag:
> "Step 1 — URL rule engine (semantic vs dynamic ratio)"
> why-tag "reject UUID / high-dynamic groups".
> "Step 2 — Shannon-entropy tail signal → 74 KNOWN / 31 UNKNOWN groups"
> why-tag "low entropy = one template = dynamic; high entropy = real directory".
> "Step 3 — MiniBatchKMeans + Ward HAC on 21,324 unknown docs → 52 clusters"
> why-tag "O(n) clustering scales to 60k+ chunks".
> "Step 4 — LLM taxonomy mapping → 11 top categories · 125 leaves".
> End with a highlighted teal box "Regex overlay → 935 regulatory chunks (29 leaves)"
> why-tag "separate binding rules from noise BEFORE any AI runs — bad taxonomy = bad obligations".
>
> BAND C — "3 · Shared store" (Orbis blue, center spine, database-cylinder icon):
> blue cylinder "PostgreSQL + pgvector" with index chips
> "HNSW (vector, L2 distance)" why-tag "approx. nearest-neighbour, tuneable recall/speed"
> and "GIN (keyword TSVECTOR, TR/EN stemming)" why-tag "sub-ms full-text at 60k+ rows".
> Note "one DB = shared memory for evidence, rules, assignments, logs".
> Arrows fan out to all three lanes.
>
> BAND D — "4 · Three runtime paths → student" (far right, three stacked lanes,
> each with a why-tag on its key decision):
> LANE 1 (teal, search icon) "PULL · RAG chatbot":
> "Router (4 tools: vector/sql/calendar/schedule)" → "Hybrid search TOP_K=30 (keyword-first merge)"
> why-tag "keyword matches first = precision, vector fills recall" →
> "2-stage Jina rerank + Smart Context Expansion → FINAL_K=10"
> why-tag "pre-expansion rerank keeps quality; post-expansion rebuilds full regulation" →
> "Streamed grounded answer (cited)".
> LANE 2 (gold, bell icon) "PUSH · Event pipeline":
> "Orchestrator + SearchAgent / ReasoningAgent / EventCreator"
> why-tag "central orchestrator owns state; workers stateless = idempotent" →
> "Two-pass adversarial review" why-tag "pass 2 removes stale/weak rules" →
> "178 obligations" → "SQL + contextual matching → 176 assignments (My Regulations)"
> why-tag "SQL for thresholds (fast/cheap); LLM for situational context".
> LANE 3 (green, shield-check icon) "REVIEW · Submission agent":
> "File gate (no LLM)" why-tag "reject empty/corrupt/oversized without spending an LLM call" →
> "Decompose requirements (LLM call 1)" → "Judge each requirement w/ evidence (LLM call 2)"
> why-tag "document is evidence, not instruction → resists prompt injection" →
> "Approve / reject + appeal (flag_for_review)" why-tag "false rejection must not end a student's chance".
> All three lanes converge with arrows into ONE single gold "Student" node on the
> far right (do not draw two separate student nodes).
>
> BOTTOM full-width thin strip, TWO lines (≈16pt, gray):
> Line 1: "Process: iterative / Agile — incremental sprints · GitHub PR review · build subsystem → evaluate → refine".
> Line 2: "Stack: React/Vite · FastAPI · PostgreSQL + pgvector   |   Contributions: Arda — scraping & RAG chatbot · Atakan — events, matching, submission agent   |   Full pipeline: 80 sources in 59 min".
> Keep arrows clean, band headers bold, and every why-tag small and italic so the
> stages stay primary. This is the intentionally detailed full-system showcase.

---

## SLIDE 4 — System Design / Architecture  (COMPONENT & TECHNOLOGY VIEW — detailed)

**Title bar text:** "System architecture — components & technologies"
**Slide number:** 4

> NOTE: This slide is the COMPONENT/TECH view and must be visibly DIFFERENT from
> Slide 3 (which is the data-flow showcase). Here, show a layered architecture
> stack — Client → API → Services → Data/Infra — with the REAL technology behind
> each box (frameworks, models, providers, indexes, tables). Fill the canvas;
> this is a detailed engineering diagram. Reproduce every quoted string exactly.

PER-SLIDE PROMPT:

> A layered system-architecture diagram with FOUR horizontal tiers stacked top to
> bottom, each tier a labeled band of component cards, with a thin vertical
> "request flow" arrow on the left spanning all tiers and a "streamed response
> (SSE)" arrow on the right going back up. Use the fixed color meaning. Put a
> small technology chip under each component.
>
> TIER 1 — "Client" (gray band): one card "React / Vite student shell" with
> sub-chips "Chatbot", "Dashboard", "My Regulations", "Submission review".
> Tech chip "Server-Sent Events (token streaming)".
>
> TIER 2 — "API — FastAPI (Python 3.10, Uvicorn)" (blue band): a row of route
> cards in monospace: "/api/chat", "/api/search", "/api/events/trigger",
> "/api/regulations/me", "/api/assignments/{id}/submit/stream",
> "/api/sis/* (calendar, schedule)". Tech chip "JWT auth · async dispatch".
>
> TIER 3 — "Services / AI" (three colored component cards side by side):
> CARD A (teal) "RAG service": chips "Router LLM — Groq llama-3.3-70b",
> "Hybrid search", "Jina reranker v2 (cross-encoder)",
> "Smart Context Expansion", "context_injectors.py (SIS)".
> CARD B (gold) "Event service": chips "EventPipelineOrchestrator",
> "SearchAgent / ReasoningAgent / EventCreator", "two-pass LLM review",
> "SQL + contextual matcher".
> CARD C (green) "Submission service": chips "deterministic file gate",
> "evaluate_submission", "two-call LLM reviewer", "flag_for_review".
> Under this tier a small note: "LLM providers: Groq · Google Gemini · OpenAI-compatible (env-selectable)".
>
> TIER 4 — "Data & infrastructure" (blue band): on the left a large database
> cylinder "PostgreSQL + pgvector" with two index chips
> "HNSW index (vector, 384-dim, L2)" and "GIN index (TSVECTOR, TR/EN stemming)";
> beside it a column of table chips in monospace (≈16pt):
> "knowledge_base", "knowledge_base_embeddings", "regulation_rules",
> "user_rule_assignments", "assignment_submissions", "event_runs",
> "event_candidate_logs", "event_agent_logs".
> To the right, an "Embedding infra" card: chips
> "MiniLM paraphrase-multilingual-L12-v2 (384-dim)",
> "TEI container + Nginx load-balance", "local Hugging Face fallback".
>
> BOTTOM caption strip (≈18pt, gray, full width):
> "One PostgreSQL + pgvector instance is the shared memory for all three paths — relational schema and vector index in the same database".
> Keep tiers clearly separated, technology chips small under each component, and
> the request-down / SSE-response-up arrows visible. Detailed engineering view.

---

## SLIDE 5 — Implementation & Challenges

**Title bar text:** "Implementation & challenges"
**Slide number:** 5

> NOTE: Detailed slide. Top shows the SDP II progress; below it a dense
> challenge→resolution matrix with concrete evidence. Reproduce numbers exactly.

PER-SLIDE PROMPT:

> Implementation-and-challenges slide in two zones.
>
> TOP ZONE — "Progress in Senior Design Project II" (thin blue band): a compact
> horizontal checklist of six green-checked items (≈18pt):
> "Backend + all API routes completed", "Taxonomy pipeline (125 leaves)",
> "RAG chatbot end-to-end", "Event pipeline + matching",
> "Submission review agent", "Gold-label evaluation harness".
> Tiny note on the right: "built on the S1 foundation: scraping, embedding choice, DB".
>
> BOTTOM ZONE — a challenge→resolution matrix: FIVE rows, each three linked cells:
> a left RED-bordered "Challenge" card, a center GREEN-bordered "How we solved it"
> card, and a small right gray "Evidence" chip. Text ≈18-20pt, alignment perfectly
> consistent.
> Row 1 — Challenge "Formal rules mixed with casual news/announcements" |
> Solved "4-step taxonomy guardrail isolates rules before any AI runs" |
> Evidence "935 regulatory chunks / 60,649".
> Row 2 — Challenge "Vague, non-actionable obligations" |
> Solved "Two-pass adversarial LLM review (pass 2 removes stale/weak rules)" |
> Evidence "55% accepted · 45% rejected by design".
> Row 3 — Challenge "65% of corpus is temporal news/events drowning answers" |
> Solved "Keyword-first hybrid search + 2-stage Jina rerank + Smart Context Expansion" |
> Evidence "0 temporal contamination in final context".
> Row 4 — Challenge "Multi-article regulations fragmented across 150-word chunks" |
> Solved "Smart Context Expansion rebuilds full source document around top hits" |
> Evidence "8-step grade-appeal procedure recovered from 4 chunks".
> Row 5 — Challenge "Prompt injection hidden inside uploaded files" |
> Solved "Two-call reviewer treats document as evidence, not instruction" |
> Evidence "injection resistance 1/4 → 4/4".
> BOTTOM, one full-width gray strip with a small shield icon (≈18pt):
> "Every decision is logged and auditable (event_candidate_logs · event_agent_logs)".
> Use RED only on the Challenge card borders.

---

## SLIDE 6 — Results & Testing (1/2): RAG + extraction + matching

**Title bar text:** "Results & testing — search, extraction, matching"
**Slide number:** 6

> NOTE: This is a DENSE data slide. Every number below must appear EXACTLY.
> Lay it out as a tight 2-row grid of cards; small fonts are acceptable here
> (down to ~16pt for stat labels) but every digit must remain legible. Do not
> drop, round, or merge any value. If the generator cannot fit all text, prefer
> shrinking whitespace over deleting numbers.

PER-SLIDE PROMPT:

> Dense evaluation dashboard slide. Arrange FOUR cards: a wide top card spanning
> full width, then a row of THREE cards beneath it.
>
> TOP WIDE CARD (teal heading "RAG chatbot — 100-query bilingual benchmark, 7 routing categories"):
> a single row of four big bold stats with labels under each:
> "92.3%" label "Routing accuracy", "94.7%" label "Context recall",
> "0.94" label "MRR", "97.6%" label "Semantic accuracy".
> To the right of those, a thin separated sub-box (gray heading "Embedding benchmark"):
> two small stats "70.8%" label "Best top-3 (TEI MiniLM, 100-word)" and
> "0.571" label "Best MRR", with a tiny note "justifies model + chunk size".
>
> BOTTOM-LEFT CARD (teal heading "Event extraction", sublabel "323 candidates · gold-labeled"):
> a row of four stats "0.978" label "Precision", "0.574" label "Recall",
> "0.723" label "F1", "0.588" label "Accuracy". Under them a tiny 2x2 confusion
> grid labeled "Confusion (N=323)": top row "Accept" cells "174 TP" (green) and
> "4 FP" (red); bottom row "Reject" cells "129 FN" (red) and "16 TN".
> Add a small green tag "Very precise — avoids bad obligations".
>
> BOTTOM-CENTER CARD (gold heading "Assignment matching", sublabel "712 pairs = 4 profiles × 178 obligations"):
> a row of three stats "0.608" label "Precision", "0.446" label "Recall",
> "0.514" label "F1". Below, a tiny 4-row table headed "Per profile (P / R / F1)":
> "P1" "0.548 / 0.469 / 0.505",
> "P2" "0.667 / 0.358 / 0.466",
> "P3" "0.650 / 0.500 / 0.565",
> "P4" "0.553 / 0.457 / 0.500".
> Add a RED tag "Weakest layer — clear next target".
>
> BOTTOM-RIGHT CARD (blue heading "Pipeline funnel"):
> a vertical mini-funnel of five stacked rows, each "number — label":
> "80 — sources (run in 59 min)", "935 — KB chunks consumed",
> "323 — candidate rules", "178 — accepted (55%)" (green),
> "145 — rejected (45%)" (gray, note "specificity filter").
>
> BOTTOM caption strip (≈16pt, gray, full width):
> "All scored against author-validated gold ground truth (323 candidates + 712 pairs manually labeled)".
> Use RED only on: the 4 FP / 129 FN confusion cells and the matching weakness tag.

---

## SLIDE 7 — Results & Testing (2/2): submission review + safety

**Title bar text:** "Results & testing — submission review & safety"
**Slide number:** 7

> NOTE: Dense data slide. Reproduce every number EXACTLY; do not round or drop.

PER-SLIDE PROMPT:

> Dense evaluation slide for the submission-review subsystem. Arrange FOUR cards
> in a 2x2 grid.
>
> TOP-LEFT CARD (green heading "Submission review", sublabel "32 cases = 4 assignments × 8 strata"):
> four big stats in a 2x2 mini-grid: "93.8%" label "Accuracy",
> "1.000" label "Recall", "0.889" label "F1", "0.800" label "Precision".
> Below them a tiny 2x2 confusion grid labeled "Confusion (N=32, positive=approve)":
> top row "Approve gold" cells "8 TP" (green) and "0 FN" (green);
> bottom row "Reject gold" cells "2 FP" (red) and "22 TN".
> Add a small green tag "Zero false negatives — no genuine work rejected".
>
> TOP-RIGHT CARD (blue heading "How we tested — 8 strata (4 each)"):
> a two-column checklist; mark the green-correct ones "4/4" and the imperfect one
> in red. Rows (label — score):
> "approve — 4/4", "approve multi-file — 4/4", "reject wrong content — 4/4",
> "reject wrong extension — 4/4", "reject empty — 4/4", "reject corrupt — 4/4",
> "reject injection — 4/4", "flag partial — 2/4" (this last one red).
> Tiny note: "7 of 8 strata perfect".
>
> BOTTOM-LEFT CARD (blue heading "Ablation — single-call → two-call agentic"):
> a small before→after table, two metric rows:
> row "Accuracy": "0.781" arrow "0.938" (green up-arrow on the after value);
> row "Injection resistance": "1/4" arrow "4/4" (green up-arrow).
> Tiny note: "two-call agent verifies each requirement, bypassing embedded instructions".
>
> BOTTOM-RIGHT CARD (red-bordered heading "Prompt-injection resistance"):
> one very large stat "4 / 4" label "tested injection cases rejected", and below
> a gray caveat line "Directional finding — not a general security guarantee".
>
> BOTTOM caption strip (≈18pt, dark ink, full width):
> "Strong, safe screening; the only residual weakness is over-approving partial drafts (2/4)".
> Use RED only on: the "2 FP" confusion cell, the "flag partial — 2/4" row, and
> the injection card border.

---

## SLIDE 8 — Conclusion & Acknowledgments

**Title bar text:** "Conclusion"
**Slide number:** 8

PER-SLIDE PROMPT:

> Conclusion slide. TOP CENTER: one large banner line (≈30pt, dark ink with the
> key words colored): "From static lookup to proactive, inspectable, measurable
> support" (color "proactive" gold, "inspectable" blue, "measurable" green).
> MIDDLE: three short takeaway bullets (≈22pt) each with a green check icon:
> "Three paths shipped: grounded search, proactive obligations, submission review",
> "Boundaries kept: advisory not authoritative; screening not grading",
> "Every subsystem is measurable — results point straight at the next work".
> BOTTOM: a thin divider, then a small "Acknowledgments" label and one line
> (≈18pt, gray): "Supervisor Özgür Özdemir · Course coordinator Doç. Dr. Tuğba
> Dalyan · Istanbul Bilgi University".

---

## SLIDE 9 — Future Work & Recommendations

**Title bar text:** "Future work"
**Slide number:** 9

PER-SLIDE PROMPT:

> Future-work slide. Four equal rounded cards in a 2x2 grid, each with a line
> icon, a bold heading (≈22pt) and one subtext line (≈18pt):
> Card 1 (gold) heading "Improve matching recall", subtext "Recall-oriented second pass on the weakest layer".
> Card 2 (blue) heading "Live SIS integration", subtext "Replace synthetic profiles with real academic state".
> Card 3 (green) heading "Human review queue", subtext "Explicit flag-for-review class for partial/suspect work".
> Card 4 (red) heading "Broader safety testing", subtext "Injection patterns beyond the tested cases".
> Keep the grid perfectly aligned, lots of whitespace, no extra text.

---

## SLIDE 10 — Demo

**Title bar text:** "Demo"
**Slide number:** 10

> NOTE: This slide hosts an EMBEDDED YouTube video in Google Slides. The
> generated image is only the BACKGROUND FRAME — it must leave a large empty 16:9
> area where the real video player will be placed on top in Slides. Do NOT draw a
> fake video player, play button, or thumbnail inside that area; leave it as a
> clean empty placeholder rectangle. (Requires venue internet — keep a local MP4
> fallback ready.)

PER-SLIDE PROMPT:

> Demo slide built around an embedded video. Layout:
> LEFT ~68% of the canvas: a large empty rounded rectangle with a thin gray
> border and a faint centered label "video area" (this is a PLACEHOLDER ONLY —
> the real YouTube embed goes here in Google Slides; do not render any player UI,
> thumbnail, or play button).
> RIGHT ~32%: a vertical 3-step storyboard strip, three small stacked cards each
> with a number badge, heading, and one-line caption (≈18pt):
> Card 1 (teal, badge "1") heading "Ask", caption "Natural-language question → grounded, cited answer".
> Card 2 (gold, badge "2") heading "Obligation", caption "Personalized rule in My Regulations with its source".
> Card 3 (green, badge "3") heading "Submit", caption "Upload checked vs requirements → approve/reject + appeal".
> BOTTOM full-width line (≈26pt, bold, dark ink, centered):
> "Proactive, inspectable, measurable academic support".
> Keep the left video placeholder genuinely empty and clean.

---

## Notes for assembly in Google Slides

- Generate each image at 16:9 (1920×1080). Set Slides page size to 16:9 first.
- After inserting, **double-check every number against FLOW.md** — image
  generators sometimes alter digits. The quoted strings above are the source of
  truth.
- Keep the title-bar wording identical to the "Title bar text" line so the deck
  reads consistently.
## Slide 10 — embedded video setup (Google Drive, IMPORTANT)

The demo video is `_deliverables/05_Video/demo_video/orbis-demo.mp4`. Embed it
on Slide 10 via **Google Drive** (no YouTube):

  1. Upload `orbis-demo.mp4` to **Google Drive** (same account as the deck).
     Give it a moment to finish processing (Drive must transcode before it can
     play in Slides — large files take a few minutes).
  2. Share the file: right-click → Share → set "Anyone with the link" =
     **Viewer** (Slides will not play a Drive video the audience/account can't
     access).
  3. In Google Slides: Slide 10 → **Insert → Video → Google Drive** tab →
     select `orbis-demo.mp4` → Insert.
  4. Drag/resize the player over the empty "video area" placeholder in the
     background image.
  5. Format options → Video playback → set **play On click** (not autoplay) so
     you control timing; optionally trim start/end.

- **Present from live Google Slides, NOT the exported PDF** — a PDF cannot play
  video. The PDF is only for the Moodle submission (shows the placeholder).
- **Requires internet** to stream from Drive. Keep the **local `orbis-demo.mp4`
  on the laptop** (open in a browser tab/VLC) as an offline fallback if venue
  WiFi fails.
- This is separate from the 1-minute Moodle video deliverable
  (`studentid_name_surname_video.mpg`) — don't confuse the two.
