"""End-to-end sync orchestrator for one (account, resource_type) pair.

Two shapes of sync live in this module:

* **Root resources** (``projects`` today; ``users`` / ``vendors`` next)
  fetch all rows in a single adapter call, then upsert — there IS no
  parent-project scope because root resources ARE the parent scope
  other resources hang off of.

* **Project-scoped resources** (``rfis`` today) iterate
  ``rex.connector_mappings WHERE source_table='procore.projects'`` and
  call ``adapter.fetch_<resource>(project_external_id, cursor)`` for
  each canonical project the account has linked.

Pipeline (project-scoped path):
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

Pipeline (root path): same but no step 3, no per-project loop; the
cursor advances directly to ``page.next_cursor`` since there's only
one cursor stream.

Currently wired: ``rfis`` and ``projects``. Any other resource_type
raises NotImplementedError.

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
#
# A resource is either ROOT-SCOPED (no parent, e.g. ``projects`` — we
# fetch all then upsert) or PROJECT-SCOPED (iterates rex.connector_mappings
# for procore.projects, then fetches per-project, e.g. ``rfis``).
# ``_ROOT_RESOURCES`` lists the root ones; ``sync_resource`` branches on
# membership below.
_RESOURCE_CONFIG: dict[str, dict[str, Any]] = {
    "rfis": {
        "raw_table":       "rfis_raw",
        "map_fn":          mapper.map_rfi,
        "canonical_table": "rfis",         # rex.rfis
        "source_table":    "procore.rfis",
        "fetch_fn_name":   "fetch_rfis",
    },
    "projects": {
        "raw_table":       "projects_raw",
        "map_fn":          mapper.map_project,      # single-arg mapper
        "canonical_table": "projects",              # rex.projects
        "source_table":    "procore.projects",
        "fetch_fn_name":   "list_projects",
    },
    "users": {
        "raw_table":       "users_raw",
        "map_fn":          mapper.map_user,         # single-arg mapper
        "canonical_table": "people",                # rex.people
        "source_table":    "procore.users",
        "fetch_fn_name":   "list_users",
    },
    "vendors": {
        "raw_table":       "vendors_raw",
        "map_fn":          mapper.map_vendor,       # single-arg mapper
        "canonical_table": "companies",             # rex.companies
        "source_table":    "procore.vendors",
        "fetch_fn_name":   "list_vendors",
    },
    "submittals": {
        # Phase 4 Wave 2 (direct Procore API) — project-scoped resource.
        # fetch_submittals calls ProcoreClient.list_submittals directly;
        # the rex-procore Railway DB does NOT have a procore.submittals
        # table, so unlike rfis this resource can't fall back to the
        # flattened source.
        "raw_table":       "submittals_raw",
        "map_fn":          mapper.map_submittal,
        "canonical_table": "submittals",            # rex.submittals
        "source_table":    "procore.submittals",
        "fetch_fn_name":   "fetch_submittals",
    },
    "daily_logs": {
        # Phase 4 Wave 2 (direct Procore API) — project-scoped resource.
        # fetch_daily_logs calls ProcoreClient.list_daily_logs directly
        # against /rest/v1.0/projects/{id}/daily_logs/
        # construction_report_logs. Like submittals, this resource has
        # no rex-procore Railway fallback — going direct is the only
        # path to a rex.daily_logs row.
        "raw_table":       "daily_logs_raw",
        "map_fn":          mapper.map_daily_log,
        "canonical_table": "daily_logs",            # rex.daily_logs
        "source_table":    "procore.daily_logs",
        "fetch_fn_name":   "fetch_daily_logs",
    },
    "schedule_activities": {
        # Phase 4 Wave 2 (direct Procore API) — project-scoped resource.
        # fetch_schedule_activities calls ProcoreClient.list_schedule_tasks
        # directly against /rest/v1.0/projects/{id}/schedule/standard_tasks.
        # Like submittals / daily_logs, this resource has no rex-procore
        # Railway fallback.
        #
        # Staging lands in connector_procore.schedule_tasks_raw (created by
        # migration 013; named after Procore's endpoint noun, not the rex
        # canonical name). The canonical target is rex.schedule_activities,
        # which requires a rex.schedules FK — the writer bootstraps a
        # "Procore default schedule" row per project on the fly. See
        # _write_schedule_activities for the bootstrap mechanics.
        "raw_table":       "schedule_tasks_raw",
        "map_fn":          mapper.map_schedule_activity,
        "canonical_table": "schedule_activities",   # rex.schedule_activities
        "source_table":    "procore.schedule_activities",
        "fetch_fn_name":   "fetch_schedule_activities",
    },
    "change_events": {
        # Phase 4 Wave 2 (direct Procore API) — project-scoped resource.
        # fetch_change_events calls ProcoreClient.list_change_events
        # directly against /rest/v1.0/projects/{id}/change_events. Like
        # submittals / daily_logs / schedule_activities, this resource
        # has no rex-procore Railway fallback.
        #
        # LLM-tool overlap: Phase 6b Wave 2 shipped a ``create_change_event``
        # LLM tool that inserts into rex.change_events directly. Both
        # paths upsert on the ``(project_id, event_number)`` natural key
        # via ON CONFLICT DO UPDATE, so the sync-vs-tool write sources
        # converge cleanly on one canonical row.
        "raw_table":       "change_events_raw",
        "map_fn":          mapper.map_change_event,
        "canonical_table": "change_events",           # rex.change_events
        "source_table":    "procore.change_events",
        "fetch_fn_name":   "fetch_change_events",
    },
}

# Resources with no parent-project scope. Their ``map_fn`` takes ONE arg
# (the raw payload) and the orchestrator's main per-project loop is
# skipped for them.
_ROOT_RESOURCES: frozenset[str] = frozenset({"projects", "users", "vendors"})


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

        # ── Root resource branch (projects / users / vendors) ────────────
        #
        # Root resources have no parent-project scope — we fetch the full
        # page straight off the adapter and upsert into the canonical
        # table. The per-project iteration below doesn't apply because
        # there ARE no parent projects: these resources ARE the parent.
        # ``map_fn`` for root resources takes ONE argument (the raw
        # payload); project-scoped resources take ``(raw, project_id)``.
        #
        # The canonical_id is also the project_id when the resource IS
        # projects — that's what we pass to upsert_source_link below so
        # other resources can later join rex.connector_mappings to find
        # their project parent.
        if resource_type in _ROOT_RESOURCES:
            fetch_fn = getattr(adapter, cfg["fetch_fn_name"])
            page = await fetch_fn(cursor=cursor)
            total_fetched = len(page.items)
            if page.items:
                await upsert_raw(
                    db,
                    raw_table=cfg["raw_table"],
                    items=page.items,
                    account_id=account_id,
                )
                for item in page.items:
                    canonical_row = cfg["map_fn"](item)
                    canonical_id = await _upsert_canonical(
                        db, cfg["canonical_table"], canonical_row,
                    )
                    # For the ``projects`` resource the canonical row IS
                    # the project, so canonical_id == project_id. When
                    # users / vendors land, their source_links won't
                    # carry a project_id (they're account-scoped) —
                    # special-case as needed.
                    link_project_id = (
                        canonical_id if resource_type == "projects" else None
                    )
                    await upsert_source_link(
                        db,
                        connector_key="procore",
                        source_table=cfg["source_table"],
                        source_id=str(item["id"]),
                        canonical_table=f"rex.{cfg['canonical_table']}",
                        canonical_id=canonical_id,
                        project_id=link_project_id,
                    )
                    total_upserted += 1
                if page.next_cursor and page.next_cursor != cursor:
                    await set_cursor(
                        db,
                        connector_account_id=account_id,
                        resource_type=resource_type,
                        cursor_value=page.next_cursor,
                    )
            await finish_sync_run(
                db,
                sync_run_id=run_id,
                status="succeeded",
                rows_fetched=total_fetched,
                rows_upserted=total_upserted,
            )
            return {
                "rows_fetched":  total_fetched,
                "rows_upserted": total_upserted,
            }

        # ── Project-scoped path (rfis and siblings) ──────────────────────
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


async def _write_projects(db: AsyncSession, row: dict[str, Any]) -> UUID:
    """Upsert a single project row into rex.projects keyed on project_number.

    Migration 025 adds the UNIQUE (project_number) constraint this
    ON CONFLICT relies on. Without it, Postgres fails at plan time
    with "there is no unique or exclusion constraint matching the
    ON CONFLICT specification".

    ``row``'s keys are the mapper's canonical-column output —
    splatted dynamically as the INSERT column list so mapper.map_project
    stays the single source of truth for which columns get written.
    """
    cols = list(row.keys())
    col_sql = ", ".join(cols)
    val_sql = ", ".join(f":{c}" for c in cols)
    # project_number is the identity key — never rewrite it as part
    # of the conflict update. Everything else gets overwritten so a
    # Procore row that moved city/status/dates converges on the new
    # values after the next sync.
    update_sql = ", ".join(
        f"{c} = EXCLUDED.{c}"
        for c in cols
        if c != "project_number"
    )

    sql = text(f"""
        INSERT INTO rex.projects (id, {col_sql})
        VALUES (gen_random_uuid(), {val_sql})
        ON CONFLICT (project_number)
        DO UPDATE SET {update_sql}
        RETURNING id
    """)
    res = await db.execute(sql, row)
    await db.commit()
    return res.scalar_one()


async def _write_users(db: AsyncSession, row: dict[str, Any]) -> UUID:
    """Upsert a single person row into rex.people keyed on email.

    Migration 026 adds the UNIQUE (email) constraint this ON CONFLICT
    relies on. Without it, Postgres fails at plan time with "there is
    no unique or exclusion constraint matching the ON CONFLICT
    specification".

    ``row``'s keys are the mapper's canonical-column output —
    splatted dynamically as the INSERT column list so mapper.map_user
    stays the single source of truth for which columns get written.

    NULL-email note: mapper.map_user synthesizes a deterministic
    ``procore-user-<id>@placeholder.invalid`` address for source rows
    with NULL email. Those placeholders still satisfy the UNIQUE
    constraint and make the upsert idempotent across re-syncs.
    """
    cols = list(row.keys())
    col_sql = ", ".join(cols)
    val_sql = ", ".join(f":{c}" for c in cols)
    # email is the identity key — never rewrite it as part of the
    # conflict update. Everything else gets overwritten so a Procore
    # row that moved phone/title/name converges on the new values
    # after the next sync.
    update_sql = ", ".join(
        f"{c} = EXCLUDED.{c}" for c in cols if c != "email"
    )

    sql = text(f"""
        INSERT INTO rex.people (id, {col_sql})
        VALUES (gen_random_uuid(), {val_sql})
        ON CONFLICT (email) DO UPDATE SET {update_sql}
        RETURNING id
    """)
    res = await db.execute(sql, row)
    await db.commit()
    return res.scalar_one()


async def _write_vendors(db: AsyncSession, row: dict[str, Any]) -> UUID:
    """Upsert a single vendor row into rex.companies keyed on name.

    Migration 027 adds the UNIQUE (name) constraint this ON CONFLICT
    relies on. Without it, Postgres fails at plan time with "there is
    no unique or exclusion constraint matching the ON CONFLICT
    specification".

    ``row``'s keys are the mapper's canonical-column output —
    splatted dynamically as the INSERT column list so mapper.map_vendor
    stays the single source of truth for which columns get written.

    Defensive behavior: if the live DB already has multiple
    rex.companies rows with the same ``name`` (two subs with the same
    legal name but different locations), migration 027's DO-block
    exception-swallow leaves the UNIQUE constraint un-applied. The
    ON CONFLICT upsert here will then fail at plan time with a clear
    error — which is the right signal for an operator to resolve the
    duplicates manually before retrying the sync.
    """
    cols = list(row.keys())
    col_sql = ", ".join(cols)
    val_sql = ", ".join(f":{c}" for c in cols)
    # name is the identity key — never rewrite it as part of the
    # conflict update. Everything else gets overwritten so a Procore
    # row that moved phone/trade/dates converges on the new values
    # after the next sync.
    update_sql = ", ".join(
        f"{c} = EXCLUDED.{c}" for c in cols if c != "name"
    )

    sql = text(f"""
        INSERT INTO rex.companies (id, {col_sql})
        VALUES (gen_random_uuid(), {val_sql})
        ON CONFLICT (name) DO UPDATE SET {update_sql}
        RETURNING id
    """)
    res = await db.execute(sql, row)
    await db.commit()
    return res.scalar_one()


async def _write_submittals(db: AsyncSession, row: dict[str, Any]) -> UUID:
    """Upsert a single submittal row into rex.submittals keyed on
    (project_id, submittal_number).

    Migration 031 adds the UNIQUE (project_id, submittal_number)
    constraint this ON CONFLICT relies on. Without it, Postgres fails
    at plan time with "there is no unique or exclusion constraint
    matching the ON CONFLICT specification".

    ``row``'s keys are mapper.map_submittal's canonical-column output —
    splatted dynamically as the INSERT column list so the mapper stays
    the single source of truth for which columns get written. The
    identity tuple (project_id, submittal_number) is never rewritten
    on conflict; everything else converges on the Procore-side values
    after each sync.
    """
    cols = list(row.keys())
    col_sql = ", ".join(cols)
    val_sql = ", ".join(f":{c}" for c in cols)
    update_sql = ", ".join(
        f"{c} = EXCLUDED.{c}"
        for c in cols
        if c not in ("project_id", "submittal_number")
    )

    sql = text(f"""
        INSERT INTO rex.submittals (id, {col_sql})
        VALUES (gen_random_uuid(), {val_sql})
        ON CONFLICT (project_id, submittal_number)
        DO UPDATE SET {update_sql}
        RETURNING id
    """)
    res = await db.execute(sql, row)
    await db.commit()
    return res.scalar_one()


async def _write_daily_logs(db: AsyncSession, row: dict[str, Any]) -> UUID:
    """Upsert a single daily-log row into rex.daily_logs keyed on
    (project_id, log_date).

    The canonical DDL (rex2_canonical_ddl.sql line 285) already carries
    the ``UNIQUE (project_id, log_date)`` constraint this ON CONFLICT
    relies on — no supplementary migration is required for this
    resource (unlike rfis / submittals whose unique constraints were
    added retroactively in migrations 024 / 031).

    ``row``'s keys are mapper.map_daily_log's canonical-column output —
    splatted dynamically as the INSERT column list so the mapper stays
    the single source of truth for which columns get written. The
    identity tuple (project_id, log_date) is never rewritten on
    conflict; everything else converges on the Procore-side values
    after each sync.
    """
    cols = list(row.keys())
    col_sql = ", ".join(cols)
    val_sql = ", ".join(f":{c}" for c in cols)
    update_sql = ", ".join(
        f"{c} = EXCLUDED.{c}"
        for c in cols
        if c not in ("project_id", "log_date")
    )

    sql = text(f"""
        INSERT INTO rex.daily_logs (id, {col_sql})
        VALUES (gen_random_uuid(), {val_sql})
        ON CONFLICT (project_id, log_date)
        DO UPDATE SET {update_sql}
        RETURNING id
    """)
    res = await db.execute(sql, row)
    await db.commit()
    return res.scalar_one()


async def _write_schedule_activities(
    db: AsyncSession, row: dict[str, Any]
) -> UUID:
    """Upsert a single schedule activity into rex.schedule_activities,
    bootstrapping the parent rex.schedules row on the fly.

    rex.schedule_activities.schedule_id is a NOT NULL FK to rex.schedules,
    but Procore's standard_tasks endpoint has no first-class "schedule"
    concept — tasks come back without a schedule container. rex.schedules
    is a Rex-specific abstraction. To satisfy the FK without forcing
    upstream projects to pre-create a schedule row, the writer upserts a
    "Procore default schedule" row scoped to the project, then resolves
    its id as schedule_id on the activity.

    Bootstrap schedule shape (matches the rex.schedules CHECK constraints):
      * project_id     — from the mapper's ``project_id`` sidecar
      * name           — from the mapper's ``schedule_name`` sidecar
                         ("Procore default schedule")
      * schedule_type  — 'master' (the only "whole project" shape in the
                         rex.schedules CHECK enum; master is the right
                         classification for Procore's single per-project
                         task list)
      * status         — 'active' (DB default fires via omission pattern,
                         but we set it explicitly so the ON CONFLICT DO
                         UPDATE doesn't NULL it out on re-sync)
      * start_date     — CURRENT_DATE at insert time. Updated on conflict
                         only if null (keeps the original creation date
                         stable across syncs).
      * end_date       — None; the schedule has no fixed end date since
                         activities belong to a continuously-evolving
                         project plan.
      * created_by     — None; Procore sync doesn't know which Rex user
                         triggered it.
    The (project_id, name) UNIQUE constraint (migration 032) backs the
    ON CONFLICT upsert; the DO UPDATE is a no-op that just returns the
    existing id.

    Canonical activity upsert: after the schedule is resolved, the
    activity INSERT ... ON CONFLICT (schedule_id, activity_number) DO
    UPDATE keys on the tuple migration 032 makes UNIQUE. The mapper's
    ``schedule_name`` and ``project_id`` sidecars are stripped before
    the INSERT splat — they're consumed by the schedule bootstrap only.

    Transactional integrity: both statements run in the same session
    (no intermediate commit), so if the activity INSERT fails after the
    schedule row was created, the outer sync_resource's failure path
    leaves the sync_run marked 'failed' — but the schedule row remains
    (committed by the explicit ``await db.commit()`` call below, matching
    the pattern the other _write_* functions use). Idempotent replay
    catches up cleanly.
    """
    # Step 1: upsert the parent rex.schedules row keyed on
    # (project_id, name). migration 032 adds the UNIQUE constraint.
    schedule_stmt = text(
        """
        INSERT INTO rex.schedules (
            id, project_id, name, schedule_type, status,
            start_date, end_date, created_by,
            created_at, updated_at
        )
        VALUES (
            gen_random_uuid(), :project_id, :schedule_name,
            'master', 'active',
            CURRENT_DATE, NULL, NULL,
            now(), now()
        )
        ON CONFLICT (project_id, name)
        DO UPDATE SET updated_at = rex.schedules.updated_at
        RETURNING id
        """
    )
    schedule_result = await db.execute(schedule_stmt, {
        "project_id":    row["project_id"],
        "schedule_name": row["schedule_name"],
    })
    schedule_id = schedule_result.scalar_one()

    # Step 2: strip the bootstrap sidecars — ``schedule_name`` and
    # ``project_id`` are NOT rex.schedule_activities columns — and
    # build the activity payload with the resolved schedule_id.
    activity_row = {
        k: v for k, v in row.items()
        if k not in ("schedule_name", "project_id")
    }
    activity_row["schedule_id"] = schedule_id

    cols = list(activity_row.keys())
    col_sql = ", ".join(cols)
    val_sql = ", ".join(f":{c}" for c in cols)
    # Never rewrite the identity tuple on conflict. Everything else
    # converges on the Procore-side values after each sync.
    update_sql = ", ".join(
        f"{c} = EXCLUDED.{c}"
        for c in cols
        if c not in ("schedule_id", "activity_number")
    )

    sql = text(f"""
        INSERT INTO rex.schedule_activities (id, {col_sql})
        VALUES (gen_random_uuid(), {val_sql})
        ON CONFLICT (schedule_id, activity_number)
        DO UPDATE SET {update_sql}
        RETURNING id
    """)
    res = await db.execute(sql, activity_row)
    await db.commit()
    return res.scalar_one()


async def _write_change_events(
    db: AsyncSession, row: dict[str, Any]
) -> UUID:
    """Upsert a single change-event row into rex.change_events keyed on
    (project_id, event_number).

    Migration 033 adds the UNIQUE (project_id, event_number) constraint
    this ON CONFLICT relies on — it is NOT declared in the canonical
    DDL (rex2_canonical_ddl.sql line 619) so a supplementary migration
    is required. Without it, Postgres fails at plan time with "there is
    no unique or exclusion constraint matching the ON CONFLICT
    specification".

    Overlap note: Phase 6b Wave 2's ``create_change_event`` LLM tool
    also inserts into rex.change_events. The (project_id, event_number)
    ON CONFLICT upsert is shared between the tool and this sync writer,
    so both paths converge on a single canonical row. If the LLM tool
    pre-creates a row for an event_number the Procore sync later
    discovers, the DO UPDATE overwrites the title/description/status/
    reason/type/scope/estimated_amount with Procore's values (Procore is
    the authoritative source of truth for this resource in production).

    ``row``'s keys are mapper.map_change_event's canonical-column output
    — splatted dynamically as the INSERT column list so the mapper stays
    the single source of truth for which columns get written. The
    identity tuple (project_id, event_number) is never rewritten on
    conflict; everything else converges on the Procore-side values after
    each sync.
    """
    stmt = text(
        """
        INSERT INTO rex.change_events (
            id, project_id, event_number, title, description,
            status, change_reason, event_type, scope, estimated_amount,
            rfi_id, prime_contract_id, created_by,
            created_at, updated_at
        ) VALUES (
            gen_random_uuid(), :project_id, :event_number, :title, :description,
            :status, :change_reason, :event_type, :scope, :estimated_amount,
            :rfi_id, :prime_contract_id, :created_by,
            now(), now()
        )
        ON CONFLICT (project_id, event_number) DO UPDATE SET
            title = EXCLUDED.title,
            description = EXCLUDED.description,
            status = EXCLUDED.status,
            change_reason = EXCLUDED.change_reason,
            event_type = EXCLUDED.event_type,
            scope = EXCLUDED.scope,
            estimated_amount = EXCLUDED.estimated_amount,
            updated_at = now()
        RETURNING id
        """
    )
    result = await db.execute(stmt, row)
    await db.commit()
    return result.scalar_one()


# Per-resource canonical writers. Each writer owns the INSERT ... ON CONFLICT
# for its rex.<table>. Add a new entry here when a sibling resource lands —
# keep the signature (db, row) -> UUID so _upsert_canonical's dispatch holds.
#
# Dispatch key is the ``canonical_table`` from _RESOURCE_CONFIG, not the
# resource_type — ``users`` maps to rex.people so the writer registers
# under ``people``. See _upsert_canonical's lookup below.
_CANONICAL_WRITERS: dict[
    str, Callable[[AsyncSession, dict[str, Any]], Awaitable[UUID]]
] = {
    "rfis":                 _write_rfis,
    "projects":             _write_projects,
    "people":               _write_users,
    "companies":            _write_vendors,
    "submittals":           _write_submittals,
    "daily_logs":           _write_daily_logs,
    "schedule_activities":  _write_schedule_activities,
    "change_events":        _write_change_events,
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
