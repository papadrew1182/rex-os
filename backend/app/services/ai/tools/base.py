# backend/app/services/ai/tools/base.py
"""Phase 6 tool definitions.

ActionSpec is the source of truth for one LLM-invokable action:
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
    conn: live asyncpg connection; dispatcher owns lifecycle.
    user_account_id: who the action runs AS.
    args: tool_args passed by the LLM, validated against tool_schema.
    action_id: the rex.action_queue row id.
    original_result: result from handler, available to compensators.
    """
    conn: asyncpg.Connection
    user_account_id: UUID
    args: dict[str, Any]
    action_id: UUID
    original_result: dict[str, Any] | None = None


@dataclass
class ActionResult:
    """What a handler returns on success. result_payload: JSONB-serializable
    dict persisted to rex.action_queue.result_payload."""
    result_payload: dict[str, Any]


class ClassifyFn(Protocol):
    async def __call__(
        self, args: dict[str, Any], ctx: ClassifyContext
    ) -> BlastRadius: ...


class HandlerFn(Protocol):
    async def __call__(self, ctx: ActionContext) -> ActionResult: ...


class CompensatorFn(Protocol):
    async def __call__(
        self, original_result: dict[str, Any], ctx: "ActionContext"
    ) -> ActionResult: ...


@dataclass
class ActionSpec:
    slug: str
    tool_schema: dict[str, Any]
    classify: ClassifyFn
    handler: HandlerFn
    fires_external_effect: bool = False
    compensator: CompensatorFn | None = None


__all__ = [
    "ActionContext",
    "ActionResult",
    "ActionSpec",
    "ClassifyFn",
    "CompensatorFn",
    "HandlerFn",
]
