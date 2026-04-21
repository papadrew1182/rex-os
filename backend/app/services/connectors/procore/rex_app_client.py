"""Read-only client for the Rex App (old rex-procore) Railway Postgres.

Wraps an asyncpg pool with a single generic row-fetch method. The
connector-specific logic (payload shape, ordering, filters) lives in the
adapter layer; this module only knows how to run a safe SELECT.
"""

from __future__ import annotations

import re
from typing import Any

import asyncpg

_IDENT_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def _assert_identifier(name: str, kind: str) -> None:
    """Defense-in-depth: reject anything that isn't a plain SQL identifier.

    Schema/table/column names are concatenated into the query string
    because asyncpg can't parameterize identifiers. All callers today
    pass static constants, but future callers could pass user input.
    Fail fast if it looks suspicious.
    """
    if not _IDENT_RE.match(name):
        raise ValueError(
            f"{kind} {name!r} is not a safe SQL identifier"
        )


class RexAppDbClient:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def fetch_rows(
        self,
        *,
        schema: str,
        table: str,
        cursor_col: str,
        cursor_value: str | None,
        limit: int,
        filters: list[tuple[str, str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        _assert_identifier(schema, "schema")
        _assert_identifier(table, "table")
        _assert_identifier(cursor_col, "cursor_col")

        params: list[Any] = []
        where_clauses: list[str] = []

        if cursor_value is not None:
            params.append(cursor_value)
            # IMPORTANT: the ::text::timestamptz double cast is intentional.
            # With $N::timestamptz alone, asyncpg's type inference demands a
            # Python datetime for the parameter; pinning $N to ::text first
            # forces asyncpg to send a string and lets Postgres do the cast.
            # Do NOT "simplify" to a single cast without also updating every
            # caller to pass datetime objects instead of ISO strings.
            # Assumes cursor_col is a timestamptz-typed column -- a bigint
            # column (e.g. procore_id) would fail the text->timestamptz cast
            # at runtime. All Phase 4 callers use timestamp cursors.
            where_clauses.append(f"{cursor_col} > ${len(params)}::text::timestamptz")

        for col, op, value in filters or []:
            _assert_identifier(col, "filter col")
            if op not in ("=", "!=", ">", "<", ">=", "<="):
                raise ValueError(f"filter op {op!r} not allowed")
            params.append(value)
            where_clauses.append(f"{col} {op} ${len(params)}")

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        params.append(limit)
        sql = (
            f"SELECT * FROM {schema}.{table} "
            f"{where_sql} "
            f"ORDER BY {cursor_col} ASC "
            f"LIMIT ${len(params)}"
        )
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
            return [dict(r) for r in rows]


__all__ = ["RexAppDbClient"]
