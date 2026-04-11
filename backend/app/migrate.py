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
    "001_create_schema.sql",
    "rex2_canonical_ddl.sql",
    "rex2_foundation_bootstrap.sql",
    "rex2_business_seed.sql",
]

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "migrations"

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
