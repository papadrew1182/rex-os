-- ============================================================
-- Migration 018 -- Canonical schedule additions + bridge views
-- ============================================================
-- Session 2 (feat/canonical-connectors) lane.
-- Charter-original slot: 012_canonical_schedule.sql
-- Real-repo slot: 018
--
-- Creates rex.delay_events (genuinely missing) plus bridge views for
-- the charter's schedule names that map onto existing rex tables:
--   rex.v_schedule_tasks        -- alias for rex.schedule_activities
--   rex.v_schedule_dependencies -- alias for rex.activity_links
--   rex.v_schedule_baselines    -- projection of inline baseline fields
--   rex.v_schedule_milestones   -- alias for rex.completion_milestones
--
-- Charter schedule objects already in rex:
--   schedules, schedule_activities, activity_links, schedule_constraints,
--   schedule_snapshots, completion_milestones.
--
-- Idempotent: CREATE IF NOT EXISTS + CREATE OR REPLACE VIEW.
-- Depends on: rex.schedule_activities, rex.activity_links,
--   rex.completion_milestones, rex.projects.
-- ============================================================


-- 1. rex.delay_events --------------------------------------------------
-- Discrete delay occurrences on a project. Links to the schedule
-- activity the delay affected (if known), captures the cause category,
-- and tracks the recovery plan.
CREATE TABLE IF NOT EXISTS rex.delay_events (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          uuid NOT NULL REFERENCES rex.projects(id) ON DELETE CASCADE,
    activity_id         uuid REFERENCES rex.schedule_activities(id) ON DELETE SET NULL,
    title               text NOT NULL,
    description         text,
    cause_category      text NOT NULL
                          CHECK (cause_category IN (
                            'weather','design_change','owner_direction','rfi_pending',
                            'submittal_pending','permit','material_delivery','subcontractor',
                            'labor','equipment','inspection','coordination','other')),
    severity            text NOT NULL DEFAULT 'medium'
                          CHECK (severity IN ('low','medium','high','critical')),
    status              text NOT NULL DEFAULT 'active'
                          CHECK (status IN ('active','mitigated','resolved')),
    delay_start_date    date NOT NULL,
    delay_end_date      date,
    delay_days          int,
    critical_path_impact boolean NOT NULL DEFAULT false,
    recovery_plan       text,
    reported_by         uuid REFERENCES rex.people(id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rex_delay_events_project ON rex.delay_events (project_id);
CREATE INDEX IF NOT EXISTS idx_rex_delay_events_activity ON rex.delay_events (activity_id);
CREATE INDEX IF NOT EXISTS idx_rex_delay_events_status ON rex.delay_events (status);
CREATE INDEX IF NOT EXISTS idx_rex_delay_events_cause ON rex.delay_events (cause_category);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_rex_delay_events_updated_at') THEN
        CREATE TRIGGER trg_rex_delay_events_updated_at
            BEFORE UPDATE ON rex.delay_events
            FOR EACH ROW EXECUTE FUNCTION rex.set_updated_at();
    END IF;
END $$;


-- 2. rex.v_schedule_tasks (bridge view) --------------------------------
-- Charter name for rex.schedule_activities.
CREATE OR REPLACE VIEW rex.v_schedule_tasks AS
SELECT
    sa.id                          AS id,
    sa.schedule_id                 AS schedule_id,
    sa.parent_id                   AS parent_id,
    sa.activity_number             AS task_number,
    sa.name                        AS name,
    sa.activity_type               AS task_type,
    sa.start_date                  AS start_date,
    sa.end_date                    AS end_date,
    sa.duration_days               AS duration_days,
    sa.percent_complete            AS percent_complete,
    sa.is_critical                 AS is_critical,
    sa.is_manually_scheduled       AS is_manually_scheduled,
    sa.variance_days               AS variance_days,
    sa.float_days                  AS float_days,
    sa.assigned_company_id         AS assigned_company_id,
    sa.assigned_person_id          AS assigned_person_id,
    sa.actual_start_date           AS actual_start_date,
    sa.actual_finish_date          AS actual_finish_date,
    sa.wbs_code                    AS wbs_code,
    sa.location                    AS location,
    sa.notes                       AS notes,
    sa.sort_order                  AS sort_order,
    sa.start_variance_days         AS start_variance_days,
    sa.finish_variance_days        AS finish_variance_days,
    sa.free_float_days             AS free_float_days,
    sa.created_at                  AS created_at,
    sa.updated_at                  AS updated_at
FROM rex.schedule_activities sa;


-- 3. rex.v_schedule_dependencies (bridge view) ------------------------
-- Charter name for rex.activity_links.
CREATE OR REPLACE VIEW rex.v_schedule_dependencies AS
SELECT
    al.id                          AS id,
    al.schedule_id                 AS schedule_id,
    al.from_activity_id            AS from_task_id,
    al.to_activity_id              AS to_task_id,
    al.link_type                   AS dependency_type,
    al.lag_days                    AS lag_days,
    al.created_at                  AS created_at
FROM rex.activity_links al;


-- 4. rex.v_schedule_baselines (bridge view) ---------------------------
-- Project baselines as stored inline on rex.schedule_activities
-- (baseline_start, baseline_end). Denormalizes into a per-activity
-- baseline row shape for consumers that want to compare current vs
-- baseline side-by-side.
CREATE OR REPLACE VIEW rex.v_schedule_baselines AS
SELECT
    sa.id                          AS task_id,
    sa.schedule_id                 AS schedule_id,
    sa.name                        AS task_name,
    sa.baseline_start              AS baseline_start,
    sa.baseline_end                AS baseline_end,
    sa.start_date                  AS current_start,
    sa.end_date                    AS current_end,
    sa.variance_days               AS variance_days,
    sa.start_variance_days         AS start_variance_days,
    sa.finish_variance_days        AS finish_variance_days
FROM rex.schedule_activities sa
WHERE sa.baseline_start IS NOT NULL OR sa.baseline_end IS NOT NULL;


-- 5. rex.v_schedule_milestones (bridge view) --------------------------
-- Charter name for rex.completion_milestones.
CREATE OR REPLACE VIEW rex.v_schedule_milestones AS
SELECT
    cm.id                          AS id,
    cm.project_id                  AS project_id,
    cm.milestone_type              AS milestone_type,
    cm.milestone_name              AS name,
    cm.forecast_date               AS forecast_date,
    cm.scheduled_date              AS scheduled_date,
    cm.actual_date                 AS actual_date,
    cm.percent_complete            AS percent_complete,
    cm.variance_days               AS variance_days,
    cm.status                      AS status,
    cm.is_evidence_complete        AS is_evidence_complete,
    cm.certified_by                AS certified_by,
    cm.notes                       AS notes,
    cm.sort_order                  AS sort_order,
    cm.created_at                  AS created_at,
    cm.updated_at                  AS updated_at
FROM rex.completion_milestones cm;
