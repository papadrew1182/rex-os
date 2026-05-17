-- seed_dashboard_demo.sql
-- Demo-only additive dashboard seed for BM-001.
-- Idempotent inserts via natural-key existence checks / ON CONFLICT DO NOTHING.

DO $seed$
DECLARE
  v_project uuid;
  v_cost_code uuid;
  v_day date;
  i int;
BEGIN
  SELECT id INTO v_project
  FROM rex.projects
  WHERE project_number = 'BM-001'
  LIMIT 1;

  IF v_project IS NULL THEN
    RAISE NOTICE 'BM-001 project not found; skipping seed_dashboard_demo.sql';
    RETURN;
  END IF;

  SELECT id INTO v_cost_code
  FROM rex.cost_codes
  WHERE project_id = v_project
  ORDER BY sort_order NULLS LAST, code
  LIMIT 1;

  IF v_cost_code IS NULL THEN
    INSERT INTO rex.cost_codes (id, project_id, code, name, cost_type, sort_order, is_active)
    VALUES (
      '71000000-0000-4000-a000-000000000001',
      v_project,
      '99-100',
      'Dashboard Seed Cost Code',
      'subcontract',
      999,
      true
    )
    ON CONFLICT (id) DO NOTHING;

    SELECT id INTO v_cost_code
    FROM rex.cost_codes
    WHERE project_id = v_project
      AND code = '99-100'
    LIMIT 1;
  END IF;

  -- 28 daily logs (yesterday backward)
  FOR i IN 1..28 LOOP
    v_day := CURRENT_DATE - i;
    INSERT INTO rex.daily_logs (
      project_id, log_date, status, weather_summary, temp_high_f, temp_low_f, is_weather_delay, work_summary, safety_notes
    ) VALUES (
      v_project,
      v_day,
      CASE WHEN i <= 4 THEN 'draft' WHEN i <= 16 THEN 'submitted' ELSE 'approved' END,
      CASE (i % 4)
        WHEN 0 THEN 'Clear and sunny'
        WHEN 1 THEN 'Cloudy with light wind'
        WHEN 2 THEN 'Partly cloudy, warm'
        ELSE 'Overcast with light rain'
      END,
      75 - (i % 8),
      58 - (i % 8),
      (i % 11 = 0),
      'Dashboard seed: field progress and coordination updates captured.',
      'Daily safety briefing completed; no major incidents.'
    )
    ON CONFLICT (project_id, log_date) DO NOTHING;
  END LOOP;

  -- 12 RFIs
  FOR i IN 1..12 LOOP
    INSERT INTO rex.rfis (project_id, rfi_number, subject, question, status, priority, due_date)
    SELECT v_project,
           format('DASH-RFI-%s', lpad(i::text, 3, '0')),
           format('Dashboard RFI %s', i),
           'Seeded RFI for dashboard workload realism.',
           CASE WHEN i % 5 = 0 THEN 'answered' WHEN i % 2 = 0 THEN 'open' ELSE 'draft' END,
           CASE WHEN i % 3 = 0 THEN 'high' WHEN i % 3 = 1 THEN 'medium' ELSE 'low' END,
           CURRENT_DATE + (i - 6)
    WHERE NOT EXISTS (
      SELECT 1 FROM rex.rfis
      WHERE project_id = v_project
        AND rfi_number = format('DASH-RFI-%s', lpad(i::text, 3, '0'))
    );
  END LOOP;

  -- 8 submittals
  FOR i IN 1..8 LOOP
    INSERT INTO rex.submittals (project_id, submittal_number, title, submittal_type, status)
    SELECT v_project,
           format('DASH-SUB-%s', lpad(i::text, 3, '0')),
           format('Dashboard Submittal %s', i),
           CASE WHEN i % 3 = 0 THEN 'sample' WHEN i % 3 = 1 THEN 'shop_drawing' ELSE 'product_data' END,
           CASE WHEN i % 4 = 0 THEN 'approved' WHEN i % 2 = 0 THEN 'pending' ELSE 'submitted' END
    WHERE NOT EXISTS (
      SELECT 1 FROM rex.submittals
      WHERE project_id = v_project
        AND submittal_number = format('DASH-SUB-%s', lpad(i::text, 3, '0'))
    );
  END LOOP;

  -- 15 punch items
  FOR i IN 1..15 LOOP
    INSERT INTO rex.punch_items (project_id, punch_number, title, status, priority, due_date)
    SELECT v_project,
           9500 + i,
           format('Dashboard Punch Item %s', i),
           CASE WHEN i % 5 = 0 THEN 'ready_to_close' WHEN i % 2 = 0 THEN 'work_required' ELSE 'open' END,
           CASE WHEN i % 3 = 0 THEN 'high' WHEN i % 3 = 1 THEN 'medium' ELSE 'low' END,
           CURRENT_DATE + i
    WHERE NOT EXISTS (
      SELECT 1 FROM rex.punch_items
      WHERE project_id = v_project
        AND punch_number = 9500 + i
    );
  END LOOP;

  -- 10 budget line items (if cost code exists)
  IF v_cost_code IS NOT NULL THEN
    FOR i IN 1..10 LOOP
      INSERT INTO rex.budget_line_items (
        id, project_id, cost_code_id, description,
        original_budget, approved_changes, revised_budget,
        committed_costs, direct_costs, pending_changes,
        projected_cost, over_under
      )
      VALUES (
        ('70000000-0000-4000-a000-' || lpad((990000 + i)::text, 12, '0'))::uuid,
        v_project,
        v_cost_code,
        format('Dashboard Budget Line %s', i),
        100000 + (i * 25000),
        5000 * (i % 3),
        100000 + (i * 25000) + 5000 * (i % 3),
        85000 + (i * 18000),
        22000 + (i * 4000),
        3000 * (i % 4),
        108000 + (i * 22000),
        8000 - (i * 250)
      )
      ON CONFLICT (id) DO NOTHING;
    END LOOP;
  END IF;

  -- 12 tasks
  FOR i IN 1..12 LOOP
    INSERT INTO rex.tasks (project_id, task_number, title, status, priority, category, due_date)
    SELECT v_project,
           9600 + i,
           format('Dashboard Task %s', i),
           CASE WHEN i % 4 = 0 THEN 'complete' WHEN i % 2 = 0 THEN 'in_progress' ELSE 'open' END,
           CASE WHEN i % 3 = 0 THEN 'high' WHEN i % 3 = 1 THEN 'medium' ELSE 'low' END,
           CASE WHEN i % 3 = 0 THEN 'coordination' WHEN i % 3 = 1 THEN 'quality' ELSE 'admin' END,
           CURRENT_DATE + (i - 5)
    WHERE NOT EXISTS (
      SELECT 1 FROM rex.tasks
      WHERE project_id = v_project
        AND task_number = 9600 + i
    );
  END LOOP;

  -- 4 inspections
  FOR i IN 1..4 LOOP
    INSERT INTO rex.inspections (project_id, inspection_number, title, inspection_type, status, scheduled_date)
    SELECT v_project,
           format('DASH-INSP-%s', lpad(i::text, 3, '0')),
           format('Dashboard Inspection %s', i),
           CASE WHEN i % 2 = 0 THEN 'quality' ELSE 'safety' END,
           CASE WHEN i = 1 THEN 'scheduled' WHEN i = 2 THEN 'in_progress' WHEN i = 3 THEN 'passed' ELSE 'scheduled' END,
           CURRENT_DATE + (i * 2)
    WHERE NOT EXISTS (
      SELECT 1 FROM rex.inspections
      WHERE project_id = v_project
        AND inspection_number = format('DASH-INSP-%s', lpad(i::text, 3, '0'))
    );
  END LOOP;

  RAISE NOTICE 'seed_dashboard_demo.sql applied for BM-001 (%).', v_project;
END
$seed$;
