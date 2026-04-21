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

from app.services.ai.action_dispatcher import ActionDispatcher
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
    from app.services.ai.action_dispatcher import _default_dispatcher
    got = set(_default_dispatcher.slugs())
    assert expected <= got, f"missing slugs: {expected - got}"
