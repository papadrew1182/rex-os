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
            # Cast $N through text first so asyncpg treats the parameter as
            # text regardless of what Postgres infers from the comparison.
            # The column type could be timestamptz, timestamp, date, etc.
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
