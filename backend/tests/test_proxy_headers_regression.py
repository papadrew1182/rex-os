"""Regression tests for proxy-header / slash-redirect mis-handling.

Background
----------
Rex OS is deployed behind Railway's edge proxy. Railway terminates TLS at the
edge and forwards requests to the backend with ``X-Forwarded-Proto: https``
from an internal IP (not 127.0.0.1). Uvicorn's default ``--forwarded-allow-ips``
is 127.0.0.1 only, so without explicit trust the forwarded-proto header is
ignored and ``request.url.scheme`` falls back to ``http``.

The concrete symptom: FastAPI's trailing-slash redirect emits a
``Location: http://...`` header, and HTTPS frontends (Vercel) silently drop
the redirect as Mixed Content. The entire deployed app appeared dead.

Commit ``2671b23`` fixed this by mounting ``ProxyHeadersMiddleware(trusted_hosts="*")``
in ``main.py``. These tests lock that fix in so a regression fails CI instead
of re-breaking production.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from starlette.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware


def test_proxy_headers_middleware_is_mounted_on_main_app():
    """The ProxyHeadersMiddleware must be present on the top-level app.

    We don't assert trusted_hosts here because Starlette's middleware stack
    wraps options at build time; we just confirm the class is in the chain.
    Removing it would instantly re-break Railway deploys.
    """
    from main import app

    middleware_classes = [m.cls for m in app.user_middleware]
    assert ProxyHeadersMiddleware in middleware_classes, (
        "ProxyHeadersMiddleware missing from main.app — Railway redirects "
        "will downgrade to http:// and break HTTPS frontends."
    )


def test_forwarded_proto_updates_scope_scheme_when_trusted():
    """When trusted_hosts='*', X-Forwarded-Proto: https must update the scope.

    This is the canonical ProxyHeadersMiddleware behavior we rely on.
    We build a minimal app to isolate the middleware from the rest of
    Rex OS — this test should pass even if main.app is refactored, as
    long as the middleware contract itself is unchanged.
    """
    inner = FastAPI()
    inner.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

    @inner.get("/scheme")
    async def _scheme(request: Request):
        return {"scheme": request.url.scheme}

    with TestClient(inner) as client:
        r = client.get("/scheme", headers={"X-Forwarded-Proto": "https"})
    assert r.status_code == 200
    assert r.json()["scheme"] == "https", (
        "ProxyHeadersMiddleware did not honor X-Forwarded-Proto — the "
        "Railway proxy fix would not work."
    )


def test_slash_redirect_preserves_https_scheme_under_proxy_headers():
    """End-to-end invariant: a 307 slash redirect must emit a https:// Location.

    Builds a tiny inner app with a single trailing-slash route and the same
    middleware as production, then hits the no-slash path with
    X-Forwarded-Proto: https. The Location header must be https://, never
    http:// — that was the exact regression observed on Railway.
    """
    inner = FastAPI()  # redirect_slashes defaults to True
    inner.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

    @inner.get("/thing/")
    async def _thing():
        return {"ok": True}

    with TestClient(inner) as client:
        r = client.get(
            "/thing",
            headers={"X-Forwarded-Proto": "https", "Host": "rex.example"},
            follow_redirects=False,
        )

    assert r.status_code in (307, 308), (
        f"Expected trailing-slash redirect, got {r.status_code}"
    )
    location = r.headers.get("location", "")
    assert location, "Redirect response missing Location header"
    assert not location.startswith("http://"), (
        f"Slash redirect downgraded scheme to http://: {location!r}"
    )
    # Either absolute https or a relative/path-only redirect is acceptable —
    # the regression we're locking out is specifically http://.
    if "://" in location:
        assert location.startswith("https://"), (
            f"Redirect Location has non-https absolute scheme: {location!r}"
        )


async def test_health_endpoint_is_reachable_on_main_app(client):
    """Belt-and-braces: /api/health must always be 200 and cheap.

    Uses the session-scoped ``client`` fixture so we don't churn the shared
    asyncpg pool (sync TestClient would trigger a lifespan shutdown and
    break any session-scoped test that runs after us).
    """
    r = await client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
