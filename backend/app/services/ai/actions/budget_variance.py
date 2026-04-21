"""budget_variance quick action handler.

STUB — real implementation lands in the task that owns this slug.
Returns an empty ActionResult so the dispatcher can register it and
other tests are unblocked. See plan Task 6 for the real SQL.
"""
from __future__ import annotations

from app.services.ai.actions.base import ActionContext, ActionResult


class Handler:
    slug = "budget_variance"

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
