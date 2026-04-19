# Orbis Event System — Full Technical Documentation

Istanbul Bilgi University · Orbis RAG Platform  
Student project by two undergraduate students.

---

## What This System Does

The event system reads university regulation documents, extracts every actionable obligation from them, and assigns the relevant ones to each person in the university — with a plain-language explanation of exactly why that rule applies to them specifically.

The end result: any user (student, instructor, admin) can call `GET /api/events/assignments/me` and receive a prioritized list of university rules that currently apply to their situation, each explained in their own terms.

---

## The Single Flow

```
University regulation documents (80 sources, 935 chunks in KnowledgeBase)
        │
        ▼
POST /api/events/trigger
        │
        ▼
EventRun created in DB (status=RUNNING)
        │
        ▼
RuleExtractionOrchestrator.run(db)
  ├── Load regulation doc IDs from tree_with_regulations.json
  ├── Fetch all matching KB chunks from knowledge_base table
  ├── Group chunks by source URL → 80 unique documents
  └── ThreadPoolExecutor (max_workers=2) — process each document:
        │
        ▼
        _process_document(url, chunks)
          ├── Infer document type: "regulation" | "announcement" | "form_template"
          ├── Skip form_template documents immediately
          │
          ├── PASS 1 — LLM extraction
          │     System prompt: "You are an extraction engine..."
          │     User prompt:   PASS1_PROMPT with full document text (≤12,000 chars)
          │     Model:         claude-opus-4-6 via Outlier proxy
          │     Output:        JSON array of candidate rules, each with:
          │                    rule_text, applies_to, trigger, deadline,
          │                    valid_from, valid_until, blocking, consequence,
          │                    authority, exceptions, target_role,
          │                    match_type (sql|contextual), sql_condition,
          │                    evidence_quote, confidence
          │
          ├── PASS 2 — LLM adversarial review
          │     Same model sees original document + Pass 1 output
          │     Decides: keep | fix | remove for each item
          │     Also scans for missed rules and adds them
          │     Output: { reviewed: [...], missed_rules: [...] }
          │
          ├── Specificity filter (_specificity_issue)
          │     Rejects rules where:
          │     - applies_to is "all students" with no refinement
          │     - trigger is "when on campus" or always-on
          │     - rule_text starts with weak openers (Be aware, Consider, Note that)
          │     - blocking=true but consequence is missing
          │     - valid_from/valid_until are malformed dates
          │
          ├── Semantic + lexical deduplication
          │     Cosine similarity threshold: 0.97
          │     Lexical (SequenceMatcher) threshold: 0.93
          │     Fingerprint (SHA-256 of rule_text + target_role) uniqueness check
          │
          └── Persist to regulation_rules (status=ACTIVE)
              Log every candidate to event_candidate_logs with decision reason
              Log agent steps to event_agent_logs
        │
        ▼
EventRun status → COMPLETED
sources_processed=80, chunks_processed=935, events_created=178
        │
        ▼
POST /api/events/assign  (admin-triggered, runs in background)
  OR
POST /api/events/assign/me  (any authenticated user, runs immediately)
        │
        ▼
user_agent.run_for_user(db, user)
  │
  ├── build_user_context(db, user)
  │     Reads from: users, students, user_profiles, enrollments, course_sections
  │     Builds plain-text context blob:
  │       Name, Role, Active status
  │       Department, Faculty, Program level, Academic year
  │       Semesters completed, Credits completed
  │       Status flags: on probation, advisor hold, financial hold,
  │                     exchange student, double major, minor
  │       Title / Office / Responsibilities (instructors/staff)
  │       Enrolled courses this term (live from DB)
  │       All key:value pairs from user_profiles.extra_context (JSONB)
  │
  ├── SQL path — deterministic, student-only
  │     Fetches all regulation_rules where match_type='SQL' and status='ACTIVE'
  │     Evaluates each sql_condition in Python against {gpa, enrolled_credits, is_active}
  │     No LLM involved — fires instantly
  │     Reason: "Your profile matches the condition: gpa < 2.00"
  │
  ├── Contextual path — LLM reasoning, any role
  │     Fetches all regulation_rules where match_type='CONTEXTUAL' and status='ACTIVE'
  │     Batches them in groups of 25 (to avoid 503 on large payloads)
  │     For each batch: sends user context + rules to claude-opus-4-6
  │     LLM decides which rules apply and writes a reason for each
  │     Reasons reference specific facts from the user's context:
  │       "Zeynep is an undergraduate student in the Faculty of Engineering
  │        with mandatory internship required this semester..."
  │
  ├── Urgency derivation (no LLM)
  │     blocking=True             → HIGH
  │     deadline or consequence   → MEDIUM
  │     otherwise                 → LOW
  │
  └── Persist to user_rule_assignments
        Upsert on (user_id, rule_id) — re-runs update reason + urgency, never duplicate
        If previously DISMISSED, reactivates to ACTIVE
        │
        ▼
GET /api/events/assignments/me
Returns: all ACTIVE assignments for current user, ordered by assigned_at desc
Each item includes: rule_text, trigger, deadline, blocking, consequence,
                    authority, exceptions, match_type, urgency, reason, source_url
```

---

## Critical Points

**Document type filter:** Announcements are treated as cycle-scoped by default. If the announcement's cycle has expired before `current_date`, Pass 1 returns `[]`. Form templates almost always return `[]` — the LLM is instructed to extract only standing policy, not form labels.

**Two-pass LLM with adversarial review:** Pass 1 extracts. Pass 2 sees the original document again and can fix weak wording, remove stale items, or add missed rules. If Pass 2 fails (network error), rules from Pass 1 are saved as `status=NEEDS_REVIEW` rather than discarded.

**Batching for contextual matching:** 167 contextual rules sent in one prompt exceed the proxy's payload limit and cause 503. The agent batches in groups of 25, merging results across all batches. One failed batch does not block the others.

**Deduplication is layered:** fingerprint hash catches exact duplicates across runs; semantic + lexical similarity catches near-duplicates like the same rule extracted from two differently-worded source paragraphs.

**`extra_context` JSONB is the injection point:** Anything placed in `user_profiles.extra_context` is included verbatim in the context blob. This is how internship status, scholarship type, thesis topic, and other facts not stored in structured columns reach the LLM. The agent reads it without any schema — it just serializes the dict as `key: value` lines.

**User agent works on request:** `POST /api/events/assign/me` runs synchronously for the authenticated user and returns the match results immediately. `POST /api/events/assign` (admin) queues a batch run for all 988 active users in the background.

---

## Measured Results

### Extraction Pipeline (1 run)

| Metric | Value |
|--------|-------|
| Source documents processed | 80 |
| KB chunks consumed | 935 |
| Candidate rules evaluated | 323 |
| Accepted (active rules) | 178 (55%) |
| Rejected — quality filter | 145 (44%) |
| Rejected — duplicate | 0 (0%) |
| SQL-matchable rules | 11 |
| Contextual rules | 167 |
| Blocking rules | 108 of 178 (61%) |

The 44% rejection rate is by design. The specificity filter removes rules that would be noise as notifications — overly broad audience, always-on trigger, or no concrete action.

### Assignment Results (4 test students)

| Student | GPA | Profile context | Assignments | HIGH | MED | LOW | SQL | CTX |
|---------|-----|----------------|-------------|------|-----|-----|-----|-----|
| Ali Yilmaz | 1.60 | Academic probation, Year 2, CE | 42 | 30 | 8 | 4 | 8 | 34 |
| Ayse Kaya | 3.50 | Double major, Year 3, Business | 36 | 25 | 6 | 5 | 3 | 33 |
| Mehmet Demir | 2.40 | Graduation project in progress, Year 4 | 60 | 38 | 17 | 5 | 2 | 58 |
| Zeynep Arslan | 2.85 | Mandatory internship this semester, Year 3 | 38 | 29 | 5 | 4 | 2 | 36 |

**Total assignments across all users: 176**  
**HIGH urgency: 122 (69%) · MEDIUM: 36 (20%) · LOW: 18 (10%)**  
**SQL-matched: 15 · Contextual (LLM-reasoned): 161**

### Accuracy Illustration — Zeynep Arslan (internship student)

Zeynep's `extra_context`:
```json
{
  "internship_status": "mandatory internship required this semester",
  "internship_company": "not yet found",
  "internship_credits_needed": 30,
  "internship_form_submitted": false,
  "has_insurance": false
}
```

The agent assigned **10 internship-specific rules** out of her 38 total. Each was matched because the LLM read her context and connected it to the rule. Examples:

> **Rule:** "Submit the Internship Contract Cover Form… at least 10 working days before your internship start date."  
> **Reason:** "Zeynep is an undergraduate student in the Faculty of Engineering with a mandatory internship required this semester. She has not yet found a company or submitted forms, but once she secures a placement she must submit the internship contract forms at least 10 working days before starting."

> **Rule:** "Do not schedule classes or exams on your internship days if completing the internship during the semester; must cover at least three working days per week."  
> **Reason:** "Zeynep's mandatory internship is required this semester (during the academic term rather than summer), so she must ensure no class/exam conflicts on internship days and work at least three days per week."

> **Rule:** "Do not begin a compulsory internship before the summer following the end of your 4th semester."  
> **Reason:** "Having completed 6 semesters (past the 4th semester requirement), she is eligible to begin — the timing constraint is satisfied, but the rule still governs her internship scheduling."

The third example is notable: the LLM correctly identified that the rule applies but that Zeynep has already satisfied the constraint — it did not blindly flag it as a violation.

### SQL Matching Accuracy

SQL rules fire deterministically with zero LLM involvement. Ali (GPA 1.60) matched all 8 rules with `gpa < 2.00` or `gpa < 1.75` conditions. Ayse (GPA 3.50) matched 3 rules requiring `gpa >= 3.00`, `>= 2.80`, `>= 2.60`. No false positives are possible by construction — the condition is evaluated in Python against the actual DB value.

### Deduplication

Re-running the agent for Zeynep twice produced `new_assignments=6` on the second run (only the previously-failed batch) and `new_assignments=0` on a third run. The upsert on `(user_id, rule_id)` ensures idempotency — re-runs update reasons without creating duplicates.

---

## API Surface

| Endpoint | Auth | What it does |
|----------|------|-------------|
| `POST /api/events/trigger` | admin | Starts rule extraction from all regulation documents (background) |
| `GET /api/events/runs/{run_id}` | admin | Polls extraction run status |
| `GET /api/events/runs/{run_id}/telemetry` | admin | Returns all agent decision logs for a run |
| `GET /api/events/runs/{run_id}/candidates` | admin | Returns all candidate decisions (accepted/rejected + reason) |
| `POST /api/events/assign` | admin | Triggers user agent for all active users (background) |
| `POST /api/events/assign/me` | any user | Runs user agent for caller immediately, returns matches |
| `GET /api/events/assignments/me` | any user | Returns caller's active rule assignments with reasons |

### User Flow: How a Student Gets Their Assignments

```
Student logs in → receives session cookie
        │
        ▼
POST /api/events/assign/me
  (no body needed — user identity comes from session)
        │
        ▼
Server reads user from cookie → loads user + student + user_profile + enrollments
        │
        ▼
Runs SQL match + 7 batches of contextual LLM matching (~30–90 seconds)
        │
        ▼
Returns JSON: { sql_rules: [...], contextual_rules: [...], total_matched: N }
        │
        ▼
GET /api/events/assignments/me
Returns persisted assignments sorted by assigned_at desc
Each item:
  {
    "rule_text": "Complete a total of 40 working days of mandatory internship...",
    "trigger": "when the student is about to begin their compulsory internship",
    "blocking": true,
    "urgency": "high",
    "match_type": "contextual",
    "reason": "Zeynep is an undergraduate student in Computer Engineering with mandatory internship required this semester...",
    "source_url": "https://bilgi.edu.tr/en/internship-guidelines/",
    "deadline": null,
    "consequence": "Cannot qualify for undergraduate degree without completing 40 working days."
  }
```

---

## DB Tables

| Table | Purpose |
|-------|---------|
| `event_runs` | One row per extraction run. Tracks status, counts, errors. |
| `event_source_logs` | One row per document per run. Status: done/skipped/failed. |
| `event_candidate_logs` | Every rule candidate ever evaluated — accepted or rejected, with reason code. |
| `event_agent_logs` | Step-by-step LLM agent decisions for auditability. |
| `regulation_rules` | The extracted rules. Deduped, fingerprinted, status-tagged. |
| `user_profiles` | Enriched user context: department, year, status flags, extra_context JSONB. |
| `user_rule_assignments` | Rule → user assignments. Deduped on (user_id, rule_id). Stores reason + urgency. |
