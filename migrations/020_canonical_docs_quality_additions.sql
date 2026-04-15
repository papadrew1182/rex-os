-- ============================================================
-- Migration 019 -- Canonical docs/quality/weather additions + bridge views
-- ============================================================
-- Session 2 (feat/canonical-connectors) lane.
-- Charter-original slot: 013_canonical_documents_quality.sql
-- Real-repo slot: 019
--
-- Creates rex.quality_findings and rex.weather_observations (both
-- genuinely missing from phase 1-53) plus bridge views for the
-- charter's doc/quality names that map onto existing rex tables:
--   rex.v_documents       -- alias for rex.attachments
--   rex.v_spec_sections   -- alias for rex.specifications
--   rex.v_closeout_items  -- alias for rex.closeout_checklist_items
--
-- Charter doc/field-ops objects already in rex: drawings,
-- drawing_areas, drawing_revisions, specifications, photos, attachments,
-- correspondence, closeout_checklist_items.
--
-- Idempotent: CREATE IF NOT EXISTS + CREATE OR REPLACE VIEW.
-- Depends on: rex.projects, rex.attachments, rex.specifications,
--   rex.closeout_checklist_items, rex.people.
-- ============================================================


-- 1. rex.quality_findings ----------------------------------------------
-- Project-level quality finding registry. Distinct from
-- rex.inspection_items (which is tied to one inspection) in that
-- quality_findings live at project scope, can cross-reference any
-- related entity, and carry their own lifecycle.
CREATE TABLE IF NOT EXISTS rex.quality_findings (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          uuid NOT NULL REFERENCES rex.projects(id) ON DELETE CASCADE,
    finding_number      text NOT NULL,
    title               text NOT NULL,
    description         text,
    category            text NOT NULL
                          CHECK (category IN ('workmanship','materials','design_conflict',
                                              'code_compliance','coordination','documentation',
                                              'test_failure','other')),
    severity            text NOT NULL DEFAULT 'medium'
                          CHECK (severity IN ('low','medium','high','critical')),
    status              text NOT NULL DEFAULT 'open'
                          CHECK (status IN ('open','in_progress','verified','closed','void')),
    location            text,
    location_id         uuid REFERENCES rex.project_locations(id),
    assigned_company_id uuid REFERENCES rex.companies(id),
    assigned_person_id  uuid REFERENCES rex.people(id),
    discovered_date     date NOT NULL,
    resolved_date       date,
    related_entity_type text,
    related_entity_id   uuid,
    root_cause          text,
    corrective_action   text,
    preventive_action   text,
    reported_by         uuid REFERENCES rex.people(id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, finding_number)
);

CREATE INDEX IF NOT EXISTS idx_rex_quality_findings_project ON rex.quality_findings (project_id);
CREATE INDEX IF NOT EXISTS idx_rex_quality_findings_status ON rex.quality_findings (status);
CREATE INDEX IF NOT EXISTS idx_rex_quality_findings_severity ON rex.quality_findings (severity);
CREATE INDEX IF NOT EXISTS idx_rex_quality_findings_category ON rex.quality_findings (category);


-- 2. rex.weather_observations ------------------------------------------
-- Structured weather observations per project per day. rex.daily_logs
-- has a weather_summary TEXT field; this is the structured counterpart
-- that weather-impact analytics can group over.
CREATE TABLE IF NOT EXISTS rex.weather_observations (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          uuid NOT NULL REFERENCES rex.projects(id) ON DELETE CASCADE,
    observation_date    date NOT NULL,
    observation_time    text,
    temp_high_f         int,
    temp_low_f          int,
    temp_avg_f          int,
    precipitation_in    numeric,
    wind_speed_mph      int,
    wind_direction      text,
    humidity_pct        int,
    sky_condition       text
                          CHECK (sky_condition IS NULL OR sky_condition IN (
                            'clear','partly_cloudy','cloudy','overcast','fog',
                            'rain_light','rain','rain_heavy','storm','snow','ice','other')),
    is_weather_delay    boolean NOT NULL DEFAULT false,
    delay_hours         numeric,
    affected_activities text,
    source              text NOT NULL DEFAULT 'manual'
                          CHECK (source IN ('manual','noaa','openweather','daily_log','other')),
    daily_log_id        uuid REFERENCES rex.daily_logs(id),
    notes               text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, observation_date, source)
);

CREATE INDEX IF NOT EXISTS idx_rex_weather_observations_project ON rex.weather_observations (project_id);
CREATE INDEX IF NOT EXISTS idx_rex_weather_observations_date ON rex.weather_observations (observation_date DESC);
CREATE INDEX IF NOT EXISTS idx_rex_weather_observations_delay ON rex.weather_observations (is_weather_delay)
    WHERE is_weather_delay = true;


-- updated_at triggers
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_rex_quality_findings_updated_at') THEN
        CREATE TRIGGER trg_rex_quality_findings_updated_at
            BEFORE UPDATE ON rex.quality_findings
            FOR EACH ROW EXECUTE FUNCTION rex.set_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_rex_weather_observations_updated_at') THEN
        CREATE TRIGGER trg_rex_weather_observations_updated_at
            BEFORE UPDATE ON rex.weather_observations
            FOR EACH ROW EXECUTE FUNCTION rex.set_updated_at();
    END IF;
END $$;


-- 3. rex.v_documents (bridge view) -------------------------------------
-- Charter name for rex.attachments.
CREATE OR REPLACE VIEW rex.v_documents AS
SELECT
    a.id                           AS id,
    a.project_id                   AS project_id,
    a.source_type                  AS related_entity_type,
    a.source_id                    AS related_entity_id,
    a.filename                     AS filename,
    a.file_size                    AS file_size,
    a.content_type                 AS content_type,
    a.storage_url                  AS storage_url,
    a.storage_key                  AS storage_key,
    a.uploaded_by                  AS uploaded_by,
    a.created_at                   AS created_at
FROM rex.attachments a;


-- 4. rex.v_spec_sections (bridge view) --------------------------------
-- Charter name for rex.specifications.
CREATE OR REPLACE VIEW rex.v_spec_sections AS
SELECT
    s.id                           AS id,
    s.project_id                   AS project_id,
    s.section_number               AS section_number,
    s.title                        AS title,
    s.division                     AS division,
    s.current_revision             AS current_revision,
    s.revision_date                AS revision_date,
    s.attachment_id                AS attachment_id,
    s.created_at                   AS created_at,
    s.updated_at                   AS updated_at
FROM rex.specifications s;


-- 5. rex.v_closeout_items (bridge view) -------------------------------
-- Charter name for rex.closeout_checklist_items.
CREATE OR REPLACE VIEW rex.v_closeout_items AS
SELECT
    cci.id                         AS id,
    cci.checklist_id               AS checklist_id,
    cc.project_id                  AS project_id,
    cci.category                   AS category,
    cci.item_number                AS item_number,
    cci.name                       AS name,
    cci.status                     AS status,
    cci.assigned_company_id        AS assigned_company_id,
    cci.assigned_person_id         AS assigned_person_id,
    cci.due_date                   AS due_date,
    cci.completed_date             AS completed_date,
    cci.completed_by               AS completed_by,
    cci.notes                      AS notes,
    cci.sort_order                 AS sort_order,
    cci.spec_division              AS spec_division,
    cci.spec_section               AS spec_section,
    cci.created_at                 AS created_at,
    cci.updated_at                 AS updated_at
FROM rex.closeout_checklist_items cci
JOIN rex.closeout_checklists cc ON cc.id = cci.checklist_id;
