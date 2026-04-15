# AI Spine Handoff (Session 1 → Session 2 and Session 3)

**Branch:** `feat/ai-spine`
**Scope:** backend assistant backbone only — routing, persistence, catalog, SQL guard, SSE stream.

This doc is a short developer-facing cheat sheet. For the long-form
charter see `docs/roadmaps/parallel-sessions/rex_os_session_1_ai_spine.md`.

## What Session 1 owns

- `backend/routers/assistant.py` — the 5 frozen HTTP endpoints
- `backend/services/ai/` — dispatcher, chat service, SQL guard/planner,
  prompt registry, context builder, followups, catalog service,
  model client, catalog importer
- `backend/repositories/` — asyncpg data access for `rex.chat_*` and
  `rex.ai_*` tables
- `backend/schemas/` — Pydantic request/response contracts
- `backend/data/quick_actions_catalog.py` — canonical source of truth
  for the quick-action catalog (77 slugs / 80 legacy aliases)
- `migrations/006_ai_chat_and_prompts.sql`
- `migrations/007_ai_action_catalog.sql`
- `migrations/008_ai_action_catalog_seed.sql`

## Drift-proofing and merge-safety guardrails

Three test files exist specifically to keep Session 1 merge-ready.
None of them require a live DB.

| Test file | What it protects |
|---|---|
| `tests/test_catalog_migration_drift.py` | Regenerates `008_ai_action_catalog_seed.sql` in memory from `backend/data/quick_actions_catalog.py` and fails if the checked-in SQL differs by a single byte. Failure message points at the regenerate command. |
| `tests/test_assistant_route_registration.py` | Imports `main.app` and asserts every frozen `/api/assistant/*` endpoint is physically mounted on the live FastAPI app. Scans `services/ai/chat_service.py` source for every SSE event type in the frozen vocabulary. Catches the exact regression where the wiring in `app/routes/__init__.py` got reverted and requests fell through to the SPA fallback. |
| `tests/test_assistant_fresh_env_smoke.py` | End-to-end check of Session 1-owned surfaces using `FakeDispatcher`: catalog endpoint returns all 77 slugs, all 80 legacy aliases carry to the wire, required dedupes survive the round-trip, chat endpoint streams the full SSE vocabulary. |

To run all guardrails together:

```sh
cd backend
py -3 -m pytest tests/test_catalog_migration_drift.py \
                tests/test_assistant_route_registration.py \
                tests/test_assistant_fresh_env_smoke.py -q
```

## Frozen HTTP contracts

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/assistant/catalog` | Full catalog projection, optionally filtered by the caller's canonical role keys (done inside the router). |
| `GET` | `/api/assistant/conversations` | List of un-archived conversations for the current user, ordered by `last_message_at desc`. |
| `GET` | `/api/assistant/conversations/{conversation_id}` | Conversation + full message history. |
| `DELETE` | `/api/assistant/conversations/{conversation_id}` | Soft delete via `archived_at`; returns 204 or 404. |
| `POST` | `/api/assistant/chat` | SSE streaming. Frame format: `data: <json>\n\n`. |

### SSE event vocabulary (frozen for Session 3)

Every event is a JSON object emitted as a `data:` line. The type lives
in the payload itself — no custom `event:` field.

```
conversation.created   { "type", "conversation_id" }
message.started        { "type", "conversation_id", "user_message_id" }
message.delta          { "type", "delta" }
followups.generated    { "type", "items": [...] }
action.suggestions     { "type", "items": [...] }         // reserved; not emitted in first pass
message.completed      { "type", "conversation_id", "message_id" }
error                  { "type", "code", "message" }
```

Ordering guarantees:
1. `conversation.created` (only when the caller did not pass a conversation_id)
2. `message.started`
3. one or more `message.delta` events
4. `followups.generated`
5. `message.completed`

An `error` event terminates the stream immediately. User messages are
**persisted before** the model is called, so a subsequent failure does
not lose the user prompt.

## Canonical catalog

- Source of truth: `backend/data/quick_actions_catalog.py`
- Bootstrap path: `migrations/008_ai_action_catalog_seed.sql` (auto-applied
  on startup when `REX_AUTO_MIGRATE=true`)
- Runtime surface: `rex.ai_action_catalog` table, read via
  `CatalogRepository` and projected through `CatalogService`
- Programmatic backfill: `services.ai.catalog_import.upsert_catalog(pool)`
  — idempotent; safe to re-run on any environment
- Counts: **77 canonical slugs** covering **80 legacy `C-*` aliases**

### Regenerate the SQL migration from the Python source

If you edit `quick_actions_catalog.py`, regenerate migration 008 in place:

```sh
cd backend
py -3 scripts/_build_catalog_migration.py
```

Then run the catalog + drift tests:

```sh
py -3 -m pytest tests/test_quick_actions_catalog.py \
                tests/test_catalog_migration_drift.py -q
```

The drift test will fail loudly if you edit the Python catalog without
regenerating the SQL (or vice versa). Commit both files in the same
change so CI can never observe them out of sync.

Structural invariants enforced by the test suite:

- 77 unique slugs
- 80 unique legacy aliases, all matching `C-\d+`
- every `C-1..C-79 + C-104` accounted for
- no `C-*` string used as a primary identity
- every `role_visibility` entry is one of the 6 canonical role keys
- every `risk_tier` and `readiness_state` is in the documented vocabulary
- required dedupes are present:
  - `C-8` + `C-28` → `submittal_sla`
  - `C-15` + `C-60` → `monthly_owner_report`
  - `C-5` + `C-29` → `rfi_aging` (Session 3 mockCatalog parity)

### Readiness vocabulary

`live | alpha | adapter_pending | writeback_pending | blocked | disabled`

### Risk vocabulary

`read_only | internal_write_low | connector_write_medium | connector_write_high`

### Canonical role keys

`VP | PM | GENERAL_SUPER | LEAD_SUPER | ASSISTANT_SUPER | ACCOUNTANT`

Legacy aliases (e.g. `VP_PM`, `General_Superintendent`) are normalized
in `services/ai/context_builder.py::normalize_role`. Role policy lives
in the backend; the frontend should never carry legacy keys.

### `can_run` semantics

`can_run` is a presentation hint derived from `enabled && readiness in {live, alpha}`.
It is intentionally **not** connector-aware in Session 1 — Session 2 can
layer a connector-availability check on top without changing the contract.

## What Session 2 must still provide

The AI spine depends on these but does not own them:

1. **`GET /api/me`** — returns canonical role keys and project membership.
2. **`GET /api/me/permissions`** — string permission list.
3. **`GET /api/context/current`** — current project + route + page context.
4. **`rex.v_*` curated views** — the full allowlist:
   - `rex.v_project_mgmt`
   - `rex.v_financials`
   - `rex.v_schedule`
   - `rex.v_directory`
   - `rex.v_portfolio`
   - `rex.v_risk`
   - `rex.v_myday`
5. **Connector availability metadata** — tells the catalog which
   `required_connectors` are provisioned so the frontend can render
   disabled chips for unavailable actions.

Until Session 2 lands:
- The router builds `AssistantUser` from `UserAccount.global_role`
  (legacy text column) via `ContextBuilder.build_user`.
- `SqlPlanner.plan_and_run` will fail when it hits a `rex.v_*` view that
  does not exist — the guard is fine, the views are missing.
- `AssistantUser.project_ids` is empty.

## What Session 3 can safely consume now

- `GET /api/assistant/catalog` — full 77-action catalog, role-filtered.
- `GET /api/assistant/conversations` / `GET /api/assistant/conversations/{id}` /
  `DELETE /api/assistant/conversations/{id}` — fully working against
  `rex.chat_conversations` once migration 006 is applied.
- `POST /api/assistant/chat` SSE — works today with `REX_AI_PROVIDER=echo`
  (the default). The echo client chunks a deterministic reply so the
  sidebar can be developed and tested without live model credentials.
- SSE event vocabulary, request shape, and response shape are frozen.
  Session 3 can parse `data:` frames and switch on the `type` field.

## Non-negotiable invariants

- **One conversation system.** `rex.chat_conversations` is the only
  conversation store. Do not reintroduce the legacy `assistant_conversations`
  / `chat_conversations` split from rex-procore.
- **Slug-first identity.** `C-*` IDs live only in `legacy_aliases`.
  No code path should treat a `C-*` string as a primary key.
- **Canonical roles only.** The frontend and the prompt never see
  legacy role strings — normalization happens inside `ContextBuilder`.
- **No connector-table reads in assistant logic.** Anything the
  assistant reads must go through a curated `rex.v_*` view.
- **The SQL guard is strict by default.** If a query fails the deny-list
  it is rejected with a structured `BlockedQueryError`. Never relax the
  guard — tighten the allowlist instead.
- **`can_run` is readiness/enabled only.** It is explicitly NOT
  connector-aware in Session 1. Session 2 can layer a per-tenant
  connector-availability check on top of `can_run` without changing
  the contract shape.
- **Router wiring must stay in `app/routes/__init__.py`.** The AI
  spine router is mounted by appending `assistant_router` to
  `all_routers`. `tests/test_assistant_route_registration.py` guards
  this wiring and will fail loudly if it is dropped.

## Parallel-session repo hygiene

Session 1 hit a real problem during its first and second passes: a
parallel agent for Session 2 was running in the same physical repo,
flipping the git HEAD between tool calls and wiping untracked Session 1
files. If you find yourself in the same situation, the survival rules
are:

1. **Use `git worktree` for true isolation.** Create a dedicated
   worktree for Session 1 with
   `git worktree add ../rex-os-ai-spine feat/ai-spine`. The parallel
   session cannot touch the worktree because its HEAD is independent.
2. **Commit fast.** Untracked files are vulnerable to branch-switching
   by other agents. Committed files on `feat/ai-spine` live in git
   history and cannot be wiped without an explicit `git reset --hard`.
3. **Use one Bash invocation for `checkout + add + commit`** so the
   branch cannot flip between the three. Staging inside a shell across
   separate tool calls is not atomic.
4. **Do not broad-stage `git add migrations/`** — that sweeps up
   other sessions' dirty tracked files. Stage by exact filename or
   by narrow subdirectories you own.
5. **Session 1-owned migrations are 006/007/008 under the
   `008_ai_action_catalog_seed.sql` filename**. Session 2 also has
   files numbered 008/009/020 but on different names. They coexist
   alphabetically; no filename collision exists.

## Test layout

```
backend/tests/
  _assistant_fakes.py                       # FakeDispatcher, FakeChatRepo, etc.
  test_assistant_sql_guard.py               # 15 deny-list / accept cases
  test_assistant_context_builder.py         # 13 role normalization cases
  test_quick_actions_catalog.py             # 22 catalog invariant cases
  test_assistant_router_contract.py         # 8 contract cases (catalog + conv + SSE)
  test_catalog_migration_drift.py           # 3 drift-detection cases
  test_assistant_route_registration.py      # 7 route-registration + SSE vocabulary
  test_assistant_fresh_env_smoke.py         # 8 end-to-end surface checks
```

Run the AI spine suite in isolation:

```sh
cd backend
py -3 -m pytest tests/test_assistant_sql_guard.py \
                tests/test_assistant_context_builder.py \
                tests/test_quick_actions_catalog.py \
                tests/test_assistant_router_contract.py \
                tests/test_catalog_migration_drift.py \
                tests/test_assistant_route_registration.py \
                tests/test_assistant_fresh_env_smoke.py -q
```

Expected: **76 tests passing** (15 + 13 + 22 + 8 + 3 + 7 + 8) with zero DB.

## What remains unproven without a live Postgres

The fresh-environment smoke test substitutes `FakeDispatcher` for the
real asyncpg path. The following must still be verified against an
actual Postgres instance before Session 1 can be called fully merge-safe:

1. **Migrations 006/007/008 apply cleanly** on a fresh DB under
   `REX_AUTO_MIGRATE=true` — the CHECK constraints on `risk_tier` and
   `readiness_state`, the partial unique index on `ai_prompt_registry`,
   and the `ON CONFLICT (slug) DO UPDATE` upsert in migration 008 are
   not exercised by any unit test.
2. **`rex.chat_conversations` / `rex.chat_messages` CRUD** through the
   real `ChatRepository` — the router-contract tests use
   `FakeChatRepository`, so jsonb column round-trips, trigger-based
   `updated_at`, and the cascade from `chat_conversations -> chat_messages`
   are not exercised.
3. **The `rex.v_*` curated views** needed by `SqlPlanner.plan_and_run`
   are owned by Session 2 and do not exist yet. The guard and planner
   are ready; the data is not.

To run the missing verification manually once the views land:

```sh
# 1. apply migrations
REX_AUTO_MIGRATE=true uvicorn backend.main:app

# 2. curl the catalog and count actions
curl -s http://localhost:8000/api/assistant/catalog | jq '.actions | length'
# -> 77

# 3. curl a chat round-trip (echo provider is fine)
curl -N -X POST http://localhost:8000/api/assistant/chat \
    -H 'content-type: application/json' \
    -d '{"message":"smoke","page_context":{}}'
```
