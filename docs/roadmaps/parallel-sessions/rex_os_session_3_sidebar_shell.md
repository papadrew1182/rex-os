# Rex OS parallel session 3 — app shell, persistent sidebar assistant, and control-plane UI

## How to use this document

This file is the **full context packet** for one parallel coding/chat session. Open it in its own chat and treat it as the execution charter for the frontend and UI shell lane.

This session must reconcile against these master artifacts at the start and end of each work block:

- `rex_os_full_roadmap.md`
- `rex_os_quick_actions_inventory.csv`
- `rex_os_automation_inventory.csv`

This lane maps to the master roadmap primarily across:
- Phase 0 — inventory, normalization, and contract freeze
- Phase 3 — persistent sidebar shell
- Phase 8 — My Day, alerts, notifications, and control plane
- later support for Phase 9 and Phase 10 surfaces

## Program context you should assume

> **BASELINE RECONCILIATION 2026-04-14.** The "placeholder App.jsx"
> description below was from an earlier planning snapshot. The current
> repo is production-deployed at `main @ 3148f0c` with 32 existing page
> components, react-router 7, a functional (non-placeholder) App.jsx,
> and 81 Vite build modules. There is still no assistant sidebar,
> control plane UI, or My Day surface, so this lane's core mission is
> unchanged. Session 3's first commit on `feat/sidebar-shell` at
> `ee8f7dd` already added the sidebar + mocked hooks (`useMe`,
> `usePermissions`, `useCurrentContext`) alongside the existing shell
> without removing it. Session 2 will deliver the backing endpoints
> (`GET /api/me`, `/api/me/permissions`, `/api/context/current`,
> `/api/connectors`, `/api/connectors/health`) that the mocked hooks
> are already written against. See
> `docs/roadmaps/baseline-reconciliation.md` for the full mapping.

`rex-os` currently has:
- a placeholder `frontend/src/App.jsx`
- a basic Vite React setup
- no routing library yet
- no persistent app shell
- no assistant UI
- no control plane UI

`rex-procore` is the behavioral source system for this lane. The most important reference modules are:

- `frontend/src/UnifiedAssistant.jsx`
- `frontend/src/AIAssistant.jsx`
- `frontend/src/AISessions.jsx`
- `frontend/src/MyDayDashboard.jsx`
- `frontend/src/AlertsPage.jsx`
- `frontend/src/NotificationPreferencesPanel.jsx`
- `frontend/src/SyncMonitor.jsx`
- `frontend/src/App.jsx`
- `frontend/src/config/dashboard_access_config_6roles.json`

Architectural decisions already locked:
- the assistant must live as a **persistent sidebar**, not a separate page
- the sidebar must be available everywhere in the app shell
- action visibility, readiness, and permissions should come from the backend, not hardcoded frontend logic
- the action catalog is registry-driven
- roles are canonicalized to the six-key system and are extensible
- the UI should be built to consume stable API contracts from Session 1 and Session 2
- this lane should favor a clean shell and durable contracts over a flashy one-off page

## Canonical role model

Canonical role keys:

- `VP`
- `PM`
- `GENERAL_SUPER`
- `LEAD_SUPER`
- `ASSISTANT_SUPER`
- `ACCOUNTANT`

Do not hardcode legacy role names as primary UI logic keys.

## Lane mission

Build the app shell that turns `rex-os` from a placeholder into a usable operating system with AI always present.

This lane owns:
- replacing the placeholder frontend shell
- global layout
- persistent right-rail assistant
- conversation history UI
- quick action launcher UI
- command mode UI
- app-level context capture
- starter control-plane UI surfaces
- My Day starter surface
- control-plane placeholders for connectors, actions, automations, and queues

This lane does **not** own:
- backend migrations
- connector sync implementation
- assistant model execution
- chat persistence internals
- writeback execution logic
- final automation business logic

## Branch and ownership boundary

Recommended branch name:

`feat/sidebar-shell`

Do not take ownership of:
- backend conversation persistence
- canonical schema design
- connector adapters
- action execution queues on the server side

You can mock these interfaces until the backend lanes are ready, but do not permanently redefine their contracts in the frontend lane.

## What the app shell should become

The current `frontend/src/App.jsx` is only a health-check page. Replace that with a shell architecture.

Recommended top-level structure:

```text
frontend/src/
  App.jsx
  main.jsx
  app/
    Shell.jsx
    routes.jsx
    AppContext.jsx
  assistant/
    AssistantSidebar.jsx
    ConversationList.jsx
    ChatThread.jsx
    ChatComposer.jsx
    QuickActionLauncher.jsx
    ParamForm.jsx
    CommandModePanel.jsx
    useAssistantClient.js
    useAssistantState.js
  controlPlane/
    ControlPlaneHome.jsx
    ConnectorHealthPanel.jsx
    ActionCatalogPanel.jsx
    AutomationRegistryPanel.jsx
    QueueReviewPanel.jsx
  myday/
    MyDayHome.jsx
  hooks/
    useCurrentContext.js
    useMe.js
    usePermissions.js
  lib/
    api.js
    sse.js
```

You do not have to use exactly these names, but the shell should clearly separate assistant UI, control-plane UI, and app context.

## Required dependency additions

The current frontend only has React and React DOM. This lane will almost certainly need at least:

- `react-router-dom`

Avoid introducing heavy state-management libraries unless there is a strong reason. React context + hooks + reducers is enough for the first pass.

## Primary UI goals

### 1. Persistent sidebar assistant
The assistant should be visible across the product in a right rail with:
- collapse / expand
- conversation list
- active thread
- streaming responses
- quick actions
- follow-up chips
- command mode entry
- route/project context awareness
- ability to expand into a larger workspace mode

### 2. App shell
The shell should support:
- a main content area
- a right assistant rail
- top-level route state
- page context capture for the assistant
- space for later dashboard and operational surfaces

### 3. Control plane starter surfaces
Because this project will be built in parallel and heavily tested, the UI should expose a control plane early:
- connector health
- action catalog with readiness badges
- automation registry with readiness badges
- writeback/queue placeholders
- role and capability inspection placeholders
- My Day entry point

## Assistant API contracts consumed by this lane

Do not invent alternate contracts unless the team explicitly agrees and all docs are updated.

### `GET /api/me`

Use this shape:

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

Use this shape:

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

Use this shape:

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

### `GET /api/assistant/catalog`

Use this shape:

```json
{
  "version": "v1",
  "categories": [
    {"key": "FINANCIALS", "label": "Financials"}
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

Use this shape:

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

Use this shape:

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

Use this request shape:

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

Consume the SSE stream with these event types:
- `conversation.created`
- `message.started`
- `message.delta`
- `message.completed`
- `followups.generated`
- `action.suggestions`
- `error`

## UI state model

Use a small, clear state architecture. Recommended global state buckets:

- `me`
- `permissions`
- `currentContext`
- `assistantCatalog`
- `assistantConversations`
- `activeConversation`
- `assistantUIState`  
  e.g. collapsed/expanded, active tab, workspace mode
- `controlPlaneSummary`

Avoid letting route components own the only copy of critical assistant state. The assistant is global.

## Component responsibilities

### `Shell`
- app chrome
- main content area
- right sidebar mount
- global route context hook
- control of expanded workspace mode

### `AssistantSidebar`
- overall assistant container
- collapse/expand
- tabs or sections if needed
- renders conversation list + active thread + quick action entry

### `ConversationList`
- recent conversations
- selection
- archive/delete affordance later
- loading and empty states

### `ChatThread`
- message rendering
- stream updates
- assistant structured payload rendering
- follow-up chip rendering

### `ChatComposer`
- free-form prompt input
- action-aware prompt behavior
- submit and retry
- loading/disabled states

### `QuickActionLauncher`
- browse catalog
- category filter
- readiness badges
- role visibility handling based on backend payload
- parameter entry and launch

### `ParamForm`
- render from `params_schema`
- support project/date/month/quarter/year/text/select
- validate required params
- hand back normalized param payload

### `CommandModePanel`
- explicit command mode entry
- confirm parsed commands later
- low-risk/high-risk display later
- can be initially a thin wrapper over `POST /api/assistant/chat` with `mode: "command"`

### `ControlPlane` panels
- connector health
- action catalog
- automation registry
- queue review placeholders
- role/capability inspector placeholders

### `MyDayHome`
- starter personalized summary surface
- can begin as mocked or thin API-driven placeholder
- should visually fit into the new shell from the beginning

## Recommended implementation sequence

### Work packet A — shell foundation
- replace placeholder `App.jsx`
- add routing
- create a durable shell layout with a right rail
- make the shell resilient on narrow widths

### Work packet B — assistant sidebar skeleton
- create sidebar container
- add collapsed and expanded states
- add placeholder conversation list
- add placeholder thread area
- add composer shell

### Work packet C — mocked clients
Before backend endpoints are live:
- create mock `useMe`
- create mock `usePermissions`
- create mock `useCurrentContext`
- create mock `useAssistantClient`
- create mock catalog and conversation responses using the published contract

This lets the UI lane move immediately.

### Work packet D — catalog and quick actions
- render categories
- render action cards
- show readiness badges
- render parameter forms from schema
- launch actions into chat

### Work packet E — streaming thread
- wire SSE client
- show incremental assistant message output
- persist streamed content in client state
- show follow-up chips

### Work packet F — context injection
- detect current route
- detect selected project
- pass page context into the assistant request
- make current project visible in the sidebar

### Work packet G — control plane starter
- add a control-plane home route or panel
- show connector health
- show action readiness
- show automation readiness
- show queue placeholders
- show role/capability inspection placeholder

### Work packet H — My Day starter
- create the first My Day surface
- make it part of the shell
- support a compact summary and future deeper navigation

### Work packet I — hardening
- loading states
- error states
- reconnect behavior for SSE
- empty states
- responsive behavior
- keyboard usability

## What to lift from `rex-procore` vs what to rewrite

### Lift behavior from:
- `UnifiedAssistant.jsx` for action-launch and conversation behavior
- `AISessions.jsx` for session-list ideas
- `MyDayDashboard.jsx` for the idea of the My Day surface
- `AlertsPage.jsx`, `NotificationPreferencesPanel.jsx`, and `SyncMonitor.jsx` for control-plane concepts

### Rewrite for `rex-os`:
- app shell layout
- role visibility logic (must be backend-driven now)
- action identity (slug-based, not `C-*` primary keys)
- permanent sidebar implementation
- overall state model
- contract-driven hooks and clients

## Readiness badge vocabulary

The UI should display readiness in a consistent way using the backend field `readiness_state`.

Supported values:
- `live`
- `alpha`
- `adapter_pending`
- `writeback_pending`
- `blocked`
- `disabled`

Do not invent frontend-only statuses unless the team agrees and docs are updated.

## Non-goals for this session

Do not spend time on:
- backend migration authoring
- connector sync code
- model prompt engineering
- final queue approval workflows
- fully polished design systems
- mobile-first redesign
- voice input implementation

## Cross-lane dependencies

### Session 1 dependencies
Need:
- stable assistant API contracts
- SSE event vocabulary
- catalog payload
- conversation payloads

Until Session 1 lands:
- use mock clients and sample payloads from this doc
- do not freeze a different contract in code

### Session 2 dependencies
Need:
- `/api/me`
- `/api/me/permissions`
- `/api/context/current`
- connector health
- control-plane status data
- role/capability metadata

Until Session 2 lands:
- use mock identity and context hooks
- design the UI so the swap from mocks to live data is trivial

## Merge gates for this lane

### Gate A — shell freeze
- the app is no longer a health page
- the right-rail assistant is mounted in the shell
- mocks can drive the UI even before backend completion

### Gate B — contract freeze
- hooks consume the published API shapes
- no frontend-only alternate contract has been introduced

### Gate C — demo readiness
- user can see the assistant everywhere
- user can open a conversation
- user can launch a quick action
- user can see a stream render in the thread
- user can inspect starter control-plane surfaces

## Definition of done for the first pass

This lane is considered done for the first merge if all of these are true:

- `App.jsx` has been replaced by a real shell
- a persistent right-rail assistant exists
- conversation list UI exists
- active thread UI exists
- quick action launcher exists
- schema-driven parameter forms exist
- mockable API hooks exist
- SSE streaming renderer exists
- route/project context can be attached to assistant requests
- starter control-plane surfaces exist
- My Day starter surface exists or has a clear mounted placeholder in the shell

## Reconciliation checklist against the master roadmap

At the start and end of each work block, explicitly verify:

1. Is the implementation still aligned to:
   - Phase 3
   - Phase 8
   - later support for Phase 9 and 10

2. Has any code reintroduced old `rex-procore` structural issues?
   - assistant as a separate page rather than a persistent shell surface
   - hardcoded frontend role logic as the source of truth
   - `C-*` as primary action identity
   - one-off components not wired into a durable shell

3. Did any UI contract drift from the published API shapes?

4. If a drift was necessary, was it reflected in:
   - this session doc
   - the master roadmap
   - Session 1 and Session 2 docs

## Suggested end-of-session status note

Use this template in the parallel chat when closing a work block:

```md
### Session 3 status
Completed:
- ...

In progress:
- ...

Blocked by Session 1:
- ...

Blocked by Session 2:
- ...

Contracts changed:
- ...

Roadmap reconciliation:
- Still aligned to Phase 3 / 8 / later 9-10 support
- Drift introduced: yes/no
- If yes, updated docs: yes/no
```
