import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import db

load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

MIGRATE_SECRET = os.getenv("MIGRATE_SECRET", "rex-migrate-2026")
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Rex OS starting up")
    await db.get_pool()
    yield
    log.info("Rex OS shutting down")
    await db.close_pool()


app = FastAPI(title="Rex OS", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ──────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT NOW() AS ts, current_schema() AS schema")
    return {"status": "ok", "db_time": str(row["ts"]), "schema": row["schema"]}


# ── Admin: run migrations ────────────────────────────────────────────────────

MIGRATION_ORDER: list[str] = [
    "001_create_schema.sql",
]


@app.get("/api/admin/migrate")
async def run_migrations(secret: str = ""):
    if secret != MIGRATE_SECRET:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Invalid secret")

    import pathlib
    migrations_dir = pathlib.Path(__file__).parent.parent / "migrations"
    pool = await db.get_pool()
    results = []

    for filename in MIGRATION_ORDER:
        path = migrations_dir / filename
        if not path.exists():
            results.append({"file": filename, "status": "missing"})
            continue
        sql = path.read_text()
        try:
            async with pool.acquire() as conn:
                await conn.execute(sql)
            results.append({"file": filename, "status": "ok"})
            log.info(f"Migration applied: {filename}")
        except Exception as e:
            results.append({"file": filename, "status": "error", "detail": str(e)})
            log.error(f"Migration failed: {filename} — {e}")

    return {"migrations": results}


# ── Serve frontend (must be last) ────────────────────────────────────────────

if os.path.isdir(FRONTEND_DIST):
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
