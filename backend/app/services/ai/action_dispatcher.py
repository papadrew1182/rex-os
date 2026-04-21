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
