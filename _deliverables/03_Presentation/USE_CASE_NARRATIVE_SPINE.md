# Orbis Use-Case Narrative Spine

Use this file to keep the presentation intellectually clean. Each major use case
should be presented with the same argument shape:

1. Problem
2. Objective
3. Theory/design idea
4. Use-case flow
5. Findings
6. Result
7. Limitation / next step

This prevents the deck from becoming a shallow feature tour.

## Use Case 1: RAG Search

### Problem

Students and staff can search university information, but official knowledge is
spread across course pages, SIS-like data, regulations, PDFs, and bilingual web
content. A normal search result does not explain which source supports the
answer.

### Objective

Provide grounded answers over official institutional data, while keeping source
evidence visible.

### Theory / Design Idea

Retrieval-Augmented Generation grounds an LLM answer in retrieved context rather
than relying only on model memory. Orbis combines SQL-style intent handling and
vector retrieval so structured course/SIS queries and unstructured document
queries are handled differently.

### Use-Case Flow

1. Student asks a question through `/chat`.
2. `RAGService.process_query` receives the query.
3. `route_query` decides whether the request is SQL-like, vector-like, or both.
4. `execute_sql_intent` handles structured lookups.
5. `execute_vector_intent` uses `VectorSearchRepository.search_knowledge_base`.
6. PostgreSQL + pgvector retrieves rows from `knowledge_base_embeddings`.
7. `rerank_docs` ranks candidate chunks.
8. `build_context` constructs grounded context.
9. `stream_answer` returns the answer with source evidence.

### Findings

RAG is a necessary support layer, but it is reactive. It helps when the student
knows the question, but it does not discover obligations the student never asks
about.

### Result To Present

RAG is the pull-based path: grounded, source-backed search over institutional
data.

### Limitation / Next Step

RAG alone cannot solve timing and personalization. This motivates the proactive
event pipeline.

## Use Case 2: Proactive Regulation Events

### Problem

Important academic obligations are written as prose inside regulations and
directives. Students may miss them because they are not converted into
student-specific actions.

### Objective

Extract strict, assignable obligations from formal regulation text and turn them
into auditable student-facing regulation assignments.

### Theory / Design Idea

The system separates regulatory content from noisy university pages before
extraction. It then uses a conservative obligation-extraction pipeline: better
to reject vague awareness-only text than to notify students about weak or
incorrect obligations.

### Use-Case Flow

1. Admin triggers `/events/trigger`.
2. `EventPipelineOrchestrator.start_run` creates an `event_runs` record.
3. `SearchAgent.fetch_regulation_sources` reads regulatory chunks from the
   knowledge base.
4. `ReasoningAgent.extract` produces obligation candidates.
5. `EventCreator.persist_candidates` stores/evaluates candidates.
6. `ReasoningReviewer` reviews ambiguous or risky candidates.
7. Candidate decisions are logged in `event_candidate_logs`.
8. Accepted rules are represented as `regulation_rules`.
9. Matching logic writes applicable rows to `user_rule_assignments`.
10. Students see obligations through `/regulations/me`.

### Findings

The extraction layer is very precise but conservative. This fits the design
goal: avoid sending low-quality obligations to students.

### Result To Present

- 935 regulatory chunks processed.
- 323 candidate rules evaluated.
- 178 accepted obligations.
- 145 rejected quality candidates.
- Event extraction: precision 0.978, recall 0.574, F1 0.723.

### Limitation / Next Step

The profile-matching stage is weaker than extraction. Broad obligations can
create false positives, while situational obligations can be missed. Future work
should improve matching recall and add a human review queue.

## Use Case 3: Assignment Submission Review

### Problem

Students can upload incorrect, empty, corrupt, unrelated, partial, or adversarial
files. A submission system needs an early safety screen, but it should not
pretend to grade academic quality.

### Objective

Screen assignment submissions against assignment requirements, reject clearly
invalid files, and preserve an appeal path.

### Theory / Design Idea

The uploaded file is evidence, not instruction. Orbis first decomposes assignment
requirements, then judges extracted file evidence against those requirements.
Deterministic file checks run before LLM reasoning.

### Use-Case Flow

1. Student uploads through `/assignments/{id}/submit/stream`.
2. `stream_submission_evaluation` starts a progress stream.
3. Deterministic file gate checks extension, empty files, corrupt files, binary
   text, ZIP/PDF/DOCX/text extraction.
4. Requirement decomposition creates a checklist from the assignment title and
   description.
5. Verdict prompt compares extracted evidence against requirements.
6. `fallback_decision` handles malformed or unavailable LLM output.
7. Decision is persisted in `assignment_submissions`.
8. Rejected submissions can be appealed through `flag_submission_rejection`.

### Findings

The two-call reviewer improves safety compared with the older single-call
approach. The strongest finding is zero false negatives on genuine submissions
in the tested set. The remaining weakness is over-approval of partial drafts.

### Result To Present

- 32 deterministic cases.
- Accuracy 93.8%.
- Precision 0.800.
- Recall 1.000.
- F1 0.889.
- Prompt-injection cases rejected: 4/4 tested cases.

### Limitation / Next Step

The submission set is small and synthetic. Prompt-injection resistance is only
claimed for tested cases. Future work should add an explicit `flag_for_review`
class for partial or suspicious submissions.

## Cross-Use-Case Story

The three use cases should be connected like this:

| Use case | Mode | Main question | Key result | Limitation |
| --- | --- | --- | --- | --- |
| RAG search | Pull | Can the student ask and receive grounded answers? | Source-backed answer path | Student must know the question |
| Regulation events | Push | Can the system discover obligations before the student asks? | High extraction precision | Matching is weakest |
| Submission review | Review | Can the system screen uploaded work safely? | 93.8% accuracy, 1.000 recall | Partial drafts need flag class |

Presentation transition:

1. RAG solves grounded lookup.
2. Event extraction solves unknown obligations.
3. Assignment submission review solves safe acceptance screening.
4. Evaluation tells us which layer is strong and which layer needs the next
   engineering iteration.
