# Rex OS roadmap baseline reconciliation

> Session 2 (`feat/canonical-connectors`) — work block 0, 2026-04-14.
>
> This document resolves the false "small shell repo" baseline in the
> original session docs against the real state of `papadrew1182/rex-os`
> at `main @ 1a5e72d`. It is the authoritative mapping for Session 2's
> revised migration plan and for the downstream ownership boundaries
> between all three parallel sessions.
>
> **Direction given by the user (2026-04-14):** Option 4 — reconcile the
> roadmap + session docs against the real repo, then execute the charter's
> work packets A→I on top of the existing phase-1–53 codebase. No
> greenfield reset. No parallel `rexos_v2` schema. No separate repo.
> Extend, adapt, normalize.

---

## 1. The false baseline

All three session packets (`rex_os_session_1_ai_spine.md`,
`rex_os_session_2_connectors_canonical.md`,
`rex_os_session_3_sidebar_shell.md`) plus §5 of `rex_os_full_roadmap.md`
open with the same paragraph:

> `rex-os` is currently a very small shell repo with `backend/db.py`,
> `backend/main.py`, empty `backend/routers/`,
> placeholder React frontend, and one migration: `001_create_schema.sql`.

**This description is from an earlier planning snapshot and does not
match the current repo.** Since that paragraph was written the repo was
built through phases 1–53 of the original Rex OS plan, was promoted to
production at `main @ 3148f0c` on 2026-04-14, and continues to run live
at `rex-os.vercel.app` + `rex-os-api-production.up.railway.app`.

The architectural intent of the charter (multi-connector,
connector-scoped staging, `rex` as canonical product data, `rex.v_*` as
read-model contract, data-driven RBAC, source-link traceability,
first-class Exxir adapter) **remains locked**. Only the *starting point*
needs to be corrected.

## 2. Actual repo state at `main @ 1a5e72d`

### Migrations currently in `migrations/` + `MIGRATION_ORDER`

```
001_create_schema.sql                    — rex schema + set_updated_at trigger
rex2_canonical_ddl.sql                   — 57 canonical rex.* tables
rex2_foundation_bootstrap.sql            — companies, people, user_accounts, role_templates, projects, project_members, connector_mappings
rex2_business_seed.sql                   — closeout templates + seed_project_milestones()
002_field_parity_batch.sql               — adds change_event_line_items + audit fields
003_phase21_p1_batch.sql                 — adds insurance_certificates, schedule actuals/WBS, milestone forecast/percent
004_phase31_jobs_notifications.sql       — adds job_runs + notifications
005_phase38_phase39_p2_batch.sql         — adds om_manuals, schedule depth fields, observation contributing_*, closeout spec linkage

rex2_demo_seed.sql                       — optional, gated by REX_DEMO_SEED, not in MIGRATION_ORDER
```

Session 1 WIP (not yet committed to `origin`, parked on `feat/ai-spine`):
```
006_ai_chat_and_prompts.sql              — rex.chat_conversations, chat_messages, ai_prompt_registry
007_ai_action_catalog.sql                — rex.ai_action_catalog
```

### Existing `rex.*` tables (66 total)

Foundation (from `rex2_foundation_bootstrap.sql` + canonical DDL):
`companies`, `people`, `user_accounts`, `sessions`, `role_templates`,
`role_template_overrides`, `project_members`, `projects`,
`connector_mappings`

Schedule: `schedules`, `schedule_activities`, `activity_links`,
`schedule_constraints`, `schedule_snapshots`

Field Ops: `daily_logs`, `manpower_entries`, `punch_items`, `inspections`,
`inspection_items`, `observations`, `safety_incidents`, `photo_albums`,
`photos`, `tasks`, `meetings`, `meeting_action_items`

Financials: `cost_codes`, `budget_line_items`, `budget_snapshots`,
`prime_contracts`, `commitments`, `commitment_line_items`, `change_events`,
`change_event_line_items`, `potential_change_orders`,
`commitment_change_orders`, `pco_cco_links`, `billing_periods`,
`direct_costs`, `payment_applications`, `lien_waivers`

Document Mgmt: `drawing_areas`, `drawings`, `drawing_revisions`,
`specifications`, `rfis`, `submittal_packages`, `submittals`,
`attachments`, `correspondence`

Closeout: `closeout_templates`, `closeout_template_items`,
`closeout_checklists`, `closeout_checklist_items`, `warranties`,
`warranty_claims`, `warranty_alerts`, `completion_milestones`, `om_manuals`

Ops: `insurance_certificates`, `job_runs`, `notifications`

Session 1 WIP (uncommitted, on `feat/ai-spine`): `chat_conversations`,
`chat_messages`, `ai_prompt_registry`, `ai_action_catalog`

### Schemas

Only `rex`. No `connector_procore`, no `connector_exxir`.

### Backend code

- `backend/app/routes/` — **65 router files**, not empty. This is the
  dominant router convention in the repo.
- `backend/app/models/` — 7 ORM model files (foundation, schedule,
  field_ops, financials, document_management, closeout, notifications).
- `backend/app/services/storage.py` — storage adapter with `local`,
  `memory`, `s3` backends.
- `backend/app/rate_limit.py` — slowapi limiter on `/api/auth/login`.
- `backend/tests/` — **590 passing tests** as of 2026-04-14.

Session 1 has started (uncommitted on `feat/ai-spine`):
`backend/services/ai/`, `backend/repositories/` (chat, prompt, catalog),
`backend/schemas/` (assistant, catalog, chat), `backend/routers/assistant.py`.

Session 3 has committed (on `feat/sidebar-shell`, not merged):
frontend-only work under `frontend/src/{app,assistant,controlPlane,myday,hooks,lib}/`.

### Production posture

- Live on `main @ 3148f0c` (post-promotion), with `d119663` tip after the
  deployed-smoke fail-fast fix.
- 590 backend tests passing.
- Frontend build: 81 modules, ~620 KB raw / ~156 KB gzip.
- Railway backend + Vercel frontend deployed + healthy.

**Anything that modifies an existing rex.* table in a
non-additive way risks production downtime. The Session 2 revised plan
must stay additive and bridge rather than reshape.**

## 3. Charter object → real state mapping

This table is the authoritative source for every canonical object the
charter asks Session 2 to create. Four categories:

- **exists** — already present in the current schema, zero code change needed
- **extend** — present but needs additional columns / indexes / constraints
- **bridge** — present under a different name; create a view or rename at the contract surface
- **new** — genuinely missing, must be created

### RBAC / identity

| Charter object | Status | Real backing |
|---|---|---|
| `rex.roles` | **new** | `rex.role_templates` exists but conflates role + permission mode + home_screen + UI visibility. The new `rex.roles` is the minimal canonical role registry (slug, display_name, is_system, created_at). Existing `role_templates` stays in place as a **template** for UI provisioning and is not renamed. |
| `rex.role_aliases` | **new** | |
| `rex.permissions` | **new** | Capability strings like `assistant.chat`, `financials.view`, etc. First-class table. |
| `rex.role_permissions` | **new** | Many-to-many. |
| `rex.users` | **bridge** | `rex.user_accounts` is the existing user table. A `rex.v_users` view (not a new table) exposes `id, email, person_id, global_role` under the charter-shaped key set. The rest of the system keeps writing to `rex.user_accounts`; `/api/me` reads through `rex.v_users` + `rex.user_roles`. |
| `rex.user_roles` | **new** | Many-to-many user ↔ role. Replaces the single `user_accounts.global_role` text field over time; both can coexist during transition. |
| `rex.user_preferences` | **new** | Per-user KV (`feature_flags`, `assistant_sidebar`, etc). Consumed by `/api/me`. |
| `rex.user_project_assignments` | **bridge** | `rex.project_members` already provides user-project linkage. A `rex.v_user_project_assignments` view normalizes the contract shape without duplicating storage. |

### Organizations and projects

| Charter object | Status | Real backing |
|---|---|---|
| `rex.organizations` | **bridge** | Expose as a view filtered from `rex.companies WHERE company_type IN ('owner','gc')`. No new table. |
| `rex.projects` | **exists** | Full schema with geo, type, dates, value — `rex2_canonical_ddl.sql` line 16. |
| `rex.project_members` | **exists** | Canonical, via `rex2_foundation_bootstrap.sql`. |
| `rex.company_contacts` | **bridge** | `rex.people` already stores contacts; expose a view `rex.v_company_contacts` if a downstream surface needs it. |
| `rex.user_connector_accounts` / `rex.connector_accounts` | **new** | See connector registry section below. |

### Connector registry and sync ops

| Charter object | Status | Real backing |
|---|---|---|
| `rex.connectors` | **new** | Registry of available connector kinds — `procore`, `exxir`. Seeded. |
| `rex.connector_accounts` | **new** | Configured credentials + connection state per connector. |
| `rex.sync_runs` | **new** | One row per sync execution. |
| `rex.sync_cursors` | **new** | Per (connector_account, resource_type) pagination cursor. |
| `rex.connector_event_log` | **new** | Append-only event log (webhooks, errors, state changes). |
| `rex.source_links` | **extend** | `rex.connector_mappings` already exists with `(rex_table, rex_id, connector, external_id, external_url, synced_at)`. It is the charter's `source_links` in spirit. **Session 2 will evolve it** via `ALTER TABLE` additions (`metadata jsonb`, explicit `project_id uuid`) and expose the charter contract through a `rex.source_links` view that aliases column names. The underlying table name stays `connector_mappings` to avoid breaking phase 41–53 code that already references it. |

### Canonical core entities

| Charter object | Status | Real backing |
|---|---|---|
| `rex.project_sources` | **bridge** | A view filtered from `rex.connector_mappings WHERE rex_table = 'projects'`. No new table. |
| `rex.project_locations` | **new** | Genuinely missing. Project hierarchy (site → area → room). |
| `rex.cost_codes` | **exists** | Via `rex2_canonical_ddl.sql`. |
| `rex.trade_partners` | **bridge** | View from `rex.companies WHERE company_type = 'subcontractor'`. |
| `rex.vendors` | **bridge** | View from `rex.companies WHERE company_type IN ('supplier','subcontractor')`. |
| `rex.project_calendars` | **new** | Genuinely missing. Working days, holidays per project. |

### Project management domain

| Charter object | Status | Real backing |
|---|---|---|
| `rex.rfis` | **exists** | Full schema. |
| `rex.submittals` | **exists** | Full schema. |
| `rex.tasks` | **exists** | Full schema. |
| `rex.meetings` | **exists** | Full schema. |
| `rex.meeting_decisions` | **new** | Genuinely missing. Durable "we decided X in this meeting" rows. Distinct from `meeting_action_items` which tracks follow-ups. |
| `rex.pending_decisions` | **new** | Genuinely missing. Decisions needed but not yet made. |
| `rex.daily_logs` | **exists** | Full schema. |
| `rex.inspections` | **exists** | Full schema. |
| `rex.observations` | **exists** | Full schema. |
| `rex.punch_items` | **exists** | Full schema. |

### Financial / commercial domain

| Charter object | Status | Real backing |
|---|---|---|
| `rex.budgets` | **bridge** | A view rolling up `rex.budget_line_items` to project level. No new table. |
| `rex.commitments` | **exists** | Full schema + line items + CCOs + PCOs. |
| `rex.change_events` | **exists** | Plus `change_event_line_items`. |
| `rex.pcos` | **bridge** | `rex.potential_change_orders` exists. Charter name `pcos` aliases via view. |
| `rex.pay_apps` | **bridge** | `rex.payment_applications` exists. Charter name `pay_apps` aliases via view. |
| `rex.lien_waivers` | **exists** | Full schema. |
| `rex.procurement_items` | **new** | Genuinely missing. |
| `rex.billing_periods` | **exists** | Full schema. |

### Schedule domain

| Charter object | Status | Real backing |
|---|---|---|
| `rex.schedules` | **exists** | Full schema. |
| `rex.schedule_tasks` | **bridge** | `rex.schedule_activities` exists. Charter name `schedule_tasks` aliases via view. |
| `rex.schedule_dependencies` | **bridge** | `rex.activity_links` exists. Charter name aliases via view. |
| `rex.schedule_baselines` | **bridge** | Baseline fields already present inline on `schedule_activities.baseline_start/end`. A view normalizes them into a denormalized `schedule_baselines` shape if a downstream surface needs it. |
| `rex.schedule_milestones` | **bridge** | `rex.completion_milestones` exists. |
| `rex.delay_events` | **new** | Genuinely missing. |

### Documents / field ops

| Charter object | Status | Real backing |
|---|---|---|
| `rex.documents` | **bridge** | `rex.attachments` + `rex.correspondence` already cover this. View-based alias. |
| `rex.drawings` | **exists** | Full schema + `drawing_areas` + `drawing_revisions`. |
| `rex.spec_sections` | **bridge** | `rex.specifications` exists. Alias via view. |
| `rex.photos` | **exists** | Full schema + upload endpoint + bytes endpoint from phase 53. |
| `rex.closeout_items` | **bridge** | `rex.closeout_checklist_items` exists. View-based alias. |
| `rex.quality_findings` | **new** | Genuinely missing. Distinct from inspection items in that it's a project-level finding registry, not tied to one inspection. |
| `rex.weather_observations` | **new** | Genuinely missing. `daily_logs.weather_summary` exists but isn't structured. |

### Views — all net-new, no existing backing

- `rex.v_project_mgmt`
- `rex.v_financials`
- `rex.v_schedule`
- `rex.v_directory`
- `rex.v_portfolio`
- `rex.v_risk`
- `rex.v_myday`

Plus several smaller view aliases used by the bridges above:
`rex.v_users`, `rex.v_user_project_assignments`, `rex.v_organizations`,
`rex.v_vendors`, `rex.v_trade_partners`, `rex.v_project_sources`,
`rex.v_budgets`, `rex.v_pcos`, `rex.v_pay_apps`, `rex.v_schedule_tasks`,
`rex.v_schedule_dependencies`, `rex.v_schedule_baselines`,
`rex.v_schedule_milestones`, `rex.v_spec_sections`, `rex.v_closeout_items`,
`rex.v_documents`, `rex.source_links`, `rex.v_company_contacts`.

### Summary counts

- **exists (zero new code)**: 22 charter objects
- **bridge (view alias, no new storage)**: 21 charter objects
- **extend (ALTER TABLE)**: 1 (`connector_mappings` → source_links contract)
- **new (genuinely missing)**: 20 charter objects + 7 `rex.v_*` core views + ~18 bridge views

## 4. Migration numbering — real repo plan

### Collisions with existing slots

- `001` through `005` taken by phase 1–53 numeric migrations
- `006`, `007` taken by Session 1's WIP on `feat/ai-spine` (AI chat + action catalog)
- `rex2_canonical_ddl.sql`, `rex2_foundation_bootstrap.sql`,
  `rex2_business_seed.sql`, `rex2_demo_seed.sql` occupy the `rex2_*`
  prefix namespace

### Session 2 slot allocation (`feat/canonical-connectors`)

Session 2 takes the **`008` through `021`** range, a clean numeric
sequence that follows the repo's dominant `NNN_<topic>.sql` pattern.
Each slot aligns 1:1 with a charter migration, offset by +6 due to
slots 002–005 being taken by phase-41–53 work and 006–007 by Session 1.

| Charter # | Real repo slot | Filename | Purpose |
|---|---|---|---|
| 002 | **008** | `008_rbac_roles_permissions.sql` | rex.roles, rex.permissions, rex.role_permissions, rex.role_aliases |
| 003 | **009** | `009_user_roles_preferences.sql` | rex.user_roles, rex.user_preferences + rex.v_users bridge |
| 004 | **010** | `010_project_assignment_bridges.sql` | rex.v_user_project_assignments, rex.v_organizations, rex.project_locations, rex.project_calendars |
| 005 | **011** | `011_connector_registry.sql` | rex.connectors, rex.connector_accounts |
| 006 | **012** | `012_connector_procore_stage.sql` | CREATE SCHEMA connector_procore + starter staging tables |
| 007 | **013** | `013_connector_exxir_stage.sql` | CREATE SCHEMA connector_exxir + starter staging tables |
| 008 | **014** | `014_sync_runs_and_source_links.sql` | rex.sync_runs, rex.sync_cursors, rex.connector_event_log, evolve rex.connector_mappings + rex.source_links view |
| 009 | **015** | `015_canonical_core_additions.sql` | rex.project_locations, rex.project_calendars (if not in 010), plus view bridges for `rex.v_organizations` / `v_vendors` / `v_trade_partners` / `v_project_sources` |
| 010 | **016** | `016_canonical_pm_additions.sql` | rex.meeting_decisions, rex.pending_decisions |
| 011 | **017** | `017_canonical_financial_additions.sql` | rex.procurement_items + view bridges (`v_budgets`, `v_pcos`, `v_pay_apps`) |
| 012 | **018** | `018_canonical_schedule_additions.sql` | rex.delay_events + view bridges (`v_schedule_tasks`, `v_schedule_dependencies`, `v_schedule_baselines`, `v_schedule_milestones`) |
| 013 | **019** | `019_canonical_docs_quality_additions.sql` | rex.quality_findings, rex.weather_observations + view bridges (`v_documents`, `v_spec_sections`, `v_closeout_items`) |
| 023 | **020** | `020_seed_roles_and_aliases.sql` | INSERT canonical 6 roles, alias mappings, default permission grants |
| 024 | **021** | `021_canonical_read_views.sql` | rex.v_project_mgmt, v_financials, v_schedule, v_directory, v_portfolio, v_risk, v_myday |

Mapping is documented in this file + in the `MIGRATION_ORDER` list in
`backend/app/migrate.py` (Session 2 will append 008–021 after the
existing entries; Session 1 will insert 006–007 independently on its own
branch and rebase at merge time).

### Rules

- **Every Session 2 migration is additive.** `CREATE TABLE IF NOT
  EXISTS`, `CREATE SCHEMA IF NOT EXISTS`, `CREATE VIEW OR REPLACE`,
  `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, `INSERT ... ON CONFLICT DO
  NOTHING`. No `DROP`, no destructive column rewrites, no data
  deletion.
- **No existing canonical table is modified in a way that changes its
  column contract or breaks a current `backend/app/routes/` reader.**
  The only pre-existing table that changes is `rex.connector_mappings`,
  which gets `ADD COLUMN IF NOT EXISTS metadata jsonb DEFAULT '{}'::jsonb`
  and `ADD COLUMN IF NOT EXISTS project_id uuid`. Both are nullable, so
  every existing row stays valid.
- **Every migration file is idempotent** — re-runnable against a DB
  that has already had previous migration runs applied.

## 5. Backend route + service placement — repo-native, not charter-native

The charter suggests `backend/routers/` and `backend/services/` as the
new lane-wide locations. The real repo has 65 routers under
`backend/app/routes/` and all services under `backend/app/services/`.

**Session 2 will follow the repo convention**, not the charter's
suggested paths. New files:

- `backend/app/routes/identity.py` — GET `/api/me`, `/api/me/permissions`, `/api/context/current`
- `backend/app/routes/connectors.py` — GET `/api/connectors`, `/api/connectors/health`
- `backend/app/services/connectors/` — new subpackage
  - `base.py` — `ConnectorAdapter` ABC with `health_check`, `list_projects`, `fetch_*` methods
  - `registry.py` — in-process registry for available adapters
  - `sync_service.py` — sync orchestration, cursor handling, source-link writes
  - `procore/adapter.py`, `mapper.py`, `client.py`
  - `exxir/adapter.py`, `mapper.py`, `client.py`
- `backend/app/services/identity.py` — role resolution, permission expansion, alias translation
- `backend/app/repositories/` — new subpackage co-existing with Session 1's untracked `backend/repositories/`
  - `__init__.py`
  - `connector_repository.py`, `sync_run_repository.py`, `source_link_repository.py`, `identity_repository.py`

Note on Session 1's `backend/services/`, `backend/repositories/`,
`backend/schemas/`, `backend/routers/` at the repo root: those are
Session 1's lane and are NOT in Session 2's scope. Session 1 adopted a
different convention on its branch; harmonizing the two conventions is a
post-merge cleanup, not Session 2's responsibility.

## 6. Charter contracts preserved

The following remain **locked as the charter specifies** and must not
drift during Session 2 execution:

### Canonical roles
- `VP`, `PM`, `GENERAL_SUPER`, `LEAD_SUPER`, `ASSISTANT_SUPER`, `ACCOUNTANT`

### Legacy alias mappings to seed in `rex.role_aliases`
- `General_Superintendent` → `GENERAL_SUPER`
- `Lead_Superintendent` → `LEAD_SUPER`
- `Asst_Superintendent` → `ASSISTANT_SUPER`
- `vp` (lowercase, as currently used by `user_accounts.global_role`) → `VP`
- `VP_PM` → **`PM`**, documented ambiguity resolution: in the phase
  1–53 codebase, `VP_PM` rows always gave project-level PM authority
  while also letting the user see the Portfolio view, which is a
  PM + read-only-VP combination. The decision here is that `VP_PM`
  aliases to `PM` for permission resolution, while the portfolio-view
  privilege is granted via a separate `portfolio.view` permission
  attached to the PM role. This avoids silently implying VP-level
  financial authority.

Future roles beyond the six are explicitly supported — `rex.roles` is a
plain table, not an enum, and `is_system=false` rows can be added
without a schema change.

### Endpoint shapes
`GET /api/me`, `GET /api/me/permissions`, `GET /api/context/current`,
`GET /api/connectors`, `GET /api/connectors/health` all respond with the
exact JSON shapes documented in
`docs/roadmaps/parallel-sessions/rex_os_session_2_connectors_canonical.md`
§"Identity and context endpoints owned by this lane". Downstream lanes
(`feat/ai-spine`, `feat/sidebar-shell`) already depend on these shapes
via `frontend/src/hooks/useMe.js`, `usePermissions.js`, and
`useCurrentContext.js` — Session 2 will not change the shapes without
coordinating.

### Read-model names
`rex.v_project_mgmt`, `rex.v_financials`, `rex.v_schedule`,
`rex.v_directory`, `rex.v_portfolio`, `rex.v_risk`, `rex.v_myday` are
the exact names of the charter-locked read models. The smaller bridge
views use `rex.v_<charter_name>` naming to avoid colliding with the
existing `rex.<table_name>` storage.

## 7. Source-link evolution plan

The charter specifies this shape for `rex.source_links`:

```text
id uuid primary key
connector_key text not null
source_table text not null
source_id text not null
canonical_table text not null
canonical_id uuid not null
project_id uuid null
metadata jsonb not null default '{}'::jsonb
unique (connector_key, source_table, source_id)
```

The existing `rex.connector_mappings` has:

```text
id uuid primary key
rex_table text not null
rex_id uuid not null
connector text not null
external_id text not null
external_url text null
synced_at timestamptz null
created_at timestamptz not null
unique (rex_table, connector, external_id)
```

Evolution steps (all in migration `014_sync_runs_and_source_links.sql`):

1. `ALTER TABLE rex.connector_mappings ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb`
2. `ALTER TABLE rex.connector_mappings ADD COLUMN IF NOT EXISTS project_id uuid REFERENCES rex.projects(id)`
3. `ALTER TABLE rex.connector_mappings ADD COLUMN IF NOT EXISTS source_table text`
   (Leave existing rows with NULL `source_table`; new writes set it.)
4. Create view `rex.source_links` that projects column names into the
   charter contract:

```sql
CREATE OR REPLACE VIEW rex.source_links AS
SELECT
    id,
    connector          AS connector_key,
    COALESCE(source_table, rex_table) AS source_table,
    external_id        AS source_id,
    rex_table          AS canonical_table,
    rex_id             AS canonical_id,
    project_id,
    metadata,
    external_url,
    synced_at,
    created_at
FROM rex.connector_mappings;
```

5. The existing `(rex_table, connector, external_id)` unique constraint
   already enforces the charter's uniqueness requirement on
   `(connector_key, source_table, source_id)` in practice — the
   `source_table` column is effectively synonymous with `rex_table` for
   legacy rows and enforced at write time for new rows.

No renames, no data rewrites.

## 8. Gate criteria — real repo interpretation

The charter defines three merge gates (A: schema split freeze; B: RBAC
freeze; C: view freeze). Interpreted against the real repo:

### Gate A — schema split freeze
- `connector_procore` and `connector_exxir` schemas exist
- No canonical product data is placed in either connector schema
- `rex` has not gained any connector-native leakage (no `procore_*`
  column prefixes, no Procore-specific enums, no Procore pagination
  metadata in rex tables)
- `rex.source_links` view is resolvable from `rex.connector_mappings`

### Gate B — RBAC freeze
- `rex.roles` seeded with six canonical entries
- `rex.role_aliases` seeded with documented legacy mappings including
  the `VP_PM` ambiguity decision
- `rex.permissions` table has at least the Session 1 + Session 3
  initially-needed rows (`assistant.chat`, `assistant.catalog.read`,
  `financials.view`, `schedule.view`, `myday.view`, `portfolio.view`)
- `GET /api/me/permissions` resolves permissions through the join
  `user_accounts → user_roles → role_permissions → permissions`, not
  through a hardcoded config file

### Gate C — view freeze
- All seven top-level `rex.v_*` views exist at least in starter form
- `rex.v_project_mgmt`, `rex.v_financials`, `rex.v_schedule` are
  complete enough for Session 1's dashboard + assistant read paths
- `rex.v_myday` is complete enough for Session 3's MyDay surface

## 9. Definition of done for Session 2 first merge (revised)

- [x] `docs/roadmaps/baseline-reconciliation.md` committed (this file)
- [ ] `rex_os_full_roadmap.md` updated: false "small shell repo"
      paragraph replaced with a pointer to this doc
- [ ] Three session packet docs each get a 5-line preamble noting the
      reconciliation and pointing at this doc
- [ ] Migrations `008` through `021` exist as at least stub files with
      lane ownership headers
- [ ] Migrations `008`, `009`, `011`, `012`, `013`, `014`, `020`, `021`
      have real content (RBAC, connectors, staging schemas, sync runs,
      seeds, views — the critical path)
- [ ] `MIGRATION_ORDER` in `backend/app/migrate.py` extended to include
      008–021 **without reordering the existing entries**
- [ ] Backend test suite still passes (current baseline: 590)
- [ ] Frontend build still passes
- [ ] `GET /api/me`, `GET /api/me/permissions`, `GET /api/context/current`
      all return charter-shaped JSON against real DB state
- [ ] `GET /api/connectors`, `GET /api/connectors/health` return the
      charter shape with `procore` and `exxir` both present (Exxir as
      `configured` / not yet `connected`)
- [ ] `backend/app/services/connectors/` subpackage exists with base
      ABC + Procore + Exxir adapter skeletons
- [ ] No assistant/business logic is forced to read
      `connector_procore.*` or `connector_exxir.*` directly
- [ ] No existing phase-1–53 endpoint is broken

## 10. Reconciliation against the master checklist

Per the charter §"Reconciliation checklist against the master roadmap",
verified at the start of this work block:

1. **Still aligned to Phase 1 / Phase 4 / Phase 8-data / Phase 11?** Yes.
   This reconciliation doc does not change phase alignment — it only
   corrects the starting point.
2. **Schema split pattern preserved?** Yes. Every table in §3 above is
   assigned to either `rex` (canonical) or `connector_procore`/
   `connector_exxir` (staging). No cross-contamination.
3. **Any reintroduction of old rex-procore anti-patterns?** No.
   - No mixed source + product data: `rex.connector_mappings` is
     canonical metadata about source links, not raw staged data. Raw
     staged data will live in `connector_*` schemas only.
   - No duplicate role systems: the existing `rex.role_templates` is a
     **UI provisioning template**, not a competing canonical role
     registry. The new `rex.roles` is the single canonical source of
     truth for role identity. `role_templates` is re-framed as
     "preset configurations for newly-provisioned users" and
     documented in §3 above.
   - No Procore-shaped canon: the existing `rex.*` tables are already
     connector-agnostic (no `procore_id` column, no Procore-specific
     status enums). The charter's concern does not apply to the
     current shape.
4. **Were contract changes reflected in docs?** Yes — the only contract
   change in this doc is the `backend/app/routes/` path convention
   (not `backend/routers/`), and the migration number offset (+6 from
   charter originals). Both are documented here and will be updated in
   the session packet docs in the next commit.

## 11. Open questions deferred to Session 1 / Session 3 coordination

- **`backend/repositories/` vs `backend/app/repositories/` naming.**
  Session 1 chose the former (repo root), Session 2 (this doc) will use
  `backend/app/repositories/` to match `backend/app/routes/` +
  `backend/app/services/` already in place. Post-merge, one convention
  should win. Not blocking.
- **`backend/routers/` vs `backend/app/routes/` naming.** Same as above.
  Post-merge cleanup.
- **`backend/schemas/` vs per-module schema files.** Session 1 chose a
  top-level `backend/schemas/` package. The existing repo convention is
  to define Pydantic schemas inline in each router file (e.g.,
  `LoginRequest` + `LoginResponse` inside `backend/app/routes/auth.py`).
  Session 2 will follow the inline convention. Post-merge cleanup.
- **Frontend hook contract stability.** Session 3's
  `frontend/src/hooks/useMe.js`, `usePermissions.js`,
  `useCurrentContext.js` were written against the charter's JSON shapes
  using mock data. Session 2 must deliver the same shapes from the real
  backend. Any contract drift requires Session 3 notification.

---

## Appendix A — The `rex2_*` naming convention

The `rex2_*` prefix in the existing migration set is not an ordering
mechanism — it is a batch-identifier for the "rex2 canonical" planning
wave (phase 1–8 of the original roadmap). The `rex2_*` files are
explicitly inserted into `MIGRATION_ORDER` after `001_create_schema.sql`
and before the `00[2-5]_*` phase-batch migrations, and they do not
follow numeric ordering at all:

```python
MIGRATION_ORDER = [
    "001_create_schema.sql",
    "rex2_canonical_ddl.sql",
    "rex2_foundation_bootstrap.sql",
    "rex2_business_seed.sql",
    "002_field_parity_batch.sql",
    ...
]
```

Session 2 does not extend the `rex2_*` convention. New files use the
numeric `NNN_*` pattern because numeric slots 008+ are clean and the
ordering is explicit and greppable.
