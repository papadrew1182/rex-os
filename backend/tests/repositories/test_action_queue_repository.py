"""Live-DB tests for ActionQueueRepository Phase 6b additions.

Phase 6b Wave 1 Task 2 adds two capabilities to the repo:

  1. ``insert(..., correction_of_id=..., committed_at_now=True)`` so the
     synthetic ``<slug>__undo`` correction rows Task 3 will create can
     record a FK back to the original action and set ``committed_at``
     atomically with the insert.
  2. ``list_pending_for_user`` / ``list_pending_by_role`` exclude any
     ``<slug>__undo`` rows. Those synthetic rows are auto-committed
     compensators and must never appear as user-facing pending approvals.

These tests talk to the live dev Postgres (same pattern as
``tests/services/connectors/procore/test_staging.py``) and clean up
their own rows on teardown.
"""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.database import async_session_factory
from app.repositories.action_queue_repository import ActionQueueRepository


# Seeded admin user from foundation_bootstrap.sql — safe to reuse as the
# action owner since we delete only the rows we insert during teardown.
_SEED_USER_ID = uuid.UUID("20000000-0000-4000-a000-000000000001")


def _require_live_db():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")


@asynccontextmanager
async def _session():
    async with async_session_factory() as s:
        yield s


@pytest_asyncio.fixture
async def inserted_ids():
    """Tracks action_queue ids inserted during a test for teardown."""
    _require_live_db()
    ids: list[uuid.UUID] = []
    yield ids
    # Teardown: delete every row we created. Delete in reverse insertion
    # order so correction rows (FK -> original) go before their targets.
    if not ids:
        return
    async with async_session_factory() as s:
        # Two-pass: clear correction_of_id first, then delete. Simpler to
        # just delete in reverse order since correction rows are inserted
        # after their referents.
        for aid in reversed(ids):
            await s.execute(
                text("DELETE FROM rex.action_queue WHERE id = :id"),
                {"id": aid},
            )
        await s.commit()


async def test_insert_accepts_correction_of_id_and_committed_at(inserted_ids):
    """insert(correction_of_id=X, committed_at_now=True) writes both fields."""
    original_id = uuid.uuid4()
    correction_id = uuid.uuid4()
    inserted_ids.extend([original_id, correction_id])

    async with _session() as s:
        repo = ActionQueueRepository(s)

        await repo.insert(
            id=original_id,
            user_account_id=_SEED_USER_ID,
            requested_by_user_id=_SEED_USER_ID,
            conversation_id=None,
            message_id=None,
            tool_slug="create_task",
            tool_args={"title": "original"},
            blast_radius={"audience": "internal"},
            requires_approval=False,
            status="auto_committed",
            approver_role=None,
        )

        await repo.insert(
            id=correction_id,
            user_account_id=_SEED_USER_ID,
            requested_by_user_id=_SEED_USER_ID,
            conversation_id=None,
            message_id=None,
            tool_slug="create_task__undo",
            tool_args={"target_action_id": str(original_id)},
            blast_radius={"audience": "internal"},
            requires_approval=False,
            status="auto_committed",
            approver_role=None,
            correction_of_id=original_id,
            committed_at_now=True,
        )

    async with _session() as s:
        row = (
            await s.execute(
                text(
                    "SELECT correction_of_id, committed_at "
                    "FROM rex.action_queue WHERE id = :id"
                ),
                {"id": correction_id},
            )
        ).mappings().first()

    assert row is not None
    assert row["correction_of_id"] == original_id
    assert row["committed_at"] is not None


async def test_list_pending_excludes_undo_rows(inserted_ids):
    """__undo rows must not surface in list_pending_for_user."""
    real_id = uuid.uuid4()
    undo_id = uuid.uuid4()
    inserted_ids.extend([real_id, undo_id])

    async with _session() as s:
        repo = ActionQueueRepository(s)

        await repo.insert(
            id=real_id,
            user_account_id=_SEED_USER_ID,
            requested_by_user_id=_SEED_USER_ID,
            conversation_id=None,
            message_id=None,
            tool_slug="answer_rfi",
            tool_args={"rfi_id": "abc"},
            blast_radius={"audience": "external"},
            requires_approval=True,
            status="pending_approval",
            approver_role="pm",
        )
        await repo.insert(
            id=undo_id,
            user_account_id=_SEED_USER_ID,
            requested_by_user_id=_SEED_USER_ID,
            conversation_id=None,
            message_id=None,
            tool_slug="create_task__undo",
            tool_args={},
            blast_radius={"audience": "internal"},
            requires_approval=True,
            status="pending_approval",
            approver_role="pm",
        )

    async with _session() as s:
        repo = ActionQueueRepository(s)
        user_rows = await repo.list_pending_for_user(_SEED_USER_ID, limit=100)
        role_rows = await repo.list_pending_by_role("pm", limit=100)

    user_ids = {r["id"] for r in user_rows}
    role_ids = {r["id"] for r in role_rows}

    assert real_id in user_ids
    assert undo_id not in user_ids
    assert real_id in role_ids
    assert undo_id not in role_ids
