# Rex OS parallel session 1 — AI spine, catalog, and assistant backend

## How to use this document

This file is the **full context packet** for one parallel coding/chat session. It is meant to be opened in its own chat and treated as the lane charter for that session.

This session must reconcile against these master artifacts at the start and end of each work block:

- `rex_os_full_roadmap.md`
- `rex_os_quick_actions_inventory.csv`
- `rex_os_automation_inventory.csv`

This lane maps to the master roadmap primarily across:
- Phase 0 — inventory, normalization, and contract freeze
- Phase 2 — AI spine backend
- Phase 5 — quick action registry import and Wave 1 execution
- Phase 6 — action execution, command mode, and approvals (backend prep only in this lane)
- Phase 11 — hardening for assistant APIs, prompts, and evals

## Program context you should assume

`rex-os` is currently a minimal shell. It has:
- a very small FastAPI backend
- a minimal Vite/React frontend
- one schema bootstrap migration
- no actual AI UX
- no implemented AI architecture in the repo

`rex-procore` is the source system we are lifting from. The primary source-of-truth modules for this lane are:

- `routes/assistant.py`
- `core/chat_dispatcher.py`
- `command_parser.py` (only for command-mode backend prep, not the full action execution ownership)
- `frontend/src/UnifiedAssistant.jsx` (to understand the action catalog shape and client expectations)
- `migrations/015_chat_tables.sql`
- `migrations/048_action_quality_risk_closeout_meeting.sql`
- `migrations/050_intelligence_layer.sql`
- `migrations/051_final_frontier.sql`

Architectural decisions already locked:
- `rex-os` is **multi-connector from day one**
- connector-specific ingestion lives outside `rex` in connector schemas
- canonical product data lives in `rex`
- AI is a **persistent sidebar** across the app shell
- quick actions and automations are **registry-driven**
- roles start with the current six-role model, but become **data-driven**
- low-risk actions can auto-pass-through later; medium/high-risk actions need queueing and approval
- the assistant must read from curated `rex.v_*` views, **not** directly from connector tables

## Canonical role model

Use these as the canonical role keys:

- `VP`
- `PM`
- `GENERAL_SUPER`
- `LEAD_SUPER`
- `ASSISTANT_SUPER`
- `ACCOUNTANT`

Legacy aliases from `rex-procore` are aliases only. Do not create a new duplicate role system in this lane.

## Lane mission

Build the assistant backbone that makes the persistent sidebar real.

This lane owns:
- assistant router and service architecture
- streaming chat endpoint
- persistent conversations
- prompt registry
- quick action catalog API
- follow-up suggestions
- role-constrained assistant context
- safe free-form query orchestration
- assistant-facing contracts used by the frontend lane
- action-catalog normalization from legacy `C-*` IDs into stable slugs

This lane does **not** own:
- connector staging schemas
- canonical business entities
- sync orchestration
- frontend shell/layout
- queue review UI
- full writeback execution plumbing
- full automation platform

## Branch and ownership boundary

Recommended branch name:

`feat/ai-spine`

Do not take ownership of:
- migrations `002` through `013`
- connector adapters
- app shell layout
- route-level control plane UI work

You may define interface requirements for those areas, but do not implement them here unless it is a small mock or stub needed to keep the lane moving.

## Source artifacts to inspect in rex-procore

Read these before implementing:

1. `routes/assistant.py`
   - understand the current streaming pattern
   - identify the parts that are Procore-bound and must be decoupled
   - extract conversation behavior, follow-ups, route patterns, and SQL/planner flow

2. `core/chat_dispatcher.py`
   - inventory quick-action categories and dispatcher semantics
   - capture how action IDs, user roles, and parameter requests work today

3. `frontend/src/UnifiedAssistant.jsx`
   - understand current action catalog usage, param shapes, command mode expectations, and UX event flow
   - use it as behavioral reference, not as the permanent architecture

4. `command_parser.py`
   - capture parsing strategy and normalization patterns
   - do **not** take over execution queues in this lane

5. `migrations/015_chat_tables.sql`
   - use for chat persistence patterns
   - normalize away any duplicate conversation systems

## Structural fixes this lane must enforce

Do not port these problems from `rex-procore`:

- duplicate conversation storage (`assistant_conversations` vs `chat_conversations`)
- direct `procore.*` assumptions inside assistant logic
- frontend-hardcoded action visibility as the source of truth
- action IDs that only make sense as legacy `C-*` labels
- role checks based on legacy keys like `VP_PM` or `General_Superintendent`

## Deliverables

By the end of the first complete pass, this lane should deliver:

1. Assistant router package in `backend/routers/assistant.py`
2. AI service package in `backend/services/ai/`
3. Assistant/chat schemas in `backend/schemas/`
4. Conversation persistence tables
5. Prompt registry tables
6. Quick action catalog tables
7. Streaming assistant endpoint
8. Conversation CRUD endpoints
9. Catalog endpoint
10. Role-aware context builder
11. Follow-up suggestion generation
12. Safe free-form query orchestration against curated views only
13. Backend tests for the assistant contract

## Recommended backend package structure

Target structure for this lane:

```text
backend/
  routers/
    assistant.py
    catalog.py            # optional if catalog is split from assistant.py
  services/
    ai/
      __init__.py
      model_client.py
      dispatcher.py
      prompt_registry.py
      followups.py
      context_builder.py
      sql_planner.py
      sql_guard.py
      catalog_service.py
      chat_service.py
  repositories/
    chat_repository.py
    prompt_repository.py
    catalog_repository.py
  schemas/
    assistant.py
    catalog.py
    chat.py
```

## Database objects this lane should own

These should live in `rex`, not connector schemas.

### 1. `rex.chat_conversations`

Recommended columns:

- `id uuid primary key`
- `user_id uuid not null`
- `title text not null default 'New conversation'`
- `project_id uuid null`
- `active_action_slug text null`
- `page_context jsonb not null default '{}'::jsonb`
- `conversation_metadata jsonb not null default '{}'::jsonb`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`
- `last_message_at timestamptz not null default now()`
- `archived_at timestamptz null`

### 2. `rex.chat_messages`

Recommended columns:

- `id uuid primary key`
- `conversation_id uuid not null references rex.chat_conversations(id)`
- `sender_type text not null`  
  Allowed values: `user`, `assistant`, `system`, `tool`
- `content text not null`
- `content_format text not null default 'markdown'`
- `structured_payload jsonb not null default '{}'::jsonb`
- `citations jsonb not null default '[]'::jsonb`
- `model_key text null`
- `prompt_key text null`
- `token_usage jsonb not null default '{}'::jsonb`
- `created_at timestamptz not null default now()`

### 3. `rex.ai_prompt_registry`

Recommended columns:

- `prompt_key text not null`
- `version integer not null`
- `prompt_type text not null`
- `content text not null`
- `is_active boolean not null default false`
- `metadata jsonb not null default '{}'::jsonb`
- `created_at timestamptz not null default now()`
- primary key: `(prompt_key, version)`

### 4. `rex.ai_action_catalog`

Recommended columns:

- `slug text primary key`
- `legacy_aliases text[] not null default '{}'`
- `label text not null`
- `category text not null`
- `description text not null`
- `params_schema jsonb not null default '[]'::jsonb`
- `risk_tier text not null`
- `readiness_state text not null`
- `required_connectors text[] not null default '{}'`
- `role_visibility text[] not null default '{}'`
- `handler_key text null`
- `enabled boolean not null default true`
- `metadata jsonb not null default '{}'::jsonb`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

### 5. Optional support tables if needed immediately

- `rex.ai_action_aliases`
- `rex.ai_conversation_artifacts`
- `rex.ai_eval_runs`

Only add these if they are necessary for the first implementation pass.

## Quick action normalization rules

Import all 80 legacy quick actions into the catalog, but normalize the identity model.

### Stable identity
Use a stable slug as the canonical identity. Examples:

- `budget_variance`
- `change_event_sweep`
- `rfi_aging`
- `daily_log_summary`
- `submittal_sla`
- `critical_path_delays`
- `lookahead_2week`
- `project_team_roster`
- `vendor_compliance`
- `morning_briefing`
- `monthly_owner_report`
- `scorecard_preview`

### Legacy aliases
Preserve the original `C-*` IDs in `legacy_aliases`, but never let those become the primary key.

### Required dedupes
Normalize these duplicates:

- `C-8` and `C-28` → `submittal_sla`
- `C-15` and `C-60` → `monthly_owner_report`

## Assistant API contract owned by this lane

These contracts are intentionally explicit so the frontend lane and connector lane can build around them.

### `GET /api/assistant/catalog`

Purpose:
Return the full assistant action catalog with readiness, visibility, parameter schema, and connector requirements.

Recommended response shape:

```json
{
  "version": "v1",
  "categories": [
    {"key": "FINANCIALS", "label": "Financials"},
    {"key": "SCHEDULING", "label": "Scheduling"}
  ],
  "actions": [
    {
      "slug": "budget_variance",
      "legacy_aliases": ["C-1"],
      "label": "Budget Variance",
      "category": "FINANCIALS",
      "description": "Budget vs projected cost by cost code",
      "params_schema": [
        {"name": "PROJECT_ID", "type": "project", "label": "Project", "required": true}
      ],
      "risk_tier": "read_only",
      "readiness_state": "live",
      "required_connectors": ["procore"],
      "role_visibility": ["VP", "PM", "ACCOUNTANT"],
      "enabled": true,
      "can_run": true
    }
  ]
}
```

### `GET /api/assistant/conversations`

Purpose:
Return conversation history for the current user.

Recommended response shape:

```json
{
  "items": [
    {
      "id": "uuid",
      "title": "Budget Variance for Tower 3",
      "project_id": "uuid",
      "active_action_slug": "budget_variance",
      "last_message_preview": "Current projection is over budget...",
      "last_message_at": "2026-04-14T17:22:00Z",
      "updated_at": "2026-04-14T17:22:00Z"
    }
  ]
}
```

### `GET /api/assistant/conversations/{conversation_id}`

Purpose:
Load one conversation with all messages.

Recommended response shape:

```json
{
  "conversation": {
    "id": "uuid",
    "title": "Budget Variance for Tower 3",
    "project_id": "uuid",
    "active_action_slug": "budget_variance",
    "page_context": {"route": "/projects/tower-3"}
  },
  "messages": [
    {
      "id": "uuid",
      "sender_type": "user",
      "content": "Show me budget variance for Tower 3",
      "created_at": "2026-04-14T17:20:00Z"
    },
    {
      "id": "uuid",
      "sender_type": "assistant",
      "content": "Current projected variance is ...",
      "structured_payload": {
        "followups": ["Show top 5 cost codes", "Compare against last month"]
      },
      "created_at": "2026-04-14T17:20:03Z"
    }
  ]
}
```

### `POST /api/assistant/chat`

Purpose:
Stream a response for a new or existing conversation.

Recommended request shape:

```json
{
  "conversation_id": null,
  "message": "Show me budget variance for Tower 3",
  "project_id": "uuid-or-null",
  "active_action_slug": "budget_variance",
  "mode": "chat",
  "params": {"PROJECT_ID": "uuid"},
  "page_context": {
    "route": "/projects/tower-3",
    "surface": "assistant_sidebar",
    "entity_type": "project",
    "entity_id": "uuid"
  },
  "client_context": {
    "selected_project_id": "uuid",
    "route_name": "project_dashboard"
  },
  "stream": true
}
```

### Streaming response contract

Use Server-Sent Events. Recommended event types:

- `conversation.created`
- `message.started`
- `message.delta`
- `message.completed`
- `followups.generated`
- `action.suggestions`
- `error`

Example stream event payloads:

```json
{"type":"conversation.created","conversation_id":"uuid"}
{"type":"message.delta","delta":"Current projected variance is "}
{"type":"message.delta","delta":"$182,000 over budget"}
{"type":"followups.generated","items":["Show top 5 drivers","Draft owner narrative"]}
{"type":"message.completed","message_id":"uuid"}
```

### `DELETE /api/assistant/conversations/{conversation_id}`

Purpose:
Soft-delete or archive a conversation.

Recommended behavior:
Set `archived_at`, do not hard-delete messages in the first pass.

## Support contracts consumed from other lanes

This lane does **not** own these long-term, but should build against them.

### `GET /api/me`
Owned by Session 2. Use this shape:

```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "Alex Builder",
    "primary_role_key": "PM",
    "role_keys": ["PM"],
    "legacy_role_aliases": ["VP_PM"],
    "project_ids": ["uuid-1", "uuid-2"]
  }
}
```

### `GET /api/me/permissions`
Owned by Session 2. Use this shape:

```json
{
  "permissions": [
    "assistant.chat",
    "assistant.catalog.read",
    "financials.view",
    "schedule.view"
  ]
}
```

### `GET /api/context/current`
Owned by Session 2, consumed heavily by Session 3 and this lane. Use this shape:

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

## Safe free-form query requirements

The assistant may support broad analytical questions, but the planner must only target curated read-only views.

Hard rules:
- no writes
- no connector-table direct reads
- no arbitrary table access outside the allowlist
- deny DDL and DML
- deny multiple statements
- deny comments that may hide injections
- deny cross-schema reads outside allowed `rex.v_*` views

Recommended initial allowlist:
- `rex.v_project_mgmt`
- `rex.v_financials`
- `rex.v_schedule`
- `rex.v_directory`
- `rex.v_portfolio`
- `rex.v_risk`
- `rex.v_myday`

## Implementation sequence

### Work packet A — scaffold the AI package
- create `backend/services/ai/`
- create `backend/schemas/assistant.py`
- create `backend/repositories/chat_repository.py`
- add provider abstraction in `model_client.py`
- default to Anthropic-first behind the abstraction
- do not hardwire the app to one vendor

### Work packet B — add migrations
Create or contribute to:
- `014_ai_chat_prompt_registry.sql`
- `015_ai_action_catalog.sql`

Include:
- `chat_conversations`
- `chat_messages`
- `ai_prompt_registry`
- `ai_action_catalog`

### Work packet C — catalog import
- import the 80 legacy actions from the inventory
- generate slug mapping
- encode legacy aliases
- assign readiness states
- assign risk tiers
- assign role visibility using canonical role keys
- expose via `GET /api/assistant/catalog`

### Work packet D — conversations
- create conversation summary queries
- create message history queries
- create new conversation behavior
- generate titles lazily
- support soft delete/archive

### Work packet E — streaming chat
- implement `POST /api/assistant/chat`
- support both new and existing conversations
- persist the user message before model execution
- stream assistant deltas
- persist the final assistant response
- generate follow-up suggestions

### Work packet F — role and page context
- inject current user role(s)
- inject current project context when present
- inject current page context
- do not encode role policy in frontend assumptions

### Work packet G — planner and guard
- implement a read-only planner/guard path
- allow only curated `rex.v_*` views
- return structured errors when a query is blocked

### Work packet H — tests
At minimum:
- catalog endpoint tests
- conversation create/load tests
- streaming endpoint contract tests
- SQL guard deny-list tests
- role-constrained context builder tests

## Readiness-state vocabulary

Use a consistent vocabulary in this lane so the UI and control plane can rely on it:

- `live`
- `alpha`
- `adapter_pending`
- `writeback_pending`
- `blocked`
- `disabled`

## Risk-tier vocabulary

Use a consistent vocabulary:

- `read_only`
- `internal_write_low`
- `connector_write_medium`
- `connector_write_high`

## Non-goals for this session

Do not spend time on:
- a full frontend redesign
- connector ETL or sync scheduling
- large automation implementations
- production-grade writeback mutation handlers
- mobile/voice interfaces
- advanced export formatting

## Cross-lane dependencies

### Dependency on Session 2
Need:
- user identity and roles
- project membership
- current project context
- canonical read views
- connector availability metadata

Until Session 2 lands:
- mock `/api/me`
- mock `/api/me/permissions`
- mock `/api/context/current`
- stub the planner against a fixed allowlist

### Dependency on Session 3
Need:
- UI client ready to consume SSE
- conversation and catalog clients
- active route/page context to be sent into `POST /api/assistant/chat`

Until Session 3 lands:
- validate contracts with sample payloads and curlable examples
- keep the SSE event vocabulary stable

## Merge gates for this lane

This lane should not merge until these are true:

### Gate A — contract freeze
- request/response shapes are written down
- Session 3 can consume them without guessing
- Session 2 knows what identity/context payloads are needed

### Gate B — schema freeze
- `014` and `015` are stable
- no second conversation system exists
- action catalog identity model is stable

### Gate C — endpoint proof
- catalog endpoint returns imported actions
- conversation list and detail endpoints work
- streaming endpoint can be demoed end-to-end

## Definition of done for the first pass

This lane is considered done for the first merge if all of these are true:

- `GET /api/assistant/catalog` works
- `GET /api/assistant/conversations` works
- `GET /api/assistant/conversations/{id}` works
- `POST /api/assistant/chat` streams SSE events
- conversations persist and reload
- catalog entries are slug-based and legacy aliases are preserved
- no direct connector-table reads exist in the assistant planner
- role aliases are normalized to canonical role keys
- tests cover the contract and guardrails

## Reconciliation checklist against the master roadmap

At the start and end of each work block, explicitly verify:

1. Is the implementation still aligned to:
   - Phase 2
   - Phase 5
   - Phase 6 prep
   - Phase 11 hardening

2. Has any code reintroduced one of the known problems?
   - duplicate conversation storage
   - `procore.*` assumptions
   - legacy role keys as canon
   - `C-*` as primary action identity

3. Did any contract drift from:
   - `GET /api/assistant/catalog`
   - `GET /api/assistant/conversations`
   - `POST /api/assistant/chat`
   - `GET /api/context/current`

4. If a drift was necessary, was it reflected in:
   - this session doc
   - the master roadmap
   - the other two session docs

## Suggested end-of-session status note

Use this template in the parallel chat when closing a work block:

```md
### Session 1 status
Completed:
- ...

In progress:
- ...

Blocked by Session 2:
- ...

Blocked by Session 3:
- ...

Contracts changed:
- ...

Roadmap reconciliation:
- Still aligned to Phase 2 / 5 / 6-prep / 11
- Drift introduced: yes/no
- If yes, updated docs: yes/no
```
