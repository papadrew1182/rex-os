-- ============================================================
-- Migration 018 — Canonical schedule additions + view bridges
-- ============================================================
-- Session 2 (feat/canonical-connectors) lane.
-- Charter-original slot: 012_canonical_schedule.sql
-- Real-repo slot: 018 (charter 012 + 6)
-- Scope:
--   - create rex.delay_events (genuinely missing)
--   - create rex.v_schedule_tasks alias view over rex.schedule_activities
--   - create rex.v_schedule_dependencies alias view over rex.activity_links
--   - create rex.v_schedule_baselines view projecting the inline
--     baseline_start/baseline_end fields on rex.schedule_activities
--   - create rex.v_schedule_milestones alias view over
--     rex.completion_milestones
-- Depends on: rex.schedule_activities, rex.activity_links,
--   rex.completion_milestones.
-- Content: stub in this commit.
-- ============================================================

DO $$ BEGIN NULL; END $$;
