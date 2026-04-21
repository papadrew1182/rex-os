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
            "INSERT INTO rex.people (id, first_name, last_name, email, role_type) "
            "VALUES ($1::uuid, 'Test', 'Scope', $2, 'internal')",
            person_id, f"scope-{person_id}@test.invalid",
        )
        await conn.execute(
            "INSERT INTO rex.user_accounts "
            "(id, person_id, email, password_hash, is_active) "
            "VALUES ($1::uuid, $2::uuid, $3, 'x', true)",
            user_id, person_id, f"scope-{user_id}@test.invalid",
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
