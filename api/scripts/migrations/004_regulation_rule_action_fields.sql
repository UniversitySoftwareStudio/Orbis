-- Migration 004: upgrade regulation_rules from rule clauses to action objects
-- - rename condition -> trigger
-- - add timing / severity support for notification use cases

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'regulation_rules'
          AND column_name = 'condition'
    ) AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'regulation_rules'
          AND column_name = 'trigger'
    ) THEN
        ALTER TABLE regulation_rules RENAME COLUMN condition TO trigger;
    END IF;
END $$;

ALTER TABLE regulation_rules
    ADD COLUMN IF NOT EXISTS valid_from DATE,
    ADD COLUMN IF NOT EXISTS valid_until DATE,
    ADD COLUMN IF NOT EXISTS blocking BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS consequence TEXT;

