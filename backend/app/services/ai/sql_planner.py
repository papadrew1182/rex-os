"""Safe free-form SQL orchestration against curated rex.v_* views."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import asyncpg

from services.ai.sql_guard import (
    BlockedQueryError,
    DEFAULT_ALLOWED_VIEWS,
    GuardResult,
    SqlGuard,
)


@dataclass
class PlannedQueryResult:
    rows: list[dict[str, Any]]
    row_count: int
    referenced_views: list[str]


class SqlPlanner:
    def __init__(
        self,
        pool: asyncpg.Pool,
        *,
        guard: SqlGuard | None = None,
        max_rows: int = 500,
    ) -> None:
        self._pool = pool
        self._guard = guard or SqlGuard()
        self._max_rows = max_rows

    @property
    def allowed_views(self) -> frozenset[str]:
        return self._guard.allowed_views

    def validate(self, sql: str) -> GuardResult:
        return self._guard.check(sql)

    async def plan_and_run(self, sql: str) -> PlannedQueryResult:
        result = self._guard.check(sql)
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("SET LOCAL default_transaction_read_only = on")
                rows = await conn.fetch(f"{result.sql} LIMIT {self._max_rows}")
        return PlannedQueryResult(
            rows=[dict(r) for r in rows],
            row_count=len(rows),
            referenced_views=result.referenced_views,
        )


__all__ = [
    "BlockedQueryError",
    "DEFAULT_ALLOWED_VIEWS",
    "PlannedQueryResult",
    "SqlPlanner",
]
