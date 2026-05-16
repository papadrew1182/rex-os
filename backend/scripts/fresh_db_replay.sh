#!/usr/bin/env bash
set -euo pipefail

# Fresh DB replay harness for Rex OS (local only).
# - No production writes
# - Creates/uses a local postgres database
# - Applies full migration chain
# - Runs survivability checks
# - Emits artifacts for handoffs/PR evidence

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
ART_BASE="$ROOT_DIR/docs/ops/runtime"
STAMP="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
ART_DIR="$ART_BASE/${STAMP}_fresh_db_replay"

DB_HOST="127.0.0.1"
DB_PORT="5432"
DB_USER="rex"
DB_PASS="rex"
DB_NAME="rex_os_fresh"
DB_URL="postgresql://${DB_USER}:${DB_PASS}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

mkdir -p "$ART_DIR"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

log "artifact_dir=$ART_DIR"
log "repo_root=$ROOT_DIR"

if ! command -v psql >/dev/null 2>&1; then
  log "ERROR: psql not found. Install postgresql client/server first."
  exit 1
fi

if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl start postgresql || true
fi

# Ensure role/database exist.
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';"

sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"

# Hard reset db for deterministic replay.
PGPASSWORD="$DB_PASS" dropdb --if-exists -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME"
PGPASSWORD="$DB_PASS" createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME"

cd "$BACKEND_DIR"
export DATABASE_URL="$DB_URL"

log "running migrate dry-run"
python -m app.migrate --dry-run 2>&1 | tee "$ART_DIR/01_migrate_dry_run.log"

log "running migrate apply"
python -m app.migrate 2>&1 | tee "$ART_DIR/02_migrate_apply.log"

log "running survivability tests"
pytest -q tests/test_proxy_headers_regression.py 2>&1 | tee "$ART_DIR/03_proxy_headers_test.log"
pytest -q tests/test_session2_views_and_endpoints.py 2>&1 | tee "$ART_DIR/04_session2_views_test.log"
pytest -q tests/test_assistant_live_db_smoke.py 2>&1 | tee "$ART_DIR/05_assistant_live_db_smoke.log"

log "collecting schema metrics"
python - <<'PY' 2>&1 | tee "$ART_DIR/06_schema_metrics.txt"
import os, asyncio, asyncpg

async def main():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    tables = await conn.fetchval("select count(*) from information_schema.tables where table_schema='rex'")
    views = await conn.fetchval("select count(*) from information_schema.views where table_schema='rex'")
    seed_users = await conn.fetchval("select count(*) from rex.user_accounts")
    print(f"rex_tables={tables}")
    print(f"rex_views={views}")
    print(f"rex_user_accounts={seed_users}")
    await conn.close()

asyncio.run(main())
PY

cat > "$ART_DIR/00_summary.txt" <<EOF
fresh_db_replay: PASS
timestamp_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)
database_url: $DB_URL
artifact_dir: $ART_DIR
EOF

log "fresh db replay complete"
log "summary=$ART_DIR/00_summary.txt"
