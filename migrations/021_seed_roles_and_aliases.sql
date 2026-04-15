-- ============================================================
-- Migration 021 -- Seed canonical roles, permissions, aliases, grants
-- ============================================================
-- Session 2 (feat/canonical-connectors) lane.
-- Charter-original slot: 023 (Session 2 owns role + alias parts only).
-- Real-repo slot: 021
--
-- Seeds the canonical six-role model + starter permissions + grant
-- matrix + legacy alias map. VP_PM resolves to PM per
-- baseline-reconciliation.md section 6: VP_PM rows in legacy data
-- gave PM project-level authority plus portfolio read. Aliasing to
-- PM preserves that (portfolio.view is granted to the PM role below).
-- Aliasing to VP would silently promote to admin + approval authority.
--
-- Also backfills rex.user_roles from existing rex.user_accounts and
-- seeds default rex.user_preferences rows.
--
-- Idempotent: every INSERT uses ON CONFLICT DO NOTHING.
-- Depends on: 009 (roles/perms/role_perms/aliases),
--             010 (user_roles, user_preferences),
--             rex2_foundation_bootstrap.sql (user_accounts seed rows).
-- ============================================================


-- 1. CANONICAL ROLES ---------------------------------------------------
INSERT INTO rex.roles (id, slug, display_name, description, is_system, sort_order)
VALUES
    ('a1000000-0000-4000-b000-000000000001', 'VP',              'Vice President',          'Executive oversight. Portfolio-level view. Full approval authority.', true, 1),
    ('a1000000-0000-4000-b000-000000000002', 'PM',              'Project Manager',         'Project-level execution. Budget plus schedule plus write authority.', true, 2),
    ('a1000000-0000-4000-b000-000000000003', 'GENERAL_SUPER',   'General Superintendent',  'Multi-project field oversight. Quality plus safety consistency.',      true, 3),
    ('a1000000-0000-4000-b000-000000000004', 'LEAD_SUPER',      'Lead Superintendent',     'Single-project field owner. Daily execution plus trade coordination.',true, 4),
    ('a1000000-0000-4000-b000-000000000005', 'ASSISTANT_SUPER', 'Assistant Superintendent','Field execution support. Daily logs, punch walks, inspection.',       true, 5),
    ('a1000000-0000-4000-b000-000000000006', 'ACCOUNTANT',      'Project Accountant',      'Financial tracking. Pay apps, lien waivers, evidence packs.',          true, 6)
ON CONFLICT (slug) DO NOTHING;


-- 2. CANONICAL PERMISSIONS ---------------------------------------------
INSERT INTO rex.permissions (id, slug, description, domain)
VALUES
    ('a2000000-0000-4000-b000-000000000001', 'assistant.chat',         'Invoke the assistant chat endpoint',     'assistant'),
    ('a2000000-0000-4000-b000-000000000002', 'assistant.catalog.read', 'Read the quick-action catalog',          'assistant'),
    ('a2000000-0000-4000-b000-000000000003', 'assistant.action.run',   'Run a quick action end-to-end',          'assistant'),
    ('a2000000-0000-4000-b000-000000000010', 'project_mgmt.view',      'Read rex.v_project_mgmt',                'read'),
    ('a2000000-0000-4000-b000-000000000011', 'financials.view',        'Read rex.v_financials',                  'read'),
    ('a2000000-0000-4000-b000-000000000012', 'schedule.view',          'Read rex.v_schedule',                    'read'),
    ('a2000000-0000-4000-b000-000000000013', 'directory.view',         'Read rex.v_directory',                   'read'),
    ('a2000000-0000-4000-b000-000000000014', 'portfolio.view',         'Read rex.v_portfolio',                   'read'),
    ('a2000000-0000-4000-b000-000000000015', 'risk.view',              'Read rex.v_risk',                        'read'),
    ('a2000000-0000-4000-b000-000000000016', 'myday.view',             'Read rex.v_myday',                       'read'),
    ('a2000000-0000-4000-b000-000000000020', 'control_plane.view',     'Read connector health plus job registry','control_plane'),
    ('a2000000-0000-4000-b000-000000000021', 'connector.view',         'Read rex.connectors plus account state', 'control_plane'),
    ('a2000000-0000-4000-b000-000000000030', 'admin.users',            'Manage rex.users / rex.user_roles',      'admin'),
    ('a2000000-0000-4000-b000-000000000031', 'admin.connectors',       'Manage rex.connector_accounts',          'admin'),
    ('a2000000-0000-4000-b000-000000000032', 'admin.roles',            'Manage rex.roles / role_permissions',    'admin')
ON CONFLICT (slug) DO NOTHING;


-- 3. ROLE -> PERMISSION GRANTS -----------------------------------------
WITH grants AS (
    SELECT * FROM (VALUES
        -- VP: everything
        ('VP', 'assistant.chat'), ('VP', 'assistant.catalog.read'), ('VP', 'assistant.action.run'),
        ('VP', 'project_mgmt.view'), ('VP', 'financials.view'), ('VP', 'schedule.view'),
        ('VP', 'directory.view'), ('VP', 'portfolio.view'), ('VP', 'risk.view'), ('VP', 'myday.view'),
        ('VP', 'control_plane.view'), ('VP', 'connector.view'),
        ('VP', 'admin.users'), ('VP', 'admin.connectors'), ('VP', 'admin.roles'),
        -- PM: everything except admin
        ('PM', 'assistant.chat'), ('PM', 'assistant.catalog.read'), ('PM', 'assistant.action.run'),
        ('PM', 'project_mgmt.view'), ('PM', 'financials.view'), ('PM', 'schedule.view'),
        ('PM', 'directory.view'), ('PM', 'portfolio.view'), ('PM', 'risk.view'), ('PM', 'myday.view'),
        ('PM', 'control_plane.view'), ('PM', 'connector.view'),
        -- GENERAL_SUPER: multi-project field oversight
        ('GENERAL_SUPER', 'assistant.chat'), ('GENERAL_SUPER', 'assistant.catalog.read'),
        ('GENERAL_SUPER', 'assistant.action.run'), ('GENERAL_SUPER', 'project_mgmt.view'),
        ('GENERAL_SUPER', 'schedule.view'), ('GENERAL_SUPER', 'directory.view'),
        ('GENERAL_SUPER', 'risk.view'), ('GENERAL_SUPER', 'myday.view'),
        -- LEAD_SUPER: single-project field execution
        ('LEAD_SUPER', 'assistant.chat'), ('LEAD_SUPER', 'assistant.catalog.read'),
        ('LEAD_SUPER', 'assistant.action.run'), ('LEAD_SUPER', 'project_mgmt.view'),
        ('LEAD_SUPER', 'schedule.view'), ('LEAD_SUPER', 'directory.view'), ('LEAD_SUPER', 'myday.view'),
        -- ASSISTANT_SUPER: field execution support
        ('ASSISTANT_SUPER', 'assistant.chat'), ('ASSISTANT_SUPER', 'assistant.catalog.read'),
        ('ASSISTANT_SUPER', 'project_mgmt.view'), ('ASSISTANT_SUPER', 'myday.view'),
        -- ACCOUNTANT: financial tracking
        ('ACCOUNTANT', 'assistant.chat'), ('ACCOUNTANT', 'assistant.catalog.read'),
        ('ACCOUNTANT', 'assistant.action.run'), ('ACCOUNTANT', 'financials.view'),
        ('ACCOUNTANT', 'portfolio.view'), ('ACCOUNTANT', 'directory.view'), ('ACCOUNTANT', 'myday.view')
    ) AS t(role_slug, perm_slug)
)
INSERT INTO rex.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM grants g
JOIN rex.roles       r ON r.slug = g.role_slug
JOIN rex.permissions p ON p.slug = g.perm_slug
ON CONFLICT (role_id, permission_id) DO NOTHING;


-- 4. LEGACY ROLE ALIASES -----------------------------------------------
-- VP_PM resolves to PM per baseline-reconciliation.md section 6.
INSERT INTO rex.role_aliases (alias, canonical_role_slug, notes)
VALUES
    ('VP',                       'VP',              'canonical self-alias'),
    ('vp',                       'VP',              'legacy lowercase from user_accounts.global_role'),
    ('Vice_President',           'VP',              'rex-procore legacy form'),
    ('Vice President',           'VP',              'human-typed form'),
    ('PM',                       'PM',              'canonical self-alias'),
    ('pm',                       'PM',              'legacy lowercase'),
    ('Project_Manager',          'PM',              'rex-procore legacy form'),
    ('Project Manager',          'PM',              'human-typed form'),
    ('VP_PM',                    'PM',              'AMBIGUOUS: resolves to PM so PM project authority plus portfolio.view via PM role. See baseline-reconciliation.md section 6.'),
    ('VP/PM',                    'PM',              'same ambiguity resolution as VP_PM'),
    ('GENERAL_SUPER',            'GENERAL_SUPER',   'canonical self-alias'),
    ('general_super',            'GENERAL_SUPER',   'legacy lowercase'),
    ('General_Superintendent',   'GENERAL_SUPER',   'rex-procore legacy form'),
    ('General Superintendent',   'GENERAL_SUPER',   'human-typed form'),
    ('LEAD_SUPER',               'LEAD_SUPER',      'canonical self-alias'),
    ('lead_super',               'LEAD_SUPER',      'legacy lowercase'),
    ('Lead_Superintendent',      'LEAD_SUPER',      'rex-procore legacy form'),
    ('Lead Superintendent',      'LEAD_SUPER',      'human-typed form'),
    ('ASSISTANT_SUPER',          'ASSISTANT_SUPER', 'canonical self-alias'),
    ('assistant_super',          'ASSISTANT_SUPER', 'legacy lowercase'),
    ('asst_super',               'ASSISTANT_SUPER', 'legacy shorter lowercase'),
    ('Asst_Superintendent',      'ASSISTANT_SUPER', 'rex-procore legacy form'),
    ('Assistant Superintendent', 'ASSISTANT_SUPER', 'human-typed form'),
    ('ACCOUNTANT',               'ACCOUNTANT',      'canonical self-alias'),
    ('accountant',               'ACCOUNTANT',      'legacy lowercase'),
    ('Project_Accountant',       'ACCOUNTANT',      'rex-procore legacy form'),
    ('Project Accountant',       'ACCOUNTANT',      'human-typed form')
ON CONFLICT (alias) DO NOTHING;


-- 5. BACKFILL rex.user_roles FROM EXISTING rex.user_accounts -----------
INSERT INTO rex.user_roles (user_account_id, role_id, is_primary, granted_at)
SELECT
    ua.id,
    r.id,
    true,
    COALESCE(ua.created_at, now())
FROM rex.user_accounts ua
JOIN rex.role_aliases  al ON al.alias = ua.global_role
JOIN rex.roles         r  ON r.slug  = al.canonical_role_slug
WHERE ua.global_role IS NOT NULL
ON CONFLICT (user_account_id, role_id) DO NOTHING;


-- 6. DEFAULT rex.user_preferences FOR EXISTING USERS -------------------
-- assistant_sidebar defaults true for admin/VP/PM users, false for
-- field roles. Session 3 shell reads this to toggle the right-rail.
INSERT INTO rex.user_preferences (user_account_id, preferences, feature_flags)
SELECT
    ua.id,
    '{}'::jsonb,
    CASE
        WHEN ua.is_admin
          OR ua.global_role IN ('vp', 'VP', 'pm', 'PM', 'VP_PM', 'VP/PM')
        THEN '{"assistant_sidebar": true}'::jsonb
        ELSE '{"assistant_sidebar": false}'::jsonb
    END
FROM rex.user_accounts ua
ON CONFLICT (user_account_id) DO NOTHING;
