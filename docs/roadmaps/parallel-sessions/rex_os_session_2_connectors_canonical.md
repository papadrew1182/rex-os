# Rex OS parallel session 2 — connectors, canonical data model, RBAC, and read models

## How to use this document

This file is the **full context packet** for one parallel coding/chat session. Open it in its own chat and treat it as the authoritative charter for the data and connector lane.

This session must reconcile against these master artifacts at the start and end of each work block:

- `rex_os_full_roadmap.md`
- `rex_os_quick_actions_inventory.csv`
- `rex_os_automation_inventory.csv`

This lane maps to the master roadmap primarily across:
- Phase 0 — inventory, normalization, and contract freeze
- Phase 1 — foundation schema and RBAC
- Phase 4 — connectors and canonical read models
- Phase 8 — My Day, alerts, notifications, and control plane (data layer only)
- Phase 11 — hardening for sync, data integrity, and migration quality

## Program context you should assume

> **BASELINE RECONCILIATION 2026-04-14.** The "very small shell repo"
> description below was from an earlier planning snapshot and does not
> match the current repo state. `rex-os` is now a production-deployed
> codebase at `main @ 3148f0c` with 8 migrations, 65 routers, 66 rex.*
> tables, 590 passing tests, and a live Vercel frontend serving 32 page
> components. See `docs/roadmaps/baseline-reconciliation.md` for the
> authoritative charter → real-state mapping. Session 2 execution
> originally used migration slots 008–021 (not 002–013); after Session 1
> (AI Spine) landed on `main` and consumed slot 008
> (`008_ai_action_catalog_seed.sql`), Session 2 was bumped one slot
> forward to 009–022. Session 2 follows the repo-native
> `backend/app/routes/` + `backend/app/services/` path conventions.
> The architectural intent locked below (multi-connector, canonical
> rex, v_* read models, data-driven RBAC) remains unchanged.

`rex-os` is currently a very small shell repo with:
- `backend/db.py`
- `backend/main.py`
- an empty `backend/routers/`
- an empty `backend/models/`
- a placeholder React frontend
- one migration: `001_create_schema.sql`

`rex-procore` is the source system we are lifting from. This lane should use these sources heavily:

- `migrations/048_action_quality_risk_closeout_meeting.sql`
- `migrations/050_intelligence_layer.sql`
- `migrations/051_final_frontier.sql`
- `migrations/057_all_spec_tables.sql`
- `migrations/088_rex_independent_schema.sql`
- `migrations/092_rex_schedules.sql`
- `migrations/101_budget_schedule_crosswalk.sql`
- any route/service code in `rex-procore` that reveals current table usage, join patterns, or business logic assumptions

Architectural decisions already locked:
- `rex-os` is **multi-connector from day one**
- connector-specific ingestion does **not** live in `rex`
- canonical product data lives in `rex`
- the assistant, dashboards, automations, and writeback should read from curated `rex.v_*` views
- Procore is the first live connector
- Exxir must have a first-class adapter contract immediately
- roles are data-driven and extensible
- current six roles are the seed set, not a hard ceiling

## Canonical role model

These are the canonical role keys and must be seeded into the database:

- `VP`
- `PM`
- `GENERAL_SUPER`
- `LEAD_SUPER`
- `ASSISTANT_SUPER`
- `ACCOUNTANT`

Support legacy aliases for compatibility with imported logic from `rex-procore`, but aliases are not canonical roles.

## Lane mission

Build the data foundation that lets `rex-os` become a true multi-connector operating system rather than a Procore-shaped clone.

This lane owns:
- RBAC tables and permission model
- user-role-project assignment model
- connector registry
- connector accounts / connection state
- sync runs, sync cursors, webhook/event logs, and source-link model
- staging schemas for Procore and Exxir
- canonical `rex` entities
- curated `rex.v_*` read models
- identity/context endpoints consumed by the assistant and frontend lanes
- migration sequencing from `002` through `013`, plus seed and control-plane support where relevant

This lane does **not** own:
- assistant chat persistence
- prompt registry
- action catalog API implementation
- frontend app shell or sidebar UX
- queue review UI
- full automation implementation logic

## Branch and ownership boundary

Recommended branch name:

`feat/canonical-connectors`

Do not take ownership of:
- assistant router internals
- frontend assistant components
- conversation storage
- SSE streaming
- full queue UI

You can stub or expose data needed by those lanes, but avoid crossing ownership boundaries unless absolutely necessary.

## Canonical schema split

This is non-negotiable.

### Connector schemas
Use source-specific schemas for raw/staged connector data:

- `connector_procore`
- `connector_exxir`

These schemas may contain:
- raw API snapshots
- lightly normalized staging tables
- source-native identifiers
- sync metadata specific to that connector

### Product schema
Use `rex` for canonical product data and operational metadata.

`rex` contains:
- identity and RBAC
- projects and organizations
- canonical project-management data
- canonical financial data
- canonical scheduling data
- canonical documents/quality data
- source links and sync references
- read models
- later: assistant/chat, action queues, automations, My Day, alerts, training

### Read-model contract
All assistant and dashboard data should ultimately come from curated read views in `rex.v_*`, not from connector tables directly.

## Recommended migration ownership

This lane should own or co-own the following migrations:

- `002_rbac_roles_permissions.sql`
- `003_users_sessions_preferences.sql`
- `004_projects_assignments_orgs.sql`
- `005_connector_registry.sql`
- `006_connector_procore_stage.sql`
- `007_connector_exxir_stage.sql`
- `008_source_links_sync_runs.sql`
- `009_canonical_core_entities.sql`
- `010_canonical_project_mgmt.sql`
- `011_canonical_financials.sql`
- `012_canonical_schedule.sql`
- `013_canonical_documents_quality.sql`
- `023_seed_roles_actions_automations_aliases.sql` (co-own the role and alias parts)
- `024_control_plane_views.sql` (co-own the data/read-view pieces)

## Core database objects this lane should create

### RBAC and identity
Recommended tables:

- `rex.roles`
- `rex.role_aliases`
- `rex.permissions`
- `rex.role_permissions`
- `rex.users`
- `rex.user_roles`
- `rex.user_preferences`
- `rex.user_project_assignments`

### Organizations and projects
Recommended tables:

- `rex.organizations`
- `rex.projects`
- `rex.project_members`
- `rex.company_contacts`
- `rex.user_connector_accounts` or `rex.connector_accounts`

### Connector registry and sync ops
Recommended tables:

- `rex.connectors`
- `rex.connector_accounts`
- `rex.sync_runs`
- `rex.sync_cursors`
- `rex.connector_event_log`
- `rex.source_links`

### Canonical core entities
Recommended tables:

- `rex.project_sources`
- `rex.project_locations`
- `rex.cost_codes`
- `rex.trade_partners`
- `rex.vendors`
- `rex.project_calendars`

### Project management domain
Recommended tables:

- `rex.rfis`
- `rex.submittals`
- `rex.tasks`
- `rex.meetings`
- `rex.meeting_decisions`
- `rex.pending_decisions`
- `rex.daily_logs`
- `rex.inspections`
- `rex.observations`
- `rex.punch_items`

### Financial and commercial domain
Recommended tables:

- `rex.budgets`
- `rex.commitments`
- `rex.change_events`
- `rex.pcos`
- `rex.pay_apps`
- `rex.lien_waivers`
- `rex.procurement_items`
- `rex.billing_periods`

### Schedule domain
Recommended tables:

- `rex.schedules`
- `rex.schedule_tasks`
- `rex.schedule_dependencies`
- `rex.schedule_baselines`
- `rex.schedule_milestones`
- `rex.delay_events`

### Documents and field ops
Recommended tables:

- `rex.documents`
- `rex.drawings`
- `rex.spec_sections`
- `rex.photos`
- `rex.closeout_items`
- `rex.quality_findings`
- `rex.weather_observations`

Do not treat this as a requirement to fully implement every business column on the first pass. The point is to establish the canonical structure and enough columns for assistant, quick actions, and automations to build on.

## Connector adapter contract

Define a clean adapter interface in `backend/services/connectors/`.

Suggested package structure:

```text
backend/
  services/
    connectors/
      base.py
      registry.py
      sync_service.py
      procore/
        adapter.py
        mapper.py
        client.py
      exxir/
        adapter.py
        mapper.py
        client.py
```

### Required interface concepts

The base connector interface should provide methods along these lines:

- `health_check()`
- `list_projects()`
- `list_users()`
- `fetch_project_directory(project_external_id)`
- `fetch_rfis(project_external_id, cursor=None)`
- `fetch_submittals(project_external_id, cursor=None)`
- `fetch_daily_logs(project_external_id, cursor=None)`
- `fetch_budget(project_external_id, cursor=None)`
- `fetch_commitments(project_external_id, cursor=None)`
- `fetch_change_events(project_external_id, cursor=None)`
- `fetch_schedule(project_external_id, cursor=None)`
- `fetch_documents(project_external_id, cursor=None)`

Do **not** force Exxir to match Procore field-for-field at the connector layer. Normalize into `rex` after staging.

## Source-link model

Every canonical entity that originates in a connector should be traceable back to its source.

Recommended pattern:
- canonical row lives in `rex`
- connector-native ID, connector key, and origin metadata live in `rex.source_links`

Recommended columns in `rex.source_links`:
- `id uuid primary key`
- `connector_key text not null`
- `source_table text not null`
- `source_id text not null`
- `canonical_table text not null`
- `canonical_id uuid not null`
- `project_id uuid null`
- `metadata jsonb not null default '{}'::jsonb`
- unique index on `(connector_key, source_table, source_id)`

## Curated read models this lane must expose

These are the initial views that the assistant and dashboard surfaces should target:

- `rex.v_project_mgmt`
- `rex.v_financials`
- `rex.v_schedule`
- `rex.v_directory`
- `rex.v_portfolio`
- `rex.v_risk`
- `rex.v_myday`

### Purpose of each view

`rex.v_project_mgmt`
- RFIs
- submittals
- tasks
- punch items
- pending decisions
- meeting action context

`rex.v_financials`
- budgets
- commitments
- change events
- PCOs
- direct cost
- invoice and pay-app state
- waiver status

`rex.v_schedule`
- tasks
- dependencies
- milestones
- variance
- critical path markers
- lookahead slices
- delay flags

`rex.v_directory`
- team roster
- role assignments
- vendor compliance
- insurance status
- communication targets

`rex.v_portfolio`
- portfolio rollups
- cash flow
- budget aggregates
- cross-project trends
- executive metrics

`rex.v_risk`
- active risk rows
- risk scores
- predicted exposure
- punch-to-milestone issues
- documentation debt flags

`rex.v_myday`
- personalized action summary for the current user
- alerts
- due items
- project priorities
- meeting/decision follow-ups

## Identity and context endpoints owned by this lane

These contracts are important because the assistant lane and frontend lane will build against them.

### `GET /api/me`

Recommended response shape:

```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "Alex Builder",
    "primary_role_key": "PM",
    "role_keys": ["PM"],
    "legacy_role_aliases": ["VP_PM"],
    "project_ids": ["uuid-1", "uuid-2"],
    "feature_flags": {
      "assistant_sidebar": true
    }
  }
}
```

### `GET /api/me/permissions`

Recommended response shape:

```json
{
  "permissions": [
    "assistant.chat",
    "assistant.catalog.read",
    "financials.view",
    "schedule.view",
    "myday.view"
  ]
}
```

### `GET /api/context/current`

Recommended response shape:

```json
{
  "project": {
    "id": "uuid",
    "name": "Tower 3",
    "status": "active"
  },
  "route": {
    "name": "project_dashboard",
    "path": "/projects/tower-3"
  },
  "page_context": {
    "surface": "dashboard",
    "entity_type": "project",
    "entity_id": "uuid",
    "filters": {}
  },
  "assistant_defaults": {
    "suggested_action_slugs": ["budget_variance", "morning_briefing"]
  }
}
```

### `GET /api/connectors`

Recommended response shape:

```json
{
  "items": [
    {
      "connector_key": "procore",
      "label": "Procore",
      "status": "connected",
      "last_sync_at": "2026-04-14T12:00:00Z"
    },
    {
      "connector_key": "exxir",
      "label": "Exxir",
      "status": "configured",
      "last_sync_at": null
    }
  ]
}
```

### `GET /api/connectors/health`

Recommended response shape:

```json
{
  "items": [
    {
      "connector_key": "procore",
      "healthy": true,
      "last_success_at": "2026-04-14T12:00:00Z",
      "last_error_at": null,
      "last_error_message": null
    }
  ]
}
```

## Role and alias strategy

Seed the canonical roles first, then alias legacy names to those roles.

Examples of legacy aliases to support:
- `VP_PM` → `VP` or `PM` depending on actual intent; document the chosen mapping
- `General_Superintendent` → `GENERAL_SUPER`
- `Lead_Superintendent` → `LEAD_SUPER`
- `Asst_Superintendent` → `ASSISTANT_SUPER`

Do not silently preserve ambiguous aliases. If a legacy alias could map to more than one canonical role, explicitly document the chosen behavior.

## Implementation sequence

### Work packet A — migration scaffold
- create the migration files from `002` through `013`
- establish naming patterns
- avoid future collisions with lane A and lane C
- document ownership per migration

### Work packet B — RBAC and identity
- create role tables
- create permission tables
- create user-role assignment tables
- create user preferences
- seed the six canonical roles
- seed alias mappings

### Work packet C — connector registry
- create connector registry tables
- create connector account tables
- create sync-run and cursor tracking
- create connector event logging

### Work packet D — stage schemas
- create `connector_procore`
- create `connector_exxir`
- define minimum staged tables required for the first live actions
- keep source-native IDs intact

### Work packet E — canonical entities
- create core project and organization tables
- create canonical PM, financial, schedule, and field/document tables
- wire `source_links`

### Work packet F — views
- create `rex.v_project_mgmt`
- create `rex.v_financials`
- create `rex.v_schedule`
- create `rex.v_directory`
- create starter versions of `rex.v_portfolio`, `rex.v_risk`, and `rex.v_myday`

### Work packet G — endpoints
- implement `GET /api/me`
- implement `GET /api/me/permissions`
- implement `GET /api/context/current`
- implement `GET /api/connectors`
- implement `GET /api/connectors/health`

### Work packet H — repository and adapter scaffolding
- repository package under `backend/repositories/`
- connector adapter base classes
- Procore adapter skeleton
- Exxir adapter contract skeleton

### Work packet I — tests
At minimum:
- migration sanity tests
- role alias mapping tests
- source-link uniqueness tests
- connector registry tests
- view smoke tests
- endpoint contract tests

## What “multi-connector from day one” means in practice

It does **not** mean every Exxir business flow must be fully live on day one.

It **does** mean:
- the schemas support more than one connector
- the canonical model is not Procore-shaped
- source links are connector-aware
- adapters are connector-scoped
- read models do not depend on a single source
- the assistant does not assume Procore table names

## Non-goals for this session

Do not spend time on:
- frontend interaction polish
- assistant prompt engineering
- SSE streaming
- queue review UI
- full writeback mutations
- late-phase training or voice features

## Cross-lane dependencies

### Session 1 depends on this lane for:
- identity and roles
- project membership
- current context
- canonical `rex.v_*` read models
- connector availability metadata

To unblock Session 1 quickly:
- get `GET /api/me`, `GET /api/me/permissions`, and `GET /api/context/current` stable early
- get starter `rex.v_financials`, `rex.v_schedule`, and `rex.v_project_mgmt` views live early

### Session 3 depends on this lane for:
- current user info
- permissions
- current project context
- connector health
- readiness/status metadata for control-plane surfaces

To unblock Session 3 quickly:
- stabilize API response shapes before finishing all migrations
- allow mock-backed implementations first if needed

## Merge gates for this lane

### Gate A — schema split freeze
- connector schemas and canonical schema responsibilities are explicit
- no new product data is placed in connector schemas
- no connector-specific assumptions leak into `rex` identity modeling

### Gate B — RBAC freeze
- canonical roles seeded
- alias strategy documented
- permissions resolvable from DB

### Gate C — view freeze
- initial `rex.v_*` views exist
- Session 1 can target them safely
- Session 3 can build context displays and stubs against them

## Definition of done for the first pass

This lane is considered done for the first merge if all of these are true:

- migrations `002` through at least `013` exist in workable form
- roles, permissions, users, and assignments are DB-backed
- connector registry exists
- `connector_procore` and `connector_exxir` schemas exist
- canonical `rex` core entities exist
- starter `rex.v_*` views exist
- `GET /api/me`, `GET /api/me/permissions`, `GET /api/context/current`, `GET /api/connectors`, and `GET /api/connectors/health` work
- no assistant/business logic is forced to read connector tables directly

## Reconciliation checklist against the master roadmap

At the start and end of each work block, explicitly verify:

1. Is the implementation still aligned to:
   - Phase 1
   - Phase 4
   - Phase 8 data-layer prep
   - Phase 11 hardening

2. Has any schema choice violated the locked pattern?
   - connector schemas for source-native data
   - `rex` for canonical product data
   - `rex.v_*` for read models

3. Did any code reintroduce old `rex-procore` structural issues?
   - mixed source and product data
   - duplicate role systems
   - Procore-shaped canon

4. If a contract changed, was the change reflected in:
   - this session doc
   - the master roadmap
   - Session 1 and Session 3 docs

## Suggested end-of-session status note

Use this template in the parallel chat when closing a work block:

```md
### Session 2 status
Completed:
- ...

In progress:
- ...

Blocked by Session 1:
- ...

Blocked by Session 3:
- ...

Contracts changed:
- ...

Roadmap reconciliation:
- Still aligned to Phase 1 / 4 / 8-data / 11
- Drift introduced: yes/no
- If yes, updated docs: yes/no
```
