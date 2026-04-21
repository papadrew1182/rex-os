"""Phase 6 action routes - approve / discard / undo / pending.

EVENT-LOOP NOTE: These tests intentionally do NOT carry ``@pytest.mark.anyio``.
The session-scoped ``client`` fixture (see tests/conftest.py) and the shared
SQLAlchemy engine pool are bound to pytest-asyncio's session loop. Adding
``@pytest.mark.anyio`` would route these through pytest-anyio's per-test
loop instead, which on Linux CI (Python 3.14 + asyncpg) triggers
"Future attached to a different loop" / "got result for unknown protocol
state 3" the moment ``Depends(get_db)`` checks out a pooled connection.
On Windows the race is slow enough to mask the bug locally.

The module's ``auto`` mode (see backend/pytest.ini) collects plain
``async def test_*`` functions directly under pytest-asyncio with the
session-scoped loop, matching every other route test in this suite.
"""
from __future__ import annotations

import json
import uuid
from datetime import date
from uuid import uuid4


# Seeded admin user from foundation_bootstrap.sql — same UUID the
# conftest `_stub_admin_user` override uses for `get_current_user`.
_SEED_ADMIN_USER_ID = uuid.UUID("20000000-0000-4000-a000-000000000001")


async def test_approve_returns_404_for_unknown_action(client):
    r = await client.post(f"/api/actions/{uuid4()}/approve")
    assert r.status_code == 404


async def test_discard_returns_404_for_unknown_action(client):
    r = await client.post(f"/api/actions/{uuid4()}/discard")
    assert r.status_code == 404


async def test_undo_returns_404_for_unknown_action(client):
    r = await client.post(f"/api/actions/{uuid4()}/undo")
    assert r.status_code == 404


async def test_pending_endpoint_returns_empty_for_clean_user(client):
    r = await client.get("/api/actions/pending")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert isinstance(body["items"], list)


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


async def test_undo_route_actually_reverses_create_task(client):
    """End-to-end: seed a committed create_task action + the task it
    produced, then POST /api/actions/{id}/undo and verify:

      - HTTP 200
      - rex.tasks row deleted (compensator DELETE ran)
      - correction ``create_task__undo`` row exists with status='committed'
        and correction_of_id pointing at the original
      - original action flipped to status='undone' with undone_at set
    """
    import db as rex_db

    admin_user_id = _SEED_ADMIN_USER_ID
    proj_id = uuid4()
    task_id = uuid4()
    action_id = uuid4()
    proj_number = f"E2E-{uuid4().hex[:8]}"

    pool = await rex_db.get_pool()
    async with pool.acquire() as conn:
        # Seed isolated project + task. Task FK -> project is NOT NULL.
        await conn.execute(
            "INSERT INTO rex.projects (id, name, status, project_number) "
            "VALUES ($1::uuid, 'E2E Undo Test', 'active', $2)",
            proj_id, proj_number,
        )
        await conn.execute(
            """
            INSERT INTO rex.tasks (id, project_id, task_number, title, status,
                                   priority, due_date)
            VALUES ($1::uuid, $2::uuid, 1, 'End-to-end target', 'open',
                    'medium', $3::date)
            """,
            task_id, proj_id, date(2026, 5, 1),
        )
        # Seed the action_queue row that "created" this task.
        await conn.execute(
            """
            INSERT INTO rex.action_queue (
                id, user_account_id, tool_slug, tool_args, blast_radius,
                requires_approval, status, committed_at, result_payload,
                created_at, updated_at
            ) VALUES (
                $1::uuid, $2::uuid, 'create_task',
                '{}'::jsonb,
                '{"audience":"internal","fires_external_effect":false,"financial_dollar_amount":null,"scope_size":1}'::jsonb,
                false, 'auto_committed', now(),
                $3::jsonb,
                now(), now()
            )
            """,
            action_id, admin_user_id,
            json.dumps({
                "task_id": str(task_id),
                "task_number": 1,
                "title": "End-to-end target",
                "project_id": str(proj_id),
                "assignee_person_id": None,
            }),
        )

    try:
        r = await client.post(f"/api/actions/{action_id}/undo")
        assert r.status_code == 200, (
            f"expected 200, got {r.status_code}: {r.text}"
        )
        body = r.json()
        assert body.get("status") == "undone", body

        async with pool.acquire() as conn:
            # Task should be gone (compensator DELETE ran).
            gone = await conn.fetchrow(
                "SELECT id FROM rex.tasks WHERE id = $1::uuid", task_id,
            )
            assert gone is None, "compensator should have deleted the task"

            # Original action should be 'undone' with undone_at set.
            orig = await conn.fetchrow(
                "SELECT status, undone_at FROM rex.action_queue "
                "WHERE id = $1::uuid",
                action_id,
            )
            assert orig is not None
            assert orig["status"] == "undone"
            assert orig["undone_at"] is not None

            # Correction row should exist with committed status + FK.
            corr = await conn.fetchrow(
                """
                SELECT tool_slug, status, correction_of_id
                FROM rex.action_queue
                WHERE correction_of_id = $1::uuid
                """,
                action_id,
            )
            assert corr is not None, "correction row not inserted"
            assert corr["tool_slug"] == "create_task__undo"
            assert corr["status"] == "committed"
    finally:
        # Cleanup — always runs. Correction row FK references original, so
        # delete it first. Task may or may not already be gone depending
        # on where the test failed.
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM rex.action_queue WHERE correction_of_id = $1::uuid",
                action_id,
            )
            await conn.execute(
                "DELETE FROM rex.action_queue WHERE id = $1::uuid",
                action_id,
            )
            await conn.execute(
                "DELETE FROM rex.tasks WHERE id = $1::uuid", task_id,
            )
            await conn.execute(
                "DELETE FROM rex.projects WHERE id = $1::uuid", proj_id,
            )
