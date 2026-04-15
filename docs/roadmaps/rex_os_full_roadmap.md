# Rex OS full roadmap

## 1. Locked program decisions

Rex OS will be multi-connector from day one. Procore is the first live connector, but Exxir is part of the target architecture immediately and the canonical model cannot be Procore-shaped.

Canonical application data lives in `rex`. Connector-specific ingestion lives outside `rex` in connector schemas. The working pattern is:

`connector_procore` and `connector_exxir` → `rex` canonical tables → `rex.v_*` read models → assistant, sidebar, dashboards, automations, writeback, and reporting.

The AI lives as a persistent sidebar across the app shell. Quick actions and automations are registry-driven. Roles start with the current six-role model and become fully data-driven so roles can be added, renamed, split, or granted custom capabilities later.

Low-risk actions can auto-pass-through. Medium- and high-risk actions require queueing, approval, audit, and optional reverse-sync.

## 2. Source-of-truth modules in rex-procore

The modules to lift are:

- `routes/assistant.py`
- `core/chat_dispatcher.py`
- `frontend/src/UnifiedAssistant.jsx`
- `command_parser.py`
- `routes/action_queue.py`
- `routes/writeback.py`
- `automations.py`

The migrations that define most of the reusable data patterns are:

- `migrations/015_chat_tables.sql`
- `migrations/048_action_quality_risk_closeout_meeting.sql`
- `migrations/050_intelligence_layer.sql`
- `migrations/051_final_frontier.sql`
- `migrations/057_all_spec_tables.sql`
- `migrations/088_rex_independent_schema.sql`
- `migrations/092_rex_schedules.sql`
- `migrations/101_budget_schedule_crosswalk.sql`

## 3. What gets fixed during the port

There are several structural problems in rex-procore that should not be carried forward as-is:

- Duplicate role systems: `dashboard_access_config_6roles.json` uses the six-role framework, but `main.py` and `UnifiedAssistant.jsx` still use legacy role keys like `VP_PM` and `General_Superintendent`.
- Duplicate conversation storage: `assistant_conversations` and `chat_conversations`.
- Duplicate writeback audit models: `procore_writeback_log` and `procore.writeback_log`.
- Duplicate quick actions: `C-8` and `C-28` both represent Submittal SLA; `C-15` and `C-60` both represent Monthly Owner Report.
- Mixed source and product data in the same `procore` schema.
- Direct `procore.*` assumptions inside prompt logic and SQL generation.

Rex OS should normalize all of these during the initial foundation phase.

## 4. Target architecture

### Backend structure

- `backend/routers/assistant.py`
- `backend/routers/catalog.py`
- `backend/routers/actions.py`
- `backend/routers/writeback.py`
- `backend/routers/automations.py`
- `backend/routers/connectors.py`
- `backend/routers/control_plane.py`
- `backend/routers/myday.py`
- `backend/services/ai/*`
- `backend/services/connectors/*`
- `backend/services/domain/*`
- `backend/services/writeback/*`
- `backend/services/automations/*`
- `backend/repositories/*`
- `backend/schemas/*`

### Canonical domains in `rex`

- identity and RBAC
- connectors and sync ops
- projects and directory
- project management
- schedule
- financials and commercial ops
- documents and field ops
- intelligence and predictions
- assistant and catalog
- writeback and approvals
- alerts, notifications, My Day
- training

### Read models

The assistant and dashboards should read from curated `rex.v_*` views, not from connector tables directly.

## 5. Migration plan for rex-os

> **BASELINE RECONCILIATION 2026-04-14.** The charter-original migration
> numbering below (002–024) was written against the assumption that the
> repo was a "very small shell". The current repo already has migration
> slots 001–005 filled with phase 1–53 work (`001_create_schema.sql`,
> `002_field_parity_batch.sql`, `003_phase21_p1_batch.sql`,
> `004_phase31_jobs_notifications.sql`, `005_phase38_phase39_p2_batch.sql`)
> plus four `rex2_*` canonical files. Session 1 claimed slots 006 + 007
> on `feat/ai-spine` for the AI spine. Session 2's revised slot plan
> starts at 008 and maps 1:1 to the charter numbering with a +6 offset.
> See `docs/roadmaps/baseline-reconciliation.md` §4 for the full
> mapping and `backend/app/migrate.py::MIGRATION_ORDER` for the
> concrete list.
>
> **The architectural intent of the migration plan below remains
> locked** — only the file numbering shifts.

The migration path should look like this (charter-original numbering
shown in parentheses; real repo slot in bold):

- `001_create_schema.sql` (already exists)
- **`008`** (charter 002) `008_rbac_roles_permissions.sql`
- **`009`** (charter 003) `009_user_roles_preferences.sql`
- **`010`** (charter 004) `010_project_assignment_bridges.sql`
- **`011`** (charter 005) `011_connector_registry.sql`
- **`012`** (charter 006) `012_connector_procore_stage.sql`
- **`013`** (charter 007) `013_connector_exxir_stage.sql`
- **`014`** (charter 008) `014_sync_runs_and_source_links.sql`
- **`015`** (charter 009) `015_canonical_core_additions.sql`
- **`016`** (charter 010) `016_canonical_pm_additions.sql`
- **`017`** (charter 011) `017_canonical_financial_additions.sql`
- **`018`** (charter 012) `018_canonical_schedule_additions.sql`
- **`019`** (charter 013) `019_canonical_docs_quality_additions.sql`
- (charter 014) `006_ai_chat_and_prompts.sql` ← Session 1 lane, already claimed
- (charter 015) `007_ai_action_catalog.sql` ← Session 1 lane, already claimed
- (charter 016) writeback/queue — future Session 1 wave
- (charter 017) automation registry — future lane
- (charter 018) alerts/myday — future lane
- (charter 019) intelligence layer — future lane
- (charter 020) rex_schedule — already covered by the existing canonical DDL
- (charter 021) budget_schedule_crosswalk — future lane
- (charter 022) training — future lane
- **`020`** (charter 023) `020_seed_roles_and_aliases.sql`
- **`021`** (charter 024) `021_canonical_read_views.sql`

## 6. Phase roadmap

### Phase 0 — Inventory, normalization, and contract freeze

Goals:
- Inventory all quick actions and all scheduler jobs from rex-procore.
- Normalize role keys and create a legacy alias map.
- Freeze the API contract for the assistant, catalogs, actions, connectors, and control plane.
- Freeze the schema split between connectors and canonical `rex`.

Exit:
- Contracts frozen.
- Duplicate models identified and replacement models approved.
- Branch boundaries for three coding sessions are locked.

### Phase 1 — Foundation schema and RBAC

Goals:
- Data-driven roles, permissions, capabilities, and project assignments.
- Users, sessions, preferences.
- Connector registry and sync metadata.
- Canonical project and organization entities.
- Seeding of the six default roles with legacy aliases.

Exit:
- Rex OS can authenticate users, resolve roles, and answer permission questions from DB rather than hardcoded files.

### Phase 2 — AI spine backend

Goals:
- Streaming assistant endpoint.
- Conversation persistence.
- Prompt registry.
- Follow-up suggestion engine.
- Action catalog endpoint.
- SQL planner and read-only SQL guard using curated views.

Exit:
- A user can chat, stream tokens, persist history, reload a conversation, and receive role-constrained responses.

### Phase 3 — Persistent sidebar shell

Goals:
- Replace the current placeholder `App.jsx` with an app shell.
- Mount a persistent assistant sidebar.
- Add conversation history, quick actions, command mode, and route/project context injection.
- Add an expanded workspace mode for long sessions.

Exit:
- AI is visible at all times and usable anywhere in the product.

### Phase 4 — Connectors and canonical read models

Goals:
- Build the Procore connector adapter first.
- Build the Exxir adapter contract at the same time.
- Stand up sync runs, cursors, webhook/event logging, and source links.
- Build canonical `rex` entities and curated `rex.v_*` views.
- Keep the assistant and quick actions off connector tables.

Exit:
- Data is flowing into `rex` and the assistant is grounded in canonical views.

### Phase 5 — Quick action registry import and Wave 1 execution

Goals:
- Seed all imported quick actions from the legacy catalog immediately.
- Give each one a stable slug, legacy alias, readiness state, risk tier, role visibility, and required connector coverage.
- Bring the first operational wave live.

Wave 1 should include:
- budget variance
- change event sweep
- RFI aging
- daily log summary
- submittal SLA
- critical path delays
- 2-week lookahead
- project team roster
- vendor compliance
- morning briefing
- closeout readiness
- documentation compliance
- inspection pass/fail
- schedule variance
- lookahead status
- My Day briefing

Exit:
- The assistant sidebar is useful for daily operational work, not just free-form chat.

### Phase 6 — Action execution, command mode, and approvals

Goals:
- Natural-language command parsing.
- Confirmation cards.
- Action queue.
- Writeback queue.
- Auto queue.
- Approval rules.
- Reverse-sync outbox.

Auto-pass-through at launch:
- internal task creation
- internal task status updates
- save meeting packets
- save drafts
- create internal alerts
- create internal decisions and notes

Approval required at launch:
- financial changes
- official Procore object mutation
- delete operations
- external communications
- official RFI responses
- punch close/reopen
- CE or PCO creation
- pay app and lien waiver actions
- schedule-affecting changes

Exit:
- Language can become safe actions with auditability.

### Phase 7 — Automation platform and job registry

Goals:
- Register the full scheduler/job catalog from rex-procore.
- Add job definitions, enablement flags, schedules, dependency metadata, manual triggers, job runs, failure history, and health views.
- Port existing job wrappers into the new job registry.

All current jobs should be represented in the registry, even if some are disabled until their dependencies are ready.

Exit:
- Automation exists as an observable platform, not hidden code in app startup.

### Phase 8 — My Day, alerts, notifications, and control plane

Goals:
- My Day home surface.
- alert center
- notification preferences
- digest history
- connector health
- sync health
- job health
- action readiness
- automation readiness
- role/capability inspection
- writeback audit inspection

Exit:
- The system is testable, inspectable, and operationally transparent.

### Phase 9 — Schedule intelligence, meeting engine, and communication suite

Goals:
- Enriched lookaheads
- schedule-vs-billing checks
- procurement readiness
- vendor performance scorecards
- daily log vs schedule verification
- punch-to-milestone risk
- meeting packet generation
- pending decisions tracking
- decision escalation
- sub communications
- weather impact forecasting
- photo intelligence

Exit:
- Cross-wired operational intelligence is live, not just reporting.

### Phase 10 — Portfolio, risk, quality, closeout, performance, and training

Goals:
- portfolio snapshots
- portfolio cash flow
- budget roll-ups
- vendor rankings
- trend analysis
- risk prediction and active risk dashboards
- quality scans
- closeout checklists
- scorecards
- milestone bonus logic
- evidence packs
- training center
- role-based learning paths
- voice entry and mobile field surfaces as later extensions

Exit:
- Rex OS supports both field execution and executive oversight.

### Phase 11 — Hardening

Goals:
- tests
- evals
- prompt versioning
- connector replayability
- retries and backoff
- token and cost tracking
- performance budgets
- security review
- migration idempotency
- backup and recovery procedures

Exit:
- The AI layer is production infrastructure.

## 7. Quick action execution waves

### Registry import
All 80 current quick actions from `UnifiedAssistant.jsx` get imported on day one as catalog entries.

### Normalization
- `C-8` + `C-28` collapse to one `submittal_sla` slug with mode parameters if needed.
- `C-15` + `C-60` collapse to one `monthly_owner_report` slug.
- legacy `C-*` IDs remain as aliases only.

### Live waves
- Wave 1: operational core
- Wave 2: financial and schedule-intelligence crosswires
- Wave 3: meeting engine, queue review, command mode, and communications
- Wave 4: portfolio, risk, weather, photo intelligence, and training/performance finishers

## 8. Automation execution waves

All 40 currently scheduled jobs in `main.py` should be registered immediately.

Wave order:
- Wave A: sync, refresh, and alert foundation
- Wave B: briefings, digests, scorecards, and portfolio
- Wave C: delay, compliance, permit, delivery, warranty, closeout
- Wave D: schedule-commitment matching, procurement gaps, billing anomalies, weather, sub status emails, photo intelligence

## 9. Parallel lane plan

### Lane A
AI spine, catalog, prompt registry, assistant router, quick action dispatcher.

### Lane B
Connector registry, Procore adapter, Exxir adapter contract, canonical tables, views, sync ops.

### Lane C
App shell, sidebar UI, control plane UI, queue review UI, My Day surface.

Merge gates:
- Gate 1: API contract freeze
- Gate 2: migration freeze
- Gate 3: action catalog freeze
- Gate 4: automation registry freeze

## 10. Immediate start order

### Session 1
Create:
- assistant router
- AI service package
- conversation tables
- action catalog tables
- `/api/assistant/chat`
- `/api/assistant/catalog`
- `/api/assistant/conversations`

### Session 2
Create:
- RBAC migrations
- connector registry migrations
- canonical core migrations
- repository package
- Procore adapter interface
- Exxir adapter interface
- `rex.v_*` starter views

### Session 3
Create:
- app shell
- sidebar assistant
- conversation sidebar
- quick action launcher
- mocked catalog client
- mocked streaming client
- route context hook

## 11. Repo-derived inventories

Quick actions inventory:
- `rex_os_quick_actions_inventory.csv`

Automation job inventory:
- `rex_os_automation_inventory.csv`
