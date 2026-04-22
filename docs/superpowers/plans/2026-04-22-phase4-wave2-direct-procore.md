# Phase 4 Wave 2 — Direct Procore API Read Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land 5 Procore resources (submittals, daily_logs, schedule_activities, change_events, inspections) from Procore REST API directly into Rex OS canonical tables. Reuses Phase 4a's orchestrator + staging → canonical pattern; only the adapter swaps from "SELECT from rex-procore DB" to "HTTP GET from Procore API."

**Architecture:** Extend `ProcoreClient` (Phase 6a's `backend/app/services/ai/tools/procore_api.py`) with 5 new `list_<resource>()` methods. Adapter layer uses that client per-project; orchestrator follows existing pattern. 1 new migration (inspections_raw staging + sync_runs cursor column). Scheduler job added to existing apscheduler.

**Tech Stack:** Python 3.11, FastAPI, asyncpg + SQLAlchemy async, httpx (Procore API client), apscheduler (existing), pytest-asyncio.

---

## Scope note — what already exists from Phase 4a

**Already done:**
- Migration 013 created `connector_procore.projects_raw | users_raw | rfis_raw | submittals_raw | daily_logs_raw | change_events_raw | schedule_tasks_raw | documents_raw | commitments_raw | budget_line_items_raw`. **4 of our 5 Wave 2 staging tables already exist.**
- `backend/app/services/connectors/procore/adapter.py::ProcoreAdapter` has stub methods for `fetch_submittals`, `fetch_daily_logs`, `fetch_change_events`, `fetch_schedule` (all currently return empty pages).
- `mapper.py` has `map_submittal` stub (and `map_commitment` — out of scope).
- `payloads.py` has `build_project_payload`, `build_user_payload`, `build_vendor_payload`, `build_rfi_payload`.
- `_CANONICAL_WRITERS` in `orchestrator.py` has entries for `rfis | projects | people | companies`.
- apscheduler running 5 jobs on prod. Demo scheduler disabled.
- `ProcoreClient` in `backend/app/services/ai/tools/procore_api.py` — OAuth refresh flow + `answer_rfi` POST endpoint working.

**Missing (what this plan adds):**
- `connector_procore.inspections_raw` — 1 new staging table.
- `rex.sync_runs.cursor_watermark` — 1 new column.
- 5 new `ProcoreClient.list_<resource>()` HTTP methods + pagination helper.
- 5 real implementations in the adapter (fill in the stubs) + 1 new `fetch_inspections`.
- 5 new real mapper functions.
- 5 new canonical writers + `_CANONICAL_WRITERS` entries.
- 1 new apscheduler job.
- 4 quick action catalog flips (`adapter_pending` → `live`) + migration 008 regen.

**Architectural decision for implementer:** The current `ProcoreAdapter` reads from the rex-procore DB via `RexAppDbClient`. The 5 new resource fetches need to go to Procore API via `ProcoreClient`. Two paths:

- **A. Extend the existing `ProcoreAdapter`**: fill in the stub fetch methods to call `ProcoreClient` directly. Docstring updates. Simpler diff.
- **B. New `ProcoreApiAdapter` class**: separate adapter for API-based fetches; orchestrator picks one based on resource type. Cleaner separation but adapter-resolution logic changes.

**Task 1 Step 1** is a discovery step where the implementer reads the existing adapter + orchestrator + picks one. Plan assumes **A** (extend existing) for simplicity but either is acceptable.

---

## File structure

**New files:**
- `migrations/030_connector_procore_inspections_raw.sql`
- `backend/app/services/connectors/procore/scheduler_job.py` — the apscheduler job function
- `backend/tests/services/connectors/procore/test_procore_client_list_methods.py` — tests for the 5 new list_<resource>() methods
- `backend/tests/services/connectors/procore/test_adapter_fetch_submittals_api.py`
- `backend/tests/services/connectors/procore/test_adapter_fetch_daily_logs_api.py`
- `backend/tests/services/connectors/procore/test_adapter_fetch_schedule_activities_api.py`
- `backend/tests/services/connectors/procore/test_adapter_fetch_change_events_api.py`
- `backend/tests/services/connectors/procore/test_adapter_fetch_inspections_api.py`

**Modified files:**
- `backend/app/services/ai/tools/procore_api.py` — add 5 `list_<resource>()` methods + pagination helper
- `backend/app/services/connectors/procore/adapter.py` — replace stub fetch_* methods with real API calls; add fetch_inspections
- `backend/app/services/connectors/procore/payloads.py` — 5 new `build_<resource>_payload()` helpers
- `backend/app/services/connectors/procore/mapper.py` — 5 new real mapper functions (extending the submittals stub, adding 4 new)
- `backend/app/services/connectors/procore/orchestrator.py` — 5 new `_write_*` functions + `_CANONICAL_WRITERS` entries
- `backend/app/scheduler.py` (or wherever apscheduler lives) — register `procore_api_sync` job
- `backend/app/routes/admin_connectors.py` — extend resource enum with 5 new values
- `backend/app/data/quick_actions_catalog.py` — flip 4 slugs from `adapter_pending` → `live`
- `migrations/008_ai_action_catalog_seed.sql` — regen to match catalog

---

## Task 1: Procore API endpoint discovery + `ProcoreClient.list_<resource>()` methods

**Files:**
- Modify: `backend/app/services/ai/tools/procore_api.py`
- Create: `backend/tests/services/connectors/procore/test_procore_client_list_methods.py`

**Why first:** Establishes the foundation. Every later task uses these methods. Discovery happens here: confirm exact Procore endpoint paths + query-param shapes before other tasks start coding against them.

- [ ] **Step 1: Discovery — confirm Procore endpoint paths.**

Read Procore's REST API docs for these 5 endpoints. Confirm:
- Exact path (e.g. `/rest/v1.0/projects/{project_id}/submittals`)
- Query parameter for `updated_since` filter (Procore uses various — `filters[updated_at]=`, `updated_at_min=`, depending on endpoint)
- Response envelope: does it return `{data: [...]}` or a bare array?
- Pagination headers (`Link:` / `X-Total:` / `X-Per-Page:`) vs query-param-based page iteration
- Company-ID header requirement: `Procore-Company-Id: <id>`

Record findings as comments at the top of `procore_api.py` for future maintainers.

- [ ] **Step 2: Write failing test for pagination helper + all 5 list methods.**

Create `backend/tests/services/connectors/procore/test_procore_client_list_methods.py`:

```python
"""Tests for ProcoreClient.list_<resource>() methods.

Mocks httpx.AsyncBaseTransport via httpx.MockTransport to return canned
Procore API responses. Asserts pagination loop terminates, company header
is set, updated_since is passed correctly.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest

from app.services.ai.tools.procore_api import ProcoreClient


def _mk_client(handler) -> ProcoreClient:
    transport = httpx.MockTransport(handler)
    return ProcoreClient(
        client_id="x", client_secret="x", refresh_token="x",
        company_id="42", base_url="https://api.procore.com",
        _transport=transport,
    )


def _token_handler_factory():
    """Returns a handler that issues a token on /oauth/token + delegates
    the rest to the caller-provided data_handler."""
    def wrap(data_handler):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/oauth/token":
                return httpx.Response(200, json={
                    "access_token": "tok", "expires_in": 3600,
                })
            return data_handler(request)
        return handler
    return wrap


@pytest.mark.asyncio
async def test_list_submittals_single_page():
    def data(req):
        assert req.url.path == "/rest/v1.0/projects/99/submittals"
        assert req.headers.get("Procore-Company-Id") == "42"
        return httpx.Response(200, json=[
            {"id": 1, "number": "SUB-1", "title": "A"},
            {"id": 2, "number": "SUB-2", "title": "B"},
        ])
    client = _mk_client(_token_handler_factory()(data))
    rows = await client.list_submittals(project_id="99", updated_since=None)
    assert len(rows) == 2
    assert rows[0]["number"] == "SUB-1"


@pytest.mark.asyncio
async def test_list_submittals_pagination_loop_terminates():
    """Two pages then an empty page — loop should stop."""
    pages = [
        [{"id": 1}, {"id": 2}, {"id": 3}],  # full page
        [{"id": 4}, {"id": 5}, {"id": 6}],  # full page
        [],                                  # empty — stop
    ]
    idx = [0]
    def data(req):
        assert req.url.path == "/rest/v1.0/projects/99/submittals"
        page = pages[idx[0]]
        idx[0] += 1
        return httpx.Response(200, json=page)
    client = _mk_client(_token_handler_factory()(data))
    rows = await client.list_submittals(project_id="99", per_page=3)
    assert len(rows) == 6


@pytest.mark.asyncio
async def test_list_submittals_updated_since_filter():
    def data(req):
        # Whatever query-param name Procore actually uses; verify it's
        # passed when updated_since is provided.
        q = dict(req.url.params)
        assert any("updated" in k.lower() for k in q), f"no updated filter in {q}"
        return httpx.Response(200, json=[])
    client = _mk_client(_token_handler_factory()(data))
    since = datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc)
    await client.list_submittals(project_id="99", updated_since=since)


# Parallel tests for list_daily_logs, list_schedule_tasks,
# list_change_events, list_inspections — same shape:
#   test_list_<resource>_single_page
#   test_list_<resource>_pagination_loop_terminates
# Omit the updated_since filter test for the other 4 (the mechanism is
# shared between all 5 methods — one test covers the behavior).
```

Add `single_page` + `pagination_loop_terminates` tests for each of the 4 remaining resources (same shape, different paths).

- [ ] **Step 3: Verify failure.**

```
cd backend && py -m pytest tests/services/connectors/procore/test_procore_client_list_methods.py -v 2>&1 | tail -10
```

Expected: FAIL — the methods don't exist yet.

- [ ] **Step 4: Implement the 5 methods + pagination helper in `procore_api.py`.**

At module level, add:

```python
from datetime import datetime
from typing import Any

DEFAULT_PAGE_SIZE = 100
```

On `ProcoreClient`, add a private pagination helper:

```python
async def _paginate(
    self,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    per_page: int = DEFAULT_PAGE_SIZE,
) -> list[dict[str, Any]]:
    """Loop Procore's page-number pagination until an empty page arrives.
    All rows merged into a single list."""
    rows: list[dict[str, Any]] = []
    page = 1
    while True:
        q = dict(params or {})
        q["page"] = page
        q["per_page"] = per_page
        headers = await self._auth_headers()
        client = await self._get_client()
        r = await client.get(path, params=q, headers=headers)
        if r.status_code == 429:
            # Rate limit — respect Retry-After up to 3 attempts, then skip page.
            for attempt in range(3):
                retry_after = int(r.headers.get("Retry-After", "5"))
                import asyncio
                await asyncio.sleep(retry_after)
                r = await client.get(path, params=q, headers=headers)
                if r.status_code != 429:
                    break
            if r.status_code == 429:
                raise ProcoreApiError(f"rate limit exhausted on {path} page={page}")
        r.raise_for_status()
        body = r.json()
        batch = body if isinstance(body, list) else body.get("data", [])
        if not batch:
            return rows
        rows.extend(batch)
        if len(batch) < per_page:
            return rows
        page += 1
```

And `_auth_headers`:

```python
async def _auth_headers(self) -> dict[str, str]:
    token = await self._ensure_token()
    return {
        "Authorization": f"Bearer {token}",
        "Procore-Company-Id": self.company_id,
    }
```

Then the 5 list methods (use the endpoint paths discovered in Step 1 — this is best-knowledge stub; update with real paths):

```python
async def list_submittals(
    self, project_id: str, *,
    updated_since: datetime | None = None,
    per_page: int = DEFAULT_PAGE_SIZE,
) -> list[dict]:
    params: dict[str, Any] = {}
    if updated_since is not None:
        params["filters[updated_at]"] = updated_since.isoformat()
    return await self._paginate(
        f"/rest/v1.0/projects/{project_id}/submittals",
        params=params, per_page=per_page,
    )


async def list_daily_logs(
    self, project_id: str, *,
    updated_since: datetime | None = None,
    per_page: int = DEFAULT_PAGE_SIZE,
) -> list[dict]:
    params: dict[str, Any] = {}
    if updated_since is not None:
        # daily_logs filter by log_date (Procore's convention for this endpoint).
        params["log_date"] = updated_since.date().isoformat()
    return await self._paginate(
        f"/rest/v1.0/projects/{project_id}/daily_logs/construction_report_logs",
        params=params, per_page=per_page,
    )


async def list_schedule_tasks(
    self, project_id: str, *,
    updated_since: datetime | None = None,
    per_page: int = DEFAULT_PAGE_SIZE,
) -> list[dict]:
    params: dict[str, Any] = {}
    if updated_since is not None:
        params["updated_at_min"] = updated_since.isoformat()
    return await self._paginate(
        f"/rest/v1.0/projects/{project_id}/schedule/standard_tasks",
        params=params, per_page=per_page,
    )


async def list_change_events(
    self, project_id: str, *,
    updated_since: datetime | None = None,
    per_page: int = DEFAULT_PAGE_SIZE,
) -> list[dict]:
    params: dict[str, Any] = {}
    if updated_since is not None:
        params["filters[updated_at]"] = updated_since.isoformat()
    return await self._paginate(
        f"/rest/v1.0/projects/{project_id}/change_events",
        params=params, per_page=per_page,
    )


async def list_inspections(
    self, project_id: str, *,
    updated_since: datetime | None = None,
    per_page: int = DEFAULT_PAGE_SIZE,
) -> list[dict]:
    params: dict[str, Any] = {}
    if updated_since is not None:
        params["updated_at"] = updated_since.isoformat()
    # Procore's inspection endpoint name may differ — inspection_lists,
    # checklist/list_item_inspections, etc. Confirm in Step 1.
    return await self._paginate(
        f"/rest/v1.0/projects/{project_id}/inspection_lists",
        params=params, per_page=per_page,
    )
```

- [ ] **Step 5: Verify tests pass.**

```
cd backend && py -m pytest tests/services/connectors/procore/test_procore_client_list_methods.py -v 2>&1 | tail -15
```

Expected: all PASS.

- [ ] **Step 6: Regression.**

```
cd backend && py -m pytest tests/services/ai/tools/test_procore_api.py tests/services/ai/tools/test_answer_rfi.py --tb=line -q 2>&1 | tail -3
```

Expected: still pass. Don't break `answer_rfi`.

- [ ] **Step 7: Commit.**

```bash
git add backend/app/services/ai/tools/procore_api.py backend/tests/services/connectors/procore/test_procore_client_list_methods.py
git commit -m "feat(p4w2): ProcoreClient list_<resource> methods + pagination helper"
```

---

## Task 2: Migration — inspections_raw + sync_runs cursor_watermark

**Files:**
- Create: `migrations/030_connector_procore_inspections_raw.sql`

- [ ] **Step 1: Write the migration.**

Create `migrations/030_connector_procore_inspections_raw.sql` (mirror the existing `connector_procore.submittals_raw` shape from migration 013):

```sql
-- Migration 030 — Phase 4 Wave 2: inspections staging table +
-- sync_runs cursor column for direct-Procore-API polling.

CREATE TABLE IF NOT EXISTS connector_procore.inspections_raw (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id           text NOT NULL,
    account_id          uuid NOT NULL REFERENCES rex.connector_accounts(id) ON DELETE CASCADE,
    project_source_id   text NOT NULL,
    payload             jsonb NOT NULL,
    fetched_at          timestamptz NOT NULL DEFAULT now(),
    source_updated_at   timestamptz,
    checksum            text,
    UNIQUE (account_id, source_id)
);

CREATE INDEX IF NOT EXISTS idx_cp_inspections_raw_project
    ON connector_procore.inspections_raw (project_source_id);
CREATE INDEX IF NOT EXISTS idx_cp_inspections_raw_updated
    ON connector_procore.inspections_raw (source_updated_at DESC);

-- cursor_watermark: per-run high-water-mark of the source_updated_at seen
-- during that run. The next run reads MAX(cursor_watermark) WHERE status
-- = 'success' AND resource_type = $1 AND connector_account_id = $2 and
-- uses it as updated_since. NULL on first run = full pull.
ALTER TABLE rex.sync_runs
    ADD COLUMN IF NOT EXISTS cursor_watermark timestamptz;
```

- [ ] **Step 2: Verify the migration applies cleanly.**

If there's an integration test runner for migrations, run it. Otherwise apply manually in a scratch db and inspect.

```
cd backend && py -c "
import asyncio
from app.migrate import run_migrations
asyncio.run(run_migrations())
" 2>&1 | tail -3
```

Expected: `Migration applied: 030_connector_procore_inspections_raw.sql` + `auto_migrate complete applied=N failed=0`.

- [ ] **Step 3: Verify the table exists + column added.**

```python
# quick REPL: connect to dev DB and
# SELECT 1 FROM connector_procore.inspections_raw LIMIT 0;
# SELECT cursor_watermark FROM rex.sync_runs LIMIT 0;
```

- [ ] **Step 4: Commit.**

```bash
git add migrations/030_connector_procore_inspections_raw.sql
git commit -m "feat(p4w2): migration 030 — inspections_raw staging + sync_runs.cursor_watermark"
```

---

## Task 3: Submittals end-to-end

**Files:**
- Modify: `backend/app/services/connectors/procore/adapter.py` (replace `fetch_submittals` stub)
- Modify: `backend/app/services/connectors/procore/payloads.py` (add `build_submittal_payload`)
- Modify: `backend/app/services/connectors/procore/mapper.py` (extend `map_submittal` stub into real)
- Modify: `backend/app/services/connectors/procore/orchestrator.py` (add `_write_submittals` + registry entry)
- Create: `backend/tests/services/connectors/procore/test_adapter_fetch_submittals_api.py`
- Modify: `backend/tests/services/connectors/procore/test_mapper.py` (extend with submittal mapping tests)
- Modify: `backend/tests/services/connectors/procore/test_orchestrator.py` (extend with submittals write tests)

This is the longest task — it's the first end-to-end wiring. Tasks 4–7 follow the same shape and will be faster.

- [ ] **Step 1: Architectural decision.**

Read `backend/app/services/connectors/procore/adapter.py` in full. Note that the class uses `RexAppDbClient` to read from the old rex-procore DB. Decide whether to:
- **A. Extend the existing `ProcoreAdapter`** — replace the stub `fetch_submittals` with a call to `ProcoreClient.list_submittals`. Adapter becomes hybrid (DB for projects/users/vendors, API for submittals/etc.).
- **B. Add a `ProcoreApiAdapter`** class — separate API-based adapter; orchestrator dispatches based on resource type.

Recommendation: **A**. Simpler diff. The class docstring updates to reflect hybrid behavior.

If you pick B, the rest of this plan's module references stay the same — just add `ProcoreApiAdapter` alongside `ProcoreAdapter` and route the 5 new resources to it.

- [ ] **Step 2: Write failing adapter test.**

Create `backend/tests/services/connectors/procore/test_adapter_fetch_submittals_api.py`:

```python
"""Adapter.fetch_submittals uses ProcoreClient.list_submittals, wraps
the response in ConnectorPage shape, passes updated_since from the
cursor."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.services.connectors.procore.adapter import ProcoreAdapter


@pytest.mark.asyncio
async def test_fetch_submittals_returns_page_shape():
    adapter = ProcoreAdapter(account_id=str(uuid4()))
    fake_rows = [
        {"id": 101, "number": "SUB-1", "title": "A"},
        {"id": 102, "number": "SUB-2", "title": "B"},
    ]
    with patch(
        "app.services.connectors.procore.adapter.ProcoreClient.from_env",
    ) as mk_client:
        client = AsyncMock()
        client.list_submittals = AsyncMock(return_value=fake_rows)
        mk_client.return_value = client
        page = await adapter.fetch_submittals(
            project_external_id="99",
            cursor=None,
        )
        assert len(page.records) == 2
        assert page.records[0]["source_id"] == "101"
        client.list_submittals.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_submittals_passes_cursor_as_updated_since():
    adapter = ProcoreAdapter(account_id=str(uuid4()))
    cursor_iso = "2026-04-22T10:00:00+00:00"
    with patch(
        "app.services.connectors.procore.adapter.ProcoreClient.from_env",
    ) as mk_client:
        client = AsyncMock()
        client.list_submittals = AsyncMock(return_value=[])
        mk_client.return_value = client
        await adapter.fetch_submittals(project_external_id="99", cursor=cursor_iso)
        kw = client.list_submittals.await_args.kwargs
        assert kw.get("updated_since") is not None
        assert kw["updated_since"].tzinfo is not None
```

- [ ] **Step 3: Verify failure.**

```
cd backend && py -m pytest tests/services/connectors/procore/test_adapter_fetch_submittals_api.py -v 2>&1 | tail -10
```

Expected: FAIL — `fetch_submittals` currently returns an empty page, `ProcoreClient` is not imported.

- [ ] **Step 4: Implement `fetch_submittals` in `adapter.py`.**

Add the import at the top of `adapter.py`:

```python
from datetime import datetime, timezone
from app.services.ai.tools.procore_api import ProcoreClient, ProcoreNotConfigured
from app.services.connectors.procore.payloads import build_submittal_payload
```

Replace the existing stub `fetch_submittals`:

```python
async def fetch_submittals(
    self, project_external_id: str, cursor: str | None = None,
) -> ConnectorPage:
    try:
        client = ProcoreClient.from_env()
    except ProcoreNotConfigured:
        return ConnectorPage(records=[], next_cursor=None)
    updated_since = None
    if cursor is not None:
        updated_since = datetime.fromisoformat(cursor)
    rows = await client.list_submittals(
        project_id=project_external_id,
        updated_since=updated_since,
    )
    records = [build_submittal_payload(project_external_id, r) for r in rows]
    return ConnectorPage(records=records, next_cursor=None)
```

- [ ] **Step 5: Implement `build_submittal_payload` in `payloads.py`.**

```python
def build_submittal_payload(project_external_id: str, raw: dict) -> dict:
    """Normalize a Procore submittal API row into staging-table shape."""
    return {
        "source_id": str(raw["id"]),
        "project_source_id": str(project_external_id),
        "payload": raw,
        "source_updated_at": raw.get("updated_at"),
    }
```

- [ ] **Step 6: Verify adapter tests pass.**

```
cd backend && py -m pytest tests/services/connectors/procore/test_adapter_fetch_submittals_api.py -v 2>&1 | tail -10
```

Expected: 2 PASS.

- [ ] **Step 7: Write mapper tests.**

Extend `backend/tests/services/connectors/procore/test_mapper.py` with a test for `map_submittal`:

```python
def test_map_submittal_normalizes_fields():
    raw = {
        "id": 123,
        "number": "SUB-42",
        "title": "Structural steel shop drawings",
        "submittal_type": "shop_drawing",
        "status": "open",
        "due_date": "2026-05-15",
        "submitted_date": "2026-04-20",
        "approved_date": None,
    }
    resolver = _FakeResolver(project_id=uuid4())  # resolves procore project id → rex uuid
    out = map_submittal(raw, resolver=resolver)
    assert out["submittal_number"] == "SUB-42"
    assert out["title"] == "Structural steel shop drawings"
    assert out["submittal_type"] == "shop_drawing"
    assert out["status"] == "open"
    # Sentinels: unknown values fall back to safe defaults
    raw2 = {**raw, "status": "weird_procore_status"}
    out2 = map_submittal(raw2, resolver=resolver)
    assert out2["status"] == "open"  # or whatever your fallback is


def test_map_submittal_returns_none_when_project_not_resolved():
    raw = {"id": 123, "number": "S", "title": "X", "submittal_type": "shop_drawing"}
    resolver = _FakeResolver(project_id=None)  # not resolved
    out = map_submittal(raw, resolver=resolver)
    assert out is None
```

`_FakeResolver` is a test double that returns a fixed rex UUID for any procore_id, or None to simulate "not mapped yet."

- [ ] **Step 8: Implement real `map_submittal` in `mapper.py`.**

Read the existing stub. Extend it to:
- Return `None` if `resolver.project(raw["project_id"])` returns None.
- Produce output matching `rex.submittals`' NOT NULL + CHECK constraints:
  - `project_id` (uuid, resolved)
  - `submittal_number` = raw["number"]
  - `title` = raw["title"]
  - `submittal_type` — normalize to one of `('shop_drawing','product_data','sample','mock_up','quality_submittal','informational_submittal')`. Fallback to `'informational_submittal'`.
  - `status` — normalize to one of rex.submittals 7-value CHECK enum. Fallback to `'draft'`.
  - `due_date`, `submitted_date`, `approved_date` — parse ISO date or None.
  - `assigned_to`, `ball_in_court`, `responsible_contractor` — resolve through resolver.

- [ ] **Step 9: Implement `_write_submittals` in `orchestrator.py`.**

```python
async def _write_submittals(db: AsyncSession, row: dict) -> UUID:
    """Upsert a rex.submittals row by (project_id, submittal_number)."""
    stmt = text(
        """
        INSERT INTO rex.submittals (
            id, project_id, submittal_number, title,
            submittal_type, status,
            due_date, submitted_date, approved_date,
            assigned_to, ball_in_court, responsible_contractor,
            created_at, updated_at
        ) VALUES (
            gen_random_uuid(), :project_id, :submittal_number, :title,
            :submittal_type, :status,
            :due_date, :submitted_date, :approved_date,
            :assigned_to, :ball_in_court, :responsible_contractor,
            now(), now()
        )
        ON CONFLICT (project_id, submittal_number) DO UPDATE SET
            title = EXCLUDED.title,
            submittal_type = EXCLUDED.submittal_type,
            status = EXCLUDED.status,
            due_date = EXCLUDED.due_date,
            submitted_date = EXCLUDED.submitted_date,
            approved_date = EXCLUDED.approved_date,
            updated_at = now()
        RETURNING id
        """
    )
    result = await db.execute(stmt, row)
    return result.scalar_one()
```

Add to `_CANONICAL_WRITERS`:

```python
_CANONICAL_WRITERS["submittals"] = _write_submittals
```

**Note:** `rex.submittals` may not have a unique constraint on `(project_id, submittal_number)` yet. Check `migrations/rex2_canonical_ddl.sql`. If not, this task needs a supplementary migration — like `migrations/025_rex_projects_project_number_unique.sql` did for projects. Add it if missing.

- [ ] **Step 10: Extend orchestrator test.**

```python
@pytest.mark.asyncio
async def test_orchestrator_submittals_end_to_end():
    """Mocked adapter returns 2 canned rows → staging gets 2 rows →
    mapper produces canonical shape → rex.submittals gets 2 rows."""
    # Follows the Phase 4a orchestrator test pattern.
    ...
```

- [ ] **Step 11: Run targeted + regression.**

```
cd backend && py -m pytest tests/services/connectors/procore/ --tb=line -q 2>&1 | tail -5
cd backend && py -m pytest tests/services/ai/ --tb=line -q 2>&1 | tail -3
```

- [ ] **Step 12: Commit.**

```bash
git add backend/app/services/connectors/procore/adapter.py \
        backend/app/services/connectors/procore/payloads.py \
        backend/app/services/connectors/procore/mapper.py \
        backend/app/services/connectors/procore/orchestrator.py \
        backend/tests/services/connectors/procore/
# Add the supplementary migration if needed.
git commit -m "feat(p4w2): submittals end-to-end via direct Procore API"
```

---

## Task 4: daily_logs end-to-end

**Files:** same module set as Task 3 + `test_adapter_fetch_daily_logs_api.py`.

Follow Task 3's steps with these resource-specific notes:

- **Procore endpoint:** `/rest/v1.0/projects/{id}/daily_logs/construction_report_logs` (verify Step 1 finding from Task 1).
- **Staging table:** `connector_procore.daily_logs_raw` already exists from migration 013.
- **Canonical natural key:** `rex.daily_logs` has `UNIQUE(project_id, log_date)`. Writer upserts on that.
- **Mapper:** date is `raw["date"]` (ISO) → `log_date`. Status — Procore has a rich publish state; map `"published"` / `"unpublished"` to rex's 3-value enum (check the DDL).
- **Weather:** Procore returns structured weather (`{conditions, temp_high, temp_low, precipitation}`). Canonical has `weather_summary` (text) + `temp_high_f`, `temp_low_f`, `is_weather_delay`. Compose `weather_summary` from the structured data.

Commit message: `feat(p4w2): daily_logs end-to-end via direct Procore API`

---

## Task 5: schedule_activities end-to-end

**Files:** same as Task 3 + `test_adapter_fetch_schedule_activities_api.py`.

- **Procore endpoint:** `/rest/v1.0/projects/{id}/schedule/standard_tasks` (verify).
- **Staging table:** `connector_procore.schedule_tasks_raw` exists from migration 013.
- **Canonical table:** `rex.schedule_activities`. Check for unique constraint on `(schedule_id, activity_number)` or equivalent. If missing, add migration.
- **Mapper:** Procore returns per-task `id`, `name`, `start_date`, `finish_date`, `percent_complete`. Map to `rex.schedule_activities`. Predecessors / successors are arrays of related task ids — **out of scope for this task** (flag as follow-up; canonical has separate relationship tables that need their own sync). Mapper produces only the activity row; relationships are Wave 2.5.
- **schedule_id FK:** `rex.schedule_activities.schedule_id` → `rex.schedules`. If `rex.schedules` isn't populated yet, you may need to bootstrap one schedule row per project on first sync. Add a helper that does `INSERT ... ON CONFLICT DO NOTHING` on `rex.schedules` before the mapper runs, using the project + a canonical schedule name like "Procore default schedule."

Commit: `feat(p4w2): schedule_activities end-to-end via direct Procore API`

---

## Task 6: change_events end-to-end

Follow Task 3's shape.

- **Procore endpoint:** `/rest/v1.0/projects/{id}/change_events` (verify).
- **Staging table:** `connector_procore.change_events_raw` exists.
- **Canonical natural key:** `rex.change_events` has `UNIQUE(project_id, event_number)` (verify in DDL; add migration if missing).
- **Mapper:** `raw["number"]` → `event_number`. `raw["change_reason"]` and `raw["event_type"]` → normalize to rex's CHECK enums. `raw["estimated_amount"]` → numeric.

Commit: `feat(p4w2): change_events end-to-end via direct Procore API`

---

## Task 7: inspections end-to-end

Follow Task 3's shape.

- **Procore endpoint:** `/rest/v1.0/projects/{id}/inspection_lists` (verify — may be `checklist/list_item_inspections`).
- **Staging table:** newly created in Task 2.
- **Canonical:** `rex.inspections`. Natural key likely `(project_id, inspection_number)`. Verify + add migration if missing.
- **Mapper:** `inspection_type` → rex.inspections CHECK enum. `overall_status` → rex.inspections.status CHECK.

Commit: `feat(p4w2): inspections end-to-end via direct Procore API`

---

## Task 8: Scheduler job

**Files:**
- Create: `backend/app/services/connectors/procore/scheduler_job.py`
- Modify: `backend/app/scheduler.py` (or wherever apscheduler registration lives — check for existing `scheduler_started` log site)
- Create: `backend/tests/services/connectors/procore/test_scheduler_job.py`

- [ ] **Step 1: Write the job function.**

Create `scheduler_job.py`:

```python
"""apscheduler job: poll Procore API every 30 min for 5 Wave 2 resources.

Iterates active connector_accounts with connector='procore', iterates
the project list for each account, iterates 5 resources per project.
Records each iteration as a rex.sync_runs row. Reads the previous run's
cursor_watermark as updated_since for the next run.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.database import get_pool, async_session_factory
from app.services.connectors.procore.adapter import ProcoreAdapter
from app.services.connectors.procore.orchestrator import SyncOrchestrator

log = logging.getLogger("rex.connectors.procore.scheduler")

RESOURCE_TYPES = [
    "submittals", "daily_logs", "schedule_activities",
    "change_events", "inspections",
]


async def procore_api_sync_job() -> None:
    """Top-level scheduler entry."""
    log.info("procore_api_sync_job starting")
    async with async_session_factory() as db:
        # Iterate connector_accounts where connector_id links to procore + is_active.
        accounts = await db.execute(text(
            """
            SELECT ca.id, ca.label
            FROM rex.connector_accounts ca
            JOIN rex.connectors c ON c.id = ca.connector_id
            WHERE c.slug = 'procore' AND ca.status = 'connected'
            """
        ))
        account_rows = accounts.mappings().all()

    for account in account_rows:
        account_id = str(account["id"])
        adapter = ProcoreAdapter(account_id=account_id)
        orchestrator = SyncOrchestrator(adapter=adapter, account_id=account_id)
        for resource_type in RESOURCE_TYPES:
            try:
                await orchestrator.sync(resource_type=resource_type)
                log.info("procore_api_sync ok account=%s resource=%s", account_id, resource_type)
            except Exception:
                log.exception("procore_api_sync FAIL account=%s resource=%s", account_id, resource_type)
                # Don't halt — next resource, next account, next tick.
```

The orchestrator already handles per-project iteration and writes sync_runs rows.

- [ ] **Step 2: Register the job in `scheduler.py`.**

Find where apscheduler registers jobs. Add:

```python
from app.services.connectors.procore.scheduler_job import procore_api_sync_job

scheduler.add_job(
    procore_api_sync_job,
    "cron",
    minute="*/30",
    id="procore_api_sync",
    max_instances=1,
    replace_existing=True,
)
```

Only if `REX_ENABLE_SCHEDULER` is set (match the existing gating pattern — demo stays disabled).

- [ ] **Step 3: Test the job is registered.**

```python
# backend/tests/services/connectors/procore/test_scheduler_job.py
from unittest.mock import AsyncMock, patch
import pytest

from app.services.connectors.procore.scheduler_job import procore_api_sync_job


@pytest.mark.asyncio
async def test_procore_api_sync_job_iterates_all_resources():
    """Given one active connector_account, the job iterates all 5 resource types
    and calls orchestrator.sync() for each."""
    # Mock the DB query to return one account
    # Mock SyncOrchestrator.sync
    # Assert sync called 5 times with the 5 resource type names
    ...
```

Also test that the scheduler registration happens when the env flag is set — match the style of other scheduler tests already in the repo.

- [ ] **Step 4: Commit.**

```bash
git add backend/app/services/connectors/procore/scheduler_job.py backend/app/scheduler.py backend/tests/services/connectors/procore/test_scheduler_job.py
git commit -m "feat(p4w2): apscheduler job procore_api_sync (every 30 min)"
```

---

## Task 9: Admin endpoint enum + quick action catalog flip

**Files:**
- Modify: `backend/app/routes/admin_connectors.py`
- Modify: `backend/app/data/quick_actions_catalog.py`
- Modify: `migrations/008_ai_action_catalog_seed.sql`

- [ ] **Step 1: Extend admin endpoint.**

Find the existing `/api/admin/connectors/{account_id}/sync/{resource}` route. The `resource` path parameter is likely validated against an enum or a list of allowed values. Add: `submittals`, `daily_logs`, `schedule_activities`, `change_events`, `inspections`.

Extend any existing test that asserts the enum shape.

- [ ] **Step 2: Flip quick action catalog.**

In `backend/app/data/quick_actions_catalog.py`, find the 4 entries and change `readiness="adapter_pending"` → `readiness="live"`:

- `change_event_sweep`
- `inspection_pass_fail`
- `schedule_variance`
- `lookahead_status`

- [ ] **Step 3: Regenerate migration 008.**

The catalog seed is maintained as a generated SQL file. Find the regenerator script (likely in `backend/scripts/` or similar — check `git log` for past regenerations). Run it. Commit the changed `migrations/008_ai_action_catalog_seed.sql`.

If no regenerator exists, hand-edit migration 008 to update the readiness field for the 4 slugs.

- [ ] **Step 4: Commit.**

```bash
git add backend/app/routes/admin_connectors.py backend/app/data/quick_actions_catalog.py migrations/008_ai_action_catalog_seed.sql
git commit -m "feat(p4w2): admin endpoint enum + 4 quick actions adapter_pending→live"
```

---

## Task 10: Full regression + PR + deploy + live smoke

**Files:** none (operational)

- [ ] **Step 1: Backend regression.**

```
cd backend && py -m pytest --tb=line -q 2>&1 | tail -5
```

Expected: 977 (baseline) + ~30 new = ~1007 passing, 1 skipped, 0 failed.

- [ ] **Step 2: Push + open PR.**

```bash
git push -u origin feat/phase4-wave2-direct-procore
gh pr create --title "feat: Phase 4 Wave 2 — direct Procore API read sync (5 resources)" --body "$(cat <<'EOF'
## Summary
- 5 Procore resources sync via direct REST API calls (replaces failing rex-procore cron path)
- Scheduled every 30 min via existing apscheduler; updated_at windowing per resource per project
- 4 adapter_pending quick actions flipped to live: change_event_sweep, inspection_pass_fail, schedule_variance, lookahead_status
- 1 migration (inspections_raw staging + sync_runs.cursor_watermark column)
- Operator prerequisite: copy PROCORE_REFRESH_TOKEN from rex-procore → Rex OS prod + demo

## Test plan
- [x] Backend regression: ~1007 passing
- [ ] Operator env vars set on prod + demo
- [ ] Railway prod + demo deploys clean
- [ ] First scheduler tick on prod populates rex.sync_runs + rex.submittals etc.
- [ ] Demo smoke via admin endpoint per-resource

## Out of scope
- Webhooks
- Manpower entries (child of daily_logs)
- Writeback for the 5 (separate wave per spec §5)
- Schedule predecessors/successors

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Monitor CI, then merge.**

Wait for Backend + Frontend + Vercel checks to be green. Then `gh pr merge <N> --merge --delete-branch`.

- [ ] **Step 4: Operator env vars (Andrew does this).**

Pause here. Tell Andrew:
> Set these Railway env vars before I can verify the scheduler runs:
> - Prod: add `PROCORE_REFRESH_TOKEN` (copy from rex-procore Railway env)
> - Demo: add `PROCORE_CLIENT_ID`, `PROCORE_CLIENT_SECRET`, `PROCORE_COMPANY_ID`, `PROCORE_BASE_URL`, `PROCORE_TOKEN_URL`, `PROCORE_REFRESH_TOKEN`
> Restart both services after setting.

- [ ] **Step 5: Railway log check + first-tick verification.**

After operator step + Railway rebuilds:

```
railway link --workspace "exxir's Projects" --project "Rex OS" --environment production --service rex-os-api
railway logs --deployment | tail -30
```

Look for: `scheduler_started job_count=6` (was 5 — one new job). Then wait for the first 30-min tick and check for:
- `procore_api_sync_job starting`
- `procore_api_sync ok account=<uuid> resource=submittals` (× 5 resources)
- No `procore_api_sync FAIL` entries

Query `rex.sync_runs` via the admin endpoint (or direct DB query) to confirm 5+ new rows per connector_account with `status='success'`.

- [ ] **Step 6: Demo smoke via admin endpoint.**

For each of the 5 new resources:

```
curl -sS -X POST -H "Authorization: Bearer <TOKEN>" \
  "https://rex-os-demo.up.railway.app/api/admin/connectors/<account_id>/sync/submittals"
```

Expected: 200 JSON with row counts. Query the demo DB to confirm staging + canonical rows.

- [ ] **Step 7: Update handoff doc.**

Create `docs/SESSION_HANDOFF_2026_04_26.md` noting: Phase 4 Wave 2 direct-Procore shipped, 4 quick actions flipped to live, operator env vars recorded. What's next queued (submittal writeback wave, pay_application/lien_waiver now unblocked on prod, webhooks if needed).

- [ ] **Step 8: Mark umbrella task complete.**

---

## Spec coverage self-review

| Spec section | Task(s) |
|---|---|
| §1 Resource scope (5 resources) | Tasks 3, 4, 5, 6, 7 |
| §2 Architecture (layered flow) | Tasks 3 (pattern) + 4–7 (repeat) |
| §3 Procore OAuth (port refresh_token) | Task 10 Step 4 (operator) |
| §4 ProcoreClient.list_* methods | Task 1 |
| §5 Staging migrations | Task 2 |
| §6 Mappers | Tasks 3–7 (each extends mapper.py) |
| §7 Canonical writers | Tasks 3–7 |
| §8 Orchestrator + scheduler | Task 8 |
| §9 Admin endpoint | Task 9 |
| §10 Error handling | Task 1 (rate limit) + Tasks 3–7 (mapper skip-on-failure) |
| §11 Testing strategy | Each of Tasks 1, 3–8 |
| §12 Deploy sequence | Task 10 |
| §13 Out of scope | Respected |
| §14 Success criteria | Task 10 Steps 5–6 |
| §15 Operator preconditions | Task 10 Step 4 |

## Placeholder scan

Several discovery steps are intentional, not placeholders:
- Task 1 Step 1 — confirm Procore endpoint paths against docs.
- Task 3 Step 1 — architectural decision (A or B) at implementation time.
- Tasks 3–7 include "verify unique constraint on canonical table; add supplementary migration if missing." Whether such migrations are needed depends on the current state of `rex2_canonical_ddl.sql` — the implementer adds them as discovered.
- `_FakeResolver` in mapper tests — implementer builds it matching the existing Phase 4a mapper test pattern (read `test_mapper.py` for precedent).

## Type consistency

- All 5 `ProcoreClient.list_*()` methods share the same signature shape — `(project_id, *, updated_since=None, per_page=DEFAULT_PAGE_SIZE)`.
- All 5 `adapter.fetch_<resource>` methods take `(project_external_id, cursor=None)` and return `ConnectorPage`.
- All 5 `build_<resource>_payload()` helpers emit `{source_id, project_source_id, payload, source_updated_at}`.
- `_CANONICAL_WRITERS` keys match resource_type strings the orchestrator dispatches on (`submittals`, `daily_logs`, `schedule_activities`, `change_events`, `inspections`).

## Follow-ups (not in scope)

- **Webhooks** from Procore — deferred per Q3.
- **Manpower entries** (child of daily_logs).
- **Procore predecessors/successors** for schedule activities.
- **Writeback** for the 5 (future wave, starting with submittals per spec §5).
- **Migrating projects/users/vendors** from rex-procore DB reads to Procore API reads.
- **Rex-procore cron shutdown** — separate op after 1 week of stable direct sync.
- **Commitments + billing_periods** sync — unblocks `pay_application` and `lien_waiver` on prod. Follow-up wave.
