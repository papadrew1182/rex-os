"""Connector registry repository helpers.

Thin SQL wrappers for the /api/connectors + /api/connectors/health
endpoints so the logic can be reused by the admin-jobs runner and
by tests without hitting HTTP routes.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def list_connectors_with_status(db: AsyncSession) -> list[dict]:
    """Return one row per connector kind with rolling status."""
    rows = (await db.execute(
        text(
            """
            SELECT
                c.id,
                c.connector_key,
                c.label,
                c.description,
                c.is_enabled,
                CASE
                    WHEN NOT c.is_enabled THEN 'disabled'
                    WHEN EXISTS (SELECT 1 FROM rex.connector_accounts a WHERE a.connector_id = c.id AND a.status = 'connected')
                        THEN 'connected'
                    WHEN EXISTS (SELECT 1 FROM rex.connector_accounts a WHERE a.connector_id = c.id AND a.status = 'error')
                        THEN 'error'
                    WHEN EXISTS (SELECT 1 FROM rex.connector_accounts a WHERE a.connector_id = c.id AND a.status = 'configured')
                        THEN 'configured'
                    WHEN EXISTS (SELECT 1 FROM rex.connector_accounts a WHERE a.connector_id = c.id AND a.status = 'disconnected')
                        THEN 'disconnected'
                    ELSE 'configured'
                END AS status,
                (SELECT MAX(a.last_sync_at) FROM rex.connector_accounts a WHERE a.connector_id = c.id)    AS last_sync_at,
                (SELECT MAX(a.last_success_at) FROM rex.connector_accounts a WHERE a.connector_id = c.id) AS last_success_at,
                (SELECT COUNT(*) FROM rex.connector_accounts a WHERE a.connector_id = c.id)              AS account_count
            FROM rex.connectors c
            ORDER BY c.connector_key
            """
        )
    )).mappings().all()
    return [dict(r) for r in rows]


async def list_connector_accounts(db: AsyncSession, connector_key: str | None = None) -> list[dict]:
    rows = (await db.execute(
        text(
            """
            SELECT
                a.id,
                a.label,
                a.environment,
                a.status,
                a.last_sync_at,
                a.last_success_at,
                a.last_error_at,
                a.last_error_message,
                a.is_primary,
                c.connector_key,
                c.label AS connector_label
            FROM rex.connector_accounts a
            JOIN rex.connectors c ON c.id = a.connector_id
            WHERE (:ck::text IS NULL OR c.connector_key = :ck)
            ORDER BY c.connector_key, a.environment, a.label
            """
        ),
        {"ck": connector_key},
    )).mappings().all()
    return [dict(r) for r in rows]


__all__ = ["list_connectors_with_status", "list_connector_accounts"]
