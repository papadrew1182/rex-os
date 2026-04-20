"""Staging-table upserts for connector_procore.*_raw.

Takes the already-shaped payload dicts returned by the adapter and
writes them to the staging table for the given resource, scoped to
one connector_account. Uses a stable content checksum so unchanged
rows don't churn the source_updated_at column.

Idempotent on ``(account_id, source_id)``. Rows whose checksum is
unchanged become no-op UPDATEs (nothing actually mutates) thanks to
the ``WHERE checksum IS DISTINCT FROM EXCLUDED.checksum`` guard on
the ``ON CONFLICT DO UPDATE`` clause.

Project-scoped staging tables carry ``project_source_id NOT NULL``;
company-level tables (``projects_raw``, ``users_raw``) do not have
that column. We branch the SQL on that distinction.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


ALLOWED_TABLES = {
    "projects_raw",
    "users_raw",
    "rfis_raw",
    "submittals_raw",
    "daily_logs_raw",
    "budget_line_items_raw",
    "commitments_raw",
    "change_events_raw",
    "schedule_tasks_raw",
    "documents_raw",
}

# These do NOT have a project_source_id column (company-level resources).
_NON_PROJECT_TABLES = {"projects_raw", "users_raw"}


def _coerce_timestamp(value: Any) -> datetime | None:
    """Coerce a payload timestamp into a ``datetime`` asyncpg can bind.

    The payload builder stores ``updated_at`` as an ISO-8601 string. asyncpg
    refuses string inputs for ``timestamptz`` parameters, so we parse it here.
    Returns ``None`` if the value is missing or an unparseable shape.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _checksum(payload: dict[str, Any]) -> str:
    """Stable SHA-256 hash of the payload.

    Uses ``sort_keys=True`` so key ordering never influences the digest
    and ``default=str`` to cope with any residual non-JSON-primitive
    values (datetimes, UUIDs, Decimals) that may slip through payload
    builders.
    """
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def upsert_raw(
    db: AsyncSession,
    *,
    raw_table: str,
    items: list[dict[str, Any]],
    account_id: UUID,
) -> int:
    """Upsert a page of items into ``connector_procore.<raw_table>``.

    Returns the number of rows we *attempted* to upsert (== ``len(items)``).
    That count is intentionally NOT the number of mutations — the dedup
    path issues a no-op UPDATE when the checksum is unchanged.

    Raises:
        ValueError: if ``raw_table`` is not in ``ALLOWED_TABLES``.
    """
    if raw_table not in ALLOWED_TABLES:
        raise ValueError(
            f"raw_table {raw_table!r} not in ALLOWED_TABLES; "
            f"allowed: {sorted(ALLOWED_TABLES)}"
        )
    if not items:
        return 0

    has_project_col = raw_table not in _NON_PROJECT_TABLES

    # NOTE: we use ``CAST(:param AS <type>)`` rather than the ``:param::type``
    # shorthand because SQLAlchemy's ``text()`` bind-parameter parser sees the
    # double-colon as part of the parameter name and fails to substitute it.
    if has_project_col:
        sql = text(
            f"""
            INSERT INTO connector_procore.{raw_table}
                (source_id, account_id, project_source_id, payload,
                 source_updated_at, checksum)
            VALUES
                (:source_id, :account_id, :project_source_id,
                 CAST(:payload AS jsonb),
                 :source_updated_at,
                 :checksum)
            ON CONFLICT (account_id, source_id)
            DO UPDATE SET
                payload           = EXCLUDED.payload,
                source_updated_at = EXCLUDED.source_updated_at,
                checksum          = EXCLUDED.checksum,
                project_source_id = EXCLUDED.project_source_id,
                fetched_at        = now()
            WHERE connector_procore.{raw_table}.checksum
                  IS DISTINCT FROM EXCLUDED.checksum
            """
        )
    else:
        sql = text(
            f"""
            INSERT INTO connector_procore.{raw_table}
                (source_id, account_id, payload,
                 source_updated_at, checksum)
            VALUES
                (:source_id, :account_id,
                 CAST(:payload AS jsonb),
                 :source_updated_at,
                 :checksum)
            ON CONFLICT (account_id, source_id)
            DO UPDATE SET
                payload           = EXCLUDED.payload,
                source_updated_at = EXCLUDED.source_updated_at,
                checksum          = EXCLUDED.checksum,
                fetched_at        = now()
            WHERE connector_procore.{raw_table}.checksum
                  IS DISTINCT FROM EXCLUDED.checksum
            """
        )

    upserted = 0
    for item in items:
        params = {
            "source_id":         item["id"],
            "account_id":        account_id,
            "payload":           json.dumps(item, default=str),
            "source_updated_at": _coerce_timestamp(item.get("updated_at")),
            "checksum":          _checksum(item),
        }
        if has_project_col:
            params["project_source_id"] = item.get("project_source_id")
        await db.execute(sql, params)
        upserted += 1

    await db.commit()
    return upserted


__all__ = ["upsert_raw", "ALLOWED_TABLES"]
