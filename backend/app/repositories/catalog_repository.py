"""Action catalog persistence against rex.ai_action_catalog.

Slug-first identity. Legacy ``C-*`` IDs are preserved in ``legacy_aliases``
only and must never be used as a primary key anywhere upstream. This
repository exposes three lookup paths:

    list_actions(role_keys=...)    — catalog projection for a role
    get_by_slug(slug)              — canonical identity lookup
    resolve_alias(identifier)      — resolve slug OR legacy alias to the
                                     canonical row (used by the dispatcher
                                     during the legacy-id transition window)
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg


_SELECT_COLUMNS = """
    slug, legacy_aliases, label, category, description,
    params_schema, risk_tier, readiness_state,
    required_connectors, role_visibility, handler_key,
    enabled, metadata, created_at, updated_at
"""


class CatalogRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_actions(
        self,
        *,
        role_keys: list[str] | None = None,
        only_enabled: bool = True,
    ) -> list[dict[str, Any]]:
        """Return all actions, optionally filtered by role_visibility overlap.

        Filtering is done in SQL so the repository never has to load the
        whole catalog into memory. Role filtering uses the
        ``role_visibility && ARRAY[...]`` overlap operator so actions with
        no role restriction (empty array) are always visible.
        """
        clauses: list[str] = []
        args: list[Any] = []

        if only_enabled:
            clauses.append("enabled = true")
        if role_keys is not None:
            args.append(role_keys)
            clauses.append(
                f"(role_visibility = '{{}}' OR role_visibility && ${len(args)})"
            )

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT {_SELECT_COLUMNS}
            FROM rex.ai_action_catalog
            {where}
            ORDER BY category, label
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
        return [_row_to_action(r) for r in rows]

    async def get_by_slug(self, slug: str) -> dict[str, Any] | None:
        """Canonical-identity lookup. Does NOT fall back to legacy aliases.

        Used by the dispatcher when the caller sends a slug they are
        confident is canonical. If the slug is unknown, returns ``None``.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_SELECT_COLUMNS} FROM rex.ai_action_catalog WHERE slug = $1",
                slug,
            )
        return _row_to_action(row) if row else None

    async def resolve_alias(self, identifier: str) -> dict[str, Any] | None:
        """Look up an action by canonical slug OR by a legacy ``C-*`` alias.

        Returns the canonical row in both cases so the caller always
        lands on the canonical identity, never on an alias. Used by the
        dispatcher when the frontend sends a legacy identifier during
        the transition window.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                SELECT {_SELECT_COLUMNS}
                FROM rex.ai_action_catalog
                WHERE slug = $1 OR $1 = ANY(legacy_aliases)
                LIMIT 1
                """,
                identifier,
            )
        return _row_to_action(row) if row else None

    # Back-compat alias — earlier scaffolding used this name.
    async def get_by_slug_or_alias(self, identifier: str) -> dict[str, Any] | None:
        return await self.resolve_alias(identifier)

    async def count(self) -> int:
        async with self._pool.acquire() as conn:
            return int(await conn.fetchval(
                "SELECT COUNT(*) FROM rex.ai_action_catalog WHERE enabled = true"
            ))


def _row_to_action(row: asyncpg.Record) -> dict[str, Any]:
    return {
        "slug": row["slug"],
        "legacy_aliases": list(row["legacy_aliases"] or []),
        "label": row["label"],
        "category": row["category"],
        "description": row["description"],
        "params_schema": _load_json(row["params_schema"]),
        "risk_tier": row["risk_tier"],
        "readiness_state": row["readiness_state"],
        "required_connectors": list(row["required_connectors"] or []),
        "role_visibility": list(row["role_visibility"] or []),
        "handler_key": row["handler_key"],
        "enabled": row["enabled"],
        "metadata": _load_json(row["metadata"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _load_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode()
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value
