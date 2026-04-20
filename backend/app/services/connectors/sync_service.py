"""Connector sync orchestration helpers.

Session 2 owns the sync-run / cursor / event-log / source-link control
plane. This module provides thin helpers that the adapter layer and the
admin_jobs runner can call to:

  - start a sync_run row
  - finalize it with counts + status
  - read/write cursors
  - append to the connector_event_log
  - upsert source_links for canonical rows that just landed

Nothing here touches upstream APIs. The adapter layer fetches pages;
this layer records what happened and where.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger("rex.connectors.sync_service")


# ── sync_runs ───────────────────────────────────────────────────────────

async def start_sync_run(
    db: AsyncSession,
    *,
    connector_account_id: UUID,
    resource_type: str,
) -> UUID:
    """Insert a fresh sync_runs row and return its id."""
    row = (await db.execute(
        text(
            """
            INSERT INTO rex.sync_runs
                (connector_account_id, resource_type, status, started_at)
            VALUES (:account, :resource, 'running', now())
            RETURNING id
            """
        ),
        {"account": connector_account_id, "resource": resource_type},
    )).mappings().first()
    await db.commit()
    return row["id"]


async def finish_sync_run(
    db: AsyncSession,
    *,
    sync_run_id: UUID,
    status: str,
    rows_fetched: int = 0,
    rows_upserted: int = 0,
    rows_skipped: int = 0,
    error_excerpt: str | None = None,
    summary: dict[str, Any] | None = None,
) -> None:
    """Finalize a sync_runs row with counts and status."""
    if status not in ("running", "succeeded", "failed", "cancelled"):
        raise ValueError(f"invalid sync status: {status}")
    await db.execute(
        text(
            """
            UPDATE rex.sync_runs
               SET status        = :status,
                   finished_at   = now(),
                   duration_ms   = EXTRACT(MILLISECONDS FROM (now() - started_at))::int,
                   rows_fetched  = :fetched,
                   rows_upserted = :upserted,
                   rows_skipped  = :skipped,
                   error_excerpt = :err,
                   summary       = COALESCE(CAST(:summary AS jsonb), summary)
             WHERE id = :id
            """
        ),
        {
            "status": status,
            "fetched": rows_fetched,
            "upserted": rows_upserted,
            "skipped": rows_skipped,
            "err": (error_excerpt or "")[:500] or None,
            "summary": None if summary is None else _json(summary),
            "id": sync_run_id,
        },
    )
    await db.commit()


# ── sync_cursors ────────────────────────────────────────────────────────

async def get_cursor(
    db: AsyncSession,
    *,
    connector_account_id: UUID,
    resource_type: str,
) -> str | None:
    row = (await db.execute(
        text(
            """
            SELECT cursor_value
            FROM rex.sync_cursors
            WHERE connector_account_id = :account AND resource_type = :resource
            """
        ),
        {"account": connector_account_id, "resource": resource_type},
    )).mappings().first()
    return row["cursor_value"] if row else None


async def set_cursor(
    db: AsyncSession,
    *,
    connector_account_id: UUID,
    resource_type: str,
    cursor_value: str | None,
) -> None:
    await db.execute(
        text(
            """
            INSERT INTO rex.sync_cursors (connector_account_id, resource_type, cursor_value)
            VALUES (:account, :resource, :cursor)
            ON CONFLICT (connector_account_id, resource_type)
            DO UPDATE SET cursor_value = EXCLUDED.cursor_value, updated_at = now()
            """
        ),
        {
            "account": connector_account_id,
            "resource": resource_type,
            "cursor": cursor_value,
        },
    )
    await db.commit()


# ── connector_event_log ────────────────────────────────────────────────

async def log_event(
    db: AsyncSession,
    *,
    connector_account_id: UUID | None,
    event_type: str,
    severity: str = "info",
    message: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    if severity not in ("debug", "info", "warning", "error", "critical"):
        raise ValueError(f"invalid severity: {severity}")
    await db.execute(
        text(
            """
            INSERT INTO rex.connector_event_log
                (connector_account_id, event_type, severity, message, payload)
            VALUES (:account, :etype, :sev, :msg,
                    COALESCE(CAST(:payload AS jsonb), '{}'::jsonb))
            """
        ),
        {
            "account": connector_account_id,
            "etype": event_type,
            "sev": severity,
            "msg": message,
            "payload": None if payload is None else _json(payload),
        },
    )
    await db.commit()


# ── source_links ────────────────────────────────────────────────────────
#
# rex.source_links is a view over rex.connector_mappings — writes go to
# the underlying table with the new Session 2 columns populated.

async def upsert_source_link(
    db: AsyncSession,
    *,
    connector_key: str,
    source_table: str,
    source_id: str,
    canonical_table: str,
    canonical_id: UUID,
    project_id: UUID | None = None,
    external_url: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record or refresh the link from a connector-native row to a
    canonical rex.* row. Idempotent on (connector_key, source_table, source_id).
    """
    # NOTE: we use ``CAST(:param AS <type>)`` rather than the
    # ``:param::type`` shorthand because SQLAlchemy's ``text()``
    # bind-parameter parser sees the double-colon as part of the
    # parameter name and fails to substitute it. Same fix as staging.py.
    await db.execute(
        text(
            """
            INSERT INTO rex.connector_mappings
                (rex_table, rex_id, connector, external_id, external_url,
                 source_table, project_id, metadata, synced_at)
            VALUES (:canonical_table, :canonical_id, :connector, :source_id,
                    :external_url, :source_table, :project_id,
                    COALESCE(CAST(:metadata AS jsonb), '{}'::jsonb), now())
            ON CONFLICT (rex_table, connector, external_id)
            DO UPDATE SET
                rex_id       = EXCLUDED.rex_id,
                external_url = EXCLUDED.external_url,
                source_table = EXCLUDED.source_table,
                project_id   = EXCLUDED.project_id,
                metadata     = EXCLUDED.metadata,
                synced_at    = now()
            """
        ),
        {
            "canonical_table": canonical_table,
            "canonical_id": canonical_id,
            "connector": connector_key,
            "source_id": source_id,
            "external_url": external_url,
            "source_table": source_table,
            "project_id": project_id,
            "metadata": None if metadata is None else _json(metadata),
        },
    )
    await db.commit()


# ── internal helper ─────────────────────────────────────────────────────

def _json(value: Any) -> str:
    import json
    return json.dumps(value)


__all__ = [
    "start_sync_run",
    "finish_sync_run",
    "get_cursor",
    "set_cursor",
    "log_event",
    "upsert_source_link",
]
