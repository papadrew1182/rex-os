"""Lightweight migration runner for Rex OS.

Shares the ordered migration set with ``main.py``'s admin endpoint. Can be
invoked directly::

    python -m app.migrate              # apply all pending
    python -m app.migrate --dry-run    # show planned order without executing
    python -m app.migrate --list       # alias for --dry-run

The runner:
- executes migration SQL files in a deterministic, hardcoded order
- logs each applied file
- aborts on the first failure (no partial silent skips)
- works against the same DB as the backend (reads ``DATABASE_URL`` from
  ``.env`` / env vars via ``app.config.settings``)

This is intentionally NOT alembic. It's a thin runner for the 4 canonical
SQL files; schema evolution tooling can be added later without redesigning
this boundary.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# ── Ordered migration set (single source of truth) ────────────────────────

MIGRATION_ORDER: list[str] = [
    # Foundation
    "001_create_schema.sql",
    "rex2_canonical_ddl.sql",
    "rex2_foundation_bootstrap.sql",
    "rex2_business_seed.sql",
    # Phase 4-5: closed_by, is_critical_path, rfi_manager, submittal_manager_id,
    # estimated_completion_date, change_event_line_items
    "002_field_parity_batch.sql",
    # Phase 21: schedule actuals + WBS, milestone forecast/percent,
    # warranty product/manufacturer, insurance_certificates table
    "003_phase21_p1_batch.sql",
    # Phase 31-32: job_runs + notifications tables
    "004_phase31_jobs_notifications.sql",
    # Phase 38-39: schedule depth fields, project geo, company extras,
    # observation root cause, closeout spec linkage, om_manuals table
    "005_phase38_phase39_p2_batch.sql",
    # Session 1 AI spine (feat/ai-spine):
    # 006 = rex.chat_conversations, rex.chat_messages, rex.ai_prompt_registry
    #       (seeded: assistant.system.base prompt v1)
    # 007 = rex.ai_action_catalog table (CHECK constraints on risk_tier /
    #       readiness_state, gin indexes on legacy_aliases / required_connectors /
    #       role_visibility, no rows yet)
    # 008 = full 77-slug / 80-alias seed rendered from
    #       backend/app/data/quick_actions_catalog.py via
    #       backend/scripts/_build_catalog_migration.py; upserted
    #       idempotently via jsonb_to_recordset + ON CONFLICT DO UPDATE
    "006_ai_chat_and_prompts.sql",
    "007_ai_action_catalog.sql",
    "008_ai_action_catalog_seed.sql",
    # ── Session 2 (feat/canonical-connectors) lane: 009–022 ──────────────
    # Bumped one slot forward from the original 008–021 plan to clear room
    # for Session 1's 008_ai_action_catalog_seed.sql once that lane landed
    # on main. Maps 1:1 to the charter's 002–013 + 023–024 migrations with
    # a +7 offset. See docs/roadmaps/baseline-reconciliation.md §4.
    "009_rbac_roles_permissions.sql",           # charter 002
    "010_user_roles_preferences.sql",           # charter 003
    "011_project_assignment_bridges.sql",       # charter 004
    "012_connector_registry.sql",               # charter 005
    "013_connector_procore_stage.sql",          # charter 006
    "014_connector_exxir_stage.sql",            # charter 007
    "015_sync_runs_and_source_links.sql",       # charter 008
    "016_canonical_core_additions.sql",         # charter 009
    "017_canonical_pm_additions.sql",           # charter 010
    "018_canonical_financial_additions.sql",    # charter 011
    "019_canonical_schedule_additions.sql",     # charter 012
    "020_canonical_docs_quality_additions.sql", # charter 013
    "021_seed_roles_and_aliases.sql",           # charter 023 (role/alias part)
    "022_canonical_read_views.sql",             # charter 024 (read-view part)
    # ── Phase 4 (feat/phase4-procore-rex-app) lane ───────────────────────
    # 024 = unique (project_id, rfi_number) on rex.rfis so the Procore
    #       orchestrator's ON CONFLICT upsert has a matching constraint.
    "024_rex_rfis_project_rfi_number_unique.sql",
    # ── Phase 4a (feat/phase4a-resource-rollout) lane ────────────────────
    # 025 = unique (project_number) on rex.projects so the projects
    #       resource orchestrator's ON CONFLICT upsert has a matching
    #       constraint (Task 2 of Phase 4a).
    "025_rex_projects_project_number_unique.sql",
    # 026 = unique (email) on rex.people so the users resource
    #       orchestrator's ON CONFLICT upsert has a matching constraint
    #       (Task 3 of Phase 4a).
    "026_rex_people_email_unique.sql",
    # 027 = unique (name) on rex.companies + create
    #       connector_procore.vendors_raw staging table so the vendors
    #       resource orchestrator's ON CONFLICT (name) upsert has a
    #       matching constraint and a place to stage raw payloads
    #       (Task 4 of Phase 4a).
    "027_rex_companies_name_unique_and_vendors_raw.sql",
    # ── Phase 6a (feat/phase6a-commands-approvals-core) lane ─────────────
    # 028 = rex.action_queue table backing the command + approval
    #       lifecycle. Every LLM tool_use invocation lands a row here
    #       (auto_committed, pending_approval, committed, dismissed,
    #       undone, failed, pending_retry). FKs to rex.chat_conversations
    #       and rex.chat_messages are added in idempotent DO blocks so
    #       chat-table renames don't wedge the whole migration.
    "028_rex_action_queue.sql",
    # 029 = rex.notes table backing the create_note quick action. A
    #       deliberately minimal free-form notes surface (id, project_id,
    #       user_account_id, content, created_at, updated_at). Decisions
    #       get their own heavier schema in rex.pending_decisions — notes
    #       stay separate for MVP clarity.
    "029_rex_notes.sql",
]

# ── Optional demo data (Phase 41) ─────────────────────────────────────────
#
# Intentionally NOT part of MIGRATION_ORDER. Gated by REX_DEMO_SEED at the
# Python layer so production can safely run schema migrations without ever
# touching the demo data set. Applied via ``apply_demo_seed()`` below.

DEMO_SEED_FILE: str = "rex2_demo_seed.sql"

# Supplemental demo seeds applied after ``DEMO_SEED_FILE`` under the same
# ``REX_DEMO_SEED`` gate. Each file must be idempotent on its own because
# supplementals are retried on every boot when the env var is set. These
# are NEVER registered in ``MIGRATION_ORDER`` — they ship demo data only
# and must not run on production schema-migration passes.
SUPPLEMENTAL_DEMO_SEEDS: tuple[str, ...] = (
    "023_bishop_modern_dashboard_seed.sql",
)

def _find_migrations_dir() -> Path:
    """Locate the migrations directory robustly across local + container layouts.

    Tries (in order):
      1. ``REX_MIGRATIONS_DIR`` env var (explicit override for prod)
      2. <repo-root>/migrations (computed from this file's location)
      3. <cwd>/migrations  (when uvicorn is started from backend/)
      4. <cwd>/../migrations  (when uvicorn is started from backend/)
      5. /migrations  (if Nixpacks puts repo contents at /)
      6. /app/migrations  (if Nixpacks puts repo at /app/)

    Returns the first existing directory; falls back to (2) so missing-file
    warnings still log a stable path.
    """
    import os
    env = os.getenv("REX_MIGRATIONS_DIR")
    if env:
        return Path(env)

    candidates: list[Path] = [
        Path(__file__).resolve().parent.parent.parent / "migrations",
        Path.cwd() / "migrations",
        Path.cwd().parent / "migrations",
        Path("/migrations"),
        Path("/app/migrations"),
    ]
    for p in candidates:
        if p.is_dir():
            return p
    return candidates[0]


MIGRATIONS_DIR = _find_migrations_dir()

log = logging.getLogger("rex.migrate")


class MigrationResult:
    """Outcome of a single migration file execution."""

    __slots__ = ("filename", "status", "detail")

    def __init__(self, filename: str, status: str, detail: str = ""):
        self.filename = filename
        self.status = status
        self.detail = detail

    def to_dict(self) -> dict:
        d: dict = {"file": self.filename, "status": self.status}
        if self.detail:
            d["detail"] = self.detail
        return d


def get_planned_migrations(
    migrations_dir: Path | None = None,
) -> list[dict]:
    """Return the ordered list of migration files and whether each exists.

    Used by ``--dry-run`` / ``--list`` and by the admin HTTP endpoint.
    """
    base = migrations_dir or MIGRATIONS_DIR
    results: list[dict] = []
    for filename in MIGRATION_ORDER:
        path = base / filename
        results.append({
            "file": filename,
            "exists": path.is_file(),
            "path": str(path),
        })
    return results


async def apply_migrations(
    *,
    migrations_dir: Path | None = None,
    dry_run: bool = False,
) -> list[MigrationResult]:
    """Execute all migrations in order. Returns per-file results.

    Stops on the first failure so later files never run against a
    partially-applied schema. If ``dry_run`` is True, log the plan
    without touching the DB.
    """
    # Lazy-import to avoid loading DB config at module level
    import db as legacy_db

    base = migrations_dir or MIGRATIONS_DIR
    results: list[MigrationResult] = []

    if dry_run:
        for filename in MIGRATION_ORDER:
            path = base / filename
            status = "planned" if path.is_file() else "missing"
            results.append(MigrationResult(filename, status))
            log.info("  [%s] %s", status, filename)
        return results

    pool = await legacy_db.get_pool()

    for filename in MIGRATION_ORDER:
        path = base / filename
        if not path.is_file():
            res = MigrationResult(filename, "missing")
            results.append(res)
            log.warning("Migration file not found: %s", path)
            continue

        sql = path.read_text(encoding="utf-8")
        try:
            async with pool.acquire() as conn:
                await conn.execute(sql)
            res = MigrationResult(filename, "ok")
            results.append(res)
            log.info("Migration applied: %s", filename)
        except Exception as exc:
            res = MigrationResult(filename, "error", str(exc).splitlines()[0])
            results.append(res)
            log.error("Migration FAILED: %s — %s", filename, res.detail)
            break  # stop on first failure

    return results


async def apply_demo_seed(
    *,
    migrations_dir: Path | None = None,
) -> MigrationResult:
    """Apply the optional demo data seed (Bishop Modern) if enabled.

    Gated at the Python layer (not MIGRATION_ORDER) so production deploys
    can safely run schema migrations without pulling in demo rows. The
    underlying SQL file is idempotent (``ON CONFLICT DO NOTHING``) so
    re-running is safe.
    """
    import db as legacy_db

    base = migrations_dir or MIGRATIONS_DIR
    path = base / DEMO_SEED_FILE
    if not path.is_file():
        log.warning("Demo seed file not found: %s", path)
        return MigrationResult(DEMO_SEED_FILE, "missing")

    sql = path.read_text(encoding="utf-8")
    pool = await legacy_db.get_pool()
    try:
        async with pool.acquire() as conn:
            await conn.execute(sql)
        log.info("Demo seed applied: %s", DEMO_SEED_FILE)
        primary = MigrationResult(DEMO_SEED_FILE, "ok")
    except Exception as exc:
        detail = str(exc).splitlines()[0]
        log.error("Demo seed FAILED: %s — %s", DEMO_SEED_FILE, detail)
        return MigrationResult(DEMO_SEED_FILE, "error", detail)

    # Supplemental demo seeds (idempotent, log-only). Failures here are
    # non-fatal: the primary seed has already landed and callers only
    # reason about the primary result, so a supplemental hiccup must not
    # poison the boot path. Each file is still gated by REX_DEMO_SEED
    # because we're inside ``apply_demo_seed``.
    for filename in SUPPLEMENTAL_DEMO_SEEDS:
        supp_path = base / filename
        if not supp_path.is_file():
            log.warning("Supplemental demo seed not found: %s", supp_path)
            continue
        try:
            supp_sql = supp_path.read_text(encoding="utf-8")
            async with pool.acquire() as conn:
                await conn.execute(supp_sql)
            log.info("Supplemental demo seed applied: %s", filename)
        except Exception as exc:  # noqa: BLE001
            log.error(
                "Supplemental demo seed FAILED: %s — %s",
                filename,
                str(exc).splitlines()[0],
            )

    return primary


# ── CLI entry point ───────────────────────────────────────────────────────


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    dry_run = "--dry-run" in sys.argv or "--list" in sys.argv

    if dry_run:
        log.info("Planned migration order:")
        asyncio.run(apply_migrations(dry_run=True))
    else:
        log.info("Applying migrations …")
        results = asyncio.run(apply_migrations())
        failed = [r for r in results if r.status == "error"]
        if failed:
            log.error("Migration run failed. Aborting.")
            sys.exit(1)
        log.info(
            "Migration run complete: %d applied, %d missing, %d errors.",
            sum(1 for r in results if r.status == "ok"),
            sum(1 for r in results if r.status == "missing"),
            len(failed),
        )


if __name__ == "__main__":
    main()
