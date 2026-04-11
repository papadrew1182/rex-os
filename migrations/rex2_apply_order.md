# Rex 2.0 — Apply Order

## Execution sequence

Run against a fresh or existing PostgreSQL database. All statements are idempotent.

```
1. 001_create_schema.sql            -- rex schema + set_updated_at() trigger function
2. rex2_canonical_ddl.sql           -- 57 tables + deferred FKs + triggers
3. rex2_foundation_bootstrap.sql    -- companies, people, users, roles, projects, members, connectors
4. rex2_business_seed.sql           -- closeout templates, template items, milestone function
```

## Post-seed: create project milestones

The milestone function must be called per-project after the business seed.
Safe to call repeatedly — uses `ON CONFLICT DO NOTHING` against the
`uq_completion_milestones_project_type` unique constraint.

```sql
SELECT rex.seed_project_milestones('40000000-0000-4000-a000-000000000001', 'multifamily');  -- Bishop Modern
SELECT rex.seed_project_milestones('40000000-0000-4000-a000-000000000002', 'retail');        -- Jungle Lakewood
SELECT rex.seed_project_milestones('40000000-0000-4000-a000-000000000003', 'retail');        -- Jungle Fort Worth
SELECT rex.seed_project_milestones('40000000-0000-4000-a000-000000000004', 'retail');        -- Jungle Lovers Lane
```

## Verification queries

```sql
-- 1. Table count (expect 57)
SELECT count(*) AS table_count
FROM information_schema.tables
WHERE table_schema = 'rex' AND table_type = 'BASE TABLE';

-- 2. Foundation row counts
SELECT 'companies'          AS tbl, count(*) FROM rex.companies          -- expect 2
UNION ALL SELECT 'people',             count(*) FROM rex.people           -- expect 4
UNION ALL SELECT 'user_accounts',      count(*) FROM rex.user_accounts   -- expect 4
UNION ALL SELECT 'role_templates',     count(*) FROM rex.role_templates  -- expect 6
UNION ALL SELECT 'projects',           count(*) FROM rex.projects        -- expect 4
UNION ALL SELECT 'project_members',    count(*) FROM rex.project_members -- expect 16
UNION ALL SELECT 'connector_mappings', count(*) FROM rex.connector_mappings; -- expect 5

-- 3. Business seed row counts
SELECT 'closeout_templates'      AS tbl, count(*) FROM rex.closeout_templates       -- expect 3
UNION ALL SELECT 'closeout_template_items', count(*) FROM rex.closeout_template_items; -- expect 102

-- 4. Milestone counts (after calling seed_project_milestones for all 4 projects)
SELECT 'completion_milestones' AS tbl, count(*) FROM rex.completion_milestones; -- expect 18 (6 + 4 + 4 + 4)

-- 5. Milestones per project
SELECT p.name, count(m.id) AS milestones
FROM rex.projects p
LEFT JOIN rex.completion_milestones m ON m.project_id = p.id
GROUP BY p.name ORDER BY p.name;
-- Bishop Modern:       6 (multifamily)
-- Jungle Fort Worth:   4 (retail)
-- Jungle Lakewood:     4 (retail)
-- Jungle Lovers Lane:  4 (retail)

-- 6. Verify no procore_id columns on core tables
SELECT table_name, column_name
FROM information_schema.columns
WHERE table_schema = 'rex' AND column_name = 'procore_id';
-- expect 0 rows

-- 7. Verify unique constraints exist
SELECT conname, conrelid::regclass
FROM pg_constraint
WHERE connamespace = 'rex'::regnamespace
  AND conname IN (
    'uq_user_accounts_person_id',
    'uq_user_accounts_email',
    'uq_project_members_project_person',
    'uq_completion_milestones_project_type'
  )
ORDER BY conname;
-- expect 4 rows

-- 8. Verify connector_mappings bridge
SELECT rex_table, connector, count(*) FROM rex.connector_mappings GROUP BY rex_table, connector;
-- expect: projects/procore = 4, people/procore = 1

-- 9. Verify triggers exist
SELECT trigger_name FROM information_schema.triggers
WHERE trigger_schema = 'rex' AND trigger_name LIKE 'trg_%_updated_at'
ORDER BY trigger_name;
-- expect 38 triggers
```

## Expected counts summary

| Table                    | Rows |
|--------------------------|------|
| companies                | 2    |
| people                   | 4    |
| user_accounts            | 4    |
| role_templates           | 6    |
| projects                 | 4    |
| project_members          | 16   |
| connector_mappings       | 5    |
| closeout_templates       | 3    |
| closeout_template_items  | 102  |
| completion_milestones    | 18   |
| **Total seeded rows**    | **164** |

## Key constraints enforced

| Constraint | Table | Columns |
|------------|-------|---------|
| `uq_user_accounts_person_id` | user_accounts | (person_id) |
| `uq_user_accounts_email` | user_accounts | (email) |
| `uq_project_members_project_person` | project_members | (project_id, person_id) |
| `uq_completion_milestones_project_type` | completion_milestones | (project_id, milestone_type) |

## Manual assumptions

- Passwords are bcrypt of `rex2026!` — change before any non-local deployment.
- Jungle projects mapped as `retail` (not `retail_ti` / `retail_ground_up` which are not valid enum values in Rex 2.0). Distinguish via project description or metadata if subtypes are needed later.
- Milestone seeding is a separate step because it requires knowing the project type at call time. The bootstrap does not auto-invoke it. The function is idempotent via `ON CONFLICT DO NOTHING`.
- `005_seed_data_2.sql` (worktree) is superseded — its role_templates used `gen_random_uuid()` and conflicted with the deterministic IDs in the foundation bootstrap. All role template data now lives solely in `rex2_foundation_bootstrap.sql`.
- `closeout_template_items.default_assignee_role` uses actual role slugs: `vp`, `general_super`, `lead_super`, `asst_super`, `accountant`. The legacy `gs` slug is not permitted.
