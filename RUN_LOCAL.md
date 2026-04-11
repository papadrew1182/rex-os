# Rex OS — Local Development Setup

## Python version

Python 3.12+. Tested on 3.12 and 3.14.

## Install dependencies

```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Environment variables

Copy the template and fill in `DATABASE_URL` at minimum:

```bash
cp .env.example .env
```

Required for local dev:

| Variable | Example | Notes |
|----------|---------|-------|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/rex_os` | Standard libpq URI |
| `MIGRATE_SECRET` | `rex-migrate-2026` | Protects the `/api/admin/migrate` endpoint |
| `ENVIRONMENT` | `development` | Enables SQLAlchemy echo logging |
| `LOG_LEVEL` | `INFO` | Python log level |

Everything else (Procore, SMTP, Anthropic) is optional for Foundation work.

## Database creation

```bash
createdb rex_os
```

Or via psql:

```sql
CREATE DATABASE rex_os;
```

## Apply migrations (DDL + schema)

Two options:

### Option A: via the migrate endpoint

Start the server first (see below), then hit:

```bash
curl "http://localhost:8000/api/admin/migrate?secret=rex-migrate-2026"
```

This runs all 4 files in order:
1. `001_create_schema.sql` — rex schema + `set_updated_at()` trigger function
2. `rex2_canonical_ddl.sql` — 57 tables + deferred FKs + triggers
3. `rex2_foundation_bootstrap.sql` — foundation seed (companies, people, users, roles, projects, members, connectors)
4. `rex2_business_seed.sql` — closeout templates, template items, milestone function

### Option B: via psql directly

```bash
psql rex_os < ../migrations/001_create_schema.sql
psql rex_os < ../migrations/rex2_canonical_ddl.sql
```

## Run seeds

After DDL is applied:

```bash
psql rex_os < ../migrations/rex2_foundation_bootstrap.sql
psql rex_os < ../migrations/rex2_business_seed.sql
```

Then seed project milestones:

```bash
psql rex_os -c "
  SELECT rex.seed_project_milestones('40000000-0000-4000-a000-000000000001', 'multifamily');
  SELECT rex.seed_project_milestones('40000000-0000-4000-a000-000000000002', 'retail');
  SELECT rex.seed_project_milestones('40000000-0000-4000-a000-000000000003', 'retail');
  SELECT rex.seed_project_milestones('40000000-0000-4000-a000-000000000004', 'retail');
"
```

## Start FastAPI

```bash
cd backend
uvicorn main:app --reload --port 8000
```

OpenAPI docs at: http://localhost:8000/docs

## Validate the system

Run these in order. Read-only calls first, then mutating calls.

### Read-only validation

**1. List projects (expect 4 seeded)**

```bash
curl -s http://localhost:8000/api/projects/ | python -m json.tool
```

Expected: Bishop Modern, Jungle Lakewood, Jungle Fort Worth, Jungle Lovers Lane.

**2. Get a single company by ID**

```bash
curl -s http://localhost:8000/api/companies/00000000-0000-4000-a000-000000000001 | python -m json.tool
```

Expected: Rex Construction, company_type `gc`, status `active`.

**3. List people (expect 4 seeded)**

```bash
curl -s http://localhost:8000/api/people/ | python -m json.tool
```

Expected: Andrew Roberts, Mitch Andersen, Andrew Hudson, Krystal Hernandez.

**4. List role templates (expect 6 seeded)**

```bash
curl -s http://localhost:8000/api/role-templates/ | python -m json.tool
```

Expected: VP, PM, General Superintendent, Lead Superintendent, Assistant Superintendent, Accountant.

**5. List connector mappings (expect 5 seeded)**

```bash
curl -s http://localhost:8000/api/connector-mappings/ | python -m json.tool
```

Expected: 5 rows — 4 project-to-Procore mappings + 1 person-to-Procore mapping (Andrew Roberts). All with `connector: "procore"`.

### Mutating validation

These calls change the database. Run after read-only checks.

**6. Create a new project via POST**

```bash
curl -s -X POST http://localhost:8000/api/projects/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Project",
    "project_number": "TP-001",
    "status": "pre_construction",
    "project_type": "commercial",
    "city": "Austin",
    "state": "TX"
  }' | python -m json.tool
```

Expected: 201 response with a generated UUID `id`, `created_at`, and `updated_at` timestamps. Project count is now 5.

**7. PATCH an existing project**

```bash
curl -s -X PATCH http://localhost:8000/api/projects/40000000-0000-4000-a000-000000000002 \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Retail TI - Jungle Lakewood location",
    "status": "active"
  }' | python -m json.tool
```

Expected: Jungle Lakewood returned with `description` populated and `updated_at` refreshed.

## Verify table and row counts

Run this **after** the mutating validation calls above. The project count is 5 (4 seeded + 1 created in step 6).

```bash
psql rex_os -c "
  SELECT 'tables'                AS check, count(*) AS n
    FROM information_schema.tables
    WHERE table_schema = 'rex' AND table_type = 'BASE TABLE'
  UNION ALL SELECT 'projects',              count(*) FROM rex.projects
  UNION ALL SELECT 'companies',             count(*) FROM rex.companies
  UNION ALL SELECT 'people',                count(*) FROM rex.people
  UNION ALL SELECT 'user_accounts',         count(*) FROM rex.user_accounts
  UNION ALL SELECT 'role_templates',        count(*) FROM rex.role_templates
  UNION ALL SELECT 'project_members',       count(*) FROM rex.project_members
  UNION ALL SELECT 'connector_mappings',    count(*) FROM rex.connector_mappings
  UNION ALL SELECT 'closeout_templates',    count(*) FROM rex.closeout_templates
  UNION ALL SELECT 'closeout_template_items', count(*) FROM rex.closeout_template_items
  UNION ALL SELECT 'completion_milestones', count(*) FROM rex.completion_milestones;
"
```

Expected counts:

| Check | Count | Notes |
|-------|-------|-------|
| tables | 57 | All 6 domains |
| projects | 5 | 4 seeded + 1 from step 6 |
| companies | 2 | Rex Construction, Exxir Capital |
| people | 4 | |
| user_accounts | 4 | |
| role_templates | 6 | |
| project_members | 16 | 4 people x 4 projects |
| connector_mappings | 5 | 4 project + 1 person |
| closeout_templates | 3 | Standard, Retail, Multifamily |
| closeout_template_items | 102 | 34 items x 3 templates |
| completion_milestones | 18 | See breakdown below |

Milestone breakdown per project:

| Project | Type | Milestones |
|---------|------|------------|
| Bishop Modern | multifamily | 6 |
| Jungle Lakewood | retail | 4 |
| Jungle Fort Worth | retail | 4 |
| Jungle Lovers Lane | retail | 4 |
