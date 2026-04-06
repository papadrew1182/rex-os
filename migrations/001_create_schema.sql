-- Migration 001: Create rex schema
-- All core Rex OS tables live in the rex schema.

CREATE SCHEMA IF NOT EXISTS rex;

-- Idempotent helper: update updated_at on row change
CREATE OR REPLACE FUNCTION rex.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;
