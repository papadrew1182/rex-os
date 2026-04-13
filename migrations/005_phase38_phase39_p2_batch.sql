-- Migration 005: Phase 38 + 39 P2 parity batch
-- All ALTERs are additive (nullable columns), safe for live production.

-- ── Phase 38: Schedule depth fields ─────────────────────────────────────
ALTER TABLE rex.schedule_activities ADD COLUMN IF NOT EXISTS start_variance_days INT;
ALTER TABLE rex.schedule_activities ADD COLUMN IF NOT EXISTS finish_variance_days INT;
ALTER TABLE rex.schedule_activities ADD COLUMN IF NOT EXISTS free_float_days INT;

-- ── Phase 39A: Project geolocation ─────────────────────────────────────
ALTER TABLE rex.projects ADD COLUMN IF NOT EXISTS latitude NUMERIC;
ALTER TABLE rex.projects ADD COLUMN IF NOT EXISTS longitude NUMERIC;

-- ── Phase 39B: Company contact extras ──────────────────────────────────
ALTER TABLE rex.companies ADD COLUMN IF NOT EXISTS mobile_phone TEXT;
ALTER TABLE rex.companies ADD COLUMN IF NOT EXISTS website TEXT;

-- ── Phase 39C: Observation root cause fields ───────────────────────────
ALTER TABLE rex.observations ADD COLUMN IF NOT EXISTS contributing_behavior TEXT;
ALTER TABLE rex.observations ADD COLUMN IF NOT EXISTS contributing_condition TEXT;

-- ── Phase 39D: Closeout checklist item spec linkage ────────────────────
ALTER TABLE rex.closeout_checklist_items ADD COLUMN IF NOT EXISTS spec_division TEXT;
ALTER TABLE rex.closeout_checklist_items ADD COLUMN IF NOT EXISTS spec_section TEXT;

-- ── Phase 39E: O&M manual tracker ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS rex.om_manuals (
    id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES rex.projects(id),
    spec_section TEXT NOT NULL,
    spec_title TEXT,
    required_count INT NOT NULL DEFAULT 1 CHECK (required_count >= 0),
    received_count INT NOT NULL DEFAULT 0 CHECK (received_count >= 0),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','partial','received','approved','n_a')),
    vendor_company_id UUID REFERENCES rex.companies(id),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_om_manuals_project ON rex.om_manuals(project_id);
CREATE INDEX IF NOT EXISTS idx_om_manuals_status ON rex.om_manuals(status);
