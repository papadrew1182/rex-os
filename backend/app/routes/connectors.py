"""Connector registry + health endpoints for Session 2.

Charter-locked surfaces at:
  GET /api/connectors         -- kind registry + configured-account status
  GET /api/connectors/health  -- rolling health per connector account

These endpoints do NOT expose credentials or internal configuration —
they only surface the control-plane rollup that Session 3's control plane
UI needs.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_admin_or_vp
from app.models.foundation import UserAccount
from app.services.connectors.procore.orchestrator import (
    sync_resource as procore_sync_resource,
)

router = APIRouter(prefix="/api/connectors", tags=["session2-connectors"])


# ── GET /api/connectors ─────────────────────────────────────────────────

@router.get("")
@router.get("/")
async def list_connectors(
    user: UserAccount = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return one row per connector KIND with its rolling status.

    Status resolution:
      - If any account for the connector is 'connected', the kind is 'connected'.
      - Else if any account is 'error', the kind is 'error'.
      - Else if any account is 'configured' or 'disconnected', that status.
      - Else 'disabled'.
    """
    rows = (await db.execute(
        text(
            """
            SELECT
                c.connector_key,
                c.label,
                c.description,
                c.is_enabled,
                -- Resolve the best rolling status across accounts.
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

    return {
        "items": [
            {
                "connector_key": r["connector_key"],
                "label": r["label"],
                "description": r["description"],
                "is_enabled": r["is_enabled"],
                "status": r["status"],
                "last_sync_at": r["last_sync_at"].isoformat() if r["last_sync_at"] else None,
                "last_success_at": r["last_success_at"].isoformat() if r["last_success_at"] else None,
                "account_count": r["account_count"],
            }
            for r in rows
        ]
    }


# ── GET /api/connectors/health ──────────────────────────────────────────

@router.get("/health")
async def connector_health(
    user: UserAccount = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return per-connector-kind health rollup.

    One row per connector_key. `healthy=true` means the most recent
    signal across all accounts of that kind was a success with no
    unresolved error state.
    """
    rows = (await db.execute(
        text(
            """
            SELECT
                c.connector_key,
                c.label,
                bool_or(COALESCE(a.status = 'connected', false))                           AS any_connected,
                bool_or(COALESCE(a.status = 'error', false))                               AS any_error,
                MAX(a.last_success_at)                                                     AS last_success_at,
                MAX(a.last_error_at)                                                       AS last_error_at,
                (array_agg(a.last_error_message ORDER BY a.last_error_at DESC NULLS LAST))[1] AS last_error_message,
                COUNT(a.id)                                                                AS account_count
            FROM rex.connectors c
            LEFT JOIN rex.connector_accounts a ON a.connector_id = c.id
            GROUP BY c.connector_key, c.label
            ORDER BY c.connector_key
            """
        )
    )).mappings().all()

    items = []
    for r in rows:
        last_success = r["last_success_at"]
        last_error = r["last_error_at"]
        healthy = bool(r["any_connected"]) and not bool(r["any_error"])
        # If we have a newer success than the last error, consider healthy.
        if last_error is not None and last_success is not None and last_success > last_error:
            healthy = True
        items.append({
            "connector_key": r["connector_key"],
            "label": r["label"],
            "healthy": healthy,
            "last_success_at": last_success.isoformat() if last_success else None,
            "last_error_at": last_error.isoformat() if last_error else None,
            "last_error_message": r["last_error_message"],
            "account_count": r["account_count"],
        })

    return {"items": items}


# ── POST /api/connectors/{account_id}/sync/{resource_type} ──────────────
#
# Admin / VP-only. Dispatches to the appropriate connector orchestrator and
# returns the orchestrator's ``{rows_fetched, rows_upserted}`` dict. The
# scheduler will eventually call this on a cron schedule, but for now it's
# the operator's hand-pull trigger.

@router.post("/{account_id}/sync/{resource_type}")
async def admin_sync_resource(
    account_id: UUID,
    resource_type: str,
    db: AsyncSession = Depends(get_db),
    user: UserAccount = Depends(require_admin_or_vp),
) -> dict:
    """Trigger a sync for one (account, resource_type) pair.

    Returns whatever the underlying orchestrator returns (counts dict).
    Raises:
      * 404 if the connector_account doesn't exist
      * 400 if the account's connector kind doesn't have a sync path yet
      * 500 (FastAPI default) on orchestrator failure — the sync_run
        record captures the failure detail for post-mortem.
    """
    connector_key = (await db.execute(
        text(
            """
            SELECT c.connector_key
            FROM rex.connector_accounts a
            JOIN rex.connectors c ON c.id = a.connector_id
            WHERE a.id = :a
            """
        ),
        {"a": account_id},
    )).scalar_one_or_none()

    if connector_key is None:
        raise HTTPException(
            status_code=404,
            detail=f"connector_account {account_id} not found",
        )

    if connector_key == "procore":
        return await procore_sync_resource(
            db, account_id=account_id, resource_type=resource_type
        )

    raise HTTPException(
        status_code=400,
        detail=f"sync not implemented for connector {connector_key!r}",
    )
