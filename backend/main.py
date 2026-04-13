import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

import db
from app.rate_limit import limiter
from app.routes import all_routers

load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


# ── Sentry (Phase 44) ──────────────────────────────────────────────────────
#
# Optional backend error tracking. Gated by REX_SENTRY_DSN so local/dev and
# any deploy without a DSN stay silent (no background network, no startup
# slowdown). Must initialize BEFORE ``FastAPI()`` so Sentry's integrations
# can hook ASGI send/receive.

_sentry_dsn = os.getenv("REX_SENTRY_DSN", "").strip()
if _sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=_sentry_dsn,
            integrations=[StarletteIntegration(), FastApiIntegration()],
            traces_sample_rate=float(os.getenv("REX_SENTRY_TRACES", "0.0")),
            environment=os.getenv("ENVIRONMENT", "production"),
            release=(
                os.getenv("REX_RELEASE")
                or os.getenv("RAILWAY_GIT_COMMIT_SHA")
                or os.getenv("GITHUB_SHA")
                or None
            ),
            send_default_pii=False,
        )
        log.info("sentry initialized dsn_host=%s", _sentry_dsn.split("@")[-1].split("/")[0])
    except Exception as exc:  # noqa: BLE001
        log.error("sentry init failed error=%r", exc)

MIGRATE_SECRET = os.getenv("MIGRATE_SECRET", "rex-migrate-2026")
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Rex OS starting up")
    await db.get_pool()

    # Auto-apply migrations on startup if REX_AUTO_MIGRATE=true.
    # Used by Railway deploys so a fresh container picks up new schema.
    if os.getenv("REX_AUTO_MIGRATE", "").lower() in ("1", "true", "yes"):
        try:
            from app.migrate import apply_migrations
            log.info("REX_AUTO_MIGRATE enabled — applying migrations")
            results = await apply_migrations()
            applied = sum(1 for r in results if r.status == "ok")
            failed = [r for r in results if r.status == "error"]
            log.info("auto_migrate complete applied=%d failed=%d", applied, len(failed))
            for r in failed:
                log.error("auto_migrate failed file=%s detail=%s", r.filename, r.detail)
        except Exception as exc:  # noqa: BLE001
            log.error("auto_migrate exception error=%r", exc)

    # Optional demo data seed for canonical Bishop Modern project.
    # Independent from REX_AUTO_MIGRATE so production can run schema
    # migrations without importing demo rows.
    if os.getenv("REX_DEMO_SEED", "").lower() in ("1", "true", "yes"):
        try:
            from app.migrate import apply_demo_seed
            log.info("REX_DEMO_SEED enabled — applying demo data")
            res = await apply_demo_seed()
            log.info("demo_seed complete file=%s status=%s", res.filename, res.status)
            if res.status == "error":
                log.error("demo_seed failed detail=%s", res.detail)
        except Exception as exc:  # noqa: BLE001
            log.error("demo_seed exception error=%r", exc)

    # Start background job scheduler if enabled
    try:
        from app.jobs import start_scheduler
        await start_scheduler()
    except Exception as exc:  # noqa: BLE001
        log.error("scheduler_start_failed error=%r", exc)
    yield
    try:
        from app.jobs import shutdown_scheduler
        await shutdown_scheduler()
    except Exception:
        pass
    log.info("Rex OS shutting down")
    await db.close_pool()


app = FastAPI(title="Rex OS", version="0.2.0", lifespan=lifespan)

# Rate limiter (Phase 44). The Limiter instance lives in app.rate_limit so
# routers can decorate individual endpoints without importing this module.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


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

# Trust X-Forwarded-Proto from Railway's edge so FastAPI emits https:// slash
# redirects instead of http:// ones. Required because uvicorn's default
# --forwarded-allow-ips is 127.0.0.1 only, and Railway's edge proxies from a
# different internal IP. Without this, HTTPS frontends silently fail on any
# endpoint that triggers FastAPI's trailing-slash redirect.
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")


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
