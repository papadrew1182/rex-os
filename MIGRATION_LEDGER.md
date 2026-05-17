# MIGRATION_LEDGER

Last Updated (UTC): 2026-05-16 15:12:35Z

## Session 1B Policy
- No migration creation/modification.
- No schema changes.

## Observed Migration State
- `backend/app/migrate.py::MIGRATION_ORDER` includes entries through:
  - `034_rex_inspections_project_number_unique.sql`
- Dry-run plan command executed successfully:
  - `python -m app.migrate --dry-run`

## Fresh-DB Replay Rule
- Mandatory before any destructive migration planning/execution.
- Must be captured as artifact in future migration-affecting PRs.
