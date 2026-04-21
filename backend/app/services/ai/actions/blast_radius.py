"""Phase 6 blast-radius classifier.

Every tool returns a BlastRadius from its `classify(args, ctx)` function.
The dispatcher checks `requires_approval()` to route the action to either
auto-commit (with 60s undo) or approval queue.

Rubric:
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
            or (self.financial_dollar_amount is not None and self.financial_dollar_amount > 0)
            or self.scope_size >= 5
        )

    def reasons(self) -> list[str]:
        r: list[str] = []
        if self.audience == 'external':
            r.append("will notify someone outside Rex Construction")
        if self.fires_external_effect:
            r.append("writes to an external system (Procore)")
        if self.financial_dollar_amount is not None and self.financial_dollar_amount > 0:
            r.append(f"financial impact: ${self.financial_dollar_amount:,.2f}")
        if self.scope_size >= 5:
            r.append(f"batch of {self.scope_size} changes")
        return r

    def to_jsonb(self) -> dict:
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
    """State classify() may need — injected at tool_use interception time.
    Pure helpers only; no handler SQL on the context."""
    conn: asyncpg.Connection
    user_account_id: UUID

    async def is_internal_person(self, person_id: UUID | None) -> bool:
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
