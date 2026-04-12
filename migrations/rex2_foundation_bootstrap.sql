-- ============================================================
-- REX 2.0 — FOUNDATION BOOTSTRAP
-- Seeds 7 tables in dependency order:
--   1. companies       (2 rows)
--   2. people          (4 rows)
--   3. user_accounts   (4 rows)
--   4. role_templates  (6 rows)
--   5. projects        (4 rows)
--   6. project_members (16 rows)
--   7. connector_mappings (5 rows)
--
-- Uses deterministic UUIDs for cross-referencing.
-- All INSERTs use ON CONFLICT DO NOTHING — safe to re-run.
-- Passwords: bcrypt hash of 'rex2026!' for all users.
--
-- Depends on: 001_create_schema.sql, rex2_canonical_ddl.sql
-- ============================================================


-- ════════════════════════════════════════════════════════════
-- 0. DEFENSIVE CONSTRAINT BACKFILL
-- If connector_mappings already existed (e.g. leftover from a prior
-- deploy), CREATE TABLE IF NOT EXISTS in the canonical DDL will have
-- skipped creating the unique constraint. Add it idempotently here so
-- the ON CONFLICT clauses below work.
-- ════════════════════════════════════════════════════════════

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_connector_mapping'
          AND conrelid = 'rex.connector_mappings'::regclass
    ) THEN
        BEGIN
            ALTER TABLE rex.connector_mappings
                ADD CONSTRAINT uq_connector_mapping
                UNIQUE (rex_table, connector, external_id);
        EXCEPTION WHEN duplicate_table OR unique_violation THEN
            -- A unique index with these columns already exists; safe to ignore
            NULL;
        END;
    END IF;
END $$;


-- ════════════════════════════════════════════════════════════
-- 1. COMPANIES
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.companies (id, name, trade, company_type, status, email)
VALUES
    ('00000000-0000-4000-a000-000000000001', 'Rex Construction', 'general_contractor', 'gc', 'active', 'info@rexconstruction.com'),
    ('00000000-0000-4000-a000-000000000002', 'Exxir Capital', NULL, 'owner', 'active', 'info@exxircapital.com')
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- 2. PEOPLE
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.people (id, company_id, first_name, last_name, email, title, role_type, is_active)
VALUES
    ('10000000-0000-4000-a000-000000000001',
     '00000000-0000-4000-a000-000000000001',
     'Andrew', 'Roberts', 'aroberts@exxircapital.com',
     'Vice President / Project Manager', 'internal', true),

    ('10000000-0000-4000-a000-000000000002',
     '00000000-0000-4000-a000-000000000001',
     'Mitch', 'Andersen', 'mandersen@exxircapital.com',
     'General Superintendent', 'internal', true),

    ('10000000-0000-4000-a000-000000000003',
     '00000000-0000-4000-a000-000000000001',
     'Andrew', 'Hudson', 'ahudson@exxircapital.com',
     'Assistant Superintendent', 'internal', true),

    ('10000000-0000-4000-a000-000000000004',
     '00000000-0000-4000-a000-000000000001',
     'Krystal', 'Hernandez', 'khernandez@exxircapital.com',
     'Project Accountant', 'internal', true)
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- 3. USER_ACCOUNTS
-- Password: 'rex2026!' hashed with bcrypt (cost 12)
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.user_accounts (id, person_id, email, password_hash, global_role, is_admin, is_active)
VALUES
    ('20000000-0000-4000-a000-000000000001',
     '10000000-0000-4000-a000-000000000001',
     'aroberts@exxircapital.com',
     '$2b$12$qac011oMElVhT07nFNTUleTYjXE3C/wzWnXf5.Qq1teGPdHLS8Ut2',
     'vp', true, true),

    ('20000000-0000-4000-a000-000000000002',
     '10000000-0000-4000-a000-000000000002',
     'mandersen@exxircapital.com',
     '$2b$12$qac011oMElVhT07nFNTUleTYjXE3C/wzWnXf5.Qq1teGPdHLS8Ut2',
     NULL, false, true),

    ('20000000-0000-4000-a000-000000000003',
     '10000000-0000-4000-a000-000000000003',
     'ahudson@exxircapital.com',
     '$2b$12$qac011oMElVhT07nFNTUleTYjXE3C/wzWnXf5.Qq1teGPdHLS8Ut2',
     NULL, false, true),

    ('20000000-0000-4000-a000-000000000004',
     '10000000-0000-4000-a000-000000000004',
     'khernandez@exxircapital.com',
     '$2b$12$qac011oMElVhT07nFNTUleTYjXE3C/wzWnXf5.Qq1teGPdHLS8Ut2',
     NULL, false, true)
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- 4. ROLE_TEMPLATES
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.role_templates (id, name, slug, description, is_internal, default_access_level,
    visible_tools, visible_panels, quick_action_groups, can_write, can_approve,
    notification_defaults, home_screen, is_system, sort_order)
VALUES
    -- VP
    ('30000000-0000-4000-a000-000000000001',
     'Vice President', 'vp',
     'Full platform access. Portfolio-level view. All approval rights.',
     true, 'admin',
     '["daily_log","punch","tasks","schedule","budget","rfis","submittals","drawings","commitments","change_orders","pay_apps","inspections","observations","photos","meetings","directory","reports","settings","university"]'::jsonb,
     '["rfi_aging","budget_variance","punch_health","schedule_drift","safety_summary","manpower_trend","change_order_exposure","payment_status","portfolio_summary","scorecard","milestone_readiness"]'::jsonb,
     '["rfi","submittal","budget","task","punch","safety","schedule","financial","portfolio","admin"]'::jsonb,
     '["daily_log","punch","task","rfi","submittal","observation","inspection","meeting","commitment","change_event","pay_app","correspondence"]'::jsonb,
     '["commitment","pay_app","change_order","prime_contract","budget","lien_waiver"]'::jsonb,
     '{"morning_briefing":true,"sla_alerts":true,"budget_alerts":true,"safety_alerts":true,"scorecard_alerts":true,"milestone_alerts":true}'::jsonb,
     'portfolio', true, 1),

    -- PM
    ('30000000-0000-4000-a000-000000000002',
     'Project Manager', 'pm',
     'Project-level execution. Budget and schedule authority. Approval rights for assigned projects.',
     true, 'admin',
     '["daily_log","punch","tasks","schedule","budget","rfis","submittals","drawings","commitments","change_orders","pay_apps","inspections","observations","photos","meetings","directory","reports","university"]'::jsonb,
     '["rfi_aging","budget_variance","punch_health","schedule_drift","safety_summary","manpower_trend","change_order_exposure","payment_status","scorecard","milestone_readiness"]'::jsonb,
     '["rfi","submittal","budget","task","punch","safety","schedule","financial"]'::jsonb,
     '["daily_log","punch","task","rfi","submittal","observation","inspection","meeting","commitment","change_event","pay_app","correspondence"]'::jsonb,
     '["commitment","pay_app","change_order","budget","lien_waiver"]'::jsonb,
     '{"morning_briefing":true,"sla_alerts":true,"budget_alerts":true,"safety_alerts":true,"scorecard_alerts":true,"milestone_alerts":true}'::jsonb,
     'my_day', true, 2),

    -- General Superintendent
    ('30000000-0000-4000-a000-000000000003',
     'General Superintendent', 'general_super',
     'Multi-project field oversight. Quality and safety consistency. Process hygiene auditing.',
     true, 'standard',
     '["daily_log","punch","tasks","schedule","rfis","submittals","drawings","inspections","observations","photos","meetings","directory","university"]'::jsonb,
     '["rfi_aging","punch_health","schedule_drift","safety_summary","manpower_trend","scorecard","milestone_readiness"]'::jsonb,
     '["rfi","submittal","task","punch","safety","schedule"]'::jsonb,
     '["daily_log","punch","task","rfi","observation","inspection","meeting"]'::jsonb,
     '[]'::jsonb,
     '{"morning_briefing":true,"sla_alerts":true,"safety_alerts":true,"scorecard_alerts":true}'::jsonb,
     'my_day', true, 3),

    -- Lead Superintendent
    ('30000000-0000-4000-a000-000000000004',
     'Lead Superintendent', 'lead_super',
     'Single-project owner. Daily execution, field documentation, trade coordination.',
     true, 'standard',
     '["daily_log","punch","tasks","schedule","rfis","submittals","drawings","inspections","observations","photos","meetings","university"]'::jsonb,
     '["rfi_aging","punch_health","schedule_drift","safety_summary","manpower_trend","scorecard","milestone_readiness"]'::jsonb,
     '["rfi","submittal","task","punch","safety","schedule"]'::jsonb,
     '["daily_log","punch","task","rfi","observation","inspection","meeting"]'::jsonb,
     '[]'::jsonb,
     '{"morning_briefing":true,"sla_alerts":true,"safety_alerts":true,"scorecard_alerts":true,"milestone_alerts":true}'::jsonb,
     'field_ops', true, 4),

    -- Assistant Superintendent
    ('30000000-0000-4000-a000-000000000005',
     'Assistant Superintendent', 'asst_super',
     'Field execution support. Daily logs, punch walks, inspection readiness.',
     true, 'field_only',
     '["daily_log","punch","tasks","inspections","observations","photos","university"]'::jsonb,
     '["punch_health","safety_summary","scorecard"]'::jsonb,
     '["task","punch","safety"]'::jsonb,
     '["daily_log","punch","task","observation","inspection"]'::jsonb,
     '[]'::jsonb,
     '{"morning_briefing":true,"safety_alerts":true,"scorecard_alerts":true}'::jsonb,
     'field_ops', true, 5),

    -- Accountant
    ('30000000-0000-4000-a000-000000000006',
     'Accountant', 'accountant',
     'Financial tracking. Pay app processing, lien waiver compliance, evidence pack assembly.',
     true, 'standard',
     '["budget","commitments","change_orders","pay_apps","rfis","submittals","directory","reports","university"]'::jsonb,
     '["budget_variance","change_order_exposure","payment_status","scorecard"]'::jsonb,
     '["budget","financial"]'::jsonb,
     '["pay_app","lien_waiver","correspondence"]'::jsonb,
     '["pay_app","lien_waiver"]'::jsonb,
     '{"morning_briefing":true,"budget_alerts":true,"scorecard_alerts":true}'::jsonb,
     'financials', true, 6)
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- 5. PROJECTS
-- No procore_id column — external IDs go in connector_mappings.
-- project_type values match CHECK constraint on rex.projects.
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.projects (id, name, project_number, project_type, status, city, state)
VALUES
    ('40000000-0000-4000-a000-000000000001',
     'Bishop Modern', 'BM-001', 'multifamily', 'active', 'Dallas', 'TX'),

    ('40000000-0000-4000-a000-000000000002',
     'Jungle Lakewood', 'JL-001', 'retail', 'active', 'Dallas', 'TX'),

    ('40000000-0000-4000-a000-000000000003',
     'Jungle Fort Worth', 'JFW-001', 'retail', 'active', 'Fort Worth', 'TX'),

    ('40000000-0000-4000-a000-000000000004',
     'Jungle Lovers Lane', 'JLL-001', 'retail', 'active', 'Dallas', 'TX')
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- 6. PROJECT_MEMBERS
-- All 4 team members assigned to all 4 projects.
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.project_members (id, project_id, person_id, company_id, role_template_id, access_level, is_primary, is_active, start_date)
VALUES
    -- Bishop Modern
    ('50000000-0000-4000-a000-000000000001', '40000000-0000-4000-a000-000000000001', '10000000-0000-4000-a000-000000000001', '00000000-0000-4000-a000-000000000001', '30000000-0000-4000-a000-000000000001', 'admin',      true, true, '2024-01-01'),
    ('50000000-0000-4000-a000-000000000002', '40000000-0000-4000-a000-000000000001', '10000000-0000-4000-a000-000000000002', '00000000-0000-4000-a000-000000000001', '30000000-0000-4000-a000-000000000003', 'standard',   true, true, '2024-01-01'),
    ('50000000-0000-4000-a000-000000000003', '40000000-0000-4000-a000-000000000001', '10000000-0000-4000-a000-000000000003', '00000000-0000-4000-a000-000000000001', '30000000-0000-4000-a000-000000000005', 'field_only', true, true, '2024-01-01'),
    ('50000000-0000-4000-a000-000000000004', '40000000-0000-4000-a000-000000000001', '10000000-0000-4000-a000-000000000004', '00000000-0000-4000-a000-000000000001', '30000000-0000-4000-a000-000000000006', 'standard',   true, true, '2024-01-01'),

    -- Jungle Lakewood
    ('50000000-0000-4000-a000-000000000005', '40000000-0000-4000-a000-000000000002', '10000000-0000-4000-a000-000000000001', '00000000-0000-4000-a000-000000000001', '30000000-0000-4000-a000-000000000001', 'admin',      true, true, '2024-06-01'),
    ('50000000-0000-4000-a000-000000000006', '40000000-0000-4000-a000-000000000002', '10000000-0000-4000-a000-000000000002', '00000000-0000-4000-a000-000000000001', '30000000-0000-4000-a000-000000000003', 'standard',   true, true, '2024-06-01'),
    ('50000000-0000-4000-a000-000000000007', '40000000-0000-4000-a000-000000000002', '10000000-0000-4000-a000-000000000003', '00000000-0000-4000-a000-000000000001', '30000000-0000-4000-a000-000000000005', 'field_only', true, true, '2024-06-01'),
    ('50000000-0000-4000-a000-000000000008', '40000000-0000-4000-a000-000000000002', '10000000-0000-4000-a000-000000000004', '00000000-0000-4000-a000-000000000001', '30000000-0000-4000-a000-000000000006', 'standard',   true, true, '2024-06-01'),

    -- Jungle Fort Worth
    ('50000000-0000-4000-a000-000000000009', '40000000-0000-4000-a000-000000000003', '10000000-0000-4000-a000-000000000001', '00000000-0000-4000-a000-000000000001', '30000000-0000-4000-a000-000000000001', 'admin',      true, true, '2024-03-01'),
    ('50000000-0000-4000-a000-000000000010', '40000000-0000-4000-a000-000000000003', '10000000-0000-4000-a000-000000000002', '00000000-0000-4000-a000-000000000001', '30000000-0000-4000-a000-000000000003', 'standard',   true, true, '2024-03-01'),
    ('50000000-0000-4000-a000-000000000011', '40000000-0000-4000-a000-000000000003', '10000000-0000-4000-a000-000000000003', '00000000-0000-4000-a000-000000000001', '30000000-0000-4000-a000-000000000005', 'field_only', true, true, '2024-03-01'),
    ('50000000-0000-4000-a000-000000000012', '40000000-0000-4000-a000-000000000003', '10000000-0000-4000-a000-000000000004', '00000000-0000-4000-a000-000000000001', '30000000-0000-4000-a000-000000000006', 'standard',   true, true, '2024-03-01'),

    -- Jungle Lovers Lane
    ('50000000-0000-4000-a000-000000000013', '40000000-0000-4000-a000-000000000004', '10000000-0000-4000-a000-000000000001', '00000000-0000-4000-a000-000000000001', '30000000-0000-4000-a000-000000000001', 'admin',      true, true, '2024-09-01'),
    ('50000000-0000-4000-a000-000000000014', '40000000-0000-4000-a000-000000000004', '10000000-0000-4000-a000-000000000002', '00000000-0000-4000-a000-000000000001', '30000000-0000-4000-a000-000000000003', 'standard',   true, true, '2024-09-01'),
    ('50000000-0000-4000-a000-000000000015', '40000000-0000-4000-a000-000000000004', '10000000-0000-4000-a000-000000000003', '00000000-0000-4000-a000-000000000001', '30000000-0000-4000-a000-000000000005', 'field_only', true, true, '2024-09-01'),
    ('50000000-0000-4000-a000-000000000016', '40000000-0000-4000-a000-000000000004', '10000000-0000-4000-a000-000000000004', '00000000-0000-4000-a000-000000000001', '30000000-0000-4000-a000-000000000006', 'standard',   true, true, '2024-09-01')
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- 7. CONNECTOR_MAPPINGS
-- Links Rex entities to Procore IDs via the bridge table.
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.connector_mappings (rex_table, rex_id, connector, external_id, external_url, synced_at)
VALUES
    ('projects', '40000000-0000-4000-a000-000000000001', 'procore', '562949954604699',
     'https://app.procore.com/562949953445402/project/562949954604699', now()),
    ('projects', '40000000-0000-4000-a000-000000000002', 'procore', '562949955280911',
     'https://app.procore.com/562949953445402/project/562949955280911', now()),
    ('projects', '40000000-0000-4000-a000-000000000003', 'procore', '562949954757963',
     'https://app.procore.com/562949953445402/project/562949954757963', now()),
    ('projects', '40000000-0000-4000-a000-000000000004', 'procore', '562949955172624',
     'https://app.procore.com/562949953445402/project/562949955172624', now()),
    ('people',   '10000000-0000-4000-a000-000000000001', 'procore', '8440337',
     'https://app.procore.com/562949953445402/company/directory/users/8440337', now())
ON CONFLICT (rex_table, connector, external_id) DO NOTHING;
