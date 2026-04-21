"""End-to-end sync orchestrator for one (account, resource_type) pair.

Pipeline:
  1. start sync_run
  2. look up the prior cursor
  3. discover projects to sync (rex.connector_mappings where
     source_table='procore.projects')
  4. for each project:
       a. adapter.fetch_<resource>(project_external_id, cursor)
       b. staging.upsert_raw(raw_table, items, account_id)
       c. mapper.map_<resource>(item, project_canonical_id)
       d. upsert into rex.<canonical_table> (keyed on natural key)
       e. upsert_source_link for each row
  5. advance sync_cursor to min(next_cursor) across projects that
     returned non-empty pages (ensures no project is starved)
  6. finish sync_run (status=succeeded or failed)

Only 'rfis' is wired in this task; other resource_types raise
NotImplementedError. The follow-up plan adds siblings, reusing this
function's structure.

Design notes:
  * The mapper's output dict IS the canonical-column set. We splat
    ``list(row.keys())`` into the generic INSERT rather than
    hard-coding a column list, so Task 6's mapper is the single
    source of truth for which columns get written.
  * ``item["id"]`` (not the mapper output) is used for the source_link
    source_id; Task 6 intentionally does NOT emit source_id.
  * A project that has no corresponding procore.projects mapping is
    silently skipped (the orchestrator only works on mapped projects).
    An account with zero mapped projects completes cleanly with zero
    counts — the sync_run still lands as 'succeeded'.

NOTE on failure semantics: Each staging/canonical/source_link call commits
independently, so if the pipeline raises partway through a multi-project
run, the sync_run is marked 'failed' but any rows already written before
the failure remain in place. Idempotent replay catches up the rest —
checksum dedup on staging and ON CONFLICT on canonical + source_links
ensure the re-run converges on the right state.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.connectors.procore import mapper
from app.services.connectors.procore.adapter import ProcoreAdapter
from app.services.connectors.procore.staging import upsert_raw
from app.services.connectors.sync_service import (
    finish_sync_run,
    get_cursor,
    set_cursor,
    start_sync_run,
    upsert_source_link,
)

log = logging.getLogger("rex.connectors.procore.orchestrator")


# Resource-specific dispatch table. When the follow-up resource-rollout
# plan lands, add entries here — each new sibling must supply the same
# five keys so _upsert_canonical's naming convention holds.
_RESOURCE_CONFIG: dict[str, dict[str, Any]] = {
    "rfis": {
        "raw_table":       "rfis_raw",
        "map_fn":          mapper.map_rfi,
        "canonical_table": "rfis",         # rex.rfis
        "source_table":    "procore.rfis",
        "fetch_fn_name":   "fetch_rfis",
    },
}


async def sync_resource(
    db: AsyncSession,
    *,
    account_id: UUID,
    resource_type: str,
) -> dict[str, int]:
    """Sync one resource type for one connector account end-to-end.

    Returns a dict ``{"rows_fetched": N, "rows_upserted": M}``. On
    failure, the sync_run is marked 'failed' with an error excerpt and
    the exception re-raises to the caller.
    """
    cfg = _RESOURCE_CONFIG.get(resource_type)
    if cfg is None:
        raise NotImplementedError(
            f"resource_type={resource_type!r} not implemented; "
            f"supported: {sorted(_RESOURCE_CONFIG)}"
        )

    run_id = await start_sync_run(
        db, connector_account_id=account_id, resource_type=resource_type
    )
    # Hoisted above the try block so the failure path can pass the
    # partial counts to finish_sync_run (Fix 3).
    total_fetched = 0
    total_upserted = 0
    try:
        cursor = await get_cursor(
            db, connector_account_id=account_id, resource_type=resource_type
        )
        adapter = ProcoreAdapter(account_id=str(account_id))

        # Discover projects to sync. The orchestrator drives by the
        # project-level source_links — if a canonical project hasn't been
        # linked to a procore project id yet, it's silently skipped.
        project_rows = (await db.execute(text("""
            SELECT external_id, rex_id
            FROM rex.connector_mappings
            WHERE connector = 'procore'
              AND source_table = 'procore.projects'
        """))).mappings().all()

        # next_cursor values from non-empty pages only. We advance the
        # shared cursor to MIN(...) of these so no project is starved
        # by a faster-updating peer (see below).
        project_cursors: list[str] = []

        fetch_fn = getattr(adapter, cfg["fetch_fn_name"])

        for prow in project_rows:
            proj_source_id = prow["external_id"]
            proj_canonical_id = prow["rex_id"]

            page = await fetch_fn(
                project_external_id=proj_source_id,
                cursor=cursor,
            )
            total_fetched += len(page.items)
            if not page.items:
                continue

            # Stage the page.
            await upsert_raw(
                db,
                raw_table=cfg["raw_table"],
                items=page.items,
                account_id=account_id,
            )

            # Canonicalize + upsert + source_link per row.
            for item in page.items:
                canonical_row = cfg["map_fn"](item, str(proj_canonical_id))
                canonical_id = await _upsert_canonical(
                    db, cfg["canonical_table"], canonical_row
                )
                # source_id comes from the raw payload (Task 6 contract:
                # mapper does NOT emit source_id).
                await upsert_source_link(
                    db,
                    connector_key="procore",
                    source_table=cfg["source_table"],
                    source_id=str(item["id"]),
                    canonical_table=f"rex.{cfg['canonical_table']}",
                    canonical_id=canonical_id,
                    project_id=proj_canonical_id,
                )
                total_upserted += 1

            # Collect this project's next_cursor for the MIN-across
            # advancement below. ISO timestamps sort lexicographically
            # for any fixed offset format, which is what
            # build_rfi_payload emits.
            if page.next_cursor:
                project_cursors.append(page.next_cursor)

        # Advance cursor to the MIN across projects that returned non-empty
        # pages. Rationale: shared cursor semantics mean any project must
        # start from a point that no project has already advanced past.
        # Using min() prevents projects with older updated_ats from being
        # starved by faster peers. Over-fetching on the next run for
        # faster projects is absorbed by staging's checksum-based dedup.
        if project_cursors:
            new_cursor = min(project_cursors)
            if new_cursor != cursor:
                await set_cursor(
                    db,
                    connector_account_id=account_id,
                    resource_type=resource_type,
                    cursor_value=new_cursor,
                )

        await finish_sync_run(
            db,
            sync_run_id=run_id,
            status="succeeded",
            rows_fetched=total_fetched,
            rows_upserted=total_upserted,
        )
        return {"rows_fetched": total_fetched, "rows_upserted": total_upserted}

    except Exception as e:
        log.exception("sync_resource failed for %s", resource_type)
        await finish_sync_run(
            db,
            sync_run_id=run_id,
            status="failed",
            rows_fetched=total_fetched,
            rows_upserted=total_upserted,
            error_excerpt=str(e),
        )
        raise


async def _write_rfis(db: AsyncSession, row: dict[str, Any]) -> UUID:
    """Upsert a single RFI row into rex.rfis keyed on (project_id, rfi_number).

    Returns the canonical id (freshly inserted or existing row that got
    updated). ``row``'s keys are the mapper's canonical-column output —
    we splat them dynamically as the INSERT column list so the mapper
    stays the single source of truth for which columns get written.
    """
    cols = list(row.keys())
    col_sql = ", ".join(cols)
    val_sql = ", ".join(f":{c}" for c in cols)
    # The conflict key stays pinned — we never update project_id or
    # rfi_number as part of an ON CONFLICT re-write because those
    # ARE the identity.
    update_sql = ", ".join(
        f"{c} = EXCLUDED.{c}"
        for c in cols
        if c not in ("project_id", "rfi_number")
    )

    sql = text(f"""
        INSERT INTO rex.rfis (id, {col_sql})
        VALUES (gen_random_uuid(), {val_sql})
        ON CONFLICT (project_id, rfi_number)
        DO UPDATE SET {update_sql}
        RETURNING id
    """)
    res = await db.execute(sql, row)
    await db.commit()
    return res.scalar_one()


# Per-resource canonical writers. Each writer owns the INSERT ... ON CONFLICT
# for its rex.<table>. Add a new entry here when a sibling resource lands —
# keep the signature (db, row) -> UUID so _upsert_canonical's dispatch holds.
_CANONICAL_WRITERS: dict[
    str, Callable[[AsyncSession, dict[str, Any]], Awaitable[UUID]]
] = {
    "rfis": _write_rfis,
}


async def _upsert_canonical(
    db: AsyncSession,
    canonical_table: str,
    row: dict[str, Any],
) -> UUID:
    """Dispatch ``row`` to the per-resource canonical writer.

    Returns the canonical id from the underlying writer. Raises
    NotImplementedError if no writer is registered for
    ``canonical_table`` — siblings extend the pipeline by registering
    a new entry in ``_CANONICAL_WRITERS``.
    """
    writer = _CANONICAL_WRITERS.get(canonical_table)
    if writer is None:
        raise NotImplementedError(
            f"no canonical writer registered for rex.{canonical_table}"
        )
    return await writer(db, row)


__all__ = ["sync_resource"]
