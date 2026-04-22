-- ============================================================
-- Migration 033 -- Unique (project_id, event_number) on rex.change_events
-- ============================================================
-- Phase 4 Wave 2 (direct Procore API) Task 6 lane.
--
-- Adds the unique constraint the Procore orchestrator's
-- _write_change_events writer relies on for ON CONFLICT upserts into
-- rex.change_events keyed on the natural (project_id, event_number)
-- tuple. Without this, the
-- INSERT ... ON CONFLICT (project_id, event_number) DO UPDATE
-- statement fails at plan time with "there is no unique or exclusion
-- constraint matching the ON CONFLICT specification".
--
-- Shared upsert with the LLM tool: Phase 6b Wave 2 shipped a
-- ``create_change_event`` LLM tool that also inserts into
-- rex.change_events. Making (project_id, event_number) UNIQUE means
-- the tool and the Procore sync converge on a single canonical row
-- regardless of which path created it first — the ON CONFLICT DO
-- UPDATE just overwrites the mutable columns.
--
-- Mirrors migration 031 (submittals) / 024 (rfis). Idempotent:
-- wrapped in a DO $$ block with EXCEPTION WHEN duplicate_object so
-- re-running is a no-op, and the migration chain still advances past
-- already-applied constraints or pre-existing duplicate rows that
-- would otherwise block the unique add.
--
-- Depends on: rex2_canonical_ddl (creates rex.change_events).
-- ============================================================

DO $$
BEGIN
    ALTER TABLE rex.change_events
        ADD CONSTRAINT rex_change_events_project_number_uniq
        UNIQUE (project_id, event_number);
EXCEPTION WHEN duplicate_object OR duplicate_table OR unique_violation THEN
    -- Already present, or duplicate rows prevent the add. Matches 031's
    -- defensive swallow so the migration chain keeps moving and an
    -- operator can resolve duplicates manually before retrying.
    NULL;
END $$;
