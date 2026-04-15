-- ============================================================
-- Migration 022 -- Canonical read-model views (rex.v_*)
-- ============================================================
-- Session 2 (feat/canonical-connectors) lane.
-- Charter-original slot: 024_control_plane_views.sql (read-view part)
-- Real-repo slot: 022
--
-- Creates the seven canonical read models that the assistant, dashboards,
-- automations, and writeback surfaces consume. No downstream surface
-- should be forced to read connector_procore.* or connector_exxir.*
-- directly -- everything goes through these views.
--
-- Views in this migration:
--   rex.v_project_mgmt  -- unified PM feed (RFIs, submittals, tasks,
--                          punch items, pending decisions)
--   rex.v_financials    -- budget / commitments / change events /
--                          pay apps / lien waivers per project
--   rex.v_schedule      -- activities + links + milestones + delays
--                          + variance flags
--   rex.v_directory     -- team roster + role assignments + vendor
--                          compliance + insurance status
--   rex.v_portfolio     -- portfolio-level rollups (project count,
--                          budget aggregates, readiness, drift)
--   rex.v_risk          -- active risk register (delays + quality
--                          findings + overdue pending decisions +
--                          insurance expiry + schedule constraints)
--   rex.v_myday         -- personalized action summary (parameterized
--                          by user_account_id at query time)
--
-- Every view is CREATE OR REPLACE so re-running is safe.
-- Depends on: everything that comes before it in MIGRATION_ORDER.
-- ============================================================


-- ============================================================
-- 1. rex.v_project_mgmt
-- Unified PM feed. One row per PM entity (rfi, submittal, task, punch,
-- pending_decision). Downstream consumers filter by project_id + entity_type.
-- ============================================================
CREATE OR REPLACE VIEW rex.v_project_mgmt AS
SELECT
    r.id                            AS entity_id,
    'rfi'::text                     AS entity_type,
    r.project_id                    AS project_id,
    r.rfi_number                    AS entity_number,
    r.subject                       AS title,
    r.status                        AS status,
    r.priority                      AS priority,
    r.assigned_to                   AS assigned_to_person_id,
    r.ball_in_court                 AS ball_in_court_person_id,
    r.due_date                      AS due_date,
    r.days_open                     AS days_open,
    r.created_at                    AS created_at,
    r.updated_at                    AS updated_at
FROM rex.rfis r
UNION ALL
SELECT
    s.id, 'submittal'::text, s.project_id, s.submittal_number, s.title,
    s.status, NULL::text, s.assigned_to, s.ball_in_court, s.due_date,
    NULL::int, s.created_at, s.updated_at
FROM rex.submittals s
UNION ALL
SELECT
    t.id, 'task'::text, t.project_id, t.task_number::text, t.title,
    t.status, t.priority, t.assigned_to, NULL::uuid, t.due_date,
    NULL::int, t.created_at, t.updated_at
FROM rex.tasks t
UNION ALL
SELECT
    pi.id, 'punch_item'::text, pi.project_id, pi.punch_number::text, pi.title,
    pi.status, pi.priority, pi.assigned_to, NULL::uuid, pi.due_date,
    pi.days_open, pi.created_at, pi.updated_at
FROM rex.punch_items pi
UNION ALL
SELECT
    pd.id, 'pending_decision'::text, pd.project_id, NULL::text, pd.title,
    pd.status, pd.priority, pd.decision_maker_id, NULL::uuid, pd.due_date,
    NULL::int, pd.created_at, pd.updated_at
FROM rex.pending_decisions pd;


-- ============================================================
-- 2. rex.v_financials
-- Per-project financial snapshot joining budgets + commitments +
-- change events + pay apps.
-- ============================================================
CREATE OR REPLACE VIEW rex.v_financials AS
SELECT
    p.id                            AS project_id,
    p.name                          AS project_name,
    p.project_number                AS project_number,
    p.status                        AS project_status,
    COALESCE(b.original_budget, 0)  AS original_budget,
    COALESCE(b.approved_changes, 0) AS approved_changes,
    COALESCE(b.revised_budget, 0)   AS revised_budget,
    COALESCE(b.committed_costs, 0)  AS committed_costs,
    COALESCE(b.direct_costs, 0)     AS direct_costs,
    COALESCE(b.projected_cost, 0)   AS projected_cost,
    COALESCE(b.over_under, 0)       AS budget_over_under,
    (SELECT COUNT(*) FROM rex.commitments WHERE project_id = p.id)     AS commitment_count,
    (SELECT COALESCE(SUM(revised_value),0) FROM rex.commitments WHERE project_id = p.id) AS commitments_revised_value,
    (SELECT COALESCE(SUM(invoiced_to_date),0) FROM rex.commitments WHERE project_id = p.id) AS commitments_invoiced_to_date,
    (SELECT COUNT(*) FROM rex.change_events WHERE project_id = p.id AND status IN ('open','pending')) AS open_change_events,
    (SELECT COALESCE(SUM(estimated_amount),0) FROM rex.change_events WHERE project_id = p.id AND status IN ('open','pending')) AS open_change_events_amount,
    (SELECT COUNT(*) FROM rex.potential_change_orders pco
        JOIN rex.change_events ce ON ce.id = pco.change_event_id
        WHERE ce.project_id = p.id AND pco.status IN ('draft','pending')) AS open_pcos,
    (SELECT COUNT(*) FROM rex.payment_applications pa
        JOIN rex.commitments c ON c.id = pa.commitment_id
        WHERE c.project_id = p.id AND pa.status IN ('submitted','under_review','approved')) AS pay_apps_in_flight,
    (SELECT COALESCE(SUM(pa.net_payment_due),0) FROM rex.payment_applications pa
        JOIN rex.commitments c ON c.id = pa.commitment_id
        WHERE c.project_id = p.id AND pa.status IN ('submitted','under_review','approved')) AS pay_apps_in_flight_amount,
    (SELECT COUNT(*) FROM rex.lien_waivers lw
        JOIN rex.payment_applications pa ON pa.id = lw.payment_application_id
        JOIN rex.commitments c ON c.id = pa.commitment_id
        WHERE c.project_id = p.id AND lw.status = 'pending') AS lien_waivers_pending
FROM rex.projects p
LEFT JOIN rex.v_budgets b ON b.project_id = p.id;


-- ============================================================
-- 3. rex.v_schedule
-- Per-project schedule snapshot + critical-path / variance rollup.
-- ============================================================
CREATE OR REPLACE VIEW rex.v_schedule AS
SELECT
    p.id                            AS project_id,
    p.name                          AS project_name,
    (SELECT COUNT(*) FROM rex.schedule_activities sa
        JOIN rex.schedules s ON s.id = sa.schedule_id
        WHERE s.project_id = p.id) AS total_activities,
    (SELECT COUNT(*) FROM rex.schedule_activities sa
        JOIN rex.schedules s ON s.id = sa.schedule_id
        WHERE s.project_id = p.id AND sa.is_critical = true) AS critical_activities,
    (SELECT COUNT(*) FROM rex.schedule_activities sa
        JOIN rex.schedules s ON s.id = sa.schedule_id
        WHERE s.project_id = p.id AND sa.percent_complete = 100) AS complete_activities,
    (SELECT COUNT(*) FROM rex.schedule_activities sa
        JOIN rex.schedules s ON s.id = sa.schedule_id
        WHERE s.project_id = p.id AND sa.percent_complete > 0 AND sa.percent_complete < 100) AS in_progress_activities,
    (SELECT COUNT(*) FROM rex.schedule_activities sa
        JOIN rex.schedules s ON s.id = sa.schedule_id
        WHERE s.project_id = p.id AND sa.variance_days > 0) AS drifting_activities,
    (SELECT MAX(sa.variance_days) FROM rex.schedule_activities sa
        JOIN rex.schedules s ON s.id = sa.schedule_id
        WHERE s.project_id = p.id) AS max_variance_days,
    (SELECT COUNT(*) FROM rex.schedule_constraints sc
        JOIN rex.schedule_activities sa ON sa.id = sc.activity_id
        JOIN rex.schedules s ON s.id = sa.schedule_id
        WHERE s.project_id = p.id AND sc.status = 'active') AS active_constraints,
    (SELECT COUNT(*) FROM rex.delay_events
        WHERE project_id = p.id AND status = 'active') AS active_delays,
    (SELECT COUNT(*) FROM rex.delay_events
        WHERE project_id = p.id AND status = 'active' AND critical_path_impact = true) AS critical_path_delays,
    (SELECT COUNT(*) FROM rex.completion_milestones
        WHERE project_id = p.id AND status = 'achieved') AS milestones_achieved,
    (SELECT COUNT(*) FROM rex.completion_milestones
        WHERE project_id = p.id AND status = 'overdue') AS milestones_overdue,
    (SELECT COUNT(*) FROM rex.completion_milestones
        WHERE project_id = p.id) AS milestones_total
FROM rex.projects p;


-- ============================================================
-- 4. rex.v_directory
-- Team roster + role assignments + vendor compliance per project.
-- One row per project_member.
-- ============================================================
CREATE OR REPLACE VIEW rex.v_directory AS
SELECT
    pm.id                           AS project_member_id,
    pm.project_id                   AS project_id,
    pr.name                         AS project_name,
    p.id                            AS person_id,
    TRIM(CONCAT_WS(' ', p.first_name, p.last_name)) AS full_name,
    p.title                         AS title,
    p.email                         AS email,
    p.phone                         AS phone,
    c.id                            AS company_id,
    c.name                          AS company_name,
    c.company_type                  AS company_type,
    c.trade                         AS company_trade,
    pm.access_level                 AS access_level,
    pm.is_primary                   AS is_primary_role,
    pm.is_active                    AS is_active,
    (
        SELECT r.slug
        FROM rex.user_accounts ua
        JOIN rex.user_roles ur ON ur.user_account_id = ua.id AND ur.is_primary = true
        JOIN rex.roles r ON r.id = ur.role_id
        WHERE ua.person_id = p.id
        LIMIT 1
    )                               AS primary_role_slug,
    c.insurance_carrier             AS insurance_carrier,
    c.insurance_expiry              AS insurance_expiry,
    CASE
        WHEN c.insurance_expiry IS NULL THEN 'unknown'
        WHEN c.insurance_expiry < CURRENT_DATE THEN 'expired'
        WHEN c.insurance_expiry < CURRENT_DATE + INTERVAL '30 days' THEN 'expiring_soon'
        ELSE 'current'
    END                             AS insurance_status,
    c.bonding_capacity              AS bonding_capacity,
    c.license_number                AS license_number
FROM rex.project_members pm
JOIN rex.projects pr ON pr.id = pm.project_id
JOIN rex.people p ON p.id = pm.person_id
LEFT JOIN rex.companies c ON c.id = pm.company_id;


-- ============================================================
-- 5. rex.v_portfolio
-- Portfolio-level rollup across all projects.
-- ============================================================
CREATE OR REPLACE VIEW rex.v_portfolio AS
SELECT
    p.id                            AS project_id,
    p.name                          AS project_name,
    p.project_number                AS project_number,
    p.project_type                  AS project_type,
    p.status                        AS project_status,
    p.city                          AS city,
    p.state                         AS state,
    p.start_date                    AS start_date,
    p.end_date                      AS end_date,
    p.contract_value                AS contract_value,
    COALESCE(b.revised_budget, 0)   AS budget_revised,
    COALESCE(b.projected_cost, 0)   AS projected_cost,
    COALESCE(b.over_under, 0)       AS budget_over_under,
    CASE
        WHEN COALESCE(b.revised_budget, 0) = 0 THEN NULL
        ELSE ROUND((COALESCE(b.over_under, 0) / NULLIF(b.revised_budget, 0) * 100)::numeric, 2)
    END                             AS budget_variance_pct,
    (SELECT COUNT(*) FROM rex.rfis WHERE project_id = p.id AND status IN ('open','draft')) AS open_rfis,
    (SELECT COUNT(*) FROM rex.rfis WHERE project_id = p.id AND status = 'open' AND days_open > 7) AS overdue_rfis,
    (SELECT COUNT(*) FROM rex.punch_items WHERE project_id = p.id AND status NOT IN ('closed','void')) AS open_punch_items,
    (SELECT COUNT(*) FROM rex.safety_incidents WHERE project_id = p.id AND status != 'closed') AS open_safety_incidents,
    (SELECT COUNT(*) FROM rex.change_events WHERE project_id = p.id AND status IN ('open','pending')) AS open_change_events,
    (SELECT COALESCE(SUM(estimated_amount),0) FROM rex.change_events WHERE project_id = p.id AND status IN ('open','pending')) AS open_change_amount,
    (SELECT MAX(sa.variance_days) FROM rex.schedule_activities sa
        JOIN rex.schedules s ON s.id = sa.schedule_id
        WHERE s.project_id = p.id) AS max_schedule_variance_days,
    (SELECT COUNT(*) FROM rex.delay_events WHERE project_id = p.id AND status = 'active') AS active_delays,
    (SELECT COUNT(*) FROM rex.project_members WHERE project_id = p.id AND is_active = true) AS active_team_members
FROM rex.projects p
LEFT JOIN rex.v_budgets b ON b.project_id = p.id;


-- ============================================================
-- 6. rex.v_risk
-- Active risk surface. One row per active risk item.
-- ============================================================
CREATE OR REPLACE VIEW rex.v_risk AS
-- active delay events
SELECT
    de.id                           AS risk_id,
    'delay_event'::text             AS risk_type,
    de.project_id                   AS project_id,
    de.title                        AS title,
    de.severity                     AS severity,
    de.status                       AS status,
    de.delay_start_date              AS occurred_on,
    de.critical_path_impact         AS critical_path_impact,
    de.description                  AS detail,
    de.cause_category               AS category,
    de.created_at                   AS created_at
FROM rex.delay_events de
WHERE de.status = 'active'
UNION ALL
-- open quality findings
SELECT
    qf.id, 'quality_finding'::text, qf.project_id, qf.title, qf.severity,
    qf.status, qf.discovered_date, false, qf.description, qf.category,
    qf.created_at
FROM rex.quality_findings qf
WHERE qf.status IN ('open','in_progress')
UNION ALL
-- overdue pending decisions
SELECT
    pd.id, 'pending_decision'::text, pd.project_id, pd.title, pd.priority,
    pd.status, pd.raised_at::date, false, COALESCE(pd.blocks_description, pd.description), 'decision'::text,
    pd.raised_at
FROM rex.pending_decisions pd
WHERE pd.status IN ('open','in_review')
  AND (pd.due_date IS NULL OR pd.due_date < CURRENT_DATE)
UNION ALL
-- active schedule constraints
SELECT
    sc.id, 'schedule_constraint'::text,
    (SELECT s.project_id FROM rex.schedules s
     JOIN rex.schedule_activities sa ON sa.schedule_id = s.id
     WHERE sa.id = sc.activity_id LIMIT 1),
    sc.constraint_type, sc.severity, sc.status, sc.created_at::date,
    false, sc.notes, sc.source_type, sc.created_at
FROM rex.schedule_constraints sc
WHERE sc.status = 'active'
UNION ALL
-- expired / expiring insurance certificates
SELECT
    ic.id, 'insurance_expiry'::text,
    NULL::uuid,
    CONCAT(ic.policy_type, ' @ ', ic.carrier) AS title,
    CASE
        WHEN ic.expiry_date < CURRENT_DATE THEN 'critical'
        WHEN ic.expiry_date < CURRENT_DATE + INTERVAL '30 days' THEN 'high'
        ELSE 'medium'
    END,
    ic.status, ic.expiry_date,
    false, ic.notes, 'insurance'::text, ic.created_at
FROM rex.insurance_certificates ic
WHERE ic.expiry_date < CURRENT_DATE + INTERVAL '60 days';


-- ============================================================
-- 7. rex.v_myday
-- Personalized action summary. Parameterized by user_account_id at
-- query time. Returns one row per actionable item for the user.
-- ============================================================
CREATE OR REPLACE VIEW rex.v_myday AS
SELECT
    ua.id                           AS user_account_id,
    item.item_id                    AS item_id,
    item.item_type                  AS item_type,
    item.project_id                 AS project_id,
    item.title                      AS title,
    item.priority                   AS priority,
    item.status                     AS status,
    item.due_date                   AS due_date,
    item.created_at                 AS created_at
FROM rex.user_accounts ua
JOIN rex.people p ON p.id = ua.person_id
JOIN rex.project_members pm ON pm.person_id = p.id AND pm.is_active = true
JOIN LATERAL (
    -- RFIs where user is ball-in-court or assigned
    SELECT r.id AS item_id, 'rfi'::text AS item_type, r.project_id,
           r.subject AS title, r.priority, r.status, r.due_date, r.created_at
    FROM rex.rfis r
    WHERE r.project_id = pm.project_id
      AND r.status IN ('open','draft')
      AND (r.ball_in_court = p.id OR r.assigned_to = p.id)
    UNION ALL
    -- Tasks assigned to user
    SELECT t.id, 'task'::text, t.project_id, t.title, t.priority, t.status,
           t.due_date, t.created_at
    FROM rex.tasks t
    WHERE t.project_id = pm.project_id
      AND t.assigned_to = p.id
      AND t.status IN ('open','in_progress')
    UNION ALL
    -- Pending decisions where user is decision_maker
    SELECT pd.id, 'pending_decision'::text, pd.project_id, pd.title,
           pd.priority, pd.status, pd.due_date, pd.raised_at
    FROM rex.pending_decisions pd
    WHERE pd.project_id = pm.project_id
      AND pd.decision_maker_id = p.id
      AND pd.status IN ('open','in_review')
    UNION ALL
    -- Meeting action items assigned to user
    SELECT mai.id, 'meeting_action_item'::text, m.project_id, mai.description,
           'medium'::text, mai.status, mai.due_date, mai.created_at
    FROM rex.meeting_action_items mai
    JOIN rex.meetings m ON m.id = mai.meeting_id
    WHERE m.project_id = pm.project_id
      AND mai.assigned_to = p.id
      AND mai.status = 'open'
) item ON true
WHERE ua.is_active = true;
