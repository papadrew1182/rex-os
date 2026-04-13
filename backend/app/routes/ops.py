"""Operational endpoints: liveness and readiness.

- ``GET /api/health`` is a **liveness** probe. It says nothing about whether
  the app can actually serve traffic — only that the process is running and
  able to handle an HTTP request. It must be cheap and dependency-free so a
  transient DB outage does not cause a liveness-failure restart loop.

- ``GET /api/ready`` is a **readiness** probe. It checks that the dependencies
  the app needs to *serve* traffic (database, storage boundary) are usable.
  Non-ready returns ``503`` with a per-check breakdown so operators can see
  which dependency is degraded. It never exposes secrets or raw error text
  that could leak connection details.
"""

import os
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import async_session_factory
from app.services.storage import StorageConfigError, get_storage

router = APIRouter(prefix="/api", tags=["ops"])


# Backend build identity. Resolved once at import time so ``/api/version`` is
# cheap and doesn't re-read env on every call.
_BACKEND_VERSION = "0.2.0"
_BACKEND_COMMIT = (
    os.getenv("REX_RELEASE")
    or os.getenv("RAILWAY_GIT_COMMIT_SHA")
    or os.getenv("GITHUB_SHA")
    or "dev"
)
_BACKEND_BUILD_TIME = os.getenv("REX_BUILD_TIME", "")
_BACKEND_ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


@router.get("/health")
async def health() -> dict:
    """Liveness: process is up and event loop is responsive.

    No DB, no storage — just "yes I can answer HTTP". Cheap on purpose.
    """
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/version")
async def version() -> dict:
    """Release identity for the running backend.

    Used by operators + the deployed-smoke workflow to verify *which* build
    is actually serving traffic. Intentionally unauthenticated and cheap so
    it works from curl at any time.

    Populated from platform-provided env vars at import time:
      - ``REX_RELEASE`` (explicit override)
      - ``RAILWAY_GIT_COMMIT_SHA`` (Railway builds)
      - ``GITHUB_SHA`` (GitHub Actions)
      - falls back to ``dev``
    """
    return {
        "service": "rex-os-backend",
        "version": _BACKEND_VERSION,
        "commit": _BACKEND_COMMIT,
        "build_time": _BACKEND_BUILD_TIME,
        "environment": _BACKEND_ENVIRONMENT,
    }


def _safe_error(exc: Exception) -> str:
    """Strip exception text down to a safe, operator-useful string.

    We deliberately do not embed the connection URL or raw driver output
    in the response — just the class name and a short summary.
    """
    name = type(exc).__name__
    detail = str(exc).splitlines()[0] if str(exc) else ""
    return f"{name}: {detail}" if detail else name


async def _check_db() -> dict:
    try:
        async with async_session_factory() as session:
            result = await session.execute(text("SELECT 1"))
            value = result.scalar_one()
        return {"ok": value == 1}
    except Exception as exc:  # noqa: BLE001 — readiness swallows errors
        return {"ok": False, "error": _safe_error(exc)}


def _check_storage() -> dict:
    try:
        adapter = get_storage()
        adapter.healthcheck()
        return {"ok": True, "backend": adapter.scheme}
    except StorageConfigError as exc:
        return {"ok": False, "error": _safe_error(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": _safe_error(exc)}


@router.get("/ready")
async def ready() -> JSONResponse:
    """Readiness: all the dependencies required to serve traffic are usable.

    Returns ``200`` when every check passes, ``503`` with a per-check
    breakdown otherwise.
    """
    checks = {
        "db": await _check_db(),
        "storage": _check_storage(),
    }
    all_ok = all(c.get("ok") for c in checks.values())
    body = {
        "status": "ready" if all_ok else "not_ready",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return JSONResponse(content=body, status_code=200 if all_ok else 503)
