-- ============================================================
-- Migration 019 — Canonical docs/quality/weather additions + view bridges
-- ============================================================
-- Session 2 (feat/canonical-connectors) lane.
-- Charter-original slot: 013_canonical_documents_quality.sql
-- Real-repo slot: 019 (charter 013 + 6)
-- Scope:
--   - create rex.quality_findings (genuinely missing)
--   - create rex.weather_observations (genuinely missing; rex.daily_logs
--     has weather_summary text but no structured observation rows)
--   - create rex.v_documents alias view over rex.attachments
--   - create rex.v_spec_sections alias view over rex.specifications
--   - create rex.v_closeout_items alias view over
--     rex.closeout_checklist_items
-- Depends on: rex.projects, rex.attachments, rex.specifications,
--   rex.closeout_checklist_items, rex.daily_logs.
-- Content: stub in this commit.
-- ============================================================

DO $$ BEGIN NULL; END $$;
