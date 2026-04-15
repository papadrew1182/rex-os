# AI Spine Handoff (Session 1 → Session 2 and Session 3)

**Branch:** `feat/ai-spine`
**Scope:** backend assistant backbone only — routing, persistence, catalog, SQL guard, SSE stream.

This doc is a short developer-facing cheat sheet. For the long-form
charter see `docs/roadmaps/parallel-sessions/rex_os_session_1_ai_spine.md`.

## Current commit stack (merge-ready)

```
704e2a4  feat(ai-spine): real optional Anthropic provider behind ModelClient
cf7f7d3  fix(ai-spine): register 006/007/008 + add live-DB merge gate
4e29897  test(ai-spine): add drift, route-registration, fresh-env guardrails
a552deb  feat(ai-spine): Session 1 backbone + full catalog import
ee8f7dd  feat(sidebar-shell): persistent right-rail assistant + control plane + my day  [Session 3, inherited parent]
526fae1  Add rex-os roadmap and AI planning inventories                                  [merge base with main]
```

All four ``(ai-spine)`` commits are Session 1's. ``ee8f7dd`` is
Session 3's committed frontend work, inherited as a parent of this
branch — see *Merge hot spots* below for what that implies.

## Required checks before merging

Run these from ``backend/`` in the ai-spine worktree (or wherever the
branch is checked out):

| Check | Command | Required? |
|---|---|---|
| Hermetic suite (no DB, no network) | `py -3 -m pytest tests/test_assistant_sql_guard.py tests/test_assistant_context_builder.py tests/test_quick_actions_catalog.py tests/test_assistant_router_contract.py tests/test_catalog_migration_drift.py tests/test_assistant_route_registration.py tests/test_assistant_fresh_env_smoke.py tests/test_assistant_anthropic_provider.py -q` | **yes** — 91 passing |
| Live-DB merge gate | `DATABASE_URL=postgres://... py -3 -m pytest tests/test_assistant_live_db_smoke.py -v -m live_db` | **yes** — 15 passing if Postgres is reachable |
| Live Anthropic proof | `REX_RUN_LIVE_ANTHROPIC=1 ANTHROPIC_API_KEY=sk-ant-... py -3 -m pytest tests/test_assistant_live_anthropic_smoke.py -v -m live_anthropic` | **no** — optional, 1 billed call (max_tokens=50) |

Hermetic + live-DB together is the merge gate. Live-Anthropic is
evidence-only and explicitly not required.

## Merge hot spots (from the Session 1 audit)

When merging ``feat/ai-spine`` into ``main``, expect conflicts only
on the following files. Everything else Session 1 touches is a new
file and will land cleanly.

### 1. `backend/app/migrate.py`

**Highest-risk hotspot.** Session 1 appends three entries to
``MIGRATION_ORDER`` for the AI spine migrations:

```
"006_ai_chat_and_prompts.sql",
"007_ai_action_catalog.sql",
"008_ai_action_catalog_seed.sql",
```

Session 2 also appends to the same list (its RBAC / user-roles /
seed migrations use distinct filenames like
``008_rbac_roles_permissions.sql`` / ``009_user_roles_preferences.sql``
/ ``020_seed_roles_and_aliases.sql``). Git will flag a conflict
because both sessions add at the same location.

**Resolution:** keep both blocks of additions. Ordering does not
matter — the filenames are all distinct, and the migration runner
applies them in the order they appear in the list.

### 2. `backend/app/routes/__init__.py`

Session 1 adds one import for ``routers.assistant`` and one entry
for ``assistant_router`` at the end of ``all_routers``. Low conflict
risk — Session 3 is frontend-only and Session 2 does not appear to
touch this file. If it conflicts, keep Session 1's import and list
entry. ``tests/test_assistant_route_registration.py`` will fail
immediately if the wiring is dropped.

### 3. `backend/requirements.txt`

Session 1 adds one dependency (``anthropic>=0.40.0,<1.0``) near the
bottom. Low conflict risk.

### 4. `backend/pytest.ini`

Session 1 adds a ``markers`` section with two markers (``live_db``
and ``live_anthropic``). Low conflict risk.

### 5. Session 3 frontend files inherited via `ee8f7dd`

``feat/ai-spine`` is stacked on top of Session 3's frontend commit
``ee8f7dd`` (``feat(sidebar-shell): persistent right-rail assistant +
control plane + my day``). Merging Session 1 into main will also
bring Session 3's frontend work with it.

* If Session 3 has **not yet** merged into main: Session 1 brings
  Session 3's frontend along as a side effect. That is usually fine.
* If Session 3 has **already** merged via a different commit SHA
  (e.g. a squash or rebase), git will see the same content from two
  different commit paths. Standard 3-way merge handles that, but
  verify no duplicate files in the result.
* If both Session 1 and a separate Session 3 merge both touch
  ``frontend/src/App.jsx`` or ``frontend/src/rex-theme.css`` with
  different content, expect conflicts there.

If this matters at merge time, rebasing ``feat/ai-spine`` onto a
``main`` that already contains Session 3's frontend would drop the
``ee8f7dd`` parent cleanly. Do not do that speculatively — only if
the side-effect merge becomes a problem in practice.

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
  test_assistant_live_db_smoke.py           # 15 live-DB merge gate (@pytest.mark.live_db)
  test_assistant_anthropic_provider.py      # 15 hermetic provider tests (echo + Anthropic stub)
  test_assistant_live_anthropic_smoke.py    # 1 opt-in live Anthropic proof (@pytest.mark.live_anthropic + REX_RUN_LIVE_ANTHROPIC=1)
```

Run the hermetic AI spine suite (no DB required):

```sh
cd backend
py -3 -m pytest tests/test_assistant_sql_guard.py \
                tests/test_assistant_context_builder.py \
                tests/test_quick_actions_catalog.py \
                tests/test_assistant_router_contract.py \
                tests/test_catalog_migration_drift.py \
                tests/test_assistant_route_registration.py \
                tests/test_assistant_fresh_env_smoke.py \
                tests/test_assistant_anthropic_provider.py -q
```

Expected: **91 tests passing** (15 + 13 + 22 + 8 + 3 + 7 + 8 + 15) with zero DB.

Run the live-DB merge gate (requires reachable Postgres):

```sh
cd backend
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rex_os \
    py -3 -m pytest tests/test_assistant_live_db_smoke.py -v -m live_db
```

Expected: **15 passing** against a real Postgres. Skipped automatically
when `DATABASE_URL` is unset or the DB is unreachable.

Run **everything together** (hermetic + live gate) when a Postgres is
available — this is the full Session 1 merge signal:

```sh
cd backend
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rex_os \
    py -3 -m pytest tests/test_assistant_sql_guard.py \
                    tests/test_assistant_context_builder.py \
                    tests/test_quick_actions_catalog.py \
                    tests/test_assistant_router_contract.py \
                    tests/test_catalog_migration_drift.py \
                    tests/test_assistant_route_registration.py \
                    tests/test_assistant_fresh_env_smoke.py \
                    tests/test_assistant_anthropic_provider.py \
                    tests/test_assistant_live_db_smoke.py -q
```

Expected: **106 tests passing** (91 hermetic + 15 live DB gate).

## Model provider (echo default, Anthropic optional)

Session 1 ships two providers behind a single ``ModelClient`` protocol
in ``backend/services/ai/model_client.py``:

| Provider | Default? | Enabled by | Dependencies |
|---|---|---|---|
| `EchoModelClient` | **yes** | `REX_AI_PROVIDER` unset / `=echo` / unknown | none |
| `AnthropicModelClient` | no | `REX_AI_PROVIDER=anthropic` + `ANTHROPIC_API_KEY=...` | `anthropic` SDK (in `requirements.txt`) |

Env vars:

```sh
REX_AI_PROVIDER=echo                    # default, safe, no network, no key
REX_AI_PROVIDER=anthropic               # activate real Anthropic streaming
ANTHROPIC_API_KEY=sk-ant-...            # required when provider=anthropic
REX_ANTHROPIC_MODEL=claude-sonnet-4-6   # optional override, defaults to claude-sonnet-4-6
```

**Failure semantics are deterministic and loud, never silent:**

* `REX_AI_PROVIDER=anthropic` + SDK missing → first chat request
  emits a frozen `error` SSE event with code
  `anthropic_sdk_missing` and a message pointing at
  `pip install anthropic`. The stream terminates; no assistant
  message is persisted. Catalog and conversations endpoints keep
  working because dispatcher construction doesn't depend on the
  model client.
* `REX_AI_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` unset or empty →
  first chat request emits `error` SSE with code
  `anthropic_api_key_missing`. Same non-fatal behavior for the rest
  of the app.
* User message **is still persisted before** any model call, so a
  misconfigured provider never loses the user prompt — the
  `message.started` event fires with the real user_message_id
  before the `error` event appears.

Contract-stable: no change to HTTP shapes, the catalog, the chat
request payload, or the frozen SSE vocabulary. The only new code is a
provider class, a structured `ProviderNotConfigured` exception, and a
new handler in `chat_service` that converts it into an SSE `error`
event with a specific code.

**Live Anthropic traffic has been proven once against the real API.**
A single opt-in streaming call (`max_tokens=50`, model
`claude-sonnet-4-6`) succeeded end-to-end against
`api.anthropic.com/v1/messages` and yielded multiple non-empty
deltas. The hermetic path through `test_assistant_anthropic_provider.py`
still drives a stubbed SDK client that matches
`anthropic.AsyncAnthropic.messages.stream(...)` shape and remains
the routine test. The live proof lives in
`tests/test_assistant_live_anthropic_smoke.py` as a hard opt-in test:

```sh
cd backend
REX_RUN_LIVE_ANTHROPIC=1 \
ANTHROPIC_API_KEY=sk-ant-... \
    py -3 -m pytest tests/test_assistant_live_anthropic_smoke.py \
                    -v -m live_anthropic
```

The test skips cleanly in three independent ways:
* when `ANTHROPIC_API_KEY` is unset
* when the `anthropic` package is not installed
* when `REX_RUN_LIVE_ANTHROPIC` is not `1`/`true`/`yes`

All three must be present for the test to run. It is not a merge
gate and must not be treated as one.

## Live-Postgres merge gate (verified)

Session 1 is **merge-ready against a real Postgres**. A marker-gated
integration test exercises every Session 1-owned surface end to end:

```sh
cd backend
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rex_os \
    py -3 -m pytest tests/test_assistant_live_db_smoke.py -v -m live_db
```

Expected: **15 passing**. The test is skipped automatically when the
DB is unreachable, so the default hermetic suite stays green on
machines without Postgres.

The live gate proves, against a real asyncpg-backed Postgres:

1. **`app/migrate.py::MIGRATION_ORDER` registers 006/007/008** and
   `apply_migrations()` runs them cleanly. This was an actual defect
   found and fixed during Session 1's live verification pass — prior
   to the fix, fresh environments running `REX_AUTO_MIGRATE=true`
   would stop at migration 005 and never create the AI spine tables.
2. **`rex.chat_conversations`, `rex.chat_messages`, `rex.ai_prompt_registry`,
   `rex.ai_action_catalog` tables exist** with the expected shape,
   including CHECK constraints on `risk_tier` and `readiness_state`
   and the `set_updated_at` trigger.
3. **Migration 008 seeds exactly 77 canonical slugs and 80 legacy
   aliases**. The `jsonb_to_recordset` + `ON CONFLICT (slug) DO UPDATE`
   path applies cleanly.
4. **Zero `C-*` values used as primary slug** in the live catalog.
5. **All three required dedupes resolve in SQL**:
   `C-8`/`C-28` → `submittal_sla`, `C-15`/`C-60` → `monthly_owner_report`,
   `C-5`/`C-29` → `rfi_aging`.
6. **`CatalogRepository`** live: `list_actions()`, `list_actions(role_keys=...)`,
   `get_by_slug()`, `resolve_alias()` all return the expected rows.
7. **`PromptRepository.get_active('assistant.system.base')`** returns
   the seeded prompt with `is_active=true` and `prompt_type='system'`.
8. **`ChatRepository`** full round-trip: create a conversation with
   `page_context`, append user + assistant messages with
   `structured_payload`, touch to update `last_message_at` and title,
   list conversations (with `last_message_preview`), get detail, archive
   (soft delete), confirm gone from list and detail, confirm re-archive
   returns False.
9. **Live API contract** — all 5 endpoints over the real pool:
   - `GET /api/assistant/catalog` → 200, 77 actions
   - `POST /api/assistant/chat` → 200, `text/event-stream`, full
     frozen SSE vocabulary emitted in the guaranteed order
   - `GET /api/assistant/conversations` → 200, new conversation present
   - `GET /api/assistant/conversations/{id}` → 200, user+assistant messages
   - `DELETE /api/assistant/conversations/{id}` → 204
   - Refetch after DELETE → 404, re-DELETE → 404
10. **User message is persisted before model execution** (observed in
    the chat_service stream — the user message id is emitted in
    `message.started` before any `message.delta`).

## What remains unproven

Only what sits outside Session 1's lane:

1. **Planner execution against `rex.v_*` curated views** is owned by
   Session 2 and those views do not exist yet. This is NOT a Session 1
   merge blocker: `SqlGuard` unit tests prove the deny-list is correct,
   and the planner's `plan_and_run` path is fine up to the point where
   it hits the missing view. Once Session 2 lands the views, the
   assistant will transparently start executing against them.
2. **Live Anthropic network traffic at scale** — one real streaming
   call has been exercised against `api.anthropic.com/v1/messages`
   via `tests/test_assistant_live_anthropic_smoke.py` (opt-in, not a
   merge gate). Extended live usage, concurrency behavior, and
   latency characteristics are not part of Session 1's scope. The
   live DB gate continues to use `REX_AI_PROVIDER=echo`.

## Manual reproduction (no pytest)

If you want to verify the live path by hand:

```sh
# 1. apply migrations (picks up 006/007/008 automatically)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rex_os \
REX_AUTO_MIGRATE=true \
    uvicorn main:app --app-dir backend

# 2. curl the catalog and count actions
curl -s http://localhost:8000/api/assistant/catalog | jq '.actions | length'
# -> 77

# 3. curl a chat round-trip (echo provider is fine)
curl -N -X POST http://localhost:8000/api/assistant/chat \
    -H 'content-type: application/json' \
    -d '{"message":"smoke","page_context":{}}'
```
