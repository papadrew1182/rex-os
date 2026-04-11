import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import db
from app.routes import all_routers

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


app = FastAPI(title="Rex OS", version="0.2.0", lifespan=lifespan)


# ── CORS ────────────────────────────────────────────────────────────────────
#
# ``REX_CORS_ORIGINS`` (env var, comma-separated):
#   Allowed origins. Default in development: ``http://localhost:5173`` (Vite)
#   plus ``http://localhost:3000``.
#
#   In production set this to the actual frontend domain(s):
#     REX_CORS_ORIGINS=https://app.rexos.com,https://staging.rexos.com
#
#   The wildcard ``*`` is deliberately NOT the default so a misconfigured
#   production deploy fails closed rather than open.

_DEFAULT_DEV_ORIGINS = "http://localhost:5173,http://localhost:3000"
_cors_raw = os.getenv("REX_CORS_ORIGINS", _DEFAULT_DEV_ORIGINS)
CORS_ORIGINS: list[str] = [o.strip() for o in _cors_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Ops endpoints (/api/health, /api/ready) are mounted via app.routes.ops


# ── Admin: run migrations ────────────────────────────────────────────────────

from app.migrate import apply_migrations


@app.get("/api/admin/migrate")
async def run_migrations(secret: str = ""):
    if secret != MIGRATE_SECRET:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Invalid secret")

    results = await apply_migrations()
    return {"migrations": [r.to_dict() for r in results]}


# ── Foundation routers ───────────────────────────────────────────────────────

for router in all_routers:
    app.include_router(router)


# ── Serve frontend (must be last) ────────────────────────────────────────────

FRONTEND_ASSETS = os.path.join(FRONTEND_DIST, "assets")
FRONTEND_INDEX = os.path.join(FRONTEND_DIST, "index.html")

if os.path.isdir(FRONTEND_ASSETS) and os.path.isfile(FRONTEND_INDEX):
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=FRONTEND_ASSETS), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        return FileResponse(FRONTEND_INDEX)
