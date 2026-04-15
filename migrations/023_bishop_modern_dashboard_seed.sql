-- ============================================================================
-- 023_bishop_modern_dashboard_seed.sql
--
-- Supplemental demo data for the Bishop Modern (BM-001) project so the
-- redesigned dashboard has recent, realistic content to render. This file is
-- additive to rex2_demo_seed.sql — it does not replace or alter existing
-- rows. Every insert is guarded so the migration is safe to run repeatedly.
--
-- Conventions:
--   * Project resolved by project_number = 'BM-001' (no hardcoded UUID).
--   * Dates are relative to CURRENT_DATE so the dashboard always shows
--     "recent" content regardless of when the seed runs.
--   * Numbered records use a 9000-series range (task_number, punch_number)
--     and a DASH- prefix (rfi_number, submittal_number, inspection_number)
--     to stay clear of the existing demo seed's numbering.
--   * The NO-log-for-today choice is intentional: the dashboard's Quick Log
--     banner is supposed to appear, so we leave CURRENT_DATE open.
-- ============================================================================

DO $dash$
DECLARE
    v_project   uuid;
    v_company   uuid;
    v_company2  uuid;
    v_log_id    uuid;
    v_day       date;
    v_rec       record;
BEGIN
    -- ── Project lookup ──────────────────────────────────────────────────
    SELECT id INTO v_project
      FROM rex.projects
     WHERE project_number = 'BM-001'
     LIMIT 1;

    IF v_project IS NULL THEN
        RAISE NOTICE 'Bishop Modern project (BM-001) not found — skipping dashboard seed.';
        RETURN;
    END IF;

    -- ── Pick two companies for manpower entries ─────────────────────────
    -- Prefer non-Rex companies so we look like real subs.
    SELECT id INTO v_company
      FROM rex.companies
     WHERE name NOT ILIKE '%rex%'
     ORDER BY name
     LIMIT 1;

    SELECT id INTO v_company2
      FROM rex.companies
     WHERE name NOT ILIKE '%rex%'
       AND (v_company IS NULL OR id <> v_company)
     ORDER BY name
     OFFSET 1
     LIMIT 1;

    -- Fallback: if only one company exists, reuse it (the UNIQUE constraint
    -- on manpower_entries is (daily_log_id, company_id), so duplicates
    -- per-log are impossible regardless).
    IF v_company IS NULL THEN
        SELECT id INTO v_company FROM rex.companies ORDER BY name LIMIT 1;
    END IF;

    -- ── Daily logs: yesterday back to 10 days ago (skip today on purpose)
    FOR i IN 1..10 LOOP
        v_day := CURRENT_DATE - i;

        INSERT INTO rex.daily_logs (
            project_id, log_date, status,
            weather_summary, temp_high_f, temp_low_f, is_weather_delay,
            work_summary, safety_notes
        )
        VALUES (
            v_project,
            v_day,
            CASE WHEN i <= 2 THEN 'draft' WHEN i <= 6 THEN 'submitted' ELSE 'approved' END,
            CASE (i % 4)
                WHEN 0 THEN 'Partly cloudy, light breeze'
                WHEN 1 THEN 'Clear and sunny'
                WHEN 2 THEN 'Overcast with afternoon showers'
                ELSE 'Cold front moving through'
            END,
            72 - (i % 6),
            54 - (i % 6),
            (i % 7 = 0),
            'Dashboard seed: framing and MEP rough-in progressing on levels 2-3. Inspections staged for tomorrow.',
            'All crews briefed on fall-protection refresher. No incidents reported.'
        )
        ON CONFLICT (project_id, log_date) DO NOTHING;

        -- Grab the log id (newly inserted OR pre-existing) so we can attach
        -- manpower entries idempotently.
        SELECT id INTO v_log_id
          FROM rex.daily_logs
         WHERE project_id = v_project AND log_date = v_day
         LIMIT 1;

        IF v_log_id IS NOT NULL AND v_company IS NOT NULL THEN
            INSERT INTO rex.manpower_entries (
                daily_log_id, company_id, worker_count, hours, description
            )
            VALUES (
                v_log_id, v_company, 8 + (i % 5), (8 + (i % 5)) * 8, 'Framing crew'
            )
            ON CONFLICT (daily_log_id, company_id) DO NOTHING;

            IF v_company2 IS NOT NULL AND v_company2 <> v_company THEN
                INSERT INTO rex.manpower_entries (
                    daily_log_id, company_id, worker_count, hours, description
                )
                VALUES (
                    v_log_id, v_company2, 4 + (i % 3), (4 + (i % 3)) * 8, 'MEP rough-in'
                )
                ON CONFLICT (daily_log_id, company_id) DO NOTHING;
            END IF;
        END IF;
    END LOOP;

    -- ── RFIs (6 rows, mixed statuses + overdue dates) ───────────────────
    FOR v_rec IN
        SELECT * FROM (VALUES
            ('DASH-001', 'Clarify elevator pit waterproofing detail',      'open',     'high',   -3),
            ('DASH-002', 'Confirm storefront anchor spacing at grid C4',   'open',     'medium', -1),
            ('DASH-003', 'Revise mechanical chase dimensions level 2',     'draft',    'medium',  5),
            ('DASH-004', 'Missing spec section for interior sealants',     'open',     'low',    12),
            ('DASH-005', 'Coordination conflict — sprinkler vs ductwork',  'open',     'high',   -7),
            ('DASH-006', 'Roofing transition at parapet',                  'answered', 'medium', -10)
        ) AS t(rfi_number, subject, status, priority, due_offset)
    LOOP
        INSERT INTO rex.rfis (
            project_id, rfi_number, subject, question, status, priority, due_date
        )
        SELECT
            v_project,
            v_rec.rfi_number,
            v_rec.subject,
            'Please review and provide direction. Submitted via Rex dashboard demo seed.',
            v_rec.status,
            v_rec.priority,
            CURRENT_DATE + v_rec.due_offset
        WHERE NOT EXISTS (
            SELECT 1 FROM rex.rfis
             WHERE project_id = v_project AND rfi_number = v_rec.rfi_number
        );
    END LOOP;

    -- ── Submittals (4 rows) ─────────────────────────────────────────────
    FOR v_rec IN
        SELECT * FROM (VALUES
            ('DASH-S-001', 'Structural steel shop drawings — Area A', 'shop_drawing', 'submitted'),
            ('DASH-S-002', 'Curtain wall product data',                'product_data', 'pending'),
            ('DASH-S-003', 'Terrazzo flooring sample',                 'sample',       'approved'),
            ('DASH-S-004', 'Air barrier test report',                  'test_report',  'submitted')
        ) AS t(submittal_number, title, submittal_type, status)
    LOOP
        INSERT INTO rex.submittals (
            project_id, submittal_number, title, submittal_type, status
        )
        SELECT
            v_project, v_rec.submittal_number, v_rec.title,
            v_rec.submittal_type, v_rec.status
        WHERE NOT EXISTS (
            SELECT 1 FROM rex.submittals
             WHERE project_id = v_project AND submittal_number = v_rec.submittal_number
        );
    END LOOP;

    -- ── Punch items (8 rows, 9000-series) ───────────────────────────────
    FOR v_rec IN
        SELECT * FROM (VALUES
            (9001, 'Repaint drywall ding near elevator lobby',   'open',             'low'),
            (9002, 'Realign ceiling tile at grid B2',            'work_required',    'medium'),
            (9003, 'Touch up stain on wood reception desk',      'open',             'low'),
            (9004, 'Replace damaged door closer, room 203',      'work_required',    'medium'),
            (9005, 'Seal floor transition at suite 401',         'ready_for_review', 'medium'),
            (9006, 'Install missing cover plate at panel LP-2',  'open',             'high'),
            (9007, 'Adjust VAV box air flow level 3',            'work_required',    'medium'),
            (9008, 'Clean grout haze at lobby floor',            'ready_to_close',   'low')
        ) AS t(punch_number, title, status, priority)
    LOOP
        INSERT INTO rex.punch_items (
            project_id, punch_number, title, status, priority, due_date
        )
        SELECT
            v_project, v_rec.punch_number, v_rec.title,
            v_rec.status, v_rec.priority,
            CURRENT_DATE + (v_rec.punch_number - 9000) * 2
        WHERE NOT EXISTS (
            SELECT 1 FROM rex.punch_items
             WHERE project_id = v_project AND punch_number = v_rec.punch_number
        );
    END LOOP;

    -- ── Tasks (12 rows, 9000-series, mix of overdue/current) ────────────
    FOR v_rec IN
        SELECT * FROM (VALUES
            (9001, 'Review elevator coordination drawings',      'open',         'high',    'coordination', -4),
            (9002, 'Close out framing inspection punch list',    'in_progress',  'medium',  'quality',      -1),
            (9003, 'Update two-week look-ahead',                 'open',         'medium',  'admin',         0),
            (9004, 'Walk roofing transition with roofer',        'open',         'high',    'coordination',  2),
            (9005, 'File stormwater inspection report',          'open',         'low',     'safety',        7),
            (9006, 'Confirm mockup sign-off by architect',       'in_progress',  'high',    'quality',      -2),
            (9007, 'Schedule preconstruction meeting w/ MEP',    'open',         'medium',  'coordination',  4),
            (9008, 'Photo-document slab pour area C',            'complete',     'low',     'quality',      -5),
            (9009, 'Verify as-built markups for level 2',        'open',         'medium',  'admin',         3),
            (9010, 'Weekly safety walk — level 3',               'open',         'medium',  'safety',        1),
            (9011, 'Draft change event narrative RFI-5',         'open',         'high',    'admin',        -3),
            (9012, 'Update closeout tracker',                    'open',         'low',     'closeout',      6)
        ) AS t(task_number, title, status, priority, category, due_offset)
    LOOP
        INSERT INTO rex.tasks (
            project_id, task_number, title, status, priority, category, due_date
        )
        SELECT
            v_project, v_rec.task_number, v_rec.title,
            v_rec.status, v_rec.priority, v_rec.category,
            CURRENT_DATE + v_rec.due_offset
        WHERE NOT EXISTS (
            SELECT 1 FROM rex.tasks
             WHERE project_id = v_project AND task_number = v_rec.task_number
        );
    END LOOP;

    -- ── Inspections (6 rows) ────────────────────────────────────────────
    FOR v_rec IN
        SELECT * FROM (VALUES
            ('DASH-I-001', 'City framing inspection — level 2',    'municipal',  'scheduled',   2),
            ('DASH-I-002', 'Third-party waterproofing inspection', 'quality',    'scheduled',   4),
            ('DASH-I-003', 'MEP rough-in inspection level 3',      'mep_rough',  'in_progress', 0),
            ('DASH-I-004', 'Fire alarm pre-final',                 'mep_final',  'scheduled',   9),
            ('DASH-I-005', 'Safety walk — fall protection audit',  'safety',     'passed',     -5),
            ('DASH-I-006', 'Concrete pre-pour level 4',            'pre_concrete','scheduled',  7)
        ) AS t(inspection_number, title, inspection_type, status, scheduled_offset)
    LOOP
        INSERT INTO rex.inspections (
            project_id, inspection_number, title, inspection_type, status, scheduled_date
        )
        SELECT
            v_project, v_rec.inspection_number, v_rec.title,
            v_rec.inspection_type, v_rec.status,
            CURRENT_DATE + v_rec.scheduled_offset
        WHERE NOT EXISTS (
            SELECT 1 FROM rex.inspections
             WHERE project_id = v_project AND inspection_number = v_rec.inspection_number
        );
    END LOOP;

    RAISE NOTICE 'Bishop Modern dashboard seed applied (project %).', v_project;
END
$dash$;
