-- Add section type and hierarchy to existing course_sections
ALTER TABLE course_sections
    ADD COLUMN IF NOT EXISTS section_type     VARCHAR(10) NOT NULL DEFAULT 'LECTURE'
                                              CHECK (section_type IN ('LECTURE', 'LAB')),
    ADD COLUMN IF NOT EXISTS parent_section_id INTEGER REFERENCES course_sections(id)
                                              ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS instructor_name  VARCHAR(200);
-- instructor_name is a plain display string for cases where the
-- instructor is not a registered system user (TAs, visiting instructors, etc.)
-- When instructor_id FK is also set, prefer the name from users table.

CREATE INDEX IF NOT EXISTS idx_cs_parent ON course_sections(parent_section_id);
CREATE INDEX IF NOT EXISTS idx_cs_type   ON course_sections(section_type);

-- Weekly schedule slots for a section
CREATE TABLE IF NOT EXISTS section_schedules (
    id          SERIAL PRIMARY KEY,
    section_id  INTEGER NOT NULL REFERENCES course_sections(id) ON DELETE CASCADE,
    day_of_week VARCHAR(3) NOT NULL
                CHECK (day_of_week IN ('MON','TUE','WED','THU','FRI')),
    start_time  TIME NOT NULL,
    end_time    TIME NOT NULL,
    location    VARCHAR(150),    -- e.g. "Santral E1-103", "Dolapdere B1-204"
                                 -- NULL when is_online = TRUE
    is_online   BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT check_schedule_times CHECK (end_time > start_time)
);

CREATE INDEX idx_sched_section ON section_schedules(section_id);
CREATE INDEX idx_sched_day     ON section_schedules(day_of_week);