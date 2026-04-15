"""Session 1 live-Postgres merge gate.

Marked ``@pytest.mark.live_db``. This test applies Session 1's migrations
against a real Postgres and exercises every Session 1-owned surface end
to end. It is the deterministic, DB-backed equivalent of
``test_assistant_fresh_env_smoke.py`` (which runs against ``FakeDispatcher``).

**It is skipped automatically** when ``DATABASE_URL`` is unset or the
DB is unreachable, so the default test suite stays hermetic. When a
Postgres instance IS reachable it is the real merge gate: if this
passes, Session 1 is merge-ready.

Run it explicitly with::

    cd backend
    DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rex_os \\
        py -3 -m pytest tests/test_assistant_live_db_smoke.py -v -m live_db

What it proves against a real DB (not fakes):

* ``app/migrate.py`` registers 006/007/008 and applies them cleanly
* ``rex.chat_conversations`` / ``chat_messages`` / ``ai_prompt_registry``
  / ``ai_action_catalog`` exist with the expected shape
* CHECK constraints on risk_tier and readiness_state accept every
  seeded value
* 77 canonical slugs and 80 legacy aliases land via migration 008
* Required dedupes (C-8/C-28 -> submittal_sla, C-15/C-60 ->
  monthly_owner_report, C-5/C-29 -> rfi_aging) resolve in SQL
* ``ChatRepository`` create/get/list/archive/touch works over asyncpg
  with jsonb round-trip and the ``set_updated_at`` trigger
* ``PromptRepository.get_active('assistant.system.base')`` returns the
  seeded row
* ``CatalogRepository.get_by_slug`` and ``.resolve_alias`` work live
* ``GET /api/assistant/catalog`` returns 77 actions over the wire
* ``POST /api/assistant/chat`` streams SSE with the full frozen vocabulary
* ``GET /api/assistant/conversations`` + detail + ``DELETE`` round-trip

What it does NOT prove:

* Planner execution against ``rex.v_*`` views (owned by Session 2;
  they do not exist yet). This is NOT a Session 1 merge blocker
  unless ``SqlGuard`` / ``SqlPlanner`` break before the missing-view
  boundary, which the guard unit tests already verify.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.live_db


# ── DB availability probe ─────────────────────────────────────────────────
def _pg_is_reachable() -> bool:
    url = os.environ.get("DATABASE_URL")
    if not url:
        return False
    import asyncio
    try:
        async def _ping() -> bool:
            conn = await asyncpg.connect(url)
            try:
                await conn.fetchval("SELECT 1")
            finally:
                await conn.close()
            return True
        return asyncio.get_event_loop().run_until_complete(_ping())  # type: ignore[no-any-return]
    except Exception:
        try:
            async def _ping2() -> bool:
                conn = await asyncpg.connect(url)
                try:
                    await conn.fetchval("SELECT 1")
                finally:
                    await conn.close()
                return True
            return asyncio.new_event_loop().run_until_complete(_ping2())  # type: ignore[no-any-return]
        except Exception:
            return False


_LIVE_DB_REACHABLE = _pg_is_reachable()
_SKIP_REASON = (
    "Session 1 live-DB gate skipped: set DATABASE_URL to a reachable Postgres "
    "(e.g. postgresql://postgres:postgres@localhost:5432/rex_os) and run with "
    "`pytest -m live_db`."
)


# ── Fresh-state fixture ───────────────────────────────────────────────────
@pytest.fixture
async def live_pool():
    """Apply Session 1 migrations against the live DB and yield the pool.

    Relies on the ``app.migrate.apply_migrations`` path that Session 1
    registered 006/007/008 into — if that registration is missing this
    fixture fails loudly, which is exactly the defect we want to catch.
    """
    if not _LIVE_DB_REACHABLE:
        pytest.skip(_SKIP_REASON)

    import db as legacy_db
    from app.migrate import MIGRATION_ORDER, apply_migrations

    required = {
        "006_ai_chat_and_prompts.sql",
        "007_ai_action_catalog.sql",
        "008_ai_action_catalog_seed.sql",
    }
    assert required.issubset(set(MIGRATION_ORDER)), (
        f"AI spine migrations not registered in app/migrate.py MIGRATION_ORDER. "
        f"Missing: {sorted(required - set(MIGRATION_ORDER))}. "
        "This is the exact defect the Session 1 live-DB gate catches."
    )

    results = await apply_migrations()
    failures = [
        r for r in results
        if r.status == "error" and r.filename in required
    ]
    assert not failures, (
        "Session 1 migrations failed to apply: "
        + ", ".join(f"{r.filename}: {r.detail}" for r in failures)
    )

    pool = await legacy_db.get_pool()
    yield pool


# ── 1. Migrations apply cleanly through Session 1's range ────────────────
async def test_live_migration_order_includes_ai_spine(live_pool):
    from app.migrate import MIGRATION_ORDER
    for fname in (
        "006_ai_chat_and_prompts.sql",
        "007_ai_action_catalog.sql",
        "008_ai_action_catalog_seed.sql",
    ):
        assert fname in MIGRATION_ORDER, fname


async def test_live_ai_spine_tables_exist(live_pool):
    async with live_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'rex'
              AND table_name IN (
                'chat_conversations', 'chat_messages',
                'ai_prompt_registry', 'ai_action_catalog'
              )
            ORDER BY table_name
            """
        )
    names = [r[0] for r in rows]
    assert names == [
        "ai_action_catalog",
        "ai_prompt_registry",
        "chat_conversations",
        "chat_messages",
    ]


# ── 2. Catalog data lands correctly ───────────────────────────────────────
async def test_live_catalog_has_exactly_77_slugs(live_pool):
    async with live_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM rex.ai_action_catalog WHERE enabled = true"
        )
    assert count == 77


async def test_live_catalog_has_exactly_80_legacy_aliases(live_pool):
    async with live_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM (SELECT unnest(legacy_aliases) FROM rex.ai_action_catalog) t"
        )
    assert count == 80


async def test_live_no_slug_uses_C_star_as_primary_identity(live_pool):
    async with live_pool.acquire() as conn:
        bad = await conn.fetchval(
            "SELECT COUNT(*) FROM rex.ai_action_catalog "
            "WHERE slug LIKE 'C-%' OR slug LIKE 'c-%'"
        )
    assert bad == 0


@pytest.mark.parametrize("alias, expected", [
    ("C-8", "submittal_sla"),
    ("C-28", "submittal_sla"),
    ("C-15", "monthly_owner_report"),
    ("C-60", "monthly_owner_report"),
    ("C-5", "rfi_aging"),
    ("C-29", "rfi_aging"),
])
async def test_live_required_dedupes_resolve(live_pool, alias, expected):
    async with live_pool.acquire() as conn:
        slug = await conn.fetchval(
            "SELECT slug FROM rex.ai_action_catalog WHERE $1 = ANY(legacy_aliases)",
            alias,
        )
    assert slug == expected


# ── 3. Real repositories against Postgres ────────────────────────────────
async def test_live_catalog_repository_list_and_lookup(live_pool):
    from app.repositories.catalog_repository import CatalogRepository
    repo = CatalogRepository(live_pool)

    all_rows = await repo.list_actions()
    assert len(all_rows) == 77

    vp_rows = await repo.list_actions(role_keys=["VP"])
    assert len(vp_rows) == 77
    acct_rows = await repo.list_actions(role_keys=["ACCOUNTANT"])
    assert 0 < len(acct_rows) < 77

    direct = await repo.get_by_slug("submittal_sla")
    assert direct is not None
    assert set(direct["legacy_aliases"]) == {"C-8", "C-28"}

    resolved = await repo.resolve_alias("C-28")
    assert resolved is not None
    assert resolved["slug"] == "submittal_sla"

    resolved_canon = await repo.resolve_alias("budget_variance")
    assert resolved_canon is not None
    assert resolved_canon["slug"] == "budget_variance"

    assert await repo.resolve_alias("C-99999") is None


async def test_live_prompt_repository_active_lookup(live_pool):
    from app.repositories.prompt_repository import PromptRepository
    repo = PromptRepository(live_pool)
    row = await repo.get_active("assistant.system.base")
    assert row is not None
    assert row["is_active"] is True
    assert row["prompt_type"] == "system"
    assert "Rex" in row["content"]


async def test_live_chat_repository_full_round_trip(live_pool):
    from app.repositories.chat_repository import ChatRepository
    repo = ChatRepository(live_pool)

    user_id = uuid.UUID("20000000-0000-4000-a000-000000000001")

    conv = await repo.create_conversation(
        user_id=user_id,
        title="live gate round-trip",
        project_id=None,
        active_action_slug="budget_variance",
        page_context={"route": "/gate", "surface": "assistant_sidebar", "filters": {}},
        conversation_metadata={"origin": "live_db_gate"},
    )
    assert conv["page_context"]["route"] == "/gate"
    initial_last = conv["last_message_at"]

    user_msg = await repo.append_message(
        conversation_id=conv["id"],
        sender_type="user",
        content="Hello Rex",
        structured_payload={"params": {"PROJECT_ID": "abc"}},
    )
    assert user_msg["structured_payload"]["params"]["PROJECT_ID"] == "abc"

    asst_msg = await repo.append_message(
        conversation_id=conv["id"],
        sender_type="assistant",
        content="Hello back",
        structured_payload={"followups": ["a", "b"]},
        model_key="echo",
        prompt_key="assistant.system.base",
    )
    assert asst_msg["model_key"] == "echo"

    await repo.touch_conversation(conv["id"], title="updated title")
    refreshed = await repo.get_conversation(conv["id"], user_id=user_id)
    assert refreshed is not None
    assert refreshed["title"] == "updated title"
    assert refreshed["last_message_at"] >= initial_last

    msgs = await repo.list_messages(conv["id"])
    assert [m["sender_type"] for m in msgs] == ["user", "assistant"]

    items = await repo.list_conversations(user_id=user_id)
    own = [i for i in items if i["id"] == conv["id"]]
    assert len(own) == 1
    assert own[0]["last_message_preview"] == "Hello back"

    archived_ok = await repo.archive_conversation(conv["id"], user_id=user_id)
    assert archived_ok is True

    assert await repo.get_conversation(conv["id"], user_id=user_id) is None
    items_after = await repo.list_conversations(user_id=user_id)
    assert not [i for i in items_after if i["id"] == conv["id"]]

    # Re-archiving a missing conversation returns False.
    assert await repo.archive_conversation(conv["id"], user_id=user_id) is False


# ── 4-5. Real API + SSE round-trip ────────────────────────────────────────
async def test_live_api_and_sse_round_trip(live_pool):
    from app.dependencies import get_current_user
    from app.models.foundation import UserAccount
    from main import app

    def _stub_user() -> UserAccount:
        return UserAccount(
            id=uuid.UUID("20000000-0000-4000-a000-000000000001"),
            person_id=uuid.UUID("10000000-0000-4000-a000-000000000001"),
            email="live@gate",
            password_hash="(stub)",
            global_role="vp",
            is_admin=True,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    saved_override = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = _stub_user
    # Force the router to rebuild its dispatcher against the live pool.
    if hasattr(app.state, "assistant_dispatcher"):
        delattr(app.state, "assistant_dispatcher")

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://live-gate") as c:
            # GET /catalog
            r = await c.get("/api/assistant/catalog")
            assert r.status_code == 200
            body = r.json()
            assert len(body["actions"]) == 77
            submittal = next(a for a in body["actions"] if a["slug"] == "submittal_sla")
            assert set(submittal["legacy_aliases"]) == {"C-8", "C-28"}

            # POST /chat (SSE)
            r2 = await c.post(
                "/api/assistant/chat",
                json={
                    "message": "live gate smoke",
                    "active_action_slug": "budget_variance",
                    "page_context": {
                        "route": "/gate",
                        "surface": "assistant_sidebar",
                        "filters": {},
                    },
                },
            )
            assert r2.status_code == 200
            assert r2.headers["content-type"].startswith("text/event-stream")

            events = _parse_sse(r2.text)
            types = [e["type"] for e in events]
            for expected in (
                "conversation.created",
                "message.started",
                "message.delta",
                "followups.generated",
                "message.completed",
            ):
                assert expected in types, f"missing {expected}"
            assert types.index("conversation.created") < types.index("message.started")
            first_delta = types.index("message.delta")
            assert first_delta < types.index("followups.generated")
            assert first_delta < types.index("message.completed")

            conv_id = next(
                e for e in events if e["type"] == "conversation.created"
            )["conversation_id"]

            # GET /conversations
            r3 = await c.get("/api/assistant/conversations")
            assert r3.status_code == 200
            items = r3.json()["items"]
            assert any(i["id"] == conv_id for i in items)

            # GET /conversations/{id}
            r4 = await c.get(f"/api/assistant/conversations/{conv_id}")
            assert r4.status_code == 200
            detail = r4.json()
            assert detail["conversation"]["id"] == conv_id
            senders = [m["sender_type"] for m in detail["messages"]]
            assert senders == ["user", "assistant"]

            # DELETE /conversations/{id}
            r5 = await c.delete(f"/api/assistant/conversations/{conv_id}")
            assert r5.status_code == 204

            r6 = await c.get(f"/api/assistant/conversations/{conv_id}")
            assert r6.status_code == 404

            r7 = await c.delete(f"/api/assistant/conversations/{conv_id}")
            assert r7.status_code == 404
    finally:
        if saved_override is not None:
            app.dependency_overrides[get_current_user] = saved_override
        else:
            app.dependency_overrides.pop(get_current_user, None)


def _parse_sse(body: str) -> list[dict]:
    events: list[dict] = []
    for frame in body.split("\n\n"):
        frame = frame.strip()
        if not frame.startswith("data:"):
            continue
        payload = frame[len("data:"):].strip()
        if not payload:
            continue
        events.append(json.loads(payload))
    return events
