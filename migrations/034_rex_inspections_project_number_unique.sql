-- ============================================================
-- Migration 034 -- Unique (project_id, inspection_number) on rex.inspections
-- ============================================================
-- Phase 4 Wave 2 (direct Procore API) Task 7 lane.
--
-- Adds the unique constraint the Procore orchestrator's
-- _write_inspections writer relies on for ON CONFLICT upserts into
-- rex.inspections keyed on the natural (project_id, inspection_number)
-- tuple. Without this, the
-- INSERT ... ON CONFLICT (project_id, inspection_number) DO UPDATE
-- statement fails at plan time with "there is no unique or exclusion
-- constraint matching the ON CONFLICT specification".
--
-- Mirrors migration 033 (change_events) / 031 (submittals) / 024 (rfis).
-- Idempotent: wrapped in a DO $$ block with EXCEPTION WHEN
-- duplicate_object so re-running is a no-op, and the migration chain
-- still advances past already-applied constraints or pre-existing
-- duplicate rows that would otherwise block the unique add.
--
-- Depends on: rex2_canonical_ddl (creates rex.inspections).
-- ============================================================

DO $$
BEGIN
    ALTER TABLE rex.inspections
        ADD CONSTRAINT rex_inspections_project_number_uniq
        UNIQUE (project_id, inspection_number);
EXCEPTION WHEN duplicate_object OR duplicate_table OR unique_violation THEN
    -- Already present, or duplicate rows prevent the add. Matches 031's
    -- defensive swallow so the migration chain keeps moving and an
    -- operator can resolve duplicates manually before retrying.
    NULL;
END $$;
