# Phase 5 Wave 1 — Alpha Quick Actions Design

**Status:** approved 2026-04-21, ready for implementation plan.
**Author:** Claude + Andrew Roberts (brainstorming session 2026-04-21).

## Goal

Wire the 8 "alpha" Wave 1 quick actions to real SQL against existing `rex.v_*` canonical views so that clicking one in the sidebar produces a data-grounded answer instead of a generic LLM response. Ship all 8 in one PR. Flip their `readiness_state` from `"alpha"` to `"live"` in the catalog in the same commit that wires them.

**Actions in scope** (all 8 from `docs/SESSION_HANDOFF_2026_04_20.md`):

| slug                       | primary source                       |
| -------------------------- | ------------------------------------ |
| `rfi_aging`                | `rex.v_project_mgmt` (type='rfi')    |
| `submittal_sla`            | `rex.v_project_mgmt` (type='submittal') |
| `budget_variance`          | `rex.v_financials`                   |
| `daily_log_summary`        | `rex.daily_logs` + `rex.manpower_logs` |
| `critical_path_delays`     | `rex.v_schedule` (critical_path=true) |
| `two_week_lookahead`       | `rex.v_schedule` (start_date in [today, +14d]) |
| `documentation_compliance` | `rex.v_documents`                    |
| `my_day_briefing`          | `rex.v_myday`                        |

**Out of scope (follow-up):**

- The 4 `adapter_pending` Wave 1 actions (`change_event_sweep`, `inspection_pass_fail`, `schedule_variance`, `lookahead_status`) — blocked on the Phase 4 resource-rollout plan wiring connector data for submittals/daily_logs/tasks/change_events.
- Any UI-side changes in the sidebar (the frontend already sends `active_action_slug` in the chat payload; no frontend work needed for the MVP).

## Key decisions (brainstorm outcomes)

1. **Dispatch pattern (A):** Enrich the chat. `chat_service.stream_chat` checks `active_action_slug` before calling the model; if a handler is registered, run its SQL, append the result's `prompt_fragment` to the system prompt, continue SSE as today. No new routes, no new response types, no frontend contract change.
2. **Project scoping (B):** Default to portfolio view. If `page_context.project_id` is set, scope SQL to that project. Otherwise, join against `rex.v_user_project_assignments` to cover the projects the user has access to.
3. **Output shape (B):** Handler computes deterministic stats server-side (counts, aggregates) plus representative sample rows. The LLM wraps them in prose. We do NOT trust the LLM to count or aggregate.
4. **Shipping (A):** All 8 handlers in one PR with the shared dispatcher, following Phase 4's reference-pipeline pattern but without the RFI-only restriction — 8 is small enough to batch.
5. **Catalog flip:** Each action's `readiness_state` flips from `"alpha"` to `"live"` in `quick_actions_catalog.py` in the same PR.

## Architecture

### New module layout

```
backend/app/services/ai/actions/
  __init__.py
  base.py                      # ActionContext, ActionResult, QuickActionHandler
  rfi_aging.py
  submittal_sla.py
  budget_variance.py
  daily_log_summary.py
  critical_path_delays.py
  two_week_lookahead.py
  documentation_compliance.py
  my_day_briefing.py
backend/app/services/ai/action_dispatcher.py   # registry; maybe_execute(slug, ctx)
```

### Handler interface

```python
# backend/app/services/ai/actions/base.py
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID
import asyncpg
from app.schemas.assistant import AssistantUser

@dataclass
class ActionContext:
    conn: asyncpg.Connection
    user: AssistantUser            # carries user_id + role_keys
    project_id: UUID | None        # from page_context; None = portfolio mode
    params: dict[str, Any]

@dataclass
class ActionResult:
    stats: dict[str, Any]          # deterministic numbers the LLM can cite verbatim
    sample_rows: list[dict]        # representative rows, up to 10
    prompt_fragment: str           # pre-rendered markdown block, appended to system prompt

class QuickActionHandler(Protocol):
    slug: str
    async def run(self, ctx: ActionContext) -> ActionResult: ...
```

### Dispatcher

```python
# backend/app/services/ai/action_dispatcher.py
from app.services.ai.actions import (
    rfi_aging, submittal_sla, budget_variance, daily_log_summary,
    critical_path_delays, two_week_lookahead,
    documentation_compliance, my_day_briefing,
)

_HANDLERS: dict[str, QuickActionHandler] = {
    h.slug: h for h in [
        rfi_aging.Handler(),
        submittal_sla.Handler(),
        budget_variance.Handler(),
        daily_log_summary.Handler(),
        critical_path_delays.Handler(),
        two_week_lookahead.Handler(),
        documentation_compliance.Handler(),
        my_day_briefing.Handler(),
    ]
}

async def maybe_execute(slug: str | None, ctx: ActionContext) -> ActionResult | None:
    if not slug:
        return None
    handler = _HANDLERS.get(slug)
    if handler is None:
        return None
    try:
        return await handler.run(ctx)
    except Exception as e:
        log.exception("quick action %s failed", slug)
        return ActionResult(
            stats={},
            sample_rows=[],
            prompt_fragment=(
                f"[Quick action `{slug}` data temporarily unavailable. "
                "Answer the user's question using general chat instead.]"
            ),
        )
```

### Chat service integration

In `backend/app/services/ai/chat_service.py::stream_chat`, immediately before `ModelRequest` is built:

```python
action_result = None
if request.active_action_slug:
    # Acquire a pool connection scoped to this request only.
    async with self._pool.acquire() as conn:
        action_ctx = ActionContext(
            conn=conn,
            user=user,
            project_id=context.project_id,  # comes from request.page_context
            params=request.params or {},
        )
        action_result = await action_dispatcher.maybe_execute(
            request.active_action_slug, action_ctx
        )

system_prompt = context.system_prompt
if action_result is not None:
    system_prompt = system_prompt + "\n\n" + action_result.prompt_fragment
```

`ChatService.__init__` gains a `pool: asyncpg.Pool` dependency (the dispatcher already has the pool; pass it through).

### Catalog flip

In `backend/app/data/quick_actions_catalog.py`, change the 8 entries' third-to-last argument from `"alpha"` to `"live"`. No migration needed — the catalog is rebuilt from this Python module via `_build_catalog_migration.py`, which ships a SQL migration the normal way.

## Per-handler SQL sketches

These are the canonical shapes. Each handler MUST cap `sample_rows` at 10, MUST honor portfolio-vs-project scoping, MUST catch its own SQL errors (the dispatcher's outer try/except is defense-in-depth).

### rfi_aging

```sql
-- portfolio mode (ctx.project_id is None)
WITH scope AS (
    SELECT project_id
    FROM rex.v_user_project_assignments
    WHERE user_id = $1
)
SELECT
    project_id, project_name, rfi_number, subject,
    assignee_name AS ball_in_court,
    (CURRENT_DATE - due_date::date) AS days_open,
    due_date
FROM rex.v_project_mgmt
WHERE item_type = 'rfi'
  AND status = 'open'
  AND project_id IN (SELECT project_id FROM scope)
ORDER BY due_date ASC NULLS LAST
LIMIT 10;
```

Stats include `total_open`, `buckets = {"0_to_7": N, "8_to_14": N, "15_to_30": N, "30_plus": N}`, `oldest_days`.

### submittal_sla

Identical structure to `rfi_aging` but with `item_type = 'submittal'`. Different aging buckets aligned to submittal SLA norms (0-5 / 6-10 / 11-20 / 20+ working days).

### budget_variance

```sql
SELECT project_id, project_name,
       current_amount, baseline_amount,
       (current_amount - baseline_amount) AS delta_amount,
       CASE WHEN baseline_amount = 0 THEN NULL
            ELSE (current_amount - baseline_amount) / baseline_amount
       END AS delta_pct
FROM rex.v_financials
WHERE project_id IN (SELECT project_id FROM scope)
ORDER BY ABS(COALESCE(delta_pct, 0)) DESC
LIMIT 10;
```

Stats include `total_projects_over_5pct`, `worst_variance_pct`, `worst_project_name`, `total_portfolio_delta`.

### daily_log_summary

```sql
SELECT project_id, log_date, created_by, weather,
       SUM(headcount) OVER (PARTITION BY project_id, log_date) AS total_headcount,
       COUNT(DISTINCT trade) OVER (PARTITION BY project_id, log_date) AS trade_count
FROM rex.daily_logs dl
LEFT JOIN rex.manpower_logs ml ON ml.daily_log_id = dl.id
WHERE project_id IN (SELECT project_id FROM scope)
  AND log_date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY log_date DESC, project_id
LIMIT 10;
```

Stats include `logs_last_7_days`, `today_total_manpower`, `today_trades_on_site`, `projects_without_today_log`.

### critical_path_delays

```sql
SELECT project_id, project_name, task_name,
       start_date, finish_date, actual_finish_date,
       finish_variance_days
FROM rex.v_schedule
WHERE critical_path = TRUE
  AND project_id IN (SELECT project_id FROM scope)
  AND finish_variance_days > 2
ORDER BY finish_variance_days DESC
LIMIT 10;
```

Stats include `critical_tasks_delayed`, `worst_delay_days`, `projects_with_critical_delays`.

### two_week_lookahead

```sql
SELECT project_id, project_name, task_name,
       start_date, finish_date, assigned_to,
       percent_complete
FROM rex.v_schedule
WHERE start_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '14 days'
  AND project_id IN (SELECT project_id FROM scope)
ORDER BY start_date ASC, project_id
LIMIT 10;
```

Stats include `tasks_starting_next_14d`, `projects_with_starts`, `earliest_start_date`.

### documentation_compliance

```sql
SELECT project_id, project_name, doc_type, doc_name,
       approval_status, expiration_date,
       (expiration_date - CURRENT_DATE) AS days_to_expiry
FROM rex.v_documents
WHERE project_id IN (SELECT project_id FROM scope)
  AND (approval_status IN ('missing', 'pending') OR expiration_date < CURRENT_DATE + INTERVAL '30 days')
ORDER BY
    CASE WHEN approval_status = 'missing' THEN 0
         WHEN approval_status = 'pending' THEN 1
         ELSE 2 END,
    expiration_date ASC NULLS LAST
LIMIT 10;
```

Stats include `missing_approvals`, `expired`, `expiring_within_30d`.

### my_day_briefing

```sql
-- always user-scoped; project_id narrows within that
SELECT *
FROM rex.v_myday
WHERE user_id = $1
  AND ($2::uuid IS NULL OR project_id = $2::uuid)
ORDER BY due_date ASC NULLS LAST
LIMIT 10;
```

Stats include `due_today`, `overdue`, `assigned_to_me`. Sample rows include the 10 most urgent items across all types (RFIs, submittals, tasks, daily logs owed).

**Note on view-column assumptions:** each handler's SQL assumes specific columns on the `rex.v_*` views (e.g., `rex.v_project_mgmt.item_type`, `rex.v_schedule.critical_path`). Implementers MUST verify each view's actual schema in `migrations/022_canonical_read_views.sql` + `020_canonical_docs_quality_additions.sql` before writing the query. Column names in this spec are best-guess and subject to adjustment during implementation.

## Prompt fragment shape

Every handler emits a fragment matching this template (example for `rfi_aging`):

```
## Quick action data: rfi_aging

Scope: portfolio across 4 projects the user has access to

Summary:
- Total open RFIs: 23
- Aging: 12 (0-7 days), 4 (8-14 days), 3 (15-30 days), 4 (30+ days)
- Oldest: 19 days — Bishop Modern, RFI #42 ("Ceiling height at grid B/4")

Top 10 (oldest first):
| project | rfi_number | subject | ball_in_court | days_open |
| ... (up to 10 rows) |

Use these numbers verbatim in your response; do not recalculate them.
```

The "use these numbers verbatim" line is a hedge against LLM hallucination — tells the model to cite the stats rather than invent new ones.

## Testing strategy

### Per-handler unit tests (8 files)

`backend/tests/services/ai/actions/test_<slug>.py` for each handler:

- **Happy path (portfolio):** fixture inserts 3 projects with varied data via direct SQL into `rex.rfis` / `rex.schedule_tasks` / etc., no `project_id` in ctx, assert `stats.total_*` equals the seeded count, `sample_rows` length ≤ 10, `prompt_fragment` contains the expected stat strings.
- **Happy path (project-scoped):** same fixture, `project_id` set to one project, assert stats reflect only that project.
- **Empty result:** no seeded data, assert stats report zeros, `sample_rows == []`, `prompt_fragment` contains "no [resource] found" phrasing.
- **User access filtering:** seed data for two projects, create `rex.v_user_project_assignments` rows for only one, assert portfolio mode returns only the accessible project.

Each test file ~150 lines. Fixtures use raw asyncpg (per the pattern we established in Phase 4's `test_admin_sync_trigger.py` to avoid SQLAlchemy cross-loop issues when combined with the FastAPI test client).

### Dispatcher test

`backend/tests/services/ai/test_action_dispatcher.py`:
- Unknown slug → `None`.
- Empty slug → `None`.
- Known slug → handler invoked, returns `ActionResult`.
- Handler raises → dispatcher catches, returns sentinel "temporarily unavailable" fragment.

### Chat service integration test

`backend/tests/services/ai/test_chat_service_action_inject.py`:
- Mock `model_client` to capture the `system_prompt` it receives.
- POST chat with `active_action_slug='rfi_aging'` and seeded RFI data.
- Assert the captured `system_prompt` contains "Quick action data: rfi_aging" and the expected stat strings.
- Assert that with no `active_action_slug`, the system_prompt does NOT contain that header (no regression for free-form chat).

### Catalog regression test

Extend `backend/tests/test_quick_actions_catalog.py` (or add a new test file) with an assertion that these 8 slugs resolve to `readiness_state = 'live'` after the catalog rebuild.

## Error handling

| Failure                                   | Handler behavior                              | User impact                             |
| ----------------------------------------- | --------------------------------------------- | --------------------------------------- |
| View doesn't exist (`UndefinedTable`)     | Handler catches, logs, returns "unavailable" fragment | Chat continues as free-form           |
| Column missing (`UndefinedColumn`)        | Same as above                                 | Same                                    |
| SQL syntax / logic error                  | Same as above                                 | Same                                    |
| Empty result set                          | Handler returns valid `ActionResult` with zero stats and `no [resource] found` phrasing | User sees "You have no open RFIs" |
| User has no project assignments           | Handler returns valid `ActionResult` with zeros and prompt fragment noting "No projects accessible to this user" | User sees a helpful message |
| Dispatcher-level unhandled exception      | Outer try/except in `action_dispatcher.maybe_execute` returns "unavailable" fragment | Chat continues as free-form |
| `page_context.project_id` points at a project the user cannot access | Handler treats as portfolio mode (falls back to assignments query) | User sees their accessible projects, not the inaccessible one |

## File structure summary

**New:**
- `backend/app/services/ai/actions/__init__.py`
- `backend/app/services/ai/actions/base.py`
- `backend/app/services/ai/actions/rfi_aging.py`
- `backend/app/services/ai/actions/submittal_sla.py`
- `backend/app/services/ai/actions/budget_variance.py`
- `backend/app/services/ai/actions/daily_log_summary.py`
- `backend/app/services/ai/actions/critical_path_delays.py`
- `backend/app/services/ai/actions/two_week_lookahead.py`
- `backend/app/services/ai/actions/documentation_compliance.py`
- `backend/app/services/ai/actions/my_day_briefing.py`
- `backend/app/services/ai/action_dispatcher.py`
- `backend/tests/services/ai/actions/__init__.py`
- `backend/tests/services/ai/actions/test_rfi_aging.py` (+ 7 siblings, one per handler)
- `backend/tests/services/ai/test_action_dispatcher.py`
- `backend/tests/services/ai/test_chat_service_action_inject.py`

**Modified:**
- `backend/app/services/ai/chat_service.py` — inject action result into system prompt; constructor gains `pool`.
- `backend/app/services/ai/dispatcher.py` — pass `pool` into `ChatService` constructor.
- `backend/app/data/quick_actions_catalog.py` — flip 8 readiness states `alpha` → `live`.
- `backend/tests/test_quick_actions_catalog.py` — extend with live-state regression test.

## Success criteria

- All 8 actions produce real data when clicked. Andrew clicks "RFI aging" from the home page; assistant replies with real counts from `rex.v_project_mgmt`.
- Catalog's `can_run` remains correct (these 8 were already `can_run=True` since `alpha` counted; flipping to `live` keeps that).
- Free-form chat still works identically when no `active_action_slug` is set.
- Backend test suite stays green (767+ tests, zero regressions).
- Live smoke on demo: log in as aroberts, click each of the 8 actions in sequence from the sidebar, verify each response contains the action's stat block and references real project names.

## Not in this scope

- **No Decimal/date mapper work** — the existing `rex.v_*` views have been producing data for existing views already; type coercion is view-layer concern.
- **No new migrations** — this entire change is app-code.
- **No changes to `rex.v_*` views** — if a view is missing a column the spec assumes, implementers should ADJUST the handler to use what the view actually has, not amend the view. (If a column is genuinely missing from a canonical view, that's a separate discussion.)
- **No new admin HTTP routes** — the existing assistant chat endpoint is the only user-facing surface.
- **No frontend changes** — the sidebar already sends `active_action_slug`; we just start honoring it server-side.
