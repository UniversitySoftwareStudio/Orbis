-- Migration 003: regulation_rules table
-- Stores LLM-extracted rules from regulation documents.
-- Each rule is traceable back to exact KB chunk IDs and an evidence quote.

CREATE TABLE IF NOT EXISTS regulation_rules (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id            UUID REFERENCES event_runs(id) ON DELETE SET NULL,

    -- Source traceability
    source_doc_url    TEXT NOT NULL,
    source_chunk_ids  JSONB NOT NULL DEFAULT '[]',
    evidence_quote    TEXT NOT NULL,

    -- Rule content (plain student-facing language)
    rule_text         TEXT NOT NULL,
    applies_to        TEXT NOT NULL,
    condition         TEXT,
    deadline          TEXT,
    authority         TEXT,
    exceptions        TEXT,
    target_role       TEXT NOT NULL,  -- student | staff | admin | all

    -- Matching strategy
    match_type        TEXT NOT NULL,  -- sql | contextual
    sql_condition     TEXT,           -- e.g. "gpa < 1.80"  (only when match_type=sql)

    -- Quality
    status            TEXT NOT NULL DEFAULT 'active',  -- active | needs_review | rejected
    pass2_notes       TEXT,
    confidence        TEXT,           -- explicit | inferred | ambiguous

    -- Dedup
    fingerprint       VARCHAR(64) NOT NULL UNIQUE,

    created_at        TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_regulation_rules_run_id     ON regulation_rules(run_id);
CREATE INDEX IF NOT EXISTS idx_regulation_rules_match_type ON regulation_rules(match_type);
CREATE INDEX IF NOT EXISTS idx_regulation_rules_status     ON regulation_rules(status);
CREATE INDEX IF NOT EXISTS idx_regulation_rules_role       ON regulation_rules(target_role);
