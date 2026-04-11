-- ============================================================
-- REX 2.0 — BUSINESS SEED DATA
-- Seeds: closeout_templates, closeout_template_items,
--        seed_project_milestones() function
--
-- Does NOT seed role_templates (those live in foundation_bootstrap).
-- Depends on: 001_create_schema.sql, rex2_canonical_ddl.sql, rex2_foundation_bootstrap.sql
-- ============================================================


-- ════════════════════════════════════════════════════════════
-- 1. CLOSEOUT TEMPLATES (3 rows)
-- ════════════════════════════════════════════════════════════

INSERT INTO rex.closeout_templates (id, name, project_type, is_default, created_at, updated_at)
VALUES
    ('a0000001-0000-0000-0000-000000000001'::uuid, 'Rex Standard 34-Item', 'all',         true,  now(), now()),
    ('a0000001-0000-0000-0000-000000000002'::uuid, 'Retail Closeout',      'retail',      false, now(), now()),
    ('a0000001-0000-0000-0000-000000000003'::uuid, 'Multifamily Closeout', 'multifamily', false, now(), now())
ON CONFLICT (id) DO NOTHING;


-- ════════════════════════════════════════════════════════════
-- 2. CLOSEOUT TEMPLATE ITEMS (34 items x 3 templates = 102 rows)
-- ════════════════════════════════════════════════════════════

DO $$
DECLARE
    t_id uuid;
    template_ids uuid[] := ARRAY[
        'a0000001-0000-0000-0000-000000000001'::uuid,
        'a0000001-0000-0000-0000-000000000002'::uuid,
        'a0000001-0000-0000-0000-000000000003'::uuid
    ];
    item_exists boolean;
BEGIN
    FOREACH t_id IN ARRAY template_ids LOOP

        -- Skip if items already exist for this template
        SELECT EXISTS(
            SELECT 1 FROM rex.closeout_template_items WHERE template_id = t_id LIMIT 1
        ) INTO item_exists;

        IF item_exists THEN
            CONTINUE;
        END IF;

        -- DOCUMENTATION (9 items)
        INSERT INTO rex.closeout_template_items (template_id, category, item_number, name, default_assignee_role, days_before_substantial, sort_order) VALUES
        (t_id, 'documentation', 1,  'As-built drawings submitted',            'lead_super',  30, 1),
        (t_id, 'documentation', 2,  'O&M manuals received & indexed',         'accountant',  21, 2),
        (t_id, 'documentation', 3,  'Warranty letters collected',              'accountant',  21, 3),
        (t_id, 'documentation', 4,  'Certificate of Occupancy uploaded',       'vp',           7, 4),
        (t_id, 'documentation', 5,  'Final inspections passed',                'lead_super',  14, 5),
        (t_id, 'documentation', 6,  'Owner/tenant training completed',         'lead_super',   7, 6),
        (t_id, 'documentation', 7,  'Spare parts & attic stock delivered',     'asst_super',  14, 7),
        (t_id, 'documentation', 8,  'Keys & access devices turned over',       'lead_super',   3, 8),
        (t_id, 'documentation', 9,  'Final cleaning complete',                 'asst_super',   3, 9),

        -- GENERAL (7 items)
        (t_id, 'general', 10, 'Punch list 100% complete',                'lead_super',  14, 10),
        (t_id, 'general', 11, 'Final pay applications submitted',        'accountant',   7, 11),
        (t_id, 'general', 12, 'CO log closed — all COs executed',        'vp',          14, 12),
        (t_id, 'general', 13, 'Retainage release processed',             'accountant',   0, 13),
        (t_id, 'general', 14, 'Insurance certificates current',          'accountant',  14, 14),
        (t_id, 'general', 15, 'Substantial completion certified',        'vp',           0, 15),
        (t_id, 'general', 16, 'Final completion certified',              'vp',        NULL, 16),

        -- MEP (7 items)
        (t_id, 'mep', 17, 'HVAC commissioning complete',              'lead_super',  21, 17),
        (t_id, 'mep', 18, 'Fire alarm acceptance test',               'lead_super',  14, 18),
        (t_id, 'mep', 19, 'Sprinkler system tested & tagged',         'lead_super',  14, 19),
        (t_id, 'mep', 20, 'Electrical panels labeled & documented',   'asst_super',  14, 20),
        (t_id, 'mep', 21, 'Plumbing test & balance complete',         'lead_super',  14, 21),
        (t_id, 'mep', 22, 'Elevator inspection passed',               'lead_super',  14, 22),
        (t_id, 'mep', 23, 'Generator test & documentation',           'lead_super',  14, 23),

        -- EXTERIOR (5 items)
        (t_id, 'exterior', 24, 'Roofing warranty received',              'accountant',  14, 24),
        (t_id, 'exterior', 25, 'Landscaping complete',                   'asst_super',   7, 25),
        (t_id, 'exterior', 26, 'Paving & striping complete',             'lead_super',   7, 26),
        (t_id, 'exterior', 27, 'Signage installed',                      'lead_super',   7, 27),
        (t_id, 'exterior', 28, 'Final grading & drainage verified',      'lead_super',  14, 28),

        -- INTERIOR (6 items)
        (t_id, 'interior', 29, 'Flooring complete & protected',          'asst_super',  14, 29),
        (t_id, 'interior', 30, 'Paint touch-up complete',                'asst_super',   7, 30),
        (t_id, 'interior', 31, 'Appliances installed & tested',          'lead_super',   7, 31),
        (t_id, 'interior', 32, 'Fixtures installed & operational',       'asst_super',   7, 32),
        (t_id, 'interior', 33, 'Countertops installed',                  'lead_super',  14, 33),
        (t_id, 'interior', 34, 'Millwork complete & inspected',          'lead_super',  14, 34);

    END LOOP;
END $$;


-- ════════════════════════════════════════════════════════════
-- 3. MILESTONE SEED FUNCTION
-- Creates project-specific milestones with Appendix B.1
-- evidence requirements stored as JSONB.
--
-- Usage:
--   SELECT rex.seed_project_milestones('<project_uuid>', 'retail');
--   SELECT rex.seed_project_milestones('<project_uuid>', 'multifamily');
-- ════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION rex.seed_project_milestones(
    p_project_id   uuid,
    p_project_type text
)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN

    IF p_project_type NOT IN ('retail', 'multifamily') THEN
        RAISE EXCEPTION 'Invalid project_type: %. Must be retail or multifamily.', p_project_type;
    END IF;

    -- RETAIL MILESTONES (4)
    IF p_project_type = 'retail' THEN

        INSERT INTO rex.completion_milestones
            (project_id, milestone_type, milestone_name, status, is_evidence_complete, evidence_requirements, sort_order)
        VALUES
        (p_project_id, 'rough_in', 'Rough-In Complete', 'pending', false,
         '{
           "checklist": [
             {"item": "Rough inspection reports uploaded", "source": "inspections"},
             {"item": "Inspection approval cards/emails uploaded", "source": "documents"},
             {"item": "Photos of completed MEP rough-in", "source": "photos"},
             {"item": "Schedule milestone task marked Complete with actual completion date", "source": "schedule"}
           ],
           "payout_percent": 25,
           "holdback_percent": 10
         }'::jsonb,
         1),

        (p_project_id, 'sheetrock_prime', 'Sheetrock Prime Ready for Finishes', 'pending', false,
         '{
           "checklist": [
             {"item": "Photos of primed sheetrock and ceilings", "source": "photos"},
             {"item": "Coordination sign-off memo (trades walkthrough)", "source": "documents"},
             {"item": "Finish-readiness checklist completed", "source": "inspections"},
             {"item": "Schedule milestone task marked Complete", "source": "schedule"}
           ],
           "payout_percent": 25,
           "holdback_percent": 10
         }'::jsonb,
         2),

        (p_project_id, 'substantial_completion', 'Substantial Completion / Turnover', 'pending', false,
         '{
           "checklist": [
             {"item": "Owner walkthrough notes/sign-off uploaded", "source": "documents"},
             {"item": "Punch list created and uploaded", "source": "punch"},
             {"item": "Turnover package uploaded (O&M binder, warranties, as-builts)", "source": "documents"},
             {"item": "CO/TCO uploaded (if applicable)", "source": "documents"},
             {"item": "Schedule milestone task marked Complete", "source": "schedule"}
           ],
           "payout_percent": 40,
           "holdback_percent": 10
         }'::jsonb,
         3),

        (p_project_id, 'holdback_release', 'Holdback Release', 'pending', false,
         '{
           "checklist": [
             {"item": "Punch list aging report generated (within Default Punch Aging Threshold)", "source": "punch"},
             {"item": "Warranty log current (no systemic defects)", "source": "warranties"},
             {"item": "Closeout status memo confirming deliverables on track", "source": "documents"},
             {"item": "45 days elapsed since opening", "source": "calendar"}
           ],
           "payout_percent": 10,
           "holdback_percent": 0,
           "trigger_condition": "45_days_post_opening",
           "gate_conditions": ["punch_aging_within_threshold", "no_systemic_warranty_defects", "closeout_on_track"]
         }'::jsonb,
         4)
        ON CONFLICT ON CONSTRAINT uq_completion_milestones_project_type DO NOTHING;

    -- MULTIFAMILY MILESTONES (6)
    ELSIF p_project_type = 'multifamily' THEN

        INSERT INTO rex.completion_milestones
            (project_id, milestone_type, milestone_name, status, is_evidence_complete, evidence_requirements, sort_order)
        VALUES
        (p_project_id, 'foundation_podium', 'Foundation / Podium', 'pending', false,
         '{
           "checklist": [
             {"item": "Foundation/podium inspection reports uploaded", "source": "inspections"},
             {"item": "Photos of structural work complete", "source": "photos"},
             {"item": "Schedule milestone task marked Complete", "source": "schedule"}
           ],
           "payout_percent": 20,
           "holdback_percent": 10
         }'::jsonb,
         1),

        (p_project_id, 'topped_out', 'Topped Out / Dried-In', 'pending', false,
         '{
           "checklist": [
             {"item": "Dried-in inspection reports (roof, envelope)", "source": "inspections"},
             {"item": "Photos showing building envelope complete", "source": "photos"},
             {"item": "Schedule milestone task marked Complete", "source": "schedule"}
           ],
           "payout_percent": 20,
           "holdback_percent": 10
         }'::jsonb,
         2),

        (p_project_id, 'sheetrock_prime', 'Sheetrock Prime Ready for Finishes', 'pending', false,
         '{
           "checklist": [
             {"item": "Photos of primed sheetrock", "source": "photos"},
             {"item": "Coordination sign-off memo", "source": "documents"},
             {"item": "Finish-readiness checklist completed", "source": "inspections"},
             {"item": "Schedule milestone task marked Complete", "source": "schedule"}
           ],
           "payout_percent": 20,
           "holdback_percent": 10
         }'::jsonb,
         3),

        (p_project_id, 'first_turnover_tco', 'First Turnover (TCO)', 'pending', false,
         '{
           "checklist": [
             {"item": "TCO uploaded", "source": "documents"},
             {"item": "Unit turnover checklist completed", "source": "inspections"},
             {"item": "Owner acceptance sign-off uploaded", "source": "documents"},
             {"item": "Punch list status report (aging acceptable)", "source": "punch"},
             {"item": "Schedule milestone task marked Complete", "source": "schedule"}
           ],
           "payout_percent": 20,
           "holdback_percent": 10
         }'::jsonb,
         4),

        (p_project_id, 'final_co', 'Final CO', 'pending', false,
         '{
           "checklist": [
             {"item": "Final CO uploaded", "source": "documents"},
             {"item": "Punch list report (<10% aged >30 days)", "source": "punch"},
             {"item": "Closeout deliverables log (as-builts, O&Ms, warranties)", "source": "documents"},
             {"item": "Schedule milestone task marked Complete", "source": "schedule"}
           ],
           "payout_percent": 20,
           "holdback_percent": 10
         }'::jsonb,
         5),

        (p_project_id, 'holdback_release', 'Holdback Release', 'pending', false,
         '{
           "checklist": [
             {"item": "Punch list aging report (within Default Threshold, <10% >30 days)", "source": "punch"},
             {"item": "Warranty log current", "source": "warranties"},
             {"item": "Closeout deliverables checklist complete", "source": "documents"},
             {"item": "45 days elapsed since Final CO", "source": "calendar"}
           ],
           "payout_percent": 10,
           "holdback_percent": 0,
           "trigger_condition": "45_days_post_final_co",
           "gate_conditions": ["punch_aging_within_threshold", "punch_aged_30d_under_10pct", "no_systemic_warranty_defects", "closeout_complete"]
         }'::jsonb,
         6)
        ON CONFLICT ON CONSTRAINT uq_completion_milestones_project_type DO NOTHING;

    END IF;

END;
$$;

COMMENT ON FUNCTION rex.seed_project_milestones(uuid, text) IS
    'Seeds completion milestones with Appendix B.1 evidence requirements. Call at project creation with project_type = retail or multifamily.';
