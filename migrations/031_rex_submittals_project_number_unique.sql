-- ============================================================
-- Migration 031 -- Unique (project_id, submittal_number) on rex.submittals
-- ============================================================
-- Phase 4 Wave 2 (direct Procore API) lane.
--
-- Adds the unique constraint the Procore orchestrator's
-- _write_submittals writer relies on for ON CONFLICT upserts into
-- rex.submittals keyed on the natural (project_id, submittal_number)
-- tuple. Without this, the
-- INSERT ... ON CONFLICT (project_id, submittal_number) DO UPDATE
-- statement fails at plan time with "there is no unique or exclusion
-- constraint matching the ON CONFLICT specification".
--
-- Mirrors migration 024 (rex_rfis_project_rfi_number_uniq). Idempotent:
-- wrapped in a DO $$ block with EXCEPTION WHEN duplicate_object so
-- re-running is a no-op.
--
-- Depends on: rex2_canonical_ddl (creates rex.submittals).
-- ============================================================

DO $$
BEGIN
    ALTER TABLE rex.submittals
        ADD CONSTRAINT rex_submittals_project_number_uniq
        UNIQUE (project_id, submittal_number);
EXCEPTION WHEN duplicate_object OR duplicate_table OR unique_violation THEN
    -- Already present, or duplicate rows prevent the add. Matches 024's
    -- defensive swallow so the migration chain keeps moving and an
    -- operator can resolve duplicates manually before retrying.
    NULL;
END $$;
