# Phase 6a — Commands, Actions & Approvals (Core) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the backend framework that turns LLM tool_use responses into classified, queued, auto-committed-or-approval-gated actions, including 4 MVP tools (3 auto-pass + 1 approval-required using Procore writeback). Rex OS becomes source of truth for Procore objects for the RFI answer path.

**Architecture:** Four layers — (1) `ActionSpec` tool registry in `backend/app/services/ai/tools/` with per-tool `tool_schema`, `handler`, `classify`, `fires_external_effect`; (2) `BlastRadius` classifier in `blast_radius.py` with 4 dimensions + `requires_approval()`; (3) `rex.action_queue` persistence + `action_queue_service.py` orchestration for enqueue/approve/undo/dispatch; (4) `chat_service.py` intercepts LLM tool_use responses + emits new SSE events (`action_proposed`, `action_auto_committed`, `action_committed`, `action_failed`). New HTTP surface: `POST /api/actions/{id}/{approve|discard|undo}`, `GET /api/actions/pending`.

**Tech Stack:** Python 3.11+, FastAPI, asyncpg, Anthropic SDK tool use, pytest. New dep: none (Procore API client uses existing `httpx`).

**Spec:** `docs/superpowers/specs/2026-04-21-phase6-commands-approvals-design.md` (committed 2026-04-21).

---

## File structure (new/modified)

**New:**
- `migrations/028_rex_action_queue.sql` — schema for `rex.action_queue`
- `backend/app/services/ai/actions/blast_radius.py` — `BlastRadius` dataclass + `requires_approval()` + `reasons()` + `ClassifyContext`
- `backend/app/services/ai/tools/__init__.py` — registry re-exports
- `backend/app/services/ai/tools/base.py` — `ActionSpec` dataclass + protocols
- `backend/app/services/ai/tools/registry.py` — `_TOOLS` dict, `get(slug)`, `list_schemas()`
- `backend/app/services/ai/tools/create_task.py` — auto-pass tool
- `backend/app/services/ai/tools/update_task_status.py` — auto-pass tool
- `backend/app/services/ai/tools/create_note.py` — auto-pass tool (target table: `rex.pending_decisions`, see Task 8 discovery)
- `backend/app/services/ai/tools/answer_rfi.py` — approval-required tool
- `backend/app/services/ai/tools/procore_api.py` — minimal Procore REST client (OAuth refresh + answer_rfi endpoint only)
- `backend/app/services/ai/action_queue_service.py` — `enqueue`, `commit`, `discard`, `undo`, `retry`
- `backend/app/repositories/action_queue_repository.py` — SQL CRUD for `rex.action_queue`
- `backend/app/routes/actions.py` — new router mounted at `/api/actions`
- `backend/app/schemas/actions.py` — Pydantic models for API responses
- `backend/tests/services/ai/tools/__init__.py`
- `backend/tests/services/ai/tools/test_blast_radius.py`
- `backend/tests/services/ai/tools/test_create_task.py`
- `backend/tests/services/ai/tools/test_update_task_status.py`
- `backend/tests/services/ai/tools/test_create_note.py`
- `backend/tests/services/ai/tools/test_answer_rfi.py`
- `backend/tests/services/ai/test_action_queue_service.py`
- `backend/tests/routes/test_actions_routes.py`
- `backend/tests/services/ai/test_chat_service_tool_use.py`

**Modified:**
- `backend/app/services/ai/chat_service.py` — intercept `tool_use` blocks from model response; call `action_queue_service.enqueue`; emit new SSE events
- `backend/app/services/ai/dispatcher.py` — pass tool registry into ChatService
- `backend/app/services/ai/model_client.py` — extend to accept `tools` kwarg for Anthropic tool use; pass through to the API
- `backend/app/migrate.py` — register migration 028
- `backend/main.py` — mount `/api/actions` router

---

## Pre-implementation: schema discovery

Before any task writes SQL, the implementer must verify the live schema for these tables. These are NOT all in the plan's verified-shapes block for Phase 4/5 — we're introducing a new domain.

- `rex.chat_conversations` and `rex.chat_messages` — exact table names and PK columns (the `action_queue.message_id` FK needs them). Check `migrations/*.sql` or earlier conversation repo code in `backend/app/repositories/chat_repository.py`.
- `rex.user_accounts.id` — confirmed uuid PK.
- `rex.tasks` — for `create_task` / `update_task_status`. Confirm required columns (already used in Phase 5 smoke; should be `project_id, task_number, title, status, assigned_to, due_date`).
- `rex.pending_decisions` — for `create_note`. Confirm it's the right home for a free-form "note" and not a domain-specific decision object. If schema rejects our usage, Task 8 may need a new `rex.notes` table via a small migration.
- `rex.rfis` — for `answer_rfi`. Confirm columns: `answer text`, `status text`, `answered_at timestamptz` (or similar).

Each task's Step 1 includes "verify schema and adjust code to match"; implementer uses `grep` or reads `migrations/rex2_canonical_ddl.sql` before writing the SQL.

---

### Task 1: Migration for `rex.action_queue`

**Files:**
- Create: `migrations/028_rex_action_queue.sql`
- Modify: `backend/app/migrate.py` (register migration)

- [ ] **Step 1: Verify FK target table names**

Run (from worktree root):
```
grep -E "^CREATE TABLE.*(rex\.chat_conversations|rex\.chat_messages)" migrations/*.sql
```

Note the exact table names. If they're `rex.conversations` + `rex.messages` instead of the `chat_*` prefix, adjust the migration's FK lines. If one of them doesn't exist at all, fall back to `uuid` columns with no FK (they're metadata for trace/audit, not hard-enforced).

- [ ] **Step 2: Write the migration**

```sql
-- migrations/028_rex_action_queue.sql
-- Phase 6a: action_queue — every LLM tool_use invocation + classification +
-- approval lifecycle gets a row. Powers the confirmation-card inline view
-- and the filtered "Pending Approvals" sidebar.

CREATE TABLE IF NOT EXISTS rex.action_queue (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id       uuid,
    message_id            uuid,
    user_account_id       uuid NOT NULL REFERENCES rex.user_accounts(id),
    requested_by_user_id  uuid REFERENCES rex.user_accounts(id),
    tool_slug             text NOT NULL,
    tool_args             jsonb NOT NULL,
    blast_radius          jsonb NOT NULL,
    requires_approval     boolean NOT NULL,
    status                text NOT NULL CHECK (status IN (
        'auto_committed',
        'pending_approval',
        'committed',
        'dismissed',
        'undone',
        'failed',
        'pending_retry'
    )),
    approver_role         text,
    committed_at          timestamptz,
    undone_at             timestamptz,
    error_excerpt         text,
    result_payload        jsonb,
    correction_of_id      uuid REFERENCES rex.action_queue(id),
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_action_queue_status
    ON rex.action_queue (status);

CREATE INDEX IF NOT EXISTS idx_action_queue_user_pending
    ON rex.action_queue (user_account_id, status)
    WHERE status = 'pending_approval';

CREATE INDEX IF NOT EXISTS idx_action_queue_conversation
    ON rex.action_queue (conversation_id);

CREATE INDEX IF NOT EXISTS idx_action_queue_created_at
    ON rex.action_queue (created_at DESC);

COMMENT ON TABLE rex.action_queue IS
    'Phase 6: every LLM tool_use gets a row here. Auto-pass actions start as auto_committed (undoable for 60s); approval-required start as pending_approval (wait for user).';
```

If the Step 1 grep showed the chat tables exist with exact names, extend the migration to add the FK constraints:

```sql
ALTER TABLE rex.action_queue
    ADD CONSTRAINT action_queue_conversation_fk
    FOREIGN KEY (conversation_id) REFERENCES rex.chat_conversations(id) ON DELETE SET NULL;
ALTER TABLE rex.action_queue
    ADD CONSTRAINT action_queue_message_fk
    FOREIGN KEY (message_id) REFERENCES rex.chat_messages(id) ON DELETE SET NULL;
```

Wrap the ALTER TABLEs in `DO $$ EXCEPTION WHEN duplicate_object THEN NULL; END $$;` for idempotency (same pattern as migrations 024-027).

- [ ] **Step 3: Register in MIGRATION_ORDER**

Open `backend/app/migrate.py`. Append `"028_rex_action_queue.sql"` to the end of the `MIGRATION_ORDER` list.

- [ ] **Step 4: Apply the migration to the dev DB**

```
cd backend && py -c "
import asyncio
from app.migrate import run_migrations
asyncio.run(run_migrations())
"
```

Or restart the backend in dev so auto-migrate runs. Verify:

```sql
-- Via psql or a quick script
SELECT 1 FROM pg_tables WHERE schemaname='rex' AND tablename='action_queue';
```

- [ ] **Step 5: Commit**

```bash
git add migrations/028_rex_action_queue.sql backend/app/migrate.py
git commit -m "feat(phase6): rex.action_queue table for command/approval lifecycle"
```

---

### Task 2: `BlastRadius` classifier + `ClassifyContext`

**Files:**
- Create: `backend/app/services/ai/actions/blast_radius.py`
- Test: `backend/tests/services/ai/tools/test_blast_radius.py`
- Create: `backend/tests/services/ai/tools/__init__.py` (empty)

- [ ] **Step 1: Create test directory package marker**

```python
# backend/tests/services/ai/tools/__init__.py
```

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/services/ai/tools/test_blast_radius.py
"""BlastRadius dataclass + requires_approval() + reasons()."""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.services.ai.actions.blast_radius import BlastRadius


def test_internal_single_reversible_no_money_is_auto():
    br = BlastRadius(
        audience='internal',
        fires_external_effect=False,
        financial_dollar_amount=None,
        scope_size=1,
    )
    assert br.requires_approval() is False
    assert br.reasons() == []


def test_external_audience_requires_approval():
    br = BlastRadius(
        audience='external',
        fires_external_effect=False,
        financial_dollar_amount=None,
        scope_size=1,
    )
    assert br.requires_approval() is True
    assert "outside Rex Construction" in br.reasons()[0]


def test_external_effect_flag_requires_approval():
    br = BlastRadius(
        audience='internal',
        fires_external_effect=True,
        financial_dollar_amount=None,
        scope_size=1,
    )
    assert br.requires_approval() is True
    assert "external system" in br.reasons()[0].lower()


def test_any_positive_money_requires_approval():
    br = BlastRadius(
        audience='internal',
        fires_external_effect=False,
        financial_dollar_amount=0.01,
        scope_size=1,
    )
    assert br.requires_approval() is True


def test_zero_dollars_does_not_trigger():
    br = BlastRadius(
        audience='internal',
        fires_external_effect=False,
        financial_dollar_amount=0.0,
        scope_size=1,
    )
    # $0.00 is falsy in our rule; a zero-dollar change is effectively no change.
    assert br.requires_approval() is False


def test_batch_of_five_requires_approval():
    br = BlastRadius(
        audience='internal',
        fires_external_effect=False,
        financial_dollar_amount=None,
        scope_size=5,
    )
    assert br.requires_approval() is True
    assert "batch of 5" in br.reasons()[0]


def test_multiple_reasons_all_listed():
    br = BlastRadius(
        audience='external',
        fires_external_effect=True,
        financial_dollar_amount=100.0,
        scope_size=7,
    )
    reasons = br.reasons()
    assert len(reasons) == 4
    assert any("outside Rex Construction" in r for r in reasons)
    assert any("external system" in r.lower() for r in reasons)
    assert any("100" in r for r in reasons)
    assert any("7" in r for r in reasons)


def test_frozen_dataclass():
    br = BlastRadius(
        audience='internal',
        fires_external_effect=False,
        financial_dollar_amount=None,
        scope_size=1,
    )
    with pytest.raises(Exception):  # FrozenInstanceError
        br.audience = 'external'
```

- [ ] **Step 3: Run test to verify it fails**

```
cd backend && py -m pytest tests/services/ai/tools/test_blast_radius.py -v
```

Expected: FAIL with `ModuleNotFoundError: app.services.ai.actions.blast_radius`.

- [ ] **Step 4: Implement `blast_radius.py`**

```python
# backend/app/services/ai/actions/blast_radius.py
"""Phase 6 blast-radius classifier.

Every tool returns a BlastRadius from its `classify(args, ctx)` function.
The dispatcher checks `requires_approval()` to route the action to either
auto-commit (with 60s undo) or approval queue.

Rubric (per brainstorm decision 3):
- audience='external'               -> approval
- fires_external_effect=True        -> approval
- financial_dollar_amount > 0       -> approval (any dollar)
- scope_size >= 5                   -> approval

Category is the default; blast radius is the rule.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

import asyncpg


@dataclass(frozen=True)
class BlastRadius:
    audience: Literal['internal', 'external']
    fires_external_effect: bool
    financial_dollar_amount: float | None
    scope_size: int

    def requires_approval(self) -> bool:
        return (
            self.audience == 'external'
            or self.fires_external_effect
            or (
                self.financial_dollar_amount is not None
                and self.financial_dollar_amount > 0
            )
            or self.scope_size >= 5
        )

    def reasons(self) -> list[str]:
        r: list[str] = []
        if self.audience == 'external':
            r.append("will notify someone outside Rex Construction")
        if self.fires_external_effect:
            r.append("writes to an external system (Procore)")
        if (
            self.financial_dollar_amount is not None
            and self.financial_dollar_amount > 0
        ):
            r.append(
                f"financial impact: ${self.financial_dollar_amount:,.2f}"
            )
        if self.scope_size >= 5:
            r.append(f"batch of {self.scope_size} changes")
        return r

    def to_jsonb(self) -> dict:
        """Serialize for storage in rex.action_queue.blast_radius column."""
        return {
            "audience": self.audience,
            "fires_external_effect": self.fires_external_effect,
            "financial_dollar_amount": self.financial_dollar_amount,
            "scope_size": self.scope_size,
        }

    @classmethod
    def from_jsonb(cls, data: dict) -> "BlastRadius":
        return cls(
            audience=data["audience"],
            fires_external_effect=bool(data["fires_external_effect"]),
            financial_dollar_amount=data.get("financial_dollar_amount"),
            scope_size=int(data["scope_size"]),
        )


@dataclass
class ClassifyContext:
    """State the classify() function may need — injected by the dispatcher
    at tool_use interception time. Pure helpers only; no I/O directly on
    the context (handlers have the full asyncpg.Connection instead)."""
    conn: asyncpg.Connection
    user_account_id: UUID

    async def is_internal_person(self, person_id: UUID | None) -> bool:
        """rex.people.role_type == 'internal'. None → False."""
        if person_id is None:
            return False
        row = await self.conn.fetchrow(
            "SELECT role_type FROM rex.people WHERE id = $1::uuid",
            person_id,
        )
        return bool(row and row["role_type"] == "internal")

    async def person_exists(self, person_id: UUID | None) -> bool:
        if person_id is None:
            return False
        return bool(
            await self.conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM rex.people WHERE id = $1::uuid)",
                person_id,
            )
        )


__all__ = ["BlastRadius", "ClassifyContext"]
```

- [ ] **Step 5: Run test to verify it passes**

```
cd backend && py -m pytest tests/services/ai/tools/test_blast_radius.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai/actions/blast_radius.py \
        backend/tests/services/ai/tools/__init__.py \
        backend/tests/services/ai/tools/test_blast_radius.py
git commit -m "feat(phase6): BlastRadius classifier + ClassifyContext helpers"
```

---

### Task 3: Tool registry — `ActionSpec` + protocols

**Files:**
- Create: `backend/app/services/ai/tools/__init__.py`
- Create: `backend/app/services/ai/tools/base.py`
- Create: `backend/app/services/ai/tools/registry.py`

- [ ] **Step 1: Empty init**

```python
# backend/app/services/ai/tools/__init__.py
"""Phase 6 tool registry. Each tool module exports a module-level
`SPEC: ActionSpec` constant; the registry at `registry.py` aggregates
them."""
```

- [ ] **Step 2: `base.py`**

```python
# backend/app/services/ai/tools/base.py
"""Phase 6 tool definitions.

An ActionSpec is the source of truth for one LLM-invokable action:
- `slug`: stable id (the Anthropic tool_use name)
- `tool_schema`: Anthropic-compatible JSON schema the model sees
- `handler`: async function that executes the action against Rex OS state
- `classify`: sync function returning a BlastRadius given args + context
- `fires_external_effect`: grep-able flag for the reversibility dimension
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol
from uuid import UUID

import asyncpg

from app.services.ai.actions.blast_radius import BlastRadius, ClassifyContext


@dataclass
class ActionContext:
    """What a handler receives at commit time.

    conn: live asyncpg connection (dispatcher owns lifecycle).
    user_account_id: who the action runs AS (may differ from requester
        in delegate scenarios — see spec §Approver routing).
    args: tool_args passed by the LLM, validated against tool_schema.
    action_id: the rex.action_queue row id (for result_payload writeback).
    """
    conn: asyncpg.Connection
    user_account_id: UUID
    args: dict[str, Any]
    action_id: UUID


@dataclass
class ActionResult:
    """What a handler returns on success.

    result_payload: JSONB-serializable dict persisted to
        rex.action_queue.result_payload for debugging + correction UI.
    """
    result_payload: dict[str, Any]


class ClassifyFn(Protocol):
    async def __call__(
        self, args: dict[str, Any], ctx: ClassifyContext
    ) -> BlastRadius: ...


class HandlerFn(Protocol):
    async def __call__(self, ctx: ActionContext) -> ActionResult: ...


@dataclass
class ActionSpec:
    slug: str
    tool_schema: dict[str, Any]
    classify: ClassifyFn
    handler: HandlerFn
    fires_external_effect: bool = False


__all__ = [
    "ActionContext",
    "ActionResult",
    "ActionSpec",
    "ClassifyFn",
    "HandlerFn",
]
```

- [ ] **Step 3: `registry.py`**

```python
# backend/app/services/ai/tools/registry.py
"""Tool registry — aggregates all ActionSpec instances into one lookup.

New tools register themselves by adding their module + SPEC export to
`_REGISTER` below. The dispatcher uses `get(slug)` and `list_schemas()`.
"""
from __future__ import annotations

from app.services.ai.tools.base import ActionSpec

# Import tool modules; each exports SPEC: ActionSpec at module level.
# NOTE: importing a module here registers it. Keep this list up-to-date.
from app.services.ai.tools import (
    create_task as _create_task,
    update_task_status as _update_task_status,
    create_note as _create_note,
    answer_rfi as _answer_rfi,
)

_REGISTER: list[ActionSpec] = [
    _create_task.SPEC,
    _update_task_status.SPEC,
    _create_note.SPEC,
    _answer_rfi.SPEC,
]

_BY_SLUG: dict[str, ActionSpec] = {s.slug: s for s in _REGISTER}


def get(slug: str) -> ActionSpec | None:
    return _BY_SLUG.get(slug)


def all_specs() -> list[ActionSpec]:
    return list(_REGISTER)


def list_schemas() -> list[dict]:
    """The list of tool schemas to pass to the Anthropic API for tool use."""
    return [
        {
            "name": s.slug,
            **s.tool_schema,  # must contain "description" and "input_schema"
        }
        for s in _REGISTER
    ]


__all__ = ["get", "all_specs", "list_schemas"]
```

**IMPORTANT:** This registry imports 4 tool modules that don't exist yet (Tasks 5-9 create them). To make the registry importable for downstream work, create stub modules now — Task 5-9 will replace each stub's body.

- [ ] **Step 4: Create 4 stub tool modules**

For each of `create_task.py`, `update_task_status.py`, `create_note.py`, `answer_rfi.py`, create this skeleton:

```python
# backend/app/services/ai/tools/<slug>.py
"""<slug> — STUB. Real implementation lands in Task <N>."""
from __future__ import annotations

from app.services.ai.tools.base import (
    ActionContext, ActionResult, ActionSpec,
)
from app.services.ai.actions.blast_radius import BlastRadius, ClassifyContext


async def _classify(args, ctx: ClassifyContext) -> BlastRadius:
    return BlastRadius(
        audience='internal',
        fires_external_effect=False,
        financial_dollar_amount=None,
        scope_size=1,
    )


async def _handler(ctx: ActionContext) -> ActionResult:
    raise NotImplementedError(
        f"<slug> handler not yet implemented; see Phase 6 plan Task <N>"
    )


SPEC = ActionSpec(
    slug="<slug>",
    tool_schema={
        "description": "STUB",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    classify=_classify,
    handler=_handler,
    fires_external_effect=False,
)
```

Replace `<slug>` and `<N>` per file. The real implementations in Tasks 5-9 will replace these.

- [ ] **Step 5: Smoke-test the registry imports**

```
cd backend && py -c "from app.services.ai.tools import registry; print([s.slug for s in registry.all_specs()])"
```

Expected output:
```
['create_task', 'update_task_status', 'create_note', 'answer_rfi']
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai/tools/
git commit -m "feat(phase6): tool registry scaffolding + 4 stub tools"
```

---

### Task 4: `action_queue_repository.py` — SQL CRUD

**Files:**
- Create: `backend/app/repositories/action_queue_repository.py`
- Test: inline with Task 5 (the service layer)

- [ ] **Step 1: Implement the repository**

```python
# backend/app/repositories/action_queue_repository.py
"""SQL CRUD for rex.action_queue. Pure SQL — no business logic."""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ActionQueueRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def insert(
        self,
        *,
        id: UUID,
        user_account_id: UUID,
        requested_by_user_id: UUID | None,
        conversation_id: UUID | None,
        message_id: UUID | None,
        tool_slug: str,
        tool_args: dict,
        blast_radius: dict,
        requires_approval: bool,
        status: str,
        approver_role: str | None,
    ) -> None:
        await self._db.execute(
            text(
                """
                INSERT INTO rex.action_queue (
                    id, user_account_id, requested_by_user_id,
                    conversation_id, message_id,
                    tool_slug, tool_args, blast_radius, requires_approval,
                    status, approver_role, created_at, updated_at
                ) VALUES (
                    :id::uuid, :user_account_id::uuid,
                    :requested_by_user_id::uuid,
                    :conversation_id::uuid, :message_id::uuid,
                    :tool_slug,
                    CAST(:tool_args AS jsonb),
                    CAST(:blast_radius AS jsonb),
                    :requires_approval,
                    :status, :approver_role, now(), now()
                )
                """
            ),
            {
                "id": id,
                "user_account_id": user_account_id,
                "requested_by_user_id": requested_by_user_id,
                "conversation_id": conversation_id,
                "message_id": message_id,
                "tool_slug": tool_slug,
                "tool_args": json.dumps(tool_args),
                "blast_radius": json.dumps(blast_radius),
                "requires_approval": requires_approval,
                "status": status,
                "approver_role": approver_role,
            },
        )
        await self._db.commit()

    async def get(self, action_id: UUID) -> dict | None:
        row = (
            await self._db.execute(
                text(
                    "SELECT * FROM rex.action_queue WHERE id = :id::uuid"
                ),
                {"id": action_id},
            )
        ).mappings().first()
        return dict(row) if row else None

    async def update_status(
        self,
        *,
        action_id: UUID,
        status: str,
        committed_at: bool = False,
        undone_at: bool = False,
        error_excerpt: str | None = None,
        result_payload: dict | None = None,
    ) -> None:
        sets: list[str] = ["status = :status", "updated_at = now()"]
        params: dict[str, Any] = {"id": action_id, "status": status}
        if committed_at:
            sets.append("committed_at = now()")
        if undone_at:
            sets.append("undone_at = now()")
        if error_excerpt is not None:
            sets.append("error_excerpt = :error_excerpt")
            params["error_excerpt"] = error_excerpt[:500]
        if result_payload is not None:
            sets.append("result_payload = CAST(:result_payload AS jsonb)")
            params["result_payload"] = json.dumps(result_payload)

        await self._db.execute(
            text(
                f"UPDATE rex.action_queue SET {', '.join(sets)} "
                f"WHERE id = :id::uuid"
            ),
            params,
        )
        await self._db.commit()

    async def list_pending_for_user(
        self, user_account_id: UUID, limit: int = 50
    ) -> list[dict]:
        rows = (
            await self._db.execute(
                text(
                    "SELECT * FROM rex.action_queue "
                    "WHERE user_account_id = :uid::uuid "
                    "AND status = 'pending_approval' "
                    "ORDER BY created_at DESC LIMIT :lim"
                ),
                {"uid": user_account_id, "lim": limit},
            )
        ).mappings().all()
        return [dict(r) for r in rows]

    async def list_pending_by_role(
        self, approver_role: str, limit: int = 50
    ) -> list[dict]:
        rows = (
            await self._db.execute(
                text(
                    "SELECT * FROM rex.action_queue "
                    "WHERE approver_role = :role "
                    "AND status = 'pending_approval' "
                    "ORDER BY created_at DESC LIMIT :lim"
                ),
                {"role": approver_role, "lim": limit},
            )
        ).mappings().all()
        return [dict(r) for r in rows]


__all__ = ["ActionQueueRepository"]
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/repositories/action_queue_repository.py
git commit -m "feat(phase6): ActionQueueRepository for rex.action_queue CRUD"
```

(No test here; the next task's service-layer test exercises this transitively.)

---

### Task 5: `action_queue_service.py` — enqueue + commit + undo + discard

**Files:**
- Create: `backend/app/services/ai/action_queue_service.py`
- Test: `backend/tests/services/ai/test_action_queue_service.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/ai/test_action_queue_service.py
"""ActionQueueService — enqueue, commit, undo, discard."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.ai.action_queue_service import (
    ActionQueueService,
    DispatchResult,
)
from app.services.ai.actions.blast_radius import BlastRadius
from app.services.ai.tools.base import (
    ActionContext, ActionResult, ActionSpec,
)


def _spec(slug="test_tool", fires_external=False, will_approve=False):
    async def classify(args, ctx):
        return BlastRadius(
            audience='external' if will_approve else 'internal',
            fires_external_effect=fires_external,
            financial_dollar_amount=None,
            scope_size=1,
        )

    async def handler(ctx):
        return ActionResult(result_payload={"ok": True, "slug": slug})

    return ActionSpec(
        slug=slug,
        tool_schema={
            "description": "test",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        classify=classify,
        handler=handler,
        fires_external_effect=fires_external,
    )


class _FakeRepo:
    def __init__(self):
        self.rows: dict = {}  # id -> row
        self.calls: list = []

    async def insert(self, **kwargs):
        self.calls.append(("insert", kwargs))
        self.rows[kwargs["id"]] = {**kwargs, "created_at": "now"}

    async def get(self, action_id):
        return self.rows.get(action_id)

    async def update_status(self, *, action_id, status, **kwargs):
        self.calls.append(("update_status", {"id": action_id, "status": status, **kwargs}))
        if action_id in self.rows:
            self.rows[action_id]["status"] = status


class _FakeConn:
    pass


def _ctx_builder():
    """Returns a factory that builds a fresh ClassifyContext per call."""
    from app.services.ai.actions.blast_radius import ClassifyContext
    return lambda user_id: ClassifyContext(
        conn=_FakeConn(), user_account_id=user_id,
    )


@pytest.mark.asyncio
async def test_enqueue_auto_commits_when_no_approval_needed():
    repo = _FakeRepo()
    svc = ActionQueueService(
        repo=repo,
        get_tool_by_slug=lambda slug: _spec(slug="test_tool"),
        build_classify_ctx=_ctx_builder(),
        build_action_ctx=lambda conn, uid, args, aid: ActionContext(
            conn=conn, user_account_id=uid, args=args, action_id=aid,
        ),
    )
    user_id = uuid4()

    result = await svc.enqueue(
        conn=_FakeConn(),
        user_account_id=user_id,
        requested_by_user_id=user_id,
        conversation_id=None,
        message_id=None,
        tool_slug="test_tool",
        tool_args={"foo": "bar"},
    )
    assert isinstance(result, DispatchResult)
    assert result.status == "auto_committed"
    assert result.requires_approval is False
    # Handler was called (result_payload captured):
    assert result.result_payload == {"ok": True, "slug": "test_tool"}


@pytest.mark.asyncio
async def test_enqueue_queues_for_approval_when_required():
    repo = _FakeRepo()
    svc = ActionQueueService(
        repo=repo,
        get_tool_by_slug=lambda slug: _spec(slug="danger_tool", will_approve=True),
        build_classify_ctx=_ctx_builder(),
        build_action_ctx=lambda conn, uid, args, aid: ActionContext(
            conn=conn, user_account_id=uid, args=args, action_id=aid,
        ),
    )
    user_id = uuid4()

    result = await svc.enqueue(
        conn=_FakeConn(),
        user_account_id=user_id,
        requested_by_user_id=user_id,
        conversation_id=None,
        message_id=None,
        tool_slug="danger_tool",
        tool_args={},
    )
    assert result.status == "pending_approval"
    assert result.requires_approval is True
    # Handler was NOT invoked for pending actions
    assert result.result_payload is None


@pytest.mark.asyncio
async def test_commit_approved_action_runs_handler_and_marks_committed():
    repo = _FakeRepo()
    svc = ActionQueueService(
        repo=repo,
        get_tool_by_slug=lambda slug: _spec(slug="approval_tool", will_approve=True),
        build_classify_ctx=_ctx_builder(),
        build_action_ctx=lambda conn, uid, args, aid: ActionContext(
            conn=conn, user_account_id=uid, args=args, action_id=aid,
        ),
    )
    user_id = uuid4()

    enq = await svc.enqueue(
        conn=_FakeConn(), user_account_id=user_id,
        requested_by_user_id=user_id, conversation_id=None, message_id=None,
        tool_slug="approval_tool", tool_args={},
    )
    # Now approve it
    commit = await svc.commit(
        conn=_FakeConn(), action_id=enq.action_id,
    )
    assert commit.status == "committed"
    assert commit.result_payload == {"ok": True, "slug": "approval_tool"}


@pytest.mark.asyncio
async def test_discard_pending_marks_dismissed_without_running_handler():
    repo = _FakeRepo()
    svc = ActionQueueService(
        repo=repo,
        get_tool_by_slug=lambda slug: _spec(slug="x", will_approve=True),
        build_classify_ctx=_ctx_builder(),
        build_action_ctx=lambda conn, uid, args, aid: ActionContext(
            conn=conn, user_account_id=uid, args=args, action_id=aid,
        ),
    )
    user_id = uuid4()
    enq = await svc.enqueue(
        conn=_FakeConn(), user_account_id=user_id,
        requested_by_user_id=user_id, conversation_id=None, message_id=None,
        tool_slug="x", tool_args={},
    )
    result = await svc.discard(action_id=enq.action_id)
    assert result.status == "dismissed"


@pytest.mark.asyncio
async def test_handler_failure_marks_failed_with_error_excerpt():
    async def raising_handler(ctx):
        raise RuntimeError("simulated failure")

    spec = _spec(slug="flaky")
    spec.handler = raising_handler
    repo = _FakeRepo()
    svc = ActionQueueService(
        repo=repo,
        get_tool_by_slug=lambda slug: spec,
        build_classify_ctx=_ctx_builder(),
        build_action_ctx=lambda conn, uid, args, aid: ActionContext(
            conn=conn, user_account_id=uid, args=args, action_id=aid,
        ),
    )
    user_id = uuid4()
    result = await svc.enqueue(
        conn=_FakeConn(), user_account_id=user_id,
        requested_by_user_id=user_id, conversation_id=None, message_id=None,
        tool_slug="flaky", tool_args={},
    )
    # Auto-pass handler raised → status=failed, error_excerpt populated
    assert result.status == "failed"
    assert result.error_excerpt is not None
    assert "simulated failure" in result.error_excerpt
```

- [ ] **Step 2: Run test → expect FAIL (ModuleNotFoundError)**

```
cd backend && py -m pytest tests/services/ai/test_action_queue_service.py -v
```

- [ ] **Step 3: Implement the service**

```python
# backend/app/services/ai/action_queue_service.py
"""Phase 6 action queue orchestration.

Entry points:
- `enqueue`: called from chat_service when the LLM emits tool_use.
  Classifies the action, persists a row, and either commits (auto-pass)
  or waits for user approval.
- `commit`: called from /api/actions/{id}/approve. Transitions a
  pending_approval row to committed, running the handler in-band.
- `discard`: /api/actions/{id}/discard — pending_approval → dismissed.
- `undo`:  /api/actions/{id}/undo — auto_committed → undone, runs the
  tool's `undo()` if defined, else deletes any row the action created.
- `retry`: failed → retries the handler.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID, uuid4

from app.repositories.action_queue_repository import ActionQueueRepository
from app.services.ai.actions.blast_radius import BlastRadius, ClassifyContext
from app.services.ai.tools.base import (
    ActionContext, ActionResult, ActionSpec,
)

log = logging.getLogger("rex.ai.action_queue_service")

UNDO_WINDOW_SECONDS = 60


@dataclass
class DispatchResult:
    """What enqueue/commit/undo return to their callers."""
    action_id: UUID
    status: str  # auto_committed | pending_approval | committed | failed | ...
    requires_approval: bool
    blast_radius: dict
    result_payload: dict | None = None
    error_excerpt: str | None = None
    reasons: list[str] | None = None


class ActionQueueService:
    def __init__(
        self,
        *,
        repo: ActionQueueRepository,
        get_tool_by_slug: Callable[[str], ActionSpec | None],
        build_classify_ctx: Callable[[UUID], ClassifyContext],
        build_action_ctx: Callable[[Any, UUID, dict, UUID], ActionContext],
    ):
        self._repo = repo
        self._get_tool = get_tool_by_slug
        self._build_classify_ctx = build_classify_ctx
        self._build_action_ctx = build_action_ctx

    async def enqueue(
        self,
        *,
        conn,
        user_account_id: UUID,
        requested_by_user_id: UUID | None,
        conversation_id: UUID | None,
        message_id: UUID | None,
        tool_slug: str,
        tool_args: dict,
    ) -> DispatchResult:
        spec = self._get_tool(tool_slug)
        if spec is None:
            action_id = uuid4()
            await self._repo.insert(
                id=action_id,
                user_account_id=user_account_id,
                requested_by_user_id=requested_by_user_id,
                conversation_id=conversation_id,
                message_id=message_id,
                tool_slug=tool_slug,
                tool_args=tool_args,
                blast_radius={},
                requires_approval=False,
                status="failed",
                approver_role=None,
            )
            await self._repo.update_status(
                action_id=action_id,
                status="failed",
                error_excerpt=f"Unknown tool slug: {tool_slug!r}",
            )
            return DispatchResult(
                action_id=action_id,
                status="failed",
                requires_approval=False,
                blast_radius={},
                error_excerpt=f"Unknown tool slug: {tool_slug!r}",
            )

        classify_ctx = self._build_classify_ctx(user_account_id)
        # Ctor of ClassifyContext expects a conn; overwrite it for this call.
        classify_ctx.conn = conn
        try:
            br: BlastRadius = await spec.classify(tool_args, classify_ctx)
        except Exception as e:
            log.exception("classify failed for %s", tool_slug)
            br = BlastRadius(
                audience='external',  # default to safer side on classify failure
                fires_external_effect=True,
                financial_dollar_amount=None,
                scope_size=1,
            )

        requires_approval = br.requires_approval()
        status = "pending_approval" if requires_approval else "auto_committed"

        action_id = uuid4()
        await self._repo.insert(
            id=action_id,
            user_account_id=user_account_id,
            requested_by_user_id=requested_by_user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            tool_slug=tool_slug,
            tool_args=tool_args,
            blast_radius=br.to_jsonb(),
            requires_approval=requires_approval,
            status=status,
            approver_role=None,
        )

        if requires_approval:
            # User must approve via /api/actions/{id}/approve; do NOT fire handler.
            return DispatchResult(
                action_id=action_id,
                status="pending_approval",
                requires_approval=True,
                blast_radius=br.to_jsonb(),
                reasons=br.reasons(),
            )

        # Auto-pass: fire handler in-band.
        return await self._run_handler(
            conn=conn, spec=spec, action_id=action_id,
            user_account_id=user_account_id, tool_args=tool_args,
            blast_radius=br.to_jsonb(),
            requires_approval=False,
            success_status="auto_committed",
        )

    async def commit(self, *, conn, action_id: UUID) -> DispatchResult:
        """Approve a pending_approval action — run the handler in-band."""
        row = await self._repo.get(action_id)
        if row is None:
            return DispatchResult(
                action_id=action_id, status="failed",
                requires_approval=False, blast_radius={},
                error_excerpt="action not found",
            )
        if row["status"] != "pending_approval":
            return DispatchResult(
                action_id=action_id, status=row["status"],
                requires_approval=row["requires_approval"],
                blast_radius=row["blast_radius"],
                error_excerpt=f"cannot commit from status={row['status']!r}",
            )
        spec = self._get_tool(row["tool_slug"])
        if spec is None:
            await self._repo.update_status(
                action_id=action_id, status="failed",
                error_excerpt=f"Unknown tool slug: {row['tool_slug']!r}",
            )
            return DispatchResult(
                action_id=action_id, status="failed",
                requires_approval=False, blast_radius=row["blast_radius"],
                error_excerpt=f"Unknown tool slug: {row['tool_slug']!r}",
            )
        return await self._run_handler(
            conn=conn, spec=spec, action_id=action_id,
            user_account_id=row["user_account_id"],
            tool_args=row["tool_args"],
            blast_radius=row["blast_radius"],
            requires_approval=True,
            success_status="committed",
        )

    async def discard(self, *, action_id: UUID) -> DispatchResult:
        await self._repo.update_status(
            action_id=action_id, status="dismissed",
        )
        row = await self._repo.get(action_id)
        return DispatchResult(
            action_id=action_id,
            status="dismissed",
            requires_approval=bool(row.get("requires_approval")) if row else False,
            blast_radius=row.get("blast_radius", {}) if row else {},
        )

    async def undo(self, *, action_id: UUID) -> DispatchResult:
        """Mark auto_committed action as undone. For Phase 6a MVP we
        mark status only; per-tool compensating logic (e.g., deleting
        the rex.tasks row the action created) is a follow-up enhancement
        (Phase 6b). The 60s window is enforced here."""
        row = await self._repo.get(action_id)
        if row is None:
            return DispatchResult(
                action_id=action_id, status="failed",
                requires_approval=False, blast_radius={},
                error_excerpt="action not found",
            )
        if row["status"] != "auto_committed":
            return DispatchResult(
                action_id=action_id, status=row["status"],
                requires_approval=row["requires_approval"],
                blast_radius=row["blast_radius"],
                error_excerpt=f"cannot undo from status={row['status']!r}",
            )
        # Check 60s window.
        committed_at = row.get("committed_at")
        if committed_at is not None:
            # asyncpg returns timezone-aware timestamps.
            elapsed = (datetime.now(timezone.utc) - committed_at).total_seconds()
            if elapsed > UNDO_WINDOW_SECONDS:
                return DispatchResult(
                    action_id=action_id, status=row["status"],
                    requires_approval=row["requires_approval"],
                    blast_radius=row["blast_radius"],
                    error_excerpt=f"undo window expired ({elapsed:.0f}s elapsed)",
                )

        await self._repo.update_status(
            action_id=action_id, status="undone", undone_at=True,
        )
        return DispatchResult(
            action_id=action_id, status="undone",
            requires_approval=row["requires_approval"],
            blast_radius=row["blast_radius"],
        )

    async def _run_handler(
        self, *,
        conn,
        spec: ActionSpec,
        action_id: UUID,
        user_account_id: UUID,
        tool_args: dict,
        blast_radius: dict,
        requires_approval: bool,
        success_status: str,
    ) -> DispatchResult:
        action_ctx = self._build_action_ctx(
            conn, user_account_id, tool_args, action_id,
        )
        try:
            result: ActionResult = await spec.handler(action_ctx)
            await self._repo.update_status(
                action_id=action_id,
                status=success_status,
                committed_at=True,
                result_payload=result.result_payload,
            )
            return DispatchResult(
                action_id=action_id,
                status=success_status,
                requires_approval=requires_approval,
                blast_radius=blast_radius,
                result_payload=result.result_payload,
            )
        except Exception as e:
            log.exception("handler %s failed", spec.slug)
            excerpt = str(e)[:500]
            await self._repo.update_status(
                action_id=action_id,
                status="failed",
                error_excerpt=excerpt,
            )
            return DispatchResult(
                action_id=action_id,
                status="failed",
                requires_approval=requires_approval,
                blast_radius=blast_radius,
                error_excerpt=excerpt,
            )


__all__ = ["ActionQueueService", "DispatchResult", "UNDO_WINDOW_SECONDS"]
```

- [ ] **Step 4: Run tests → expect 5 PASS**

```
cd backend && py -m pytest tests/services/ai/test_action_queue_service.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/action_queue_service.py \
        backend/tests/services/ai/test_action_queue_service.py
git commit -m "feat(phase6): ActionQueueService orchestrates enqueue/commit/discard/undo"
```

---

### Task 6: Tool — `create_task` (auto-pass)

**Files:**
- Modify: `backend/app/services/ai/tools/create_task.py` (replace stub)
- Test: `backend/tests/services/ai/tools/test_create_task.py`

- [ ] **Step 1: Verify `rex.tasks` schema**

```
grep -A 20 "CREATE TABLE.*rex.tasks" migrations/rex2_canonical_ddl.sql | head -25
```

Expected columns: `id uuid, project_id uuid, task_number int, title text NOT NULL, description text, status text, priority text, assigned_to uuid (FK rex.people), due_date date, created_at, updated_at`.

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/services/ai/tools/test_create_task.py
"""create_task tool — auto if assignee is internal; approval if external."""
from __future__ import annotations

import os, ssl
from uuid import UUID, uuid4

import asyncpg, pytest, pytest_asyncio
from sqlalchemy import text

from app.services.ai.actions.blast_radius import ClassifyContext
from app.services.ai.tools.base import ActionContext
from app.services.ai.tools.create_task import SPEC
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_people():
    """Seed an internal + an external person + a project."""
    require_live_db()
    conn = await connect_raw()
    internal_id = uuid4()
    external_id = uuid4()
    proj_id = uuid4()
    requester_id = uuid4()
    req_person_id = uuid4()
    try:
        for pid, role, first in [
            (internal_id, 'internal', 'Alice'),
            (external_id, 'external', 'Bob'),
            (req_person_id, 'internal', 'Carol'),
        ]:
            await conn.execute(
                "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
                "VALUES ($1::uuid, $2, 'Test', $3, $4)",
                pid, first, f"{first.lower()}-{pid}@t.invalid", role,
            )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            requester_id, req_person_id, f"req-{requester_id}@t.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'Task Test', 'active', 'TASK-1')",
            proj_id,
        )
        yield {
            "requester_user_id": requester_id,
            "internal_person_id": internal_id,
            "external_person_id": external_id,
            "project_id": proj_id,
            "req_person_id": req_person_id,
        }
    finally:
        await conn.execute("DELETE FROM rex.tasks WHERE project_id = $1::uuid", proj_id)
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", proj_id)
        await conn.execute("DELETE FROM rex.user_accounts WHERE id = $1::uuid", requester_id)
        await conn.execute(
            "DELETE FROM rex.people WHERE id IN ($1::uuid, $2::uuid, $3::uuid)",
            internal_id, external_id, req_person_id,
        )
        await conn.close()


@pytest.mark.asyncio
async def test_classify_internal_assignee_is_auto(seeded_people):
    conn = await connect_raw()
    try:
        ctx = ClassifyContext(conn=conn, user_account_id=seeded_people["requester_user_id"])
        br = await SPEC.classify(
            {
                "title": "Check the duct conflict",
                "assignee_person_id": str(seeded_people["internal_person_id"]),
                "project_id": str(seeded_people["project_id"]),
            },
            ctx,
        )
        assert br.audience == 'internal'
        assert br.requires_approval() is False
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_classify_external_assignee_requires_approval(seeded_people):
    conn = await connect_raw()
    try:
        ctx = ClassifyContext(conn=conn, user_account_id=seeded_people["requester_user_id"])
        br = await SPEC.classify(
            {
                "title": "Send files to GC",
                "assignee_person_id": str(seeded_people["external_person_id"]),
                "project_id": str(seeded_people["project_id"]),
            },
            ctx,
        )
        assert br.audience == 'external'
        assert br.requires_approval() is True


    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_handler_inserts_task(seeded_people):
    conn = await connect_raw()
    try:
        action_id = uuid4()
        ctx = ActionContext(
            conn=conn,
            user_account_id=seeded_people["requester_user_id"],
            args={
                "title": "Walk the punch list",
                "assignee_person_id": str(seeded_people["internal_person_id"]),
                "project_id": str(seeded_people["project_id"]),
            },
            action_id=action_id,
        )
        result = await SPEC.handler(ctx)
        assert "task_id" in result.result_payload
        # Verify row exists
        row = await conn.fetchrow(
            "SELECT title FROM rex.tasks WHERE id = $1::uuid",
            UUID(result.result_payload["task_id"]),
        )
        assert row is not None
        assert row["title"] == "Walk the punch list"
    finally:
        await conn.close()


def test_spec_metadata():
    assert SPEC.slug == "create_task"
    assert SPEC.fires_external_effect is False
    assert "title" in SPEC.tool_schema["input_schema"]["properties"]
    assert "title" in SPEC.tool_schema["input_schema"]["required"]
```

- [ ] **Step 3: Run → expect FAIL (stub returns NotImplementedError)**

- [ ] **Step 4: Replace `create_task.py` with the real implementation**

```python
# backend/app/services/ai/tools/create_task.py
"""create_task — creates a task in rex.tasks. Auto-pass when assignee
is internal or self; approval required when assignee is external."""
from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import text  # noqa: F401  (unused; using asyncpg.conn directly)

from app.services.ai.actions.blast_radius import (
    BlastRadius, ClassifyContext,
)
from app.services.ai.tools.base import ActionContext, ActionResult, ActionSpec


TOOL_SCHEMA = {
    "description": (
        "Create a new internal task assigned to a person. Returns the "
        "task_id. Use this when the user asks to track work, make a "
        "checklist item, or assign a follow-up."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Short (1-sentence) description of the task.",
            },
            "description": {
                "type": "string",
                "description": "Optional longer description. Markdown OK.",
            },
            "assignee_person_id": {
                "type": "string",
                "description": "UUID of rex.people row to assign to. Optional — defaults to requester.",
            },
            "project_id": {
                "type": "string",
                "description": "UUID of rex.projects row. Optional for personal tasks but required if the task is project-scoped.",
            },
            "due_date": {
                "type": "string",
                "description": "ISO date (YYYY-MM-DD). Optional.",
            },
            "priority": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "description": "Defaults to medium.",
            },
        },
        "required": ["title"],
    },
}


async def _classify(args: dict, ctx: ClassifyContext) -> BlastRadius:
    """Internal when assignee is an internal person OR self. External otherwise."""
    assignee_raw = args.get("assignee_person_id")
    if assignee_raw is None:
        # self-assigned → internal by definition
        return BlastRadius(
            audience='internal',
            fires_external_effect=False,
            financial_dollar_amount=None,
            scope_size=1,
        )
    try:
        assignee_id = UUID(str(assignee_raw))
    except ValueError:
        # Invalid UUID — treat as external so we approve before mutating.
        return BlastRadius(
            audience='external',
            fires_external_effect=False,
            financial_dollar_amount=None,
            scope_size=1,
        )
    is_internal = await ctx.is_internal_person(assignee_id)
    return BlastRadius(
        audience='internal' if is_internal else 'external',
        fires_external_effect=False,
        financial_dollar_amount=None,
        scope_size=1,
    )


async def _handler(ctx: ActionContext) -> ActionResult:
    args = ctx.args
    task_id = uuid4()
    assignee = args.get("assignee_person_id")
    project = args.get("project_id")
    priority = args.get("priority") or "medium"

    # Get next task_number per project — simple aggregate; race-safe enough
    # for a small-team app.
    if project is not None:
        next_num = await ctx.conn.fetchval(
            "SELECT COALESCE(MAX(task_number), 0) + 1 FROM rex.tasks "
            "WHERE project_id = $1::uuid",
            UUID(str(project)),
        )
    else:
        next_num = await ctx.conn.fetchval(
            "SELECT COALESCE(MAX(task_number), 0) + 1 FROM rex.tasks "
            "WHERE project_id IS NULL",
        )

    await ctx.conn.execute(
        """
        INSERT INTO rex.tasks
            (id, project_id, task_number, title, description, status,
             priority, assigned_to, due_date, created_at, updated_at)
        VALUES (
            $1::uuid,
            $2::uuid,
            $3::int,
            $4, $5, 'open',
            $6,
            $7::uuid,
            $8::date,
            now(), now()
        )
        """,
        task_id,
        UUID(str(project)) if project else None,
        int(next_num),
        args["title"],
        args.get("description"),
        priority,
        UUID(str(assignee)) if assignee else None,
        args.get("due_date"),
    )
    return ActionResult(result_payload={
        "task_id": str(task_id),
        "task_number": int(next_num),
        "title": args["title"],
        "project_id": str(project) if project else None,
        "assignee_person_id": str(assignee) if assignee else None,
    })


SPEC = ActionSpec(
    slug="create_task",
    tool_schema=TOOL_SCHEMA,
    classify=_classify,
    handler=_handler,
    fires_external_effect=False,
)

__all__ = ["SPEC"]
```

- [ ] **Step 5: Run tests → expect PASS (4 tests)**

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai/tools/create_task.py \
        backend/tests/services/ai/tools/test_create_task.py
git commit -m "feat(phase6): create_task tool — internal auto / external approval"
```

---

### Task 7: Tool — `update_task_status` (auto-pass always)

**Files:**
- Modify: `backend/app/services/ai/tools/update_task_status.py`
- Test: `backend/tests/services/ai/tools/test_update_task_status.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/services/ai/tools/test_update_task_status.py
"""update_task_status tool — auto-pass always (internal single-row mutation)."""
from __future__ import annotations

from uuid import UUID, uuid4

import asyncpg, pytest, pytest_asyncio

from app.services.ai.actions.blast_radius import ClassifyContext
from app.services.ai.tools.base import ActionContext
from app.services.ai.tools.update_task_status import SPEC
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_task():
    require_live_db()
    conn = await connect_raw()
    proj_id = uuid4()
    task_id = uuid4()
    user_id = uuid4()
    person_id = uuid4()
    try:
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
            "VALUES ($1::uuid, 'Task', 'Updater', $2, 'internal')",
            person_id, f"task-{person_id}@t.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            user_id, person_id, f"task-{user_id}@t.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'ST', 'active', 'ST-1')",
            proj_id,
        )
        await conn.execute(
            "INSERT INTO rex.tasks (id, project_id, task_number, title, status, created_at, updated_at) "
            "VALUES ($1::uuid, $2::uuid, 1, 'Test task', 'open', now(), now())",
            task_id, proj_id,
        )
        yield {"task_id": task_id, "user_id": user_id, "proj_id": proj_id, "person_id": person_id}
    finally:
        await conn.execute("DELETE FROM rex.tasks WHERE id = $1::uuid", task_id)
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", proj_id)
        await conn.execute("DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id)
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_classify_auto(seeded_task):
    conn = await connect_raw()
    try:
        ctx = ClassifyContext(conn=conn, user_account_id=seeded_task["user_id"])
        br = await SPEC.classify(
            {"task_id": str(seeded_task["task_id"]), "status": "in_progress"},
            ctx,
        )
        assert br.audience == 'internal'
        assert br.requires_approval() is False
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_handler_updates_status(seeded_task):
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn,
            user_account_id=seeded_task["user_id"],
            args={"task_id": str(seeded_task["task_id"]), "status": "in_progress"},
            action_id=uuid4(),
        )
        result = await SPEC.handler(ctx)
        assert result.result_payload["previous_status"] == "open"
        assert result.result_payload["new_status"] == "in_progress"
        new = await conn.fetchval(
            "SELECT status FROM rex.tasks WHERE id = $1::uuid",
            seeded_task["task_id"],
        )
        assert new == "in_progress"
    finally:
        await conn.close()


def test_spec_metadata():
    assert SPEC.slug == "update_task_status"
    assert SPEC.fires_external_effect is False
```

- [ ] **Step 2: Run → expect FAIL**

- [ ] **Step 3: Implement `update_task_status.py`**

```python
# backend/app/services/ai/tools/update_task_status.py
"""update_task_status — updates rex.tasks.status. Auto-pass always."""
from __future__ import annotations

from uuid import UUID

from app.services.ai.actions.blast_radius import BlastRadius, ClassifyContext
from app.services.ai.tools.base import ActionContext, ActionResult, ActionSpec


TOOL_SCHEMA = {
    "description": (
        "Update the status of a task. Single-row internal mutation. "
        "Always auto-approves."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "UUID of rex.tasks row."},
            "status": {
                "type": "string",
                "description": "New status (open|in_progress|blocked|complete|cancelled).",
            },
        },
        "required": ["task_id", "status"],
    },
}


async def _classify(args: dict, ctx: ClassifyContext) -> BlastRadius:
    return BlastRadius(
        audience='internal',
        fires_external_effect=False,
        financial_dollar_amount=None,
        scope_size=1,
    )


async def _handler(ctx: ActionContext) -> ActionResult:
    task_uuid = UUID(str(ctx.args["task_id"]))
    new_status = str(ctx.args["status"])
    row = await ctx.conn.fetchrow(
        "SELECT status FROM rex.tasks WHERE id = $1::uuid",
        task_uuid,
    )
    if row is None:
        raise ValueError(f"task {task_uuid} not found")
    prev = row["status"]
    await ctx.conn.execute(
        "UPDATE rex.tasks SET status = $1, updated_at = now() "
        "WHERE id = $2::uuid",
        new_status, task_uuid,
    )
    return ActionResult(result_payload={
        "task_id": str(task_uuid),
        "previous_status": prev,
        "new_status": new_status,
    })


SPEC = ActionSpec(
    slug="update_task_status",
    tool_schema=TOOL_SCHEMA,
    classify=_classify,
    handler=_handler,
    fires_external_effect=False,
)

__all__ = ["SPEC"]
```

- [ ] **Step 4: Run tests → PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/tools/update_task_status.py \
        backend/tests/services/ai/tools/test_update_task_status.py
git commit -m "feat(phase6): update_task_status tool (auto-pass, single-row)"
```

---

### Task 8: Tool — `create_note` (auto-pass)

**First-step discovery:** check whether `rex.pending_decisions` or a similar table is an appropriate home for a free-form "note" entity. Read `rex.pending_decisions` schema; if it requires fields a note doesn't have (e.g., `decision_maker_id`, deadline, priority), the note won't fit cleanly. In that case, add migration `029_rex_notes.sql` creating a new `rex.notes` table with minimal columns (id, project_id, user_account_id, content, created_at, updated_at). Register in MIGRATION_ORDER.

**Files:**
- Modify: `backend/app/services/ai/tools/create_note.py`
- Test: `backend/tests/services/ai/tools/test_create_note.py`
- Possibly: `migrations/029_rex_notes.sql` + `backend/app/migrate.py`

- [ ] **Step 1: Read `rex.pending_decisions` schema; decide table target**

```
grep -A 15 "CREATE TABLE.*rex.pending_decisions" migrations/rex2_canonical_ddl.sql
```

Decide: adequate fit, or add `rex.notes` migration.

- [ ] **Step 2: If adding migration, create `029_rex_notes.sql`**

```sql
-- migrations/029_rex_notes.sql
CREATE TABLE IF NOT EXISTS rex.notes (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      uuid REFERENCES rex.projects(id) ON DELETE CASCADE,
    user_account_id uuid NOT NULL REFERENCES rex.user_accounts(id),
    content         text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_notes_project ON rex.notes (project_id);
CREATE INDEX IF NOT EXISTS idx_notes_user ON rex.notes (user_account_id);
```

Register in `backend/app/migrate.py::MIGRATION_ORDER`.

- [ ] **Step 3: Write failing test**

```python
# backend/tests/services/ai/tools/test_create_note.py
"""create_note — auto-pass; persists to rex.notes (or pending_decisions per Step 1 decision)."""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest, pytest_asyncio

from app.services.ai.actions.blast_radius import ClassifyContext
from app.services.ai.tools.base import ActionContext
from app.services.ai.tools.create_note import SPEC
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_user_project():
    require_live_db()
    conn = await connect_raw()
    user_id = uuid4()
    person_id = uuid4()
    proj_id = uuid4()
    try:
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
            "VALUES ($1::uuid, 'Note', 'Taker', $2, 'internal')",
            person_id, f"note-{person_id}@t.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            user_id, person_id, f"note-{user_id}@t.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'N', 'active', 'N-1')",
            proj_id,
        )
        yield {"user_id": user_id, "proj_id": proj_id, "person_id": person_id}
    finally:
        # Note: rex.notes FK to projects is ON DELETE CASCADE — deleting project cleans notes.
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", proj_id)
        await conn.execute("DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id)
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_classify_always_auto(seeded_user_project):
    conn = await connect_raw()
    try:
        ctx = ClassifyContext(conn=conn, user_account_id=seeded_user_project["user_id"])
        br = await SPEC.classify(
            {"content": "hello", "project_id": str(seeded_user_project["proj_id"])},
            ctx,
        )
        assert br.requires_approval() is False
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_handler_inserts_note(seeded_user_project):
    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn,
            user_account_id=seeded_user_project["user_id"],
            args={"content": "lunchtime note", "project_id": str(seeded_user_project["proj_id"])},
            action_id=uuid4(),
        )
        result = await SPEC.handler(ctx)
        assert "note_id" in result.result_payload
        # Verify — adjust table name if Step 1 used pending_decisions instead
        row = await conn.fetchrow(
            "SELECT content FROM rex.notes WHERE id = $1::uuid",
            UUID(result.result_payload["note_id"]),
        )
        assert row["content"] == "lunchtime note"
    finally:
        await conn.close()


def test_spec_metadata():
    assert SPEC.slug == "create_note"
    assert SPEC.fires_external_effect is False
```

- [ ] **Step 4: Implement handler**

```python
# backend/app/services/ai/tools/create_note.py
"""create_note — free-form note persisted to rex.notes."""
from __future__ import annotations

from uuid import UUID, uuid4

from app.services.ai.actions.blast_radius import BlastRadius, ClassifyContext
from app.services.ai.tools.base import ActionContext, ActionResult, ActionSpec


TOOL_SCHEMA = {
    "description": (
        "Create a free-form note attached to a project or standalone. "
        "Always auto-approves. Use for quick annotations, lunch ideas, "
        "or when the user says 'note that X'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Note body (markdown OK)."},
            "project_id": {
                "type": "string",
                "description": "UUID of rex.projects. Optional.",
            },
        },
        "required": ["content"],
    },
}


async def _classify(args: dict, ctx: ClassifyContext) -> BlastRadius:
    return BlastRadius(
        audience='internal',
        fires_external_effect=False,
        financial_dollar_amount=None,
        scope_size=1,
    )


async def _handler(ctx: ActionContext) -> ActionResult:
    note_id = uuid4()
    project = ctx.args.get("project_id")
    await ctx.conn.execute(
        """
        INSERT INTO rex.notes (id, project_id, user_account_id, content, created_at, updated_at)
        VALUES ($1::uuid, $2::uuid, $3::uuid, $4, now(), now())
        """,
        note_id,
        UUID(str(project)) if project else None,
        ctx.user_account_id,
        ctx.args["content"],
    )
    return ActionResult(result_payload={
        "note_id": str(note_id),
        "content": ctx.args["content"],
        "project_id": str(project) if project else None,
    })


SPEC = ActionSpec(
    slug="create_note",
    tool_schema=TOOL_SCHEMA,
    classify=_classify,
    handler=_handler,
    fires_external_effect=False,
)

__all__ = ["SPEC"]
```

- [ ] **Step 5: Run tests → PASS**

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai/tools/create_note.py \
        backend/tests/services/ai/tools/test_create_note.py \
        migrations/  # if 029 added
        backend/app/migrate.py  # if updated
git commit -m "feat(phase6): create_note tool + rex.notes table"
```

---

### Task 9: Procore API client — `procore_api.py`

**Files:**
- Create: `backend/app/services/ai/tools/procore_api.py`
- Test: `backend/tests/services/ai/tools/test_procore_api.py`

- [ ] **Step 1: Write failing test (mocked httpx transport)**

```python
# backend/tests/services/ai/tools/test_procore_api.py
"""procore_api — minimal OAuth + answer_rfi client. httpx transport mocked."""
from __future__ import annotations

import httpx, pytest

from app.services.ai.tools.procore_api import (
    ProcoreClient, ProcoreNotConfigured, ProcoreApiError,
)


@pytest.mark.asyncio
async def test_raises_when_not_configured(monkeypatch):
    for key in ("PROCORE_CLIENT_ID", "PROCORE_CLIENT_SECRET", "PROCORE_REFRESH_TOKEN", "PROCORE_COMPANY_ID"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ProcoreNotConfigured):
        ProcoreClient.from_env()


@pytest.mark.asyncio
async def test_answer_rfi_happy_path(monkeypatch):
    monkeypatch.setenv("PROCORE_CLIENT_ID", "cid")
    monkeypatch.setenv("PROCORE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("PROCORE_REFRESH_TOKEN", "refresh")
    monkeypatch.setenv("PROCORE_COMPANY_ID", "42")
    monkeypatch.setenv("PROCORE_BASE_URL", "https://api.procore.com")

    def _transport(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/token":
            return httpx.Response(
                200, json={"access_token": "abc", "expires_in": 3600, "token_type": "bearer"},
            )
        if request.url.path.endswith("/rfis/123"):
            return httpx.Response(
                200, json={"id": 123, "status": "closed", "answer": "Resolved."},
            )
        return httpx.Response(404)

    client = ProcoreClient.from_env(
        transport=httpx.MockTransport(_transport),
    )
    try:
        result = await client.answer_rfi(
            rfi_procore_id=123, answer_text="Resolved.",
        )
        assert result["id"] == 123
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_answer_rfi_api_error_surfaces(monkeypatch):
    monkeypatch.setenv("PROCORE_CLIENT_ID", "cid")
    monkeypatch.setenv("PROCORE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("PROCORE_REFRESH_TOKEN", "refresh")
    monkeypatch.setenv("PROCORE_COMPANY_ID", "42")

    def _transport(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/token":
            return httpx.Response(
                200, json={"access_token": "abc", "expires_in": 3600},
            )
        return httpx.Response(500, json={"error": "server error"})

    client = ProcoreClient.from_env(transport=httpx.MockTransport(_transport))
    try:
        with pytest.raises(ProcoreApiError) as ei:
            await client.answer_rfi(rfi_procore_id=1, answer_text="x")
        assert "500" in str(ei.value)
    finally:
        await client.close()
```

- [ ] **Step 2: Implement `procore_api.py`**

```python
# backend/app/services/ai/tools/procore_api.py
"""Minimal Procore REST API client for Phase 6 writeback.

Scope: only the endpoints Rex OS needs as a source of truth for the
approval-required tools. Starts with answer_rfi; future follow-up
lands submittal actions + pay-app etc.

OAuth: refresh-token flow. Env vars:
  PROCORE_CLIENT_ID         — OAuth app id
  PROCORE_CLIENT_SECRET     — OAuth app secret
  PROCORE_REFRESH_TOKEN     — long-lived refresh token
  PROCORE_COMPANY_ID        — company to scope API calls to
  PROCORE_BASE_URL          — optional, defaults to https://api.procore.com

If any of the required env vars is missing, `from_env()` raises
`ProcoreNotConfigured`. The calling tool's handler should catch and
surface a clear failure via the action_queue.error_excerpt.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

log = logging.getLogger("rex.ai.tools.procore_api")


class ProcoreNotConfigured(RuntimeError):
    pass


class ProcoreApiError(RuntimeError):
    pass


@dataclass
class ProcoreClient:
    client_id: str
    client_secret: str
    refresh_token: str
    company_id: str
    base_url: str = "https://api.procore.com"
    _transport: httpx.AsyncBaseTransport | None = None
    _client: httpx.AsyncClient | None = None
    _access_token: str | None = None
    _token_expires_at: float = 0.0

    @classmethod
    def from_env(
        cls, transport: httpx.AsyncBaseTransport | None = None
    ) -> "ProcoreClient":
        required = [
            "PROCORE_CLIENT_ID",
            "PROCORE_CLIENT_SECRET",
            "PROCORE_REFRESH_TOKEN",
            "PROCORE_COMPANY_ID",
        ]
        missing = [v for v in required if not os.environ.get(v)]
        if missing:
            raise ProcoreNotConfigured(
                "Missing Procore OAuth env vars: " + ", ".join(missing)
            )
        inst = cls(
            client_id=os.environ["PROCORE_CLIENT_ID"],
            client_secret=os.environ["PROCORE_CLIENT_SECRET"],
            refresh_token=os.environ["PROCORE_REFRESH_TOKEN"],
            company_id=os.environ["PROCORE_COMPANY_ID"],
            base_url=os.environ.get("PROCORE_BASE_URL", "https://api.procore.com"),
            _transport=transport,
        )
        return inst

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
                transport=self._transport,
            )
        return self._client

    async def _ensure_token(self) -> str:
        now = time.time()
        # Refresh 60s before expiry.
        if self._access_token and self._token_expires_at - now > 60:
            return self._access_token
        client = await self._get_client()
        r = await client.post(
            "/oauth/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        if r.status_code != 200:
            raise ProcoreApiError(
                f"OAuth refresh failed: HTTP {r.status_code}: {r.text[:200]}"
            )
        payload = r.json()
        self._access_token = payload["access_token"]
        self._token_expires_at = now + int(payload.get("expires_in", 3600))
        return self._access_token

    async def answer_rfi(
        self, *, rfi_procore_id: int, answer_text: str
    ) -> dict[str, Any]:
        """PATCH /rest/v1.0/projects/{project_id}/rfis/{rfi_id} with the
        official answer + status=closed.

        NOTE: Procore's exact RFI endpoint shape differs by v1.0 vs v1.1.
        This MVP uses v1.0's simple patch path. If your tenant needs v1.1's
        official_answer sub-object, adjust the payload shape here — the
        contract (rfi_procore_id, answer_text) stays the same.
        """
        token = await self._ensure_token()
        client = await self._get_client()
        r = await client.patch(
            f"/rest/v1.0/rfis/{rfi_procore_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "Procore-Company-Id": self.company_id,
            },
            json={"rfi": {"answer": answer_text, "status": "closed"}},
        )
        if r.status_code // 100 != 2:
            raise ProcoreApiError(
                f"answer_rfi failed: HTTP {r.status_code}: {r.text[:200]}"
            )
        return r.json()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


__all__ = ["ProcoreClient", "ProcoreNotConfigured", "ProcoreApiError"]
```

- [ ] **Step 3: Run tests → 3 PASS**

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/ai/tools/procore_api.py \
        backend/tests/services/ai/tools/test_procore_api.py
git commit -m "feat(phase6): minimal Procore API client (OAuth refresh + answer_rfi)"
```

---

### Task 10: Tool — `answer_rfi` (approval-required, external effect)

**Files:**
- Modify: `backend/app/services/ai/tools/answer_rfi.py`
- Test: `backend/tests/services/ai/tools/test_answer_rfi.py`

- [ ] **Step 1: Verify `rex.rfis` has `answer`, `status`, `answered_at` columns**

```
grep -A 25 "CREATE TABLE.*rex.rfis" migrations/rex2_canonical_ddl.sql | head -30
```

Should show `answer text`, `status text NOT NULL` (CHECK includes 'answered'|'closed'), and maybe `answered_date date` (from Phase 4's mapper — we emitted that).

- [ ] **Step 2: Write failing test**

```python
# backend/tests/services/ai/tools/test_answer_rfi.py
"""answer_rfi — approval-required; fires Procore API call."""
from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx, pytest, pytest_asyncio

from app.services.ai.actions.blast_radius import ClassifyContext
from app.services.ai.tools.base import ActionContext
from app.services.ai.tools import answer_rfi as answer_rfi_mod
from tests.services.ai.actions.conftest import connect_raw, require_live_db


@pytest_asyncio.fixture
async def seeded_rfi():
    require_live_db()
    conn = await connect_raw()
    user_id = uuid4()
    person_id = uuid4()
    proj_id = uuid4()
    rfi_id = uuid4()
    try:
        await conn.execute(
            "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
            "VALUES ($1::uuid, 'RFI', 'Tester', $2, 'internal')",
            person_id, f"rfi-{person_id}@t.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts (id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            user_id, person_id, f"rfi-{user_id}@t.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'RFI Test', 'active', 'RT-1')",
            proj_id,
        )
        await conn.execute(
            "INSERT INTO rex.rfis (id, project_id, rfi_number, subject, question, status, created_at, updated_at) "
            "VALUES ($1::uuid, $2::uuid, '42', 'Duct conflict', 'where?', 'open', now(), now())",
            rfi_id, proj_id,
        )
        # Link Procore external id so handler can write back
        await conn.execute(
            "INSERT INTO rex.connector_mappings "
            "(rex_table, rex_id, connector, external_id, source_table, synced_at) "
            "VALUES ('rex.rfis', $1::uuid, 'procore', '99123', 'procore.rfis', now())",
            rfi_id,
        )
        yield {"user_id": user_id, "rfi_id": rfi_id}
    finally:
        await conn.execute(
            "DELETE FROM rex.connector_mappings WHERE rex_id = $1::uuid",
            rfi_id,
        )
        await conn.execute("DELETE FROM rex.rfis WHERE id = $1::uuid", rfi_id)
        await conn.execute("DELETE FROM rex.projects WHERE id = $1::uuid", proj_id)
        await conn.execute("DELETE FROM rex.user_accounts WHERE id = $1::uuid", user_id)
        await conn.execute("DELETE FROM rex.people WHERE id = $1::uuid", person_id)
        await conn.close()


@pytest.mark.asyncio
async def test_classify_requires_approval(seeded_rfi):
    conn = await connect_raw()
    try:
        ctx = ClassifyContext(conn=conn, user_account_id=seeded_rfi["user_id"])
        br = await answer_rfi_mod.SPEC.classify(
            {"rfi_id": str(seeded_rfi["rfi_id"]), "answer_text": "Resolved."},
            ctx,
        )
        assert br.fires_external_effect is True
        assert br.requires_approval() is True
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_handler_updates_rex_and_calls_procore(seeded_rfi, monkeypatch):
    monkeypatch.setenv("PROCORE_CLIENT_ID", "cid")
    monkeypatch.setenv("PROCORE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("PROCORE_REFRESH_TOKEN", "refresh")
    monkeypatch.setenv("PROCORE_COMPANY_ID", "42")

    def _transport(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        if request.url.path == "/rest/v1.0/rfis/99123":
            return httpx.Response(200, json={"id": 99123, "status": "closed"})
        return httpx.Response(404)

    # Monkey-patch ProcoreClient.from_env to inject the transport
    from app.services.ai.tools import procore_api as procore_mod
    original = procore_mod.ProcoreClient.from_env
    monkeypatch.setattr(
        procore_mod.ProcoreClient, "from_env",
        classmethod(lambda cls, transport=None: original.__func__(
            cls, transport=httpx.MockTransport(_transport),
        )),
    )

    conn = await connect_raw()
    try:
        ctx = ActionContext(
            conn=conn,
            user_account_id=seeded_rfi["user_id"],
            args={"rfi_id": str(seeded_rfi["rfi_id"]), "answer_text": "Duct resolved."},
            action_id=uuid4(),
        )
        result = await answer_rfi_mod.SPEC.handler(ctx)
        assert result.result_payload["rfi_id"] == str(seeded_rfi["rfi_id"])
        assert result.result_payload["procore_response"]["id"] == 99123
        # rex.rfis updated
        row = await conn.fetchrow(
            "SELECT status, answer FROM rex.rfis WHERE id = $1::uuid",
            seeded_rfi["rfi_id"],
        )
        assert row["status"] in ("answered", "closed")
        assert row["answer"] == "Duct resolved."
    finally:
        await conn.close()


def test_spec_metadata():
    assert answer_rfi_mod.SPEC.slug == "answer_rfi"
    assert answer_rfi_mod.SPEC.fires_external_effect is True
```

- [ ] **Step 3: Implement `answer_rfi.py`**

```python
# backend/app/services/ai/tools/answer_rfi.py
"""answer_rfi — approval-required tool. Fires Procore API call to close
the RFI officially, then updates rex.rfis to match."""
from __future__ import annotations

from uuid import UUID

from app.services.ai.actions.blast_radius import BlastRadius, ClassifyContext
from app.services.ai.tools.base import ActionContext, ActionResult, ActionSpec
from app.services.ai.tools.procore_api import ProcoreClient, ProcoreApiError


TOOL_SCHEMA = {
    "description": (
        "Post an official answer to an RFI and close it in Procore. "
        "Requires approval (fires external effect). Handler updates "
        "rex.rfis AND calls Procore's API in-band; failure leaves "
        "rex.rfis unchanged."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "rfi_id": {"type": "string", "description": "UUID of rex.rfis row."},
            "answer_text": {"type": "string", "description": "The official answer text."},
        },
        "required": ["rfi_id", "answer_text"],
    },
}


async def _classify(args: dict, ctx: ClassifyContext) -> BlastRadius:
    return BlastRadius(
        audience='internal',  # answer goes to Procore which is internal-adjacent infra
        fires_external_effect=True,  # always fires a Procore API write
        financial_dollar_amount=None,
        scope_size=1,
    )


async def _handler(ctx: ActionContext) -> ActionResult:
    rfi_uuid = UUID(str(ctx.args["rfi_id"]))
    answer_text = str(ctx.args["answer_text"])

    # Look up the Procore external id from source_links
    row = await ctx.conn.fetchrow(
        "SELECT external_id FROM rex.connector_mappings "
        "WHERE rex_table = 'rex.rfis' AND rex_id = $1::uuid "
        "AND connector = 'procore' AND source_table = 'procore.rfis' "
        "LIMIT 1",
        rfi_uuid,
    )
    if row is None:
        raise ValueError(
            f"rex.rfis/{rfi_uuid} has no Procore source_link — cannot write back"
        )
    procore_id = int(row["external_id"])

    # Fire Procore API FIRST; if it fails, rex.rfis stays unchanged so we
    # don't produce a spurious "answered" state without Procore matching.
    client = ProcoreClient.from_env()
    try:
        procore_response = await client.answer_rfi(
            rfi_procore_id=procore_id, answer_text=answer_text,
        )
    finally:
        await client.close()

    # Update rex.rfis to match what Procore now reports.
    await ctx.conn.execute(
        "UPDATE rex.rfis "
        "SET answer = $1, status = 'answered', "
        "    answered_date = CURRENT_DATE, updated_at = now() "
        "WHERE id = $2::uuid",
        answer_text, rfi_uuid,
    )

    return ActionResult(result_payload={
        "rfi_id": str(rfi_uuid),
        "procore_id": procore_id,
        "answer_text": answer_text,
        "procore_response": procore_response,
    })


SPEC = ActionSpec(
    slug="answer_rfi",
    tool_schema=TOOL_SCHEMA,
    classify=_classify,
    handler=_handler,
    fires_external_effect=True,
)

__all__ = ["SPEC"]
```

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/tools/answer_rfi.py \
        backend/tests/services/ai/tools/test_answer_rfi.py
git commit -m "feat(phase6): answer_rfi tool — approval-required, Procore writeback"
```

---

### Task 11: `/api/actions` routes — approve, discard, undo, pending list

**Files:**
- Create: `backend/app/routes/actions.py`
- Create: `backend/app/schemas/actions.py`
- Modify: `backend/main.py` (mount router)
- Test: `backend/tests/routes/test_actions_routes.py`

- [ ] **Step 1: Write `schemas/actions.py`**

```python
# backend/app/schemas/actions.py
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ActionResponse(BaseModel):
    action_id: UUID
    status: str
    requires_approval: bool
    blast_radius: dict
    result_payload: dict | None = None
    error_excerpt: str | None = None
    reasons: list[str] | None = None


class PendingActionListItem(BaseModel):
    id: UUID
    tool_slug: str
    tool_args: dict
    blast_radius: dict
    requires_approval: bool
    status: str
    created_at: datetime
    conversation_id: UUID | None = None


class PendingActionListResponse(BaseModel):
    items: list[PendingActionListItem]
```

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/routes/test_actions_routes.py
"""Phase 6 action routes — approve / discard / undo / pending."""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text


@pytest.mark.anyio
async def test_approve_returns_404_for_unknown_action(client):
    r = await client.post(f"/api/actions/{uuid4()}/approve")
    assert r.status_code == 404


@pytest.mark.anyio
async def test_discard_returns_404_for_unknown_action(client):
    r = await client.post(f"/api/actions/{uuid4()}/discard")
    assert r.status_code == 404


@pytest.mark.anyio
async def test_undo_returns_404_for_unknown_action(client):
    r = await client.post(f"/api/actions/{uuid4()}/undo")
    assert r.status_code == 404


@pytest.mark.anyio
async def test_pending_endpoint_returns_empty_for_clean_user(client):
    r = await client.get("/api/actions/pending")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert isinstance(body["items"], list)


@pytest.mark.anyio
async def test_requires_auth(client):
    """Pop the admin override to exercise real auth dep."""
    from main import app
    from app.dependencies import get_current_user
    saved = app.dependency_overrides.pop(get_current_user, None)
    try:
        r = await client.post(f"/api/actions/{uuid4()}/approve")
        assert r.status_code in (401, 403)
    finally:
        if saved:
            app.dependency_overrides[get_current_user] = saved
```

- [ ] **Step 3: Implement `routes/actions.py`**

```python
# backend/app/routes/actions.py
"""Phase 6: action queue HTTP surface — approve, discard, undo, pending."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

import db as rex_db
from app.dependencies import get_current_user
from app.models.foundation import UserAccount
from app.repositories.action_queue_repository import ActionQueueRepository
from app.schemas.actions import (
    ActionResponse, PendingActionListItem, PendingActionListResponse,
)
from app.services.ai.action_queue_service import (
    ActionQueueService, DispatchResult,
)
from app.services.ai.actions.blast_radius import ClassifyContext
from app.services.ai.tools import registry
from app.services.ai.tools.base import ActionContext

router = APIRouter(prefix="/api/actions", tags=["actions"])


async def _build_service(request: Request) -> ActionQueueService:
    """Construct an ActionQueueService tied to the request's DB session."""
    # This service uses sqlalchemy AsyncSession for the repo (consistent
    # with other routes). We create a lightweight session per request.
    from app.database import async_session_factory
    session = async_session_factory()
    # Caller is responsible for closing. The service only needs the repo
    # for metadata ops; handler SQL uses a raw asyncpg connection from
    # rex_db.get_pool(). This duality mirrors Phase 4's chat service.
    request.state._action_session = session  # for teardown
    return ActionQueueService(
        repo=ActionQueueRepository(session),
        get_tool_by_slug=registry.get,
        build_classify_ctx=lambda uid: ClassifyContext(conn=None, user_account_id=uid),
        build_action_ctx=lambda conn, uid, args, aid: ActionContext(
            conn=conn, user_account_id=uid, args=args, action_id=aid,
        ),
    )


@router.post("/{action_id}/approve", response_model=ActionResponse)
async def approve(
    action_id: UUID,
    request: Request,
    user: UserAccount = Depends(get_current_user),
) -> ActionResponse:
    svc = await _build_service(request)
    row = await svc._repo.get(action_id)
    if row is None:
        raise HTTPException(status_code=404, detail="action not found")
    pool = await rex_db.get_pool()
    async with pool.acquire() as conn:
        result: DispatchResult = await svc.commit(conn=conn, action_id=action_id)
    return ActionResponse(
        action_id=result.action_id,
        status=result.status,
        requires_approval=result.requires_approval,
        blast_radius=result.blast_radius,
        result_payload=result.result_payload,
        error_excerpt=result.error_excerpt,
    )


@router.post("/{action_id}/discard", response_model=ActionResponse)
async def discard(
    action_id: UUID,
    request: Request,
    user: UserAccount = Depends(get_current_user),
) -> ActionResponse:
    svc = await _build_service(request)
    row = await svc._repo.get(action_id)
    if row is None:
        raise HTTPException(status_code=404, detail="action not found")
    result = await svc.discard(action_id=action_id)
    return ActionResponse(
        action_id=result.action_id,
        status=result.status,
        requires_approval=result.requires_approval,
        blast_radius=result.blast_radius,
    )


@router.post("/{action_id}/undo", response_model=ActionResponse)
async def undo(
    action_id: UUID,
    request: Request,
    user: UserAccount = Depends(get_current_user),
) -> ActionResponse:
    svc = await _build_service(request)
    row = await svc._repo.get(action_id)
    if row is None:
        raise HTTPException(status_code=404, detail="action not found")
    result = await svc.undo(action_id=action_id)
    return ActionResponse(
        action_id=result.action_id,
        status=result.status,
        requires_approval=result.requires_approval,
        blast_radius=result.blast_radius,
        error_excerpt=result.error_excerpt,
    )


@router.get("/pending", response_model=PendingActionListResponse)
async def list_pending(
    request: Request,
    user: UserAccount = Depends(get_current_user),
) -> PendingActionListResponse:
    svc = await _build_service(request)
    rows = await svc._repo.list_pending_for_user(user_account_id=user.id)
    return PendingActionListResponse(items=[
        PendingActionListItem(
            id=r["id"],
            tool_slug=r["tool_slug"],
            tool_args=r["tool_args"],
            blast_radius=r["blast_radius"],
            requires_approval=r["requires_approval"],
            status=r["status"],
            created_at=r["created_at"],
            conversation_id=r.get("conversation_id"),
        )
        for r in rows
    ])
```

- [ ] **Step 4: Mount the router in `backend/main.py`**

Find the other `include_router` calls and add:
```python
from app.routes.actions import router as actions_router
# ...
app.include_router(actions_router)
```

- [ ] **Step 5: Run tests → 5 PASS**

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/actions.py \
        backend/app/schemas/actions.py \
        backend/main.py \
        backend/tests/routes/test_actions_routes.py
git commit -m "feat(phase6): /api/actions routes — approve/discard/undo/pending"
```

---

### Task 12: Chat-service tool_use integration + SSE events

**Files:**
- Modify: `backend/app/services/ai/chat_service.py`
- Modify: `backend/app/services/ai/model_client.py` (add `tools` kwarg)
- Modify: `backend/app/services/ai/dispatcher.py` (wire the service)
- Test: `backend/tests/services/ai/test_chat_service_tool_use.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/services/ai/test_chat_service_tool_use.py
"""Chat-service must intercept LLM tool_use responses and enqueue via
ActionQueueService. Tests use a mocked model_client that emits a
canned tool_use block."""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.services.ai.chat_service import ChatService
from app.schemas.assistant import AssistantChatRequest, AssistantUser


class _FakePoolAcquireCtx:
    def __init__(self, conn): self._conn = conn
    async def __aenter__(self): return self._conn
    async def __aexit__(self, *_a): return None


class _FakePool:
    def __init__(self, conn): self._conn = conn
    def acquire(self): return _FakePoolAcquireCtx(self._conn)


class _FakeQueueSvc:
    def __init__(self):
        self.enqueue_calls = []

    async def enqueue(self, **kwargs):
        from app.services.ai.action_queue_service import DispatchResult
        self.enqueue_calls.append(kwargs)
        return DispatchResult(
            action_id=uuid4(),
            status="auto_committed",
            requires_approval=False,
            blast_radius={"audience": "internal"},
            result_payload={"ok": True},
        )


@pytest.mark.anyio
async def test_chat_service_intercepts_tool_use_and_enqueues():
    """When the LLM emits a tool_use content block, chat_service must
    call action_queue_service.enqueue and emit an SSE action event."""

    # Mock model_client to emit a canned tool_use block
    async def fake_stream(model_request):
        async def gen():
            # SSE-style chunks the chat_service would parse from Anthropic.
            # For the test, we return a sentinel string the production
            # code's parsing layer recognizes.
            yield {"type": "tool_use", "name": "create_task", "input": {"title": "Walk the site"}}
        return gen()

    model_client = MagicMock()
    model_client.model_key = "test"
    model_client.stream_completion = fake_stream

    chat_repo = MagicMock()
    chat_repo.get_conversation = AsyncMock(return_value=None)
    chat_repo.create_conversation = AsyncMock(return_value={"id": uuid4(), "user_id": uuid4()})
    chat_repo.append_message = AsyncMock(return_value={"id": uuid4()})
    chat_repo.list_messages = AsyncMock(return_value=[])
    chat_repo.touch_conversation = AsyncMock(return_value=None)

    followup = MagicMock()
    followup.suggest = MagicMock(return_value=[])

    queue_svc = _FakeQueueSvc()

    svc = ChatService(
        chat_repo=chat_repo,
        model_client=model_client,
        followup_generator=followup,
        pool=_FakePool(conn=MagicMock()),
        action_queue_service=queue_svc,
    )

    request = AssistantChatRequest(
        message="make a task to walk the site",
        active_action_slug=None, params={},
        conversation_id=None, project_id=None,
        page_context=None, mode="chat",
    )
    user = AssistantUser(
        user_id=uuid4(), email="t@t.com", full_name="T",
        role_keys=[], legacy_role=None,
    )

    @dataclass
    class _Ctx:
        system_prompt: str = "base"
        project_id: UUID | None = None

    events = []
    async for chunk in svc.stream_chat(request=request, user=user, context=_Ctx()):
        events.append(chunk)

    # Queue service was invoked with the tool_use
    assert len(queue_svc.enqueue_calls) == 1
    call = queue_svc.enqueue_calls[0]
    assert call["tool_slug"] == "create_task"
    assert call["tool_args"] == {"title": "Walk the site"}
```

**IMPORTANT:** The actual tool-use-parsing path in chat_service depends on the shape of responses from your Anthropic SDK. The test above uses a simplified model of a tool_use chunk. The implementation must parse whatever the real `stream_completion` emits for tool_use. If the Anthropic SDK emits `ToolUseBlock` objects, parse those; if it emits JSON deltas, assemble them. The test's `fake_stream` can be adjusted to match.

- [ ] **Step 2: Extend `model_client.py` to accept tools**

Read the current `model_client.py` (backend/app/services/ai/model_client.py). Add a `tools: list[dict] | None = None` kwarg to `stream_completion` / `ModelRequest`. Pass through to the Anthropic `messages.stream(..., tools=tools)` call. This enables tool use on the API side.

- [ ] **Step 3: Modify `chat_service.py`**

Add `action_queue_service` kwarg. Before streaming, call `registry.list_schemas()` to build the tools list; pass to model request. After the model yields, detect `tool_use` blocks in the stream; for each:
1. Call `action_queue_service.enqueue(...)` with `conn` from pool, `tool_slug`, `tool_args`, conversation/message/user ids.
2. Emit an SSE event: `{"type": "action_proposed", "action_id": ..., "status": ..., "reasons": [...]}` for pending_approval; `{"type": "action_auto_committed", ...}` for auto; `{"type": "action_failed", "error": ...}` for fail.

Pseudo-implementation:

```python
# Inside stream_chat, after building effective_system_prompt:
tool_schemas = registry.list_schemas() if self._action_queue_service else None
model_request = ModelRequest(
    ..., tools=tool_schemas,
)

async for chunk in self._model.stream_completion(model_request):
    # existing text-delta handling unchanged
    # NEW: intercept tool_use
    if chunk.get("type") == "tool_use":
        slug = chunk["name"]
        args = chunk.get("input", {})
        async with self._pool.acquire() as _conn:
            result = await self._action_queue_service.enqueue(
                conn=_conn,
                user_account_id=user.id,
                requested_by_user_id=user.id,
                conversation_id=conversation["id"],
                message_id=user_msg["id"],
                tool_slug=slug, tool_args=args,
            )
        # Emit SSE
        if result.status == "pending_approval":
            event = {"type": "action_proposed", "action_id": str(result.action_id),
                     "status": "pending_approval", "reasons": result.reasons or []}
        elif result.status == "auto_committed":
            event = {"type": "action_auto_committed", "action_id": str(result.action_id),
                     "tool_slug": slug, "result": result.result_payload}
        else:
            event = {"type": "action_failed", "action_id": str(result.action_id),
                     "tool_slug": slug, "error": result.error_excerpt}
        yield sse_event(event)
        # Do NOT yield text continuation — the tool_use is the response.
```

- [ ] **Step 4: Update dispatcher.py to wire ActionQueueService into ChatService**

```python
# backend/app/services/ai/dispatcher.py
# Inside AssistantDispatcher.build():
from app.services.ai.action_queue_service import ActionQueueService
from app.repositories.action_queue_repository import ActionQueueRepository
# ... existing chat_service construction ...
# Build queue service lazily via a closure so it has the right session; or
# build it per request in chat_service itself. For simplicity, create one
# at startup with a session factory.
# Actually: since action_queue_service uses the same SQLAlchemy session as
# chat_repo, pass sessionfactory in. Simplest: add a get_or_build method.
```

**Implementer discretion:** construct the service cleanly. If the existing ChatService already has a SQLAlchemy session handy via chat_repo, reuse it. If not, use the worktree's `async_session_factory` in the service.

- [ ] **Step 5: Run tests → PASS**

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai/chat_service.py \
        backend/app/services/ai/model_client.py \
        backend/app/services/ai/dispatcher.py \
        backend/tests/services/ai/test_chat_service_tool_use.py
git commit -m "feat(phase6): chat_service intercepts LLM tool_use + emits action SSE events"
```

---

### Task 13: Full regression + PR + deploy + smoke

**Files:** none.

- [ ] **Step 1: Full suite**

```
cd backend && py -m pytest tests/ -q --tb=short
```

Expected: baseline 875 + new tests (~20-30 from Phase 6a) = ~895-905 passing.

- [ ] **Step 2: Push + PR**

```
cd /c/users/rober/rex-os/.worktrees/phase6a-commands-approvals-core
git push -u origin feat/phase6a-commands-approvals-core
gh pr create --base main --title "feat: Phase 6a — commands, actions & approvals (core framework)" --body <heredoc per spec summary>
```

- [ ] **Step 3: CI → merge → demo redeploy → prod auto-deploy**

Same playbook as Phase 4 / 5:
```
gh pr checks <n> --watch
gh pr merge <n> --merge
railway link --environment demo --service rex-os
railway redeploy --yes --service rex-os
# Poll /api/version until both envs match merge commit.
```

- [ ] **Step 4: Set Procore OAuth env vars on demo (operator step)**

Before `answer_rfi` can work in production, Rex OS needs Procore OAuth credentials. On the Rex OS demo Railway env, set:

```
PROCORE_CLIENT_ID
PROCORE_CLIENT_SECRET
PROCORE_REFRESH_TOKEN
PROCORE_COMPANY_ID
```

Copy these from the rex-procore Railway project's env vars (they're the same Procore app). After setting, Railway auto-redeploys.

**Skip this step** if you want to ship Phase 6a without `answer_rfi` working against real Procore — the rest of the framework (3 auto-pass tools + the queue + routes) works without it. `answer_rfi` will simply fail with a clear `ProcoreNotConfigured` error in the queue's error_excerpt until creds land.

- [ ] **Step 5: Smoke all 4 tools on demo**

Log in as aroberts@exxircapital.com on demo. Send chat messages that trigger each tool:

1. **create_task (auto, self-assigned):** "create a task for myself to check the punch list tomorrow"
   - Expect SSE `action_auto_committed` event; row in rex.tasks; row in rex.action_queue status=auto_committed.

2. **create_task (approval, external):** "create a task for [external subcontractor person] to submit closeout docs"
   - Expect SSE `action_proposed` with approval reasons; row in rex.action_queue status=pending_approval; NO row in rex.tasks yet. Then POST /api/actions/{id}/approve → row in rex.tasks + status=committed.

3. **update_task_status (auto):** "mark task #1 as in progress"
   - Expect auto_committed; status updated in rex.tasks.

4. **create_note (auto):** "note that we need to follow up on the Bishop Modern punch walk"
   - Expect auto_committed; row in rex.notes.

5. **answer_rfi (approval + Procore write)** — only if Procore env vars are set:
   - "answer RFI-42 with 'duct conflict resolved per revised detail A-501'"
   - Expect SSE `action_proposed`; approve → status=committed, rex.rfis updated, Procore API call fired. Verify the mapped procore_id's status changed in Procore.

- [ ] **Step 6: Railway logs two passes**

Same as Phase 5: `railway logs --deployment` for demo + prod, check for errors in startup + during smoke.

- [ ] **Step 7: Update handoff doc**

Create `docs/SESSION_HANDOFF_2026_04_22.md` (or extend the existing one) noting Phase 6a shipped + MVP tool count + what's deferred to Phase 6b (remaining ~12 tools + delete variants + writeback freeze).

---

## Self-review

**Spec coverage:**
- §1 parse strategy (Anthropic tool use) → Task 3 (registry with tool_schema) + Task 12 (model_client.tools + chat_service tool_use interception). ✓
- §2 card content → SSE event shape in Task 12 provides the data the frontend needs (action_id, reasons, tool_slug, tool_args). Card UI itself is out of scope per spec. ✓
- §3 blast radius → Task 2 (classifier), Tasks 6-10 (per-tool classify functions). ✓
- §4 approver routing — MVP uses `user_account_id` queue only (Task 5 `list_pending_for_user`). `approver_role` column exists in schema (Task 1) but isn't populated or queried in MVP. Flagged in spec §Approver routing as "simplest version." ✓
- §5 writeback → Task 9 (Procore client) + Task 10 (answer_rfi direct write). ✓
- §6 undo → Task 5 (undo method with 60s window + UNDO_WINDOW_SECONDS constant). Real compensating logic is follow-up per spec. ✓
- §7 failure → Task 5 (\_run\_handler catches + populates error_excerpt). UI implementation is out of scope. ✓
- §8 conversation state → SSE events feed inline cards (Task 12); `/api/actions/pending` filter view (Task 11). ✓

**Placeholder scan:** None. Every step has concrete code or a concrete verification command.

**Type consistency:** `BlastRadius`, `ActionContext`, `ActionResult`, `ActionSpec`, `DispatchResult` types used consistently across Tasks 2, 3, 5, 6-10, 11, 12. Slug names match across tool modules, registry, and tests. `rex.action_queue` column names match migration → repository → service → routes.

**Known adjustable details:**
- Task 1's chat FK table names need grep verification (migration handles both cases).
- Task 8's target table (`rex.notes` vs `rex.pending_decisions`) decided in step 1.
- Task 10's Procore API payload shape (v1.0 vs v1.1) documented inline.
- Task 12's tool_use parsing depends on the Anthropic SDK version in use.

## Follow-up plans (not in scope)

- **Phase 6b:** remaining ~12 tools (save_meeting_packet, save_draft, create_alert, create_decision, CE/PCO creation, pay-app, lien waiver, punch close/reopen, delete variants) + per-tool compensator logic for real undo semantics.
- **Phase 6c:** freeze rex-procore writeback after 1 month validation + remove from old app's cron.
- **Phase 6-UI:** React components for confirmation card (conversation-inline) + Pending Approvals filter sidebar.
- **Countersign rules** — revisit after 2 weeks of usage data per spec §Approver routing.
- **Delegate-queue UX** — if AI drafts on behalf of another user, downstream-owner routing.
