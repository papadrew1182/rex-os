# Phase 4 — Procore Connector (Rex App DB Read Path) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the stubbed Procore adapter's HTTP fetch layer with a read path against the old rex-procore app's "Rex App" Railway Postgres, land data in `connector_procore.*_raw` staging, normalize into canonical `rex.*` tables, and wire the end-to-end orchestrator. Scope this plan to **shared plumbing + RFIs as a proven reference pipeline**; the 10 remaining resources go in a follow-up plan once RFIs is live.

**Architecture:** Rex OS opens a second read-only asyncpg pool against Rex App's public `DATABASE_URL` (cross-Railway-project). The Procore adapter's `fetch_*` methods query `procore.<table>` with `updated_at > cursor ORDER BY updated_at ASC LIMIT N`, build a synthetic JSON payload per row (keys chosen to match what the mapper consumes — not Procore's raw API shape), and return a `ConnectorPage`. A new orchestrator function calls the adapter, upserts into `connector_procore.*_raw` with a content checksum, runs the mapper, upserts into `rex.*`, writes source_links, and advances `rex.sync_cursors`. Sync runs + event log already exist; we only add the glue.

**Tech Stack:** Python 3.11+, FastAPI, asyncpg, SQLAlchemy Async, pytest + pytest-asyncio, PostgreSQL 15. No new third-party deps.

---

## File Structure

**Create:**
- `backend/app/services/connectors/procore/rex_app_pool.py` — dedicated asyncpg pool factory pointed at Rex App's public `DATABASE_URL`, lazy-initialized once per process.
- `backend/app/services/connectors/procore/rex_app_client.py` — `RexAppDbClient` — thin class that takes the pool and exposes one `fetch_rows(schema, table, cursor_col, cursor_value, limit, extra_filters)` coroutine returning a list of `dict` rows.
- `backend/app/services/connectors/procore/payloads.py` — pure functions `build_rfi_payload(row) -> dict`, one per resource. Keys match what the mapper consumes.
- `backend/app/services/connectors/procore/staging.py` — `upsert_raw(db, table, rows, account_id)` — writes items into `connector_procore.<table>_raw` with a stable `checksum` (SHA-256 of canonicalized payload JSON) for dedup.
- `backend/app/services/connectors/procore/orchestrator.py` — `sync_resource(db, account_id, resource_type)` — end-to-end pipeline for one resource type: get cursor → adapter.fetch → staging.upsert_raw → mapper → canonical upsert → source_links → cursor advance → sync_run finalize.
- `backend/tests/services/connectors/procore/__init__.py`
- `backend/tests/services/connectors/procore/test_payloads.py`
- `backend/tests/services/connectors/procore/test_staging.py`
- `backend/tests/services/connectors/procore/test_rex_app_client.py` — uses a pytest fixture that stands up a temporary Postgres schema mimicking `procore.rfis`.
- `backend/tests/services/connectors/procore/test_orchestrator.py` — end-to-end using the same fixture.

**Modify:**
- `backend/app/services/connectors/procore/adapter.py` — replace `ProcoreClient` wiring with `RexAppDbClient`; implement `fetch_rfis` for real; leave the other 10 fetch methods stubbed for now (they come in the follow-up plan).
- `backend/app/services/connectors/procore/mapper.py` — expand `map_rfi` to cover the fields the canonical `rex.rfis` table needs. Leave other map_* stubs as-is.
- `backend/app/services/connectors/procore/client.py` — deprecate (leave file, make class raise a clear "use RexAppDbClient" error on instantiation so any forgotten caller fails loudly).
- `backend/main.py` (app startup/shutdown) — open the Rex App pool on startup, close on shutdown.
- `.env.example` — add `REX_APP_DATABASE_URL` entry with a comment explaining it's the public URL of the old rex-procore Railway Postgres.
- `DEPLOY.md` — add a row under §6 env var reference for `REX_APP_DATABASE_URL`.

**Test approach:**
- Unit tests for `payloads.py`, `mapper.py`, `staging.py` use pure dicts, no DB.
- `rex_app_client` + `orchestrator` integration tests use `pytest` with a throwaway `procore` schema created in the existing Rex OS test DB — we don't need a real Rex App to test the read path, only a schema that *looks* like it.
- Follow the existing test discipline at `backend/tests/test_session2_migration_sanity.py` for fixture conventions.

---

## Prerequisites

Before Task 1, the user must provide the public `DATABASE_URL` for the "Rex App" Railway Postgres service. This value goes into Railway's `REX_APP_DATABASE_URL` env var on both `rex-os` prod and demo environments, and into the developer's local `.env` for the integration tests to run against live data. If the URL isn't available yet, Tasks 1–6 still work (tests use a synthetic schema) but Task 7's live smoke can't run until it's set.

---

### Task 1: Add the second asyncpg pool

**Files:**
- Create: `backend/app/services/connectors/procore/rex_app_pool.py`
- Modify: `backend/main.py` (add startup/shutdown hooks)
- Modify: `.env.example`
- Test: `backend/tests/services/connectors/procore/test_rex_app_pool.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/connectors/procore/test_rex_app_pool.py
import os
import pytest
from app.services.connectors.procore.rex_app_pool import (
    get_rex_app_pool,
    close_rex_app_pool,
)


@pytest.mark.asyncio
async def test_get_rex_app_pool_requires_env_var(monkeypatch):
    monkeypatch.delenv("REX_APP_DATABASE_URL", raising=False)
    # Reset the module-level pool so the test runs against a fresh state.
    import app.services.connectors.procore.rex_app_pool as mod
    mod._pool = None

    with pytest.raises(RuntimeError, match="REX_APP_DATABASE_URL"):
        await get_rex_app_pool()


@pytest.mark.asyncio
async def test_get_rex_app_pool_uses_env_var(monkeypatch):
    # Point at the local rex-os test DB so we actually get a pool back.
    # REX_APP_DATABASE_URL can legitimately *be* the same as DATABASE_URL
    # during local testing — the pool doesn't care.
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    monkeypatch.setenv("REX_APP_DATABASE_URL", url)

    import app.services.connectors.procore.rex_app_pool as mod
    mod._pool = None

    pool = await get_rex_app_pool()
    assert pool is not None

    async with pool.acquire() as conn:
        val = await conn.fetchval("SELECT 1")
        assert val == 1

    await close_rex_app_pool()
    assert mod._pool is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/services/connectors/procore/test_rex_app_pool.py -v`
Expected: FAIL with `ModuleNotFoundError: app.services.connectors.procore.rex_app_pool`.

- [ ] **Step 3: Create the pool factory**

```python
# backend/app/services/connectors/procore/rex_app_pool.py
"""Dedicated asyncpg pool for the "Rex App" Railway Postgres.

This DB is a separate Railway project (under exxir's Railway org) from
Rex OS's own Postgres, so we cannot reach it over .railway.internal and
cannot use the main rex-os pool. Callers go through this module to get
a read-only handle. Never write to Rex App from Rex OS.
"""

from __future__ import annotations

import asyncpg
import os
import ssl

_pool: asyncpg.Pool | None = None


async def get_rex_app_pool() -> asyncpg.Pool:
    global _pool
    if _pool is not None:
        return _pool

    url = os.environ.get("REX_APP_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "REX_APP_DATABASE_URL is not set. Point it at the public "
            "DATABASE_URL of the old rex-procore Railway Postgres "
            "(project 'Rex App' under exxir's Railway org)."
        )

    use_ssl = (
        "railway.internal" not in url
        and "localhost" not in url
        and "127.0.0.1" not in url
    )
    ssl_ctx: ssl.SSLContext | None = None
    if use_ssl:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

    _pool = await asyncpg.create_pool(
        url,
        ssl=ssl_ctx,
        min_size=1,
        max_size=5,
        server_settings={"search_path": "procore,public"},
    )
    return _pool


async def close_rex_app_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


__all__ = ["get_rex_app_pool", "close_rex_app_pool"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/services/connectors/procore/test_rex_app_pool.py -v`
Expected: PASS (or SKIPPED for the second test if `DATABASE_URL` isn't set locally — that's fine).

- [ ] **Step 5: Wire startup/shutdown in main.py**

Open `backend/main.py` and find the existing FastAPI `@app.on_event("startup")` and `@app.on_event("shutdown")` handlers (or lifespan context manager — use whichever pattern the repo already has). Add the Rex App pool lifecycle.

Example if the repo uses `@app.on_event`:

```python
# Near the other imports
from app.services.connectors.procore.rex_app_pool import (
    get_rex_app_pool,
    close_rex_app_pool,
)

# Inside startup handler — after the main DB pool init
try:
    await get_rex_app_pool()
    log.info("rex_app_pool ready")
except RuntimeError as e:
    # Unset env = feature off for this environment. Don't fail boot.
    log.warning("rex_app_pool not initialized: %s", e)

# Inside shutdown handler
await close_rex_app_pool()
```

Exact insertion point depends on current `main.py` layout — match the style of the existing `db.get_pool()` / `db.close_pool()` calls.

- [ ] **Step 6: Add env var entry**

Edit `.env.example` and append:

```
# Old rex-procore Railway DB (public URL from "Rex App" project).
# Leave unset to disable the Procore read path in local dev.
REX_APP_DATABASE_URL=
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/connectors/procore/rex_app_pool.py \
        backend/tests/services/connectors/procore/ \
        backend/main.py \
        .env.example
git commit -m "feat(connectors): add REX_APP_DATABASE_URL pool for Procore read path"
```

---

### Task 2: RexAppDbClient — minimal row-fetch abstraction

**Files:**
- Create: `backend/app/services/connectors/procore/rex_app_client.py`
- Test: `backend/tests/services/connectors/procore/test_rex_app_client.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/connectors/procore/test_rex_app_client.py
import os
import pytest
from datetime import datetime, timezone
from app.services.connectors.procore.rex_app_pool import (
    get_rex_app_pool,
    close_rex_app_pool,
)
from app.services.connectors.procore.rex_app_client import RexAppDbClient


@pytest.fixture
async def pool(monkeypatch):
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    monkeypatch.setenv("REX_APP_DATABASE_URL", url)
    import app.services.connectors.procore.rex_app_pool as mod
    mod._pool = None
    pool = await get_rex_app_pool()
    yield pool
    await close_rex_app_pool()


@pytest.fixture
async def fake_procore_rfis(pool):
    """Create a tiny procore.rfis table, seed 3 rows, clean up."""
    async with pool.acquire() as conn:
        await conn.execute("CREATE SCHEMA IF NOT EXISTS procore")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS procore.rfis (
                procore_id bigint PRIMARY KEY,
                project_id bigint,
                subject text,
                status text,
                updated_at timestamptz
            )
        """)
        await conn.execute("TRUNCATE procore.rfis")
        await conn.executemany(
            "INSERT INTO procore.rfis (procore_id, project_id, subject, status, updated_at) "
            "VALUES ($1, $2, $3, $4, $5)",
            [
                (1, 100, "r1", "open",   datetime(2026, 1, 1, tzinfo=timezone.utc)),
                (2, 100, "r2", "open",   datetime(2026, 1, 2, tzinfo=timezone.utc)),
                (3, 100, "r3", "closed", datetime(2026, 1, 3, tzinfo=timezone.utc)),
            ],
        )
    yield
    async with pool.acquire() as conn:
        await conn.execute("DROP TABLE procore.rfis")


@pytest.mark.asyncio
async def test_fetch_rows_no_cursor_returns_all_ordered(pool, fake_procore_rfis):
    client = RexAppDbClient(pool)
    rows = await client.fetch_rows(
        schema="procore",
        table="rfis",
        cursor_col="updated_at",
        cursor_value=None,
        limit=10,
    )
    assert [r["procore_id"] for r in rows] == [1, 2, 3]


@pytest.mark.asyncio
async def test_fetch_rows_respects_cursor(pool, fake_procore_rfis):
    client = RexAppDbClient(pool)
    rows = await client.fetch_rows(
        schema="procore",
        table="rfis",
        cursor_col="updated_at",
        cursor_value=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc).isoformat(),
        limit=10,
    )
    assert [r["procore_id"] for r in rows] == [2, 3]


@pytest.mark.asyncio
async def test_fetch_rows_respects_limit(pool, fake_procore_rfis):
    client = RexAppDbClient(pool)
    rows = await client.fetch_rows(
        schema="procore",
        table="rfis",
        cursor_col="updated_at",
        cursor_value=None,
        limit=2,
    )
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_fetch_rows_rejects_non_identifier_schema(pool):
    client = RexAppDbClient(pool)
    with pytest.raises(ValueError, match="identifier"):
        await client.fetch_rows(
            schema="public; DROP TABLE foo;",
            table="rfis",
            cursor_col="updated_at",
            cursor_value=None,
            limit=10,
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/services/connectors/procore/test_rex_app_client.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement RexAppDbClient**

```python
# backend/app/services/connectors/procore/rex_app_client.py
"""Read-only client for the Rex App (old rex-procore) Railway Postgres.

Wraps an asyncpg pool with a single generic row-fetch method. The
connector-specific logic (payload shape, ordering, filters) lives in the
adapter layer; this module only knows how to run a safe SELECT.
"""

from __future__ import annotations

import re
from typing import Any

import asyncpg

_IDENT_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def _assert_identifier(name: str, kind: str) -> None:
    """Defense-in-depth: reject anything that isn't a plain SQL identifier.

    Schema/table/column names are concatenated into the query string
    because asyncpg can't parameterize identifiers. All three come from
    code paths we control today (adapter.py constants), but future
    callers could pass user input. Fail fast if it looks suspicious.
    """
    if not _IDENT_RE.match(name):
        raise ValueError(
            f"{kind} {name!r} is not a safe SQL identifier"
        )


class RexAppDbClient:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def fetch_rows(
        self,
        *,
        schema: str,
        table: str,
        cursor_col: str,
        cursor_value: str | None,
        limit: int,
        extra_where: str | None = None,
        extra_params: list[Any] | None = None,
    ) -> list[dict[str, Any]]:
        _assert_identifier(schema, "schema")
        _assert_identifier(table, "table")
        _assert_identifier(cursor_col, "cursor_col")

        params: list[Any] = []
        where_clauses: list[str] = []

        if cursor_value is not None:
            params.append(cursor_value)
            where_clauses.append(f"{cursor_col} > ${len(params)}::timestamptz")

        if extra_where:
            # extra_where uses $N placeholders starting at current count+1
            if extra_params:
                for p in extra_params:
                    params.append(p)
            where_clauses.append(f"({extra_where})")

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        params.append(limit)
        sql = (
            f"SELECT * FROM {schema}.{table} "
            f"{where_sql} "
            f"ORDER BY {cursor_col} ASC "
            f"LIMIT ${len(params)}"
        )

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
            return [dict(r) for r in rows]


__all__ = ["RexAppDbClient"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/services/connectors/procore/test_rex_app_client.py -v`
Expected: All 4 tests PASS (or SKIPPED if `DATABASE_URL` is missing).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/connectors/procore/rex_app_client.py \
        backend/tests/services/connectors/procore/test_rex_app_client.py
git commit -m "feat(connectors): add RexAppDbClient with safe identifier-guarded row fetch"
```

---

### Task 3: Payload builder for RFIs

**Files:**
- Create: `backend/app/services/connectors/procore/payloads.py`
- Test: `backend/tests/services/connectors/procore/test_payloads.py`

Rationale for the payload shape: Rex App's `procore.rfis` table has columns like `number NUMERIC(10,2)`, `subject TEXT`, `ball_in_court TEXT`, `rfi_manager TEXT`, `cost_impact`, `schedule_impact`, `due_date TIMESTAMPTZ`, `closed_at TIMESTAMPTZ`. The mapper needs: rfi_number, subject, question, answer, status, priority, due_date, ball_in_court, assignee, closed_at, cost_impact, schedule_impact. We shape the payload as a flat dict with those exact keys so the mapper reads them with `raw.get(...)`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/connectors/procore/test_payloads.py
from datetime import datetime, timezone
from app.services.connectors.procore.payloads import build_rfi_payload


def test_build_rfi_payload_happy_path():
    row = {
        "procore_id":     1234,
        "project_id":     100,
        "project_name":   "Bishop Modern",
        "number":         5.0,
        "subject":        "Dimension clash at grid B/4",
        "question":       "Please confirm wall thickness",
        "answer":         None,
        "status":         "open",
        "ball_in_court":  "Architect",
        "assignee":       "Jane Smith",
        "rfi_manager":    "John PM",
        "due_date":       datetime(2026, 5, 1, tzinfo=timezone.utc),
        "closed_at":      None,
        "created_at":     datetime(2026, 4, 15, tzinfo=timezone.utc),
        "updated_at":     datetime(2026, 4, 20, tzinfo=timezone.utc),
        "cost_impact":    None,
        "schedule_impact": None,
    }
    p = build_rfi_payload(row)
    assert p["id"] == "1234"
    assert p["project_source_id"] == "100"
    assert p["rfi_number"] == 5.0
    assert p["subject"] == "Dimension clash at grid B/4"
    assert p["status"] == "open"
    assert p["ball_in_court"] == "Architect"
    assert p["rfi_manager"] == "John PM"
    assert p["due_date"] == "2026-05-01T00:00:00+00:00"
    assert p["updated_at"] == "2026-04-20T00:00:00+00:00"


def test_build_rfi_payload_handles_none_dates():
    row = {
        "procore_id": 7,
        "project_id": 100,
        "number": 7.0,
        "subject": "x",
        "status": "open",
        "due_date": None,
        "closed_at": None,
        "created_at": None,
        "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    p = build_rfi_payload(row)
    assert p["due_date"] is None
    assert p["closed_at"] is None


def test_build_rfi_payload_coerces_ids_to_string():
    row = {"procore_id": 9, "project_id": 100, "subject": "s", "updated_at": datetime(2026,1,1,tzinfo=timezone.utc)}
    p = build_rfi_payload(row)
    assert isinstance(p["id"], str)
    assert isinstance(p["project_source_id"], str)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/services/connectors/procore/test_payloads.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement build_rfi_payload**

```python
# backend/app/services/connectors/procore/payloads.py
"""Per-resource payload builders for the Rex App -> staging path.

Each build_<resource>_payload takes a flat row dict (asyncpg Record ->
dict) from the old rex-procore app's procore.<table> and returns the
JSON-serializable payload we'll store in connector_procore.<table>_raw.

Key names are chosen to match what the corresponding mapper.map_<resource>
reads via raw.get(...). Mapper and payload builder must evolve together.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def build_rfi_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id":                str(row["procore_id"]),
        "project_source_id": str(row.get("project_id")) if row.get("project_id") is not None else None,
        "project_name":      row.get("project_name"),
        "rfi_number":        row.get("number"),
        "subject":           row.get("subject"),
        "question":          row.get("question"),
        "answer":            row.get("answer"),
        "status":            row.get("status"),
        "ball_in_court":     row.get("ball_in_court"),
        "assignee":          row.get("assignee"),
        "rfi_manager":       row.get("rfi_manager"),
        "due_date":          _iso(row.get("due_date")),
        "closed_at":         _iso(row.get("closed_at")),
        "created_at":        _iso(row.get("created_at")),
        "updated_at":        _iso(row.get("updated_at")),
        "cost_impact":       row.get("cost_impact"),
        "schedule_impact":   row.get("schedule_impact"),
    }


__all__ = ["build_rfi_payload"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/services/connectors/procore/test_payloads.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/connectors/procore/payloads.py \
        backend/tests/services/connectors/procore/test_payloads.py
git commit -m "feat(connectors): add RFI payload builder for Rex App read path"
```

---

### Task 4: Wire the adapter's fetch_rfis for real

**Files:**
- Modify: `backend/app/services/connectors/procore/adapter.py`
- Test: extend existing test file or add `backend/tests/services/connectors/procore/test_adapter_fetch_rfis.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/connectors/procore/test_adapter_fetch_rfis.py
import os
import pytest
from datetime import datetime, timezone
from app.services.connectors.procore.rex_app_pool import (
    get_rex_app_pool,
    close_rex_app_pool,
)
from app.services.connectors.procore.adapter import ProcoreAdapter


@pytest.fixture
async def setup_rfis_fixture(monkeypatch):
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    monkeypatch.setenv("REX_APP_DATABASE_URL", url)
    import app.services.connectors.procore.rex_app_pool as mod
    mod._pool = None
    pool = await get_rex_app_pool()

    async with pool.acquire() as conn:
        await conn.execute("CREATE SCHEMA IF NOT EXISTS procore")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS procore.rfis (
                procore_id   bigint PRIMARY KEY,
                project_id   bigint,
                project_name text,
                number       numeric(10,2),
                subject      text,
                question     text,
                answer       text,
                status       text,
                ball_in_court text,
                assignee     text,
                rfi_manager  text,
                due_date     timestamptz,
                closed_at    timestamptz,
                created_at   timestamptz,
                updated_at   timestamptz,
                cost_impact  numeric,
                schedule_impact numeric
            )
        """)
        await conn.execute("TRUNCATE procore.rfis")
        await conn.executemany(
            "INSERT INTO procore.rfis (procore_id, project_id, subject, status, updated_at) "
            "VALUES ($1,$2,$3,$4,$5)",
            [
                (101, 42, "a", "open",   datetime(2026,1,1,tzinfo=timezone.utc)),
                (102, 42, "b", "open",   datetime(2026,1,2,tzinfo=timezone.utc)),
                (103, 99, "c", "closed", datetime(2026,1,3,tzinfo=timezone.utc)),
            ],
        )
    yield
    async with pool.acquire() as conn:
        await conn.execute("DROP TABLE procore.rfis")
    await close_rex_app_pool()


@pytest.mark.asyncio
async def test_fetch_rfis_scopes_to_project(setup_rfis_fixture):
    adapter = ProcoreAdapter(
        account_id="00000000-0000-0000-0000-000000000001",
        config={},
    )
    page = await adapter.fetch_rfis(project_external_id="42")
    ids = [item["id"] for item in page.items]
    assert ids == ["101", "102"]


@pytest.mark.asyncio
async def test_fetch_rfis_advances_cursor(setup_rfis_fixture):
    adapter = ProcoreAdapter(
        account_id="00000000-0000-0000-0000-000000000001",
        config={},
    )
    page1 = await adapter.fetch_rfis(project_external_id="42")
    # next_cursor should be the latest updated_at returned, as ISO string
    assert page1.next_cursor is not None
    page2 = await adapter.fetch_rfis(
        project_external_id="42",
        cursor=page1.next_cursor,
    )
    assert page2.items == []  # no new rows past the cursor
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/services/connectors/procore/test_adapter_fetch_rfis.py -v`
Expected: FAIL — `fetch_rfis` currently returns empty `ConnectorPage`.

- [ ] **Step 3: Update adapter.py**

Replace the stub `fetch_rfis` and refactor the ctor to lazily build a `RexAppDbClient`. Leave the other stub methods untouched in this task.

```python
# backend/app/services/connectors/procore/adapter.py
"""Procore connector adapter.

Reads from the "Rex App" Railway Postgres (old rex-procore sync app)
via RexAppDbClient. No longer talks to Procore's HTTP API directly —
the old app already does that and we consume its flattened tables.

Only fetch_rfis is wired for real in this commit; the other fetch_*
methods land in the follow-up resource-rollout plan.
"""

from __future__ import annotations

from typing import Any

from app.services.connectors.base import (
    ConnectorAdapter,
    ConnectorHealth,
    ConnectorPage,
)
from app.services.connectors.procore.payloads import build_rfi_payload
from app.services.connectors.procore.rex_app_client import RexAppDbClient
from app.services.connectors.procore.rex_app_pool import get_rex_app_pool

DEFAULT_PAGE_SIZE = 500


class ProcoreAdapter(ConnectorAdapter):
    connector_key = "procore"

    def __init__(self, *, account_id: str, config: dict[str, Any] | None = None):
        super().__init__(account_id=account_id, config=config)
        self._client: RexAppDbClient | None = None

    async def _get_client(self) -> RexAppDbClient:
        if self._client is None:
            pool = await get_rex_app_pool()
            self._client = RexAppDbClient(pool)
        return self._client

    async def health_check(self) -> ConnectorHealth:
        try:
            client = await self._get_client()
            rows = await client.fetch_rows(
                schema="procore",
                table="sync_log",
                cursor_col="started_at",
                cursor_value=None,
                limit=1,
            )
            return ConnectorHealth(
                healthy=True,
                details={"last_rex_app_sync_row": rows[0] if rows else None},
            )
        except Exception as e:
            return ConnectorHealth(
                healthy=False,
                last_error_message=str(e),
                details={"state": "rex_app_pool_unreachable"},
            )

    async def list_projects(self, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    async def list_users(self, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    async def fetch_project_directory(
        self, project_external_id: str, cursor: str | None = None
    ) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    async def fetch_rfis(
        self, project_external_id: str, cursor: str | None = None
    ) -> ConnectorPage:
        client = await self._get_client()
        try:
            pid = int(project_external_id)
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"project_external_id must be a numeric procore project id; got {project_external_id!r}"
            ) from e

        rows = await client.fetch_rows(
            schema="procore",
            table="rfis",
            cursor_col="updated_at",
            cursor_value=cursor,
            limit=DEFAULT_PAGE_SIZE,
            extra_where="project_id = $__PARAM__",
            extra_params=[pid],
        )
        # Above "$__PARAM__" sentinel is a placeholder for readability; the
        # real replacement happens in fetch_rows by relying on positional
        # $N injection. See follow-up in Task 4 Step 3b if needed.
        items = [build_rfi_payload(r) for r in rows]
        next_cursor: str | None = None
        if items:
            # use the last updated_at as the next cursor (ISO string)
            next_cursor = items[-1].get("updated_at")
        return ConnectorPage(items=items, next_cursor=next_cursor)

    async def fetch_submittals(self, project_external_id: str, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    async def fetch_daily_logs(self, project_external_id: str, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    async def fetch_budget(self, project_external_id: str, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    async def fetch_commitments(self, project_external_id: str, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    async def fetch_change_events(self, project_external_id: str, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    async def fetch_schedule(self, project_external_id: str, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)

    async def fetch_documents(self, project_external_id: str, cursor: str | None = None) -> ConnectorPage:
        return ConnectorPage(items=[], next_cursor=None)


__all__ = ["ProcoreAdapter"]
```

- [ ] **Step 3b: Adjust RexAppDbClient.fetch_rows to support the extra_where parameter substitution cleanly**

The sentinel approach in Step 3 is ugly. Update `fetch_rows` to rewrite `$1, $2, ...` placeholders inside `extra_where` against the already-consumed param count. Simplest: require callers to write `extra_where="project_id = ANY($PARAMS)"` style isn't worth it — instead, pass a list of `(col, op, value)` filters:

Edit `rex_app_client.py`:

```python
    async def fetch_rows(
        self,
        *,
        schema: str,
        table: str,
        cursor_col: str,
        cursor_value: str | None,
        limit: int,
        filters: list[tuple[str, str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        _assert_identifier(schema, "schema")
        _assert_identifier(table, "table")
        _assert_identifier(cursor_col, "cursor_col")

        params: list[Any] = []
        where_clauses: list[str] = []

        if cursor_value is not None:
            params.append(cursor_value)
            where_clauses.append(f"{cursor_col} > ${len(params)}::timestamptz")

        for col, op, value in filters or []:
            _assert_identifier(col, "filter col")
            if op not in ("=", "!=", ">", "<", ">=", "<="):
                raise ValueError(f"filter op {op!r} not allowed")
            params.append(value)
            where_clauses.append(f"{col} {op} ${len(params)}")

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        params.append(limit)
        sql = (
            f"SELECT * FROM {schema}.{table} "
            f"{where_sql} "
            f"ORDER BY {cursor_col} ASC "
            f"LIMIT ${len(params)}"
        )
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
            return [dict(r) for r in rows]
```

Update the adapter's `fetch_rfis` to pass `filters=[("project_id", "=", pid)]` instead of the sentinel approach. Re-run the rex_app_client tests + the new adapter test.

- [ ] **Step 4: Run all connector tests to verify everything passes**

Run: `cd backend && pytest tests/services/connectors/procore/ -v`
Expected: all tests PASS.

- [ ] **Step 5: Deprecate the old ProcoreClient**

Replace the body of `backend/app/services/connectors/procore/client.py` with:

```python
"""Deprecated — Procore HTTP client.

Rex OS no longer calls the Procore API directly. All reads go through
RexAppDbClient against the old rex-procore Railway DB. If anything
instantiates this class, it's a stale import — fix the call site.
"""


class ProcoreClient:
    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "ProcoreClient is deprecated. Use RexAppDbClient via "
            "app.services.connectors.procore.rex_app_pool.get_rex_app_pool "
            "and query procore.* tables on the Rex App DB instead."
        )
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/connectors/procore/adapter.py \
        backend/app/services/connectors/procore/rex_app_client.py \
        backend/app/services/connectors/procore/client.py \
        backend/tests/services/connectors/procore/test_adapter_fetch_rfis.py
git commit -m "feat(connectors): wire fetch_rfis to Rex App DB via RexAppDbClient"
```

---

### Task 5: Staging writer (upsert_raw with checksum dedup)

**Files:**
- Create: `backend/app/services/connectors/procore/staging.py`
- Test: `backend/tests/services/connectors/procore/test_staging.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/connectors/procore/test_staging.py
import pytest
from uuid import uuid4
from sqlalchemy import text
from app.services.connectors.procore.staging import upsert_raw


@pytest.mark.asyncio
async def test_upsert_raw_inserts_new_rows(db_session, procore_connector_account):
    items = [
        {"id": "101", "project_source_id": "42", "subject": "a", "updated_at": "2026-01-01T00:00:00+00:00"},
        {"id": "102", "project_source_id": "42", "subject": "b", "updated_at": "2026-01-02T00:00:00+00:00"},
    ]
    inserted = await upsert_raw(
        db_session,
        raw_table="rfis_raw",
        items=items,
        account_id=procore_connector_account,
    )
    assert inserted == 2

    result = await db_session.execute(text(
        "SELECT source_id, payload->>'subject' AS subj "
        "FROM connector_procore.rfis_raw "
        "WHERE account_id = :acct ORDER BY source_id"
    ), {"acct": procore_connector_account})
    rows = result.mappings().all()
    assert [(r["source_id"], r["subj"]) for r in rows] == [("101", "a"), ("102", "b")]


@pytest.mark.asyncio
async def test_upsert_raw_dedups_on_unchanged_checksum(db_session, procore_connector_account):
    items = [{"id": "101", "project_source_id": "42", "subject": "a", "updated_at": "2026-01-01T00:00:00+00:00"}]
    await upsert_raw(db_session, raw_table="rfis_raw", items=items, account_id=procore_connector_account)
    # Second call with the same content should not error and should not change checksum timestamp
    inserted = await upsert_raw(db_session, raw_table="rfis_raw", items=items, account_id=procore_connector_account)
    assert inserted == 1  # upserted still counts as 1 write


@pytest.mark.asyncio
async def test_upsert_raw_updates_payload_on_content_change(db_session, procore_connector_account):
    await upsert_raw(
        db_session, raw_table="rfis_raw",
        items=[{"id": "101", "project_source_id": "42", "subject": "a", "updated_at": "2026-01-01T00:00:00+00:00"}],
        account_id=procore_connector_account,
    )
    await upsert_raw(
        db_session, raw_table="rfis_raw",
        items=[{"id": "101", "project_source_id": "42", "subject": "b-NEW", "updated_at": "2026-01-05T00:00:00+00:00"}],
        account_id=procore_connector_account,
    )
    result = await db_session.execute(text(
        "SELECT payload->>'subject' AS subj FROM connector_procore.rfis_raw "
        "WHERE source_id='101' AND account_id=:acct"
    ), {"acct": procore_connector_account})
    assert result.scalar_one() == "b-NEW"
```

`db_session` and `procore_connector_account` are fixtures the existing test suite provides (follow the pattern used in `backend/tests/test_session2_migration_sanity.py`). If they don't exist at exactly those names, reuse whatever the existing connector tests use — the point is a connected SQLAlchemy `AsyncSession` and a seeded `rex.connector_accounts.id` with `connector_id` pointing at the `procore` row in `rex.connectors`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/services/connectors/procore/test_staging.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement upsert_raw**

```python
# backend/app/services/connectors/procore/staging.py
"""Staging-table upserts for connector_procore.*_raw.

Takes the already-shaped payload dicts returned by the adapter and
writes them to the staging table for the given resource, scoped to
one connector_account. Uses a stable content checksum so unchanged
rows don't churn the source_updated_at column.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


ALLOWED_TABLES = {
    "projects_raw",
    "users_raw",
    "rfis_raw",
    "submittals_raw",
    "daily_logs_raw",
    "budget_line_items_raw",
    "commitments_raw",
    "change_events_raw",
    "schedule_tasks_raw",
    "documents_raw",
}


def _checksum(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def upsert_raw(
    db: AsyncSession,
    *,
    raw_table: str,
    items: list[dict[str, Any]],
    account_id: UUID,
) -> int:
    """Upsert a page of items into connector_procore.<raw_table>.

    Returns number of rows upserted. Idempotent on (account_id, source_id).
    """
    if raw_table not in ALLOWED_TABLES:
        raise ValueError(f"raw_table {raw_table!r} not in ALLOWED_TABLES")
    if not items:
        return 0

    # rfis_raw and most others have a NOT NULL project_source_id column;
    # projects_raw / users_raw do not. Branch on presence.
    has_project_col = raw_table not in {"projects_raw", "users_raw"}

    upserted = 0
    for item in items:
        source_id = item["id"]
        project_source_id = item.get("project_source_id")
        source_updated_at = item.get("updated_at")
        checksum = _checksum(item)

        cols = [
            "source_id", "account_id", "payload",
            "source_updated_at", "checksum",
        ]
        vals = {
            "source_id":          source_id,
            "account_id":         account_id,
            "payload":            json.dumps(item, default=str),
            "source_updated_at":  source_updated_at,
            "checksum":           checksum,
        }
        if has_project_col:
            cols.insert(2, "project_source_id")
            vals["project_source_id"] = project_source_id

        col_list = ", ".join(cols)
        placeholders = ", ".join(f":{c}" for c in cols)
        # payload cast; source_updated_at cast
        sql = f"""
            INSERT INTO connector_procore.{raw_table} ({col_list})
            VALUES (
              :source_id, :account_id,
              {"" if not has_project_col else ":project_source_id,"}
              :payload::jsonb, :source_updated_at::timestamptz, :checksum
            )
            ON CONFLICT (account_id, source_id)
            DO UPDATE SET
              payload           = EXCLUDED.payload,
              source_updated_at = EXCLUDED.source_updated_at,
              checksum          = EXCLUDED.checksum,
              fetched_at        = now()
              {"" if not has_project_col else ", project_source_id = EXCLUDED.project_source_id"}
            WHERE connector_procore.{raw_table}.checksum IS DISTINCT FROM EXCLUDED.checksum
        """
        await db.execute(text(sql), vals)
        upserted += 1

    await db.commit()
    return upserted


__all__ = ["upsert_raw", "ALLOWED_TABLES"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/services/connectors/procore/test_staging.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/connectors/procore/staging.py \
        backend/tests/services/connectors/procore/test_staging.py
git commit -m "feat(connectors): add staging upsert_raw with checksum-based dedup"
```

---

### Task 6: Expand mapper.map_rfi

**Files:**
- Modify: `backend/app/services/connectors/procore/mapper.py`
- Test: `backend/tests/services/connectors/procore/test_mapper.py`

Look at the canonical `rex.rfis` table in `migrations/rex2_canonical_ddl.sql` before writing the test — copy the column set the mapper needs to cover. If the canonical table has columns like `rfi_number, subject, question, answer, status, assignee, ball_in_court, due_date, closed_at, cost_impact, schedule_impact`, include all of them.

- [ ] **Step 1: Read `migrations/rex2_canonical_ddl.sql` for rex.rfis columns.**

Find the `CREATE TABLE rex.rfis` statement. Note the exact column names.

- [ ] **Step 2: Write test that asserts mapper output matches canonical column set**

```python
# backend/tests/services/connectors/procore/test_mapper.py
from app.services.connectors.procore.mapper import map_rfi

PROJECT_CANONICAL_ID = "11111111-1111-1111-1111-111111111111"


def test_map_rfi_maps_all_canonical_fields():
    raw = {
        "id":                "1234",
        "project_source_id": "42",
        "rfi_number":        5.0,
        "subject":           "Clash",
        "question":          "?",
        "answer":            None,
        "status":            "open",
        "ball_in_court":     "Architect",
        "assignee":          "Jane",
        "rfi_manager":       "John PM",
        "due_date":          "2026-05-01T00:00:00+00:00",
        "closed_at":         None,
        "cost_impact":       None,
        "schedule_impact":   None,
    }
    m = map_rfi(raw, PROJECT_CANONICAL_ID)
    assert m["source_id"]      == "1234"
    assert m["project_id"]     == PROJECT_CANONICAL_ID
    assert m["rfi_number"]     == "5"  # cast to text-style number used by rex.rfis
    assert m["subject"]        == "Clash"
    assert m["status"]         == "open"
    assert m["assignee"]       == "Jane"
    assert m["ball_in_court"]  == "Architect"
    assert m["due_date"]       == "2026-05-01T00:00:00+00:00"
    assert m["closed_at"]      is None
```

- [ ] **Step 3: Update map_rfi to pull every key the test asserts**

```python
# backend/app/services/connectors/procore/mapper.py
def map_rfi(raw: dict[str, Any], project_canonical_id: str) -> dict[str, Any]:
    num = raw.get("rfi_number")
    return {
        "source_id":        str(raw.get("id", "")),
        "project_id":       project_canonical_id,
        "rfi_number":       None if num is None else str(int(num)) if float(num).is_integer() else str(num),
        "subject":          raw.get("subject"),
        "question":         raw.get("question"),
        "answer":           raw.get("answer"),
        "status":           raw.get("status"),
        "ball_in_court":    raw.get("ball_in_court"),
        "assignee":         raw.get("assignee"),
        "rfi_manager":      raw.get("rfi_manager"),
        "due_date":         raw.get("due_date"),
        "closed_at":        raw.get("closed_at"),
        "cost_impact":      raw.get("cost_impact"),
        "schedule_impact":  raw.get("schedule_impact"),
    }
```

(Keep map_project, map_submittal, map_commitment as-is — they're covered in the follow-up plan.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/services/connectors/procore/test_mapper.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/connectors/procore/mapper.py \
        backend/tests/services/connectors/procore/test_mapper.py
git commit -m "feat(connectors): expand map_rfi to cover canonical rex.rfis fields"
```

---

### Task 7: Orchestrator — end-to-end RFI sync

**Files:**
- Create: `backend/app/services/connectors/procore/orchestrator.py`
- Test: `backend/tests/services/connectors/procore/test_orchestrator.py`

- [ ] **Step 1: Write the failing test**

This is the integration-level test. It seeds `procore.rfis` in the test DB, runs the orchestrator, then asserts:
1. `connector_procore.rfis_raw` has the expected rows.
2. `rex.rfis` has the canonical mappings.
3. `rex.source_links` has the mapping rows.
4. `rex.sync_runs` has one row with `status='succeeded'` and correct counts.
5. `rex.sync_cursors` has an advanced cursor.

```python
# backend/tests/services/connectors/procore/test_orchestrator.py
import pytest
from datetime import datetime, timezone
from sqlalchemy import text

from app.services.connectors.procore.orchestrator import sync_resource


@pytest.mark.asyncio
async def test_sync_resource_rfis_end_to_end(
    db_session, procore_connector_account, project_a_canonical_id
):
    # Arrange: seed procore.rfis (same DB instance as Rex OS in this test)
    await db_session.execute(text("CREATE SCHEMA IF NOT EXISTS procore"))
    await db_session.execute(text("""
        CREATE TABLE IF NOT EXISTS procore.rfis (
            procore_id bigint PRIMARY KEY, project_id bigint,
            number numeric(10,2), subject text, status text,
            updated_at timestamptz
        )
    """))
    await db_session.execute(text("TRUNCATE procore.rfis"))
    await db_session.execute(text(
        "INSERT INTO procore.rfis (procore_id, project_id, number, subject, status, updated_at) "
        "VALUES (201, 42, 1, 'alpha', 'open', '2026-01-01T00:00:00Z')"
    ))
    await db_session.commit()

    # Act
    result = await sync_resource(
        db_session,
        account_id=procore_connector_account,
        resource_type="rfis",
    )

    # Assert staging
    r = await db_session.execute(text(
        "SELECT source_id, payload->>'subject' AS s "
        "FROM connector_procore.rfis_raw "
        "WHERE account_id = :a"
    ), {"a": procore_connector_account})
    assert [(row["source_id"], row["s"]) for row in r.mappings().all()] == [("201", "alpha")]

    # Assert canonical rex.rfis
    canonical = await db_session.execute(text("SELECT subject FROM rex.rfis WHERE rfi_number='1'"))
    assert canonical.scalar_one() == "alpha"

    # Assert source_links
    sl = await db_session.execute(text(
        "SELECT COUNT(*) FROM rex.connector_mappings "
        "WHERE connector='procore' AND external_id='201'"
    ))
    assert sl.scalar_one() == 1

    # Assert sync_runs
    sr = await db_session.execute(text(
        "SELECT status, rows_fetched, rows_upserted FROM rex.sync_runs "
        "WHERE connector_account_id=:a AND resource_type='rfis' "
        "ORDER BY started_at DESC LIMIT 1"
    ), {"a": procore_connector_account})
    row = sr.mappings().first()
    assert row["status"] == "succeeded"
    assert row["rows_fetched"] == 1
    assert row["rows_upserted"] == 1

    # Assert cursor advanced
    cur = await db_session.execute(text(
        "SELECT cursor_value FROM rex.sync_cursors "
        "WHERE connector_account_id=:a AND resource_type='rfis'"
    ), {"a": procore_connector_account})
    assert cur.scalar_one() == "2026-01-01T00:00:00+00:00"

    # Cleanup
    await db_session.execute(text("DROP TABLE procore.rfis"))
    await db_session.commit()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/services/connectors/procore/test_orchestrator.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement sync_resource**

```python
# backend/app/services/connectors/procore/orchestrator.py
"""End-to-end sync orchestrator for one (account, resource_type) pair.

Pipeline steps:
  1. start sync_run
  2. get prior cursor
  3. iterate adapter.fetch_<resource> pages
  4. upsert into connector_procore.<resource>_raw
  5. call mapper.map_<resource>
  6. upsert into rex.<canonical_table>
  7. upsert source_link per row
  8. advance sync_cursor
  9. finish sync_run

In this scope only 'rfis' is implemented; other resources raise
NotImplementedError. The follow-up plan adds the others, reusing this
function's structure.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.connectors.procore.adapter import ProcoreAdapter
from app.services.connectors.procore import mapper
from app.services.connectors.procore.staging import upsert_raw
from app.services.connectors.sync_service import (
    finish_sync_run,
    get_cursor,
    set_cursor,
    start_sync_run,
    upsert_source_link,
)

log = logging.getLogger("rex.connectors.procore.orchestrator")


# Resource -> (raw_table, mapper_fn, canonical_table, source_table_label)
_RESOURCE_CONFIG: dict[str, dict[str, Any]] = {
    "rfis": {
        "raw_table":        "rfis_raw",
        "map_fn":           mapper.map_rfi,
        "canonical_table":  "rfis",
        "source_table":     "procore.rfis",
    },
}


async def sync_resource(
    db: AsyncSession,
    *,
    account_id: UUID,
    resource_type: str,
) -> dict[str, int]:
    cfg = _RESOURCE_CONFIG.get(resource_type)
    if cfg is None:
        raise NotImplementedError(
            f"resource_type={resource_type} not implemented yet; "
            f"supported: {sorted(_RESOURCE_CONFIG)}"
        )

    run_id = await start_sync_run(
        db, connector_account_id=account_id, resource_type=resource_type
    )
    try:
        cursor = await get_cursor(
            db, connector_account_id=account_id, resource_type=resource_type
        )
        adapter = ProcoreAdapter(account_id=str(account_id))

        # For RFIs the adapter requires a project scope. In this plan we
        # loop over all known canonical projects that have a procore
        # source_link to find their source project ids. Simpler scope
        # for MVP: iterate project_source_ids from rex.source_links
        # where source_table='procore.projects'.
        project_rows = (await db.execute(text("""
            SELECT external_id, rex_id
            FROM rex.connector_mappings
            WHERE connector = 'procore' AND source_table = 'procore.projects'
        """))).mappings().all()

        total_fetched = 0
        total_upserted = 0
        max_cursor: str | None = cursor

        for prow in project_rows:
            proj_source_id = prow["external_id"]
            proj_canonical_id = prow["rex_id"]

            page = await adapter.fetch_rfis(
                project_external_id=proj_source_id,
                cursor=cursor,
            )
            total_fetched += len(page.items)
            if not page.items:
                continue

            written = await upsert_raw(
                db,
                raw_table=cfg["raw_table"],
                items=page.items,
                account_id=account_id,
            )

            for item in page.items:
                canonical_row = cfg["map_fn"](item, str(proj_canonical_id))
                canonical_id = await _upsert_canonical(
                    db, cfg["canonical_table"], canonical_row
                )
                await upsert_source_link(
                    db,
                    connector_key="procore",
                    source_table=cfg["source_table"],
                    source_id=item["id"],
                    canonical_table=f"rex.{cfg['canonical_table']}",
                    canonical_id=canonical_id,
                    project_id=proj_canonical_id,
                )
                total_upserted += 1

            if page.next_cursor and (max_cursor is None or page.next_cursor > max_cursor):
                max_cursor = page.next_cursor

        if max_cursor != cursor:
            await set_cursor(
                db, connector_account_id=account_id,
                resource_type=resource_type, cursor_value=max_cursor,
            )

        await finish_sync_run(
            db, sync_run_id=run_id, status="succeeded",
            rows_fetched=total_fetched, rows_upserted=total_upserted,
        )
        return {"rows_fetched": total_fetched, "rows_upserted": total_upserted}

    except Exception as e:
        log.exception("sync_resource failed")
        await finish_sync_run(
            db, sync_run_id=run_id, status="failed",
            error_excerpt=str(e),
        )
        raise


async def _upsert_canonical(
    db: AsyncSession, canonical_table: str, row: dict[str, Any]
) -> UUID:
    """Upsert row into rex.<canonical_table> keyed on (project_id, source_id).

    Returns the canonical id. Table-specific; for now handles 'rfis'.
    Extend this function in the follow-up plan as more canonical tables
    come online.
    """
    if canonical_table == "rfis":
        res = await db.execute(text("""
            INSERT INTO rex.rfis (
                id, project_id, rfi_number, subject, question, answer,
                status, assignee, ball_in_court, due_date, closed_at,
                cost_impact, schedule_impact
            ) VALUES (
                gen_random_uuid(), :project_id, :rfi_number, :subject, :question, :answer,
                :status, :assignee, :ball_in_court,
                :due_date::timestamptz, :closed_at::timestamptz,
                :cost_impact, :schedule_impact
            )
            ON CONFLICT (project_id, rfi_number) DO UPDATE SET
                subject         = EXCLUDED.subject,
                question        = EXCLUDED.question,
                answer          = EXCLUDED.answer,
                status          = EXCLUDED.status,
                assignee        = EXCLUDED.assignee,
                ball_in_court   = EXCLUDED.ball_in_court,
                due_date        = EXCLUDED.due_date,
                closed_at       = EXCLUDED.closed_at,
                cost_impact     = EXCLUDED.cost_impact,
                schedule_impact = EXCLUDED.schedule_impact
            RETURNING id
        """), row)
        return res.scalar_one()

    raise NotImplementedError(f"canonical upsert for rex.{canonical_table} not implemented")


__all__ = ["sync_resource"]
```

> **IMPORTANT:** The `ON CONFLICT (project_id, rfi_number)` clause assumes that constraint exists on `rex.rfis`. Before running the test, inspect `migrations/rex2_canonical_ddl.sql` — if the constraint doesn't exist, add a migration (e.g. `migrations/023_rex_rfis_unique_constraint.sql`) that creates it:
>
> ```sql
> ALTER TABLE rex.rfis ADD CONSTRAINT rex_rfis_project_rfi_number_uniq UNIQUE (project_id, rfi_number);
> ```
>
> If the canonical schema uses a different natural key (e.g. source_id alone), adjust the ON CONFLICT clause to match.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/services/connectors/procore/test_orchestrator.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full connector test suite and ensure nothing regressed**

Run: `cd backend && pytest tests/services/connectors/ -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/connectors/procore/orchestrator.py \
        backend/tests/services/connectors/procore/test_orchestrator.py \
        migrations/  # include any new migration added for the unique constraint
git commit -m "feat(connectors): end-to-end RFI sync orchestrator (Rex App -> rex.rfis)"
```

---

### Task 8: Admin trigger + docs

**Files:**
- Modify: `backend/app/routes/connectors.py` (expose POST /api/connectors/{account_id}/sync/{resource_type})
- Modify: `DEPLOY.md`
- Test: `backend/tests/services/connectors/procore/test_admin_sync_trigger.py`

- [ ] **Step 1: Add a test for the admin sync endpoint**

```python
# backend/tests/services/connectors/procore/test_admin_sync_trigger.py
import pytest

@pytest.mark.asyncio
async def test_admin_sync_rfis_returns_counts(client, admin_auth_headers, procore_connector_account):
    response = await client.post(
        f"/api/connectors/{procore_connector_account}/sync/rfis",
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert "rows_fetched" in body
    assert "rows_upserted" in body
```

(`client` and `admin_auth_headers` are existing fixtures — see `backend/tests/test_assistant_live_db_smoke.py` for how admin-scoped requests are made.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/services/connectors/procore/test_admin_sync_trigger.py -v`
Expected: FAIL (404, endpoint doesn't exist).

- [ ] **Step 3: Add the route**

In `backend/app/routes/connectors.py`, add:

```python
from app.services.connectors.procore.orchestrator import sync_resource as procore_sync_resource

@router.post("/{account_id}/sync/{resource_type}")
async def admin_sync_resource(
    account_id: UUID,
    resource_type: str,
    db: AsyncSession = Depends(get_db_session),
    user = Depends(require_admin),
) -> dict:
    # Currently only the procore connector is wired. Route the call based
    # on the account's connector_key.
    connector_key = (await db.execute(text("""
        SELECT c.connector_key FROM rex.connector_accounts a
        JOIN rex.connectors c ON c.id = a.connector_id
        WHERE a.id = :a
    """), {"a": account_id})).scalar_one_or_none()

    if connector_key == "procore":
        return await procore_sync_resource(
            db, account_id=account_id, resource_type=resource_type
        )
    raise HTTPException(
        status_code=400,
        detail=f"sync not implemented for connector {connector_key!r}",
    )
```

Reuse whatever auth dependency the existing admin routes in this file use — match, don't invent.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/services/connectors/procore/test_admin_sync_trigger.py -v`
Expected: PASS.

- [ ] **Step 5: Update DEPLOY.md**

In `DEPLOY.md §6 Env var reference` (backend table), add a row:

```
| `REX_APP_DATABASE_URL` | yes (for Procore connector) | — | Public Postgres URL of old rex-procore ("Rex App" Railway project). Leave unset to disable the Procore read path. |
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/connectors.py \
        backend/tests/services/connectors/procore/test_admin_sync_trigger.py \
        DEPLOY.md
git commit -m "feat(connectors): admin endpoint to trigger Procore RFI sync + docs"
```

---

### Task 9: Live smoke against real Rex App DB (manual)

**Files:** none — this is operator verification.

- [ ] **Step 1: Set env var**

In Rex OS Railway demo environment: set `REX_APP_DATABASE_URL` to the public DATABASE_URL of the Rex App Postgres service. Redeploy.

- [ ] **Step 2: Seed the procore source_links for at least one project**

Needed because the orchestrator iterates over `rex.connector_mappings WHERE source_table='procore.projects'`. Insert a row that points the Bishop Modern (or another test project) canonical id to the Rex App procore project id. One-shot SQL:

```sql
INSERT INTO rex.connector_mappings (rex_table, rex_id, connector, external_id, source_table, synced_at)
VALUES ('rex.projects', '<bishop_canonical_uuid>', 'procore', '<rex_app_procore_project_id>', 'procore.projects', now())
ON CONFLICT DO NOTHING;
```

Get the `<bishop_canonical_uuid>` from `rex.projects` and the `<rex_app_procore_project_id>` from `procore.projects` in Rex App.

- [ ] **Step 3: Trigger the sync**

```
curl -X POST "https://<demo-url>/api/connectors/<procore_account_uuid>/sync/rfis" \
  -H "Authorization: Bearer <admin_token>"
```

Expected: 200 with `{"rows_fetched": N, "rows_upserted": N}` where N matches the Bishop Modern RFI count in Rex App.

- [ ] **Step 4: Verify the data landed**

```
curl "https://<demo-url>/api/rfis?project_id=<bishop_canonical_uuid>"
```

Expected: RFI rows matching the Rex App data. Open the demo Vercel UI, navigate to the project's RFI page, confirm rows render.

- [ ] **Step 5: Flip the `rfi_aging` action from alpha → live**

(This is a one-line change to the action catalog row; exact path depends on how the action catalog is seeded — see migration 021 for the pattern. Follow-up plan for alpha actions will cover this in depth.)

---

## Self-Review Checklist

- [x] **Spec coverage:** Tasks 1–2 cover the second DB pool + client, Tasks 3–4 cover the adapter's fetch_rfis, Task 5 covers staging, Task 6 covers the mapper, Task 7 covers the end-to-end pipeline, Task 8 covers admin trigger + docs, Task 9 covers live verification. RFIs is a complete end-to-end reference; the 10 other resources are explicitly out of scope and go in a follow-up plan.
- [x] **Placeholder scan:** No TBD/TODO — every step has real code. One hedge at Task 7 Step 3 about the ON CONFLICT constraint that may or may not exist — called out with an inline migration snippet if needed.
- [x] **Type consistency:** `ConnectorPage`, `ConnectorHealth`, `RexAppDbClient.fetch_rows`, `build_rfi_payload`, `upsert_raw`, `map_rfi`, `sync_resource` — signatures are identical across tasks. `next_cursor` is always `str | None`.
- [x] **Open risk:** Task 8 depends on existing auth dependencies/fixtures in the repo (`require_admin`, `admin_auth_headers`). The plan notes "reuse whatever the existing admin routes use" rather than prescribing; the implementer will adapt to what's there.

---

## Follow-up plans (not in scope of this one)

1. **`2026-04-XX-phase4-procore-remaining-resources.md`** — Same pattern as Task 3–7 for submittals, daily_logs, tasks (schedule_tasks), change_events, commitments, budget_line_items, vendors (as directory), users (directory), projects (directory list), documents. Each is ~4 tasks (payload + adapter + mapper + orchestrator resource-config entry).
2. **`2026-04-XX-phase5-wave1-alpha-actions.md`** — Wire the 8 alpha Quick Actions (budget_variance, rfi_aging, daily_log_summary, submittal_sla, critical_path_delays, two_week_lookahead, documentation_compliance, my_day_briefing) to execute SQL against `rex.v_*` views.
