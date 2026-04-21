# Phase 5 Wave 1 — Alpha Quick Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the 8 alpha Wave 1 quick actions (`rfi_aging`, `submittal_sla`, `budget_variance`, `daily_log_summary`, `critical_path_delays`, `two_week_lookahead`, `documentation_compliance`, `my_day_briefing`) to real SQL against existing `rex.v_*` canonical views (and a couple of underlying tables where the rollup views don't expose row detail). Ship all 8 in one PR along with a shared dispatcher and catalog state flip from `"alpha"` to `"live"`.

**Architecture:** New module `backend/app/services/ai/actions/` contains one handler module per slug plus a shared `base.py` (`ActionContext`, `ActionResult`, `QuickActionHandler` Protocol). A sibling `action_dispatcher.py` holds the slug → handler registry and exposes `maybe_execute(slug, ctx) -> ActionResult | None`. The chat service, before building its `ModelRequest`, checks `active_action_slug`, invokes the dispatcher if set, and appends the handler's pre-rendered prompt fragment to the system prompt. SSE contract is unchanged; the LLM just gets a richer system prompt with deterministic counts it can cite verbatim.

**Tech Stack:** Python 3.11+, FastAPI, asyncpg, asyncio, pytest + pytest-asyncio. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-04-21-phase5-wave1-alpha-actions-design.md`

---

## Verified view / table shapes (use exactly these column names)

**`rex.v_project_mgmt`** (migration 022, lines 40-79):
- `entity_id uuid, entity_type text, project_id uuid, entity_number text, title text, status text, priority text, assigned_to_person_id uuid, ball_in_court_person_id uuid, due_date timestamptz, days_open int, created_at timestamptz, updated_at timestamptz`
- `entity_type` values: `'rfi' | 'submittal' | 'task' | 'punch_item' | 'pending_decision'`
- RFIs have `days_open` populated; submittals/tasks/pending_decisions have `NULL` for `days_open`.

**`rex.v_financials`** (migration 022, lines 87-119):
- `project_id uuid, project_name text, project_number text, project_status text, original_budget numeric, approved_changes numeric, revised_budget numeric, committed_costs numeric, direct_costs numeric, projected_cost numeric, budget_over_under numeric, commitment_count int, commitments_revised_value numeric, commitments_invoiced_to_date numeric, open_change_events int, open_change_events_amount numeric, open_pcos int, pay_apps_in_flight int, pay_apps_in_flight_amount numeric, lien_waivers_pending int`
- **Note:** there is no `baseline_amount` / `current_amount` / `delta_pct`. Compute variance pct in SQL: `(budget_over_under / NULLIF(revised_budget, 0))`.

**`rex.v_schedule`** (migration 022, lines 126-162):
- **Per-project rollup, not per-activity.** Columns: `project_id uuid, project_name text, total_activities int, critical_activities int, complete_activities int, in_progress_activities int, drifting_activities int, max_variance_days int, active_constraints int, active_delays int, critical_path_delays int, milestones_achieved int, milestones_overdue int, milestones_total int`.
- For per-activity drill-down (needed by `critical_path_delays` and `two_week_lookahead`), query `rex.schedule_activities` joined to `rex.schedules` (to get `project_id`).

**`rex.schedule_activities`** (rex2_canonical_ddl.sql lines 191-216):
- `id uuid, schedule_id uuid, activity_number text, name text, activity_type text, start_date date NOT NULL, end_date date NOT NULL, percent_complete numeric, is_critical boolean, baseline_start date, baseline_end date, variance_days int, float_days int, assigned_person_id uuid, created_at timestamptz, updated_at timestamptz`.
- To scope by project: `JOIN rex.schedules s ON s.id = sa.schedule_id WHERE s.project_id = ...`

**`rex.v_documents`** (migration 020, lines 123-136):
- **Bridge view over `rex.attachments`, NOT a compliance tracking view.** Columns: `id uuid, project_id uuid, related_entity_type text, related_entity_id uuid, filename text, file_size int, content_type text, storage_url text, storage_key text, uploaded_by uuid, created_at timestamptz`.
- No approval status, no expiration. **We redirect `documentation_compliance` to query `rex.v_closeout_items` instead — that's the view that actually tracks compliance status.**

**`rex.v_closeout_items`** (migration 020, lines 158-179):
- `id uuid, checklist_id uuid, project_id uuid, category text, item_number text, name text, status text, assigned_company_id uuid, assigned_person_id uuid, due_date date, completed_date date, completed_by uuid, notes text, sort_order int, spec_division text, spec_section text, created_at timestamptz, updated_at timestamptz`.

**`rex.v_myday`** (migration 022, lines 319-367):
- `user_account_id uuid, item_id uuid, item_type text, project_id uuid, title text, priority text, status text, due_date timestamptz, created_at timestamptz`.
- `item_type` values: `'rfi' | 'task' | 'pending_decision' | 'meeting_action_item'`.
- Parameterize by `user_account_id`, optionally by `project_id`.

**`rex.v_user_project_assignments`** (migration 010, lines 110-128):
- `id, user_account_id, project_id, project_name, project_number, project_status, role_template_id, access_level, is_primary_on_project, is_active, start_date, end_date, created_at`.
- Filter: `user_account_id = $1 AND is_active = true`.

**`rex.daily_logs`** (rex2_canonical_ddl.sql lines 267-286):
- `id uuid, project_id uuid, log_date date NOT NULL, status text, weather_summary text, temp_high_f int, temp_low_f int, is_weather_delay boolean, work_summary text, delay_notes text, safety_notes text, visitor_notes text, created_by uuid, approved_by uuid, approved_at timestamptz, created_at timestamptz, updated_at timestamptz`.
- Unique(`project_id`, `log_date`).

**`rex.manpower_entries`** (rex2_canonical_ddl.sql lines 289-298):
- **Named `manpower_entries`, not `manpower_logs`.** Columns: `id uuid, daily_log_id uuid, company_id uuid, worker_count int, hours numeric, description text, created_at timestamptz`.

---

## File structure

**New:**
- `backend/app/services/ai/actions/__init__.py` — empty, package marker.
- `backend/app/services/ai/actions/base.py` — `ActionContext`, `ActionResult`, `QuickActionHandler` Protocol, `resolve_scope_project_ids()` helper.
- `backend/app/services/ai/actions/rfi_aging.py`
- `backend/app/services/ai/actions/submittal_sla.py`
- `backend/app/services/ai/actions/budget_variance.py`
- `backend/app/services/ai/actions/daily_log_summary.py`
- `backend/app/services/ai/actions/critical_path_delays.py`
- `backend/app/services/ai/actions/two_week_lookahead.py`
- `backend/app/services/ai/actions/documentation_compliance.py`
- `backend/app/services/ai/actions/my_day_briefing.py`
- `backend/app/services/ai/action_dispatcher.py`
- `backend/tests/services/ai/__init__.py`
- `backend/tests/services/ai/actions/__init__.py`
- `backend/tests/services/ai/actions/test_base.py` — covers `resolve_scope_project_ids()`.
- `backend/tests/services/ai/actions/test_rfi_aging.py`
- `backend/tests/services/ai/actions/test_submittal_sla.py`
- `backend/tests/services/ai/actions/test_budget_variance.py`
- `backend/tests/services/ai/actions/test_daily_log_summary.py`
- `backend/tests/services/ai/actions/test_critical_path_delays.py`
- `backend/tests/services/ai/actions/test_two_week_lookahead.py`
- `backend/tests/services/ai/actions/test_documentation_compliance.py`
- `backend/tests/services/ai/actions/test_my_day_briefing.py`
- `backend/tests/services/ai/test_action_dispatcher.py`
- `backend/tests/services/ai/test_chat_service_action_inject.py`

**Modified:**
- `backend/app/services/ai/chat_service.py` — inject action result into system prompt before building `ModelRequest`; `ChatService.__init__` gains `pool: asyncpg.Pool`.
- `backend/app/services/ai/dispatcher.py` — pass `pool` into `ChatService(...)` during `build()`.
- `backend/app/data/quick_actions_catalog.py` — flip 8 readiness states from `"alpha"` to `"live"`.
- `backend/tests/test_quick_actions_catalog.py` — extend with a regression test asserting the 8 slugs are now `"live"`.

---

## Test fixture conventions

Per Phase 4's learning, tests that combine the FastAPI `client` fixture with SQLAlchemy async sessions hit event-loop mismatch on Linux CI. **Every test in this plan uses raw asyncpg** for test data seeding — open a connection from `asyncpg.connect(os.environ["DATABASE_URL"])` (after stripping the `postgresql+asyncpg://` prefix if present), do the DDL/inserts, close. Scope fixtures to `function` so each test has its own data and tears it down cleanly.

See `backend/tests/services/connectors/procore/test_admin_sync_trigger.py::_connect` for the helper pattern to reuse.

For the chat-service integration test (Task 13), mock the `ModelClient` to capture what `system_prompt` gets sent, so we can assert the prompt fragment was appended without actually calling an LLM.

---

### Task 1: Base types — `ActionContext`, `ActionResult`, handler protocol, scope resolver

**Files:**
- Create: `backend/app/services/ai/actions/__init__.py` (empty)
- Create: `backend/app/services/ai/actions/base.py`
- Create: `backend/tests/services/ai/__init__.py` (empty)
- Create: `backend/tests/services/ai/actions/__init__.py` (empty)
- Create: `backend/tests/services/ai/actions/test_base.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/ai/actions/test_base.py
"""Tests for app.services.connectors.ai.actions.base.

Covers ``resolve_scope_project_ids`` — returns a list of project UUIDs
a handler should filter by, given the incoming project_id (or None for
portfolio mode) and a user_account_id."""
from __future__ import annotations

import asyncio
import os
import ssl
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio

from app.services.ai.actions.base import resolve_scope_project_ids


def _raw_url() -> str:
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url[len("postgresql+asyncpg://"):]
    return url


async def _connect() -> asyncpg.Connection:
    url = _raw_url()
    use_ssl = (
        "railway.internal" not in url
        and "localhost" not in url
        and "127.0.0.1" not in url
    )
    ctx = None
    if use_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return await asyncpg.connect(url, ssl=ctx)


def _require_db():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")


@pytest_asyncio.fixture
async def two_projects_for_user():
    """Seed two projects and assign one of them to a freshly-created user.

    Yields ``(user_account_id, accessible_project_id, inaccessible_project_id)``.
    Cleans up on teardown.
    """
    _require_db()
    conn = await _connect()
    try:
        person_id = uuid4()
        user_id = uuid4()
        proj_a = uuid4()
        proj_b = uuid4()

        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email) "
            "VALUES ($1::uuid, 'Test', 'Scope', $2)",
            person_id, f"scope-{person_id}@test.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, is_active) "
            "VALUES ($1::uuid, $2::uuid, true)",
            user_id, person_id,
        )
        for pid, num in ((proj_a, "SCOPE-A"), (proj_b, "SCOPE-B")):
            await conn.execute(
                "INSERT INTO rex.projects (id, name, status, project_number) "
                "VALUES ($1::uuid, $2, 'active', $3)",
                pid, f"Scope Test {num}", num,
            )
        # Assign ONLY project A to the user.
        await conn.execute(
            "INSERT INTO rex.project_members "
            "(id, project_id, person_id, is_active, is_primary) "
            "VALUES (gen_random_uuid(), $1::uuid, $2::uuid, true, false)",
            proj_a, person_id,
        )

        yield user_id, proj_a, proj_b
    finally:
        await conn.execute(
            "DELETE FROM rex.project_members WHERE person_id = $1::uuid",
            person_id,
        )
        await conn.execute(
            "DELETE FROM rex.projects WHERE id IN ($1::uuid, $2::uuid)",
            proj_a, proj_b,
        )
        await conn.execute(
            "DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id,
        )
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_portfolio_mode_returns_only_assigned_projects(two_projects_for_user):
    user_id, proj_a, proj_b = two_projects_for_user
    conn = await _connect()
    try:
        ids = await resolve_scope_project_ids(
            conn, user_account_id=user_id, project_id=None,
        )
        assert proj_a in ids
        assert proj_b not in ids
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_project_mode_returns_single_project(two_projects_for_user):
    user_id, proj_a, _ = two_projects_for_user
    conn = await _connect()
    try:
        ids = await resolve_scope_project_ids(
            conn, user_account_id=user_id, project_id=proj_a,
        )
        assert ids == [proj_a]
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_user_with_no_assignments_returns_empty_list(two_projects_for_user):
    _, _, _ = two_projects_for_user
    lonely_user_id = uuid4()
    conn = await _connect()
    try:
        ids = await resolve_scope_project_ids(
            conn, user_account_id=lonely_user_id, project_id=None,
        )
        assert ids == []
    finally:
        await conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && py -m pytest tests/services/ai/actions/test_base.py -v`
Expected: FAIL with `ModuleNotFoundError: app.services.ai.actions.base`

- [ ] **Step 3: Create empty package markers**

```python
# backend/app/services/ai/actions/__init__.py
```

```python
# backend/tests/services/ai/__init__.py
```

```python
# backend/tests/services/ai/actions/__init__.py
```

Three empty files, each containing only the path comment. Pytest collection requires the init files to exist.

- [ ] **Step 4: Implement base.py**

```python
# backend/app/services/ai/actions/base.py
"""Shared types + helpers for quick-action handlers.

A handler is a plain object implementing ``QuickActionHandler``:
just a ``slug`` class attribute and an async ``run(ctx)`` method.
Handlers MUST NOT raise — they should catch their own DB errors and
return an ``ActionResult`` with a graceful ``prompt_fragment``. The
dispatcher wraps each call in its own try/except as defense-in-depth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

import asyncpg


@dataclass
class ActionContext:
    """Everything a handler needs to run.

    Attributes:
        conn: a live asyncpg connection the handler may use for reads.
            The caller (dispatcher) owns the connection's lifecycle.
        user_account_id: rex.user_accounts.id of the requester.
        project_id: optional project scope. If None, the handler runs
            in portfolio mode and should scope to the user's accessible
            projects via ``resolve_scope_project_ids``.
        params: arbitrary handler params from the chat request; most
            handlers ignore this today.
    """
    conn: asyncpg.Connection
    user_account_id: UUID
    project_id: UUID | None = None
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionResult:
    """What a handler returns.

    Attributes:
        stats: deterministic numbers the LLM should cite verbatim.
            e.g., ``{"total_open": 23, "oldest_days": 19}``.
        sample_rows: up to 10 representative rows for the markdown
            table in ``prompt_fragment``. Also exposed here for any
            future structured-return consumer.
        prompt_fragment: pre-rendered markdown block. Appended to the
            chat's system prompt as-is. MUST start with a
            ``## Quick action data: <slug>`` header for visual
            separation from the base prompt.
    """
    stats: dict[str, Any] = field(default_factory=dict)
    sample_rows: list[dict] = field(default_factory=list)
    prompt_fragment: str = ""


class QuickActionHandler(Protocol):
    """Handler contract. Each module under ``actions/`` exposes a
    ``Handler`` class implementing this protocol."""

    slug: str

    async def run(self, ctx: ActionContext) -> ActionResult:
        ...


async def resolve_scope_project_ids(
    conn: asyncpg.Connection,
    *,
    user_account_id: UUID,
    project_id: UUID | None,
) -> list[UUID]:
    """Resolve a handler's project-scope filter list.

    If ``project_id`` is given, returns ``[project_id]`` unconditionally
    — the caller upstream has already validated page-context access.
    If ``project_id`` is None, returns the active project_ids the user
    is assigned to via ``rex.v_user_project_assignments``.

    The dispatcher passes the result into handler SQL as an array
    parameter; handlers use ``WHERE project_id = ANY($N::uuid[])``.
    """
    if project_id is not None:
        return [project_id]

    rows = await conn.fetch(
        "SELECT project_id FROM rex.v_user_project_assignments "
        "WHERE user_account_id = $1::uuid AND is_active = true",
        user_account_id,
    )
    return [r["project_id"] for r in rows]


__all__ = [
    "ActionContext",
    "ActionResult",
    "QuickActionHandler",
    "resolve_scope_project_ids",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && py -m pytest tests/services/ai/actions/test_base.py -v`
Expected: all 3 tests PASS (or SKIPPED if `DATABASE_URL` isn't set).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai/actions/__init__.py \
        backend/app/services/ai/actions/base.py \
        backend/tests/services/ai/__init__.py \
        backend/tests/services/ai/actions/__init__.py \
        backend/tests/services/ai/actions/test_base.py
git commit -m "feat(ai): action handler base types + scope resolver"
```

---

### Task 2: `action_dispatcher.py` — registry + `maybe_execute` with error containment

**Files:**
- Create: `backend/app/services/ai/action_dispatcher.py`
- Test: `backend/tests/services/ai/test_action_dispatcher.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/ai/test_action_dispatcher.py
"""Tests for app.services.ai.action_dispatcher.

Dispatcher behavior:
- Empty/None slug returns None.
- Unknown slug returns None.
- Known slug invokes handler and returns its ActionResult.
- Handler that raises gets caught; dispatcher returns a sentinel
  ActionResult with a user-visible 'unavailable' prompt fragment.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.services.ai.action_dispatcher import (
    ActionDispatcher,
    maybe_execute as module_maybe_execute,
)
from app.services.ai.actions.base import ActionContext, ActionResult


class _StubHandler:
    slug = "stub_ok"

    async def run(self, ctx):
        return ActionResult(
            stats={"n": 7},
            sample_rows=[],
            prompt_fragment="## Quick action data: stub_ok\nok",
        )


class _RaiserHandler:
    slug = "stub_raise"

    async def run(self, ctx):
        raise RuntimeError("intentional")


def _make_ctx():
    return ActionContext(
        conn=None,  # handlers in this test don't touch the conn
        user_account_id=uuid4(),
    )


@pytest.mark.asyncio
async def test_none_slug_returns_none():
    d = ActionDispatcher(handlers=[_StubHandler()])
    assert await d.maybe_execute(None, _make_ctx()) is None


@pytest.mark.asyncio
async def test_empty_slug_returns_none():
    d = ActionDispatcher(handlers=[_StubHandler()])
    assert await d.maybe_execute("", _make_ctx()) is None


@pytest.mark.asyncio
async def test_unknown_slug_returns_none():
    d = ActionDispatcher(handlers=[_StubHandler()])
    assert await d.maybe_execute("not_a_real_slug", _make_ctx()) is None


@pytest.mark.asyncio
async def test_known_slug_invokes_handler():
    d = ActionDispatcher(handlers=[_StubHandler()])
    r = await d.maybe_execute("stub_ok", _make_ctx())
    assert r is not None
    assert r.stats == {"n": 7}
    assert "stub_ok" in r.prompt_fragment


@pytest.mark.asyncio
async def test_handler_raising_returns_fallback_fragment():
    d = ActionDispatcher(handlers=[_RaiserHandler()])
    r = await d.maybe_execute("stub_raise", _make_ctx())
    assert r is not None
    assert r.stats == {}
    assert r.sample_rows == []
    assert "temporarily unavailable" in r.prompt_fragment.lower()
    assert "stub_raise" in r.prompt_fragment


@pytest.mark.asyncio
async def test_module_default_has_all_eight_handlers():
    """Smoke check that the module-level default registry contains
    exactly the 8 alpha Wave 1 slugs once the handlers are wired in."""
    expected = {
        "rfi_aging", "submittal_sla", "budget_variance",
        "daily_log_summary", "critical_path_delays",
        "two_week_lookahead", "documentation_compliance",
        "my_day_briefing",
    }
    # module_maybe_execute is bound to the module's default registry.
    # Probe by registry introspection.
    from app.services.ai.action_dispatcher import _default_dispatcher
    got = set(_default_dispatcher.slugs())
    assert expected <= got, f"missing slugs: {expected - got}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && py -m pytest tests/services/ai/test_action_dispatcher.py -v`
Expected: FAIL with `ModuleNotFoundError: app.services.ai.action_dispatcher`

- [ ] **Step 3: Implement the dispatcher**

```python
# backend/app/services/ai/action_dispatcher.py
"""Quick-action dispatcher — resolves active_action_slug to a handler.

The chat service calls ``maybe_execute`` before building its model
request. If a handler matches, its result is appended to the system
prompt; otherwise the chat proceeds unchanged.

Handler errors are contained here — a handler that raises returns a
sentinel ``ActionResult`` with a graceful ``prompt_fragment``. The
chat flow is unaffected.

Handlers for the 8 alpha Wave 1 slugs are registered in
``_default_dispatcher`` at import time. Each handler is implemented
in a sibling module under ``actions/``.
"""

from __future__ import annotations

import logging

from app.services.ai.actions.base import (
    ActionContext,
    ActionResult,
    QuickActionHandler,
)
from app.services.ai.actions import (
    budget_variance,
    critical_path_delays,
    daily_log_summary,
    documentation_compliance,
    my_day_briefing,
    rfi_aging,
    submittal_sla,
    two_week_lookahead,
)

log = logging.getLogger("rex.ai.action_dispatcher")


class ActionDispatcher:
    """Slug → handler registry with error containment."""

    def __init__(self, handlers: list[QuickActionHandler]):
        self._by_slug: dict[str, QuickActionHandler] = {h.slug: h for h in handlers}

    def slugs(self) -> list[str]:
        return list(self._by_slug.keys())

    async def maybe_execute(
        self, slug: str | None, ctx: ActionContext
    ) -> ActionResult | None:
        if not slug:
            return None
        handler = self._by_slug.get(slug)
        if handler is None:
            return None
        try:
            return await handler.run(ctx)
        except Exception as e:  # noqa: BLE001
            log.exception("quick action %s failed: %s", slug, e)
            return ActionResult(
                stats={},
                sample_rows=[],
                prompt_fragment=(
                    f"## Quick action data: {slug}\n\n"
                    f"[Quick action `{slug}` data temporarily unavailable. "
                    "Answer the user's question using general chat instead.]\n"
                ),
            )


_default_dispatcher = ActionDispatcher(handlers=[
    rfi_aging.Handler(),
    submittal_sla.Handler(),
    budget_variance.Handler(),
    daily_log_summary.Handler(),
    critical_path_delays.Handler(),
    two_week_lookahead.Handler(),
    documentation_compliance.Handler(),
    my_day_briefing.Handler(),
])


async def maybe_execute(slug: str | None, ctx: ActionContext) -> ActionResult | None:
    """Module-level convenience wrapping the default dispatcher."""
    return await _default_dispatcher.maybe_execute(slug, ctx)


__all__ = ["ActionDispatcher", "maybe_execute"]
```

**IMPORTANT:** This imports 8 handler modules that don't exist yet. The test in Step 2 will fail with `ModuleNotFoundError` on those imports, not just on `app.services.ai.action_dispatcher`. That's expected — we'll create stub placeholder handlers first (Step 4) so the imports resolve, then replace them with real implementations in Tasks 4–11.

- [ ] **Step 4: Create 8 stub handler modules**

Create each of these 8 files. Each file has exactly this skeleton — the real SQL is filled in by Tasks 4–11. The stub returns an empty `ActionResult` so import-time chain works and the dispatcher tests pass.

For each of: `rfi_aging.py`, `submittal_sla.py`, `budget_variance.py`, `daily_log_summary.py`, `critical_path_delays.py`, `two_week_lookahead.py`, `documentation_compliance.py`, `my_day_briefing.py`

```python
# backend/app/services/ai/actions/<slug>.py
"""<slug> quick action handler.

STUB — real implementation lands in the task that owns this slug.
Returns an empty ActionResult so the dispatcher can register it and
other tests are unblocked. See plan Task <N> for the real SQL.
"""
from __future__ import annotations

from app.services.ai.actions.base import ActionContext, ActionResult


class Handler:
    slug = "<slug>"

    async def run(self, ctx: ActionContext) -> ActionResult:
        return ActionResult(
            stats={},
            sample_rows=[],
            prompt_fragment=(
                f"## Quick action data: {self.slug}\n\n"
                "[Not implemented yet.]\n"
            ),
        )


__all__ = ["Handler"]
```

Replace `<slug>` with the actual slug for each file.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && py -m pytest tests/services/ai/test_action_dispatcher.py -v`
Expected: all 6 tests PASS (including the "8 slugs in default registry" smoke).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai/action_dispatcher.py \
        backend/app/services/ai/actions/rfi_aging.py \
        backend/app/services/ai/actions/submittal_sla.py \
        backend/app/services/ai/actions/budget_variance.py \
        backend/app/services/ai/actions/daily_log_summary.py \
        backend/app/services/ai/actions/critical_path_delays.py \
        backend/app/services/ai/actions/two_week_lookahead.py \
        backend/app/services/ai/actions/documentation_compliance.py \
        backend/app/services/ai/actions/my_day_briefing.py \
        backend/tests/services/ai/test_action_dispatcher.py
git commit -m "feat(ai): action dispatcher with 8 stub handlers for Wave 1"
```

---

### Task 3: Chat service integration — inject `prompt_fragment` into system prompt

**Files:**
- Modify: `backend/app/services/ai/chat_service.py`
- Modify: `backend/app/services/ai/dispatcher.py`
- Test: `backend/tests/services/ai/test_chat_service_action_inject.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/ai/test_chat_service_action_inject.py
"""Chat-service prompt-injection contract.

When a chat request carries ``active_action_slug`` matching a handler,
the chat service must invoke the dispatcher before building its
ModelRequest and append the handler's prompt_fragment to the system
prompt.

We verify this by mocking the model client so it captures what
system_prompt it was called with.
"""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.services.ai.action_dispatcher import ActionDispatcher
from app.services.ai.actions.base import ActionContext, ActionResult
from app.services.ai.chat_service import ChatService
from app.schemas.assistant import AssistantChatRequest, AssistantUser


class _FakePoolAcquireCtx:
    def __init__(self, conn):
        self._conn = conn
    async def __aenter__(self):
        return self._conn
    async def __aexit__(self, *_a):
        return None


class _FakePool:
    def __init__(self, conn):
        self._conn = conn
    def acquire(self):
        return _FakePoolAcquireCtx(self._conn)


class _CaptureHandler:
    slug = "rfi_aging"
    def __init__(self):
        self.called_with = None
    async def run(self, ctx):
        self.called_with = ctx
        return ActionResult(
            stats={"total_open": 23, "oldest_days": 19},
            sample_rows=[],
            prompt_fragment=(
                "## Quick action data: rfi_aging\n\n"
                "Total open RFIs: 23\nOldest: 19 days\n"
            ),
        )


@pytest.mark.asyncio
async def test_chat_service_appends_prompt_fragment_when_slug_present():
    captured = {}

    async def fake_stream(model_request):
        captured["system_prompt"] = model_request.system_prompt
        async def gen():
            yield "ok"
        return gen()

    model_client = MagicMock()
    model_client.model_key = "test-mock"
    model_client.stream_completion = AsyncMock(side_effect=fake_stream)

    chat_repo = MagicMock()
    chat_repo.get_or_create_conversation = AsyncMock(return_value={"id": uuid4()})
    chat_repo.append_message = AsyncMock(return_value={"id": uuid4()})
    chat_repo.list_messages = AsyncMock(return_value=[])

    handler = _CaptureHandler()
    dispatcher = ActionDispatcher(handlers=[handler])

    followup = MagicMock()
    followup.build = MagicMock(return_value=[])

    pool = _FakePool(conn=MagicMock())

    svc = ChatService(
        chat_repo=chat_repo,
        model_client=model_client,
        followup_generator=followup,
        pool=pool,
        action_dispatcher=dispatcher,
    )

    request = AssistantChatRequest(
        message="Show me RFI aging",
        active_action_slug="rfi_aging",
        params={},
        conversation_id=None,
        project_id=None,
        page_context=None,
        mode="chat",
    )
    user = AssistantUser(
        user_id=uuid4(), email="t@t.com", full_name="Test",
        role_keys=[], legacy_role=None,
    )

    @dataclass
    class _Ctx:
        system_prompt: str = "base system prompt"
        project_id: UUID | None = None

    # Drain the stream so stream_completion is actually invoked.
    async for _chunk in svc.stream_chat(request=request, user=user, context=_Ctx()):
        pass

    assert "system_prompt" in captured, "model_client was not invoked"
    sp = captured["system_prompt"]
    assert "base system prompt" in sp
    assert "Quick action data: rfi_aging" in sp
    assert "Total open RFIs: 23" in sp


@pytest.mark.asyncio
async def test_chat_service_does_not_append_when_no_slug():
    captured = {}

    async def fake_stream(model_request):
        captured["system_prompt"] = model_request.system_prompt
        async def gen():
            yield "ok"
        return gen()

    model_client = MagicMock()
    model_client.model_key = "test-mock"
    model_client.stream_completion = AsyncMock(side_effect=fake_stream)

    chat_repo = MagicMock()
    chat_repo.get_or_create_conversation = AsyncMock(return_value={"id": uuid4()})
    chat_repo.append_message = AsyncMock(return_value={"id": uuid4()})
    chat_repo.list_messages = AsyncMock(return_value=[])

    dispatcher = ActionDispatcher(handlers=[_CaptureHandler()])
    pool = _FakePool(conn=MagicMock())

    followup = MagicMock()
    followup.build = MagicMock(return_value=[])

    svc = ChatService(
        chat_repo=chat_repo,
        model_client=model_client,
        followup_generator=followup,
        pool=pool,
        action_dispatcher=dispatcher,
    )

    request = AssistantChatRequest(
        message="hi",
        active_action_slug=None,
        params={},
        conversation_id=None,
        project_id=None,
        page_context=None,
        mode="chat",
    )
    user = AssistantUser(
        user_id=uuid4(), email="t@t.com", full_name="Test",
        role_keys=[], legacy_role=None,
    )

    @dataclass
    class _Ctx:
        system_prompt: str = "base system prompt"
        project_id: UUID | None = None

    async for _ in svc.stream_chat(request=request, user=user, context=_Ctx()):
        pass

    assert captured["system_prompt"] == "base system prompt"
    assert "Quick action data" not in captured["system_prompt"]
```

**Note to implementer:** The exact signature of `ChatService.stream_chat` and the shape of its `context` argument are defined in the current chat_service.py. Read it first (`backend/app/services/ai/chat_service.py`) to confirm field names. The test above assumes `context.system_prompt` and `context.project_id` — if the real class uses different names, adjust both the test and the implementation together.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && py -m pytest tests/services/ai/test_chat_service_action_inject.py -v`
Expected: FAIL — `ChatService.__init__` doesn't yet accept `pool` or `action_dispatcher`.

- [ ] **Step 3: Modify ChatService constructor + stream_chat**

Open `backend/app/services/ai/chat_service.py`. Add two new constructor params (`pool`, `action_dispatcher`) with sensible defaults so existing call sites don't break:

```python
# near the top of ChatService.__init__ (add parameters + assignments)
from app.services.ai.action_dispatcher import ActionDispatcher, _default_dispatcher
import asyncpg

class ChatService:
    def __init__(
        self,
        *,
        chat_repo: "ChatRepository",
        model_client: "ModelClient",
        followup_generator: "FollowupGenerator",
        pool: "asyncpg.Pool | None" = None,
        action_dispatcher: "ActionDispatcher | None" = None,
    ):
        self._chat_repo = chat_repo
        self._model = model_client
        self._followup = followup_generator
        self._pool = pool
        self._action_dispatcher = action_dispatcher or _default_dispatcher
```

Inside `stream_chat`, immediately before the `ModelRequest` is built (search for `ModelRequest(` in chat_service.py and insert this block just before it):

```python
        # Quick-action prompt injection.
        action_fragment = ""
        if request.active_action_slug and self._pool is not None:
            from app.services.ai.actions.base import ActionContext
            async with self._pool.acquire() as _conn:
                action_ctx = ActionContext(
                    conn=_conn,
                    user_account_id=user.user_id,
                    project_id=getattr(context, "project_id", None),
                    params=dict(request.params or {}),
                )
                action_result = await self._action_dispatcher.maybe_execute(
                    request.active_action_slug, action_ctx,
                )
            if action_result is not None:
                action_fragment = "\n\n" + action_result.prompt_fragment

        effective_system_prompt = context.system_prompt + action_fragment
```

Then replace the existing `system_prompt=context.system_prompt` argument to `ModelRequest(...)` with `system_prompt=effective_system_prompt`, and similarly for the system `ModelMessage(role="system", content=...)` — use `effective_system_prompt` in both places.

- [ ] **Step 4: Update the AssistantDispatcher to pass the pool**

Open `backend/app/services/ai/dispatcher.py`. Find the `ChatService(...)` instantiation in `build()` and add `pool=pool`:

```python
        instance.chat_service = ChatService(
            chat_repo=chat_repo,
            model_client=model_client,
            followup_generator=instance.followup_generator,
            pool=pool,
        )
```

(`action_dispatcher` is left unset so the default module-level dispatcher is used automatically.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && py -m pytest tests/services/ai/test_chat_service_action_inject.py -v`
Expected: both tests PASS.

Also spot-check that existing assistant tests still pass:

```
cd backend && py -m pytest tests/test_assistant_router_contract.py tests/test_assistant_live_db_smoke.py -v
```

Expected: all previously-passing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai/chat_service.py \
        backend/app/services/ai/dispatcher.py \
        backend/tests/services/ai/test_chat_service_action_inject.py
git commit -m "feat(ai): chat_service injects quick-action prompt fragment when slug set"
```

---

## Handler task template (Tasks 4–11 follow this shape)

Each handler task has six steps:

1. Write the failing test (unit test with direct DB fixtures, function-scoped asyncpg connection, seeds minimal data, asserts stats + prompt_fragment content).
2. Run test → FAIL (the stub handler returns empty).
3. Replace the stub handler with the real implementation in `backend/app/services/ai/actions/<slug>.py`.
4. Run test → PASS.
5. Spot-check: `py -m pytest tests/services/ai/ -v` — all prior tests still green, plus the new handler's tests.
6. Commit.

Every handler returns an `ActionResult` with:
- `stats`: a flat dict of the deterministic numbers (counts, buckets, extremes).
- `sample_rows`: ≤ 10 rows from a LIMIT-10 query (empty list when no matches).
- `prompt_fragment`: a markdown block starting with `## Quick action data: <slug>`, then a human-readable summary, then a markdown table, then the literal line `Use these numbers verbatim in your response; do not recalculate them.`

The helper `_render_fragment(slug, scope_label, stats_lines, rows)` (defined once in the first handler we implement — `rfi_aging` — and reused by the others) keeps formatting DRY. Subsequent handler tasks import it from `rfi_aging` to avoid a shared helpers module until there's a second consumer that genuinely needs one.

**Actually — promote `_render_fragment` to `base.py` in Task 4's implementation.** All 8 handlers use the same template; putting the helper in `base.py` from the start avoids the cross-module import. Task 4's step 3 is where this code lands.

---

### Task 4: `rfi_aging` — open RFIs with aging buckets

**Files:**
- Modify: `backend/app/services/ai/actions/base.py` (add `_render_fragment` helper)
- Modify: `backend/app/services/ai/actions/rfi_aging.py`
- Test: `backend/tests/services/ai/actions/test_rfi_aging.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/ai/actions/test_rfi_aging.py
"""rfi_aging handler — reads from rex.v_project_mgmt where entity_type='rfi'."""
from __future__ import annotations

import os
import ssl
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio

from app.services.ai.actions.base import ActionContext
from app.services.ai.actions.rfi_aging import Handler


def _raw_url() -> str:
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url[len("postgresql+asyncpg://"):]
    return url


async def _connect() -> asyncpg.Connection:
    url = _raw_url()
    use_ssl = (
        "railway.internal" not in url
        and "localhost" not in url
        and "127.0.0.1" not in url
    )
    ctx = None
    if use_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return await asyncpg.connect(url, ssl=ctx)


def _require_db():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")


@pytest_asyncio.fixture
async def seeded_rfis():
    """Seed 1 user, 1 person, 1 project, 4 RFIs with varying days_open,
    1 closed RFI (should be ignored). Yields
    ``(user_account_id, project_id, rfi_ids)``."""
    _require_db()
    conn = await _connect()
    user_id = uuid4()
    person_id = uuid4()
    project_id = uuid4()
    rfi_ids: list[UUID] = []
    try:
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email) "
            "VALUES ($1::uuid, 'Aging', 'Tester', $2)",
            person_id, f"aging-{person_id}@test.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, is_active) "
            "VALUES ($1::uuid, $2::uuid, true)",
            user_id, person_id,
        )
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'Aging Test', 'active', 'AGE-1')",
            project_id,
        )
        await conn.execute(
            "INSERT INTO rex.project_members "
            "(id, project_id, person_id, is_active, is_primary) "
            "VALUES (gen_random_uuid(), $1::uuid, $2::uuid, true, false)",
            project_id, person_id,
        )
        # 4 open RFIs with varying days_open (3, 10, 20, 40) + 1 closed.
        now = datetime.now(timezone.utc)
        for days_open, subject in [
            (3,  "Fresh"),
            (10, "Ten-day"),
            (20, "Twenty-day"),
            (40, "Forty-day"),
        ]:
            rid = uuid4()
            rfi_ids.append(rid)
            await conn.execute(
                "INSERT INTO rex.rfis "
                "(id, project_id, rfi_number, subject, question, status, days_open, created_at, updated_at) "
                "VALUES ($1::uuid, $2::uuid, $3, $4, 'q', 'open', $5, $6, $6)",
                rid, project_id, f"RFI-{days_open}", subject,
                days_open, now - timedelta(days=days_open),
            )
        # Closed RFI — should NOT be counted.
        cid = uuid4()
        await conn.execute(
            "INSERT INTO rex.rfis "
            "(id, project_id, rfi_number, subject, question, status, days_open, created_at, updated_at) "
            "VALUES ($1::uuid, $2::uuid, 'RFI-CLOSED', 'Closed one', 'q', 'closed', 99, $3, $3)",
            cid, project_id, now,
        )
        rfi_ids.append(cid)

        yield user_id, project_id, rfi_ids
    finally:
        await conn.execute("DELETE FROM rex.rfis WHERE project_id = $1::uuid", project_id)
        await conn.execute(
            "DELETE FROM rex.project_members WHERE project_id = $1::uuid",
            project_id,
        )
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", project_id)
        await conn.execute(
            "DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id,
        )
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_rfi_aging_portfolio_mode(seeded_rfis):
    user_id, project_id, _ = seeded_rfis
    conn = await _connect()
    try:
        result = await Handler().run(ActionContext(
            conn=conn, user_account_id=user_id, project_id=None,
        ))
        # 4 open RFIs total.
        assert result.stats["total_open"] == 4
        # Bucket breakdown: 0-7 = 1, 8-14 = 1, 15-30 = 1, 30+ = 1.
        buckets = result.stats["buckets"]
        assert buckets["0_to_7"] == 1
        assert buckets["8_to_14"] == 1
        assert buckets["15_to_30"] == 1
        assert buckets["30_plus"] == 1
        # Oldest is 40 days.
        assert result.stats["oldest_days"] == 40
        # Sample rows are ordered oldest-first; max 10.
        assert len(result.sample_rows) <= 10
        assert len(result.sample_rows) == 4
        assert result.sample_rows[0]["days_open"] == 40
        # Prompt fragment contains the stat block and a "Use these numbers verbatim" hint.
        assert "Quick action data: rfi_aging" in result.prompt_fragment
        assert "Total open RFIs: 4" in result.prompt_fragment
        assert "verbatim" in result.prompt_fragment.lower()
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_rfi_aging_project_mode_restricts_to_project(seeded_rfis):
    user_id, project_id, _ = seeded_rfis
    conn = await _connect()
    try:
        result = await Handler().run(ActionContext(
            conn=conn, user_account_id=user_id, project_id=project_id,
        ))
        assert result.stats["total_open"] == 4  # single-project seed anyway
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_rfi_aging_empty_result(seeded_rfis):
    user_id, project_id, _ = seeded_rfis
    conn = await _connect()
    try:
        # Close all RFIs first
        await conn.execute(
            "UPDATE rex.rfis SET status = 'closed' WHERE project_id = $1::uuid",
            project_id,
        )
        result = await Handler().run(ActionContext(
            conn=conn, user_account_id=user_id, project_id=None,
        ))
        assert result.stats["total_open"] == 0
        assert result.sample_rows == []
        assert "no open RFIs" in result.prompt_fragment.lower()
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_rfi_aging_user_without_assignments_returns_empty(seeded_rfis):
    _, project_id, _ = seeded_rfis
    lonely_user = uuid4()
    conn = await _connect()
    try:
        result = await Handler().run(ActionContext(
            conn=conn, user_account_id=lonely_user, project_id=None,
        ))
        assert result.stats["total_open"] == 0
        assert "no open RFIs" in result.prompt_fragment.lower()
    finally:
        await conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && py -m pytest tests/services/ai/actions/test_rfi_aging.py -v`
Expected: FAIL — stub handler returns empty stats, test asserts `total_open == 4`.

- [ ] **Step 3: Add `_render_fragment` helper to base.py**

Append to `backend/app/services/ai/actions/base.py` (keep everything already in the file):

```python
def _render_fragment(
    *,
    slug: str,
    scope_label: str,
    summary_lines: list[str],
    table_header: list[str],
    rows: list[dict],
    empty_message: str,
) -> str:
    """Render the standard prompt_fragment template.

    Layout:

        ## Quick action data: <slug>

        Scope: <scope_label>

        Summary:
        - <line 1>
        - <line 2>
        ...

        Top rows:
        | col | col | col |
        | --- | --- | --- |
        | v | v | v |

        Use these numbers verbatim in your response; do not recalculate them.

    When rows is empty, replaces the table with ``empty_message`` (e.g.
    ``"You have no open RFIs in the selected scope."``).
    """
    parts = [
        f"## Quick action data: {slug}",
        "",
        f"Scope: {scope_label}",
        "",
        "Summary:",
        *[f"- {line}" for line in summary_lines],
        "",
    ]
    if rows:
        header_line = "| " + " | ".join(table_header) + " |"
        sep_line = "| " + " | ".join("---" for _ in table_header) + " |"
        body_lines = []
        for r in rows:
            body_lines.append(
                "| " + " | ".join(str(r.get(h, "")) for h in table_header) + " |"
            )
        parts.extend(["Top rows:", header_line, sep_line, *body_lines, ""])
    else:
        parts.extend([empty_message, ""])

    parts.append("Use these numbers verbatim in your response; do not recalculate them.")
    return "\n".join(parts)
```

Add `_render_fragment` to the file's `__all__` list.

- [ ] **Step 4: Implement `rfi_aging.py`**

```python
# backend/app/services/ai/actions/rfi_aging.py
"""rfi_aging — open RFIs with aging buckets.

Reads rex.v_project_mgmt filtered to entity_type='rfi' and status='open'.
Aging buckets are computed from days_open:
  0-7, 8-14, 15-30, 30+.
Sample rows are the 10 oldest open RFIs (days_open DESC).
"""
from __future__ import annotations

from app.services.ai.actions.base import (
    ActionContext,
    ActionResult,
    resolve_scope_project_ids,
    _render_fragment,
)


class Handler:
    slug = "rfi_aging"

    async def run(self, ctx: ActionContext) -> ActionResult:
        project_ids = await resolve_scope_project_ids(
            ctx.conn,
            user_account_id=ctx.user_account_id,
            project_id=ctx.project_id,
        )
        if not project_ids:
            return ActionResult(
                stats={"total_open": 0, "buckets": {"0_to_7": 0, "8_to_14": 0, "15_to_30": 0, "30_plus": 0}, "oldest_days": None},
                sample_rows=[],
                prompt_fragment=_render_fragment(
                    slug=self.slug,
                    scope_label=self._scope_label(ctx, 0),
                    summary_lines=["Total open RFIs: 0"],
                    table_header=[],
                    rows=[],
                    empty_message="You have no open RFIs in the selected scope.",
                ),
            )

        buckets_row = await ctx.conn.fetchrow(
            """
            SELECT
                COUNT(*)                                                   AS total_open,
                COUNT(*) FILTER (WHERE days_open BETWEEN 0 AND 7)          AS b_0_7,
                COUNT(*) FILTER (WHERE days_open BETWEEN 8 AND 14)         AS b_8_14,
                COUNT(*) FILTER (WHERE days_open BETWEEN 15 AND 30)        AS b_15_30,
                COUNT(*) FILTER (WHERE days_open > 30)                     AS b_30_plus,
                MAX(days_open)                                             AS oldest_days
            FROM rex.v_project_mgmt
            WHERE entity_type = 'rfi'
              AND status = 'open'
              AND project_id = ANY($1::uuid[])
            """,
            project_ids,
        )

        total = int(buckets_row["total_open"] or 0)

        if total == 0:
            return ActionResult(
                stats={
                    "total_open": 0,
                    "buckets": {"0_to_7": 0, "8_to_14": 0, "15_to_30": 0, "30_plus": 0},
                    "oldest_days": None,
                },
                sample_rows=[],
                prompt_fragment=_render_fragment(
                    slug=self.slug,
                    scope_label=self._scope_label(ctx, len(project_ids)),
                    summary_lines=["Total open RFIs: 0"],
                    table_header=[],
                    rows=[],
                    empty_message="You have no open RFIs in the selected scope.",
                ),
            )

        sample_q = await ctx.conn.fetch(
            """
            SELECT
                pm.entity_number              AS rfi_number,
                pm.title                      AS subject,
                COALESCE(pm.days_open, 0)     AS days_open,
                p.name                        AS project_name
            FROM rex.v_project_mgmt pm
            JOIN rex.projects p ON p.id = pm.project_id
            WHERE pm.entity_type = 'rfi'
              AND pm.status = 'open'
              AND pm.project_id = ANY($1::uuid[])
            ORDER BY pm.days_open DESC NULLS LAST, pm.due_date ASC NULLS LAST
            LIMIT 10
            """,
            project_ids,
        )
        sample_rows = [dict(r) for r in sample_q]

        stats = {
            "total_open": total,
            "buckets": {
                "0_to_7":  int(buckets_row["b_0_7"] or 0),
                "8_to_14": int(buckets_row["b_8_14"] or 0),
                "15_to_30": int(buckets_row["b_15_30"] or 0),
                "30_plus": int(buckets_row["b_30_plus"] or 0),
            },
            "oldest_days": int(buckets_row["oldest_days"] or 0),
        }

        summary = [
            f"Total open RFIs: {total}",
            f"Aging: {stats['buckets']['0_to_7']} (0-7d), "
            f"{stats['buckets']['8_to_14']} (8-14d), "
            f"{stats['buckets']['15_to_30']} (15-30d), "
            f"{stats['buckets']['30_plus']} (30+d)",
            f"Oldest: {stats['oldest_days']} days",
        ]

        return ActionResult(
            stats=stats,
            sample_rows=sample_rows,
            prompt_fragment=_render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, len(project_ids)),
                summary_lines=summary,
                table_header=["project_name", "rfi_number", "subject", "days_open"],
                rows=sample_rows,
                empty_message="You have no open RFIs in the selected scope.",
            ),
        )

    @staticmethod
    def _scope_label(ctx: ActionContext, n_projects: int) -> str:
        if ctx.project_id is not None:
            return "single project (page scope)"
        return f"portfolio across {n_projects} projects the user has access to"


__all__ = ["Handler"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && py -m pytest tests/services/ai/actions/test_rfi_aging.py tests/services/ai/actions/test_base.py tests/services/ai/test_action_dispatcher.py -v`
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai/actions/base.py \
        backend/app/services/ai/actions/rfi_aging.py \
        backend/tests/services/ai/actions/test_rfi_aging.py
git commit -m "feat(ai): rfi_aging handler reads rex.v_project_mgmt with aging buckets"
```

---

### Task 5: `submittal_sla`

Same pattern as Task 4 but `entity_type = 'submittal'`. Submittals have `NULL` `days_open` in `rex.v_project_mgmt`, so the handler computes days since `created_at` instead.

**Files:**
- Modify: `backend/app/services/ai/actions/submittal_sla.py` (replace stub)
- Test: `backend/tests/services/ai/actions/test_submittal_sla.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/ai/actions/test_submittal_sla.py
"""submittal_sla handler — open submittals with SLA-aging buckets.

rex.v_project_mgmt has days_open=NULL for submittals; the handler
derives days_since_created from v_project_mgmt.created_at.
"""
from __future__ import annotations

import os
import ssl
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio

from app.services.ai.actions.base import ActionContext
from app.services.ai.actions.submittal_sla import Handler


def _raw_url() -> str:
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url[len("postgresql+asyncpg://"):]
    return url


async def _connect() -> asyncpg.Connection:
    url = _raw_url()
    use_ssl = (
        "railway.internal" not in url
        and "localhost" not in url
        and "127.0.0.1" not in url
    )
    ctx = None
    if use_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return await asyncpg.connect(url, ssl=ctx)


def _require_db():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")


@pytest_asyncio.fixture
async def seeded_submittals():
    _require_db()
    conn = await _connect()
    user_id = uuid4()
    person_id = uuid4()
    project_id = uuid4()
    try:
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email) "
            "VALUES ($1::uuid, 'Sub', 'Tester', $2)",
            person_id, f"sub-{person_id}@test.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, is_active) "
            "VALUES ($1::uuid, $2::uuid, true)",
            user_id, person_id,
        )
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'Submittal Test', 'active', 'SUB-1')",
            project_id,
        )
        await conn.execute(
            "INSERT INTO rex.project_members "
            "(id, project_id, person_id, is_active, is_primary) "
            "VALUES (gen_random_uuid(), $1::uuid, $2::uuid, true, false)",
            project_id, person_id,
        )
        now = datetime.now(timezone.utc)
        for days_ago, num, status in [
            (2,  "S-1", "open"),
            (12, "S-2", "open"),
            (25, "S-3", "open"),
            (40, "S-4", "open"),
            (5,  "S-5", "closed"),  # should be ignored
        ]:
            await conn.execute(
                "INSERT INTO rex.submittals "
                "(id, project_id, submittal_number, title, status, created_at, updated_at) "
                "VALUES (gen_random_uuid(), $1::uuid, $2, 'Title', $3, $4, $4)",
                project_id, num, status, now - timedelta(days=days_ago),
            )
        yield user_id, project_id
    finally:
        await conn.execute("DELETE FROM rex.submittals WHERE project_id = $1::uuid", project_id)
        await conn.execute(
            "DELETE FROM rex.project_members WHERE project_id = $1::uuid", project_id,
        )
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", project_id)
        await conn.execute(
            "DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id,
        )
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_submittal_sla_portfolio_mode(seeded_submittals):
    user_id, _ = seeded_submittals
    conn = await _connect()
    try:
        r = await Handler().run(ActionContext(
            conn=conn, user_account_id=user_id, project_id=None,
        ))
        assert r.stats["total_open"] == 4
        # Buckets 0-5/6-10/11-20/20+ (SLA norms).
        buckets = r.stats["buckets"]
        assert buckets["0_to_5"] == 1   # 2 days
        assert buckets["6_to_10"] == 0
        assert buckets["11_to_20"] == 1 # 12 days
        assert buckets["21_plus"] == 2  # 25 and 40
        assert r.stats["oldest_days"] == 40
        assert len(r.sample_rows) == 4
        assert r.sample_rows[0]["days_since_created"] == 40
        assert "Quick action data: submittal_sla" in r.prompt_fragment
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_submittal_sla_empty(seeded_submittals):
    user_id, project_id = seeded_submittals
    conn = await _connect()
    try:
        await conn.execute("UPDATE rex.submittals SET status = 'closed' WHERE project_id = $1::uuid", project_id)
        r = await Handler().run(ActionContext(
            conn=conn, user_account_id=user_id, project_id=None,
        ))
        assert r.stats["total_open"] == 0
        assert "no open submittals" in r.prompt_fragment.lower()
    finally:
        await conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && py -m pytest tests/services/ai/actions/test_submittal_sla.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `submittal_sla.py`**

```python
# backend/app/services/ai/actions/submittal_sla.py
"""submittal_sla — open submittals with SLA-aging buckets.

rex.v_project_mgmt surfaces submittals with days_open=NULL, so we
compute days_since_created from v_project_mgmt.created_at at query time.
SLA buckets: 0-5, 6-10, 11-20, 21+ working-ish days (calendar days
for MVP; swap to business-day math later if needed).
"""
from __future__ import annotations

from app.services.ai.actions.base import (
    ActionContext,
    ActionResult,
    resolve_scope_project_ids,
    _render_fragment,
)


class Handler:
    slug = "submittal_sla"

    async def run(self, ctx: ActionContext) -> ActionResult:
        project_ids = await resolve_scope_project_ids(
            ctx.conn, user_account_id=ctx.user_account_id, project_id=ctx.project_id,
        )
        empty_stats = {
            "total_open": 0,
            "buckets": {"0_to_5": 0, "6_to_10": 0, "11_to_20": 0, "21_plus": 0},
            "oldest_days": None,
        }
        if not project_ids:
            return self._empty(ctx, 0, empty_stats)

        row = await ctx.conn.fetchrow(
            """
            WITH base AS (
                SELECT
                    pm.*,
                    EXTRACT(DAY FROM now() - pm.created_at)::int AS days_since_created
                FROM rex.v_project_mgmt pm
                WHERE pm.entity_type = 'submittal'
                  AND pm.status = 'open'
                  AND pm.project_id = ANY($1::uuid[])
            )
            SELECT
                COUNT(*)                                                     AS total_open,
                COUNT(*) FILTER (WHERE days_since_created BETWEEN 0 AND 5)   AS b_0_5,
                COUNT(*) FILTER (WHERE days_since_created BETWEEN 6 AND 10)  AS b_6_10,
                COUNT(*) FILTER (WHERE days_since_created BETWEEN 11 AND 20) AS b_11_20,
                COUNT(*) FILTER (WHERE days_since_created > 20)              AS b_21_plus,
                MAX(days_since_created)                                      AS oldest_days
            FROM base
            """,
            project_ids,
        )
        total = int(row["total_open"] or 0)
        if total == 0:
            return self._empty(ctx, len(project_ids), empty_stats)

        sample = await ctx.conn.fetch(
            """
            SELECT
                pm.entity_number              AS submittal_number,
                pm.title                      AS title,
                EXTRACT(DAY FROM now() - pm.created_at)::int AS days_since_created,
                p.name                        AS project_name
            FROM rex.v_project_mgmt pm
            JOIN rex.projects p ON p.id = pm.project_id
            WHERE pm.entity_type = 'submittal'
              AND pm.status = 'open'
              AND pm.project_id = ANY($1::uuid[])
            ORDER BY pm.created_at ASC
            LIMIT 10
            """,
            project_ids,
        )
        sample_rows = [dict(r) for r in sample]

        stats = {
            "total_open": total,
            "buckets": {
                "0_to_5":   int(row["b_0_5"]  or 0),
                "6_to_10":  int(row["b_6_10"] or 0),
                "11_to_20": int(row["b_11_20"] or 0),
                "21_plus":  int(row["b_21_plus"] or 0),
            },
            "oldest_days": int(row["oldest_days"] or 0),
        }

        summary = [
            f"Total open submittals: {total}",
            f"Aging: {stats['buckets']['0_to_5']} (0-5d), "
            f"{stats['buckets']['6_to_10']} (6-10d), "
            f"{stats['buckets']['11_to_20']} (11-20d), "
            f"{stats['buckets']['21_plus']} (21+d)",
            f"Oldest: {stats['oldest_days']} days",
        ]

        return ActionResult(
            stats=stats,
            sample_rows=sample_rows,
            prompt_fragment=_render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, len(project_ids)),
                summary_lines=summary,
                table_header=["project_name", "submittal_number", "title", "days_since_created"],
                rows=sample_rows,
                empty_message="You have no open submittals in the selected scope.",
            ),
        )

    def _empty(self, ctx, n_projects, empty_stats):
        return ActionResult(
            stats=empty_stats,
            sample_rows=[],
            prompt_fragment=_render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, n_projects),
                summary_lines=["Total open submittals: 0"],
                table_header=[],
                rows=[],
                empty_message="You have no open submittals in the selected scope.",
            ),
        )

    @staticmethod
    def _scope_label(ctx, n_projects):
        if ctx.project_id is not None:
            return "single project (page scope)"
        return f"portfolio across {n_projects} projects the user has access to"


__all__ = ["Handler"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && py -m pytest tests/services/ai/actions/test_submittal_sla.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/actions/submittal_sla.py \
        backend/tests/services/ai/actions/test_submittal_sla.py
git commit -m "feat(ai): submittal_sla handler reads rex.v_project_mgmt"
```

---

### Task 6: `budget_variance`

Reads `rex.v_financials`. Variance pct = `budget_over_under / NULLIF(revised_budget, 0)`. Flag projects with \|variance pct\| > 0.05.

**Files:**
- Modify: `backend/app/services/ai/actions/budget_variance.py`
- Test: `backend/tests/services/ai/actions/test_budget_variance.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/ai/actions/test_budget_variance.py
"""budget_variance handler — reads rex.v_financials, flags |delta|>5%."""
from __future__ import annotations

import os
import ssl
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio

from app.services.ai.actions.base import ActionContext
from app.services.ai.actions.budget_variance import Handler


def _raw_url() -> str:
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url[len("postgresql+asyncpg://"):]
    return url


async def _connect() -> asyncpg.Connection:
    url = _raw_url()
    use_ssl = (
        "railway.internal" not in url
        and "localhost" not in url
        and "127.0.0.1" not in url
    )
    ctx = None
    if use_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return await asyncpg.connect(url, ssl=ctx)


def _require_db():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")


@pytest_asyncio.fixture
async def seeded_budgets():
    """Seed 3 projects with varying budget_over_under."""
    _require_db()
    conn = await _connect()
    user_id = uuid4()
    person_id = uuid4()
    project_a = uuid4()   # 3% over — NOT flagged
    project_b = uuid4()   # 10% over — flagged
    project_c = uuid4()   # 20% under — flagged (abs value)
    try:
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email) "
            "VALUES ($1::uuid, 'Bud', 'Tester', $2)",
            person_id, f"bud-{person_id}@test.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, is_active) "
            "VALUES ($1::uuid, $2::uuid, true)",
            user_id, person_id,
        )
        for pid, num, orig, rev, over in [
            (project_a, "BUD-A", 100000, 100000, 3000),    # +3%
            (project_b, "BUD-B", 500000, 500000, 50000),   # +10%
            (project_c, "BUD-C", 200000, 200000, -40000),  # -20%
        ]:
            await conn.execute(
                "INSERT INTO rex.projects (id, name, status, project_number) "
                "VALUES ($1::uuid, $2, 'active', $3)",
                pid, f"Budget {num}", num,
            )
            await conn.execute(
                "INSERT INTO rex.project_members "
                "(id, project_id, person_id, is_active, is_primary) "
                "VALUES (gen_random_uuid(), $1::uuid, $2::uuid, true, false)",
                pid, person_id,
            )
            # The v_financials view reads from rex.v_budgets which is a
            # bridge view — we need to insert the base row.
            await conn.execute(
                """
                INSERT INTO rex.budget_snapshots
                    (id, project_id, original_budget, approved_changes,
                     revised_budget, projected_cost, over_under, snapshot_date)
                VALUES (gen_random_uuid(), $1::uuid, $2, 0, $3, $3 + $4, $4, CURRENT_DATE)
                """,
                pid, orig, rev, over,
            )
        yield user_id, project_a, project_b, project_c
    finally:
        for pid in (project_a, project_b, project_c):
            await conn.execute(
                "DELETE FROM rex.budget_snapshots WHERE project_id = $1::uuid", pid,
            )
            await conn.execute(
                "DELETE FROM rex.project_members WHERE project_id = $1::uuid", pid,
            )
            await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", pid)
        await conn.execute(
            "DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id,
        )
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_budget_variance_flags_over_5pct(seeded_budgets):
    user_id, _a, _b, _c = seeded_budgets
    conn = await _connect()
    try:
        r = await Handler().run(ActionContext(
            conn=conn, user_account_id=user_id, project_id=None,
        ))
        assert r.stats["projects_over_5pct"] == 2
        assert r.stats["total_projects"] == 3
        # Rows sorted by abs(delta_pct) DESC → C (20%), B (10%), A (3%).
        assert len(r.sample_rows) == 3
        assert abs(r.sample_rows[0]["delta_pct"]) >= abs(r.sample_rows[1]["delta_pct"])
    finally:
        await conn.close()
```

**Implementer note:** `rex.v_budgets` is a bridge view (see migration 018) that reads from `rex.budget_snapshots`. The fixture inserts the snapshot. If the real `rex.v_budgets` schema has a different column set, adjust the insert to match — the goal is to land a row that rex.v_financials will pick up with the right `over_under` value.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && py -m pytest tests/services/ai/actions/test_budget_variance.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `budget_variance.py`**

```python
# backend/app/services/ai/actions/budget_variance.py
"""budget_variance — flags projects with |budget_over_under/revised_budget| > 5%."""
from __future__ import annotations

from app.services.ai.actions.base import (
    ActionContext,
    ActionResult,
    resolve_scope_project_ids,
    _render_fragment,
)


class Handler:
    slug = "budget_variance"

    async def run(self, ctx: ActionContext) -> ActionResult:
        project_ids = await resolve_scope_project_ids(
            ctx.conn, user_account_id=ctx.user_account_id, project_id=ctx.project_id,
        )
        if not project_ids:
            return self._empty(ctx, 0)

        rows = await ctx.conn.fetch(
            """
            SELECT
                project_id,
                project_name,
                revised_budget,
                budget_over_under,
                CASE
                    WHEN revised_budget = 0 OR revised_budget IS NULL THEN NULL
                    ELSE budget_over_under / NULLIF(revised_budget, 0)
                END AS delta_pct
            FROM rex.v_financials
            WHERE project_id = ANY($1::uuid[])
            ORDER BY ABS(COALESCE(
                budget_over_under / NULLIF(revised_budget, 0), 0
            )) DESC
            LIMIT 10
            """,
            project_ids,
        )

        sample_rows = [
            {
                "project_name": r["project_name"],
                "revised_budget": float(r["revised_budget"] or 0),
                "budget_over_under": float(r["budget_over_under"] or 0),
                "delta_pct": float(r["delta_pct"] or 0),
            }
            for r in rows
        ]

        over_5pct = sum(1 for r in sample_rows if abs(r["delta_pct"]) > 0.05)
        total_delta = sum(r["budget_over_under"] for r in sample_rows)
        worst = sample_rows[0] if sample_rows else None

        stats = {
            "total_projects": len(sample_rows),
            "projects_over_5pct": over_5pct,
            "total_portfolio_delta": total_delta,
            "worst_variance_pct": worst["delta_pct"] if worst else None,
            "worst_project_name": worst["project_name"] if worst else None,
        }

        summary = [
            f"Projects tracked: {stats['total_projects']}",
            f"Projects with |variance| > 5%: {over_5pct}",
            f"Portfolio budget over/under total: {total_delta:+,.2f}",
        ]
        if worst:
            summary.append(
                f"Worst variance: {worst['delta_pct']:+.1%} on {worst['project_name']}"
            )

        # For display, format delta_pct as a percentage string
        display_rows = [
            {
                **r,
                "delta_pct": f"{r['delta_pct']:+.1%}",
                "budget_over_under": f"{r['budget_over_under']:+,.0f}",
                "revised_budget": f"{r['revised_budget']:,.0f}",
            }
            for r in sample_rows
        ]

        return ActionResult(
            stats=stats,
            sample_rows=sample_rows,
            prompt_fragment=_render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, len(project_ids)),
                summary_lines=summary,
                table_header=["project_name", "revised_budget", "budget_over_under", "delta_pct"],
                rows=display_rows,
                empty_message="No budget data is available for the selected scope.",
            ),
        )

    def _empty(self, ctx, n_projects):
        return ActionResult(
            stats={
                "total_projects": 0,
                "projects_over_5pct": 0,
                "total_portfolio_delta": 0.0,
                "worst_variance_pct": None,
                "worst_project_name": None,
            },
            sample_rows=[],
            prompt_fragment=_render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, n_projects),
                summary_lines=["Projects tracked: 0"],
                table_header=[],
                rows=[],
                empty_message="No budget data is available for the selected scope.",
            ),
        )

    @staticmethod
    def _scope_label(ctx, n_projects):
        if ctx.project_id is not None:
            return "single project (page scope)"
        return f"portfolio across {n_projects} projects the user has access to"


__all__ = ["Handler"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && py -m pytest tests/services/ai/actions/test_budget_variance.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/actions/budget_variance.py \
        backend/tests/services/ai/actions/test_budget_variance.py
git commit -m "feat(ai): budget_variance handler flags projects > 5% delta"
```

---

### Task 7: `daily_log_summary`

Reads `rex.daily_logs` + `rex.manpower_entries`. Last-7-days metric + today's manpower.

**Files:**
- Modify: `backend/app/services/ai/actions/daily_log_summary.py`
- Test: `backend/tests/services/ai/actions/test_daily_log_summary.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/ai/actions/test_daily_log_summary.py
"""daily_log_summary — 7-day log counts + today's manpower."""
from __future__ import annotations

import os
import ssl
from datetime import date, timedelta
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio

from app.services.ai.actions.base import ActionContext
from app.services.ai.actions.daily_log_summary import Handler


def _raw_url() -> str:
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url[len("postgresql+asyncpg://"):]
    return url


async def _connect() -> asyncpg.Connection:
    url = _raw_url()
    use_ssl = (
        "railway.internal" not in url
        and "localhost" not in url
        and "127.0.0.1" not in url
    )
    ctx = None
    if use_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return await asyncpg.connect(url, ssl=ctx)


def _require_db():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")


@pytest_asyncio.fixture
async def seeded_logs():
    _require_db()
    conn = await _connect()
    user_id = uuid4()
    person_id = uuid4()
    project_id = uuid4()
    company_id = uuid4()
    try:
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email) "
            "VALUES ($1::uuid, 'Log', 'Tester', $2)",
            person_id, f"log-{person_id}@test.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, is_active) "
            "VALUES ($1::uuid, $2::uuid, true)",
            user_id, person_id,
        )
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'Log Test', 'active', 'LOG-1')",
            project_id,
        )
        await conn.execute(
            "INSERT INTO rex.project_members "
            "(id, project_id, person_id, is_active, is_primary) "
            "VALUES (gen_random_uuid(), $1::uuid, $2::uuid, true, false)",
            project_id, person_id,
        )
        await conn.execute(
            "INSERT INTO rex.companies (id, name, company_type) "
            "VALUES ($1::uuid, 'ACME Trades', 'subcontractor')",
            company_id,
        )
        # 4 daily logs: today, yesterday, 3 days ago, 10 days ago.
        today = date.today()
        logs = [(today, True), (today - timedelta(days=1), False),
                (today - timedelta(days=3), False), (today - timedelta(days=10), False)]
        log_ids = []
        for log_date, is_today in logs:
            lid = uuid4()
            log_ids.append((lid, is_today))
            await conn.execute(
                "INSERT INTO rex.daily_logs "
                "(id, project_id, log_date, status, weather_summary, work_summary) "
                "VALUES ($1::uuid, $2::uuid, $3::date, 'submitted', 'clear', 'work')",
                lid, project_id, log_date,
            )
        # Manpower entries ONLY for today's log.
        for lid, is_today in log_ids:
            if is_today:
                await conn.execute(
                    "INSERT INTO rex.manpower_entries "
                    "(id, daily_log_id, company_id, worker_count, hours) "
                    "VALUES (gen_random_uuid(), $1::uuid, $2::uuid, 12, 96)",
                    lid, company_id,
                )
        yield user_id, project_id
    finally:
        await conn.execute("DELETE FROM rex.manpower_entries WHERE daily_log_id IN (SELECT id FROM rex.daily_logs WHERE project_id = $1::uuid)", project_id)
        await conn.execute("DELETE FROM rex.daily_logs WHERE project_id = $1::uuid", project_id)
        await conn.execute("DELETE FROM rex.companies WHERE id = $1::uuid", company_id)
        await conn.execute(
            "DELETE FROM rex.project_members WHERE project_id = $1::uuid", project_id,
        )
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", project_id)
        await conn.execute(
            "DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id,
        )
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_daily_log_summary(seeded_logs):
    user_id, _ = seeded_logs
    conn = await _connect()
    try:
        r = await Handler().run(ActionContext(
            conn=conn, user_account_id=user_id, project_id=None,
        ))
        assert r.stats["logs_last_7_days"] == 3       # today + yesterday + 3-days-ago
        assert r.stats["today_total_manpower"] == 12  # 1 entry with 12 workers
        assert r.stats["projects_without_today_log"] == 0  # today's log exists
        assert "Quick action data: daily_log_summary" in r.prompt_fragment
    finally:
        await conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && py -m pytest tests/services/ai/actions/test_daily_log_summary.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `daily_log_summary.py`**

```python
# backend/app/services/ai/actions/daily_log_summary.py
"""daily_log_summary — last 7 days of daily logs + today's manpower rollup."""
from __future__ import annotations

from app.services.ai.actions.base import (
    ActionContext,
    ActionResult,
    resolve_scope_project_ids,
    _render_fragment,
)


class Handler:
    slug = "daily_log_summary"

    async def run(self, ctx: ActionContext) -> ActionResult:
        project_ids = await resolve_scope_project_ids(
            ctx.conn, user_account_id=ctx.user_account_id, project_id=ctx.project_id,
        )
        if not project_ids:
            return self._empty(ctx, 0)

        stats_row = await ctx.conn.fetchrow(
            """
            WITH logs7 AS (
                SELECT * FROM rex.daily_logs
                WHERE project_id = ANY($1::uuid[])
                  AND log_date >= CURRENT_DATE - INTERVAL '7 days'
            ), todays AS (
                SELECT * FROM rex.daily_logs
                WHERE project_id = ANY($1::uuid[])
                  AND log_date = CURRENT_DATE
            )
            SELECT
                (SELECT COUNT(*) FROM logs7)                                         AS logs_last_7_days,
                COALESCE((SELECT SUM(me.worker_count)
                    FROM todays t JOIN rex.manpower_entries me ON me.daily_log_id = t.id), 0) AS today_total_manpower,
                COALESCE((SELECT COUNT(DISTINCT me.company_id)
                    FROM todays t JOIN rex.manpower_entries me ON me.daily_log_id = t.id), 0) AS today_trades_on_site,
                (
                    array_length($1::uuid[], 1)
                    - (SELECT COUNT(DISTINCT project_id) FROM todays)
                )                                                                   AS projects_without_today_log
            """,
            project_ids,
        )

        sample = await ctx.conn.fetch(
            """
            SELECT
                p.name                                               AS project_name,
                dl.log_date                                          AS log_date,
                dl.weather_summary                                   AS weather,
                COALESCE(SUM(me.worker_count), 0)                    AS total_headcount,
                COUNT(DISTINCT me.company_id)                        AS trade_count
            FROM rex.daily_logs dl
            JOIN rex.projects p ON p.id = dl.project_id
            LEFT JOIN rex.manpower_entries me ON me.daily_log_id = dl.id
            WHERE dl.project_id = ANY($1::uuid[])
              AND dl.log_date >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY p.name, dl.log_date, dl.weather_summary
            ORDER BY dl.log_date DESC, p.name
            LIMIT 10
            """,
            project_ids,
        )
        sample_rows = [dict(r) for r in sample]
        display_rows = [
            {**r, "log_date": r["log_date"].isoformat() if r.get("log_date") else ""}
            for r in sample_rows
        ]

        stats = {
            "logs_last_7_days": int(stats_row["logs_last_7_days"] or 0),
            "today_total_manpower": int(stats_row["today_total_manpower"] or 0),
            "today_trades_on_site": int(stats_row["today_trades_on_site"] or 0),
            "projects_without_today_log": int(stats_row["projects_without_today_log"] or 0),
        }
        summary = [
            f"Logs submitted last 7 days: {stats['logs_last_7_days']}",
            f"Today total manpower: {stats['today_total_manpower']} across {stats['today_trades_on_site']} trade(s)",
            f"Projects without a log today: {stats['projects_without_today_log']}",
        ]

        return ActionResult(
            stats=stats,
            sample_rows=sample_rows,
            prompt_fragment=_render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, len(project_ids)),
                summary_lines=summary,
                table_header=["project_name", "log_date", "weather", "total_headcount", "trade_count"],
                rows=display_rows,
                empty_message="No daily logs in the last 7 days in the selected scope.",
            ),
        )

    def _empty(self, ctx, n_projects):
        return ActionResult(
            stats={"logs_last_7_days": 0, "today_total_manpower": 0, "today_trades_on_site": 0, "projects_without_today_log": 0},
            sample_rows=[],
            prompt_fragment=_render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, n_projects),
                summary_lines=["Logs submitted last 7 days: 0"],
                table_header=[],
                rows=[],
                empty_message="No daily logs in the last 7 days in the selected scope.",
            ),
        )

    @staticmethod
    def _scope_label(ctx, n_projects):
        if ctx.project_id is not None:
            return "single project (page scope)"
        return f"portfolio across {n_projects} projects the user has access to"


__all__ = ["Handler"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && py -m pytest tests/services/ai/actions/test_daily_log_summary.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/actions/daily_log_summary.py \
        backend/tests/services/ai/actions/test_daily_log_summary.py
git commit -m "feat(ai): daily_log_summary handler reads rex.daily_logs + manpower_entries"
```

---

### Task 8: `critical_path_delays`

Queries `rex.schedule_activities` joined to `rex.schedules` (v_schedule is a rollup, not per-activity).

**Files:**
- Modify: `backend/app/services/ai/actions/critical_path_delays.py`
- Test: `backend/tests/services/ai/actions/test_critical_path_delays.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/ai/actions/test_critical_path_delays.py
"""critical_path_delays — critical activities with variance_days > 2."""
from __future__ import annotations

import os
import ssl
from datetime import date, timedelta
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio

from app.services.ai.actions.base import ActionContext
from app.services.ai.actions.critical_path_delays import Handler


def _raw_url() -> str:
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url[len("postgresql+asyncpg://"):]
    return url


async def _connect() -> asyncpg.Connection:
    url = _raw_url()
    use_ssl = (
        "railway.internal" not in url
        and "localhost" not in url
        and "127.0.0.1" not in url
    )
    ctx = None
    if use_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return await asyncpg.connect(url, ssl=ctx)


def _require_db():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")


@pytest_asyncio.fixture
async def seeded_schedule():
    _require_db()
    conn = await _connect()
    user_id = uuid4()
    person_id = uuid4()
    project_id = uuid4()
    schedule_id = uuid4()
    try:
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email) "
            "VALUES ($1::uuid, 'Sch', 'Tester', $2)",
            person_id, f"sch-{person_id}@test.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, is_active) "
            "VALUES ($1::uuid, $2::uuid, true)",
            user_id, person_id,
        )
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'Schedule Test', 'active', 'SCH-1')",
            project_id,
        )
        await conn.execute(
            "INSERT INTO rex.project_members "
            "(id, project_id, person_id, is_active, is_primary) "
            "VALUES (gen_random_uuid(), $1::uuid, $2::uuid, true, false)",
            project_id, person_id,
        )
        await conn.execute(
            "INSERT INTO rex.schedules "
            "(id, project_id, name, schedule_type, status, start_date) "
            "VALUES ($1::uuid, $2::uuid, 'Master', 'master', 'active', CURRENT_DATE)",
            schedule_id, project_id,
        )
        # 4 activities: 2 critical + delayed, 1 critical + on-time, 1 non-critical + delayed.
        rows = [
            ("Framing",    True,  5),
            ("Roofing",    True,  10),
            ("Paint",      True,  0),   # critical but on-time
            ("Landscape",  False, 8),   # non-critical
            ("Walls",      True,  2),   # critical + variance_days=2 (NOT delayed, threshold is > 2)
        ]
        for name, crit, var in rows:
            await conn.execute(
                "INSERT INTO rex.schedule_activities "
                "(id, schedule_id, name, activity_type, start_date, end_date, "
                "percent_complete, is_critical, variance_days) "
                "VALUES (gen_random_uuid(), $1::uuid, $2, 'task', "
                "CURRENT_DATE, CURRENT_DATE + INTERVAL '5 days', 50, $3, $4)",
                schedule_id, name, crit, var,
            )
        yield user_id, project_id
    finally:
        await conn.execute("DELETE FROM rex.schedule_activities WHERE schedule_id = $1::uuid", schedule_id)
        await conn.execute("DELETE FROM rex.schedules WHERE id = $1::uuid", schedule_id)
        await conn.execute(
            "DELETE FROM rex.project_members WHERE project_id = $1::uuid", project_id,
        )
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", project_id)
        await conn.execute(
            "DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id,
        )
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_critical_path_delays(seeded_schedule):
    user_id, _ = seeded_schedule
    conn = await _connect()
    try:
        r = await Handler().run(ActionContext(
            conn=conn, user_account_id=user_id, project_id=None,
        ))
        # Framing (5) and Roofing (10) are critical + variance > 2.
        assert r.stats["critical_tasks_delayed"] == 2
        assert r.stats["worst_delay_days"] == 10
        # Ordered by variance_days DESC.
        assert r.sample_rows[0]["variance_days"] == 10
        assert r.sample_rows[1]["variance_days"] == 5
    finally:
        await conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && py -m pytest tests/services/ai/actions/test_critical_path_delays.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `critical_path_delays.py`**

```python
# backend/app/services/ai/actions/critical_path_delays.py
"""critical_path_delays — critical schedule activities with variance_days > 2.

Queries rex.schedule_activities joined to rex.schedules (for project_id).
rex.v_schedule is a per-project rollup (provides only counts); we need
per-activity detail so we bypass the view for this handler.
"""
from __future__ import annotations

from app.services.ai.actions.base import (
    ActionContext,
    ActionResult,
    resolve_scope_project_ids,
    _render_fragment,
)


class Handler:
    slug = "critical_path_delays"

    async def run(self, ctx: ActionContext) -> ActionResult:
        project_ids = await resolve_scope_project_ids(
            ctx.conn, user_account_id=ctx.user_account_id, project_id=ctx.project_id,
        )
        if not project_ids:
            return self._empty(ctx, 0)

        row = await ctx.conn.fetchrow(
            """
            SELECT
                COUNT(*)                                     AS critical_tasks_delayed,
                COALESCE(MAX(sa.variance_days), 0)           AS worst_delay_days,
                COUNT(DISTINCT s.project_id)                 AS projects_with_critical_delays
            FROM rex.schedule_activities sa
            JOIN rex.schedules s ON s.id = sa.schedule_id
            WHERE s.project_id = ANY($1::uuid[])
              AND sa.is_critical = true
              AND sa.variance_days > 2
            """,
            project_ids,
        )
        sample = await ctx.conn.fetch(
            """
            SELECT
                p.name         AS project_name,
                sa.name        AS task_name,
                sa.start_date  AS start_date,
                sa.end_date    AS end_date,
                sa.variance_days AS variance_days
            FROM rex.schedule_activities sa
            JOIN rex.schedules s ON s.id = sa.schedule_id
            JOIN rex.projects p ON p.id = s.project_id
            WHERE s.project_id = ANY($1::uuid[])
              AND sa.is_critical = true
              AND sa.variance_days > 2
            ORDER BY sa.variance_days DESC
            LIMIT 10
            """,
            project_ids,
        )
        sample_rows = [dict(r) for r in sample]
        display_rows = [
            {
                **r,
                "start_date": r["start_date"].isoformat() if r.get("start_date") else "",
                "end_date": r["end_date"].isoformat() if r.get("end_date") else "",
            }
            for r in sample_rows
        ]

        stats = {
            "critical_tasks_delayed": int(row["critical_tasks_delayed"] or 0),
            "worst_delay_days": int(row["worst_delay_days"] or 0),
            "projects_with_critical_delays": int(row["projects_with_critical_delays"] or 0),
        }

        summary = [
            f"Critical path tasks delayed (>2d): {stats['critical_tasks_delayed']}",
            f"Worst delay: {stats['worst_delay_days']} day(s)",
            f"Projects affected: {stats['projects_with_critical_delays']}",
        ]

        return ActionResult(
            stats=stats,
            sample_rows=sample_rows,
            prompt_fragment=_render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, len(project_ids)),
                summary_lines=summary,
                table_header=["project_name", "task_name", "start_date", "end_date", "variance_days"],
                rows=display_rows,
                empty_message="No critical-path tasks with variance > 2 days in the selected scope.",
            ),
        )

    def _empty(self, ctx, n_projects):
        return ActionResult(
            stats={"critical_tasks_delayed": 0, "worst_delay_days": 0, "projects_with_critical_delays": 0},
            sample_rows=[],
            prompt_fragment=_render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, n_projects),
                summary_lines=["Critical path tasks delayed: 0"],
                table_header=[],
                rows=[],
                empty_message="No critical-path tasks with variance > 2 days in the selected scope.",
            ),
        )

    @staticmethod
    def _scope_label(ctx, n_projects):
        if ctx.project_id is not None:
            return "single project (page scope)"
        return f"portfolio across {n_projects} projects the user has access to"


__all__ = ["Handler"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && py -m pytest tests/services/ai/actions/test_critical_path_delays.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/actions/critical_path_delays.py \
        backend/tests/services/ai/actions/test_critical_path_delays.py
git commit -m "feat(ai): critical_path_delays handler reads rex.schedule_activities"
```

---

### Task 9: `two_week_lookahead`

Same `rex.schedule_activities` table, different filter (start_date in [today, +14d]).

**Files:**
- Modify: `backend/app/services/ai/actions/two_week_lookahead.py`
- Test: `backend/tests/services/ai/actions/test_two_week_lookahead.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/ai/actions/test_two_week_lookahead.py
"""two_week_lookahead — tasks starting in [today, today+14d]."""
from __future__ import annotations

import os
import ssl
from datetime import date, timedelta
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio

from app.services.ai.actions.base import ActionContext
from app.services.ai.actions.two_week_lookahead import Handler


def _raw_url() -> str:
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url[len("postgresql+asyncpg://"):]
    return url


async def _connect() -> asyncpg.Connection:
    url = _raw_url()
    use_ssl = (
        "railway.internal" not in url
        and "localhost" not in url
        and "127.0.0.1" not in url
    )
    ctx = None
    if use_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return await asyncpg.connect(url, ssl=ctx)


def _require_db():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")


@pytest_asyncio.fixture
async def seeded_lookahead():
    _require_db()
    conn = await _connect()
    user_id = uuid4()
    person_id = uuid4()
    project_id = uuid4()
    schedule_id = uuid4()
    try:
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email) "
            "VALUES ($1::uuid, 'LA', 'Tester', $2)",
            person_id, f"la-{person_id}@test.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, is_active) "
            "VALUES ($1::uuid, $2::uuid, true)",
            user_id, person_id,
        )
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'LA Test', 'active', 'LA-1')",
            project_id,
        )
        await conn.execute(
            "INSERT INTO rex.project_members "
            "(id, project_id, person_id, is_active, is_primary) "
            "VALUES (gen_random_uuid(), $1::uuid, $2::uuid, true, false)",
            project_id, person_id,
        )
        await conn.execute(
            "INSERT INTO rex.schedules "
            "(id, project_id, name, schedule_type, status, start_date) "
            "VALUES ($1::uuid, $2::uuid, 'Master', 'master', 'active', CURRENT_DATE)",
            schedule_id, project_id,
        )
        today = date.today()
        # Includes: day 1, day 7, day 14 (upper bound inclusive)
        # Excludes: day -1 (past), day 20 (out of range)
        for name, start_offset in [
            ("In-range A (tomorrow)", 1),
            ("In-range B (day 7)",    7),
            ("In-range C (day 14)",   14),
            ("Past (yesterday)",      -1),
            ("Future (day 20)",       20),
        ]:
            await conn.execute(
                "INSERT INTO rex.schedule_activities "
                "(id, schedule_id, name, activity_type, start_date, end_date, "
                "percent_complete, is_critical) "
                "VALUES (gen_random_uuid(), $1::uuid, $2, 'task', "
                "$3::date, $3::date + INTERVAL '3 days', 0, false)",
                schedule_id, name, today + timedelta(days=start_offset),
            )
        yield user_id, project_id
    finally:
        await conn.execute("DELETE FROM rex.schedule_activities WHERE schedule_id = $1::uuid", schedule_id)
        await conn.execute("DELETE FROM rex.schedules WHERE id = $1::uuid", schedule_id)
        await conn.execute(
            "DELETE FROM rex.project_members WHERE project_id = $1::uuid", project_id,
        )
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", project_id)
        await conn.execute(
            "DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id,
        )
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_two_week_lookahead(seeded_lookahead):
    user_id, _ = seeded_lookahead
    conn = await _connect()
    try:
        r = await Handler().run(ActionContext(
            conn=conn, user_account_id=user_id, project_id=None,
        ))
        assert r.stats["tasks_starting_next_14d"] == 3
        assert r.stats["projects_with_starts"] == 1
        # Ordered by start_date ASC.
        assert r.sample_rows[0]["task_name"].startswith("In-range A")
    finally:
        await conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && py -m pytest tests/services/ai/actions/test_two_week_lookahead.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `two_week_lookahead.py`**

```python
# backend/app/services/ai/actions/two_week_lookahead.py
"""two_week_lookahead — schedule_activities starting in [today, today+14d]."""
from __future__ import annotations

from app.services.ai.actions.base import (
    ActionContext,
    ActionResult,
    resolve_scope_project_ids,
    _render_fragment,
)


class Handler:
    slug = "two_week_lookahead"

    async def run(self, ctx: ActionContext) -> ActionResult:
        project_ids = await resolve_scope_project_ids(
            ctx.conn, user_account_id=ctx.user_account_id, project_id=ctx.project_id,
        )
        if not project_ids:
            return self._empty(ctx, 0)

        row = await ctx.conn.fetchrow(
            """
            SELECT
                COUNT(*)                                     AS tasks_starting_next_14d,
                COUNT(DISTINCT s.project_id)                 AS projects_with_starts,
                MIN(sa.start_date)                           AS earliest_start
            FROM rex.schedule_activities sa
            JOIN rex.schedules s ON s.id = sa.schedule_id
            WHERE s.project_id = ANY($1::uuid[])
              AND sa.start_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '14 days'
            """,
            project_ids,
        )
        sample = await ctx.conn.fetch(
            """
            SELECT
                p.name         AS project_name,
                sa.name        AS task_name,
                sa.start_date  AS start_date,
                sa.end_date    AS end_date,
                sa.percent_complete AS percent_complete
            FROM rex.schedule_activities sa
            JOIN rex.schedules s ON s.id = sa.schedule_id
            JOIN rex.projects p ON p.id = s.project_id
            WHERE s.project_id = ANY($1::uuid[])
              AND sa.start_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '14 days'
            ORDER BY sa.start_date ASC, p.name
            LIMIT 10
            """,
            project_ids,
        )
        sample_rows = [dict(r) for r in sample]
        display_rows = [
            {
                **r,
                "start_date": r["start_date"].isoformat() if r.get("start_date") else "",
                "end_date": r["end_date"].isoformat() if r.get("end_date") else "",
                "percent_complete": f"{float(r['percent_complete'] or 0):.0f}%",
            }
            for r in sample_rows
        ]

        stats = {
            "tasks_starting_next_14d": int(row["tasks_starting_next_14d"] or 0),
            "projects_with_starts": int(row["projects_with_starts"] or 0),
            "earliest_start_date": (
                row["earliest_start"].isoformat() if row["earliest_start"] else None
            ),
        }

        summary = [
            f"Tasks starting in next 14 days: {stats['tasks_starting_next_14d']}",
            f"Projects with starts: {stats['projects_with_starts']}",
        ]
        if stats["earliest_start_date"]:
            summary.append(f"Earliest start: {stats['earliest_start_date']}")

        return ActionResult(
            stats=stats,
            sample_rows=sample_rows,
            prompt_fragment=_render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, len(project_ids)),
                summary_lines=summary,
                table_header=["project_name", "task_name", "start_date", "end_date", "percent_complete"],
                rows=display_rows,
                empty_message="No tasks starting in the next 14 days in the selected scope.",
            ),
        )

    def _empty(self, ctx, n_projects):
        return ActionResult(
            stats={"tasks_starting_next_14d": 0, "projects_with_starts": 0, "earliest_start_date": None},
            sample_rows=[],
            prompt_fragment=_render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, n_projects),
                summary_lines=["Tasks starting in next 14 days: 0"],
                table_header=[],
                rows=[],
                empty_message="No tasks starting in the next 14 days in the selected scope.",
            ),
        )

    @staticmethod
    def _scope_label(ctx, n_projects):
        if ctx.project_id is not None:
            return "single project (page scope)"
        return f"portfolio across {n_projects} projects the user has access to"


__all__ = ["Handler"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && py -m pytest tests/services/ai/actions/test_two_week_lookahead.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/actions/two_week_lookahead.py \
        backend/tests/services/ai/actions/test_two_week_lookahead.py
git commit -m "feat(ai): two_week_lookahead handler reads rex.schedule_activities"
```

---

### Task 10: `documentation_compliance`

**Redirected from `rex.v_documents` to `rex.v_closeout_items`** — v_documents is a bridge over attachments with no compliance semantics (no approval status, no expiration). `rex.v_closeout_items` tracks overdue/near-due closeout checklist items, which IS what a "documentation compliance" signal needs for a VP.

**Files:**
- Modify: `backend/app/services/ai/actions/documentation_compliance.py`
- Test: `backend/tests/services/ai/actions/test_documentation_compliance.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/ai/actions/test_documentation_compliance.py
"""documentation_compliance — closeout checklist items overdue or near-due."""
from __future__ import annotations

import os
import ssl
from datetime import date, timedelta
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio

from app.services.ai.actions.base import ActionContext
from app.services.ai.actions.documentation_compliance import Handler


def _raw_url() -> str:
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url[len("postgresql+asyncpg://"):]
    return url


async def _connect() -> asyncpg.Connection:
    url = _raw_url()
    use_ssl = (
        "railway.internal" not in url
        and "localhost" not in url
        and "127.0.0.1" not in url
    )
    ctx = None
    if use_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return await asyncpg.connect(url, ssl=ctx)


def _require_db():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")


@pytest_asyncio.fixture
async def seeded_closeout():
    _require_db()
    conn = await _connect()
    user_id = uuid4()
    person_id = uuid4()
    project_id = uuid4()
    checklist_id = uuid4()
    try:
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email) "
            "VALUES ($1::uuid, 'DC', 'Tester', $2)",
            person_id, f"dc-{person_id}@test.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, is_active) "
            "VALUES ($1::uuid, $2::uuid, true)",
            user_id, person_id,
        )
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'DC Test', 'active', 'DC-1')",
            project_id,
        )
        await conn.execute(
            "INSERT INTO rex.project_members "
            "(id, project_id, person_id, is_active, is_primary) "
            "VALUES (gen_random_uuid(), $1::uuid, $2::uuid, true, false)",
            project_id, person_id,
        )
        await conn.execute(
            "INSERT INTO rex.closeout_checklists "
            "(id, project_id, name, status) "
            "VALUES ($1::uuid, $2::uuid, 'Main', 'active')",
            checklist_id, project_id,
        )
        today = date.today()
        items = [
            ("Overdue-1",   "open",        today - timedelta(days=5)),
            ("Overdue-2",   "in_progress", today - timedelta(days=12)),
            ("Near-due",    "open",        today + timedelta(days=15)),
            ("Far-future",  "open",        today + timedelta(days=60)),
            ("Completed",   "completed",   today - timedelta(days=20)),
        ]
        for name, status, due in items:
            await conn.execute(
                "INSERT INTO rex.closeout_checklist_items "
                "(id, checklist_id, category, name, status, due_date, item_number) "
                "VALUES (gen_random_uuid(), $1::uuid, 'general', $2, $3, $4::date, $2)",
                checklist_id, name, status, due,
            )
        yield user_id, project_id
    finally:
        await conn.execute("DELETE FROM rex.closeout_checklist_items WHERE checklist_id = $1::uuid", checklist_id)
        await conn.execute("DELETE FROM rex.closeout_checklists WHERE id = $1::uuid", checklist_id)
        await conn.execute(
            "DELETE FROM rex.project_members WHERE project_id = $1::uuid", project_id,
        )
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", project_id)
        await conn.execute(
            "DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id,
        )
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_documentation_compliance(seeded_closeout):
    user_id, _ = seeded_closeout
    conn = await _connect()
    try:
        r = await Handler().run(ActionContext(
            conn=conn, user_account_id=user_id, project_id=None,
        ))
        # Overdue = 2, near-due (within 30d and not completed) = 1.
        assert r.stats["overdue_items"] == 2
        assert r.stats["due_within_30_days"] == 1
        # Completed items are excluded.
        assert all(r["status"] != "completed" for r in r.sample_rows)
    finally:
        await conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && py -m pytest tests/services/ai/actions/test_documentation_compliance.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `documentation_compliance.py`**

```python
# backend/app/services/ai/actions/documentation_compliance.py
"""documentation_compliance — overdue / near-due closeout checklist items.

Reads rex.v_closeout_items. (The originally-specced rex.v_documents is
a bridge over attachments with no compliance semantics.)
Buckets:
  - overdue:            status != 'completed' AND due_date < today
  - due_within_30_days: status != 'completed' AND due_date BETWEEN today AND today+30
"""
from __future__ import annotations

from app.services.ai.actions.base import (
    ActionContext,
    ActionResult,
    resolve_scope_project_ids,
    _render_fragment,
)


class Handler:
    slug = "documentation_compliance"

    async def run(self, ctx: ActionContext) -> ActionResult:
        project_ids = await resolve_scope_project_ids(
            ctx.conn, user_account_id=ctx.user_account_id, project_id=ctx.project_id,
        )
        if not project_ids:
            return self._empty(ctx, 0)

        row = await ctx.conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (
                    WHERE status != 'completed'
                      AND due_date < CURRENT_DATE
                )                                            AS overdue_items,
                COUNT(*) FILTER (
                    WHERE status != 'completed'
                      AND due_date BETWEEN CURRENT_DATE
                                       AND CURRENT_DATE + INTERVAL '30 days'
                )                                            AS due_within_30_days
            FROM rex.v_closeout_items
            WHERE project_id = ANY($1::uuid[])
            """,
            project_ids,
        )
        sample = await ctx.conn.fetch(
            """
            SELECT
                p.name       AS project_name,
                ci.category  AS category,
                ci.name      AS item_name,
                ci.status    AS status,
                ci.due_date  AS due_date,
                (ci.due_date - CURRENT_DATE) AS days_to_due
            FROM rex.v_closeout_items ci
            JOIN rex.projects p ON p.id = ci.project_id
            WHERE ci.project_id = ANY($1::uuid[])
              AND ci.status != 'completed'
              AND (
                ci.due_date < CURRENT_DATE
                OR ci.due_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'
              )
            ORDER BY
                CASE WHEN ci.due_date < CURRENT_DATE THEN 0 ELSE 1 END,
                ci.due_date ASC
            LIMIT 10
            """,
            project_ids,
        )
        sample_rows = [dict(r) for r in sample]
        display_rows = [
            {
                **r,
                "due_date": r["due_date"].isoformat() if r.get("due_date") else "",
            }
            for r in sample_rows
        ]

        stats = {
            "overdue_items": int(row["overdue_items"] or 0),
            "due_within_30_days": int(row["due_within_30_days"] or 0),
        }

        summary = [
            f"Overdue items: {stats['overdue_items']}",
            f"Due within 30 days: {stats['due_within_30_days']}",
        ]

        return ActionResult(
            stats=stats,
            sample_rows=sample_rows,
            prompt_fragment=_render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, len(project_ids)),
                summary_lines=summary,
                table_header=["project_name", "category", "item_name", "status", "due_date", "days_to_due"],
                rows=display_rows,
                empty_message="No overdue or near-due closeout items in the selected scope.",
            ),
        )

    def _empty(self, ctx, n_projects):
        return ActionResult(
            stats={"overdue_items": 0, "due_within_30_days": 0},
            sample_rows=[],
            prompt_fragment=_render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, n_projects),
                summary_lines=["Overdue items: 0"],
                table_header=[],
                rows=[],
                empty_message="No overdue or near-due closeout items in the selected scope.",
            ),
        )

    @staticmethod
    def _scope_label(ctx, n_projects):
        if ctx.project_id is not None:
            return "single project (page scope)"
        return f"portfolio across {n_projects} projects the user has access to"


__all__ = ["Handler"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && py -m pytest tests/services/ai/actions/test_documentation_compliance.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/actions/documentation_compliance.py \
        backend/tests/services/ai/actions/test_documentation_compliance.py
git commit -m "feat(ai): documentation_compliance handler reads rex.v_closeout_items"
```

---

### Task 11: `my_day_briefing`

Reads `rex.v_myday`. User-scoped, project-optional.

**Files:**
- Modify: `backend/app/services/ai/actions/my_day_briefing.py`
- Test: `backend/tests/services/ai/actions/test_my_day_briefing.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/ai/actions/test_my_day_briefing.py
"""my_day_briefing — pulls rex.v_myday for the requesting user."""
from __future__ import annotations

import os
import ssl
from datetime import date, timedelta
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio

from app.services.ai.actions.base import ActionContext
from app.services.ai.actions.my_day_briefing import Handler


def _raw_url() -> str:
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url[len("postgresql+asyncpg://"):]
    return url


async def _connect() -> asyncpg.Connection:
    url = _raw_url()
    use_ssl = (
        "railway.internal" not in url
        and "localhost" not in url
        and "127.0.0.1" not in url
    )
    ctx = None
    if use_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return await asyncpg.connect(url, ssl=ctx)


def _require_db():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")


@pytest_asyncio.fixture
async def seeded_myday():
    _require_db()
    conn = await _connect()
    user_id = uuid4()
    person_id = uuid4()
    project_id = uuid4()
    try:
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email) "
            "VALUES ($1::uuid, 'My', 'Day', $2)",
            person_id, f"md-{person_id}@test.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, is_active) "
            "VALUES ($1::uuid, $2::uuid, true)",
            user_id, person_id,
        )
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'My Day', 'active', 'MD-1')",
            project_id,
        )
        await conn.execute(
            "INSERT INTO rex.project_members "
            "(id, project_id, person_id, is_active, is_primary) "
            "VALUES (gen_random_uuid(), $1::uuid, $2::uuid, true, false)",
            project_id, person_id,
        )
        today = date.today()
        # 1 RFI ball-in-court for user, due today (urgent)
        # 1 RFI assigned to user, overdue
        # 1 Task assigned to user, in progress
        await conn.execute(
            "INSERT INTO rex.rfis "
            "(id, project_id, rfi_number, subject, question, status, ball_in_court, due_date, created_at, updated_at) "
            "VALUES (gen_random_uuid(), $1::uuid, 'R-1', 'Due today', 'q', 'open', $2::uuid, $3::date, now(), now())",
            project_id, person_id, today,
        )
        await conn.execute(
            "INSERT INTO rex.rfis "
            "(id, project_id, rfi_number, subject, question, status, assigned_to, due_date, created_at, updated_at) "
            "VALUES (gen_random_uuid(), $1::uuid, 'R-2', 'Overdue', 'q', 'open', $2::uuid, $3::date, now(), now())",
            project_id, person_id, today - timedelta(days=2),
        )
        await conn.execute(
            "INSERT INTO rex.tasks "
            "(id, project_id, task_number, title, status, assigned_to, due_date, created_at, updated_at) "
            "VALUES (gen_random_uuid(), $1::uuid, 1, 'Task for me', 'in_progress', $2::uuid, $3::date, now(), now())",
            project_id, person_id, today + timedelta(days=3),
        )
        yield user_id, project_id, person_id
    finally:
        await conn.execute("DELETE FROM rex.rfis WHERE project_id = $1::uuid", project_id)
        await conn.execute("DELETE FROM rex.tasks WHERE project_id = $1::uuid", project_id)
        await conn.execute(
            "DELETE FROM rex.project_members WHERE project_id = $1::uuid", project_id,
        )
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", project_id)
        await conn.execute(
            "DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id,
        )
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_my_day_briefing(seeded_myday):
    user_id, _, _ = seeded_myday
    conn = await _connect()
    try:
        r = await Handler().run(ActionContext(
            conn=conn, user_account_id=user_id, project_id=None,
        ))
        # 3 items total for this user.
        assert r.stats["total_items"] == 3
        assert r.stats["overdue"] == 1
        assert r.stats["due_today"] == 1
        assert len(r.sample_rows) == 3
    finally:
        await conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && py -m pytest tests/services/ai/actions/test_my_day_briefing.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `my_day_briefing.py`**

```python
# backend/app/services/ai/actions/my_day_briefing.py
"""my_day_briefing — personalized digest from rex.v_myday.

Always user-scoped (v_myday is already keyed by user_account_id).
project_id (if set) narrows the digest to that project.
"""
from __future__ import annotations

from app.services.ai.actions.base import (
    ActionContext,
    ActionResult,
    _render_fragment,
)


class Handler:
    slug = "my_day_briefing"

    async def run(self, ctx: ActionContext) -> ActionResult:
        row = await ctx.conn.fetchrow(
            """
            SELECT
                COUNT(*)                                                   AS total_items,
                COUNT(*) FILTER (WHERE due_date::date < CURRENT_DATE)      AS overdue,
                COUNT(*) FILTER (WHERE due_date::date = CURRENT_DATE)      AS due_today,
                COUNT(*) FILTER (WHERE item_type = 'rfi')                  AS rfis_count,
                COUNT(*) FILTER (WHERE item_type = 'task')                 AS tasks_count,
                COUNT(*) FILTER (WHERE item_type = 'pending_decision')     AS pending_decisions_count,
                COUNT(*) FILTER (WHERE item_type = 'meeting_action_item')  AS meeting_action_items_count
            FROM rex.v_myday
            WHERE user_account_id = $1::uuid
              AND ($2::uuid IS NULL OR project_id = $2::uuid)
            """,
            ctx.user_account_id, ctx.project_id,
        )
        sample = await ctx.conn.fetch(
            """
            SELECT
                v.item_type                 AS item_type,
                v.title                     AS title,
                v.priority                  AS priority,
                v.status                    AS status,
                v.due_date                  AS due_date,
                p.name                      AS project_name
            FROM rex.v_myday v
            JOIN rex.projects p ON p.id = v.project_id
            WHERE v.user_account_id = $1::uuid
              AND ($2::uuid IS NULL OR v.project_id = $2::uuid)
            ORDER BY v.due_date ASC NULLS LAST
            LIMIT 10
            """,
            ctx.user_account_id, ctx.project_id,
        )
        sample_rows = [dict(r) for r in sample]
        display_rows = [
            {
                **r,
                "due_date": (
                    r["due_date"].isoformat() if r.get("due_date") else "(no due date)"
                ),
            }
            for r in sample_rows
        ]

        total = int(row["total_items"] or 0)
        stats = {
            "total_items": total,
            "overdue": int(row["overdue"] or 0),
            "due_today": int(row["due_today"] or 0),
            "by_type": {
                "rfi":                 int(row["rfis_count"] or 0),
                "task":                int(row["tasks_count"] or 0),
                "pending_decision":    int(row["pending_decisions_count"] or 0),
                "meeting_action_item": int(row["meeting_action_items_count"] or 0),
            },
        }

        summary = [
            f"Items on your plate: {total}",
            f"Overdue: {stats['overdue']}, Due today: {stats['due_today']}",
            f"By type: {stats['by_type']['rfi']} RFI(s), "
            f"{stats['by_type']['task']} task(s), "
            f"{stats['by_type']['pending_decision']} decision(s), "
            f"{stats['by_type']['meeting_action_item']} meeting item(s)",
        ]

        return ActionResult(
            stats=stats,
            sample_rows=sample_rows,
            prompt_fragment=_render_fragment(
                slug=self.slug,
                scope_label=(
                    "your items (project-scoped)" if ctx.project_id
                    else "your items across all your projects"
                ),
                summary_lines=summary,
                table_header=["project_name", "item_type", "title", "priority", "status", "due_date"],
                rows=display_rows,
                empty_message="Nothing on your plate right now — inbox zero.",
            ),
        )


__all__ = ["Handler"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && py -m pytest tests/services/ai/actions/test_my_day_briefing.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/actions/my_day_briefing.py \
        backend/tests/services/ai/actions/test_my_day_briefing.py
git commit -m "feat(ai): my_day_briefing handler reads rex.v_myday"
```

---

### Task 12: Flip catalog readiness states from `alpha` to `live`

**Files:**
- Modify: `backend/app/data/quick_actions_catalog.py`
- Modify: `backend/tests/test_quick_actions_catalog.py`

- [ ] **Step 1: Find the 8 entries in the catalog**

Open `backend/app/data/quick_actions_catalog.py`. Search for each of these slugs:
- `rfi_aging`, `submittal_sla`, `budget_variance`, `daily_log_summary`, `critical_path_delays`, `two_week_lookahead`, `documentation_compliance`, `my_day_briefing`

Each will appear in an `_entry(...)` call with `"alpha"` as one of the arguments.

- [ ] **Step 2: Write the failing regression test**

Open `backend/tests/test_quick_actions_catalog.py` and add this test at the bottom:

```python
WAVE1_LIVE_SLUGS = frozenset({
    "rfi_aging",
    "submittal_sla",
    "budget_variance",
    "daily_log_summary",
    "critical_path_delays",
    "two_week_lookahead",
    "documentation_compliance",
    "my_day_briefing",
})


def test_wave1_alpha_actions_are_now_live():
    """Phase 5 Wave 1 alpha handlers were wired to real SQL; the catalog
    must reflect readiness_state='live' for the 8 slugs."""
    from app.data.quick_actions_catalog import CATALOG_ENTRIES
    by_slug = {e["slug"]: e for e in CATALOG_ENTRIES}
    for slug in WAVE1_LIVE_SLUGS:
        assert slug in by_slug, f"missing catalog entry for {slug!r}"
        assert by_slug[slug]["readiness_state"] == "live", (
            f"{slug} is still {by_slug[slug]['readiness_state']!r}, "
            "expected 'live' after Phase 5 Wave 1 wiring"
        )
```

(If the existing catalog file exposes entries under a different name than `CATALOG_ENTRIES`, adjust the import in the test. Look at the top of `quick_actions_catalog.py` for the exported name.)

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd backend && py -m pytest tests/test_quick_actions_catalog.py::test_wave1_alpha_actions_are_now_live -v`
Expected: FAIL — all 8 slugs still have `"alpha"`.

- [ ] **Step 4: Flip the 8 entries to `"live"`**

For each of the 8 slugs in `backend/app/data/quick_actions_catalog.py`, change `"alpha"` to `"live"` in that specific `_entry(...)` call. Example diff:

```python
# before
_entry("rfi_aging",      ["A-9",   "A-22"], "RFI Aging",      "PROJECT_MGMT", ...,
       _P_PROJECT_OPT, "alpha", ["procore"], _R_PM_LEAD),

# after
_entry("rfi_aging",      ["A-9",   "A-22"], "RFI Aging",      "PROJECT_MGMT", ...,
       _P_PROJECT_OPT, "live",  ["procore"], _R_PM_LEAD),
```

Do this for all 8 slugs. Do NOT touch any other catalog entry.

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd backend && py -m pytest tests/test_quick_actions_catalog.py::test_wave1_alpha_actions_are_now_live -v`
Expected: PASS.

Then run the full catalog test file to be sure no other catalog invariant broke:

```
cd backend && py -m pytest tests/test_quick_actions_catalog.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/data/quick_actions_catalog.py \
        backend/tests/test_quick_actions_catalog.py
git commit -m "feat(ai): flip 8 Wave 1 quick actions from alpha to live in catalog"
```

---

### Task 13: Full-suite regression + live smoke (manual operator step)

**Files:** none.

- [ ] **Step 1: Run the full backend test suite locally**

```
cd backend && py -m pytest tests/ -q
```

Expected: previous baseline (767 passed, 1 skipped from Phase 4) + the new tests from Tasks 1–12. Rough expected total: **~815 passed** (45 existing procore tests + ~40 new handler/base/dispatcher/chat-inject tests). Zero regressions.

If anything that was passing before is now failing, investigate and fix before moving on.

- [ ] **Step 2: Push the branch + open a draft PR**

```
git push origin feat/phase5-wave1-alpha-actions
gh pr create --draft --base main \
  --title "feat: Phase 5 Wave 1 — wire 8 alpha quick actions to real SQL" \
  --body "Implements docs/superpowers/plans/2026-04-21-phase5-wave1-alpha-actions.md. 8 handlers + shared dispatcher + catalog flip. Draft until demo smoke completes."
```

- [ ] **Step 3: Wait for CI to go green**

```
gh pr checks --watch
```

Expected: Backend pytest + migrations — pass. Frontend — pass. Vercel — pass.

If Backend pytest fails, diagnose from the CI log (`gh run view <run_id> --log-failed`) and push fixes.

- [ ] **Step 4: Merge to main + let demo + prod auto-deploy**

Demo doesn't auto-deploy from main, so after merge:

```
gh pr merge <n> --merge
# Demo Railway needs a forced redeploy because it doesn't watch main.
railway link --workspace "exxir's Projects" --project "Rex OS" --environment demo --service rex-os
railway redeploy --yes --service rex-os
# Poll demo's /api/version until it reflects the merge commit.
```

- [ ] **Step 5: Live smoke on demo**

Log in as `aroberts@exxircapital.com / rex2026!` on demo. In the sidebar, click each of the 8 quick actions in sequence:
- rfi_aging
- submittal_sla
- budget_variance
- daily_log_summary
- critical_path_delays
- two_week_lookahead
- documentation_compliance
- my_day_briefing

For each click, verify the assistant's reply:
- Contains real numbers (counts) — not "I don't have that data".
- References at least one real project name (if scope is non-empty).
- The LLM's reply visibly echoes the `Total X: N` line from the prompt fragment.

If any action returns a "temporarily unavailable" message, check Rex OS demo's backend logs for the underlying SQL error, file a bug, and include that slug in a follow-up plan.

- [ ] **Step 6: Flip PR out of draft + request review from self (meaningless formality) + merge**

```
gh pr ready <n>
```

Or if already merged in Step 4, you're done.

- [ ] **Step 7: Update the handoff doc**

Edit `docs/SESSION_HANDOFF_2026_04_20.md` (or create a new `SESSION_HANDOFF_2026_04_21.md`):
- Mark Wave 1 alpha actions as live.
- Note that 4 adapter_pending actions remain (change_event_sweep, inspection_pass_fail, schedule_variance, lookahead_status) — those unblock once Phase 4 resource rollout ships the connector data for submittals/daily_logs/tasks/change_events.

Commit the handoff update directly to main.

---

## Self-review

**Spec coverage check** (against `docs/superpowers/specs/2026-04-21-phase5-wave1-alpha-actions-design.md`):

- [x] Goal — all 8 alpha actions wired to real SQL, catalog flipped. Tasks 4–12.
- [x] Dispatch pattern A (enrich the chat) — Task 3.
- [x] Project scoping B (portfolio default + single-project when page-scoped) — Task 1's `resolve_scope_project_ids`; used by all 8 handlers.
- [x] Output shape B (pre-computed stats + sample rows) — each handler emits `ActionResult` with all three fields; `_render_fragment` standardizes the markdown.
- [x] Error handling — Task 2's dispatcher catches; handlers themselves raise only in programmer-error paths; empty results return valid `ActionResult`.
- [x] Catalog flip — Task 12.
- [x] Live smoke — Task 13.

**Placeholder scan:** none. Every step has real code + expected output. Handler SQL uses verified column names from the "Verified view / table shapes" block at the top of this plan.

**Type consistency:**
- `ActionContext.user_account_id` is `UUID` in Task 1. Used as `UUID` in all handlers. Task 3's chat-service wiring passes `user.user_id` which is already a `UUID`.
- `ActionResult.stats: dict[str, Any]`, `sample_rows: list[dict]`, `prompt_fragment: str` — consistent across all handlers.
- `Handler.slug` is `str` on every handler.
- `_render_fragment` signature is defined in Task 4 and used identically in Tasks 5–11.

**Known scope question:** Task 13 Step 4's manual "railway redeploy" step duplicates Phase 4's workaround. That's acceptable — fixing the demo-watches-main config is a separate one-time Railway UI change, not in scope here.

---

## Follow-ups (not in this plan)

- **4 adapter_pending actions** (`change_event_sweep`, `inspection_pass_fail`, `schedule_variance`, `lookahead_status`) — blocked on Phase 4 resource rollout.
- **Frontend table rendering** — the sample_rows are currently only consumed via the LLM's markdown pass-through. A future plan could add a structured card UI that reads the stats/sample_rows JSON directly, bypassing the LLM entirely for that rendering slot.
- **People-FK resolution** — `assigned_to_person_id` / `ball_in_court_person_id` are surfaced as UUIDs; a follow-up could join them to `rex.people` and show names in the sample_row tables.
- **Working-day SLA math for submittal_sla** — currently uses calendar days; a follow-up could switch to business-day math using a holidays table.
