-- ============================================================
-- Migration 032 -- Unique constraints for the Procore Wave 2
--                  schedule_activities pipeline.
-- ============================================================
-- Phase 4 Wave 2 (direct Procore API) Task 5 lane.
--
-- Adds two unique constraints the Procore orchestrator's
-- _write_schedule_activities writer relies on:
--
--   1. rex.schedules UNIQUE (project_id, name) — the per-project
--      schedule-bootstrap upsert keys on this tuple so a project's
--      "Procore default schedule" row converges on a single id
--      across repeated syncs.
--
--   2. rex.schedule_activities UNIQUE (schedule_id, activity_number)
--      — the per-activity canonical upsert keys on this tuple so
--      re-syncing a task converges on the same row rather than
--      spawning duplicates each run.
--
-- Without either, the corresponding
-- INSERT ... ON CONFLICT (...) DO UPDATE
-- statement would fail at plan time with "there is no unique or
-- exclusion constraint matching the ON CONFLICT specification".
--
-- Mirrors migration 031's defensive DO-block pattern: wrapped in
-- exception-swallowing blocks so re-running is a no-op, and the
-- migration chain still advances past already-applied constraints
-- or pre-existing duplicate rows that would otherwise block the
-- unique add.
--
-- Depends on: rex2_canonical_ddl (creates rex.schedules + rex.schedule_activities).
-- ============================================================

DO $$
BEGIN
    ALTER TABLE rex.schedules
        ADD CONSTRAINT rex_schedules_project_name_uniq
        UNIQUE (project_id, name);
EXCEPTION WHEN duplicate_object OR duplicate_table OR unique_violation THEN
    -- Already present, or duplicate rows prevent the add. Matches 031's
    -- defensive swallow so the migration chain keeps moving and an
    -- operator can resolve duplicates manually before retrying.
    NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE rex.schedule_activities
        ADD CONSTRAINT rex_schedule_activities_schedule_activity_number_uniq
        UNIQUE (schedule_id, activity_number);
EXCEPTION WHEN duplicate_object OR duplicate_table OR unique_violation THEN
    NULL;
END $$;
