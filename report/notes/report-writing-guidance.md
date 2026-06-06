# Report writing guidance from sample reports

## Source set reviewed

I treated `report/reports/` as the local report-samples source. The folder contains six prior reports:

- `120200013_Hamza_Sallam_Report1 (1).pdf` - 43 pages. Strong full report sample for an AI/CV project.
- `2022-2023 - Feature Selection Optimization With Meta-heuristic Algorithms for Disease Classification (1) (3) (1).pdf` - 28 pages. Strong for literature/method breadth and results tables.
- `2022-2023 - AI Application to Art Therapy Using Drawings Of The HTP Test (5) (1).pdf` - 21 pages. Strong for honest dataset limitations and future work.
- `2022-2023 - Artifical Neural Network Based Netlist Generator (1) (3) (1).pdf` - 16 pages. Strong for implementation pipeline explanation with figures and algorithm/code listings.
- `117200061_burakcan_turkan_Report2 (2) (1).pdf` - 8 pages. A Report 2 constraints/risk/contribution report.
- `117200080_Muhammed_Sedef_Report2 (2) (1).pdf` - 11 pages. Another Report 2 constraints/risk/contribution report.

## What the school seems to expect

The samples are not written like product blog posts. They are written as engineering reports: formal title page, abstract or executive-style opening for full reports, table of contents, lists of figures/tables/abbreviations where relevant, numbered sections, evidence-heavy method descriptions, tables, figures, references, and a conclusion that restates measured achievements.

For a full project report, the expected spine is:

1. Title page with project title, authors, IDs, supervisor, faculty, degree, department, and date.
2. Abstract that states the problem, method, dataset/system scale, experiments, measured results, and future direction.
3. Table of contents, list of figures, list of tables, and list of abbreviations.
4. Introduction that explains the real-world problem, why it matters, what the project does, and how the rest of the report is organized.
5. Related Works or Literature Review that compares prior approaches with numbers, datasets, limitations, and the gap your project addresses.
6. Dataset/Data/System Inputs section with source, size, structure, splits/categories, preprocessing, limitations, and why the data is challenging.
7. Design/Methodology section with diagrams, algorithmic steps, implementation logic, and enough detail that the reader can reproduce the pipeline.
8. Experimental Setup section with programming language, frameworks, hardware/cloud/runtime, model/service choices, parameters, metrics, and test protocol.
9. Experiments and Discussion section that shows multiple experiments or evaluation scenarios, not just final numbers.
10. Results section with tables, figures, error analysis, benchmark comparison, and interpretation.
11. Realistic Constraints/Risks/Ethics section if this is the final combined report or if the instructor expects Report 2 content to be included.
12. Conclusion and Future Work that is specific, measured, and honest.
13. References in IEEE-like numeric style, with citations in the body.

For Report 2 style submissions, the samples become much narrower. They focus on `Realistic Constraints`, `Risk Analysis and Precautions/Changes`, `Contributions`, `Conclusion`, and `References`. The constraints section repeatedly includes social/environmental/economic impact, cost analysis, NSPE ethics, and IEEE/ISO software engineering standards.

## Repeated quality signals

Quantification is everywhere in the stronger reports. The school appears to reward numbers: dataset counts, train/test splits, page/record/image counts, model accuracies, precision/recall/F1, loss, runtime, cost, hardware prices, number of features, number of classes, number of experiments, and benchmark deltas.

Benchmark comparison matters. The Hamza sample does not just say "we built a model"; it names benchmark papers, repeats their experiments, reports their accuracies, and states exactly how much the project improved. The Feature Selection sample compares its method to previous published results. Our Orbis report should similarly define what baseline it beats: manual search, static chatbot/RAG answer, keyword rule extraction, or a non-agent assignment/submission workflow.

Figures and tables are treated as proof, not decoration. The samples use diagrams for workflow/design, tables for datasets and results, confusion matrices for errors, screenshots for deployed interfaces, and code/algorithm listings for key procedures. Orbis should add more tables and figures, especially for data ingestion, event extraction, assignment matching, and submission review.

The reports explain limitations without sounding weak. The HTP report directly says feature extraction cannot yet be scored because ground truth is missing. That is good academic behavior. Orbis should be similarly honest about generated test profiles, missing SIS integration, manual validation limits, and LLM nondeterminism.

The methodology must be operational. Good sections answer "what exactly did you do?" The Netlist sample breaks the project into dataset, object detection, node detection, OCR, and netlist generation. The Hamza sample gives model architectures, layers, epochs, dropout, optimizer, loss function, train/test split, and metrics. Orbis should do this for taxonomy generation, event extraction, assignment matching, submission review, and reviewer override/flagging.

Related work should be more than background. It should compare prior work on the same problem, then position Orbis. For Orbis this likely means academic advising systems, degree audit systems, student information systems, RAG chatbots in education, LLM agent workflows, rule extraction from policy documents, and human-in-the-loop review.

Claims need citations. The samples cite external facts, benchmark papers, datasets, standards, and tools. Any claim like "students miss deadlines", "static systems fail", "HermiOne lacks logical reasoning", or "AI reduces cognitive load" needs either a citation, direct evidence from Orbis testing, or softer wording.

## Sample-specific lessons

### Hamza full report

This is the best model for our final report. It has a clear problem, measurable motivation, benchmark papers, dataset tables, model architecture discussion, experimental setup, multiple experiments, final results, and future work. Its abstract is especially strong because it gives exact dataset sizes, exact models, benchmark accuracies, achieved accuracies, and improvement percentages.

Use this pattern for Orbis:

- Identify a concrete baseline.
- State the exact corpus size and exact evaluation set.
- Show each major experiment in a table.
- Add error analysis, not only success metrics.
- Explain why false positives/false negatives happen.

### Netlist generator report

This report is useful for implementation-heavy software projects. It breaks a complex pipeline into small subproblems and gives each step its own subsection. It also uses code snippets and algorithm blocks where the implementation is easiest to understand procedurally.

Use this pattern for Orbis:

- Separate ingestion, taxonomy, event extraction, assignment matching, and submission review.
- Add an algorithm block for the submission review agent.
- Add diagrams that show inputs, decisions, database writes, and human override/flag flow.
- Show real examples of accepted and rejected outputs.

### Feature Selection report

This report is strong on literature/method breadth and comparative tables. Its weakness is that some method explanations become long textbook summaries. The useful lesson is to compare many alternatives, but Orbis should avoid long generic explanations of AI/RAG and instead keep the theory tied to actual project choices.

Use this pattern for Orbis:

- Include comparative result tables.
- Compare deterministic SQL rules vs contextual LLM matching vs hybrid matching.
- Compare pre-agent submission validation vs agentic review.
- Avoid several pages of generic RAG explanation unless it directly supports design decisions.

### HTP report

This report is good at handling incomplete research honestly. It documents small datasets, preprocessing, class imbalance, and why some evaluation cannot be completed yet. It still presents partial experiments and clearly marks future work.

Use this pattern for Orbis:

- Be explicit about what is production-ready, prototype-only, and future integration.
- If SIS integration is not done, say it is future work.
- If submission review was evaluated manually or with sample documents only, say so.
- Do not overstate accuracy without a labeled evaluation set.

### Report 2 samples

The two Report 2 samples show that constraints and risks are not optional filler. They are expected to be structured and concrete. Cost analysis should include actual infrastructure/service/labor estimates. Risk analysis should name risks and mitigations. Standards should name specific NSPE and IEEE/ISO standards and connect them to the project.

Use this pattern for Orbis:

- Social impact: better advising access, reduced missed obligations, but risk of wrong advice.
- Environmental impact: less printed material and less duplicated administrative work, balanced against cloud/LLM compute cost.
- Economic impact: advising time saved, infrastructure/API cost, development labor.
- Ethics: student welfare, transparency, appeal/flagging, not hiding uncertainty, human review.
- Standards: IEEE/ISO/IEC 16085 for risk management, ISO/IEC/IEEE 29148 for requirements if used, ISO/IEC/IEEE 12207 for software lifecycle if relevant, assurance case standards if making safety/quality claims.

## Current Orbis report assessment

Current source: `report/report.tex`.

### Strengths

The current report now satisfies the sample-report pattern much better than the
initial draft. It has a compileable thesis structure, a category-based Related
Works section, dataset statistics, methodology diagrams, experiment tables,
quantitative evaluation, realistic constraints, cost analysis, and future work.

It also includes the project-specific numbers the samples reward: 60,649 chunks,
935 regulatory chunks, 323 candidate rules, 178 accepted obligations, 145
rejections, 176 generated assignments, 4 student profiles, 59 minutes runtime,
and 32 submission-review cases.

The Related Works section is now evidence-aware. It compares Orbis against RAG
academic chatbots, degree-audit systems, regulatory information extraction,
local HermiOne context, automated submission assessment, and LLM-as-a-judge
evaluation. The baseline-validity table is a good academic move because it
labels external comparisons as contextual or partial rather than claiming false
head-to-head wins.

The assignment submission agent is now represented as a concrete user-facing
workflow: deterministic file gate, text extraction, requirement decomposition,
per-requirement judgment, streamed evidence, approve/reject verdict, and
student flag-for-review path.

### Critical gaps

The biggest remaining gap is implementation-boundary clarity. The report's
regulation assignment metrics are based on preserved historical database
artifacts (`regulation_rules`, `user_rule_assignments`, and
`event_candidate_logs`), while the currently wired `/api/events/trigger` route
writes extraction output into `regulatory_events`. This does not invalidate the
metrics, but the report should be careful to call them evaluation artifacts and
not imply that the current API exposes a live `/api/events/assign/me` route.

The HermiOne comparison is still the softest external claim. It is carefully
worded as public behavior and lack of design-document access, which is fine, but
it would be stronger with a public source or screenshot.

The event labels are silver LLM labels, not human gold labels. The report
already says this, but the low inter-judge agreement (0.529 on 51 candidates)
should stay visible anywhere recall is discussed.

Submission injection resistance is only 4/4 tested cases. Keep it framed as a
directional finding for the tested payload family, not a general security
guarantee.

## What to add to make the Orbis report feel like the samples

### Required structural fixes

- Add or restore the required thesis style package at `report/styles/ibu-thesis.sty`, or switch to a compileable template used by the samples.
- Add `report/references.bib` and replace all uncited claims with proper `\cite{...}` references.
- Replace `fragments[cite: 4]` with a real citation or delete the citation marker.
- Add list of figures and list of tables if the template does not generate them automatically.
- Make sure every table and figure is referenced in the text.

### Evidence to collect

- Crawl summary: source URLs by category, crawl date, total pages/chunks, language split, deduplication count.
- Taxonomy output: top-level category counts, regulatory leaves, examples of correct and incorrect category mappings.
- Event extraction audit: sample of accepted obligations and rejected candidates with reasons.
- Assignment matching audit: a labeled set of student profiles and expected obligations, then precision/recall or at least manual correctness percentages.
- Submission review audit: sample assignment requirements, submitted files, agent reasoning steps, approval/rejection decision, and flag-for-review path.
- Runtime/cost: extraction time, matching time, API call count, estimated API cost, infrastructure cost.
- UI evidence: screenshots for assignments, submission modal, rejection modal with flag option, reviewer/admin view if available.

### Suggested revised outline

1. Abstract
2. Introduction
   - Problem: students miss obligations because rules are scattered and static.
   - Contribution: Orbis as proactive academic agent.
   - Research questions: extraction accuracy, assignment relevance, submission relevance review.
3. Related Works
   - Academic advising and degree audit systems.
   - RAG chatbots for student support.
   - LLM agents and tool/orchestrator workflows.
   - Policy/rule extraction from unstructured documents.
4. Data Collection and Knowledge Base
   - Crawling, chunking, deduplication, language handling, regulatory subset.
5. System Design
   - Backend/frontend architecture.
   - Database and vector search.
   - Orchestrator and worker agents.
6. Methodology
   - Taxonomy generation.
   - Event extraction and adversarial review.
   - Assignment matching: SQL path vs contextual path.
   - Assignment submission review agent.
7. Experimental Setup
   - Environment, model settings, datasets, test profiles, labeled audit set, metrics.
8. Experiments and Discussion
   - Taxonomy quality experiment.
   - Event extraction experiment.
   - Assignment matching experiment.
   - Submission approval/rejection experiment.
9. Results
   - Tables, examples, errors, cost/time, comparison with baseline.
10. Realistic Constraints and Risk Analysis
11. Contributions
12. Conclusion and Future Work
13. References

## Submission review agent write-up plan

This feature should be written as an agentic evaluation pipeline, not a simple upload validator.

Recommended subsection title: `Agentic Assignment Submission Evaluation`.

Core explanation:

- The agent receives the assignment title, requirement text, due date/points, and submitted document directory.
- It performs a file-system inspection first: file count, names, extensions, sizes, total size, empty/corrupt files, and extractable text.
- It reads supported textual content line by line or chunk by chunk and creates evidence notes.
- It maps assignment requirements to submitted evidence.
- It reasons about relevance, completeness, and obvious mismatch.
- It returns a final decision: approved or rejected.
- If rejected, it gives a concise reason and exposes a student flag-for-review path so the student can still submit the documents for human review.

Evaluation table to add:

| Case | Assignment requirement | Submitted file | Agent decision | Expected decision | Notes |
| --- | --- | --- | --- | --- | --- |
| Relevant design document | Prototype design doc required | Game design PDF | Approved | Approved | Mentions gameplay, controls, implementation |
| Wrong archive | Game prototype required | Tokenizer zip | Rejected | Rejected | No playable prototype/design evidence |
| Partial but plausible | Prototype required | Short README/code | Flag/review or reject with flag | Human-review needed | Incomplete but related |

Important: rejected submissions should not dead-end. The report should frame flagging as an ethical safety feature, not as a loophole. It protects students from false negative automated review.

## Writing style rules to follow

Write with measured confidence. Avoid phrases like "exceptional contextual intelligence" unless the report provides a rigorous metric. Prefer "The system matched 10 internship-specific obligations for the internship profile, including..." because it is evidence-based.

Every major claim needs one of three supports: a citation, a table/figure from our experiment, or a concrete example from the system.

Do not make the report sound like a product pitch. The sample reports use formal engineering language: problem, method, dataset, experiment, result, limitation.

Keep theory short but purposeful. Explain only the parts used by Orbis, and tie every formula to an implementation decision.

Use honest limitations. This will make the report stronger, not weaker.

## High-priority checklist

- [x] Make `report/report.tex` compile.
- [x] Add real references and replace draft citation placeholders.
- [x] Expand Related Works with real sources and a baseline comparison.
- [x] Add a reproducible data collection/chunking subsection.
- [x] Add a full assignment submission review agent subsection.
- [x] Add figures for architecture, event pipeline, taxonomy, and submission review flow.
- [x] Add tables for dataset/corpus statistics, extraction audit, assignment results, submission review cases, and costs.
- [x] Add risk analysis with mitigation for wrong advice, stale rules, privacy, prompt injection, false rejection, and student appeal.
- [x] Add limitations and future work that match the current implementation status.
- [ ] Keep implementation-boundary wording explicit: current `/api/events/*`
  extraction route vs report's preserved `regulation_rules`/assignment metrics.
- [ ] Strengthen or source the HermiOne local-context paragraph.
- [ ] Replace silver ground truth with human-validated gold when time permits.
