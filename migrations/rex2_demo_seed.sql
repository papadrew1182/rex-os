-- ============================================================
-- REX 2.0 — DEMO DATA SEED (Bishop Modern)
-- ============================================================
-- Optional, demo-only. Gated at the Python layer by
-- REX_DEMO_SEED=true in app/migrate.py::apply_demo_seed().
-- NOT part of MIGRATION_ORDER; production can run foundation
-- migrations without ever touching this file.
--
-- Gives the canonical seeded project (Bishop Modern) a small,
-- intentional, representative data set across every high-value
-- product surface so a fresh seeded environment demos like a
-- real live project rather than a mostly-blank app.
--
-- Rules:
--   - All INSERTs are idempotent (ON CONFLICT DO NOTHING).
--   - Every row uses deterministic UUIDs in the 6xxxxxxx range.
--   - No randomness, no bulk junk — 1 healthy + 1 problem state
--     per major page where it reasonably applies.
--   - Depends on foundation bootstrap (companies, people,
--     user_accounts, projects) already being seeded.
-- ============================================================


-- ════════════════════════════════════════════════════════════
-- 0. SHORTCUTS — reference existing foundation rows
-- ════════════════════════════════════════════════════════════
--   Project:  Bishop Modern          40000000-0000-4000-a000-000000000001
--   GC:       Rex Construction       00000000-0000-4000-a000-000000000001
--   Owner:    Exxir Capital          00000000-0000-4000-a000-000000000002
--   Roberts:  VP                     10000000-0000-4000-a000-000000000001
--   Andersen: General Super          10000000-0000-4000-a000-000000000002
--   Hudson:   Asst Super             10000000-0000-4000-a000-000000000003
--   Hernandez: Accountant            10000000-0000-4000-a000-000000000004


-- ════════════════════════════════════════════════════════════
-- 1. SUBCONTRACTOR COMPANIES + CONTACTS
--    Used by commitments, daily logs, punch items, inspections,
--    safety, warranties, insurance certs.
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.companies (id, name, trade, company_type, status, email, city, state)
VALUES
    ('60000000-0000-4000-a000-000000000010', 'Apex Concrete Co.',       'concrete',   'subcontractor', 'active', 'ops@apexconcrete.example',  'Dallas',     'TX'),
    ('60000000-0000-4000-a000-000000000011', 'Steel Frame Partners',    'structural', 'subcontractor', 'active', 'pm@steelframe.example',     'Fort Worth', 'TX'),
    ('60000000-0000-4000-a000-000000000012', 'Riverline Mechanical',    'mechanical', 'subcontractor', 'active', 'info@riverlinemech.example','Dallas',     'TX'),
    ('60000000-0000-4000-a000-000000000013', 'Bluewater Plumbing',      'plumbing',   'subcontractor', 'active', 'pm@bluewaterplumb.example', 'Dallas',     'TX'),
    ('60000000-0000-4000-a000-000000000014', 'Voltmark Electric',       'electrical', 'subcontractor', 'active', 'ops@voltmark.example',      'Dallas',     'TX'),
    ('60000000-0000-4000-a000-000000000015', 'NorthPoint Roofing',      'roofing',    'subcontractor', 'active', 'ops@northpointroof.example','Dallas',     'TX'),
    ('60000000-0000-4000-a000-000000000016', 'Glassline Exterior',      'glazing',    'subcontractor', 'active', 'pm@glassline.example',      'Dallas',     'TX'),
    ('60000000-0000-4000-a000-000000000017', 'Summit Drywall',          'drywall',    'subcontractor', 'active', 'info@summitdrywall.example','Dallas',     'TX'),
    ('60000000-0000-4000-a000-000000000018', 'Carver Painting',         'finishes',   'subcontractor', 'active', 'pm@carverpaint.example',    'Dallas',     'TX'),
    ('60000000-0000-4000-a000-000000000019', 'Sitewide Earthworks',     'sitework',   'subcontractor', 'active', 'ops@sitewide.example',      'Dallas',     'TX')
ON CONFLICT (id) DO NOTHING;

INSERT INTO rex.people (id, company_id, first_name, last_name, email, title, role_type, is_active)
VALUES
    ('60000000-0000-4000-a000-000000000020', '60000000-0000-4000-a000-000000000010', 'Ray',   'Kendrick', 'ray@apexconcrete.example',   'PM',          'external', true),
    ('60000000-0000-4000-a000-000000000021', '60000000-0000-4000-a000-000000000011', 'Dana',  'Oduya',    'dana@steelframe.example',    'Superintendent','external', true),
    ('60000000-0000-4000-a000-000000000022', '60000000-0000-4000-a000-000000000012', 'Marcus','Allen',    'marcus@riverlinemech.example','PM',         'external', true),
    ('60000000-0000-4000-a000-000000000023', '60000000-0000-4000-a000-000000000013', 'Priya', 'Shah',     'priya@bluewaterplumb.example','PM',         'external', true),
    ('60000000-0000-4000-a000-000000000024', '60000000-0000-4000-a000-000000000014', 'Evan',  'Wolff',    'evan@voltmark.example',      'PM',          'external', true),
    ('60000000-0000-4000-a000-000000000025', '60000000-0000-4000-a000-000000000015', 'Nina',  'Okafor',   'nina@northpointroof.example','PM',          'external', true),
    ('60000000-0000-4000-a000-000000000026', '60000000-0000-4000-a000-000000000016', 'Tom',   'Reyes',    'tom@glassline.example',      'PM',          'external', true),
    ('60000000-0000-4000-a000-000000000027', '60000000-0000-4000-a000-000000000017', 'Sam',   'Fischer',  'sam@summitdrywall.example',  'Super',       'external', true),
    ('60000000-0000-4000-a000-000000000028', '60000000-0000-4000-a000-000000000018', 'Liv',   'Nash',     'liv@carverpaint.example',    'PM',          'external', true),
    ('60000000-0000-4000-a000-000000000029', '60000000-0000-4000-a000-000000000019', 'Quinn', 'Park',     'quinn@sitewide.example',     'Super',       'external', true)
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- 2. SCHEDULE — 1 schedule, 12 activities, mixed states
--    Covers: open, complete, critical, drifting, constrained.
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.schedules (id, project_id, name, schedule_type, status, start_date, end_date, created_by)
VALUES
    ('60000000-0000-4000-a000-000000000100',
     '40000000-0000-4000-a000-000000000001',
     'Bishop Modern — Master Schedule', 'master', 'active',
     '2024-01-15', '2026-06-30',
     '10000000-0000-4000-a000-000000000001')
ON CONFLICT (id) DO NOTHING;

INSERT INTO rex.schedule_activities
    (id, schedule_id, activity_number, name, activity_type,
     start_date, end_date, duration_days, percent_complete, is_critical,
     baseline_start, baseline_end, variance_days, float_days,
     assigned_company_id, actual_start_date, actual_finish_date, wbs_code, sort_order)
VALUES
    -- COMPLETE — sitework, actual dates set, 100%
    ('60000000-0000-4000-a000-000000000101', '60000000-0000-4000-a000-000000000100',
     'A1000', 'Site Prep & Mass Grading', 'task',
     '2024-02-01', '2024-03-15', 43, 100, false,
     '2024-02-01', '2024-03-15', 0, 5,
     '60000000-0000-4000-a000-000000000019', '2024-02-01', '2024-03-14', '1.1', 10),

    -- COMPLETE — foundations
    ('60000000-0000-4000-a000-000000000102', '60000000-0000-4000-a000-000000000100',
     'A1010', 'Foundations & Slab on Grade', 'task',
     '2024-03-16', '2024-05-10', 55, 100, true,
     '2024-03-16', '2024-05-05', 5, 0,
     '60000000-0000-4000-a000-000000000010', '2024-03-18', '2024-05-12', '1.2', 20),

    -- IN-PROGRESS CRITICAL, on schedule
    ('60000000-0000-4000-a000-000000000103', '60000000-0000-4000-a000-000000000100',
     'A1020', 'Structural Steel Erection', 'task',
     '2024-05-11', '2024-08-20', 100, 65, true,
     '2024-05-11', '2024-08-15', 5, 0,
     '60000000-0000-4000-a000-000000000011', '2024-05-13', NULL, '1.3', 30),

    -- IN-PROGRESS, DRIFTING — variance +14 days
    ('60000000-0000-4000-a000-000000000104', '60000000-0000-4000-a000-000000000100',
     'A1030', 'Exterior Skin — Glazing', 'task',
     '2024-08-21', '2024-12-15', 116, 30, false,
     '2024-08-01', '2024-12-01', 14, 3,
     '60000000-0000-4000-a000-000000000016', '2024-08-21', NULL, '1.4', 40),

    -- IN-PROGRESS CRITICAL — MEP rough-in
    ('60000000-0000-4000-a000-000000000105', '60000000-0000-4000-a000-000000000100',
     'A1040', 'MEP Rough-In Levels 1-4', 'task',
     '2024-09-15', '2025-02-28', 166, 20, true,
     '2024-09-15', '2025-02-15', 13, 0,
     '60000000-0000-4000-a000-000000000012', '2024-09-16', NULL, '1.5', 50),

    -- NOT STARTED — drywall (waiting on MEP)
    ('60000000-0000-4000-a000-000000000106', '60000000-0000-4000-a000-000000000100',
     'A1050', 'Drywall & Interior Partitions', 'task',
     '2025-03-01', '2025-06-15', 106, 0, false,
     '2025-02-15', '2025-06-01', 14, 4,
     '60000000-0000-4000-a000-000000000017', NULL, NULL, '1.6', 60),

    -- NOT STARTED — finishes
    ('60000000-0000-4000-a000-000000000107', '60000000-0000-4000-a000-000000000100',
     'A1060', 'Interior Finishes & Paint', 'task',
     '2025-06-16', '2025-10-31', 137, 0, false,
     '2025-06-01', '2025-10-15', 15, 2,
     '60000000-0000-4000-a000-000000000018', NULL, NULL, '1.7', 70),

    -- NOT STARTED — roofing critical
    ('60000000-0000-4000-a000-000000000108', '60000000-0000-4000-a000-000000000100',
     'A1070', 'Roofing & Flashing', 'task',
     '2024-11-01', '2025-01-31', 92, 0, true,
     '2024-10-15', '2025-01-15', 17, 0,
     '60000000-0000-4000-a000-000000000015', NULL, NULL, '1.8', 80),

    -- NOT STARTED — site electrical
    ('60000000-0000-4000-a000-000000000109', '60000000-0000-4000-a000-000000000100',
     'A1080', 'Site Electrical & Lighting', 'task',
     '2025-08-01', '2025-10-31', 92, 0, false,
     '2025-08-01', '2025-10-31', 0, 10,
     '60000000-0000-4000-a000-000000000014', NULL, NULL, '1.9', 90),

    -- PUNCH WALK MILESTONE
    ('60000000-0000-4000-a000-000000000110', '60000000-0000-4000-a000-000000000100',
     'M100', 'Substantial Completion Walk', 'milestone',
     '2025-11-15', '2025-11-15', 0, 0, true,
     '2025-11-01', '2025-11-01', 14, 0,
     NULL, NULL, NULL, '2.0', 100),

    -- FINAL COMPLETION MILESTONE
    ('60000000-0000-4000-a000-000000000111', '60000000-0000-4000-a000-000000000100',
     'M200', 'Final Completion', 'milestone',
     '2026-01-31', '2026-01-31', 0, 0, true,
     '2026-01-15', '2026-01-15', 16, 0,
     NULL, NULL, NULL, '2.1', 110),

    -- CONSTRAINED — waiting on RFI
    ('60000000-0000-4000-a000-000000000112', '60000000-0000-4000-a000-000000000100',
     'A1090', 'Elevator Shaft Framing', 'task',
     '2024-09-01', '2024-10-31', 61, 10, false,
     '2024-09-01', '2024-10-15', 16, 1,
     '60000000-0000-4000-a000-000000000011', '2024-09-02', NULL, '1.10', 55)
ON CONFLICT (id) DO NOTHING;

-- One active schedule constraint (drives "constrained" dashboard state)
INSERT INTO rex.schedule_constraints
    (id, activity_id, constraint_type, source_type, source_id, status, severity, notes)
VALUES
    ('60000000-0000-4000-a000-000000000120',
     '60000000-0000-4000-a000-000000000112',
     'rfi_pending', 'rfi',
     '60000000-0000-4000-a000-000000000380',
     'active', 'red',
     'Elevator shaft dims blocked pending RFI-0001 answer.')
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- 3. COST CODES + BUDGET
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.cost_codes (id, project_id, code, name, cost_type, sort_order, is_active)
VALUES
    ('60000000-0000-4000-a000-000000000200', '40000000-0000-4000-a000-000000000001', '02-200', 'Sitework / Earthwork',  'subcontract', 10, true),
    ('60000000-0000-4000-a000-000000000201', '40000000-0000-4000-a000-000000000001', '03-300', 'Concrete — Structural', 'subcontract', 20, true),
    ('60000000-0000-4000-a000-000000000202', '40000000-0000-4000-a000-000000000001', '05-100', 'Structural Steel',      'subcontract', 30, true),
    ('60000000-0000-4000-a000-000000000203', '40000000-0000-4000-a000-000000000001', '07-500', 'Roofing',               'subcontract', 40, true),
    ('60000000-0000-4000-a000-000000000204', '40000000-0000-4000-a000-000000000001', '08-400', 'Glazing / Curtain Wall','subcontract', 50, true),
    ('60000000-0000-4000-a000-000000000205', '40000000-0000-4000-a000-000000000001', '09-200', 'Drywall & Framing',     'subcontract', 60, true),
    ('60000000-0000-4000-a000-000000000206', '40000000-0000-4000-a000-000000000001', '09-900', 'Painting & Coatings',   'subcontract', 70, true),
    ('60000000-0000-4000-a000-000000000207', '40000000-0000-4000-a000-000000000001', '22-000', 'Plumbing',              'subcontract', 80, true),
    ('60000000-0000-4000-a000-000000000208', '40000000-0000-4000-a000-000000000001', '23-000', 'HVAC / Mechanical',     'subcontract', 90, true),
    ('60000000-0000-4000-a000-000000000209', '40000000-0000-4000-a000-000000000001', '26-000', 'Electrical',            'subcontract', 100, true)
ON CONFLICT (id) DO NOTHING;

INSERT INTO rex.budget_line_items
    (id, project_id, cost_code_id, description,
     original_budget, approved_changes, revised_budget,
     committed_costs, direct_costs, pending_changes,
     projected_cost, over_under)
VALUES
    ('60000000-0000-4000-a000-000000000230', '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000200',
     'Sitework package',        850000,   0,   850000,  820000,  35000,     0,   855000,   5000),
    ('60000000-0000-4000-a000-000000000231', '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000201',
     'Structural concrete',    2100000, 45000, 2145000, 2120000, 110000,    0,  2230000,  85000),
    ('60000000-0000-4000-a000-000000000232', '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000202',
     'Structural steel',       3800000, 0,    3800000, 3800000, 1900000,    0,  3800000,      0),
    ('60000000-0000-4000-a000-000000000233', '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000203',
     'Roofing assembly',        560000, 0,     560000,  540000,     0,  30000,   570000,  10000),
    ('60000000-0000-4000-a000-000000000234', '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000204',
     'Glazing / curtain wall', 1250000, 0,    1250000, 1220000, 380000, 40000,  1260000,  10000),
    ('60000000-0000-4000-a000-000000000235', '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000208',
     'HVAC / mechanical',      1640000, 0,    1640000, 1600000, 220000,     0, 1600000,  -40000)
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- 4. PRIME CONTRACT + COMMITMENTS + CHANGE ORDERS
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.prime_contracts
    (id, project_id, contract_number, title, status,
     original_value, approved_cos, revised_value, billed_to_date,
     retention_rate, executed_date, owner_company_id)
VALUES
    ('60000000-0000-4000-a000-000000000250',
     '40000000-0000-4000-a000-000000000001',
     'PC-001', 'Bishop Modern — Prime Contract',
     'executed', 18500000, 45000, 18545000, 6200000, 5,
     '2024-01-05',
     '00000000-0000-4000-a000-000000000002')
ON CONFLICT (id) DO NOTHING;

INSERT INTO rex.commitments
    (id, project_id, vendor_id, commitment_number, title, contract_type,
     status, executed_date, original_value, approved_cos, revised_value,
     invoiced_to_date, remaining_to_invoice, retention_rate, retention_held,
     scope_of_work, created_by)
VALUES
    ('60000000-0000-4000-a000-000000000260',
     '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000019',
     'SC-001', 'Sitework & Mass Grading', 'subcontract',
     'executed', '2024-01-20',  850000, 0,  850000,  820000,  30000, 10,  82000,
     'Mass grading, utility trenching, site prep.',
     '10000000-0000-4000-a000-000000000001'),

    ('60000000-0000-4000-a000-000000000261',
     '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000010',
     'SC-002', 'Structural Concrete', 'subcontract',
     'executed', '2024-02-28',  2100000, 45000, 2145000, 2120000, 25000, 10, 214500,
     'Structural cast-in-place concrete: footings, foundation walls, slabs.',
     '10000000-0000-4000-a000-000000000001'),

    ('60000000-0000-4000-a000-000000000262',
     '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000011',
     'SC-003', 'Structural Steel', 'subcontract',
     'executed', '2024-04-10', 3800000, 0, 3800000, 1900000, 1900000, 10, 190000,
     'Structural steel supply and erection for all levels.',
     '10000000-0000-4000-a000-000000000001'),

    ('60000000-0000-4000-a000-000000000263',
     '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000012',
     'SC-004', 'Mechanical / HVAC', 'subcontract',
     'executed', '2024-06-15', 1640000, 0, 1640000,  220000, 1420000, 10,  22000,
     'Chillers, AHUs, ductwork, controls.',
     '10000000-0000-4000-a000-000000000001'),

    ('60000000-0000-4000-a000-000000000264',
     '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000016',
     'SC-005', 'Glazing & Curtain Wall', 'subcontract',
     'executed', '2024-07-01', 1250000, 0, 1250000,  380000,  870000, 10,  38000,
     'Curtain wall, storefronts, punched openings.',
     '10000000-0000-4000-a000-000000000001')
ON CONFLICT (id) DO NOTHING;

INSERT INTO rex.commitment_line_items (id, commitment_id, cost_code_id, description, quantity, unit, unit_cost, amount, sort_order)
VALUES
    ('60000000-0000-4000-a000-000000000270', '60000000-0000-4000-a000-000000000261', '60000000-0000-4000-a000-000000000201', 'Foundation concrete',  1,'ls',1250000,1250000, 10),
    ('60000000-0000-4000-a000-000000000271', '60000000-0000-4000-a000-000000000261', '60000000-0000-4000-a000-000000000201', 'Slabs on grade',       1,'ls', 600000, 600000, 20),
    ('60000000-0000-4000-a000-000000000272', '60000000-0000-4000-a000-000000000261', '60000000-0000-4000-a000-000000000201', 'Elevated slabs',       1,'ls', 250000, 250000, 30),
    ('60000000-0000-4000-a000-000000000273', '60000000-0000-4000-a000-000000000262', '60000000-0000-4000-a000-000000000202', 'Steel supply',         1,'ls',2400000,2400000, 10),
    ('60000000-0000-4000-a000-000000000274', '60000000-0000-4000-a000-000000000262', '60000000-0000-4000-a000-000000000202', 'Steel erection',       1,'ls',1400000,1400000, 20)
ON CONFLICT (id) DO NOTHING;

-- Change events: one healthy (approved) and one open problem
INSERT INTO rex.change_events
    (id, project_id, event_number, title, description, status, change_reason, event_type, scope, estimated_amount, prime_contract_id, created_by)
VALUES
    ('60000000-0000-4000-a000-000000000320',
     '40000000-0000-4000-a000-000000000001',
     'CE-001', 'Foundation rebar upgrade (owner direction)',
     'Owner requested upgraded rebar spec for podium slab.',
     'approved', 'owner_change', 'owner_change', 'in_scope', 45000,
     '60000000-0000-4000-a000-000000000250',
     '10000000-0000-4000-a000-000000000001'),
    ('60000000-0000-4000-a000-000000000321',
     '40000000-0000-4000-a000-000000000001',
     'CE-002', 'Curtain wall glazing delay — premium freight',
     'Freight premium to recover glazing schedule after supplier delay.',
     'open', 'unforeseen', 'tbd', 'tbd', 40000,
     '60000000-0000-4000-a000-000000000250',
     '10000000-0000-4000-a000-000000000001'),
    ('60000000-0000-4000-a000-000000000322',
     '40000000-0000-4000-a000-000000000001',
     'CE-003', 'MEP coordination rework — Level 3',
     'Mechanical/plumbing clash requiring limited rework in core.',
     'open', 'design_change', 'tbd', 'tbd', 28000,
     '60000000-0000-4000-a000-000000000250',
     '10000000-0000-4000-a000-000000000001')
ON CONFLICT (id) DO NOTHING;

INSERT INTO rex.change_event_line_items (id, change_event_id, cost_code_id, description, amount, sort_order)
VALUES
    ('60000000-0000-4000-a000-000000000325', '60000000-0000-4000-a000-000000000320', '60000000-0000-4000-a000-000000000201', 'Upgraded rebar material',  30000, 10),
    ('60000000-0000-4000-a000-000000000326', '60000000-0000-4000-a000-000000000320', '60000000-0000-4000-a000-000000000201', 'Additional labor',         15000, 20),
    ('60000000-0000-4000-a000-000000000327', '60000000-0000-4000-a000-000000000321', '60000000-0000-4000-a000-000000000204', 'Freight premium',          40000, 10),
    ('60000000-0000-4000-a000-000000000328', '60000000-0000-4000-a000-000000000322', '60000000-0000-4000-a000-000000000208', 'Rework labor',             18000, 10),
    ('60000000-0000-4000-a000-000000000329', '60000000-0000-4000-a000-000000000322', '60000000-0000-4000-a000-000000000208', 'Replacement fittings',     10000, 20)
ON CONFLICT (id) DO NOTHING;

-- One approved PCO → CCO link (ties change-event flow end to end)
INSERT INTO rex.potential_change_orders
    (id, change_event_id, commitment_id, pco_number, title, status, amount, cost_code_id, description, created_by)
VALUES
    ('60000000-0000-4000-a000-000000000335',
     '60000000-0000-4000-a000-000000000320',
     '60000000-0000-4000-a000-000000000261',
     'PCO-001', 'Rebar upgrade — concrete sub', 'approved', 45000,
     '60000000-0000-4000-a000-000000000201',
     'Approved PCO against SC-002 for rebar upgrade.',
     '10000000-0000-4000-a000-000000000001')
ON CONFLICT (id) DO NOTHING;

INSERT INTO rex.commitment_change_orders
    (id, commitment_id, cco_number, title, status, total_amount, executed_date, description, created_by)
VALUES
    ('60000000-0000-4000-a000-000000000340',
     '60000000-0000-4000-a000-000000000261',
     'CCO-001', 'Rebar upgrade — CCO', 'executed', 45000, '2024-05-01',
     'Executed against SC-002 after owner approval of CE-001.',
     '10000000-0000-4000-a000-000000000001')
ON CONFLICT (id) DO NOTHING;

INSERT INTO rex.pco_cco_links (id, pco_id, cco_id)
VALUES
    ('60000000-0000-4000-a000-000000000345',
     '60000000-0000-4000-a000-000000000335',
     '60000000-0000-4000-a000-000000000340')
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- 5. BILLING PERIODS + PAY APPS + LIEN WAIVERS
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.billing_periods (id, project_id, period_number, start_date, end_date, due_date, status)
VALUES
    ('60000000-0000-4000-a000-000000000290', '40000000-0000-4000-a000-000000000001', 1, '2024-03-01', '2024-03-31', '2024-04-25', 'closed'),
    ('60000000-0000-4000-a000-000000000291', '40000000-0000-4000-a000-000000000001', 2, '2024-04-01', '2024-04-30', '2024-05-25', 'closed'),
    ('60000000-0000-4000-a000-000000000292', '40000000-0000-4000-a000-000000000001', 3, '2024-05-01', '2024-05-31', '2024-06-25', 'closed'),
    ('60000000-0000-4000-a000-000000000293', '40000000-0000-4000-a000-000000000001', 4, '2024-06-01', '2024-06-30', '2024-07-25', 'closed'),
    ('60000000-0000-4000-a000-000000000294', '40000000-0000-4000-a000-000000000001', 5, '2024-07-01', '2024-07-31', '2024-08-25', 'open')
ON CONFLICT (id) DO NOTHING;

INSERT INTO rex.payment_applications
    (id, commitment_id, billing_period_id, pay_app_number, status,
     period_start, period_end,
     this_period_amount, total_completed, retention_held, retention_released,
     net_payment_due, submitted_date, approved_date, paid_date, created_by)
VALUES
    -- Concrete pay app — paid through period 3
    ('60000000-0000-4000-a000-000000000300',
     '60000000-0000-4000-a000-000000000261', '60000000-0000-4000-a000-000000000292', 3,
     'paid',      '2024-05-01','2024-05-31',
     420000, 1680000, 168000, 0, 378000,
     '2024-06-01','2024-06-12','2024-06-25',
     '10000000-0000-4000-a000-000000000004'),
    -- Concrete pay app — current submitted, not paid yet
    ('60000000-0000-4000-a000-000000000301',
     '60000000-0000-4000-a000-000000000261', '60000000-0000-4000-a000-000000000293', 4,
     'submitted', '2024-06-01','2024-06-30',
     200000, 1880000, 188000, 0, 180000,
     '2024-07-02', NULL, NULL,
     '10000000-0000-4000-a000-000000000004'),
    -- Steel first pay app — approved, pending payment
    ('60000000-0000-4000-a000-000000000302',
     '60000000-0000-4000-a000-000000000262', '60000000-0000-4000-a000-000000000293', 1,
     'approved',  '2024-06-01','2024-06-30',
     950000,  950000,  95000, 0, 855000,
     '2024-07-02','2024-07-10', NULL,
     '10000000-0000-4000-a000-000000000004'),
    -- Sitework pay app — paid
    ('60000000-0000-4000-a000-000000000303',
     '60000000-0000-4000-a000-000000000260', '60000000-0000-4000-a000-000000000291', 1,
     'paid',      '2024-04-01','2024-04-30',
     820000,  820000,  82000, 0, 738000,
     '2024-05-01','2024-05-12','2024-05-25',
     '10000000-0000-4000-a000-000000000004'),
    -- Open draft — mechanical first draw
    ('60000000-0000-4000-a000-000000000304',
     '60000000-0000-4000-a000-000000000263', '60000000-0000-4000-a000-000000000294', 1,
     'draft',     '2024-07-01','2024-07-31',
     220000,  220000,  22000, 0, 198000,
     NULL, NULL, NULL,
     '10000000-0000-4000-a000-000000000004')
ON CONFLICT (id) DO NOTHING;

INSERT INTO rex.lien_waivers
    (id, payment_application_id, vendor_id, waiver_type, status, amount, through_date, received_date, notes)
VALUES
    ('60000000-0000-4000-a000-000000000310',
     '60000000-0000-4000-a000-000000000300',
     '60000000-0000-4000-a000-000000000010',
     'conditional_progress', 'received', 378000, '2024-05-31', '2024-06-20',
     'Conditional waiver through period 3.'),
    ('60000000-0000-4000-a000-000000000311',
     '60000000-0000-4000-a000-000000000303',
     '60000000-0000-4000-a000-000000000019',
     'conditional_progress', 'received', 738000, '2024-04-30', '2024-05-22',
     'Conditional waiver through period 1.'),
    ('60000000-0000-4000-a000-000000000312',
     '60000000-0000-4000-a000-000000000301',
     '60000000-0000-4000-a000-000000000010',
     'conditional_progress', 'pending', 180000, '2024-06-30', NULL,
     'Pending — waiting on signed document from Apex.'),
    ('60000000-0000-4000-a000-000000000313',
     '60000000-0000-4000-a000-000000000302',
     '60000000-0000-4000-a000-000000000011',
     'conditional_progress', 'pending', 855000, '2024-06-30', NULL,
     'Pending — first steel draw.')
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- 6. DAILY LOGS + MANPOWER
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.daily_logs
    (id, project_id, log_date, status, weather_summary, temp_high_f, temp_low_f,
     is_weather_delay, work_summary, delay_notes, safety_notes, created_by)
VALUES
    ('60000000-0000-4000-a000-000000000350', '40000000-0000-4000-a000-000000000001',
     '2024-07-15', 'approved', 'Sunny, light wind', 94, 76,
     false, 'Level 3 deck pour continuing. Steel erection resumed on east side.',
     NULL, 'Heat stress protocol active — cold water stations refreshed 2x.',
     '10000000-0000-4000-a000-000000000003'),
    ('60000000-0000-4000-a000-000000000351', '40000000-0000-4000-a000-000000000001',
     '2024-07-16', 'approved', 'Heavy afternoon storms', 89, 72,
     true, 'Morning productive; afternoon halted 1:30pm due to lightning.',
     'Lost ~3.5 crew-hours to lightning hold.', 'Lightning protocol invoked.',
     '10000000-0000-4000-a000-000000000003'),
    ('60000000-0000-4000-a000-000000000352', '40000000-0000-4000-a000-000000000001',
     '2024-07-17', 'approved', 'Clear, hot', 96, 77,
     false, 'Catch-up day on deck pour. Steel crew continuing on column bases.',
     NULL, NULL,
     '10000000-0000-4000-a000-000000000003'),
    ('60000000-0000-4000-a000-000000000353', '40000000-0000-4000-a000-000000000001',
     '2024-07-18', 'submitted', 'Sunny', 97, 78,
     false, 'Steel erection on schedule. Glazing kickoff meeting held.',
     NULL, NULL,
     '10000000-0000-4000-a000-000000000003')
ON CONFLICT (id) DO NOTHING;

INSERT INTO rex.manpower_entries (id, daily_log_id, company_id, worker_count, hours, description)
VALUES
    ('60000000-0000-4000-a000-000000000360', '60000000-0000-4000-a000-000000000350', '60000000-0000-4000-a000-000000000010', 14, 8, 'Level 3 deck pour'),
    ('60000000-0000-4000-a000-000000000361', '60000000-0000-4000-a000-000000000350', '60000000-0000-4000-a000-000000000011', 10, 8, 'Steel erection east'),
    ('60000000-0000-4000-a000-000000000362', '60000000-0000-4000-a000-000000000350', '60000000-0000-4000-a000-000000000012',  6, 8, 'MEP layout'),
    ('60000000-0000-4000-a000-000000000363', '60000000-0000-4000-a000-000000000351', '60000000-0000-4000-a000-000000000010', 14, 5, 'Storm cut short'),
    ('60000000-0000-4000-a000-000000000364', '60000000-0000-4000-a000-000000000351', '60000000-0000-4000-a000-000000000011', 10, 5, 'Storm cut short'),
    ('60000000-0000-4000-a000-000000000365', '60000000-0000-4000-a000-000000000352', '60000000-0000-4000-a000-000000000010', 16, 9, 'Catch-up pour'),
    ('60000000-0000-4000-a000-000000000366', '60000000-0000-4000-a000-000000000352', '60000000-0000-4000-a000-000000000011', 12, 9, 'Column bases'),
    ('60000000-0000-4000-a000-000000000367', '60000000-0000-4000-a000-000000000353', '60000000-0000-4000-a000-000000000011', 12, 8, 'Steel erection'),
    ('60000000-0000-4000-a000-000000000368', '60000000-0000-4000-a000-000000000353', '60000000-0000-4000-a000-000000000016',  4, 6, 'Glazing layout')
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- 7. RFIs
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.rfis
    (id, project_id, rfi_number, subject, status, priority, question, answer,
     cost_impact, schedule_impact, assigned_to, ball_in_court, created_by, rfi_manager,
     due_date, answered_date, days_open, location, spec_section)
VALUES
    -- Open, over-SLA, elevator shaft blocker
    ('60000000-0000-4000-a000-000000000380', '40000000-0000-4000-a000-000000000001',
     'RFI-0001', 'Elevator shaft finished dims vs. structural opening',
     'open', 'high',
     'Architectural and structural drawings show different finished elevator shaft openings at Level 2. Please confirm controlling dim.',
     NULL, 'tbd', 'yes',
     '10000000-0000-4000-a000-000000000002',
     '10000000-0000-4000-a000-000000000002',
     '10000000-0000-4000-a000-000000000003',
     '10000000-0000-4000-a000-000000000001',
     '2024-07-05', NULL, 18,
     'Core — Level 2', '14 2100'),
    -- Answered healthy
    ('60000000-0000-4000-a000-000000000381', '40000000-0000-4000-a000-000000000001',
     'RFI-0002', 'Slab control joint spacing',
     'closed', 'medium',
     'Please clarify max control joint spacing for podium slab.',
     'Use 25ft max spacing as noted in spec 03 3000 §3.4.',
     'no', 'no',
     '10000000-0000-4000-a000-000000000001',
     NULL,
     '10000000-0000-4000-a000-000000000003',
     '10000000-0000-4000-a000-000000000001',
     '2024-04-10', '2024-04-08', 2,
     'Podium Level', '03 3000'),
    -- Open normal
    ('60000000-0000-4000-a000-000000000382', '40000000-0000-4000-a000-000000000001',
     'RFI-0003', 'Curtain wall anchor detail at column 4B',
     'open', 'medium',
     'Shop drawings show anchor interfering with embedded steel plate. Please advise.',
     NULL, 'tbd', 'tbd',
     '10000000-0000-4000-a000-000000000001',
     '10000000-0000-4000-a000-000000000001',
     '60000000-0000-4000-a000-000000000026',
     '10000000-0000-4000-a000-000000000001',
     '2024-08-01', NULL, 4,
     'Column 4B', '08 4400'),
    -- Closed with cost impact
    ('60000000-0000-4000-a000-000000000383', '40000000-0000-4000-a000-000000000001',
     'RFI-0004', 'HVAC rooftop unit curb height',
     'closed', 'low',
     'Rooftop unit curb conflicts with roof insulation assembly.',
     'Increase curb by 4in. Change covered under CE-003.',
     'yes', 'no',
     '10000000-0000-4000-a000-000000000002',
     NULL,
     '10000000-0000-4000-a000-000000000003',
     '10000000-0000-4000-a000-000000000001',
     '2024-06-20','2024-06-18', 1,
     'Roof', '23 7400')
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- 8. SUBMITTALS
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.submittal_packages
    (id, project_id, package_number, title, status, total_submittals, approved_count)
VALUES
    ('60000000-0000-4000-a000-000000000390', '40000000-0000-4000-a000-000000000001', 'SPK-001', 'Structural Concrete Submittals', 'open', 4, 3),
    ('60000000-0000-4000-a000-000000000391', '40000000-0000-4000-a000-000000000001', 'SPK-002', 'Structural Steel Submittals',    'open', 3, 2),
    ('60000000-0000-4000-a000-000000000392', '40000000-0000-4000-a000-000000000001', 'SPK-003', 'Mechanical / HVAC Submittals',   'open', 3, 0)
ON CONFLICT (id) DO NOTHING;

INSERT INTO rex.submittals
    (id, project_id, submittal_package_id, submittal_number, title, status, submittal_type,
     spec_section, current_revision, responsible_contractor, ball_in_court, submittal_manager_id,
     is_critical_path, due_date, submitted_date, approved_date, lead_time_days, required_on_site)
VALUES
    ('60000000-0000-4000-a000-000000000395', '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000390',
     'SUB-0001', 'Concrete mix design', 'approved', 'product_data',
     '03 3000', 1, '60000000-0000-4000-a000-000000000010', NULL,
     '10000000-0000-4000-a000-000000000001',
     false, '2024-03-01', '2024-02-20', '2024-02-28', 14, '2024-03-15'),
    ('60000000-0000-4000-a000-000000000396', '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000390',
     'SUB-0002', 'Reinforcing steel shop drawings', 'approved', 'shop_drawing',
     '03 2000', 2, '60000000-0000-4000-a000-000000000010', NULL,
     '10000000-0000-4000-a000-000000000001',
     false, '2024-03-10', '2024-03-02', '2024-03-20', 14, '2024-04-01'),
    ('60000000-0000-4000-a000-000000000397', '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000391',
     'SUB-0003', 'Structural steel shop drawings', 'rejected', 'shop_drawing',
     '05 1200', 2, '60000000-0000-4000-a000-000000000011',
     '60000000-0000-4000-a000-000000000021',
     '10000000-0000-4000-a000-000000000001',
     true, '2024-05-01', '2024-04-22', NULL, 28, '2024-06-01'),
    ('60000000-0000-4000-a000-000000000398', '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000391',
     'SUB-0004', 'High-strength bolts product data', 'approved', 'product_data',
     '05 1200', 1, '60000000-0000-4000-a000-000000000011', NULL,
     '10000000-0000-4000-a000-000000000001',
     false, '2024-05-15', '2024-05-01', '2024-05-10', 14, '2024-06-01'),
    ('60000000-0000-4000-a000-000000000399', '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000392',
     'SUB-0005', 'Chiller product data', 'submitted', 'product_data',
     '23 6200', 1, '60000000-0000-4000-a000-000000000012',
     '10000000-0000-4000-a000-000000000001',
     '10000000-0000-4000-a000-000000000001',
     true, '2024-08-15', '2024-08-05', NULL, 42, '2024-10-15'),
    ('60000000-0000-4000-a000-000000000400', '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000392',
     'SUB-0006', 'AHU product data', 'draft', 'product_data',
     '23 7300', 0, '60000000-0000-4000-a000-000000000012',
     '60000000-0000-4000-a000-000000000022',
     '10000000-0000-4000-a000-000000000001',
     true, '2024-08-30', NULL, NULL, 56, '2024-11-01'),
    ('60000000-0000-4000-a000-000000000401', '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000392',
     'SUB-0007', 'VAV boxes product data', 'draft', 'product_data',
     '23 3600', 0, '60000000-0000-4000-a000-000000000012',
     '60000000-0000-4000-a000-000000000022',
     '10000000-0000-4000-a000-000000000001',
     false, '2024-09-15', NULL, NULL, 35, '2024-11-20')
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- 9. PUNCH ITEMS
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.punch_items
    (id, project_id, punch_number, title, description, status, priority, punch_type,
     assigned_company_id, assigned_to, punch_manager_id, location,
     due_date, closed_date, days_open, is_critical_path)
VALUES
    ('60000000-0000-4000-a000-000000000405', '40000000-0000-4000-a000-000000000001', 1,
     'Touch up paint at north elevator lobby', 'Scuff marks on wall B4.',
     'open', 'low', 'finish',
     '60000000-0000-4000-a000-000000000018',
     '60000000-0000-4000-a000-000000000028',
     '10000000-0000-4000-a000-000000000003',
     'L1 Elevator Lobby', '2024-08-15', NULL, 5, false),
    ('60000000-0000-4000-a000-000000000406', '40000000-0000-4000-a000-000000000001', 2,
     'Adjust door closer — L2 stair A', 'Closer too aggressive, slams shut.',
     'ready_to_close', 'medium', 'mechanical',
     '60000000-0000-4000-a000-000000000017',
     '60000000-0000-4000-a000-000000000027',
     '10000000-0000-4000-a000-000000000003',
     'L2 Stair A', '2024-08-01', NULL, 9, false),
    ('60000000-0000-4000-a000-000000000407', '40000000-0000-4000-a000-000000000001', 3,
     'Replace cracked floor tile — L3 restroom',
     'Single cracked tile near urinal wall.',
     'work_required', 'medium', 'finish',
     '60000000-0000-4000-a000-000000000017',
     '60000000-0000-4000-a000-000000000027',
     '10000000-0000-4000-a000-000000000003',
     'L3 Restroom', '2024-08-10', NULL, 3, false),
    ('60000000-0000-4000-a000-000000000408', '40000000-0000-4000-a000-000000000001', 4,
     'Missing ceiling grid clip — L2 corridor',
     'Ceiling grid clip missing at grid E-4.',
     'closed', 'low', 'finish',
     '60000000-0000-4000-a000-000000000017',
     '60000000-0000-4000-a000-000000000027',
     '10000000-0000-4000-a000-000000000003',
     'L2 Corridor', '2024-07-10', '2024-07-09', 0, false),
    ('60000000-0000-4000-a000-000000000409', '40000000-0000-4000-a000-000000000001', 5,
     'GFCI outlet not tripping — kitchenette',
     'GFCI at kitchenette counter does not trip per test.',
     'open', 'high', 'electrical',
     '60000000-0000-4000-a000-000000000014',
     '60000000-0000-4000-a000-000000000024',
     '10000000-0000-4000-a000-000000000003',
     'L1 Kitchenette', '2024-07-25', NULL, 12, true)
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- 10. INSPECTIONS + INSPECTION ITEMS
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.inspections
    (id, project_id, inspection_number, title, inspection_type, status,
     scheduled_date, completed_date, inspector_name, inspecting_company_id,
     responsible_person_id, location, comments, created_by)
VALUES
    ('60000000-0000-4000-a000-000000000420', '40000000-0000-4000-a000-000000000001',
     'INS-001', 'Foundation rebar inspection', 'pre_concrete',
     'passed', '2024-04-02', '2024-04-02',
     'City of Dallas — Inspector Rivera', NULL,
     '10000000-0000-4000-a000-000000000002',
     'Foundation — SE quadrant', 'Passed with 2 minor items corrected on-site.',
     '10000000-0000-4000-a000-000000000003'),
    ('60000000-0000-4000-a000-000000000421', '40000000-0000-4000-a000-000000000001',
     'INS-002', 'L2 framing inspection', 'framing',
     'failed', '2024-06-15', '2024-06-15',
     'City of Dallas — Inspector Rivera', NULL,
     '10000000-0000-4000-a000-000000000002',
     'L2 framing', 'Failed — two connection details required rework.',
     '10000000-0000-4000-a000-000000000003'),
    ('60000000-0000-4000-a000-000000000422', '40000000-0000-4000-a000-000000000001',
     'INS-003', 'MEP rough inspection — L1', 'mep_rough',
     'scheduled', '2024-08-20', NULL,
     'City of Dallas — Inspector Tran', NULL,
     '10000000-0000-4000-a000-000000000002',
     'L1 MEP rough', NULL,
     '10000000-0000-4000-a000-000000000003')
ON CONFLICT (id) DO NOTHING;

INSERT INTO rex.inspection_items (id, inspection_id, item_number, description, result, comments)
VALUES
    ('60000000-0000-4000-a000-000000000430', '60000000-0000-4000-a000-000000000420', 1, 'Rebar size matches drawings', 'pass', NULL),
    ('60000000-0000-4000-a000-000000000431', '60000000-0000-4000-a000-000000000420', 2, 'Rebar cover at top and bottom', 'pass', NULL),
    ('60000000-0000-4000-a000-000000000432', '60000000-0000-4000-a000-000000000420', 3, 'Hook lengths at terminations', 'pass', 'Two short hooks lengthened on-site.'),
    ('60000000-0000-4000-a000-000000000433', '60000000-0000-4000-a000-000000000421', 1, 'Beam-to-column connection grid D',  'fail', 'Missing bolt per detail S-301.'),
    ('60000000-0000-4000-a000-000000000434', '60000000-0000-4000-a000-000000000421', 2, 'Moment frame stiffener grid E',     'fail', 'Stiffener plate thickness below spec.'),
    ('60000000-0000-4000-a000-000000000435', '60000000-0000-4000-a000-000000000421', 3, 'Decking fastener pattern',          'pass', NULL)
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- 11. TASKS
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.tasks
    (id, project_id, task_number, title, description, status, priority, category,
     assigned_to, assigned_company_id, due_date, completed_date, created_by)
VALUES
    ('60000000-0000-4000-a000-000000000450', '40000000-0000-4000-a000-000000000001', 1,
     'Circulate updated glazing schedule', NULL, 'open', 'medium', 'coordination',
     '10000000-0000-4000-a000-000000000002',
     '00000000-0000-4000-a000-000000000001',
     '2024-08-05', NULL,
     '10000000-0000-4000-a000-000000000001'),
    ('60000000-0000-4000-a000-000000000451', '40000000-0000-4000-a000-000000000001', 2,
     'Follow up with city on L2 framing re-inspection', NULL, 'in_progress', 'high', 'quality',
     '10000000-0000-4000-a000-000000000002',
     '00000000-0000-4000-a000-000000000001',
     '2024-08-01', NULL,
     '10000000-0000-4000-a000-000000000001'),
    ('60000000-0000-4000-a000-000000000452', '40000000-0000-4000-a000-000000000001', 3,
     'Send July pay app packet to owner', NULL, 'complete', 'medium', 'admin',
     '10000000-0000-4000-a000-000000000004',
     '00000000-0000-4000-a000-000000000001',
     '2024-08-02', '2024-08-01',
     '10000000-0000-4000-a000-000000000001'),
    ('60000000-0000-4000-a000-000000000453', '40000000-0000-4000-a000-000000000001', 4,
     'Schedule elevator kickoff meeting with sub', NULL, 'open', 'low', 'coordination',
     '10000000-0000-4000-a000-000000000002',
     '00000000-0000-4000-a000-000000000001',
     '2024-08-12', NULL,
     '10000000-0000-4000-a000-000000000001')
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- 12. MEETINGS + ACTION ITEMS
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.meetings
    (id, project_id, meeting_type, title, meeting_date, start_time, end_time, location, agenda, minutes, created_by)
VALUES
    ('60000000-0000-4000-a000-000000000460', '40000000-0000-4000-a000-000000000001',
     'owner_architect_contractor', 'OAC Meeting — July',
     '2024-07-10', '10:00:00', '11:30:00', 'Bishop Modern Trailer',
     'Schedule update, pay app review, RFI log, safety',
     'Schedule tracking 2wk behind on steel. Owner accepted CE-001. Approved July pay app. Elevator RFI remains open.',
     '10000000-0000-4000-a000-000000000001'),
    ('60000000-0000-4000-a000-000000000461', '40000000-0000-4000-a000-000000000001',
     'subcontractor', 'Weekly Sub Coordination — July 17',
     '2024-07-17', '07:30:00', '08:30:00', 'Bishop Modern Trailer',
     'Manpower, lookahead, conflicts',
     'Steel crew at 12. Concrete catching up on deck. MEP clash at L3 — CE-003 in motion.',
     '10000000-0000-4000-a000-000000000002')
ON CONFLICT (id) DO NOTHING;

INSERT INTO rex.meeting_action_items (id, meeting_id, item_number, description, assigned_to, due_date, status)
VALUES
    ('60000000-0000-4000-a000-000000000465', '60000000-0000-4000-a000-000000000460', 1, 'Close out elevator RFI with architect', '10000000-0000-4000-a000-000000000002', '2024-07-20', 'open'),
    ('60000000-0000-4000-a000-000000000466', '60000000-0000-4000-a000-000000000460', 2, 'Distribute approved CE-001 to subs',    '10000000-0000-4000-a000-000000000004', '2024-07-15', 'complete'),
    ('60000000-0000-4000-a000-000000000467', '60000000-0000-4000-a000-000000000461', 1, 'Re-baseline steel milestone in P6',     '10000000-0000-4000-a000-000000000002', '2024-07-25', 'open')
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- 13. OBSERVATIONS + SAFETY INCIDENTS
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.observations
    (id, project_id, observation_number, title, observation_type, status, priority,
     description, corrective_action, location, assigned_to, assigned_company_id,
     due_date, closed_date, created_by, contributing_behavior, contributing_condition)
VALUES
    ('60000000-0000-4000-a000-000000000475', '40000000-0000-4000-a000-000000000001', 1,
     'Unsecured materials at perimeter — L3', 'safety', 'open', 'high',
     'Stack of unsecured plywood within 6ft of L3 edge during windy conditions.',
     'Remove to staging area or secure with strapping.',
     'L3 East Perimeter',
     '10000000-0000-4000-a000-000000000003',
     '60000000-0000-4000-a000-000000000017',
     '2024-07-18', NULL,
     '10000000-0000-4000-a000-000000000002',
     'improper_housekeeping', 'weather_exposed'),
    ('60000000-0000-4000-a000-000000000476', '40000000-0000-4000-a000-000000000001', 2,
     'Quality — slab finishing tolerance', 'quality', 'closed', 'medium',
     'Podium slab finish outside tolerance in SW bay.',
     'Re-ground and re-tested. Passed.',
     'Podium SW',
     '10000000-0000-4000-a000-000000000002',
     '60000000-0000-4000-a000-000000000010',
     '2024-05-10', '2024-05-11',
     '10000000-0000-4000-a000-000000000002',
     NULL, NULL),
    ('60000000-0000-4000-a000-000000000477', '40000000-0000-4000-a000-000000000001', 3,
     'Housekeeping at stair A', 'housekeeping', 'open', 'low',
     'Debris accumulation along stair A landings.',
     'Daily cleanup cadence for stair.',
     'Stair A — all levels',
     '10000000-0000-4000-a000-000000000003',
     NULL,
     '2024-07-30', NULL,
     '10000000-0000-4000-a000-000000000003',
     'unclear_ownership', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO rex.safety_incidents
    (id, project_id, incident_number, title, incident_type, severity, status,
     incident_date, incident_time, location, description, root_cause, corrective_action,
     affected_person_id, affected_company_id, reported_by, is_osha_recordable, lost_time_days)
VALUES
    ('60000000-0000-4000-a000-000000000485', '40000000-0000-4000-a000-000000000001',
     'SI-001', 'Minor laceration — concrete crew',
     'first_aid', 'minor', 'closed',
     '2024-05-05', '14:20:00', 'Podium slab',
     'Worker sustained small hand laceration on rebar tie.',
     'Inadequate glove rating for rebar handling.',
     'Upgraded glove rating standard + toolbox talk.',
     NULL,
     '60000000-0000-4000-a000-000000000010',
     '10000000-0000-4000-a000-000000000003',
     false, 0)
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- 14. DRAWING AREAS + DRAWINGS + REVISIONS + SPECS
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.drawing_areas (id, project_id, name, sort_order)
VALUES
    ('60000000-0000-4000-a000-000000000490', '40000000-0000-4000-a000-000000000001', 'Architectural', 10),
    ('60000000-0000-4000-a000-000000000491', '40000000-0000-4000-a000-000000000001', 'Structural',    20),
    ('60000000-0000-4000-a000-000000000492', '40000000-0000-4000-a000-000000000001', 'Mechanical',    30),
    ('60000000-0000-4000-a000-000000000493', '40000000-0000-4000-a000-000000000001', 'Electrical',    40),
    ('60000000-0000-4000-a000-000000000494', '40000000-0000-4000-a000-000000000001', 'Plumbing',      50)
ON CONFLICT (id) DO NOTHING;

INSERT INTO rex.drawings
    (id, project_id, drawing_area_id, drawing_number, title, discipline,
     current_revision, current_revision_date, is_current)
VALUES
    ('60000000-0000-4000-a000-000000000495', '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000490', 'A-101', 'Level 1 Floor Plan',      'architectural', 2, '2024-05-15', true),
    ('60000000-0000-4000-a000-000000000496', '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000490', 'A-102', 'Level 2 Floor Plan',      'architectural', 1, '2024-03-01', true),
    ('60000000-0000-4000-a000-000000000497', '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000490', 'A-201', 'Building Elevations N/S', 'architectural', 1, '2024-03-01', true),
    ('60000000-0000-4000-a000-000000000498', '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000491', 'S-101', 'Foundation Plan',         'structural',    2, '2024-05-20', true),
    ('60000000-0000-4000-a000-000000000499', '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000491', 'S-301', 'Steel Framing Details',   'structural',    3, '2024-06-25', true),
    ('60000000-0000-4000-a000-000000000500', '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000492', 'M-101', 'HVAC Plan Level 1',       'mechanical',    1, '2024-04-05', true),
    ('60000000-0000-4000-a000-000000000501', '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000493', 'E-101', 'Electrical Plan Level 1', 'electrical',    1, '2024-04-05', true),
    ('60000000-0000-4000-a000-000000000502', '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000494', 'P-101', 'Plumbing Plan Level 1',   'plumbing',      1, '2024-04-05', true)
ON CONFLICT (id) DO NOTHING;

INSERT INTO rex.drawing_revisions
    (id, drawing_id, revision_number, revision_date, description, image_url, uploaded_by)
VALUES
    ('60000000-0000-4000-a000-000000000505', '60000000-0000-4000-a000-000000000495', 1, '2024-03-01', 'Issued for construction',        'demo://drawings/A-101-r1.pdf', '10000000-0000-4000-a000-000000000001'),
    ('60000000-0000-4000-a000-000000000506', '60000000-0000-4000-a000-000000000495', 2, '2024-05-15', 'Rev 2: owner tenant mods L1',   'demo://drawings/A-101-r2.pdf', '10000000-0000-4000-a000-000000000001'),
    ('60000000-0000-4000-a000-000000000507', '60000000-0000-4000-a000-000000000498', 1, '2024-02-10', 'Issued for construction',        'demo://drawings/S-101-r1.pdf', '10000000-0000-4000-a000-000000000001'),
    ('60000000-0000-4000-a000-000000000508', '60000000-0000-4000-a000-000000000498', 2, '2024-05-20', 'Rev 2: rebar upgrade per CE-001','demo://drawings/S-101-r2.pdf', '10000000-0000-4000-a000-000000000001'),
    ('60000000-0000-4000-a000-000000000509', '60000000-0000-4000-a000-000000000499', 3, '2024-06-25', 'Rev 3: connection corrections',  'demo://drawings/S-301-r3.pdf', '10000000-0000-4000-a000-000000000001')
ON CONFLICT (id) DO NOTHING;

INSERT INTO rex.specifications
    (id, project_id, section_number, title, division, current_revision, revision_date)
VALUES
    ('60000000-0000-4000-a000-000000000515', '40000000-0000-4000-a000-000000000001', '03 3000', 'Cast-in-Place Concrete',      '03 — Concrete',           1, '2024-02-01'),
    ('60000000-0000-4000-a000-000000000516', '40000000-0000-4000-a000-000000000001', '05 1200', 'Structural Steel Framing',    '05 — Metals',             2, '2024-04-15'),
    ('60000000-0000-4000-a000-000000000517', '40000000-0000-4000-a000-000000000001', '07 5400', 'Thermoplastic Roofing',       '07 — Thermal & Moisture', 1, '2024-02-01'),
    ('60000000-0000-4000-a000-000000000518', '40000000-0000-4000-a000-000000000001', '08 4400', 'Aluminum Curtain Wall',       '08 — Openings',           1, '2024-02-01'),
    ('60000000-0000-4000-a000-000000000519', '40000000-0000-4000-a000-000000000001', '23 7400', 'Packaged Rooftop Units',      '23 — HVAC',               2, '2024-06-20'),
    ('60000000-0000-4000-a000-000000000520', '40000000-0000-4000-a000-000000000001', '26 0500', 'Common Work for Electrical',  '26 — Electrical',         1, '2024-02-01')
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- 15. CORRESPONDENCE
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.correspondence
    (id, project_id, correspondence_number, subject, correspondence_type, status,
     from_person_id, to_person_id, body, sent_date, received_date, created_by)
VALUES
    ('60000000-0000-4000-a000-000000000525', '40000000-0000-4000-a000-000000000001',
     'LTR-0001', 'Notice of schedule impact — elevator RFI', 'letter', 'sent',
     '10000000-0000-4000-a000-000000000001', NULL,
     'Formal notice that RFI-0001 remains open and is now impacting the elevator shaft framing activity on the critical path.',
     '2024-07-15', NULL,
     '10000000-0000-4000-a000-000000000001'),
    ('60000000-0000-4000-a000-000000000526', '40000000-0000-4000-a000-000000000001',
     'LTR-0002', 'Transmittal — approved shop drawings SUB-0002', 'transmittal', 'sent',
     '10000000-0000-4000-a000-000000000001',
     '60000000-0000-4000-a000-000000000020',
     'Attached are the approved reinforcing shop drawings for Apex Concrete records.',
     '2024-03-21', NULL,
     '10000000-0000-4000-a000-000000000001'),
    ('60000000-0000-4000-a000-000000000527', '40000000-0000-4000-a000-000000000001',
     'LTR-0003', 'Request for insurance certificate renewal — Summit Drywall', 'letter', 'sent',
     '10000000-0000-4000-a000-000000000004',
     '60000000-0000-4000-a000-000000000027',
     'Your GL certificate expires in 30 days. Please provide renewal COI.',
     '2024-07-10', NULL,
     '10000000-0000-4000-a000-000000000004')
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- 16. PHOTO ALBUMS + PHOTOS + ATTACHMENTS
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.photo_albums (id, project_id, name, description, is_default, sort_order, created_by)
VALUES
    ('60000000-0000-4000-a000-000000000535', '40000000-0000-4000-a000-000000000001', 'Progress — July 2024', 'Weekly progress photos',      false, 10, '10000000-0000-4000-a000-000000000003'),
    ('60000000-0000-4000-a000-000000000536', '40000000-0000-4000-a000-000000000001', 'Safety Observations',  'Observations photo log',       false, 20, '10000000-0000-4000-a000-000000000003'),
    ('60000000-0000-4000-a000-000000000537', '40000000-0000-4000-a000-000000000001', 'Punch Walk',           'Close-out punch photo record', false, 30, '10000000-0000-4000-a000-000000000003')
ON CONFLICT (id) DO NOTHING;

-- Photos: metadata only — storage_key points to a demo placeholder.
INSERT INTO rex.photos
    (id, project_id, photo_album_id, filename, file_size, content_type,
     storage_url, storage_key, taken_at, location, description, uploaded_by)
VALUES
    ('60000000-0000-4000-a000-000000000540', '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000535',
     'deck-pour-l3.jpg',  1843200, 'image/jpeg',
     'demo://photos/deck-pour-l3.jpg', 'demo/photos/deck-pour-l3.jpg',
     '2024-07-15T14:25:00+00:00', 'L3 Deck', 'L3 deck pour in progress',
     '10000000-0000-4000-a000-000000000003'),
    ('60000000-0000-4000-a000-000000000541', '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000535',
     'steel-east.jpg',    1523400, 'image/jpeg',
     'demo://photos/steel-east.jpg', 'demo/photos/steel-east.jpg',
     '2024-07-16T09:10:00+00:00', 'East elevation', 'Steel erection east side',
     '10000000-0000-4000-a000-000000000003'),
    ('60000000-0000-4000-a000-000000000542', '40000000-0000-4000-a000-000000000001', '60000000-0000-4000-a000-000000000536',
     'unsecured-plywood.jpg', 980123, 'image/jpeg',
     'demo://photos/unsecured-plywood.jpg', 'demo/photos/unsecured-plywood.jpg',
     '2024-07-17T11:00:00+00:00', 'L3 East Perimeter',
     'Evidence photo for observation 1 (unsecured plywood).',
     '10000000-0000-4000-a000-000000000002')
ON CONFLICT (id) DO NOTHING;

-- Attachments: demo metadata rows linked to RFIs and lien waivers.
INSERT INTO rex.attachments
    (id, project_id, source_type, source_id, filename, file_size, content_type,
     storage_url, storage_key, uploaded_by)
VALUES
    ('60000000-0000-4000-a000-000000000550', '40000000-0000-4000-a000-000000000001',
     'rfi', '60000000-0000-4000-a000-000000000380',
     'elevator-shaft-markup.pdf', 345221, 'application/pdf',
     'demo://attachments/elevator-shaft-markup.pdf',
     'demo/attachments/elevator-shaft-markup.pdf',
     '10000000-0000-4000-a000-000000000003'),
    ('60000000-0000-4000-a000-000000000551', '40000000-0000-4000-a000-000000000001',
     'lien_waiver', '60000000-0000-4000-a000-000000000310',
     'apex-concrete-waiver-p3.pdf', 122334, 'application/pdf',
     'demo://attachments/apex-concrete-waiver-p3.pdf',
     'demo/attachments/apex-concrete-waiver-p3.pdf',
     '10000000-0000-4000-a000-000000000004'),
    ('60000000-0000-4000-a000-000000000552', '40000000-0000-4000-a000-000000000001',
     'submittal', '60000000-0000-4000-a000-000000000395',
     'concrete-mix-design.pdf', 221117, 'application/pdf',
     'demo://attachments/concrete-mix-design.pdf',
     'demo/attachments/concrete-mix-design.pdf',
     '10000000-0000-4000-a000-000000000004')
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- 17. WARRANTIES + CLAIMS + ALERTS
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.warranties
    (id, project_id, commitment_id, company_id, cost_code_id,
     system_or_product, manufacturer, scope_description, warranty_type,
     duration_months, start_date, expiration_date, status,
     is_letter_received, is_om_received, created_by)
VALUES
    ('60000000-0000-4000-a000-000000000560', '40000000-0000-4000-a000-000000000001',
     '60000000-0000-4000-a000-000000000263',
     '60000000-0000-4000-a000-000000000012',
     '60000000-0000-4000-a000-000000000208',
     'Chiller package', 'Trane',
     'Full warranty on chiller package per spec 23 6200.',
     'manufacturer', 60,
     '2025-11-15', '2030-11-15', 'active',
     false, false,
     '10000000-0000-4000-a000-000000000001'),
    ('60000000-0000-4000-a000-000000000561', '40000000-0000-4000-a000-000000000001',
     NULL,
     '60000000-0000-4000-a000-000000000015',
     '60000000-0000-4000-a000-000000000203',
     'TPO roof membrane', 'Carlisle',
     '20-year NDL roof warranty.',
     'manufacturer', 240,
     '2025-11-15', '2045-11-15', 'active',
     false, false,
     '10000000-0000-4000-a000-000000000001'),
    ('60000000-0000-4000-a000-000000000562', '40000000-0000-4000-a000-000000000001',
     '60000000-0000-4000-a000-000000000264',
     '60000000-0000-4000-a000-000000000016',
     '60000000-0000-4000-a000-000000000204',
     'Curtain wall assembly', 'Kawneer',
     '2-year workmanship warranty on curtain wall.',
     'labor_only', 24,
     '2025-11-15', '2027-11-15', 'active',
     false, false,
     '10000000-0000-4000-a000-000000000001')
ON CONFLICT (id) DO NOTHING;

INSERT INTO rex.warranty_claims
    (id, warranty_id, claim_number, title, description, status, priority,
     reported_date, resolved_date, days_open, location, cost_to_repair, is_covered_by_warranty, reported_by)
VALUES
    ('60000000-0000-4000-a000-000000000570',
     '60000000-0000-4000-a000-000000000561', 1,
     'Seam lift at NE corner (placeholder)',
     'Placeholder claim used for UI completeness — no live incident.',
     'open', 'medium',
     '2026-01-10', NULL, 3,
     'Roof NE corner', 1200, true,
     '10000000-0000-4000-a000-000000000003')
ON CONFLICT (id) DO NOTHING;

INSERT INTO rex.warranty_alerts (id, warranty_id, alert_type, alert_date, is_sent, recipient_id)
VALUES
    ('60000000-0000-4000-a000-000000000575',
     '60000000-0000-4000-a000-000000000562',
     '90_day', '2026-10-15', false,
     '10000000-0000-4000-a000-000000000001'),
    ('60000000-0000-4000-a000-000000000576',
     '60000000-0000-4000-a000-000000000560',
     '90_day', '2026-10-15', false,
     '10000000-0000-4000-a000-000000000001')
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- 18. INSURANCE CERTIFICATES
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.insurance_certificates
    (id, company_id, policy_type, carrier, policy_number,
     effective_date, expiry_date, limit_amount, status, notes)
VALUES
    ('60000000-0000-4000-a000-000000000580', '60000000-0000-4000-a000-000000000010',
     'gl', 'Hartford', 'GL-APEX-2024', '2024-01-01', '2024-12-31', 2000000, 'current',  'Apex Concrete GL current.'),
    ('60000000-0000-4000-a000-000000000581', '60000000-0000-4000-a000-000000000010',
     'wc', 'Hartford', 'WC-APEX-2024', '2024-01-01', '2024-12-31', 1000000, 'current',  'Apex Concrete WC current.'),
    ('60000000-0000-4000-a000-000000000582', '60000000-0000-4000-a000-000000000011',
     'gl', 'Travelers','GL-STEEL-2024','2024-01-15','2025-01-14',2000000, 'current',  'Steel Frame Partners GL current.'),
    ('60000000-0000-4000-a000-000000000583', '60000000-0000-4000-a000-000000000017',
     'gl', 'Chubb',    'GL-SUMMIT-2023','2023-08-01','2024-07-31',2000000, 'expiring_soon', 'Summit Drywall GL — expiring soon.'),
    ('60000000-0000-4000-a000-000000000584', '60000000-0000-4000-a000-000000000016',
     'gl', 'Zurich',   'GL-GLASS-2024','2024-02-01','2025-01-31',2000000, 'current',  'Glassline Exterior GL current.'),
    ('60000000-0000-4000-a000-000000000585', '60000000-0000-4000-a000-000000000014',
     'gl', 'Liberty',  'GL-VOLT-2023', '2023-05-01','2024-04-30',2000000, 'expired',  'Voltmark Electric GL — expired, renewal pending.')
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- 19. O&M MANUALS
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.om_manuals
    (id, project_id, spec_section, spec_title, required_count, received_count, status, vendor_company_id, notes)
VALUES
    ('60000000-0000-4000-a000-000000000590', '40000000-0000-4000-a000-000000000001',
     '23 6200', 'Chillers', 2, 0, 'pending',
     '60000000-0000-4000-a000-000000000012',
     'Expected at substantial completion.'),
    ('60000000-0000-4000-a000-000000000591', '40000000-0000-4000-a000-000000000001',
     '07 5400', 'TPO Roofing', 2, 1, 'partial',
     '60000000-0000-4000-a000-000000000015',
     '1 of 2 copies received — warranty letter still outstanding.'),
    ('60000000-0000-4000-a000-000000000592', '40000000-0000-4000-a000-000000000001',
     '08 4400', 'Curtain Wall', 2, 2, 'received',
     '60000000-0000-4000-a000-000000000016',
     'Complete — filed in closeout binder.'),
    ('60000000-0000-4000-a000-000000000593', '40000000-0000-4000-a000-000000000001',
     '26 0500', 'Electrical common work', 2, 0, 'pending',
     '60000000-0000-4000-a000-000000000014',
     NULL)
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- DEMO SEED COMPLETE
-- ════════════════════════════════════════════════════════════
