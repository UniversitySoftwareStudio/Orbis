-- Academic calendar entries
CREATE TABLE IF NOT EXISTS academic_calendar_entries (
    id           SERIAL PRIMARY KEY,
    title_tr     VARCHAR(300) NOT NULL,
    title_en     VARCHAR(300),
    start_date   DATE NOT NULL,
    end_date     DATE,  -- NULL means single-day
    entry_type   VARCHAR(50) NOT NULL
                 CHECK (entry_type IN (
                     'holiday', 'exam_period', 'registration',
                     'add_drop', 'section_change', 'withdrawal_deadline',
                     'semester_start', 'semester_end', 'makeup_exam',
                     'graduation', 'orientation', 'grade_announcement',
                     'freeze_period', 'summer_school', 'other'
                 )),
    applies_to   VARCHAR(30) NOT NULL DEFAULT 'undergraduate'
                 CHECK (applies_to IN ('undergraduate', 'graduate', 'prep', 'all')),
    academic_year VARCHAR(10) NOT NULL,  -- e.g. '2025-2026'
    notes        TEXT,
    created_at   TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_cal_start_date  ON academic_calendar_entries(start_date);
CREATE INDEX idx_cal_year        ON academic_calendar_entries(academic_year);
CREATE INDEX idx_cal_applies_to  ON academic_calendar_entries(applies_to);
CREATE INDEX idx_cal_type        ON academic_calendar_entries(entry_type);