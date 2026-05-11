-- Migration 005: store submission agent reports and student rejection flags

ALTER TYPE submissionstatus ADD VALUE IF NOT EXISTS 'flagged';

ALTER TABLE assignment_submissions
    ADD COLUMN IF NOT EXISTS evaluation_report JSONB,
    ADD COLUMN IF NOT EXISTS flagged_by_student BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS student_flag_reason TEXT,
    ADD COLUMN IF NOT EXISTS flagged_at TIMESTAMP;

CREATE UNIQUE INDEX IF NOT EXISTS uq_assignment_submission_student_assignment
    ON assignment_submissions (assignment_id, student_id);
